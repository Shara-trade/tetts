from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict, Optional

def get_main_keyboard(user_level: int = 1, has_promo: bool = False):
    """Адаптивная главная клавиатура

    Args:
        user_level: Уровень игрока (для адаптации кнопок)
        has_promo: Есть ли активные промокоды
    """
    keyboard_rows = [
        [KeyboardButton(text="🌾 Моя Ферма"), KeyboardButton(text="🏪 Магазин")],
        [KeyboardButton(text="📦 Амбар"), KeyboardButton(text="📜 Квесты")],
        [KeyboardButton(text="🏆 Достижения"), KeyboardButton(text="🚜 Престиж")],
    ]
    
    # Добавляем кнопку промокодов если есть активные
    if has_promo:
        keyboard_rows.append([KeyboardButton(text="🎁 Промокоды")])
    
    keyboard_rows.append([KeyboardButton(text="❓ Помощь")])
    
    return ReplyKeyboardMarkup(
        keyboard=keyboard_rows,
        resize_keyboard=True,
        persistent=True
    )

def get_admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Юзеры"), KeyboardButton(text="⚙️ Настройки")],
            [KeyboardButton(text="💰 Финансы"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="🎁 Бонусы"), KeyboardButton(text="📢 Рассылка")],
            [KeyboardButton(text="🚪 Выйти")]
        ],
        resize_keyboard=True
    )

def get_farm_keyboard(plots: List[Dict]):
    """Динамические кнопки посадки для пустых грядок"""
    inline_rows = []
    
    # Кнопки посадки для пустых грядок
    empty_plots = [p for p in plots if p["status"] == "empty"]
    plant_buttons = []
    for plot in empty_plots:
        plant_buttons.append(InlineKeyboardButton(
            text=f"🌱 Посадить на #{plot['number']}", 
            callback_data=f"plant_{plot['number']}"
        ))
    
    # Добавляем кнопки посадки по 2 в ряд, только если есть кнопки
    if plant_buttons:
        for i in range(0, len(plant_buttons), 2):
            row = plant_buttons[i:i+2]
            if row:  # Проверяем что строка не пустая
                inline_rows.append(row)

    # Кнопки удобрений для растущих грядок
    growing_plots = [p for p in plots if p["status"] == "growing"]
    if growing_plots:
        fertilize_buttons = []
        for plot in growing_plots[:2]:  # Максимум 2 кнопки удобрений
            fertilize_buttons.append(InlineKeyboardButton(
                text=f"⚡ Удобрить #{plot['number']}", 
                callback_data=f"fertilize_{plot['number']}"
            ))
        if fertilize_buttons:
            inline_rows.append(fertilize_buttons)
    
    # Кнопка сбора урожая если есть готовые грядки
    ready_plots = [p for p in plots if p["status"] == "ready"]
    if ready_plots:
        inline_rows.append([InlineKeyboardButton(
            text=f"✅ Собрать урожай ({len(ready_plots)})", 
            callback_data="harvest_all"
        )])
    
    # Кнопки бонуса и обновления
    inline_rows.append([
        InlineKeyboardButton(text="🎁 Забрать бонус", callback_data="claim_daily"),
        InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_farm")
    ])
 
    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_rows)
    return keyboard

def get_shop_categories(categories: Optional[List[Dict]] = None, seasonal_categories: List[str] = None):
    """Клавиатура категорий магазина

    Args:
        categories: Список категорий из БД [{"code": "seed", "name": "Семена", "icon": "🌱"}, ...]
        seasonal_categories: Список кодов сезонных категорий
    """
    if seasonal_categories is None:
        seasonal_categories = []
    
    # Если категории не переданы, используем статичный список
    if not categories:
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🌱 Семена", callback_data="shop_seed"),
                InlineKeyboardButton(text="🧪 Удобрения", callback_data="shop_fertilizer")
            ],
            [
                InlineKeyboardButton(text="🚜 Улучшения", callback_data="shop_upgrade"),
                InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")
            ]
        ])
    
    # Формируем клавиатуру из БД
    inline_rows = []
    current_row = []
    
    for cat in categories:
        icon = cat.get('icon', '📦')
        name = cat.get('name', cat.get('code', '???'))
        code = cat.get('code', '')
        
        # Добавляем метку сезонной категории
        if code in seasonal_categories:
            name = f"{name} 🌟"
        
        button = InlineKeyboardButton(text=f"{icon} {name}", callback_data=f"shop_{code}")
        current_row.append(button)
        
        # Добавляем по 2 кнопки в ряд
        if len(current_row) == 2:
            inline_rows.append(current_row)
            current_row = []
    
    # Добавляем оставшиеся кнопки
    if current_row:
        inline_rows.append(current_row)
    
    # Кнопка назад
    inline_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_rows)

def get_back_keyboard(back_to: str = "farm", label: str = None):
    """Универсальная кнопка назад

    Args:
        back_to: Куда вернуться (farm, main, shop, inventory, etc.)
        label: Текст кнопки (если None, использует стандартный текст)
    """
    if label is None:
        labels = {
            "farm": "🔙 Назад к грядкам",
            "main": "🔙 В главное меню",
            "shop": "🔙 В магазин",
            "inventory": "🔙 В амбар",
            "quests": "🔙 К квестам",
            "achievements": "🔙 К достижениям",
        }
        label = labels.get(back_to, "🔙 Назад")

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data=f"back_{back_to}")]
    ])
 
