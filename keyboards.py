from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌾 Моя Ферма"), KeyboardButton(text="🏪 Магазин")],
            [KeyboardButton(text="📦 Амбар"), KeyboardButton(text="📜 Квесты")],
            [KeyboardButton(text="🏆 Достижения"), KeyboardButton(text="🚜 Престиж")]
        ],
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
    
    # Добавляем кнопки посадки по 2 в ряд
    for i in range(0, len(plant_buttons), 2):
        inline_rows.append(plant_buttons[i:i+2])
    
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

def get_shop_categories():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌱 Семена", callback_data="shop_seeds"),
            InlineKeyboardButton(text="🧪 Удобрения", callback_data="shop_fertilizers")
        ],
        [
            InlineKeyboardButton(text="🚜 Улучшения", callback_data="shop_upgrades"),
            InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")
        ]
    ])

def get_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к грядкам", callback_data="back_farm")]
    ])
 
