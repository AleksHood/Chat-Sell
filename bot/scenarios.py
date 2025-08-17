from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple


SCENARIOS = {
    "cold_call": "Холодный звонок",
    "office_visit": "Клиент в офисе",
    "objections": "Клиент с возражениями",
}

DIFFICULTIES = {
    "loyal": "Лояльный",
    "neutral": "Нейтральный",
    "aggressive": "Агрессивный",
}


@dataclass
class ConversationState:
    scenario: str = "cold_call"
    difficulty: str = "neutral"
    stage: str = "intro"  # intro | discovery | pitch | objection | closing
    active: bool = False


def get_initial_client_message(scenario: str, difficulty: str) -> str:
    if scenario == "cold_call":
        if difficulty == "aggressive":
            return "Алло. Кто это? У меня мало времени, говорите по делу."
        if difficulty == "loyal":
            return "Здравствуйте! Слушаю вас. Чем вы занимаетесь?"
        return "Здравствуйте. Что вы предлагаете?"
    if scenario == "office_visit":
        if difficulty == "aggressive":
            return "Вы ко мне без записи? Если кратко, что у вас за продукт?"
        if difficulty == "loyal":
            return "Добрый день! Проходите, присаживайтесь. О чём пойдёт речь?"
        return "Добрый день. Слушаю."
    if scenario == "objections":
        if difficulty == "aggressive":
            return "Сразу скажу: дорого, времени нет, скорее всего не подойдёт."
        if difficulty == "loyal":
            return "У меня есть вопросы по цене и срокам. Объясните, пожалуйста."
        return "У меня сомнения по цене и результату."
    return "Здравствуйте."


_OBJECTION_TEMPLATES = {
    "price": {
        "aggressive": [
            "Слишком дорого. Конкуренты дают дешевле.",
            "Ценник завышен. Предложите что-то реальное.",
        ],
        "neutral": [
            "Цена выше ожидаемой. А какие выгоды я получу?",
            "Есть ли гибкость по стоимости?",
        ],
        "loyal": [
            "Можно ли обсудить условия и, возможно, скидку?",
            "Поясните, как формируется цена.",
        ],
    },
    "need": {
        "aggressive": [
            "Не вижу смысла. Мы и так справляемся.",
            "Задача не приоритетная сейчас.",
        ],
        "neutral": [
            "Как это решит мою конкретную задачу?",
            "Какие результаты у ваших клиентов?",
        ],
        "loyal": [
            "Покажите, как это поможет в нашей ситуации.",
            "Есть ли кейсы из нашей отрасли?",
        ],
    },
    "time": {
        "aggressive": [
            "Нет времени на внедрение.",
            "Слишком долго. Нам надо вчера.",
        ],
        "neutral": [
            "Сколько займет внедрение?",
            "Какие сроки старта?",
        ],
        "loyal": [
            "Если начнём на этой неделе, когда будут первые результаты?",
            "Как ускорить запуск?",
        ],
    },
}


def _pick(objs: List[str]) -> str:
    return random.choice(objs)


def _difficulty_bias(difficulty: str) -> Dict[str, float]:
    if difficulty == "aggressive":
        return {"objection": 0.7, "short": 0.8}
    if difficulty == "loyal":
        return {"objection": 0.2, "short": 0.3}
    return {"objection": 0.45, "short": 0.5}


def generate_client_reply(user_message: str, state: ConversationState) -> Tuple[str, ConversationState]:
    random.seed(time.time_ns())
    bias = _difficulty_bias(state.difficulty)
    text = user_message.lower()

    # Stage transitions based on seller input
    if state.stage == "intro" and ("как" in text or "что" in text or "предлага" in text):
        state.stage = "discovery"
    if state.stage == "discovery" and ("покаж" in text or "демо" in text or "предлагаю" in text or "предлагаем" in text):
        state.stage = "pitch"
    if state.stage == "pitch" and ("цена" in text or "стоим" in text or "бюджет" in text):
        state.stage = "objection"
    if state.stage in ("pitch", "objection") and ("давайте" in text or "встреч" in text or "счет" in text or "счёт" in text or "оформ" in text):
        state.stage = "closing"

    # Objection triggers
    if any(w in text for w in ["цена", "стоим", "дорог", "дёшев", "дешев"]):
        reply = _pick(_OBJECTION_TEMPLATES["price"][state.difficulty])
        return reply, state
    if any(w in text for w in ["не нуж", "смыс", "зачем", "почему"]):
        reply = _pick(_OBJECTION_TEMPLATES["need"][state.difficulty])
        return reply, state
    if any(w in text for w in ["срок", "когда", "сколько займ", "врем"]):
        reply = _pick(_OBJECTION_TEMPLATES["time"][state.difficulty])
        return reply, state

    # Default behavior per stage
    if state.stage == "intro":
        if random.random() < bias["objection"]:
            return _pick(_OBJECTION_TEMPLATES["need"][state.difficulty]), state
        return {
            "aggressive": "Говорите конкретнее. Что именно вы продаёте?",
            "neutral": "О чём речь? Кому это может быть полезно?",
            "loyal": "Расскажите, чем это может нам помочь.",
        }[state.difficulty], state

    if state.stage == "discovery":
        if random.random() < bias["objection"]:
            return _pick(_OBJECTION_TEMPLATES["time"][state.difficulty]), state
        return {
            "aggressive": "Короче. Какие цифры и сроки?",
            "neutral": "Какие есть варианты решения?",
            "loyal": "Хорошо. А какие есть пакеты/тарифы?",
        }[state.difficulty], state

    if state.stage == "pitch":
        if random.random() < bias["objection"]:
            return _pick(_OBJECTION_TEMPLATES["price"][state.difficulty]), state
        return {
            "aggressive": "Меньше воды. Чем вы лучше конкурентов?",
            "neutral": "Есть сравнение с альтернативами?",
            "loyal": "Какие кейсы можете показать?",
        }[state.difficulty], state

    if state.stage == "objection":
        return _pick(_OBJECTION_TEMPLATES["price"][state.difficulty]), state

    if state.stage == "closing":
        return {
            "aggressive": "Пришлите КП. Посмотрим, если будет время.",
            "neutral": "Окей, пришлите материалы. Дальше обсудим.",
            "loyal": "Давайте. Готов подтвердить встречу на этой неделе.",
        }[state.difficulty], state

    return "Поясните, пожалуйста.", state