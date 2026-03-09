"""
Константы для Lazy Farmer Bot
Все callback_data и магические значения в одном месте
"""

# ==================== CALLBACK DATA ====================

# Навигация
CALLBACK_BACK_FARM = "back_farm"
CALLBACK_BACK_MAIN = "back_main"
CALLBACK_BACK_SHOP = "back_shop"
CALLBACK_BACK_INVENTORY = "back_inventory"
CALLBACK_BACK_BONUS = "back_bonus"
CALLBACK_BACK_REFERRALS = "back_referrals"
CALLBACK_BACK_HELP = "back_help"
CALLBACK_BACK_EVENT = "back_event"
CALLBACK_BACK_FARMERS = "back_farmers"

# Ферма
CALLBACK_HARVEST_ALL = "harvest_all"
CALLBACK_REFRESH_FARM = "refresh_farm"
CALLBACK_CLAIM_DAILY = "claim_daily"

# Магазин
CALLBACK_SHOP_SEED = "shop_seed"
CALLBACK_SHOP_FERTILIZER = "shop_fertilizer"
CALLBACK_SHOP_UPGRADES = "shop_upgrades"
CALLBACK_SHOP_FARMERS = "shop_farmers"
CALLBACK_SHOP_SEASONAL = "shop_seasonal"
CALLBACK_SHOP_SELL = "shop_sell"

# Админ-панель
CALLBACK_ADMIN_BACK_MAIN = "admin_back_main"
CALLBACK_ADMIN_PLAYERS = "admin_players"
CALLBACK_ADMIN_PLANTS = "admin_plants"
CALLBACK_ADMIN_ECONOMY = "admin_economy"
CALLBACK_ADMIN_BROADCAST = "admin_broadcast"
CALLBACK_ADMIN_PROMO = "admin_promo"
CALLBACK_ADMIN_DAILY = "admin_daily"
CALLBACK_ADMIN_ACHIEVEMENTS = "admin_achievements"
CALLBACK_ADMIN_MANAGE_ADMINS = "admin_manage_admins"
CALLBACK_ADMIN_LOGS = "admin_logs"
CALLBACK_ADMIN_SETTINGS = "admin_settings"
CALLBACK_ADMIN_HELP = "admin_help"

# Ачивки
CALLBACK_ACH_CATEGORY = "ach_category"
CALLBACK_ACH_ALL = "ach_all"
CALLBACK_ACH_CLAIM_ALL = "claim_all_achievements"

# ==================== ИГРОВЫЕ КОНСТАНТЫ ====================

# Престиж
PRESTIGE_FOR_UPGRADES = 5  # Улучшения доступны с 5 престижа
PRESTIGE_FOR_FARMERS = 10  # Фермеры доступны с 10 престижа

# Интервалы (в секундах)
NOTIFICATION_INTERVAL = 300  # 5 минут
FARMER_WORK_INTERVAL = 120   # 2 минуты

# Лимиты
MAX_PLOTS_DEFAULT = 6
MAX_PLOTS_PER_PRESTIGE = 1
MAX_INVENTORY_SLOTS = 100

# Начальные ресурсы
START_BALANCE = 100
START_GEMS = 0

# Ежедневный бонус
DAILY_BONUS_BASE = 50
DAILY_BONUS_STREAK_MULTIPLIER = 1.5
DAILY_BONUS_MAX_STREAK = 30

# Переводы
TRANSFER_FEE_PERCENT = 5
TRANSFER_MIN_AMOUNT = 10

# ==================== ТЕКСТЫ ====================

TEXT_IN_DEVELOPMENT = "🔧 Эта функция находится в разработке. Скоро будет доступна!"
TEXT_NO_ACCESS = "⛔ У тебя нет доступа к этому действию!"
TEXT_ERROR_OCCURRED = "❌ Произошла ошибка. Попробуй позже."
TEXT_USER_NOT_FOUND = "❌ Пользователь не найден!"
TEXT_INSUFFICIENT_FUNDS = "❌ Недостаточно средств!"
TEXT_SUCCESS = "✅ Успешно!"

# ==================== РОЛИ ====================

ROLES = {
    'creator': {'emoji': '👑', 'level': 3, 'name': 'Создатель'},
    'admin': {'emoji': '⚡', 'level': 2, 'name': 'Администратор'},
    'moderator': {'emoji': '🛡️', 'level': 1, 'name': 'Модератор'},
}

# ==================== КАТЕГОРИИ МАГАЗИНА ====================

SHOP_CATEGORIES = {
    'seed': {'icon': '🌱', 'name': 'Семена'},
    'fertilizer': {'icon': '🧪', 'name': 'Удобрения'},
    'upgrade': {'icon': '⬆️', 'name': 'Улучшения'},
    'farmer': {'icon': '👤', 'name': 'Фермеры'},
    'seasonal': {'icon': '🎉', 'name': 'Сезонное'},
}

# ==================== ТИПЫ АЧИВОК ====================

ACHIEVEMENT_TYPES = {
    'regular': {'icon': '📌', 'name': 'Обычная'},
    'multi': {'icon': '📊', 'name': 'Многоуровневая'},
    'secret': {'icon': '🤫', 'name': 'Секретная'},
    'event': {'icon': '🎪', 'name': 'Ивентовая'},
}

# ==================== ТИПЫ ЦЕЛЕЙ АЧИВОК ====================

ACHIEVEMENT_GOALS = {
    'harvest': {'icon': '🌾', 'name': 'Собрано урожая'},
    'plant': {'icon': '🌱', 'name': 'Посажено растений'},
    'balance': {'icon': '💰', 'name': 'Достигнут баланс'},
    'prestige': {'icon': '🏆', 'name': 'Уровень престижа'},
    'streak_days': {'icon': '📅', 'name': 'Дней подряд'},
    'gems_total': {'icon': '💎', 'name': 'Накоплено кристаллов'},
    'spend': {'icon': '💸', 'name': 'Потрачено монет'},
    'earn': {'icon': '💵', 'name': 'Заработано монет'},
    'buy_plot': {'icon': '🟫', 'name': 'Куплено грядок'},
}
