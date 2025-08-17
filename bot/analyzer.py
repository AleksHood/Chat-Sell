from __future__ import annotations

import math
import re
import time
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any


FILLER_WORDS = [
    "ээ", "э-э", "эм", "мм", "ну", "вот", "как бы", "типа", "вроде", "короче",
    "значит", "это самое", "в общем", "собственно", "так сказать", "скажем так",
]
UNCERTAIN_PHRASES = [
    "наверное", "может", "может быть", "попробуем", "попробовать", "постараемся",
    "постараюсь", "надеюсь", "возможно", "скорее всего", "если что",
]
CLOSING_TRIGGERS = [
    "давайте", "готовы", "когда можем", "назначим", "встречу", "демо", "оформим",
    "вы готовы", "перешлем", "выслать", "счет", "счёт", "подписать", "закрыть",
]
VALUE_TRIGGERS = [
    "выгода", "ценность", "результат", "прибыль", "экономия", "сэкономить",
    "срок", "качество", "гарантия", "поддержка", "сервис", "кейсы", "пример",
]
PRICE_WORDS = ["цена", "стоимость", "дорого", "дешево", "дёшево", "бюджет", "смета"]
DISCOUNT_WORDS = ["скидк", "дисконт", "акци", "спецпредложение", "промо"]


@dataclass
class Turn:
    role: str  # 'seller' | 'client'
    text: str
    ts: float


@dataclass
class AnalysisResult:
    metrics: Dict[str, Any]
    strengths: List[str]
    weaknesses: List[str]
    argumentation: List[str]
    alternative_phrases: List[str]
    recommendations: List[str]


_word_re = re.compile(r"[а-яА-Яa-zA-ZёЁ0-9-']+")


def _tokenize(text: str) -> List[str]:
    return [w.lower() for w in _word_re.findall(text)]


def _count_fillers(text: str) -> int:
    lower = text.lower()
    count = 0
    for fw in FILLER_WORDS:
        count += lower.count(fw)
    return count


def _count_uncertain(text: str) -> int:
    lower = text.lower()
    c = 0
    for up in UNCERTAIN_PHRASES:
        c += lower.count(up)
    return c


def _has_closing(text: str) -> bool:
    lower = text.lower()
    return any(t in lower for t in CLOSING_TRIGGERS)


def _has_value_words(text: str) -> bool:
    lower = text.lower()
    return any(t in lower for t in VALUE_TRIGGERS)


def _div_safe(a: float, b: float) -> float:
    return a / b if b else 0.0


def analyze_conversation(transcript: List[Turn]) -> AnalysisResult:
    seller_turns = [t for t in transcript if t.role == 'seller']
    client_turns = [t for t in transcript if t.role == 'client']

    total_seller_chars = sum(len(t.text) for t in seller_turns)
    total_client_chars = sum(len(t.text) for t in client_turns)

    total_seller_msgs = len(seller_turns)
    total_client_msgs = len(client_turns)

    seller_text_full = "\n".join(t.text for t in seller_turns)

    tokens = _tokenize(seller_text_full)
    unique_tokens = set(tokens)
    ttr = _div_safe(len(unique_tokens), len(tokens))

    q_marks = seller_text_full.count("?")

    fillers = sum(_count_fillers(t.text) for t in seller_turns)
    uncertain = sum(_count_uncertain(t.text) for t in seller_turns)

    closing_attempts = sum(1 for t in seller_turns if _has_closing(t.text))
    value_mentions = sum(1 for t in seller_turns if _has_value_words(t.text))

    price_focus = sum(1 for t in seller_turns if any(w in t.text.lower() for w in PRICE_WORDS))
    discount_focus = sum(1 for t in seller_turns if any(w in t.text.lower() for w in DISCOUNT_WORDS))

    # Pauses: time gap > 30s from seller to seller
    seller_pauses = 0
    prev_ts = None
    for t in seller_turns:
        if prev_ts is not None and t.ts - prev_ts > 30.0:
            seller_pauses += 1
        prev_ts = t.ts

    # Repetitiveness: most common token frequency
    token_counts = Counter(tokens)
    most_common_freq = token_counts.most_common(1)[0][1] if token_counts else 0
    repetitiveness = _div_safe(most_common_freq, len(tokens))

    talk_ratio = _div_safe(total_seller_chars, total_seller_chars + total_client_chars)

    metrics = {
        "seller_messages": total_seller_msgs,
        "client_messages": total_client_msgs,
        "seller_talk_ratio": round(talk_ratio, 3),
        "question_count": q_marks,
        "type_token_ratio": round(ttr, 3),
        "filler_words": fillers,
        "uncertain_phrases": uncertain,
        "closing_attempts": closing_attempts,
        "value_mentions": value_mentions,
        "price_mentions": price_focus,
        "discount_mentions": discount_focus,
        "long_pauses": seller_pauses,
        "repetitiveness": round(repetitiveness, 3),
    }

    strengths: List[str] = []
    weaknesses: List[str] = []
    argumentation: List[str] = []
    alternative_phrases: List[str] = []
    recommendations: List[str] = []

    # Strengths
    if metrics["seller_talk_ratio"] < 0.6:
        strengths.append("Соблюдён баланс: вы не доминировали в разговоре.")
    if metrics["question_count"] >= 3:
        strengths.append("Хороший уровень уточняющих вопросов.")
    if metrics["type_token_ratio"] >= 0.45:
        strengths.append("Достаточное разнообразие формулировок.")
    if metrics["value_mentions"] >= 2:
        strengths.append("Фокус на ценности и результате для клиента.")

    # Weaknesses
    if metrics["filler_words"] > 0:
        weaknesses.append(f"Слова-паразиты: {metrics['filler_words']}. Сократите их количество.")
    if metrics["uncertain_phrases"] > 0:
        weaknesses.append(f"Неуверенные конструкции: {metrics['uncertain_phrases']}. Формулируйте увереннее.")
    if metrics["long_pauses"] > 0:
        weaknesses.append(f"Длинные паузы: {metrics['long_pauses']}. Готовьте ключевые блоки заранее.")
    if metrics["repetitiveness"] > 0.08:
        weaknesses.append("Речь однообразна. Используйте больше синонимов и примеров.")
    if metrics["closing_attempts"] == 0:
        weaknesses.append("Нет попыток закрытия сделки/следующего шага.")

    # Argumentation
    if metrics["price_mentions"] > metrics["value_mentions"]:
        argumentation.append("Сместите фокус с цены на ценность и бизнес-результат.")
    if metrics["discount_mentions"] > 0 and metrics["value_mentions"] == 0:
        argumentation.append("Перед обсуждением скидок проговорите ценность и кейсы.")
    if metrics["question_count"] < 3:
        argumentation.append("Задавайте больше открытых вопросов для выявления потребностей.")

    # Alternative phrasings suggestions
    alternative_pairs = [
        ("может быть, вам будет интересно", "уверен, это решит задачу X: давайте покажу как"),
        ("попробуем", "предлагаю конкретный шаг: созвон завтра в 11:00 на 15 минут"),
        ("если что, напишу", "подтвержу детали на почту и пришлю счёт сегодня"),
        ("цена высокая", "окупаемость за N месяцев благодаря A, B, C"),
    ]
    for weak, strong in alternative_pairs:
        if weak in seller_text_full.lower():
            alternative_phrases.append(f"Вместо ‘{weak}’ используйте более предметно: ‘{strong}’.")

    # Recommendations
    if metrics["closing_attempts"] == 0:
        recommendations.append("Завершайте блок призывом к действию: договоритесь о следующем шаге и сроке.")
    if metrics["question_count"] < 3:
        recommendations.append("Подготовьте список из 5-7 вопросов для диагностики потребностей.")
    if metrics["type_token_ratio"] < 0.4:
        recommendations.append("Расширьте словарь: добавьте 10-15 синонимов к основным выгодам.")
    if metrics["value_mentions"] < 2:
        recommendations.append("Используйте кейсы/цифры: эффект, сроки, экономия, гарантии.")

    return AnalysisResult(
        metrics=metrics,
        strengths=strengths,
        weaknesses=weaknesses,
        argumentation=argumentation,
        alternative_phrases=alternative_phrases,
        recommendations=recommendations,
    )


def format_feedback_report(analysis: AnalysisResult) -> str:
    m = analysis.metrics
    lines: List[str] = []
    lines.append("Итоги тренировки\n")
    lines.append("Метрики:")
    lines.append(f"- Сообщений продавца: {m['seller_messages']}")
    lines.append(f"- Сообщений клиента: {m['client_messages']}")
    lines.append(f"- Доля речи продавца: {int(m['seller_talk_ratio']*100)}%")
    lines.append(f"- Вопросительные конструкции: {m['question_count']}")
    lines.append(f"- Разнообразие речи (TTR): {m['type_token_ratio']}")
    lines.append(f"- Слова-паразиты: {m['filler_words']}")
    lines.append(f"- Неуверенные конструкции: {m['uncertain_phrases']}")
    lines.append(f"- Попытки закрытия: {m['closing_attempts']}")
    lines.append(f"- Упоминания ценности: {m['value_mentions']}")

    if analysis.strengths:
        lines.append("\nСильные стороны:")
        for s in analysis.strengths:
            lines.append(f"- {s}")

    if analysis.weaknesses:
        lines.append("\nЗоны роста:")
        for w in analysis.weaknesses:
            lines.append(f"- {w}")

    if analysis.argumentation:
        lines.append("\nГде усилить аргументацию:")
        for a in analysis.argumentation:
            lines.append(f"- {a}")

    if analysis.alternative_phrases:
        lines.append("\nАльтернативные формулировки:")
        for a in analysis.alternative_phrases:
            lines.append(f"- {a}")

    if analysis.recommendations:
        lines.append("\nРекомендации:")
        for r in analysis.recommendations:
            lines.append(f"- {r}")

    return "\n".join(lines)