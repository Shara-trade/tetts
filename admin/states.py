"""
FSM состояния для Lazy Farmer Bot
Все состояния собраны в одном месте для избежания дублирования
"""

from aiogram.fsm.state import State, StatesGroup


# ==================== ИГРОВЫЕ СОСТОЯНИЯ ====================

class PlayerStates(StatesGroup):
    """Состояния игрока"""
    waiting_promo = State()
    planting_crop = State()
    viewing_achievement = State()
    claiming_reward = State()
    changing_nick = State()
    
    # Переводы
    transfer_amount = State()
    transfer_confirm = State()
    
    # Рефералы
    waiting_ref_code = State()


# ==================== АДМИНСКИЕ СОСТОЯНИЯ ====================

class AdminStates(StatesGroup):
    """Состояния админ-панели"""
    
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
    plant_edit_text = State()
    plant_edit_number = State()
    
    # Промо
    promo_code = State()
    promo_type = State()
    promo_reward_type = State()
    promo_reward_value = State()
    promo_limit = State()
    promo_per_user = State()
    promo_dates = State()
    promo_confirm = State()
    promo_edit_code = State()
    promo_edit_reward = State()
    promo_edit_uses = State()
    promo_edit_date = State()
    promo_delete_confirm = State()
    
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
    

# ==================== СОСТОЯНИЯ ДЛЯ АЧИВОК ====================

class AchievementCreateStates(StatesGroup):
    """Пошаговый мастер создания ачивки"""
    step_category = State()
    step_basic_info = State()
    step_icon = State()
    step_goal_type = State()
    step_goal_value = State()
    step_reward_type = State()
    step_reward_value = State()
    step_achievement_type = State()
    step_parent_achievement = State()
    step_level = State()
    step_event_date = State()
    step_sort_order = State()
    step_confirm = State()


class AchievementEditStates(StatesGroup):
    """Редактирование ачивки"""
    selecting_achievement = State()
    editing_field = State()
    editing_value = State()
    confirm_delete = State()


class AchievementGiveStates(StatesGroup):
    """Выдача ачивки игроку"""
    waiting_player = State()
    waiting_achievement = State()
    confirm_give = State()
    

