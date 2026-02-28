from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from handlers.states import AddDebtFSM, SearchDebtFSM, DebtPaymentFSM
from services.debt_service import (
    get_debts, search_debts, get_debt_by_id, pay_debt,
    add_debt, get_total_debt, record_payment
)
from utils.texts import *
from utils.keyboards import (
    debts_menu, cancel_keyboard, user_main_menu,
    debt_actions_keyboard, debt_pay_type_keyboard, confirm_delete_keyboard
)
from utils.helpers import validate_phone, validate_positive_float, format_number

router = Router()
PAGE_SIZE = 10


def check_user(db_user):
    return db_user is not None and db_user["is_active"]


# ===== NAVIGATION =====

@router.message(F.text == BTN_DEBTS)
async def debts_menu_handler(message: Message, db_user):
    if not check_user(db_user):
        await message.answer(MSG_NO_ACCESS)
        return
    await message.answer(MSG_DEBTS_MENU, reply_markup=debts_menu())


# ===== DEBT LIST =====

@router.message(F.text == BTN_DEBT_LIST)
async def debt_list_handler(message: Message, db_user):
    if not check_user(db_user):
        return
    debts, total = await get_debts(db_user["id"])
    if not debts:
        await message.answer(MSG_DEBT_LIST_EMPTY, reply_markup=debts_menu())
        return
    await message.answer(f"💰 Qarzdorlar ({total} ta):", reply_markup=debts_menu())
    for debt in debts:
        rental_ref = f"\n🔗 Ijara #{debt['rental_id']}" if debt["rental_id"] else ""
        text = (
            f"👤 {debt['customer_name']}\n"
            f"📞 {debt['customer_phone']}\n"
            f"💰 Qarz: {format_number(debt['amount'])} so'm"
            f"{rental_ref}"
        )
        await message.answer(text, reply_markup=debt_actions_keyboard(debt["id"]))


# ===== TOTAL DEBT =====

@router.message(F.text == BTN_TOTAL_DEBT)
async def total_debt_handler(message: Message, db_user):
    if not check_user(db_user):
        return
    total = await get_total_debt(db_user["id"])
    _, count = await get_debts(db_user["id"], limit=1000)
    await message.answer(
        f"📊 Umumiy qarzdorlik\n\n"
        f"👥 Qarzdorlar soni: {count} ta\n"
        f"💰 Jami qarz: {format_number(total)} so'm",
        reply_markup=debts_menu()
    )


# ===== SEARCH DEBT =====

@router.message(F.text == BTN_SEARCH_DEBT)
async def search_debt_start(message: Message, state: FSMContext, db_user):
    if not check_user(db_user):
        return
    await state.set_state(SearchDebtFSM.query)
    await message.answer(MSG_SEARCH_PROMPT, reply_markup=cancel_keyboard())


@router.message(SearchDebtFSM.query)
async def search_debt_result(message: Message, state: FSMContext, db_user):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer(MSG_CANCELLED, reply_markup=debts_menu())
        return
    debts = await search_debts(db_user["id"], message.text.strip())
    await state.clear()
    if not debts:
        await message.answer(MSG_NOT_FOUND, reply_markup=debts_menu())
        return
    for debt in debts:
        rental_ref = f"\n🔗 Ijara #{debt['rental_id']}" if debt["rental_id"] else ""
        text = (
            f"👤 {debt['customer_name']}\n"
            f"📞 {debt['customer_phone']}\n"
            f"💰 Qarz: {format_number(debt['amount'])} so'm"
            f"{rental_ref}"
        )
        await message.answer(text, reply_markup=debt_actions_keyboard(debt["id"]))
    await message.answer("✅ Qidiruv tugadi.", reply_markup=debts_menu())


# ===== ADD DEBT MANUALLY =====

@router.message(F.text == BTN_ADD_DEBT)
async def add_debt_start(message: Message, state: FSMContext, db_user):
    if not check_user(db_user):
        return
    await state.set_state(AddDebtFSM.name)
    await message.answer(MSG_ADD_DEBT_NAME, reply_markup=cancel_keyboard())


@router.message(AddDebtFSM.name)
async def add_debt_name(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer(MSG_CANCELLED, reply_markup=debts_menu())
        return
    await state.update_data(debt_name=message.text.strip())
    await state.set_state(AddDebtFSM.phone)
    await message.answer(MSG_ADD_DEBT_PHONE)


@router.message(AddDebtFSM.phone)
async def add_debt_phone(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer(MSG_CANCELLED, reply_markup=debts_menu())
        return
    if not validate_phone(message.text):
        await message.answer(MSG_INVALID_PHONE)
        return
    await state.update_data(debt_phone=message.text.strip())
    await state.set_state(AddDebtFSM.amount)
    await message.answer(MSG_ADD_DEBT_AMOUNT)


@router.message(AddDebtFSM.amount)
async def add_debt_amount(message: Message, state: FSMContext, db_user):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer(MSG_CANCELLED, reply_markup=debts_menu())
        return
    amount = validate_positive_float(message.text)
    if amount is None:
        await message.answer("❌ Noto'g'ri summa. Musbat son kiriting.")
        return
    data = await state.get_data()
    await add_debt(
        user_id=db_user["id"],
        customer_name=data["debt_name"],
        customer_phone=data["debt_phone"],
        amount=amount
    )
    await state.clear()
    await message.answer(MSG_DEBT_ADDED, reply_markup=debts_menu())


# ===== DEBT PAYMENT CALLBACK =====

@router.callback_query(F.data.startswith("debt_pay:"))
async def cb_debt_pay(callback: CallbackQuery, state: FSMContext):
    debt_id = int(callback.data.split(":")[1])
    debt = await get_debt_by_id(debt_id)
    if not debt:
        await callback.answer("Topilmadi")
        return
    await callback.message.answer(
        MSG_DEBT_PAY_TYPE.format(amount=format_number(debt["amount"])),
        reply_markup=debt_pay_type_keyboard(debt_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("debt_payment:full:"))
async def cb_debt_full_payment(callback: CallbackQuery, db_user):
    debt_id = int(callback.data.split(":")[2])
    debt = await get_debt_by_id(debt_id)
    if not debt:
        await callback.answer("Topilmadi", show_alert=True)
        return
    amount = debt["amount"]
    if amount <= 0:
        await callback.answer("Bu qarz allaqachon to'langan.", show_alert=True)
        return
    await record_payment(db_user["id"], debt["rental_id"] if debt["rental_id"] else None, amount)
    await pay_debt(debt_id, amount)
    await callback.message.answer(MSG_DEBT_CLEARED)
    await callback.answer()


@router.callback_query(F.data.startswith("debt_payment:partial:"))
async def cb_debt_partial_start(callback: CallbackQuery, state: FSMContext):
    debt_id = int(callback.data.split(":")[2])
    debt = await get_debt_by_id(debt_id)
    await state.set_state(DebtPaymentFSM.amount)
    await state.update_data(paying_debt_id=debt_id, max_amount=debt["amount"])
    await callback.message.answer(
        MSG_ENTER_DEBT_PAYMENT.format(max=format_number(debt["amount"])),
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(DebtPaymentFSM.amount)
async def debt_partial_payment(message: Message, state: FSMContext, db_user):
    data = await state.get_data()
    max_amount = data["max_amount"]

    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer(MSG_CANCELLED, reply_markup=debts_menu())
        return

    amount = validate_positive_float(message.text)
    if amount is None or amount <= 0:
        await message.answer(
            f"❌ Noto'g'ri summa. 0 dan {format_number(max_amount)} so'mgacha kiriting."
        )
        return
    if amount > max_amount:
        await message.answer(
            f"❌ Summa haddan ortiq. Maksimal: {format_number(max_amount)} so'm."
        )
        return

    debt_id = data["paying_debt_id"]
    debt = await get_debt_by_id(debt_id)
    if not debt:
        await message.answer(MSG_ERROR, reply_markup=debts_menu())
        await state.clear()
        return

    await record_payment(db_user["id"], debt["rental_id"] if debt["rental_id"] else None, amount)
    remaining = await pay_debt(debt_id, amount)
    await state.clear()

    if remaining <= 0:
        await message.answer(MSG_DEBT_CLEARED, reply_markup=debts_menu())
    else:
        await message.answer(
            f"✅ {format_number(amount)} so'm to'lov qabul qilindi.\n"
            f"💰 Qolgan qarz: {format_number(remaining)} so'm",
            reply_markup=debts_menu()
        )


# ===== DELETE DEBT =====

@router.callback_query(F.data.startswith("debt_delete:"))
async def cb_debt_delete_confirm(callback: CallbackQuery):
    debt_id = int(callback.data.split(":")[1])
    await callback.message.answer(
        MSG_CONFIRM_DELETE,
        reply_markup=confirm_delete_keyboard("debt_del_final", debt_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("debt_del_final:confirm:"))
async def cb_debt_delete_do(callback: CallbackQuery):
    from database import get_db
    debt_id = int(callback.data.split(":")[2])
    async with get_db() as conn:
        await conn.execute("DELETE FROM debts WHERE id = $1", debt_id)
    await callback.message.edit_text("🗑 Qarz o'chirildi.")
    await callback.answer()


@router.callback_query(F.data.startswith("debt_del_final:cancel:"))
async def cb_debt_delete_cancel(callback: CallbackQuery):
    await callback.message.edit_text(MSG_CANCELLED)
    await callback.answer()
