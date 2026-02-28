from aiogram.fsm.state import State, StatesGroup


class AddUserFSM(StatesGroup):
    full_name = State()
    shop_name = State()
    address = State()
    phone = State()
    telegram_id = State()


class EditUserFSM(StatesGroup):
    full_name = State()
    shop_name = State()
    address = State()
    phone = State()


class SearchUserFSM(StatesGroup):
    query = State()


class AddToolFSM(StatesGroup):
    name = State()
    quantity = State()
    price = State()


class EditToolFSM(StatesGroup):
    select_tool = State()
    select_field = State()
    new_value = State()


class SearchToolFSM(StatesGroup):
    query = State()


class AddRentalFSM(StatesGroup):
    customer_name = State()
    customer_address = State()
    customer_phone = State()
    select_tools = State()
    tool_quantity = State()
    confirm = State()


class ReturnRentalFSM(StatesGroup):
    search = State()
    select_rental = State()
    return_type = State()
    select_item = State()
    item_quantity = State()
    confirm_more = State()
    payment = State()
    partial_amount = State()


class AddDebtFSM(StatesGroup):
    name = State()
    phone = State()
    amount = State()


class SearchDebtFSM(StatesGroup):
    query = State()


class DebtPaymentFSM(StatesGroup):
    amount = State()
