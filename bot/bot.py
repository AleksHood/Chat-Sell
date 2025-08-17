from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from config import load_config
from analyzer import analyze_conversation, format_feedback_report, Turn
from scenarios import SCENARIOS, DIFFICULTIES, ConversationState, get_initial_client_message, generate_client_reply

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

CHAT_STATE: Dict[int, ConversationState] = {}
TRANSCRIPTS: Dict[int, List[Turn]] = {}


def _get_state(chat_id: int) -> ConversationState:
    st = CHAT_STATE.get(chat_id)
    if st is None:
        st = ConversationState()
        CHAT_STATE[chat_id] = st
    return st


def _add_turn(chat_id: int, role: str, text: str) -> None:
    arr = TRANSCRIPTS.get(chat_id)
    if arr is None:
        arr = []
        TRANSCRIPTS[chat_id] = arr
    arr.append(Turn(role=role, text=text, ts=time.time()))


async def start_handler(message: Message) -> None:
    chat_id = message.chat.id
    _get_state(chat_id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Выбрать сценарий", callback_data="menu:scenario")],
        [InlineKeyboardButton(text="Выбрать сложность", callback_data="menu:difficulty")],
        [InlineKeyboardButton(text="Начать тренировку", callback_data="menu:start")],
        [InlineKeyboardButton(text="Завершить и получить разбор", callback_data="menu:end")],
    ])
    await message.answer(
        "Привет! Я тренажёр продаж. Выберите сценарий и сложность, затем начните тренировку.\n\nКоманды:\n/scene — сценарий\n/level — сложность\n/train — начать\n/end — завершить",
        reply_markup=kb,
    )


async def help_handler(message: Message) -> None:
    await message.answer(
        "Доступные команды:\n/scene — выбрать сценарий\n/level — выбрать сложность\n/train — начать тренировку\n/end — завершить и получить обратную связь"
    )


async def show_scenarios(message: Message) -> None:
    buttons = [[InlineKeyboardButton(text=title, callback_data=f"scenario:{key}")]
               for key, title in SCENARIOS.items()]
    await message.answer("Выберите сценарий:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


async def show_difficulties(message: Message) -> None:
    buttons = [[InlineKeyboardButton(text=title, callback_data=f"difficulty:{key}")]
               for key, title in DIFFICULTIES.items()]
    await message.answer("Выберите сложность клиента:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


async def callback_handler(callback: CallbackQuery) -> None:
    chat_id = callback.message.chat.id if callback.message else None
    if chat_id is None:
        await callback.answer()
        return
    st = _get_state(chat_id)

    data = callback.data or ""
    if data.startswith("menu:"):
        _, action = data.split(":", 1)
        if action == "scenario":
            await show_scenarios(callback.message)
        elif action == "difficulty":
            await show_difficulties(callback.message)
        elif action == "start":
            await train_handler(callback.message)
        elif action == "end":
            await end_handler(callback.message)
        await callback.answer()
        return

    if data.startswith("scenario:"):
        _, key = data.split(":", 1)
        if key in SCENARIOS:
            st.scenario = key
            await callback.message.edit_text(f"Сценарий: {SCENARIOS[key]}")
    if data.startswith("difficulty:"):
        _, key = data.split(":", 1)
        if key in DIFFICULTIES:
            st.difficulty = key
            await callback.message.edit_text(f"Сложность: {DIFFICULTIES[key]}")
    await callback.answer()


async def train_handler(message: Message) -> None:
    chat_id = message.chat.id
    st = _get_state(chat_id)
    st.active = True
    st.stage = "intro"
    TRANSCRIPTS[chat_id] = []

    init_msg = get_initial_client_message(st.scenario, st.difficulty)
    _add_turn(chat_id, "client", init_msg)
    await message.answer(
        f"Сценарий: {SCENARIOS[st.scenario]} | Сложность: {DIFFICULTIES[st.difficulty]}\n\n{init_msg}\n\nПишите как продавец. Для завершения используйте /end"
    )


async def text_router(message: Message) -> None:
    chat_id = message.chat.id
    st = _get_state(chat_id)
    if not st.active:
        return

    user_text = (message.text or "").strip()
    if not user_text:
        return

    _add_turn(chat_id, "seller", user_text)

    reply, new_state = generate_client_reply(user_text, st)
    CHAT_STATE[chat_id] = new_state
    _add_turn(chat_id, "client", reply)

    await message.answer(reply)

    if len(TRANSCRIPTS.get(chat_id, [])) >= 30:
        await message.answer("Диалог получился длинным. Можете завершить командой /end для разбора.")


async def end_handler(message: Message) -> None:
    chat_id = message.chat.id
    st = _get_state(chat_id)
    if not st.active:
        await message.answer("Нет активной тренировки. Используйте /train чтобы начать.")
        return

    st.active = False
    transcript = TRANSCRIPTS.get(chat_id, [])
    if not transcript or all(t.role == 'client' for t in transcript):
        await message.answer("Недостаточно данных для анализа. Сначала отправьте несколько сообщений.")
        return

    analysis = analyze_conversation(transcript)
    report = format_feedback_report(analysis)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = {
        "chat_id": chat_id,
        "scenario": st.scenario,
        "difficulty": st.difficulty,
        "transcript": [{"role": t.role, "text": t.text, "ts": t.ts} for t in transcript],
        "analysis": analysis.metrics,
        "created_at": ts,
    }
    out_path = DATA_DIR / f"dialog_{chat_id}_{ts}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    await message.answer(report)


async def main() -> None:
    cfg = load_config()
    bot = Bot(token=cfg.telegram_token)
    dp = Dispatcher()

    dp.message.register(start_handler, Command(commands=["start"]))
    dp.message.register(help_handler, Command(commands=["help"]))
    dp.message.register(show_scenarios, Command(commands=["scene"]))
    dp.message.register(show_difficulties, Command(commands=["level"]))
    dp.message.register(train_handler, Command(commands=["train"]))
    dp.message.register(end_handler, Command(commands=["end"]))

    dp.callback_query.register(callback_handler)
    dp.message.register(text_router, F.text & ~F.via_bot & ~F.content_type.in_({"sticker", "photo", "video", "document"}))

    print("[bot] Starting polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        import uvloop  # type: ignore
        uvloop.install()
    except Exception:
        pass
    asyncio.run(main())