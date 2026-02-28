from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from config import SUPER_ADMIN_ID
from utils.texts import *
from utils.keyboards import admin_main_menu, user_main_menu

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, is_super_admin: bool, db_user):
    if is_super_admin:
        await message.answer(MSG_ADMIN_WELCOME, reply_markup=admin_main_menu())
        return

    if db_user is None:
        await message.answer(MSG_NO_ACCESS)
        return

    if not db_user["is_active"]:
        await message.answer(MSG_INACTIVE)
        return

    await message.answer(
        MSG_USER_WELCOME.format(shop_name=db_user["shop_name"]),
        reply_markup=user_main_menu()
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message, is_super_admin: bool, db_user):
    """Boshqa qaytish — returns user to main menu from anywhere."""
    if is_super_admin:
        await message.answer(MSG_ADMIN_WELCOME, reply_markup=admin_main_menu())
        return

    if db_user is None:
        await message.answer(MSG_NO_ACCESS)
        return

    if not db_user["is_active"]:
        await message.answer(MSG_INACTIVE)
        return

    await message.answer(
        MSG_USER_WELCOME.format(shop_name=db_user["shop_name"]),
        reply_markup=user_main_menu()
    )
