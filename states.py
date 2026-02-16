from aiogram.fsm.state import State, StatesGroup

class PlayerStates(StatesGroup):
    waiting_promo = State()
    planting_crop = State()

class AdminStates(StatesGroup):
    waiting_user_id = State()
    waiting_balance_change = State()
    adding_crop_name = State()
    adding_crop_emoji = State()
    adding_crop_code = State()
    adding_crop_seed_price = State()
    adding_crop_sell_price = State()
    adding_crop_growth_time = State()
    creating_promo_code = State()
    creating_promo_reward = State()
    creating_promo_limit = State()
    creating_promo_days = State()
    mailing_message = State()
    mailing_message_confirmation = State()
    
    