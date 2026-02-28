from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from handlers.states import AddRentalFSM, ReturnRentalFSM
from services.tool_service import get_all_tools, get_tool_by_id
from services.rental_service import (
    create_rental, get_active_rentals, search_rentals,
    get_rental_by_id, get_rental_items, calculate_rental_cost,
    calculate_return_cost, get_already_paid, process_return,
    close_rental, is_fully_returned, get_unreturned_items
)
from services.debt_service import add_debt, record_payment
from utils.texts import *
from utils.keyboards import (
    rentals_menu, cancel_keyboard,
    rental_tools_selection_keyboard, rental_confirmation_keyboard,
    rental_list_keyboard, rental_return_type_keyboard,
    payment_type_keyboard, yes_no_keyboard
)
from utils.helpers import (
    validate_phone, validate_positive_int,
    validate_positive_float, format_number, format_date
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import get_db

router = Router()


def check_user(db_user):
    return db_user is not None and db_user["is_active"]


# ── inline keyboard builder used only inside this file ──────────────

def _items_keyboard(items: list, staged_ids: set) -> InlineKeyboardMarkup:
    """Inline keyboard of unreturned items, excluding already-staged ones."""
    from aiogram.types import InlineKeyboardMarkup
    builder = InlineKeyboardBuilder()
    for item in items:
        if item["id"] not in staged_ids:
            remaining = item["quantity"] - item["returned_quantity"]
            if remaining > 0:
                builder.button(
                    text=f"🔧 {item['tool_name']}  ({remaining} dona)",
                    callback_data=f"ri:{item['id']}"
                )
    builder.adjust(1)
    return builder.as_markup()


def _payment_text(total: float, paid: float, remaining: float) -> str:
    lines = ["💰 Hisob-kitob:\n",
             f"📊 Jami:            {format_number(total)} so'm"]
    if paid > 0:
        lines.append(f"✅ To'langan:       {format_number(paid)} so'm")
    lines.append(f"💳 To'lanishi kerak: {format_number(remaining)} so'm")
    lines.append("\nTo'lov turini tanlang:")
    return "\n".join(lines)


def _staged_ids(partial_returns: list) -> set:
    return {r["item_id"] for r in partial_returns}


async def _go_payment(target, state: FSMContext,
                      rental_id: int, cost: float, paid: float):
    """Set payment state and send payment summary."""
    remaining = round(max(cost - paid, 0.0), 2)
    await state.update_data(
        return_rental_id=rental_id,
        return_cost=cost,
        already_paid=paid,
        remaining_balance=remaining,
    )
    await state.set_state(ReturnRentalFSM.payment)
    # target can be Message or CallbackQuery.message
    msg = target if isinstance(target, Message) else target
    await msg.answer(
        _payment_text(cost, paid, remaining),
        reply_markup=payment_type_keyboard(rental_id)
    )


# ================================================================
# NAVIGATION  (clears any stale FSM state)
# ================================================================

@router.message(F.text == BTN_RENTALS)
async def rentals_menu_handler(message: Message, state: FSMContext, db_user):
    if not check_user(db_user):
        await message.answer(MSG_NO_ACCESS)
        return
    await state.clear()
    await message.answer(MSG_RENTALS_MENU, reply_markup=rentals_menu())


# ================================================================
# ADD RENTAL
# ================================================================

@router.message(F.text == BTN_ADD_RENTAL)
async def add_rental_start(message: Message, state: FSMContext, db_user):
    if not check_user(db_user):
        return
    await state.clear()
    await state.set_state(AddRentalFSM.customer_name)
    await message.answer(MSG_RENTAL_CUSTOMER_NAME, reply_markup=cancel_keyboard())


@router.message(AddRentalFSM.customer_name)
async def _add_rental_name(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        return await message.answer(MSG_CANCELLED, reply_markup=rentals_menu())
    await state.update_data(customer_name=message.text.strip())
    await state.set_state(AddRentalFSM.customer_address)
    await message.answer(MSG_RENTAL_CUSTOMER_ADDRESS, reply_markup=cancel_keyboard())


@router.message(AddRentalFSM.customer_address)
async def _add_rental_address(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        return await message.answer(MSG_CANCELLED, reply_markup=rentals_menu())
    await state.update_data(customer_address=message.text.strip())
    await state.set_state(AddRentalFSM.customer_phone)
    await message.answer(MSG_RENTAL_CUSTOMER_PHONE, reply_markup=cancel_keyboard())


@router.message(AddRentalFSM.customer_phone)
async def _add_rental_phone(message: Message, state: FSMContext, db_user):
    if message.text == BTN_CANCEL:
        await state.clear()
        return await message.answer(MSG_CANCELLED, reply_markup=rentals_menu())
    if not validate_phone(message.text):
        return await message.answer(MSG_INVALID_PHONE)
    tools = await get_all_tools(db_user["id"])
    available = [t for t in tools if t["quantity"] > 0]
    if not available:
        await state.clear()
        return await message.answer("❌ Mavjud asboblar yo'q.", reply_markup=rentals_menu())
    await state.update_data(customer_phone=message.text.strip(), selected_tools={})
    await state.set_state(AddRentalFSM.select_tools)
    await message.answer(MSG_SELECT_TOOL_FOR_RENTAL,
                         reply_markup=rental_tools_selection_keyboard(available))


@router.callback_query(AddRentalFSM.select_tools, F.data.startswith("rental_tool:"))
async def _add_rental_tool(callback: CallbackQuery, state: FSMContext, db_user):
    action = callback.data.split(":")[1]
    if action == "done":
        data = await state.get_data()
        if not data.get("selected_tools"):
            return await callback.answer("❌ Kamida bitta asbob tanlang!", show_alert=True)
        await state.set_state(AddRentalFSM.confirm)
        await _show_summary(callback.message, data)
        return await callback.answer()
    tool_id = int(action)
    tool = await get_tool_by_id(tool_id)
    if not tool:
        return await callback.answer("Topilmadi")
    await state.update_data(current_tool_id=tool_id)
    await state.set_state(AddRentalFSM.tool_quantity)
    await callback.message.answer(
        MSG_TOOL_QTY_FOR_RENTAL.format(name=tool["name"], available=tool["quantity"]),
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(AddRentalFSM.tool_quantity)
async def _add_rental_tool_qty(message: Message, state: FSMContext, db_user):
    data = await state.get_data()
    if message.text == BTN_CANCEL:
        await state.set_state(AddRentalFSM.select_tools)
        tools = await get_all_tools(db_user["id"])
        selected = data.get("selected_tools", {})
        available = [t for t in tools if t["quantity"] > 0]
        return await message.answer(
            MSG_SELECT_TOOL_FOR_RENTAL,
            reply_markup=rental_tools_selection_keyboard(
                available, list(map(int, selected.keys())))
        )
    tool = await get_tool_by_id(data["current_tool_id"])
    qty = validate_positive_int(message.text)
    if qty is None or qty > tool["quantity"]:
        return await message.answer(MSG_TOOL_NOT_ENOUGH.format(available=tool["quantity"]))
    selected = data.get("selected_tools", {})
    selected[str(tool["id"])] = {"qty": qty, "name": tool["name"], "price": tool["daily_price"]}
    await state.update_data(selected_tools=selected)
    await state.set_state(AddRentalFSM.select_tools)
    tools = await get_all_tools(db_user["id"])
    available = [t for t in tools if t["quantity"] > 0]
    await message.answer(
        f"✅ {tool['name']} x{qty} qo'shildi.\n\n{MSG_SELECT_TOOL_FOR_RENTAL}",
        reply_markup=rental_tools_selection_keyboard(
            available, [int(k) for k in selected.keys()])
    )


async def _show_summary(message: Message, data: dict):
    tools_text, daily = "", 0.0
    for info in data.get("selected_tools", {}).values():
        tools_text += f"• {info['name']} x{info['qty']} — {format_number(info['price'])} so'm/kun\n"
        daily += float(info["price"]) * float(info["qty"])
    await message.answer(
        MSG_RENTAL_SUMMARY.format(
            customer_name=data["customer_name"],
            customer_address=data["customer_address"],
            customer_phone=data["customer_phone"],
            tools_list=tools_text,
            daily_total=format_number(daily)
        ),
        reply_markup=rental_confirmation_keyboard()
    )


@router.callback_query(AddRentalFSM.confirm, F.data.startswith("rental_confirm:"))
async def _add_rental_confirm(callback: CallbackQuery, state: FSMContext, db_user):
    action = callback.data.split(":")[1]
    data = await state.get_data()
    if action == "cancel":
        await state.clear()
        await callback.message.answer(MSG_CANCELLED, reply_markup=rentals_menu())
        return await callback.answer()
    if action == "edit":
        await state.set_state(AddRentalFSM.select_tools)
        tools = await get_all_tools(db_user["id"])
        selected = data.get("selected_tools", {})
        await callback.message.answer(
            MSG_SELECT_TOOL_FOR_RENTAL,
            reply_markup=rental_tools_selection_keyboard(
                [t for t in tools if t["quantity"] > 0],
                [int(k) for k in selected.keys()])
        )
        return await callback.answer()
    if action == "yes":
        items = [
            {"tool_id": int(tid), "quantity": info["qty"], "daily_price": info["price"]}
            for tid, info in data.get("selected_tools", {}).items()
        ]
        rental_id = await create_rental(
            user_id=db_user["id"],
            customer_name=data["customer_name"],
            customer_address=data["customer_address"],
            customer_phone=data["customer_phone"],
            items=items
        )
        await state.clear()
        msg = MSG_RENTAL_CONFIRMED if rental_id else MSG_ERROR
        await callback.message.answer(msg, reply_markup=rentals_menu())
        await callback.answer()


# ================================================================
# VIEW ACTIVE RENTALS  (no state — plain list view)
# ================================================================

@router.message(F.text == BTN_RENTAL_LIST)
async def rental_list_handler(message: Message, state: FSMContext, db_user):
    if not check_user(db_user):
        return
    await state.clear()
    rentals, total = await get_active_rentals(db_user["id"])
    if not rentals:
        return await message.answer(MSG_RENTAL_LIST_EMPTY, reply_markup=rentals_menu())
    await message.answer(
        f"📋 Faol ijaralar ({total} ta):",
        reply_markup=rental_list_keyboard(rentals)
    )


# rental_detail — only fires when NO active FSM state (i.e. from list view)
@router.callback_query(F.data.startswith("rental_detail:"))
async def cb_rental_detail(callback: CallbackQuery, state: FSMContext):
    cur = await state.get_state()
    if cur is not None:
        # Some FSM is active — ignore this stray callback silently
        return await callback.answer()

    rental_id = int(callback.data.split(":")[1])
    rental = await get_rental_by_id(rental_id)
    if not rental:
        return await callback.answer("Topilmadi")
    items = await get_rental_items(rental_id)
    total_cost = await calculate_rental_cost(rental_id)
    tools_text = ""
    for item in items:
        rem = item["quantity"] - item["returned_quantity"]
        if rem > 0:
            tools_text += f"• {item['tool_name']} x{rem} — {format_number(item['daily_price'])} so'm/kun\n"
    await callback.message.answer(
        MSG_RENTAL_DETAIL.format(
            rental_id=rental_id,
            customer_name=rental["customer_name"],
            customer_address=rental["customer_address"],
            customer_phone=rental["customer_phone"],
            rental_date=format_date(rental["rental_date"]),
            tools_list=tools_text or "—",
            total_cost=format_number(total_cost)
        )
    )
    await callback.answer()


# ================================================================
# RETURN RENTAL
# Flow:
#  BTN_RETURN_RENTAL
#    → search (text input)
#    → select_rental (tap a rental button  "rd:<id>")
#    → return_type  (To'liq / Qisman)
#      FULL  → process all → payment stage
#      PARTIAL:
#        → select_item  (tap a tool button  "ri:<item_id>")
#        → item_quantity (type number)
#        → confirm_more  ("Ha, yana bor" / "Yo'q, tugatish")
#        loop back to select_item or → finalize → payment stage
#    → payment (To'liq / Qisman)
#      FULL  → record, close if returned, done
#      PARTIAL:
#        → partial_amount (type number)
#        → record, debt if needed, done
# ================================================================

@router.message(F.text == BTN_RETURN_RENTAL)
async def return_start(message: Message, state: FSMContext, db_user):
    if not check_user(db_user):
        return
    await state.clear()
    await state.set_state(ReturnRentalFSM.search)
    await message.answer(MSG_RETURN_SEARCH, reply_markup=cancel_keyboard())


# ── STEP 1 : search ─────────────────────────────────────────────

@router.message(ReturnRentalFSM.search)
async def return_search(message: Message, state: FSMContext, db_user):
    if message.text == BTN_CANCEL:
        await state.clear()
        return await message.answer(MSG_CANCELLED, reply_markup=rentals_menu())
    rentals = await search_rentals(db_user["id"], message.text.strip())
    if not rentals:
        return await message.answer(
            MSG_NOT_FOUND + "\n\nQaytadan urinib ko'ring yoki bekor qiling.",
            reply_markup=cancel_keyboard()
        )
    await state.set_state(ReturnRentalFSM.select_rental)
    await message.answer(
        MSG_SELECT_RENTAL,
        reply_markup=_rentals_kb(rentals)   # uses "rd:" prefix — NO conflict
    )


def _rentals_kb(rentals):
    """Rental pick keyboard that uses 'rd:' prefix to avoid clashing with 'rental_detail:'."""
    builder = InlineKeyboardBuilder()
    for r in rentals:
        builder.button(
            text=f"👤 {r['customer_name']}  📞 {r['customer_phone']}",
            callback_data=f"rd:{r['id']}"
        )
    builder.adjust(1)
    return builder.as_markup()


# ── STEP 2 : select rental ──────────────────────────────────────

@router.callback_query(ReturnRentalFSM.select_rental, F.data.startswith("rd:"))
async def return_pick_rental(callback: CallbackQuery, state: FSMContext):
    rental_id = int(callback.data.split(":")[1])
    rental = await get_rental_by_id(rental_id)
    if not rental:
        return await callback.answer("Topilmadi", show_alert=True)

    await state.update_data(
        return_rental_id=rental_id,
        customer_name=rental["customer_name"],
        customer_phone=rental["customer_phone"],
        partial_returns=[],
    )
    await state.set_state(ReturnRentalFSM.return_type)
    await callback.message.answer(
        f"👤 {rental['customer_name']}  📞 {rental['customer_phone']}\n\n"
        f"Qaytarish turini tanlang:",
        reply_markup=rental_return_type_keyboard(rental_id)
    )
    await callback.answer()


# ── STEP 3a : TO'LIQ TOPSHIRISH ─────────────────────────────────

@router.callback_query(ReturnRentalFSM.return_type, F.data.startswith("return_type:full:"))
async def return_full(callback: CallbackQuery, state: FSMContext):
    rental_id = int(callback.data.split(":")[2])
    items = await get_unreturned_items(rental_id)
    if not items:
        await state.clear()
        await callback.message.answer(
            "⚠️ Bu ijarada qaytariladigan asbob qolmagan.",
            reply_markup=rentals_menu()
        )
        return await callback.answer()

    returns = [
        {"item_id": it["id"], "tool_id": it["tool_id"],
         "quantity": it["quantity"] - it["returned_quantity"]}
        for it in items
    ]
    cost = await calculate_return_cost(rental_id, returns)
    await process_return(rental_id, returns)
    paid = await get_already_paid(rental_id)

    await state.update_data(return_rental_id=rental_id)
    await _go_payment(callback.message, state, rental_id, cost, paid)
    await callback.answer()


# ── STEP 3b : QISMAN TOPSHIRISH — start ─────────────────────────

@router.callback_query(ReturnRentalFSM.return_type, F.data.startswith("return_type:partial:"))
async def return_partial_start(callback: CallbackQuery, state: FSMContext):
    rental_id = int(callback.data.split(":")[2])
    items = await get_unreturned_items(rental_id)
    if not items:
        await state.clear()
        await callback.message.answer(
            "⚠️ Bu ijarada qaytariladigan asbob qolmagan.",
            reply_markup=rentals_menu()
        )
        return await callback.answer()

    await state.update_data(return_rental_id=rental_id, partial_returns=[])
    await state.set_state(ReturnRentalFSM.select_item)
    await callback.message.answer(
        MSG_SELECT_TOOL_TO_RETURN,
        reply_markup=_items_keyboard(items, staged_ids=set())
    )
    await callback.answer()


# ── STEP 3b : select which tool ─────────────────────────────────

@router.callback_query(ReturnRentalFSM.select_item, F.data.startswith("ri:"))
async def return_pick_item(callback: CallbackQuery, state: FSMContext):
    item_id = int(callback.data.split(":")[1])

    async with get_db() as conn:
        item = await conn.fetchrow(
            "SELECT ri.*, t.name AS tool_name FROM rental_items ri JOIN tools t ON t.id = ri.tool_id WHERE ri.id = $1",
            item_id
        )

    if not item:
        return await callback.answer("Topilmadi", show_alert=True)

    max_ret = item["quantity"] - item["returned_quantity"]
    await state.update_data(current_return_item_id=item_id)
    await state.set_state(ReturnRentalFSM.item_quantity)
    await callback.message.answer(
        f"🔧 <b>{item['tool_name']}</b>\n"
        f"Berilgan: {item['quantity']} dona\n"
        f"Qaytarilgan: {item['returned_quantity']} dona\n"
        f"Qaytarish mumkin: <b>{max_ret}</b> dona\n\n"
        f"Nechta qaytariladi? (1–{max_ret})",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


# ── STEP 3b : enter quantity ─────────────────────────────────────

@router.message(ReturnRentalFSM.item_quantity)
async def return_item_qty(message: Message, state: FSMContext):
    data = await state.get_data()
    rental_id = data["return_rental_id"]
    item_id = data["current_return_item_id"]

    if message.text == BTN_CANCEL:
        # discard current item selection, back to tool list
        await state.set_state(ReturnRentalFSM.select_item)
        staged = _staged_ids(data.get("partial_returns", []))
        items = await get_unreturned_items(rental_id)
        avail = [i for i in items if i["id"] not in staged]
        if avail:
            return await message.answer(
                MSG_SELECT_TOOL_TO_RETURN,
                reply_markup=_items_keyboard(items, staged)
            )
        else:
            # nothing left to pick — finalize what's staged
            return await _finalize(message, state, data)

    async with get_db() as conn:
        item = await conn.fetchrow("SELECT * FROM rental_items WHERE id = $1", item_id)

    if not item:
        await state.clear()
        return await message.answer(MSG_ERROR, reply_markup=rentals_menu())

    max_qty = item["quantity"] - item["returned_quantity"]
    qty = validate_positive_int(message.text)
    if not qty or qty > max_qty:
        return await message.answer(f"❌ 1 dan {max_qty} gacha kiriting.")

    # stage it
    partial = data.get("partial_returns", [])
    existing = next((r for r in partial if r["item_id"] == item_id), None)
    if existing:
        new_q = existing["quantity"] + qty
        if new_q > max_qty:
            return await message.answer(f"❌ Jami {max_qty} dan oshib ketdi.")
        existing["quantity"] = new_q
    else:
        partial.append({"item_id": item_id, "tool_id": item["tool_id"], "quantity": qty})

    await state.update_data(partial_returns=partial)
    await state.set_state(ReturnRentalFSM.confirm_more)

    # show tool name for confirmation
    async with get_db() as conn:
        row = await conn.fetchrow(
            "SELECT t.name FROM rental_items ri JOIN tools t ON t.id=ri.tool_id WHERE ri.id=$1",
            item_id
        )
    tool_name = row["name"] if row else "Asbob"

    await message.answer(
        f"✅ <b>{tool_name}</b> — {qty} dona ro'yxatga qo'shildi.\n\n"
        f"Yana boshqa asbob qaytarasizmi?",
        parse_mode="HTML",
        reply_markup=yes_no_keyboard()
    )


# ── STEP 3b : "Yana bor?" yes ────────────────────────────────────

@router.callback_query(ReturnRentalFSM.confirm_more, F.data == "more_items:yes")
async def return_more_yes(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    rental_id = data["return_rental_id"]
    staged = _staged_ids(data.get("partial_returns", []))
    items = await get_unreturned_items(rental_id)
    avail = [i for i in items if i["id"] not in staged]

    if not avail:
        await callback.message.answer("✅ Barcha mavjud asboblar tanlandi.")
        await _finalize(callback.message, state, data)
    else:
        await state.set_state(ReturnRentalFSM.select_item)
        await callback.message.answer(
            MSG_SELECT_TOOL_TO_RETURN,
            reply_markup=_items_keyboard(items, staged)
        )
    await callback.answer()


# ── STEP 3b : "Yana bor?" no — finalize ─────────────────────────

@router.callback_query(ReturnRentalFSM.confirm_more, F.data == "more_items:no")
async def return_more_no(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await _finalize(callback.message, state, data)
    await callback.answer()


async def _finalize(msg: Message, state: FSMContext, data: dict):
    """Commit staged items → payment stage."""
    partial = data.get("partial_returns", [])
    rental_id = data["return_rental_id"]
    if not partial:
        await state.clear()
        return await msg.answer("❌ Hech narsa tanlanmadi.", reply_markup=rentals_menu())
    cost = await calculate_return_cost(rental_id, partial)
    await process_return(rental_id, partial)
    await state.update_data(partial_returns=[])
    paid = await get_already_paid(rental_id)
    await _go_payment(msg, state, rental_id, cost, paid)


# ================================================================
# PAYMENT — TO'LIQ TO'LOV
# ================================================================

@router.callback_query(ReturnRentalFSM.payment, F.data.startswith("payment:full:"))
async def payment_full(callback: CallbackQuery, state: FSMContext, db_user):
    rental_id = int(callback.data.split(":")[2])
    data = await state.get_data()
    remaining = data.get("remaining_balance", 0.0)

    if remaining > 0:
        await record_payment(db_user["id"], rental_id, remaining)

    fully_returned = await is_fully_returned(rental_id)
    if fully_returned:
        await close_rental(rental_id)
        msg = "✅ To'lov qabul qilindi. Ijara yopildi."
    else:
        msg = "✅ To'lov qabul qilindi.\n📑 Ijara faol — asboblar hali qaytarilmagan."

    await state.clear()
    await callback.message.answer(msg, reply_markup=rentals_menu())
    await callback.answer()


# ================================================================
# PAYMENT — QISMAN TO'LOV : ask amount
# ================================================================

@router.callback_query(ReturnRentalFSM.payment, F.data.startswith("payment:partial:"))
async def payment_partial_start(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    remaining = data.get("remaining_balance", 0.0)
    if remaining <= 0:
        return await callback.answer("❌ To'lanadigan summa yo'q.", show_alert=True)
    await state.set_state(ReturnRentalFSM.partial_amount)
    await callback.message.answer(
        f"💵 To'langan summani kiriting:\n"
        f"(Maksimal: {format_number(remaining)} so'm)",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(ReturnRentalFSM.partial_amount)
async def payment_partial_amount(message: Message, state: FSMContext, db_user):
    data = await state.get_data()
    rental_id = data["return_rental_id"]
    remaining = data.get("remaining_balance", 0.0)
    cost = data.get("return_cost", 0.0)
    paid = data.get("already_paid", 0.0)

    if message.text == BTN_CANCEL:
        await state.set_state(ReturnRentalFSM.payment)
        return await message.answer(
            _payment_text(cost, paid, remaining),
            reply_markup=payment_type_keyboard(rental_id)
        )

    amount = validate_positive_float(message.text)
    if not amount or amount <= 0:
        return await message.answer(
            f"❌ Noto'g'ri summa. 0 dan {format_number(remaining)} gacha kiriting."
        )
    if amount > remaining:
        return await message.answer(
            f"❌ Maksimal summa: {format_number(remaining)} so'm."
        )

    await record_payment(db_user["id"], rental_id, amount)
    debt = round(remaining - amount, 2)

    if debt > 0:
        await add_debt(
            user_id=db_user["id"],
            customer_name=data.get("customer_name", ""),
            customer_phone=data.get("customer_phone", ""),
            amount=debt,
            rental_id=rental_id
        )

    fully_returned = await is_fully_returned(rental_id)
    if fully_returned:
        await close_rental(rental_id)
        status = "📑 Ijara yopildi."
    else:
        status = "📑 Ijara faol — asboblar hali qaytarilmagan."

    await state.clear()
    if debt > 0:
        await message.answer(
            f"✅ {format_number(amount)} so'm to'landi.\n"
            f"💰 Qolgan qarz: {format_number(debt)} so'm qarzdorlikka o'tkazildi.\n"
            f"{status}",
            reply_markup=rentals_menu()
        )
    else:
        await message.answer(
            f"✅ To'lov qabul qilindi.\n{status}",
            reply_markup=rentals_menu()
        )
