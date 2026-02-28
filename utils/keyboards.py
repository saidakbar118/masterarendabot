from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from utils.texts import *


def remove_keyboard():
    return ReplyKeyboardRemove()


def back_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text=BTN_BACK)
    return builder.as_markup(resize_keyboard=True)


def cancel_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text=BTN_CANCEL)
    return builder.as_markup(resize_keyboard=True)


def back_cancel_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text=BTN_BACK)
    builder.button(text=BTN_CANCEL)
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


# ===================== SUPER ADMIN =====================

def admin_main_menu():
    builder = ReplyKeyboardBuilder()
    builder.button(text=BTN_ADD_USER)
    builder.button(text=BTN_USER_LIST)
    builder.button(text=BTN_SEARCH_USER)
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def admin_user_actions(user_id: int, is_active: bool):
    builder = InlineKeyboardBuilder()
    if is_active:
        builder.button(text=BTN_DEACTIVATE, callback_data=f"user:deactivate:{user_id}")
    else:
        builder.button(text=BTN_ACTIVATE, callback_data=f"user:activate:{user_id}")
    builder.button(text=BTN_EDIT_USER, callback_data=f"user:edit:{user_id}")
    builder.button(text=BTN_DELETE_USER, callback_data=f"user:delete:{user_id}")
    builder.adjust(2)
    return builder.as_markup()


def confirm_delete_keyboard(callback_prefix: str, item_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_YES, callback_data=f"{callback_prefix}:confirm:{item_id}")
    builder.button(text=BTN_NO, callback_data=f"{callback_prefix}:cancel:{item_id}")
    builder.adjust(2)
    return builder.as_markup()


def pagination_keyboard(current: int, total_pages: int, prefix: str):
    builder = InlineKeyboardBuilder()
    if current > 1:
        builder.button(text=BTN_PREV, callback_data=f"{prefix}:page:{current - 1}")
    if current < total_pages:
        builder.button(text=BTN_NEXT, callback_data=f"{prefix}:page:{current + 1}")
    return builder.as_markup()


# ===================== USER / SHOP OWNER =====================

def user_main_menu():
    builder = ReplyKeyboardBuilder()
    builder.button(text=BTN_TOOLS)
    builder.button(text=BTN_RENTALS)
    builder.button(text=BTN_DEBTS)
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


# ---- TOOLS ----

def tools_menu():
    builder = ReplyKeyboardBuilder()
    builder.button(text=BTN_ADD_TOOL)
    builder.button(text=BTN_TOOL_LIST)
    builder.button(text=BTN_EDIT_TOOL)
    builder.button(text=BTN_DELETE_TOOL)
    builder.button(text=BTN_BACK)
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def tools_list_keyboard(tools: list, prefix: str = "tool_select"):
    builder = InlineKeyboardBuilder()
    for tool in tools:
        builder.button(
            text=f"🔧 {tool['name']} (x{tool['quantity']})",
            callback_data=f"{prefix}:{tool['id']}"
        )
    builder.adjust(1)
    return builder.as_markup()


def edit_tool_fields_keyboard(tool_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_EDIT_NAME, callback_data=f"tool_edit_field:name:{tool_id}")
    builder.button(text=BTN_EDIT_QTY, callback_data=f"tool_edit_field:qty:{tool_id}")
    builder.button(text=BTN_EDIT_PRICE, callback_data=f"tool_edit_field:price:{tool_id}")
    builder.adjust(1)
    return builder.as_markup()


# ---- RENTALS ----

def rentals_menu():
    builder = ReplyKeyboardBuilder()
    builder.button(text=BTN_ADD_RENTAL)
    builder.button(text=BTN_RENTAL_LIST)
    builder.button(text=BTN_RETURN_RENTAL)
    builder.button(text=BTN_BACK)
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def rental_tools_selection_keyboard(tools: list, selected_ids: list[int] = None):
    selected_ids = selected_ids or []
    builder = InlineKeyboardBuilder()
    for tool in tools:
        if tool["quantity"] > 0:
            check = "✅ " if tool["id"] in selected_ids else ""
            builder.button(
                text=f"{check}🔧 {tool['name']} (x{tool['quantity']}) - {tool['daily_price']:,.0f} so'm",
                callback_data=f"rental_tool:{tool['id']}"
            )
    builder.button(text=BTN_FINISH_TOOLS, callback_data="rental_tool:done")
    builder.adjust(1)
    return builder.as_markup()


def rental_confirmation_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_CONFIRM, callback_data="rental_confirm:yes")
    builder.button(text=BTN_EDIT, callback_data="rental_confirm:edit")
    builder.button(text=BTN_DELETE, callback_data="rental_confirm:cancel")
    builder.adjust(2)
    return builder.as_markup()


def rental_list_keyboard(rentals: list):
    builder = InlineKeyboardBuilder()
    for r in rentals:
        builder.button(
            text=f"👤 {r['customer_name']} | 📞 {r['customer_phone']}",
            callback_data=f"rental_detail:{r['id']}"
        )
    builder.adjust(1)
    return builder.as_markup()


def rental_return_type_keyboard(rental_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_FULL_RETURN, callback_data=f"return_type:full:{rental_id}")
    builder.button(text=BTN_PARTIAL_RETURN, callback_data=f"return_type:partial:{rental_id}")
    builder.adjust(1)
    return builder.as_markup()


def unreturned_items_keyboard(items: list):
    builder = InlineKeyboardBuilder()
    for item in items:
        remaining = item["quantity"] - item["returned_quantity"]
        builder.button(
            text=f"🔧 {item['tool_name']} (qaytarilmagan: {remaining})",
            callback_data=f"return_item:{item['id']}"
        )
    builder.button(text=BTN_FINISH_RETURN, callback_data="return_item:done")
    builder.adjust(1)
    return builder.as_markup()


def payment_type_keyboard(rental_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_FULL_PAYMENT, callback_data=f"payment:full:{rental_id}")
    builder.button(text=BTN_PARTIAL_PAYMENT, callback_data=f"payment:partial:{rental_id}")
    builder.adjust(1)
    return builder.as_markup()


# ---- DEBTS ----

def debts_menu():
    builder = ReplyKeyboardBuilder()
    builder.button(text=BTN_DEBT_LIST)
    builder.button(text=BTN_SEARCH_DEBT)
    builder.button(text=BTN_ADD_DEBT)
    builder.button(text=BTN_TOTAL_DEBT)
    builder.button(text=BTN_BACK)
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def debt_actions_keyboard(debt_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_PAY_DEBT, callback_data=f"debt_pay:{debt_id}")
    builder.button(text=BTN_DELETE, callback_data=f"debt_delete:{debt_id}")
    builder.adjust(2)
    return builder.as_markup()


def debt_pay_type_keyboard(debt_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_FULL_PAYMENT, callback_data=f"debt_payment:full:{debt_id}")
    builder.button(text=BTN_PARTIAL_PAYMENT, callback_data=f"debt_payment:partial:{debt_id}")
    builder.adjust(1)
    return builder.as_markup()


def yes_no_keyboard():
    """Used for 'Yana bor?' prompt during partial return."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Ha, yana bor", callback_data="more_items:yes")
    builder.button(text="❌ Yo'q, tugatish", callback_data="more_items:no")
    builder.adjust(1)
    return builder.as_markup()
