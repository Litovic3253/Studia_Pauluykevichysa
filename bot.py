"""Telegram-бот для учёта заказов на 3D-печать."""
import asyncio
import logging
import os
import re
import socket
from datetime import date, datetime
from html import escape

from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    ErrorEvent,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from dotenv import load_dotenv

import db
from pricing import (
    calc_price,
    deadline_mark,
    fmt_date,
    money,
    parse_date,
    parse_hours,
    parse_number,
    price_breakdown,
    recalc_order_price,
)

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ENV_ADMIN_IDS = {int(x) for x in re.findall(r"\d+", os.getenv("ADMIN_IDS", ""))}

router = Router()


class IPv4AiohttpSession(AiohttpSession):
    """AiohttpSession без IPv6: у части провайдеров/сетей маршрут до
    api.telegram.org по IPv6 «висит» и роняет запрос по таймауту (WinError 121),
    хотя IPv4 доступен нормально."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._connector_init["family"] = socket.AF_INET

BTN_NEW = "➕ Новый заказ"
BTN_ORDERS = "📋 Заказы"
BTN_CALC = "🧮 Калькулятор"
BTN_STATS = "📊 Статистика"
BTN_PRICES = "⚙️ Цены"
BTN_SKIP = "⏭ Пропустить"
BTN_CANCEL = "❌ Отмена"

MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_NEW), KeyboardButton(text=BTN_ORDERS)],
        [KeyboardButton(text=BTN_CALC), KeyboardButton(text=BTN_STATS), KeyboardButton(text=BTN_PRICES)],
    ],
    resize_keyboard=True,
)
SKIP_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_SKIP), KeyboardButton(text=BTN_CANCEL)]],
    resize_keyboard=True,
)
CANCEL_KB = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_CANCEL)]], resize_keyboard=True)


# ---------- доступ только владельцу ----------

def owner_ids() -> set[int]:
    return ENV_ADMIN_IDS or set(db.get_settings()["owners"])


class OwnerOnly(BaseMiddleware):
    """Пропускает только владельцев. Если владелец не задан — им становится первый, кто напишет боту."""

    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user is None:
            return None
        owners = owner_ids()
        if not owners:
            db.set_setting("owners", [user.id])
            logging.info("Владелец бота назначен: %s (%s)", user.id, user.full_name)
            owners = {user.id}
        if user.id not in owners:
            if isinstance(event, Message):
                await event.answer("⛔ Это приватный бот.")
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔ Нет доступа", show_alert=True)
            return None
        return await handler(event, data)


# ---------- утилиты ----------


def order_card(o) -> str:
    lines = [
        f"<b>Заказ #{o['id']}</b> — {db.STATUSES.get(o['status'], o['status'])}",
        f"👤 {escape(o['client'])}" + (f" · {escape(o['contact'])}" if o["contact"] else ""),
    ]
    if o["description"]:
        lines.append(f"📝 {escape(o['description'])}")
    lines.append(
        f"🧵 {escape(o['material'] or '—')}" + (f", {escape(o['color'])}" if o["color"] else "")
        + f" · {o['weight_g']:g} г · {o['print_hours']:g} ч · {o['qty']} шт."
    )
    mark = deadline_mark(o)
    lines.append(f"📅 Срок: {fmt_date(o['deadline'])}" + (f" ({mark})" if mark else ""))
    lines.append(
        f"💰 {money(o['price'])} · "
        + ("✅ оплачен" if o["paid"] else "💸 не оплачен")
    )
    if o["file_id"]:
        lines.append("📎 Файл прикреплён")
    elif o["reverse_engineering"]:
        lines.append("🔧 Реверс-моделирование")
    if o["notes"]:
        lines.append(f"🗒 {escape(o['notes'])}")
    lines.append(f"<i>Создан {datetime.fromisoformat(o['created_at']).strftime('%d.%m.%Y %H:%M')}</i>")
    return "\n".join(lines)


def order_kb(o) -> InlineKeyboardMarkup:
    oid = o["id"]
    status_buttons = [
        InlineKeyboardButton(text=label, callback_data=f"o:st:{oid}:{code}")
        for code, label in db.STATUSES.items()
        if code != o["status"]
    ]
    rows = [status_buttons[i:i + 2] for i in range(0, len(status_buttons), 2)]
    rows.append([
        InlineKeyboardButton(
            text="↩️ Снять оплату" if o["paid"] else "💵 Оплачен", callback_data=f"o:paid:{oid}"
        ),
        InlineKeyboardButton(text="✏️ Цена", callback_data=f"o:price:{oid}"),
    ])
    extra = [
        InlineKeyboardButton(text="📅 Срок", callback_data=f"o:dl:{oid}"),
        InlineKeyboardButton(text="🗒 Заметка", callback_data=f"o:note:{oid}"),
    ]
    if o["file_id"]:
        extra.append(InlineKeyboardButton(text="📎 Файл", callback_data=f"o:file:{oid}"))
    rows.append(extra)
    rows.append([InlineKeyboardButton(
        text="🔧 Убрать реверс-модел." if o["reverse_engineering"] else "🔧 + Реверс-модел.",
        callback_data=f"o:reverse:{oid}",
    )])
    rows.append([InlineKeyboardButton(text="✏️ Изменить", callback_data=f"o:edit:{oid}")])
    rows.append([
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"o:del:{oid}"),
        InlineKeyboardButton(text="⬅️ К списку", callback_data="l:active"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def materials_kb(prefix: str) -> InlineKeyboardMarkup:
    names = list(db.get_settings()["materials"])
    buttons = [InlineKeyboardButton(text=n, callback_data=f"{prefix}:{n}") for n in names]
    return InlineKeyboardMarkup(inline_keyboard=[buttons[i:i + 3] for i in range(0, len(buttons), 3)])


EDIT_FIELDS = [
    ("client", "👤 Клиент"), ("contact", "📱 Контакт"),
    ("desc", "📝 Описание"), ("color", "🎨 Цвет"),
    ("weight", "⚖️ Вес"), ("hours", "⏱ Время"), ("qty", "🔢 Кол-во"),
]


def edit_menu_kb(oid: int) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=label, callback_data=f"o:{code}:{oid}") for code, label in EDIT_FIELDS]
    buttons.insert(2, InlineKeyboardButton(text="🧵 Материал", callback_data=f"o:matmenu:{oid}"))
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"o:view:{oid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def order_materials_kb(oid: int) -> InlineKeyboardMarkup:
    names = list(db.get_settings()["materials"])
    buttons = [InlineKeyboardButton(text=n, callback_data=f"o:mat:{oid}:{n}") for n in names]
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"o:edit:{oid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


LIST_TITLES = {"active": "Активные", "unpaid": "Неоплаченные", "done": "Завершённые", "all": "Все"}


def list_kb(kind: str, orders) -> InlineKeyboardMarkup:
    filters = [
        InlineKeyboardButton(text=("• " if k == kind else "") + title, callback_data=f"l:{k}")
        for k, title in LIST_TITLES.items()
    ]
    rows = [filters[:2], filters[2:]]
    for o in orders:
        mark = deadline_mark(o)
        label = (
            f"#{o['id']} {db.STATUSES[o['status']].split()[0]} {o['client']} · {money(o['price'])}"
            + ("" if o["paid"] else " 💸")
            + (f" · {mark}" if mark else "")
        )
        rows.append([InlineKeyboardButton(text=label[:60], callback_data=f"o:view:{o['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def list_text(kind: str, orders) -> str:
    if not orders:
        return f"<b>{LIST_TITLES[kind]} заказы</b>\n\nПусто."
    total = sum(o["price"] for o in orders)
    return f"<b>{LIST_TITLES[kind]} заказы</b> ({len(orders)} шт., на {money(total)})\n\nВыберите заказ:"


# ---------- общие команды ----------

HELP = (
    "<b>Бот для заказов 3D-печати</b>\n\n"
    f"{BTN_NEW} — оформить заказ с расчётом цены\n"
    f"{BTN_ORDERS} — список, смена статуса, оплата\n"
    f"{BTN_CALC} — быстро прикинуть стоимость\n"
    f"{BTN_STATS} — выручка, долги, расход пластика\n"
    f"{BTN_PRICES} — тарифы\n\n"
    "<b>Команды</b>\n"
    "/find текст — поиск по клиенту, описанию, заметкам\n"
    "/order 12 — открыть заказ №12\n"
    "/setprice PLA 4000 — цена материала за кг (новое имя = новый материал)\n"
    "/delmaterial TPU — убрать материал\n"
    "/sethour 50 — стоимость часа печати\n"
    "/setreverse 1000 — цена реверс-моделирования (если нет STL)\n"
    "/cancel — прервать текущее действие\n\n"
    "Каждое утро бот пришлёт сводку по срокам."
)


@router.message(CommandStart())
@router.message(Command("help"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(HELP, reply_markup=MAIN_KB)


@router.message(StateFilter("*"), Command("cancel"))
@router.message(StateFilter("*"), F.text == BTN_CANCEL)
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено.", reply_markup=MAIN_KB)


# ---------- новый заказ ----------

class NewOrder(StatesGroup):
    client = State()
    contact = State()
    description = State()
    file = State()
    reverse = State()
    material = State()
    color = State()
    weight = State()
    hours = State()
    qty = State()
    deadline = State()
    confirm = State()
    custom_price = State()


def is_skip(message: Message) -> bool:
    return (message.text or "").strip() in (BTN_SKIP, "-", "—")


@router.message(StateFilter(None), F.text == BTN_NEW)
@router.message(StateFilter(None), Command("new"))
async def new_start(message: Message, state: FSMContext):
    await state.set_state(NewOrder.client)
    await message.answer("👤 Имя клиента?", reply_markup=CANCEL_KB)


@router.message(NewOrder.client, F.text)
async def new_client(message: Message, state: FSMContext):
    await state.update_data(client=message.text.strip())
    await state.set_state(NewOrder.contact)
    await message.answer("📱 Контакт (телефон, @username)?", reply_markup=SKIP_KB)


@router.message(NewOrder.contact, F.text)
async def new_contact(message: Message, state: FSMContext):
    await state.update_data(contact=None if is_skip(message) else message.text.strip())
    await state.set_state(NewOrder.description)
    await message.answer("📝 Что печатаем? (описание, размеры, пожелания)", reply_markup=SKIP_KB)


@router.message(NewOrder.description, F.text)
async def new_description(message: Message, state: FSMContext):
    await state.update_data(description=None if is_skip(message) else message.text.strip())
    await state.set_state(NewOrder.file)
    await message.answer("📎 Пришлите модель (STL/3MF/OBJ) или фото/эскиз.", reply_markup=SKIP_KB)


@router.message(NewOrder.file, F.document | F.photo | F.text)
async def new_file(message: Message, state: FSMContext):
    if message.document:
        await state.update_data(file_id=message.document.file_id, file_type="document", reverse_engineering=False)
        if not (await state.get_data()).get("description"):
            await state.update_data(description=message.document.file_name)
    elif message.photo:
        await state.update_data(file_id=message.photo[-1].file_id, file_type="photo", reverse_engineering=False)
    elif not is_skip(message):
        await message.answer("Пришлите файл или нажмите «Пропустить».")
        return
    else:
        await state.set_state(NewOrder.reverse)
        s = db.get_settings()
        await message.answer(
            f"🔧 Нет STL-модели — нужно реверс-моделирование? (+{money(s['reverse_price'])})",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Да", callback_data="nr:yes"),
                InlineKeyboardButton(text="Нет", callback_data="nr:no"),
            ]]),
        )
        return
    await state.set_state(NewOrder.material)
    await message.answer("🧵 Материал:", reply_markup=materials_kb("nm"))


@router.callback_query(NewOrder.reverse, F.data.in_({"nr:yes", "nr:no"}))
async def new_reverse(call: CallbackQuery, state: FSMContext):
    reverse = call.data == "nr:yes"
    await state.update_data(reverse_engineering=reverse)
    await call.message.edit_text("🔧 Реверс-моделирование: " + ("да" if reverse else "нет"))
    await state.set_state(NewOrder.material)
    await call.message.answer("🧵 Материал:", reply_markup=materials_kb("nm"))
    await call.answer()


@router.callback_query(NewOrder.material, F.data.startswith("nm:"))
async def new_material(call: CallbackQuery, state: FSMContext):
    material = call.data.split(":", 1)[1]
    await state.update_data(material=material)
    await call.message.edit_text(f"🧵 Материал: <b>{escape(material)}</b>")
    await state.set_state(NewOrder.color)
    await call.message.answer("🎨 Цвет?", reply_markup=SKIP_KB)
    await call.answer()


@router.message(NewOrder.material)
async def new_material_text(message: Message):
    await message.answer("Выберите материал кнопкой выше (добавить новый: /setprice Имя цена).")


@router.message(NewOrder.color, F.text)
async def new_color(message: Message, state: FSMContext):
    await state.update_data(color=None if is_skip(message) else message.text.strip())
    await state.set_state(NewOrder.weight)
    await message.answer("⚖️ Вес одной детали в граммах (из слайсера)?", reply_markup=CANCEL_KB)


@router.message(NewOrder.weight, F.text)
async def new_weight(message: Message, state: FSMContext):
    value = parse_number(message.text)
    if value is None:
        await message.answer("Нужно число, например 45 или 12,5")
        return
    await state.update_data(weight_g=value)
    await state.set_state(NewOrder.hours)
    await message.answer("⏱ Время печати одной детали? (2.5 / 2:30 / 2ч 30м)")


@router.message(NewOrder.hours, F.text)
async def new_hours(message: Message, state: FSMContext):
    value = parse_hours(message.text)
    if value is None:
        await message.answer("Не понял время. Примеры: 3, 2.5, 2:30, 1ч 15м")
        return
    await state.update_data(print_hours=round(value, 2))
    await state.set_state(NewOrder.qty)
    await message.answer(
        "🔢 Количество штук?",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="1"), KeyboardButton(text="2"), KeyboardButton(text="5")],
                      [KeyboardButton(text=BTN_CANCEL)]],
            resize_keyboard=True,
        ),
    )


@router.message(NewOrder.qty, F.text)
async def new_qty(message: Message, state: FSMContext):
    value = parse_number(message.text)
    if not value or value != int(value):
        await message.answer("Нужно целое число больше нуля.")
        return
    await state.update_data(qty=int(value))
    await state.set_state(NewOrder.deadline)
    await message.answer("📅 Срок сдачи? (25.09, 25.09.2026, завтра)", reply_markup=SKIP_KB)


@router.message(NewOrder.deadline, F.text)
async def new_deadline(message: Message, state: FSMContext):
    if is_skip(message):
        deadline = None
    else:
        deadline = parse_date(message.text)
        if deadline is None:
            await message.answer("Не понял дату. Пример: 25.09 или 25.09.2026")
            return
    data = await state.update_data(deadline=deadline)
    p = calc_price(
        data["material"], data["weight_g"], data["print_hours"], data["qty"],
        data.get("reverse_engineering", False),
    )
    await state.update_data(cost=round(p["cost"], 2), price=p["price"])
    await state.set_state(NewOrder.confirm)
    await show_confirm(message, state)


async def show_confirm(message: Message, state: FSMContext):
    d = await state.get_data()
    text = (
        "<b>Проверьте заказ</b>\n\n"
        f"👤 {escape(d['client'])}" + (f" · {escape(d['contact'])}" if d.get("contact") else "") + "\n"
        + (f"📝 {escape(d['description'])}\n" if d.get("description") else "")
        + f"🧵 {escape(d['material'])}" + (f", {escape(d['color'])}" if d.get("color") else "") + "\n"
        f"📅 Срок: {fmt_date(d.get('deadline'))}\n"
        + ("📎 Файл прикреплён\n" if d.get("file_id") else "")
        + ("🔧 Реверс-моделирование\n" if d.get("reverse_engineering") else "")
        + "\n" + price_breakdown(
            d["material"], d["weight_g"], d["print_hours"], d["qty"], d.get("reverse_engineering", False)
        )
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Сохранить", callback_data="nc:save")],
        [InlineKeyboardButton(text="✏️ Своя цена", callback_data="nc:price"),
         InlineKeyboardButton(text="❌ Отмена", callback_data="nc:cancel")],
    ])
    await message.answer("Почти готово 👇", reply_markup=MAIN_KB)
    await message.answer(text, reply_markup=kb)


@router.callback_query(NewOrder.confirm, F.data == "nc:save")
async def new_save(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    order_id = db.add_order(data)
    await state.clear()
    await call.message.edit_reply_markup(reply_markup=None)
    o = db.get_order(order_id)
    await call.message.answer(f"✅ Заказ #{order_id} сохранён!\n\n" + order_card(o), reply_markup=order_kb(o))
    await call.answer()


@router.callback_query(NewOrder.confirm, F.data == "nc:price")
async def new_custom_price(call: CallbackQuery, state: FSMContext):
    await state.set_state(NewOrder.custom_price)
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer("Введите цену заказа:", reply_markup=CANCEL_KB)
    await call.answer()


@router.message(NewOrder.custom_price, F.text)
async def new_custom_price_value(message: Message, state: FSMContext):
    value = parse_number(message.text)
    if value is None:
        await message.answer("Нужно число.")
        return
    await state.update_data(price=value)
    await state.set_state(NewOrder.confirm)
    await show_confirm(message, state)


@router.callback_query(NewOrder.confirm, F.data == "nc:cancel")
async def new_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Заказ отменён.")
    await call.answer()


# ---------- список и карточка заказа ----------

@router.message(StateFilter(None), F.text == BTN_ORDERS)
@router.message(StateFilter(None), Command("orders"))
async def orders_list(message: Message):
    orders = db.list_orders("active")
    await message.answer(list_text("active", orders), reply_markup=list_kb("active", orders))


@router.callback_query(F.data.startswith("l:"))
async def orders_filter(call: CallbackQuery):
    kind = call.data.split(":")[1]
    orders = db.list_orders(kind)
    await call.message.edit_text(list_text(kind, orders), reply_markup=list_kb(kind, orders))
    await call.answer()


@router.message(StateFilter(None), Command("find"))
async def orders_find(message: Message, command: CommandObject):
    if not command.args:
        await message.answer("Использование: /find Иван")
        return
    orders = db.search_orders(command.args.strip())
    if not orders:
        await message.answer("Ничего не найдено.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"#{o['id']} {db.STATUSES[o['status']].split()[0]} {o['client']} · {money(o['price'])}"[:60],
            callback_data=f"o:view:{o['id']}",
        )]
        for o in orders
    ])
    await message.answer(f"Найдено: {len(orders)}", reply_markup=kb)


@router.message(StateFilter(None), Command("order"))
async def order_open(message: Message, command: CommandObject):
    if not command.args or not command.args.strip().lstrip("#").isdigit():
        await message.answer("Использование: /order 12")
        return
    o = db.get_order(int(command.args.strip().lstrip("#")))
    if not o:
        await message.answer("Заказ не найден.")
        return
    await message.answer(order_card(o), reply_markup=order_kb(o))


async def refresh_card(call: CallbackQuery, order_id: int, note: str = ""):
    o = db.get_order(order_id)
    if not o:
        await call.message.edit_text("Заказ удалён.")
        return
    await call.message.edit_text(order_card(o), reply_markup=order_kb(o))
    await call.answer(note)


@router.callback_query(F.data.startswith("o:view:"))
async def order_view(call: CallbackQuery):
    await refresh_card(call, int(call.data.split(":")[2]))


@router.callback_query(F.data.startswith("o:st:"))
async def order_status(call: CallbackQuery):
    _, _, oid, status = call.data.split(":")
    db.update_order(int(oid), status=status)
    await refresh_card(call, int(oid), f"Статус: {db.STATUSES[status]}")


@router.callback_query(F.data.startswith("o:paid:"))
async def order_paid(call: CallbackQuery):
    oid = int(call.data.split(":")[2])
    o = db.get_order(oid)
    if not o:
        await call.answer("Заказ не найден", show_alert=True)
        return
    db.update_order(oid, paid=0 if o["paid"] else 1)
    await refresh_card(call, oid, "Оплата снята" if o["paid"] else "Отмечено как оплачено")


@router.callback_query(F.data.startswith("o:reverse:"))
async def order_reverse(call: CallbackQuery):
    oid = int(call.data.split(":")[2])
    o = db.get_order(oid)
    if not o:
        await call.answer("Заказ не найден", show_alert=True)
        return
    s = db.get_settings()
    turn_on = not o["reverse_engineering"]
    delta = s["reverse_price"] if turn_on else -s["reverse_price"]
    db.update_order(oid, reverse_engineering=turn_on, price=o["price"] + delta)
    await refresh_card(call, oid, "Реверс-моделирование добавлено" if turn_on else "Реверс-моделирование убрано")


@router.callback_query(F.data.startswith("o:edit:"))
async def order_edit_menu(call: CallbackQuery):
    oid = int(call.data.split(":")[2])
    if not db.get_order(oid):
        await call.answer("Заказ не найден", show_alert=True)
        return
    await call.message.edit_reply_markup(reply_markup=edit_menu_kb(oid))
    await call.answer()


@router.callback_query(F.data.startswith("o:matmenu:"))
async def order_material_menu(call: CallbackQuery):
    oid = int(call.data.split(":")[2])
    await call.message.edit_reply_markup(reply_markup=order_materials_kb(oid))
    await call.answer()


@router.callback_query(F.data.startswith("o:mat:"))
async def order_material_set(call: CallbackQuery):
    _, _, oid, name = call.data.split(":", 3)
    oid = int(oid)
    db.update_order(oid, material=name)
    recalc_order_price(oid)
    await refresh_card(call, oid, f"Материал: {name}")


@router.callback_query(F.data.startswith("o:file:"))
async def order_file(call: CallbackQuery):
    o = db.get_order(int(call.data.split(":")[2]))
    if not o or not o["file_id"]:
        await call.answer("Файла нет", show_alert=True)
        return
    caption = f"Заказ #{o['id']} — {o['client']}"
    if o["file_type"] == "photo":
        await call.message.answer_photo(o["file_id"], caption=caption)
    else:
        await call.message.answer_document(o["file_id"], caption=caption)
    await call.answer()


@router.callback_query(F.data.startswith("o:del:"))
async def order_delete_ask(call: CallbackQuery):
    oid = call.data.split(":")[2]
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🗑 Да, удалить", callback_data=f"o:delok:{oid}"),
        InlineKeyboardButton(text="Нет", callback_data=f"o:view:{oid}"),
    ]])
    await call.message.edit_reply_markup(reply_markup=kb)
    await call.answer("Удалить заказ безвозвратно?")


@router.callback_query(F.data.startswith("o:delok:"))
async def order_delete(call: CallbackQuery):
    oid = int(call.data.split(":")[2])
    db.delete_order(oid)
    await call.message.edit_text(f"🗑 Заказ #{oid} удалён.")
    await call.answer()


class EditOrder(StatesGroup):
    value = State()


EDIT_PROMPTS = {
    "price": "Новая цена заказа:",
    "dl": "Новый срок (25.09 / завтра) или «-», чтобы убрать:",
    "note": "Текст заметки (или «-», чтобы удалить):",
    "client": "Имя клиента:",
    "contact": "Контакт (или «-», чтобы убрать):",
    "desc": "Что печатаем? (или «-», чтобы убрать)",
    "color": "Цвет (или «-», чтобы убрать):",
    "weight": "Вес одной детали в граммах:",
    "hours": "Время печати одной детали? (2.5 / 2:30 / 2ч 30м)",
    "qty": "Количество штук?",
}


@router.callback_query(F.data.regexp(r"^o:(price|dl|note|client|contact|desc|color|weight|hours|qty):\d+$"))
async def order_edit_start(call: CallbackQuery, state: FSMContext):
    _, field, oid = call.data.split(":")
    await state.set_state(EditOrder.value)
    await state.update_data(field=field, order_id=int(oid))
    await call.message.answer(f"Заказ #{oid}. {EDIT_PROMPTS[field]}", reply_markup=CANCEL_KB)
    await call.answer()


@router.message(EditOrder.value, F.text)
async def order_edit_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field, oid, text = data["field"], data["order_id"], message.text.strip()
    clear = text in ("-", "—")
    recalc = False
    if field == "price":
        value = parse_number(text)
        if value is None:
            await message.answer("Нужно число.")
            return
        db.update_order(oid, price=value)
    elif field == "dl":
        value = None if clear else parse_date(text)
        if value is None and not clear:
            await message.answer("Не понял дату. Пример: 25.09")
            return
        db.update_order(oid, deadline=value)
    elif field == "note":
        db.update_order(oid, notes=None if clear else text)
    elif field == "client":
        if not text:
            await message.answer("Имя не может быть пустым.")
            return
        db.update_order(oid, client=text)
    elif field == "contact":
        db.update_order(oid, contact=None if clear else text)
    elif field == "desc":
        db.update_order(oid, description=None if clear else text)
    elif field == "color":
        db.update_order(oid, color=None if clear else text)
    elif field == "weight":
        value = parse_number(text)
        if value is None or value <= 0:
            await message.answer("Нужно число больше нуля.")
            return
        db.update_order(oid, weight_g=value)
        recalc = True
    elif field == "hours":
        value = parse_hours(text)
        if value is None:
            await message.answer("Не понял время. Примеры: 3, 2.5, 2:30")
            return
        db.update_order(oid, print_hours=round(value, 2))
        recalc = True
    elif field == "qty":
        value = parse_number(text)
        if not value or value != int(value):
            await message.answer("Нужно целое число больше нуля.")
            return
        db.update_order(oid, qty=int(value))
        recalc = True
    if recalc:
        recalc_order_price(oid)
    await state.clear()
    o = db.get_order(oid)
    if not o:
        await message.answer("Заказ не найден.", reply_markup=MAIN_KB)
        return
    await message.answer("Сохранено ✅", reply_markup=MAIN_KB)
    await message.answer(order_card(o), reply_markup=order_kb(o))


# ---------- калькулятор ----------

class Calc(StatesGroup):
    material = State()
    weight = State()
    hours = State()


@router.message(StateFilter(None), F.text == BTN_CALC)
@router.message(StateFilter(None), Command("calc"))
async def calc_start(message: Message, state: FSMContext):
    await state.set_state(Calc.material)
    await message.answer("🧮 Калькулятор. Материал:", reply_markup=materials_kb("cm"))


@router.callback_query(Calc.material, F.data.startswith("cm:"))
async def calc_material(call: CallbackQuery, state: FSMContext):
    material = call.data.split(":", 1)[1]
    await state.update_data(material=material)
    await state.set_state(Calc.weight)
    await call.message.edit_text(f"🧵 {escape(material)}")
    await call.message.answer("Вес в граммах?", reply_markup=CANCEL_KB)
    await call.answer()


@router.message(Calc.weight, F.text)
async def calc_weight(message: Message, state: FSMContext):
    value = parse_number(message.text)
    if value is None:
        await message.answer("Нужно число.")
        return
    await state.update_data(weight_g=value)
    await state.set_state(Calc.hours)
    await message.answer("Время печати? (2.5 / 2:30)")


@router.message(Calc.hours, F.text)
async def calc_hours(message: Message, state: FSMContext):
    value = parse_hours(message.text)
    if value is None:
        await message.answer("Не понял время. Примеры: 3, 2.5, 2:30")
        return
    data = await state.get_data()
    await state.clear()
    await message.answer(
        f"🧮 <b>{escape(data['material'])}</b>, 1 шт.\n\n"
        + price_breakdown(data["material"], data["weight_g"], round(value, 2), 1),
        reply_markup=MAIN_KB,
    )


# ---------- статистика ----------

@router.message(StateFilter(None), F.text == BTN_STATS)
@router.message(StateFilter(None), Command("stats"))
async def stats(message: Message):
    s = db.stats()
    total = sum(s["by_status"].values())
    status_lines = "\n".join(
        f"{label}: {s['by_status'][code]}" for code, label in db.STATUSES.items() if s["by_status"].get(code)
    ) or "Заказов пока нет."
    materials = "\n".join(f"• {escape(m)}: {g / 1000:.2f} кг" for m, g in s["materials"]) or "—"
    await message.answer(
        f"<b>📊 Статистика</b>\n\n"
        f"Всего заказов: {total}\n{status_lines}\n\n"
        f"<b>Этот месяц</b>: {s['month_orders']} заказов, оплачено {money(s['month_revenue'])}\n\n"
        f"💰 Выручка (оплачено): <b>{money(s['revenue'])}</b>\n"
        f"📈 Прибыль: <b>{money(s['profit'])}</b>\n"
        f"💸 Ждём оплату: <b>{money(s['unpaid'])}</b>\n\n"
        f"<b>Расход материала</b> (всего {s['grams'] / 1000:.2f} кг)\n{materials}"
    )


# ---------- настройки цен ----------

@router.message(StateFilter(None), F.text == BTN_PRICES)
@router.message(StateFilter(None), Command("prices"))
async def prices(message: Message):
    s = db.get_settings()
    mats = "\n".join(f"• {escape(k)}: {money(v)}/кг" for k, v in s["materials"].items())
    await message.answer(
        f"<b>⚙️ Тарифы</b>\n\n{mats}\n\n"
        f"Час печати: {money(s['hour_rate'])}\n"
        f"Реверс-моделирование (без STL): {money(s['reverse_price'])}\n\n"
        "Изменить:\n/setprice PLA 4000\n/delmaterial TPU\n/sethour 50\n/setreverse 1000"
    )


@router.message(StateFilter(None), Command("setprice"))
async def set_price(message: Message, command: CommandObject):
    parts = (command.args or "").rsplit(maxsplit=1)
    value = parse_number(parts[1]) if len(parts) == 2 else None
    if value is None:
        await message.answer("Использование: /setprice PLA 1500")
        return
    s = db.get_settings()
    s["materials"][parts[0]] = value
    db.set_setting("materials", s["materials"])
    await message.answer(f"✅ {escape(parts[0])}: {money(value)}/кг")


@router.message(StateFilter(None), Command("delmaterial"))
async def del_material(message: Message, command: CommandObject):
    name = (command.args or "").strip()
    s = db.get_settings()
    if name not in s["materials"]:
        await message.answer("Такого материала нет. Список: /prices")
        return
    del s["materials"][name]
    db.set_setting("materials", s["materials"])
    await message.answer(f"🗑 {escape(name)} удалён из списка.")


def number_setting(key: str, title: str):
    async def handler(message: Message, command: CommandObject):
        value = parse_number(command.args)
        if value is None:
            await message.answer(f"Использование: /{command.command} число")
            return
        db.set_setting(key, value)
        await message.answer(f"✅ {title}: {value:g}")
    return handler


router.message(StateFilter(None), Command("sethour"))(number_setting("hour_rate", "Час печати"))
router.message(StateFilter(None), Command("setreverse"))(number_setting("reverse_price", "Реверс-моделирование"))


@router.errors()
async def on_error(event: ErrorEvent):
    # повторное нажатие той же кнопки — Telegram ругается, что сообщение не изменилось
    if isinstance(event.exception, TelegramBadRequest) and "not modified" in str(event.exception):
        if event.update.callback_query:
            await event.update.callback_query.answer()
        return True
    logging.exception("Ошибка при обработке апдейта", exc_info=event.exception)
    return None


@router.message(StateFilter(None))
async def fallback(message: Message):
    await message.answer("Выберите действие в меню 👇 или /help", reply_markup=MAIN_KB)


# ---------- утренние напоминания ----------

async def reminder_loop(bot: Bot):
    while True:
        try:
            s = db.get_settings()
            today = date.today().isoformat()
            if datetime.now().hour >= s["reminder_hour"] and s["last_reminder"] != today:
                db.set_setting("last_reminder", today)
                urgent = [
                    o for o in db.list_orders("active", limit=200)
                    if o["deadline"] and (date.fromisoformat(o["deadline"]) - date.today()).days <= 1
                ]
                if urgent:
                    text = "<b>⏰ Сроки поджимают</b>\n\n" + "\n".join(
                        f"#{o['id']} {escape(o['client'])} — {db.STATUSES[o['status']]} · {deadline_mark(o)}"
                        for o in urgent
                    )
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text=f"#{o['id']} {o['client']}"[:60], callback_data=f"o:view:{o['id']}")]
                        for o in urgent
                    ])
                    for uid in owner_ids():
                        await bot.send_message(uid, text, reply_markup=kb)
        except Exception:
            logging.exception("Ошибка в напоминаниях")
        await asyncio.sleep(600)


async def main():
    if not BOT_TOKEN:
        raise SystemExit("Не задан BOT_TOKEN. Создайте файл .env (см. .env.example).")
    db.init()
    bot = Bot(
        BOT_TOKEN,
        session=IPv4AiohttpSession(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.outer_middleware(OwnerOnly())
    dp.callback_query.outer_middleware(OwnerOnly())
    dp.include_router(router)
    await bot.set_my_commands([
        BotCommand(command="new", description="Новый заказ"),
        BotCommand(command="orders", description="Список заказов"),
        BotCommand(command="find", description="Поиск заказа"),
        BotCommand(command="calc", description="Калькулятор стоимости"),
        BotCommand(command="stats", description="Статистика"),
        BotCommand(command="prices", description="Тарифы"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="cancel", description="Отменить действие"),
    ])
    asyncio.create_task(reminder_loop(bot))
    me = await bot.get_me()
    logging.info("Бот @%s запущен", me.username)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
