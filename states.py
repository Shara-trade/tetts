from aiogram.fsm.state import State, StatesGroup

class PlayerStates(StatesGroup):
    waiting_promo = State()
    planting_crop = State()
    viewing_achievement = State()  # Просмотр деталей ачивки
    claiming_reward = State()      # Получение награды

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
    
# ==================== СОСТОЯНИЯ ДЛЯ СОЗДАНИЯ АЧИВОК ====================
    
class AchievementCreateStates(StatesGroup):
    # Пошаговый мастер создания ачивки
    step_category = State()          # Шаг 1: Выбор категории
    step_basic_info = State()        # Шаг 2: Базовые параметры (ID, название, описание)
    step_icon = State()              # Шаг 3: Иконка
    step_goal_type = State()         # Шаг 4: Тип цели
    step_goal_value = State()        # Шаг 5: Значение цели
    step_reward_type = State()       # Шаг 6: Тип награды
    step_reward_value = State()      # Шаг 7: Значение награды
    step_achievement_type = State()  # Шаг 8: Тип ачивки (обычная/многоуровневая/секретная/ивентовая)
    step_parent_achievement = State() # Шаг 9: Родительская ачивка (для многоуровневых)
    step_level = State()             # Шаг 10: Уровень
    step_event_date = State()        # Шаг 11: Дата окончания ивента
    step_sort_order = State()        # Шаг 12: Порядок сортировки
    step_confirm = State()           # Шаг 13: Подтверждение

class AchievementEditStates(StatesGroup):
    # Редактирование ачивки
    selecting_achievement = State()
    editing_field = State()
    editing_value = State()
    confirm_delete = State()

class AchievementGiveStates(StatesGroup):
    # Выдача ачивки игроку
    waiting_player = State()
    waiting_achievement = State()
    confirm_give = State()
    

    
