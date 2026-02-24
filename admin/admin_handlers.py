# ============================================================
# АДМИН-ПАНЕЛЬ (ТЗ v4.0 п.21)
# ============================================================

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from typing import Dict, List
import logging
import os
import sys

# Добавляем родительскую директорию в путь для импортов
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database  import get_database
from keyboards import get_main_keyboard

router = Router()

# ID создателя бота (загружается из env)
CREATOR_ID = int(os.getenv("CREATOR_ID", "0"))

async def get_db() -> Database:
    """Получает экземпляр БД"""
    return await Database.get_instance()


def is_admin(user_id: int) -> bool:
    """Проверяет является ли пользователь админом"""
    return user_id == CREATOR_ID


# =================== 21.1 ГЛАВНОЕ МЕНЮ АДМИНКИ ===================

@router.message(Command("admin"))
async def admin_handler(message: Message):
    """Главное меню админ-панели - ТЗ v4.0 п.21.1"""
    
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У тебя нет доступа к админ-панели!")
        return
    
    text = (
        f"👑 <b>АДМИН-ПАНЕЛЬ</b>\n\n"
        f"Роль: Создатель 👑\n"
        f"ID: {message.from_user.id}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>ОСНОВНЫЕ РАЗДЕЛЫ:</b>\n\n"
        f"👥 Игроки — управление пользователями\n"
        f"🌱 Растения — настройка культур\n"
        f"💰 Экономика — баланс и цены\n"
        f"🎁 Промо — управление промокодами\n"
        f"📢 Рассылка — массовые сообщения\n"
        f"🏆 Ачивки — настройка достижений\n"
        f"📜 Квесты — настройка заданий\n"
        f"👤 Фермеры — настройка найма\n"
        f"🚜 Улучшения — апгрейды\n"
        f"🎲 Рандом — настройка шансов\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚙️ <b>СИСТЕМА:</b>\n\n"
        f"📊 Статистика — метрики и аналитика\n"
        f"📋 Логи — действия админов\n"
        f"🔄 Миграции — обновление БД\n"
        f"🧪 Тест — тестирование механик"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Игроки", callback_data="admin_users")],
        [InlineKeyboardButton(text="🌱 Растения", callback_data="admin_plants")],
        [InlineKeyboardButton(text="💰 Экономика", callback_data="admin_economy")],
        [InlineKeyboardButton(text="🎁 Промо", callback_data="admin_promo")],
        [InlineKeyboardButton(text="🏆 Ачивки", callback_data="admin_achievements")],
        [InlineKeyboardButton(text="📜 Квесты", callback_data="admin_quests")],
        [InlineKeyboardButton(text="👤 Фермеры", callback_data="admin_farmers")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📋 Логи", callback_data="admin_logs")],
        [InlineKeyboardButton(text="🔙 Выйти", callback_data="back_main")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


# =================== 21.2 УПРАВЛЕНИЕ РАСТЕНИЯМИ ===================

@router.callback_query(F.data == "admin_plants")
async def admin_plants_handler(callback: CallbackQuery):
    """Раздел управления растениями - ТЗ v4.0 п.21.2"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    db = await get_db()
    
    # Получаем список всех растений
    plants = await db.get_shop_items("seed")
    
    text_lines = [
        "🌱 <b>УПРАВЛЕНИЕ РАСТЕНИЯМИ</b>",
        f"",
        f"Всего растений: {len(plants)}",
        f"",
        f"━━━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    buttons = []
    
    for plant in plants[:10]:  # Показываем первые 10
        code = plant.get('item_code', '???')
        name = plant.get('item_name', '???')
        icon = plant.get('item_icon', '🌱')
        buy = plant.get('buy_price', 0)
        sell = plant.get('sell_price', 0)
        active = "✅" if plant.get('is_active', True) else "❌"
        
        text_lines.append(f"{active} {icon} <b>{name}</b> (ID: {code})")
        text_lines.append(f"   Цена: {buy}🪙 | Продажа: {sell}🪙")
        text_lines.append(f"   Время: {plant.get('growth_time', 0)}с | Ур. треб.: {plant.get('required_level', 1)}")
        
        buttons.append(InlineKeyboardButton(
            text=f"✏️ {name[:10]}",
            callback_data=f"admin_edit_plant_{code}"
        ))
    
    text_lines.append(f"",
        f"[➕ Добавить растение] [📋 Категории]"
    )
    
    # Формируем клавиатуру
    keyboard_rows = [[btn] for btn in buttons[:8]]
    keyboard_rows.append([InlineKeyboardButton(text="➕ Добавить растение", callback_data="admin_add_plant")])
    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_handler")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    await callback.message.edit_text("\n".join(text_lines), reply_markup=keyboard, parse_mode="HTML")


# =================== 21.3 УПРАВЛЕНИЕ ИГРОКАМИ ===================

@router.callback_query(F.data == "admin_users")
async def admin_users_handler(callback: CallbackQuery):
    """Раздел управления игроками - ТЗ v4.0 п.21.3"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    db = await get_db()
    
    # Получаем статистику
    stats = await db.get_admin_stats()
    
    text = (
        f"👥 <b>УПРАВЛЕНИЕ ИГРОКАМИ</b>\n\n"
        f"📊 СТАТИСТИКА:\n"
        f"Всего игроков: {stats.get('total_users', 0):,}\n"
        f"Активных сегодня: {stats.get('active_today', 0):,}\n"
        f"Активных за неделю: {stats.get('active_week', 0):,}\n"
        f"Забанено: {stats.get('banned', 0):,}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔍 Поиск игрока по ID или @username"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Найти игрока", callback_data="admin_find_user")],
        [InlineKeyboardButton(text="📋 Последние 10", callback_data="admin_recent_users")],
        [InlineKeyboardButton(text="💰 Топ по балансу", callback_data="admin_top_balance")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_handler")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# =================== 21.5 УПРАВЛЕНИЕ ПРОМОКОДАМИ ===================

@router.callback_query(F.data == "admin_promo")
async def admin_promo_handler(callback: CallbackQuery):
    """Раздел управления промокодами - ТЗ v4.0 п.21.5"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    db = await get_db()
    
    # Получаем активные промокоды
    promos = await db.get_active_promocodes()
    
    text_lines = [
        "🎁 <b>УПРАВЛЕНИЕ ПРОМОКОДАМИ</b>",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━",
        "📋 <b>АКТИВНЫЕ ПРОМО:</b>",
        ""
    ]
    
    for promo in promos[:5]:
        code = promo.get('code', '???')
        p_type = promo.get('type', '???')
        used = promo.get('times_used', 0)
        max_act = promo.get('max_activations', 0)
        limit = f"{used}/{max_act}" if max_act > 0 else "∞"
        
        text_lines.append(f"✅ <b>{code}</b> ({p_type})")
        text_lines.append(f"   Активаций: {limit}")
        if promo.get('reward_coins', 0) > 0:
            text_lines.append(f"   Награда: {promo['reward_coins']:,}🪙")
        text_lines.append("")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin_create_promo")],
        [InlineKeyboardButton(text="📋 Все промокоды", callback_data="admin_all_promos")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_handler")]
    ])
    
    await callback.message.edit_text("\n".join(text_lines), reply_markup=keyboard, parse_mode="HTML")


# =================== 21.6 РАССЫЛКА ===================

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_handler(callback: CallbackQuery):
    """Раздел массовой рассылки - ТЗ v4.0 п.21.6"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    db = await get_db()
    stats = await db.get_admin_stats()
    
    text = (
        f"📢 <b>МАССОВАЯ РАССЫЛКА</b>\n\n"
        f"👥 <b>АУДИТОРИЯ:</b>\n"
        f"• Все игроки: {stats.get('total_users', 0):,}\n"
        f"• Активные сегодня: {stats.get('active_today', 0):,}\n"
        f"• Активные за неделю: {stats.get('active_week', 0):,}\n"
        f"• Новички (<7 дней): {stats.get('new_users', 0):,}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ Внимание! Рассылка может занять время.\n"
        f"Сообщение получат все выбранные пользователи."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Все игроки", callback_data="broadcast_all")],
        [InlineKeyboardButton(text="📅 Активные сегодня", callback_data="broadcast_active_today")],
        [InlineKeyboardButton(text="🆕 Новички", callback_data="broadcast_new")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_handler")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# =================== 21.10 СТАТИСТИКА ===================

@router.callback_query(F.data == "admin_stats")
async def admin_stats_handler(callback: CallbackQuery):
    """Раздел статистики - ТЗ v4.0 п.21.10"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    db = await get_db()
    stats = await db.get_admin_stats()
    
    text = (
        f"📊 <b>СТАТИСТИКА БОТА</b>\n\n"
        f"<b>ОБЩАЯ:</b>\n"
        f"👥 Пользователи: {stats.get('total_users', 0):,}\n"
        f"📊 DAU: {stats.get('active_today', 0):,}\n"
        f"📊 WAU: {stats.get('active_week', 0):,}\n"
        f"💰 Всего монет в игре: {stats.get('total_coins', 0):,}\n"
        f"💎 Всего кристаллов: {stats.get('total_gems', 0):,}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>ЭКОНОМИКА:</b>\n"
        f"📈 Средний баланс: {stats.get('avg_balance', 0):,.0f}🪙\n"
        f"💰 Транзакций сегодня: {stats.get('transactions_today', 0):,}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>АКТИВНОСТЬ:</b>\n"
        f"🌾 Посадок сегодня: {stats.get('plants_today', 0):,}\n"
        f"🌾 Сборов сегодня: {stats.get('harvests_today', 0):,}\n"
        f"📜 Квестов выполнено: {stats.get('quests_completed', 0):,}\n"
        f"🏆 Ачивок получено: {stats.get('achievements_earned', 0):,}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📥 Экспорт", callback_data="admin_export_stats")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_handler")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# =================== 21.4 РЕДАКТОР РАСТЕНИЙ ===================

@router.callback_query(F.data.startswith("admin_edit_plant_"))
async def admin_edit_plant_handler(callback: CallbackQuery):
    """Редактирование растения"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    plant_code = callback.data.replace("admin_edit_plant_", "")
    db = await get_db()
    
    plant = await db.get_shop_item(plant_code)
    if not plant:
        await callback.answer("❌ Растение не найдено!", show_alert=True)
        return
    
    text = (
        f"🌱 <b>РЕДАКТИРОВАНИЕ РАСТЕНИЯ</b>\n\n"
        f"ID: <code>{plant_code}</code>\n"
        f"Название: {plant.get('item_name', '???')}\n"
        f"Иконка: {plant.get('item_icon', '🌱')}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Текущие параметры:</b>\n"
        f"💰 Цена покупки: {plant.get('buy_price', 0):,}🪙\n"
        f"💰 Цена продажи: {plant.get('sell_price', 0):,}🪙\n"
        f"⏱️ Время роста: {plant.get('growth_time', 0)} сек\n"
        f"🌾 Урожайность: {plant.get('yield_amount', 1)}\n"
        f"⭐ Требуемый уровень: {plant.get('required_level', 1)}\n"
        f"📦 Категория: {plant.get('category', 'seed')}\n"
        f"✅ Активно: {'Да' if plant.get('is_active', True) else 'Нет'}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Изменить цены", callback_data=f"admin_edit_price_{plant_code}")],
        [InlineKeyboardButton(text="⏱️ Изменить время", callback_data=f"admin_edit_time_{plant_code}")],
        [InlineKeyboardButton(text="🌾 Изменить урожай", callback_data=f"admin_edit_yield_{plant_code}")],
        [InlineKeyboardButton(text="⭐ Изменить уровень", callback_data=f"admin_edit_level_{plant_code}")],
        [InlineKeyboardButton(text="🔄 Вкл/Выкл", callback_data=f"admin_toggle_plant_{plant_code}")],
        [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"admin_delete_plant_{plant_code}")],
        [InlineKeyboardButton(text="🔙 К списку", callback_data="admin_plants")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "admin_add_plant")
async def admin_add_plant_handler(callback: CallbackQuery):
    """Добавление нового растения"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    text = (
        "🌱 <b>ДОБАВЛЕНИЕ НОВОГО РАСТЕНИЯ</b>\n\n"
        "Формат:\n"
        "<code>/addplant код название икона цена_покупки цена_продажи время_роста</code>\n\n"
        "Пример:\n"
        "<code>/addplant super_carrot Супер морковь 🥕 500 1000 300</code>\n\n"
        "Параметры:\n"
        "• код - уникальный ID (латиница, без пробелов)\n"
        "• название - произвольное\n"
        "• икона - эмодзи\n"
        "• цены в 🪙\n"
        "• время в секундах"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_plants")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# =================== 21.7 НАСТРОЙКА АЧИВОК ===================

@router.callback_query(F.data == "admin_achievements")
async def admin_achievements_handler(callback: CallbackQuery):
    """Настройка ачивок"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    db = await get_db()
    
    # Получаем все категории ачивок
    categories = await db.fetchall(
        "SELECT category_id, name, icon FROM achievement_categories ORDER BY sort_order"
    )
    
    text_lines = [
        "🏆 <b>НАСТРОЙКА АЧИВОК</b>",
        "",
        "Выбери категорию:"
    ]
    
    buttons = []
    for cat in categories:
        cat_id = cat[0]
        name = cat[1]
        icon = cat[2]
        
        # Считаем количество ачивок в категории
        count = await db.fetchone(
            "SELECT COUNT(*) FROM achievements WHERE category_id = ?",
            (cat_id,)
        )
        
        text_lines.append(f"{icon} <b>{name}</b> ({count[0]} ачивок)")
        buttons.append(InlineKeyboardButton(
            text=f"{icon} {name}",
            callback_data=f"admin_achievements_cat_{cat_id}"
        ))
    
    keyboard_rows = [[btn] for btn in buttons]
    keyboard_rows.append([InlineKeyboardButton(text="➕ Добавить ачивку", callback_data="admin_add_achievement")])
    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_handler")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    await callback.message.edit_text("\n".join(text_lines), reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_achievements_cat_"))
async def admin_achievements_category_handler(callback: CallbackQuery):
    """Список ачивок в категории"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    category_id = callback.data.replace("admin_achievements_cat_", "")
    db = await get_db()
    
    # Получаем ачивки категории
    achievements = await db.fetchall(
        """SELECT achievement_code, name, description, requirement_count,
                  reward_coins, reward_gems, reward_multiplier, is_active
           FROM achievements 
           WHERE category_id = ?
           ORDER BY sort_order""",
        (category_id,)
    )
    
    text_lines = [
        f"🏆 <b>АЧИВКИ КАТЕГОРИИ</b>",
        f"",
        f"Всего: {len(achievements)} ачивок",
        f"",
        f"━━━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    buttons = []
    for ach in achievements[:10]:
        code = ach[0]
        name = ach[1]
        req = ach[3]
        coins = ach[4]
        active = "✅" if ach[7] else "❌"
        
        text_lines.append(f"{active} <b>{name}</b>")
        text_lines.append(f"   Требование: {req} | Награда: {coins:,}🪙")
        
        buttons.append(InlineKeyboardButton(
            text=f"✏️ {name[:12]}",
            callback_data=f"admin_edit_ach_{code}"
        ))
    
    keyboard_rows = [[btn] for btn in buttons[:8]]
    keyboard_rows.append([InlineKeyboardButton(text="➕ Добавить", callback_data=f"admin_add_ach_{category_id}")])
    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_achievements")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    await callback.message.edit_text("\n".join(text_lines), reply_markup=keyboard, parse_mode="HTML")


# =================== 21.8 НАСТРОЙКА КВЕСТОВ ===================

@router.callback_query(F.data == "admin_quests")
async def admin_quests_handler(callback: CallbackQuery):
    """Настройка квестов"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    db = await get_db()
    
    # Получаем квесты по типам
    daily = await db.fetchall(
        "SELECT quest_code, name, requirement_value, reward_coins FROM quest_templates WHERE quest_type = 'daily' AND is_active = 1"
    )
    weekly = await db.fetchall(
        "SELECT quest_code, name, requirement_value, reward_coins FROM quest_templates WHERE quest_type = 'weekly' AND is_active = 1"
    )
    
    text_lines = [
        "📜 <b>НАСТРОЙКА КВЕСТОВ</b>",
        "",
        f"📅 Ежедневных: {len(daily)}",
        f"📆 Еженедельных: {len(weekly)}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━",
        "📅 <b>ЕЖЕДНЕВНЫЕ:</b>",
        ""
    ]
    
    for quest in daily[:5]:
        text_lines.append(f"• <b>{quest[1]}</b>")
        text_lines.append(f"  {quest[2]} раз | {quest[3]:,}🪙")
    
    if len(daily) > 5:
        text_lines.append(f"... и еще {len(daily) - 5}")
    
    text_lines.extend(["", "📆 <b>ЕЖЕНЕДЕЛЬНЫЕ:</b>", ""])
    
    for quest in weekly[:3]:
        text_lines.append(f"• <b>{quest[1]}</b>")
        text_lines.append(f"  {quest[2]} раз | {quest[3]:,}🪙")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Ежедневные", callback_data="admin_quests_daily")],
        [InlineKeyboardButton(text="📆 Еженедельные", callback_data="admin_quests_weekly")],
        [InlineKeyboardButton(text="➕ Добавить квест", callback_data="admin_add_quest")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_handler")]
    ])
    
    await callback.message.edit_text("\n".join(text_lines), reply_markup=keyboard, parse_mode="HTML")


# =================== 21.9 НАСТРОЙКА ФЕРМЕРОВ ===================

@router.callback_query(F.data == "admin_farmers")
async def admin_farmers_handler(callback: CallbackQuery):
    """Настройка фермеров"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    db = await get_db()
    
    # Получаем типы фермеров
    farmer_types = await db.fetchall(
        "SELECT type_code, name, icon, price_coins, price_gems, bonus_percent, is_active FROM farmer_types ORDER BY sort_order"
    )
    
    # Получаем статистику
    total_farmers = await db.fetchone("SELECT COUNT(*) FROM farmers WHERE status = 'active'")
    
    text_lines = [
        "👤 <b>НАСТРОЙКА ФЕРМЕРОВ</b>",
        "",
        f"Активных фермеров: {total_farmers[0] if total_farmers else 0}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━",
        "<b>ТИПЫ ФЕРМЕРОВ:</b>",
        ""
    ]
    
    buttons = []
    for ft in farmer_types:
        code = ft[0]
        name = ft[1]
        icon = ft[2]
        price = ft[3] if ft[3] > 0 else f"{ft[4]}💎"
        bonus = ft[5]
        active = "✅" if ft[6] else "❌"
        
        text_lines.append(f"{active} {icon} <b>{name}</b>")
        text_lines.append(f"   Цена: {price} | Бонус: +{bonus}%")
        
        buttons.append(InlineKeyboardButton(
            text=f"✏️ {name[:10]}",
            callback_data=f"admin_edit_farmer_{code}"
        ))
    
    keyboard_rows = [[btn] for btn in buttons]
    keyboard_rows.append([InlineKeyboardButton(text="➕ Добавить тип", callback_data="admin_add_farmer_type")])
    keyboard_rows.append([InlineKeyboardButton(text="📊 Статистика", callback_data="admin_farmers_stats")])
    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_handler")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    await callback.message.edit_text("\n".join(text_lines), reply_markup=keyboard, parse_mode="HTML")


# =================== 21.10 ЛОГИ ===================

@router.callback_query(F.data == "admin_logs")
async def admin_logs_handler(callback: CallbackQuery):
    """Просмотр логов админов"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    db = await get_db()
    logs = await db.get_admin_logs(20)
    
    if not logs:
        text = "📋 <b>ЛОГИ АДМИНОВ</b>\n\nПока нет записей."
    else:
        text_lines = ["📋 <b>ЛОГИ АДМИНОВ</b> (последние 20)", ""]
        
        for log in logs:
            action = log.get('action', '???')
            admin = log.get('admin_username', '???')
            target = log.get('target_username', '')
            time = log.get('created_at', '')[:16]  # Обрезаем секунды
            
            if target:
                text_lines.append(f"[{time}] {admin}: {action} → @{target}")
            else:
                text_lines.append(f"[{time}] {admin}: {action}")
        
        text = "\n".join(text_lines)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_logs")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_handler")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# =================== КОМАНДЫ ДЛЯ РАСТЕНИЙ ===================

@router.message(Command("addplant"))
async def addplant_command(message: Message):
    """Команда добавления растения"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа!")
        return
    
    args = message.text.split()
    if len(args) < 7:
        await message.answer(
            "❌ Неверный формат!\n\n"
            "Используй:\n"
            "<code>/addplant код название икона цена_покупки цена_продажи время_роста</code>\n\n"
            "Пример:\n"
            "<code>/addplant super_carrot Супер_морковь 🥕 500 1000 300</code>"
        )
        return
    
    try:
        code = args[1]
        name = args[2].replace("_", " ")
        icon = args[3]
        buy_price = int(args[4])
        sell_price = int(args[5])
        growth_time = int(args[6])
        
        db = await get_db()
        result = await db.admin_add_plant(
            message.from_user.id, code, name, icon, 
            buy_price, sell_price, growth_time
        )
        
        if result:
            await message.answer(
                f"✅ <b>Растение добавлено!</b>\n\n"
                f"Код: <code>{code}</code>\n"
                f"Название: {icon} {name}\n"
                f"Цена покупки: {buy_price:,}🪙\n"
                f"Цена продажи: {sell_price:,}🪙\n"
                f"Время роста: {growth_time} сек"
            )
        else:
            await message.answer("❌ Ошибка добавления растения!")
    except ValueError:
        await message.answer("❌ Ошибка в параметрах! Проверь, что цены и время - числа.")


# =================== КОМАНДЫ ДЛЯ РАССЫЛКИ ===================

@router.callback_query(F.data.startswith("broadcast_"))
async def broadcast_execute_handler(callback: CallbackQuery):
    """Выполнение рассылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    target_type = callback.data.replace("broadcast_", "")
    
    # Запрашиваем текст сообщения
    await callback.message.edit_text(
        f"📢 <b>РАССЫЛКА</b>\n\n"
        f"Цель: {target_type}\n\n"
        f"Отправь текст сообщения для рассылки:\n"
        f"(или /cancel для отмены)",
        parse_mode="HTML"
    )
    
    # Устанавливаем состояние ожидания текста
    # Здесь должна быть логика FSM, пока просто пример
    await callback.answer("Введи текст сообщения")


# =================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ===================

@router.callback_query(F.data == "admin_handler")
async def back_to_admin(callback: CallbackQuery):
    """Возврат в админ-панель"""
    await admin_handler(callback.message)
