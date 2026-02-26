from aiogram.fsm.state import State, StatesGroup

class PlayerStates(StatesGroup):
    waiting_promo = State()
    planting_crop = State()
    viewing_achievement = State()  # Просмотр деталей ачивки
    claiming_reward = State()      # Получение награды
    changing_nick = State()        # Смена ника (ТЗ v4.0)

class AdminStates(StatesGroup):
    # Поиск игроков
    search_user_id = State()
    search_username = State()
    search_unified = State()
    
    # Выдача ресурсов
    give_coins_amount = State()
    give_coins_reason = State()
    give_gems_amount = State()
    give_gems_reason = State()
    give_item_select = State()
    give_item_quantity = State()
    give_item_reason = State()
    
    # Забор ресурсов
    take_resource_type = State()
    take_resource_amount = State()
    take_resource_confirm = State()
    
    # Бан
    ban_reason = State()
    ban_duration = State()
    ban_confirm = State()
    
    # Растения
    plant_id = State()
    plant_name = State()
    plant_emoji = State()
    plant_grow_time = State()
    plant_seed_price = State()
    plant_sell_price = State()
    plant_yield = State()
    plant_level = State()
    plant_exp = State()
    plant_active = State()
    plant_confirm = State()
    plant_edit_select = State()
    plant_edit_field = State()
    plant_edit_value = State()
    
    # Промо
    promo_code = State()
    promo_type = State()
    promo_reward_type = State()
    promo_reward_value = State()
    promo_limit = State()
    promo_per_user = State()
    promo_dates = State()
    promo_confirm = State()
    
    # Рассылка
    broadcast_content = State()
    broadcast_audience = State()
    broadcast_confirm = State()
    
    # Управление админами
    new_admin_username = State()
    new_admin_role = State()
    new_admin_confirm = State()
    remove_admin_select = State()
    remove_admin_confirm = State()
    
    # Сообщение игроку
    message_to_player = State()
    message_confirm = State()
    
    # Редактирование цен
    edit_price_select = State()
    edit_price_value = State()
    edit_price_mass_value = State()
    edit_price_mass_confirm = State()
    
    # Ежедневный бонус
    daily_day_select = State()
    daily_coins = State()
    daily_gems = State()
    daily_item_select = State()
    daily_item_qty = State()
    daily_give_player = State()
    daily_give_day = State()
    daily_reset_player = State()
    
    # Сброс прогресса
    reset_player_confirm = State()
    delete_player_confirm = State()
    
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
    

    
