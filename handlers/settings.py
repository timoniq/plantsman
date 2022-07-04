from telegrinder import (
    Dispatch,
    Message,
    InlineKeyboard,
    InlineButton,
    CallbackQuery,
)
from telegrinder.bot.rules import Text, FuncRule

import database.user
from database.user import User
from client import bot
from tools import send_menu, search_city
from logic import SETTING_TOGGLE_RECEIVED
from keyboard.set import KeyboardSet

dp = Dispatch()


def get_kb(user: User):
    return (
        InlineKeyboard(resize_keyboard=True)
        .add(
            InlineButton(
                "Указать город" if not user.city else "Изменить/удалить город",
                callback_data="toggle_city",
            )
        )
        .row()
        .add(
            InlineButton(
                "Включить безопасный режим"
                if not user.safe_mode
                else "Выключить безопасный режим",
                callback_data="toggle_safe_mode",
            )
        )
        .row()
        .add(
            InlineButton(
                "❌ Поиск только в моем городе"
                if not user.search_city
                else "✅ Поиск только в моем городе",
                callback_data="toggle_search_city",
            )
        )
        .get_markup()
    )


def get_text(user: User):
    return (
        f"Настройки: \n"
        f"Город: {user.city_written_name if user.city else 'не указан'}\n"
        f"Поиск: {'безопасный' if user.safe_mode else 'без модерации'}, {'только в твоем городе' if user.search_city else 'где угодно'}\n"
        f"Если ты хочешь полностью сбросить свой профиль, воспользуйся командой /reset"
    )


@dp.message(Text(["/settings", "настройки"], ignore_case=True))
async def settings(m: Message, user: User):
    await m.answer(text=get_text(user), reply_markup=get_kb(user))
    await send_menu(m.chat.id)


@dp.callback_query(SETTING_TOGGLE_RECEIVED)
async def settings_set(cb: CallbackQuery):
    users = await database.user.get_full(cb.from_.id)
    if not users:
        return
    u: User = users[0]
    do_send_menu = False
    await cb.answer("Применяю.")

    if cb.data == "toggle_city":
        do_send_menu = True
        await cb.ctx_api.send_message(
            chat_id=cb.from_.id,
            text="Пришли название города, где ты располагаешься или выбери «Не указывать».",
            reply_markup=KeyboardSet.KEYBOARD_NOTSET.get_markup(),
        )
        m, _ = await bot.dispatch.message.wait_for_message(
            cb.from_.id, FuncRule(lambda event, _: bool(event["message"]["text"]))
        )
        if m.text.lower() == "не указывать":
            await database.user.set_city(m.from_.id, 0)
            await m.answer("Ты выбрал не указывать город.")
        else:
            city_id = await search_city(m.text)
            if not city_id:
                await m.reply(
                    "Такой город не найден в моей базе городов, возможно скоро он будет добавлен"
                )
                await settings(m, u)
                return
            await database.user.set_city(m.from_.id, city_id, m.text)
        await m.answer("Настройки города успешно изменены")
    elif cb.data == "toggle_search_city":
        await database.user.toggle_search_city(cb.from_.id)
    else:
        await database.user.toggle_safe_mode(cb.from_.id)

    u = (await database.user.get_full(cb.from_.id))[0]
    await cb.ctx_api.edit_message_text(
        cb.from_.id, cb.message.message_id, text=get_text(u), reply_markup=get_kb(u)
    )
    if do_send_menu:
        await send_menu(cb.from_.id)
