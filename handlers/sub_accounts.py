"""
handlers/sub_accounts.py

Allows a regular user (shop owner) to manage up to 4 extra Telegram accounts
that can access the bot under the same user/shop profile.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from handlers.states import SubAccountFSM
from services.user_service import (
    get_sub_accounts, add_sub_account, remove_sub_account, MAX_SUB_ACCOUNTS
)
from middlewares.role_middleware import _invalidate
from utils.texts import *
from utils.keyboards import sub_accounts_keyboard, cancel_keyboard, user_main_menu

router = Router()


def _format_list(sub_accounts: list) -> str:
    if not sub_accounts:
        return "—"
    lines = []
    for i, sa in enumerate(sub_accounts, 1):
        lines.append(f"{i}. TG ID: <code>{sa['telegram_id']}</code>")
    return "\n".join(lines)


# ── Main sub-accounts screen ──────────────────────────────────────────────────

@router.message(F.text == BTN_SUB_ACCOUNTS)
async def sub_accounts_menu(message: Message, db_user, is_super_admin: bool):
    if is_super_admin or db_user is None or not db_user["is_active"]:
        return

    subs = await get_sub_accounts(db_user["id"])
    count = len(subs)

    if not subs:
        text = MSG_SUB_ACCOUNTS_EMPTY
    else:
        text = MSG_SUB_ACCOUNTS_MENU.format(list=_format_list(subs))

    # Show Add button only when below limit
    if count < MAX_SUB_ACCOUNTS:
        keyboard = sub_accounts_keyboard(subs)
    else:
        # Still show delete buttons but no add button
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        for sa in subs:
            builder.button(
                text=f"🗑 TG ID: {sa['telegram_id']}",
                callback_data=f"sub_del:{sa['id']}"
            )
        builder.adjust(1)
        keyboard = builder.as_markup()

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


# ── Add sub-account flow ──────────────────────────────────────────────────────

@router.callback_query(F.data == "sub_add")
async def cb_sub_add(callback: CallbackQuery, state: FSMContext, db_user, is_super_admin: bool):
    if is_super_admin or db_user is None or not db_user["is_active"]:
        await callback.answer()
        return

    count = len(await get_sub_accounts(db_user["id"]))
    if count >= MAX_SUB_ACCOUNTS:
        await callback.answer(MSG_SUB_LIMIT, show_alert=True)
        return

    await state.set_state(SubAccountFSM.add_telegram_id)
    await state.update_data(user_id=db_user["id"])
    await callback.message.answer(MSG_ADD_SUB_PROMPT, reply_markup=cancel_keyboard())
    await callback.answer()


@router.message(SubAccountFSM.add_telegram_id)
async def process_sub_tg_id(message: Message, state: FSMContext, db_user):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer(MSG_CANCELLED, reply_markup=user_main_menu())
        return

    try:
        tg_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting.")
        return

    data = await state.get_data()
    result = await add_sub_account(data["user_id"], tg_id)
    await state.clear()

    if result == "ok":
        # Invalidate cache for the new sub-account so it resolves immediately
        _invalidate(tg_id)
        await message.answer(MSG_SUB_ADDED.format(tg_id=tg_id), reply_markup=user_main_menu())
    elif result == "limit":
        await message.answer(MSG_SUB_LIMIT, reply_markup=user_main_menu())
    elif result == "main_account":
        await message.answer(MSG_SUB_MAIN_ACCOUNT, reply_markup=user_main_menu())
    else:
        await message.answer(MSG_SUB_DUPLICATE, reply_markup=user_main_menu())


# ── Delete sub-account ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("sub_del:"))
async def cb_sub_delete(callback: CallbackQuery, db_user, is_super_admin: bool):
    if is_super_admin or db_user is None or not db_user["is_active"]:
        await callback.answer()
        return

    sub_id = int(callback.data.split(":")[1])

    # Find the telegram_id before deleting so we can invalidate cache
    subs_before = await get_sub_accounts(db_user["id"])
    tg_id_to_invalidate = None
    for sa in subs_before:
        if sa["id"] == sub_id:
            tg_id_to_invalidate = sa["telegram_id"]
            break

    await remove_sub_account(db_user["id"], sub_id)

    if tg_id_to_invalidate:
        _invalidate(tg_id_to_invalidate)

    # Refresh the list
    subs = await get_sub_accounts(db_user["id"])
    count = len(subs)

    if not subs:
        text = MSG_SUB_ACCOUNTS_EMPTY
    else:
        text = MSG_SUB_ACCOUNTS_MENU.format(list=_format_list(subs))

    if count < MAX_SUB_ACCOUNTS:
        keyboard = sub_accounts_keyboard(subs)
    else:
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        for sa in subs:
            builder.button(
                text=f"🗑 TG ID: {sa['telegram_id']}",
                callback_data=f"sub_del:{sa['id']}"
            )
        builder.adjust(1)
        keyboard = builder.as_markup()

    await callback.answer(MSG_SUB_DELETED)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
