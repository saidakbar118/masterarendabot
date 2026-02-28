import math
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from handlers.states import AddToolFSM, EditToolFSM, SearchToolFSM
from services.tool_service import (
    get_tools, get_all_tools, search_tools, get_tool_by_id,
    create_tool, update_tool_name, update_tool_qty, update_tool_price, delete_tool
)
from utils.texts import *
from utils.keyboards import (
    tools_menu, user_main_menu, cancel_keyboard, back_keyboard,
    tools_list_keyboard, edit_tool_fields_keyboard, confirm_delete_keyboard
)
from utils.helpers import validate_positive_int, validate_positive_float, format_number

router = Router()
PAGE_SIZE = 10


def check_user(db_user):
    return db_user is not None and db_user["is_active"]


# ===== NAVIGATION =====

@router.message(F.text == BTN_TOOLS)
async def tools_menu_handler(message: Message, db_user):
    if not check_user(db_user):
        await message.answer(MSG_NO_ACCESS)
        return
    await message.answer(MSG_TOOLS_MENU, reply_markup=tools_menu())


@router.message(F.text == BTN_BACK)
async def back_handler(message: Message, state: FSMContext, db_user, is_super_admin: bool):
    await state.clear()
    if is_super_admin:
        from utils.keyboards import admin_main_menu
        await message.answer(MSG_ADMIN_WELCOME, reply_markup=admin_main_menu())
    elif db_user and db_user["is_active"]:
        await message.answer(
            MSG_USER_WELCOME.format(shop_name=db_user["shop_name"]),
            reply_markup=user_main_menu()
        )


# ===== ADD TOOL =====

@router.message(F.text == BTN_ADD_TOOL)
async def add_tool_start(message: Message, state: FSMContext, db_user):
    if not check_user(db_user):
        return
    await state.set_state(AddToolFSM.name)
    await message.answer(MSG_TOOL_NAME, reply_markup=cancel_keyboard())


@router.message(AddToolFSM.name)
async def add_tool_name(message: Message, state: FSMContext, db_user):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer(MSG_CANCELLED, reply_markup=tools_menu())
        return
    await state.update_data(tool_name=message.text.strip())
    await state.set_state(AddToolFSM.quantity)
    await message.answer(MSG_TOOL_QTY)


@router.message(AddToolFSM.quantity)
async def add_tool_qty(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer(MSG_CANCELLED, reply_markup=tools_menu())
        return
    qty = validate_positive_int(message.text)
    if qty is None:
        await message.answer(MSG_TOOL_INVALID_QTY)
        return
    await state.update_data(quantity=qty)
    await state.set_state(AddToolFSM.price)
    await message.answer(MSG_TOOL_PRICE)


@router.message(AddToolFSM.price)
async def add_tool_price(message: Message, state: FSMContext, db_user):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer(MSG_CANCELLED, reply_markup=tools_menu())
        return
    price = validate_positive_float(message.text)
    if price is None:
        await message.answer(MSG_TOOL_INVALID_PRICE)
        return
    data = await state.get_data()
    success = await create_tool(db_user["id"], data["tool_name"], data["quantity"], price)
    await state.clear()
    if success:
        await message.answer(
            MSG_TOOL_CREATED.format(
                name=data["tool_name"],
                qty=data["quantity"],
                price=format_number(price)
            ),
            reply_markup=tools_menu()
        )
    else:
        await message.answer(MSG_TOOL_EXISTS, reply_markup=tools_menu())


# ===== TOOL LIST =====

@router.message(F.text == BTN_TOOL_LIST)
async def tool_list_handler(message: Message, db_user, state: FSMContext):
    if not check_user(db_user):
        return
    await state.set_state(SearchToolFSM.query)
    await state.update_data(list_mode=True)
    tools, total = await get_tools(db_user["id"], limit=PAGE_SIZE)
    if not tools:
        await state.clear()
        await message.answer(MSG_TOOL_LIST_EMPTY, reply_markup=tools_menu())
        return
    text = f"🔧 Asboblar ro'yxati ({total} ta):\n\n"
    for t in tools:
        text += f"• {t['name']} | x{t['quantity']} | {format_number(t['daily_price'])} so'm/kun\n"
    await state.clear()
    await message.answer(text, reply_markup=tools_menu())
    await message.answer(f"🔍 Qidirish uchun nom kiriting yoki {BTN_BACK}:", reply_markup=back_keyboard())
    await state.set_state(SearchToolFSM.query)


@router.message(SearchToolFSM.query)
async def search_tool_result(message: Message, state: FSMContext, db_user):
    if message.text == BTN_BACK:
        await state.clear()
        await message.answer(MSG_TOOLS_MENU, reply_markup=tools_menu())
        return
    tools = await search_tools(db_user["id"], message.text.strip())
    await state.clear()
    if not tools:
        await message.answer(MSG_NOT_FOUND, reply_markup=tools_menu())
        return
    text = f"🔍 Natijalar:\n\n"
    for t in tools:
        text += f"• {t['name']} | x{t['quantity']} | {format_number(t['daily_price'])} so'm/kun\n"
    await message.answer(text, reply_markup=tools_menu())


# ===== EDIT TOOL =====

@router.message(F.text == BTN_EDIT_TOOL)
async def edit_tool_start(message: Message, state: FSMContext, db_user):
    if not check_user(db_user):
        return
    tools = await get_all_tools(db_user["id"])
    if not tools:
        await message.answer(MSG_TOOL_LIST_EMPTY, reply_markup=tools_menu())
        return
    await state.set_state(EditToolFSM.select_tool)
    await message.answer(MSG_SELECT_TOOL, reply_markup=tools_list_keyboard(tools, "tool_edit"))


@router.callback_query(F.data.startswith("tool_edit:"))
async def cb_edit_tool_select(callback: CallbackQuery, state: FSMContext):
    tool_id = int(callback.data.split(":")[1])
    tool = await get_tool_by_id(tool_id)
    if not tool:
        await callback.answer("Topilmadi")
        return
    await state.update_data(editing_tool_id=tool_id)
    await state.set_state(EditToolFSM.select_field)
    await callback.message.answer(
        MSG_EDIT_TOOL_FIELD.format(
            name=tool["name"], qty=tool["quantity"], price=format_number(tool["daily_price"])
        ),
        reply_markup=edit_tool_fields_keyboard(tool_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tool_edit_field:"))
async def cb_edit_tool_field(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    field = parts[1]
    tool_id = int(parts[2])
    await state.update_data(edit_field=field, editing_tool_id=tool_id)
    await state.set_state(EditToolFSM.new_value)
    prompts = {"name": "Yangi nom kiriting:", "qty": "Yangi miqdor kiriting:", "price": "Yangi narx kiriting:"}
    await callback.message.answer(prompts.get(field, "Yangi qiymat:"), reply_markup=cancel_keyboard())
    await callback.answer()


@router.message(EditToolFSM.new_value)
async def edit_tool_value(message: Message, state: FSMContext, db_user):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer(MSG_CANCELLED, reply_markup=tools_menu())
        return
    data = await state.get_data()
    field = data.get("edit_field")
    tool_id = data.get("editing_tool_id")

    if field == "name":
        success = await update_tool_name(tool_id, message.text.strip(), db_user["id"])
        if not success:
            await message.answer(MSG_TOOL_EXISTS, reply_markup=tools_menu())
            await state.clear()
            return
    elif field == "qty":
        qty = validate_positive_int(message.text)
        if qty is None:
            await message.answer(MSG_TOOL_INVALID_QTY)
            return
        await update_tool_qty(tool_id, qty)
    elif field == "price":
        price = validate_positive_float(message.text)
        if price is None:
            await message.answer(MSG_TOOL_INVALID_PRICE)
            return
        await update_tool_price(tool_id, price)

    await state.clear()
    await message.answer(MSG_TOOL_UPDATED, reply_markup=tools_menu())


# ===== DELETE TOOL =====

@router.message(F.text == BTN_DELETE_TOOL)
async def delete_tool_start(message: Message, state: FSMContext, db_user):
    if not check_user(db_user):
        return
    tools = await get_all_tools(db_user["id"])
    if not tools:
        await message.answer(MSG_TOOL_LIST_EMPTY, reply_markup=tools_menu())
        return
    await message.answer(MSG_SELECT_TOOL, reply_markup=tools_list_keyboard(tools, "tool_del"))


@router.callback_query(F.data.startswith("tool_del:"))
async def cb_delete_tool_confirm(callback: CallbackQuery):
    tool_id = int(callback.data.split(":")[1])
    await callback.message.answer(
        MSG_CONFIRM_DELETE,
        reply_markup=confirm_delete_keyboard("tool_del_final", tool_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tool_del_final:confirm:"))
async def cb_delete_tool_do(callback: CallbackQuery):
    tool_id = int(callback.data.split(":")[2])
    success = await delete_tool(tool_id)
    if success:
        await callback.message.edit_text(MSG_TOOL_DELETED)
    else:
        await callback.message.edit_text(MSG_TOOL_IN_USE)
    await callback.answer()


@router.callback_query(F.data.startswith("tool_del_final:cancel:"))
async def cb_delete_tool_cancel(callback: CallbackQuery):
    await callback.message.edit_text(MSG_CANCELLED)
    await callback.answer()
