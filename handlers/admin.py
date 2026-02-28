import math
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from handlers.states import AddUserFSM, SearchUserFSM, EditUserFSM
from services.user_service import (
    create_user, get_all_users, search_users, get_user_by_id,
    activate_user, deactivate_user, delete_user, update_user
)
from utils.texts import *
from utils.keyboards import (
    admin_main_menu, back_keyboard, cancel_keyboard,
    admin_user_actions, confirm_delete_keyboard, pagination_keyboard
)
from utils.helpers import validate_phone, validate_positive_int
from loguru import logger

router = Router()
PAGE_SIZE = 8


def is_admin(is_super_admin: bool):
    return is_super_admin


# ===== MAIN MENU NAVIGATION =====

@router.message(F.text == BTN_ADD_USER)
async def add_user_start(message: Message, state: FSMContext, is_super_admin: bool):
    if not is_admin(is_super_admin):
        return
    await state.set_state(AddUserFSM.full_name)
    await message.answer(MSG_ADD_USER_NAME, reply_markup=cancel_keyboard())


@router.message(F.text == BTN_USER_LIST)
async def user_list(message: Message, is_super_admin: bool):
    if not is_admin(is_super_admin):
        return
    await show_user_list(message, page=1)


@router.message(F.text == BTN_SEARCH_USER)
async def search_user_start(message: Message, state: FSMContext, is_super_admin: bool):
    if not is_admin(is_super_admin):
        return
    await state.set_state(SearchUserFSM.query)
    await message.answer(MSG_SEARCH_PROMPT, reply_markup=cancel_keyboard())


# ===== ADD USER FSM =====

@router.message(AddUserFSM.full_name)
async def add_user_name(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer(MSG_CANCELLED, reply_markup=admin_main_menu())
        return
    await state.update_data(full_name=message.text.strip())
    await state.set_state(AddUserFSM.shop_name)
    await message.answer(MSG_ADD_USER_SHOP)


@router.message(AddUserFSM.shop_name)
async def add_user_shop(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer(MSG_CANCELLED, reply_markup=admin_main_menu())
        return
    await state.update_data(shop_name=message.text.strip())
    await state.set_state(AddUserFSM.address)
    await message.answer(MSG_ADD_USER_ADDRESS)


@router.message(AddUserFSM.address)
async def add_user_address(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer(MSG_CANCELLED, reply_markup=admin_main_menu())
        return
    await state.update_data(address=message.text.strip())
    await state.set_state(AddUserFSM.phone)
    await message.answer(MSG_ADD_USER_PHONE)


@router.message(AddUserFSM.phone)
async def add_user_phone(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer(MSG_CANCELLED, reply_markup=admin_main_menu())
        return
    if not validate_phone(message.text):
        await message.answer(MSG_INVALID_PHONE)
        return
    await state.update_data(phone=message.text.strip())
    await state.set_state(AddUserFSM.telegram_id)
    await message.answer(MSG_ADD_USER_TG_ID)


@router.message(AddUserFSM.telegram_id)
async def add_user_tg_id(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer(MSG_CANCELLED, reply_markup=admin_main_menu())
        return
    try:
        tg_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting.")
        return

    data = await state.get_data()
    success = await create_user(
        full_name=data["full_name"],
        shop_name=data["shop_name"],
        address=data["address"],
        phone=data["phone"],
        telegram_id=tg_id
    )
    await state.clear()
    if success:
        await message.answer(
            MSG_USER_CREATED.format(
                name=data["full_name"],
                shop=data["shop_name"],
                phone=data["phone"],
                tg_id=tg_id
            ),
            reply_markup=admin_main_menu()
        )
    else:
        await message.answer(MSG_USER_EXISTS, reply_markup=admin_main_menu())


# ===== USER LIST =====

async def show_user_list(message: Message, page: int = 1):
    offset = (page - 1) * PAGE_SIZE
    users, total = await get_all_users(offset=offset, limit=PAGE_SIZE)
    if not users:
        await message.answer(MSG_USER_LIST_EMPTY, reply_markup=admin_main_menu())
        return
    total_pages = math.ceil(total / PAGE_SIZE)
    text = f"📋 Foydalanuvchilar ro'yxati (sahifa {page}/{total_pages}):\n\n"
    for u in users:
        status = "✅ Faol" if u["is_active"] else "🚫 Faol emas"
        text += f"👤 {u['full_name']} | 🏪 {u['shop_name']} | {status}\n"
    await message.answer(text, reply_markup=admin_main_menu())

    # Show each user as separate message with actions for first page simplicity
    # Use inline for each user
    for u in users:
        status = "✅ Faol" if u["is_active"] else "🚫 Nofaol"
        utext = (f"👤 <b>{u['full_name']}</b>\n"
                 f"🏪 {u['shop_name']}\n"
                 f"📍 {u['address']}\n"
                 f"📞 {u['phone']}\n"
                 f"🆔 TG: {u['telegram_id']}\n"
                 f"Status: {status}")
        await message.answer(
            utext,
            reply_markup=admin_user_actions(u["id"], bool(u["is_active"])),
            parse_mode="HTML"
        )


# ===== SEARCH USER =====

@router.message(SearchUserFSM.query)
async def search_user_result(message: Message, state: FSMContext, is_super_admin: bool):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer(MSG_CANCELLED, reply_markup=admin_main_menu())
        return
    users = await search_users(message.text.strip())
    await state.clear()
    if not users:
        await message.answer(MSG_NOT_FOUND, reply_markup=admin_main_menu())
        return
    for u in users:
        status = "✅ Faol" if u["is_active"] else "🚫 Nofaol"
        text = (f"👤 <b>{u['full_name']}</b>\n"
                f"🏪 {u['shop_name']}\n"
                f"📍 {u['address']}\n"
                f"📞 {u['phone']}\n"
                f"🆔 TG: {u['telegram_id']}\n"
                f"Status: {status}")
        await message.answer(
            text,
            reply_markup=admin_user_actions(u["id"], bool(u["is_active"])),
            parse_mode="HTML"
        )
    await message.answer("✅ Qidiruv tugadi.", reply_markup=admin_main_menu())


# ===== USER ACTIONS (CALLBACKS) =====

@router.callback_query(F.data.startswith("user:activate:"))
async def cb_activate(callback: CallbackQuery, is_super_admin: bool):
    if not is_admin(is_super_admin):
        return
    user_id = int(callback.data.split(":")[2])
    await activate_user(user_id)
    await callback.answer(MSG_USER_ACTIVATED)
    user = await get_user_by_id(user_id)
    await callback.message.edit_reply_markup(
        reply_markup=admin_user_actions(user_id, True)
    )


@router.callback_query(F.data.startswith("user:deactivate:"))
async def cb_deactivate(callback: CallbackQuery, is_super_admin: bool):
    if not is_admin(is_super_admin):
        return
    user_id = int(callback.data.split(":")[2])
    await deactivate_user(user_id)
    await callback.answer(MSG_USER_DEACTIVATED)
    await callback.message.edit_reply_markup(
        reply_markup=admin_user_actions(user_id, False)
    )


@router.callback_query(F.data.startswith("user:delete:"))
async def cb_delete_confirm(callback: CallbackQuery, is_super_admin: bool):
    if not is_admin(is_super_admin):
        return
    user_id = int(callback.data.split(":")[2])
    await callback.message.edit_reply_markup(
        reply_markup=confirm_delete_keyboard("user_del", user_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("user_del:confirm:"))
async def cb_delete_do(callback: CallbackQuery, is_super_admin: bool):
    if not is_admin(is_super_admin):
        return
    user_id = int(callback.data.split(":")[2])
    await delete_user(user_id)
    await callback.message.edit_text(MSG_USER_DELETED)
    await callback.answer()


@router.callback_query(F.data.startswith("user_del:cancel:"))
async def cb_delete_cancel(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[2])
    user = await get_user_by_id(user_id)
    if user:
        await callback.message.edit_reply_markup(
            reply_markup=admin_user_actions(user_id, bool(user["is_active"]))
        )
    await callback.answer(MSG_CANCELLED)


@router.callback_query(F.data.startswith("user:edit:"))
async def cb_edit_user(callback: CallbackQuery, state: FSMContext, is_super_admin: bool):
    if not is_admin(is_super_admin):
        return
    user_id = int(callback.data.split(":")[2])
    user = await get_user_by_id(user_id)
    if not user:
        await callback.answer("Topilmadi")
        return
    await state.update_data(editing_user_id=user_id,
                             shop_name=user["shop_name"],
                             address=user["address"],
                             phone=user["phone"])
    await state.set_state(EditUserFSM.full_name)
    await callback.message.answer(
        f"Yangi to'liq ism (hozir: {user['full_name']}):",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(EditUserFSM.full_name)
async def edit_user_name(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer(MSG_CANCELLED, reply_markup=admin_main_menu())
        return
    await state.update_data(full_name=message.text.strip())
    await state.set_state(EditUserFSM.shop_name)
    data = await state.get_data()
    await message.answer(f"Yangi do'kon nomi (hozir: {data['shop_name']}):")


@router.message(EditUserFSM.shop_name)
async def edit_user_shop(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer(MSG_CANCELLED, reply_markup=admin_main_menu())
        return
    await state.update_data(shop_name=message.text.strip())
    await state.set_state(EditUserFSM.address)
    data = await state.get_data()
    await message.answer(f"Yangi manzil (hozir: {data['address']}):")


@router.message(EditUserFSM.address)
async def edit_user_address(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer(MSG_CANCELLED, reply_markup=admin_main_menu())
        return
    await state.update_data(address=message.text.strip())
    await state.set_state(EditUserFSM.phone)
    data = await state.get_data()
    await message.answer(f"Yangi telefon (hozir: {data['phone']}):")


@router.message(EditUserFSM.phone)
async def edit_user_phone(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer(MSG_CANCELLED, reply_markup=admin_main_menu())
        return
    if not validate_phone(message.text):
        await message.answer(MSG_INVALID_PHONE)
        return
    data = await state.get_data()
    await update_user(
        user_id=data["editing_user_id"],
        full_name=data["full_name"],
        shop_name=data["shop_name"],
        address=data["address"],
        phone=message.text.strip()
    )
    await state.clear()
    await message.answer(MSG_SUCCESS, reply_markup=admin_main_menu())
