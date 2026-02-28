from aiogram import Router
from .common import router as common_router
from .admin import router as admin_router
from .tools import router as tools_router
from .rentals import router as rentals_router
from .debts import router as debts_router
from .sub_accounts import router as sub_accounts_router

main_router = Router()
main_router.include_router(common_router)
main_router.include_router(admin_router)
main_router.include_router(tools_router)
main_router.include_router(rentals_router)
main_router.include_router(debts_router)
main_router.include_router(sub_accounts_router)

__all__ = ["main_router"]
