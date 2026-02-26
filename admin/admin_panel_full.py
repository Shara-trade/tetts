"""
Полноценная админ-панель для Lazy Farmer Bot
Полностью инлайн-интерфейс, единая команда /admin
Версия: 2.0 (полная переработка)
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
from database import get_database
import asyncio
import json

router = Router()

# ==================== FSM СОСТОЯНИЯ ====================

class AdminFSM(StatesGroup):
    # Поиск игроков
    search_unified = State()  # Объединенный поиск (ID или username)
    
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

    # Редактирование растений
    plant_edit_text = State()
    plant_edit_number = State()

    # Редактирование промокодов
    promo_edit_code = State()
    promo_edit_reward = State()
    promo_edit_uses = State()
    promo_edit_date = State()
    promo_delete_confirm = State()

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

async def get_db():
    return await get_database()

async def check_admin_access(user_id: int) -> str:
    """Проверяет доступ и возвращает роль"""
    db = await get_db()
    return await db.get_admin_role(user_id)

def get_role_emoji(role: str) -> str:
    return {'creator': '👑', 'admin': '⚡️', 'moderator': '🛡️'}.get(role, '❓')

def get_nav_buttons(back_callback: str = "admin_back_main", show_home: bool = True) -> list:
    """Стандартные кнопки навигации"""
    buttons = [InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback)]
    if show_home:
        buttons.append(InlineKeyboardButton(text="🏠 Главное меню", callback_data="admin_back_main"))
    return buttons

def paginate_buttons(items: list, page: int, per_page: int, 
                     callback_prefix: str, total_count: int = None) -> tuple:
    """Создает кнопки с пагинацией"""
    if total_count is None:
        total_count = len(items)
    
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    
    start = page * per_page
    end = min(start + per_page, total_count)
    page_items = items[start:end]
    
    # Кнопки навигации
    nav_buttons = []
    if total_pages > 1:
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"{callback_prefix}_{page-1}"))
        nav_buttons.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"{callback_prefix}_{page+1}"))
    
    return page_items, nav_buttons, page + 1, total_pages

async def log_admin_action(admin_id: int, action: str, target_id: int = None, details: dict = None):
    """Логирует действие админа"""
    db = await get_db()
    try:
        await db.log_admin_action(admin_id, action, target_id, details)
    except:
        pass  # Игнорируем ошибки логирования

# ==================== ГЛАВНОЕ МЕНЮ ====================

@router.message(Command("admin"))
async def admin_main_menu(message: Message, state: FSMContext):
    """Главное меню админ-панели"""
    await state.clear()
    await show_admin_menu(message, message.from_user.id)

async def show_admin_menu(target, user_id: int, edit: bool = False):
    """Показывает меню админки"""
    role = await check_admin_access(user_id)
    if not role:
        if isinstance(target, CallbackQuery):
            await target.answer("⛔ У тебя нет доступа к админ-панели!", show_alert=True)
        else:
            await target.answer("⛔ У тебя нет доступа к админ-панели!")
        return
    
    # Базовые разделы для всех
    buttons = [
        [InlineKeyboardButton(text="👥 Игроки", callback_data="admin_players")],
        [InlineKeyboardButton(text="🌱 Растения", callback_data="admin_plants")],
        [InlineKeyboardButton(text="💰 Экономика", callback_data="admin_economy")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="admin_help")],
    ]
    
    # Admin и Creator видят дополнительные разделы
    if role in ('admin', 'creator'):
        buttons.insert(2, [InlineKeyboardButton(text="🎁 Промо-акции", callback_data="admin_promo")])
        buttons.insert(3, [InlineKeyboardButton(text="⭐️ Ежедневный бонус", callback_data="admin_daily")])
        buttons.insert(4, [InlineKeyboardButton(text="🏆 Управление ачивками", callback_data="admin_achievements")])
    
    # Только Creator видит управление админами и логи
    if role == 'creator':
        buttons.append([InlineKeyboardButton(text="👑 Управление админами", callback_data="admin_manage_admins")])
        buttons.append([InlineKeyboardButton(text="📊 Логи действий", callback_data="admin_logs")])
        buttons.append([InlineKeyboardButton(text="⚙️ Настройки системы", callback_data="admin_settings")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    text = (
        f"{get_role_emoji(role)} <b>Админ-панель Lazy Farmer</b>\n\n"
        f"Твоя роль: <b>{role.upper()}</b>\n"
        f"ID: <code>{user_id}</code>\n\n"
        f"Выбери раздел:"
    )
    
    if isinstance(target, CallbackQuery):
        if edit:
            await target.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await target.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "admin_back_main")
async def admin_back_to_main(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    await show_admin_menu(callback, callback.from_user.id, edit=True)

@router.callback_query(F.data == "noop")
async def noop_handler(callback: CallbackQuery):
    """Пустой обработчик для кнопок без действия"""
    await callback.answer()

# ==================== РАЗДЕЛ «ИГРОКИ» ====================

@router.callback_query(F.data == "admin_players")
async def admin_players_menu(callback: CallbackQuery, state: FSMContext):
    """Меню управления игроками"""
    await state.clear()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Поиск", callback_data="admin_search_unified")],
        [InlineKeyboardButton(text="📋 Список игроков", callback_data="admin_list_players_0")],
        [InlineKeyboardButton(text="💰 Топ по балансу", callback_data="admin_top_balance")],
        [InlineKeyboardButton(text="🏆 Топ по уровню", callback_data="admin_top_level")],
        [InlineKeyboardButton(text="📊 Онлайн статистика", callback_data="admin_online_stats")],
        get_nav_buttons(),
    ])
    
    await callback.message.edit_text(
        "👥 <b>Управление игроками. Выбери действие:</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# Объединенный поиск
@router.callback_query(F.data == "admin_search_unified")
async def admin_search_unified(callback: CallbackQuery, state: FSMContext):
    """Объединенный поиск по ID или username"""
    await state.set_state(AdminFSM.search_unified)

    await callback.message.edit_text(
        "🔍 <b>Поиск игрока</b>\n\n"
        "Введи ID или @username игрока:\n"
        "<i>Например: 123456789 или @durov</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_players")]
        ]),
        parse_mode="HTML"
    )

@router.message(AdminFSM.search_unified)
async def admin_process_search_unified(message: Message, state: FSMContext):
    """Обработка объединенного поиска"""
    text = message.text.strip()
    db = await get_db()
    user = None

    # Проверяем: число -> ID, текст -> username
    if text.isdigit():
        # Поиск по ID
        user_id = int(text)
        user = await db.get_user(user_id)
    else:
        # Поиск по username
        username = text.replace('@', '').lower()
        user = await db.get_user_by_username(username)

    await state.clear()

    if not user:
        await message.answer(
            "❌ <b>Игрок не найден!</b>\n\n"
            "Проверь правильность введенных данных.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Новый поиск", callback_data="admin_search_unified")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_players")]
            ]),
            parse_mode="HTML"
        )
        return
    
    await show_user_profile(message, user['user_id'])

# Последние 10 игроков
@router.callback_query(F.data == "admin_last_players")
async def admin_last_players(callback: CallbackQuery):
    """Список последних игроков"""
    db = await get_db()
    
    rows = await db.fetchall(
        """SELECT user_id, first_name, username, joined_date, last_activity 
           FROM users WHERE is_banned = 0 
           ORDER BY joined_date DESC LIMIT 10"""
    )
    
    if not rows:
        await callback.answer("Нет зарегистрированных игроков!")
        return
    
    text_lines = ["📋 <b>Последние 10 игроков</b>\n"]
    keyboard_rows = []
    
    for i, row in enumerate(rows, 1):
        user_id, name, username, joined, last_active = row
        username_text = f"@{username}" if username else "нет @"
        text_lines.append(f"{i}. {name} ({username_text})")
        
        keyboard_rows.append([InlineKeyboardButton(
            text=f"👤 {name[:20]}",
            callback_data=f"admin_profile_{user_id}"
        )])
    
    keyboard_rows.append(get_nav_buttons("admin_players"))
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        parse_mode="HTML"
    )

# ==================== РАЗДЕЛ «ПРОМО-АКЦИИ» ====================

@router.callback_query(F.data == "admin_promo")
async def admin_promo_menu(callback: CallbackQuery, state: FSMContext):
    """Меню промо-кодов"""
    await state.clear()

    role = await check_admin_access(callback.from_user.id)
    if role not in ('admin', 'creator'):
        await callback.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    db = await get_db()
    active_count = await db.fetchone(
        "SELECT COUNT(*) FROM promocodes WHERE is_active = 1 AND valid_until > datetime('now')"
    )
    expired_count = await db.fetchone(
        "SELECT COUNT(*) FROM promocodes WHERE valid_until <= datetime('now')"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать промо", callback_data="admin_create_promo")],
        [InlineKeyboardButton(text="📋 Список промо", callback_data="admin_list_promo_0")],
        [InlineKeyboardButton(text="📊 Статистика активаций", callback_data="admin_promo_stats")],
        [InlineKeyboardButton(text="⚡️ Активные промо", callback_data="admin_promo_active")],
        [InlineKeyboardButton(text="🗑 Просроченные", callback_data="admin_promo_expired")],
        get_nav_buttons(),
    ])
    
    await callback.message.edit_text(
        f"🎁 <b>Управление промо-кодами</b>\n\n"
        f"Активных: {active_count[0]}\n"
        f"Просроченных: {expired_count[0]}\n\n"
        f"Выбери действие:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# Создание промо - пошаговый мастер
@router.callback_query(F.data == "admin_create_promo")
async def admin_create_promo_start(callback: CallbackQuery, state: FSMContext):
    """Шаг 1: Код промо"""
    await state.set_state(AdminFSM.promo_code)
    
    await callback.message.edit_text(
        "🎁 <b>Создание промо - Шаг 1/6</b>\n\n"
        "📝 <b>Код промо:</b>\n"
        "Уникальный код (латиница, цифры)\n"
        "<i>Например: SUMMER2024</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_promo")]
        ]),
        parse_mode="HTML"
    )

@router.message(AdminFSM.promo_code)
async def admin_promo_code(message: Message, state: FSMContext):
    """Шаг 2: Тип промо"""
    code = message.text.strip().upper()
    
    if not code.replace("_", "").isalnum():
        await message.answer("❌ Код должен содержать только латиницу, цифры и _")
        return
    
    # Проверяем уникальность
    db = await get_db()
    exists = await db.fetchone("SELECT 1 FROM promocodes WHERE code = ?", (code,))
    if exists:
        await message.answer("❌ Такой промокод уже существует!")
        return
    
    await state.update_data(code=code)
    await state.set_state(AdminFSM.promo_type)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏰ По времени", callback_data="promo_type_time")],
        [InlineKeyboardButton(text="🔢 По количеству", callback_data="promo_type_count")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_promo")],
    ])
    
    await message.answer(
        "🎁 <b>Шаг 2/6</b> - Тип промо\n\n"
        "Выбери тип промо:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("promo_type_"))
async def admin_promo_type(callback: CallbackQuery, state: FSMContext):
    """Шаг 3: Тип награды"""
    promo_type = callback.data.replace("promo_type_", "")
    await state.update_data(promo_type=promo_type)
    await state.set_state(AdminFSM.promo_reward_type)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Монеты", callback_data="promo_reward_coins")],
        [InlineKeyboardButton(text="💎 Кристаллы", callback_data="promo_reward_gems")],
        [InlineKeyboardButton(text="🌱 Предмет", callback_data="promo_reward_item")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_promo")],
    ])
    
    await callback.message.edit_text(
        "🎁 <b>Шаг 3/6</b> - Тип награды\n\n"
        "Выбери тип награды:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("promo_reward_"))
async def admin_promo_reward_type(callback: CallbackQuery, state: FSMContext):
    """Шаг 4: Количество награды"""
    reward_type = callback.data.replace("promo_reward_", "")
    await state.update_data(reward_type=reward_type)
    await state.set_state(AdminFSM.promo_reward_value)
    
    type_names = {"coins": "монет", "gems": "кристаллов", "item": "предметов"}
    
    await callback.message.edit_text(
        f"🎁 <b>Шаг 4/6</b> - Количество\n\n"
        f"Введи количество {type_names.get(reward_type, 'награды')}:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_promo")]
        ]),
        parse_mode="HTML"
    )

@router.message(AdminFSM.promo_reward_value)
async def admin_promo_reward_value(message: Message, state: FSMContext):
    """Шаг 5: Лимиты"""
    try:
        value = int(message.text.strip())
        if value <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи положительное число!")
        return
    
    data = await state.get_data()
    await state.update_data(reward_value=value)
    
    if data['promo_type'] == 'count':
        await state.set_state(AdminFSM.promo_limit)
        await message.answer(
            "🎁 <b>Шаг 5/6</b> - Лимит активаций\n\n"
            "Введи максимальное количество активаций\n"
            "(0 = безлимит):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_promo")]
            ]),
            parse_mode="HTML"
        )
    else:
        await state.set_state(AdminFSM.promo_dates)
        await message.answer(
            "🎁 <b>Шаг 5/6</b> - Даты действия\n\n"
            "Введи даты в формате:\n"
            "<code>ДД.ММ.ГГГГ - ДД.ММ.ГГГГ</code>\n\n"
            "<i>Например: 01.06.2024 - 30.06.2024</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_promo")]
            ]),
            parse_mode="HTML"
        )

@router.message(AdminFSM.promo_limit)
async def admin_promo_limit(message: Message, state: FSMContext):
    """Шаг 6: Лимит на игрока"""
    try:
        limit = int(message.text.strip())
        if limit < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи неотрицательное число!")
        return
    
    await state.update_data(max_uses=limit)
    await state.set_state(AdminFSM.promo_per_user)
    
    await message.answer(
        "🎁 <b>Шаг 6/6</b> - Лимит на игрока\n\n"
        "Введи сколько раз один игрок может активировать:\n"
        "<i>По умолчанию: 1</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_promo")]
        ]),
        parse_mode="HTML"
    )

@router.message(AdminFSM.promo_dates)
async def admin_promo_dates(message: Message, state: FSMContext):
    """Обработка дат для временного промо"""
    try:
        text = message.text.strip()
        dates = text.split("-")
        if len(dates) != 2:
            raise ValueError
        
        start_date = datetime.strptime(dates[0].strip(), "%d.%m.%Y")
        end_date = datetime.strptime(dates[1].strip(), "%d.%m.%Y")
        
        await state.update_data(
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d")
        )
        await state.set_state(AdminFSM.promo_per_user)
        
        await message.answer(
            "🎁 <b>Шаг 6/6</b> - Лимит на игрока\n\n"
            "Введи сколько раз один игрок может активировать:\n"
            "<i>По умолчанию: 1</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_promo")]
            ]),
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Неверный формат! Используй: ДД.ММ.ГГГГ - ДД.ММ.ГГГГ")

@router.message(AdminFSM.promo_per_user)
async def admin_promo_per_user(message: Message, state: FSMContext):
    """Подтверждение создания промо"""
    data = await state.get_data()
    await state.set_state(AdminFSM.promo_confirm)
    
    # Формируем превью
    reward_text = f"{data['reward_value']}"
    if data['reward_type'] == 'coins':
        reward_text += "🪙"
    elif data['reward_type'] == 'gems':
        reward_text += "💎"
    else:
        reward_text += "🌱"
    
    limit_text = ""
    if data['promo_type'] == 'count':
        limit_text = f"📊 Лимит: {data['max_uses'] if data['max_uses'] > 0 else 'Безлимит'} активаций"
    else:
        limit_text = f"📅 С {data['start_date']} по {data['end_date']}"
    
    preview = f"""🎁 <b>Предпросмотр промо</b>

📝 Код: <code>{data['code']}</code>
🎁 Награда: {reward_text}
{limit_text}

Сохранить промокод?"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Сохранить", callback_data="admin_save_promo")],
        [InlineKeyboardButton(text="🔄 Заново", callback_data="admin_create_promo")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_promo")],
    ])
    
    await message.answer(preview, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "admin_save_promo")
async def admin_save_promo(callback: CallbackQuery, state: FSMContext):
    """Сохранение промокода"""
    data = await state.get_data()
    db = await get_db()
    
    try:
        # Формируем награды
        rewards = {}
        if data['reward_type'] == 'coins':
            rewards['coins'] = data['reward_value']
        elif data['reward_type'] == 'gems':
            rewards['gems'] = data['reward_value']
        else:
            rewards['items'] = {"seed": data['reward_value']}
        
        # Определяем даты
        if data['promo_type'] == 'time':
            valid_until = data['end_date'] + " 23:59:59"
            max_uses = 0
        else:
            valid_until = "2099-12-31"
            max_uses = data['max_uses']
        
        await db.execute(
            """INSERT INTO promocodes 
               (code, reward_json, description, max_uses, valid_until, is_active)
               VALUES (?, ?, ?, ?, ?, 1)""",
            (data['code'], json.dumps(rewards), f"Промокод {data['code']}", 
             max_uses, valid_until),
            commit=True
        )
        
        # Логируем
        await log_admin_action(
            callback.from_user.id,
            "create_promo",
            None,
            {"code": data['code'], "reward": rewards}
        )
        
        await callback.message.edit_text(
            f"✅ <b>Промокод создан!</b>\n\n"
            f"📝 Код: <code>{data['code']}</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 К списку", callback_data="admin_list_promo_0")],
                [InlineKeyboardButton(text="➕ Создать еще", callback_data="admin_create_promo")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="admin_back_main")],
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ <b>Ошибка создания:</b>\n<code>{str(e)}</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Повторить", callback_data="admin_create_promo")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_promo")],
            ]),
            parse_mode="HTML"
        )
    
    await state.clear()

# ==================== РАЗДЕЛ «РАССЫЛКА» ====================

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_menu(callback: CallbackQuery, state: FSMContext):
    """Меню рассылки"""
    await state.clear()
    
    db = await get_db()
    total_users = await db.fetchone("SELECT COUNT(*) FROM users WHERE is_banned = 0")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📨 Создать рассылку", callback_data="admin_broadcast_new")],
        [InlineKeyboardButton(text="🎯 Выбрать аудиторию", callback_data="admin_broadcast_audience")],
        get_nav_buttons(),
    ])
    
    await callback.message.edit_text(
        f"📢 <b>Рассылка сообщений</b>\n\n"
        f"Всего получателей: {total_users[0]:,}\n\n"
        f"Выбери действие:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_broadcast_new")
async def admin_broadcast_new(callback: CallbackQuery, state: FSMContext):
    """Создание рассылки"""
    await state.set_state(AdminFSM.broadcast_content)
    
    await callback.message.edit_text(
        "📢 <b>Создание рассылки</b>\n\n"
        "Отправь текст сообщения:\n"
        "<i>Можно использовать HTML-разметку</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_broadcast")]
        ]),
        parse_mode="HTML"
    )

@router.message(AdminFSM.broadcast_content)
async def admin_broadcast_content(message: Message, state: FSMContext):
    """Получение контента рассылки"""
    content = message.text or message.caption or ""
    
    await state.update_data(content=content, has_photo=bool(message.photo))
    await state.set_state(AdminFSM.broadcast_audience)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Все игроки", callback_data="broadcast_all")],
        [InlineKeyboardButton(text="📅 Активные сегодня", callback_data="broadcast_today")],
        [InlineKeyboardButton(text="🆕 Новички (до 7 дней)", callback_data="broadcast_new")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_broadcast")],
    ])
    
    await message.answer(
        "📢 <b>Выбор аудитории</b>\n\n"
        "Кому отправить сообщение?",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("broadcast_"))
async def admin_broadcast_audience(callback: CallbackQuery, state: FSMContext):
    """Подтверждение рассылки"""
    audience = callback.data.replace("broadcast_", "")
    await state.update_data(audience=audience)
    data = await state.get_data()
    await state.set_state(AdminFSM.broadcast_confirm)
    
    db = await get_db()
    
    # Считаем получателей
    if audience == "all":
        count = await db.fetchone("SELECT COUNT(*) FROM users WHERE is_banned = 0")
        audience_text = "Все игроки"
    elif audience == "today":
        count = await db.fetchone(
            "SELECT COUNT(*) FROM users WHERE last_activity >= date('now') AND is_banned = 0"
        )
        audience_text = "Активные сегодня"
    elif audience == "new":
        count = await db.fetchone(
            "SELECT COUNT(*) FROM users WHERE joined_date >= date('now', '-7 days') AND is_banned = 0"
        )
        audience_text = "Новички (до 7 дней)"
    else:
        count = [0]
        audience_text = "Неизвестно"
    
    preview = f"""📢 <b>Предпросмотр рассылки</b>

👥 Аудитория: {audience_text}
📊 Получателей: {count[0]:,}

<b>Сообщение:</b>
{data['content'][:500]}{'...' if len(data['content']) > 500 else ''}

Отправить?"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить", callback_data="broadcast_confirm")],
        [InlineKeyboardButton(text="🔄 Тест (себе)", callback_data="broadcast_test")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_broadcast")],
    ])
    
    await callback.message.edit_text(preview, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "broadcast_test")
async def admin_broadcast_test(callback: CallbackQuery, state: FSMContext):
    """Тестовая отправка себе"""
    data = await state.get_data()
    
    try:
        await callback.message.answer(
            f"📢 <b>ТЕСТОВАЯ РАССЫЛКА</b>\n\n{data['content']}",
            parse_mode="HTML"
        )
        await callback.answer("✅ Тестовое сообщение отправлено!")
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {str(e)[:100]}", show_alert=True)

@router.callback_query(F.data == "broadcast_confirm")
async def admin_broadcast_send(callback: CallbackQuery, state: FSMContext):
    """Отправка рассылки"""
    data = await state.get_data()
    db = await get_db()
    
    # Получаем список получателей
    if data['audience'] == "all":
        users = await db.fetchall(
            "SELECT user_id FROM users WHERE is_banned = 0"
        )
    elif data['audience'] == "today":
        users = await db.fetchall(
            "SELECT user_id FROM users WHERE last_activity >= date('now') AND is_banned = 0"
        )
    elif data['audience'] == "new":
        users = await db.fetchall(
            "SELECT user_id FROM users WHERE joined_date >= date('now', '-7 days') AND is_banned = 0"
        )
    else:
        users = []
    
    # Отправляем
    sent = 0
    failed = 0
    
    await callback.message.edit_text(
        f"⏳ <b>Рассылка выполняется...</b>\n\n"
        f"Отправлено: {sent}\n"
        f"Ошибок: {failed}\n"
        f"Всего: {len(users)}",
        parse_mode="HTML"
    )
    
    for user_row in users:
        try:
            await callback.bot.send_message(
                user_row[0],
                data['content'],
                parse_mode="HTML"
            )
            sent += 1
            await asyncio.sleep(0.05)  # Небольшая задержка
        except:
            failed += 1
    
    # Логируем
    await log_admin_action(
        callback.from_user.id,
        "broadcast",
        None,
        {"sent": sent, "failed": failed, "audience": data['audience']}
    )
    
    await callback.message.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📨 Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="admin_back_main")],
        ]),
        parse_mode="HTML"
    )
    
    await state.clear()

# ==================== РАЗДЕЛ «УПРАВЛЕНИЕ АДМИНАМИ» ====================

@router.callback_query(F.data == "admin_manage_admins")
async def admin_manage_admins(callback: CallbackQuery, state: FSMContext):
    """Управление админами (только Creator)"""
    await state.clear()
    
    role = await check_admin_access(callback.from_user.id)
    if role != 'creator':
        await callback.answer("⛔ Только для создателя!", show_alert=True)
        return
    
    db = await get_db()
    admins = await db.get_admins()
    
    text_lines = ["👑 <b>Управление администраторами</b>\n\n<b>Текущие админы:</b>\n"]
    
    for admin in admins:
        emoji = get_role_emoji(admin.get('role', 'moderator'))
        username = admin.get('username') or f"ID:{admin['user_id']}"
        text_lines.append(f"{emoji} @{username} — {admin.get('role', 'moderator')}")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Назначить админа", callback_data="admin_add_admin")],
        [InlineKeyboardButton(text="➕ Назначить модератора", callback_data="admin_add_moderator")],
        [InlineKeyboardButton(text="🗑 Снять роль", callback_data="admin_remove_role")],
        get_nav_buttons(),
    ])
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.in_(["admin_add_admin", "admin_add_moderator"]))
async def admin_add_role_start(callback: CallbackQuery, state: FSMContext):
    """Начало назначения роли"""
    role = "admin" if callback.data == "admin_add_admin" else "moderator"
    await state.update_data(new_role=role)
    await state.set_state(AdminFSM.new_admin_username)
    
    role_name = "администратора" if role == "admin" else "модератора"
    
    await callback.message.edit_text(
        f"👑 <b>Назначение {role_name}</b>\n\n"
        f"Введи username игрока:\n"
        f"<i>Например: @ivanov</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_manage_admins")]
        ]),
        parse_mode="HTML"
    )

@router.message(AdminFSM.new_admin_username)
async def admin_add_role_username(message: Message, state: FSMContext):
    """Подтверждение назначения"""
    username = message.text.strip().replace('@', '').lower()
    data = await state.get_data()
    
    db = await get_db()
    user = await db.get_user_by_username(username)
    
    if not user:
        await message.answer(f"❌ Игрок @{username} не найден!")
        return
    
    # Проверяем не админ ли уже
    existing_role = await db.get_admin_role(user['user_id'])
    if existing_role:
        await message.answer(f"❌ Игрок @{username} уже имеет роль {existing_role}!")
        await state.clear()
        return
    
    await state.update_data(target_user_id=user['user_id'], target_name=user['first_name'])
    await state.set_state(AdminFSM.new_admin_confirm)
    
    role_name = "администратора" if data['new_role'] == "admin" else "модератора"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="admin_confirm_role")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_manage_admins")],
    ])
    
    await message.answer(
        f"👑 <b>Подтверждение</b>\n\n"
        f"Назначить <b>{user['first_name']}</b> (@{username})\n"
        f"на роль <b>{role_name}</b>?",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_confirm_role")
async def admin_confirm_role(callback: CallbackQuery, state: FSMContext):
    """Назначение роли"""
    data = await state.get_data()
    db = await get_db()
    
    try:
        await db.execute(
            """INSERT INTO admin_roles (user_id, role, assigned_by, assigned_at)
               VALUES (?, ?, ?, datetime('now'))""",
            (data['target_user_id'], data['new_role'], callback.from_user.id),
            commit=True
        )
        
        # Логируем
        await log_admin_action(
            callback.from_user.id,
            "add_admin",
            data['target_user_id'],
            {"role": data['new_role']}
        )
        
        role_emoji = get_role_emoji(data['new_role'])
        role_name = "администратором" if data['new_role'] == "admin" else "модератором"
        
        await callback.message.edit_text(
            f"{role_emoji} <b>Роль назначена!</b>\n\n"
            f"{data['target_name']} теперь {role_name}.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👑 К управлению", callback_data="admin_manage_admins")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="admin_back_main")],
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ <b>Ошибка:</b> {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_manage_admins")],
            ]),
            parse_mode="HTML"
        )
    
    await state.clear()

# ==================== РАЗДЕЛ «ЛОГИ» ====================

@router.callback_query(F.data == "admin_logs")
async def admin_logs_menu(callback: CallbackQuery, state: FSMContext):
    """Меню логов (только Creator)"""
    await state.clear()
    
    role = await check_admin_access(callback.from_user.id)
    if role != 'creator':
        await callback.answer("⛔ Только для создателя!", show_alert=True)
        return
    
    db = await get_db()
    
    # Статистика
    today = await db.fetchone(
        "SELECT COUNT(*) FROM admin_logs WHERE date(created_at) = date('now')"
    )
    week = await db.fetchone(
        "SELECT COUNT(*) FROM admin_logs WHERE created_at >= datetime('now', '-7 days')"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👑 Админ-действия", callback_data="logs_group_admin")],
        [InlineKeyboardButton(text="💰 Экономика", callback_data="logs_group_economy")],
        [InlineKeyboardButton(text="🌱 Прогресс", callback_data="logs_group_gameplay")],
        [InlineKeyboardButton(text="🛡️ Безопасность", callback_data="logs_group_security")],
        [InlineKeyboardButton(text="📊 Аналитика", callback_data="logs_analytics")],
        [InlineKeyboardButton(text="⚙️ Очистка", callback_data="logs_cleanup")],
        get_nav_buttons(),
    ])
    
    await callback.message.edit_text(
        f"📊 <b>Система логирования</b>\n\n"
        f"📅 Сегодня: {today[0]} событий\n"
        f"📅 За неделю: {week[0]} событий\n\n"
        f"Выбери категорию:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("logs_group_"))
async def admin_logs_filtered(callback: CallbackQuery):
    """Просмотр логов по группам"""
    group = callback.data.replace("logs_group_", "")
    
    db = await get_db()
    logs = await db.get_filtered_logs(log_group=group, limit=10)
    
    if not logs:
        await callback.message.edit_text(
            f"📋 <b>Логи: {group.upper()}</b>\n\nНет записей.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_logs")],
            ]),
            parse_mode="HTML"
        )
        return
    
    text_lines = [f"📋 <b>Логи: {group.upper()}</b>\n"]
    
    for log in logs:
        emoji = {'DEBUG': '🐞', 'INFO': 'ℹ️', 'WARNING': '⚠️', 'ERROR': '❌'}.get(log.get('level', 'INFO'), '•')
        time_str = log['created_at'][11:19] if log.get('created_at') else '--:--'
        
        text_lines.append(
            f"\n{emoji} {time_str}"
            f"\n👤 {log.get('username') or log.get('user_id') or 'System'}"
            f"\n🔹 {log.get('action', 'unknown')}"
        )
        if log.get('details'):
            details_str = str(log['details'])[:100]
            text_lines.append(f"\n📝 {details_str}")
        text_lines.append("\n" + "━" * 20)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"logs_group_{group}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_logs")],
    ])
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "logs_cleanup")
async def admin_logs_cleanup(callback: CallbackQuery):
    """Очистка логов"""
    await callback.message.edit_text(
        "⚠️ <b>Очистка логов</b>\n\n"
        "Выбери период:\n\n"
        "⚠️ Внимание: удаленные логи нельзя восстановить!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Старше 30 дней", callback_data="logs_cleanup_30")],
            [InlineKeyboardButton(text="🗑 Старше 60 дней", callback_data="logs_cleanup_60")],
            [InlineKeyboardButton(text="🗑 Старше 90 дней", callback_data="logs_cleanup_90")],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_logs")],
        ]),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("logs_cleanup_"))
async def admin_logs_cleanup_confirm(callback: CallbackQuery):
    """Подтверждение очистки"""
    days = int(callback.data.split("_")[2])
    
    db = await get_db()
    
    try:
        await db.execute(
            "DELETE FROM admin_logs WHERE created_at < datetime('now', '-{} days')".format(days),
            commit=True
        )
        
        await log_admin_action(callback.from_user.id, "cleanup_logs", None, {"days": days})
        
        await callback.message.edit_text(
            f"✅ Логи старше {days} дней удалены!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_logs")],
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ <b>Ошибка:</b> {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_logs")],
            ]),
            parse_mode="HTML"
        )

# ==================== СНЯТИЕ РОЛИ АДМИНА ====================

@router.callback_query(F.data == "admin_remove_role")
async def admin_remove_role_start(callback: CallbackQuery, state: FSMContext):
    """Начало снятия роли"""
    db = await get_db()
    admins = await db.get_admins()
    
    if not admins:
        await callback.answer("Нет администраторов для снятия роли!", show_alert=True)
        return
    
    keyboard_rows = []
    for admin in admins:
        username = admin.get('username') or f"ID:{admin['user_id']}"
        role = admin.get('role', 'moderator')
        emoji = get_role_emoji(role)
        keyboard_rows.append([
            InlineKeyboardButton(
                text=f"{emoji} @{username} ({role})",
                callback_data=f"remove_admin_{admin['user_id']}"
            )
        ])
    
    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_manage_admins")])
    
    await callback.message.edit_text(
        "🗑 <b>Снятие роли администратора</b>\n\n"
        "Выбери администратора для снятия роли:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("remove_admin_"))
async def admin_remove_role_confirm(callback: CallbackQuery, state: FSMContext):
    """Подтверждение снятия роли"""
    target_id = int(callback.data.split("_")[2])
    
    # Проверяем не снимаем ли себя
    if target_id == callback.from_user.id:
        await callback.answer("❌ Нельзя снять роль самому себе!", show_alert=True)
        return
    
    db = await get_db()
    admin = await db.fetchone(
        """SELECT ar.user_id, u.first_name, u.username, ar.role
           FROM admin_roles ar
           JOIN users u ON ar.user_id = u.user_id
           WHERE ar.user_id = ?""",
        (target_id,)
    )
    
    if not admin:
        await callback.answer("❌ Админ не найден!", show_alert=True)
        return
    
    user_id, first_name, username, role = admin
    username = username or f"ID:{user_id}"
    role_name = "администратора" if role == "admin" else "модератора"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_remove_{target_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_remove_role")],
    ])
    
    await callback.message.edit_text(
        f"⚠️ <b>Подтверждение снятия роли</b>\n\n"
        f"Снять роль <b>{role_name}</b> у {first_name} (@{username})?\n\n"
        f"⚠️ Это действие нельзя отменить!",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("confirm_remove_"))
async def admin_remove_role_execute(callback: CallbackQuery, state: FSMContext):
    """Выполнение снятия роли"""
    target_id = int(callback.data.split("_")[2])
    
    db = await get_db()
    
    # Получаем информацию до удаления
    admin = await db.fetchone(
        """SELECT u.first_name, u.username, ar.role
           FROM admin_roles ar
           JOIN users u ON ar.user_id = u.user_id
           WHERE ar.user_id = ?""",
        (target_id,)
    )
    
    if not admin:
        await callback.answer("❌ Админ не найден!", show_alert=True)
        return
    
    first_name, username, role = admin
    username = username or f"ID:{target_id}"
    role_name = "администратора" if role == "admin" else "модератора"
    
    try:
        # Удаляем роль
        await db.execute(
            "DELETE FROM admin_roles WHERE user_id = ?",
            (target_id,), commit=True
        )
        
        # Логируем
        await log_admin_action(
            callback.from_user.id,
            "remove_admin",
            target_id,
            {"role": role}
        )
        
        await callback.message.edit_text(
            f"✅ <b>Роль снята!</b>\n\n"
            f"{first_name} (@{username}) больше не является {role_name}.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👑 К управлению", callback_data="admin_manage_admins")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="admin_back_main")],
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ <b>Ошибка:</b> {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_manage_admins")],
            ]),
            parse_mode="HTML"
        )

# ==================== РЕДАКТИРОВАНИЕ РАСТЕНИЙ ====================

@router.callback_query(F.data.startswith("plant_edit_"))
async def admin_plant_edit(callback: CallbackQuery, state: FSMContext):
    """Меню редактирования растения"""
    plant_id = callback.data.replace("plant_edit_", "")
    
    db = await get_db()
    plant = await db.fetchone(
        "SELECT * FROM shop_config WHERE item_code = ? AND category = 'seed'",
        (plant_id,)
    )
    
    if not plant:
        await callback.answer("❌ Растение не найдено!", show_alert=True)
        return
    
    await state.update_data(editing_plant_id=plant_id, original_plant=dict(plant))
    
    grow_min = plant['growth_time'] // 60
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏷️ Название", callback_data="edit_plant_name")],
        [InlineKeyboardButton(text="😊 Эмодзи", callback_data="edit_plant_emoji")],
        [InlineKeyboardButton(text="⏱️ Время роста", callback_data="edit_plant_growtime")],
        [InlineKeyboardButton(text="💰 Цена семян", callback_data="edit_plant_seedprice")],
        [InlineKeyboardButton(text="💵 Цена продажи", callback_data="edit_plant_sellprice")],
        [InlineKeyboardButton(text="🌾 Урожайность", callback_data="edit_plant_yield")],
        [InlineKeyboardButton(text="⭐ Требуемый уровень", callback_data="edit_plant_level")],
        [InlineKeyboardButton(text="✨ Опыт", callback_data="edit_plant_exp")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin_list_plants_0")],
    ])
    
    await callback.message.edit_text(
        f"✏️ <b>Редактирование растения</b>\n\n"
        f"{plant['item_icon']} <b>{plant['item_name']}</b> ({plant['item_code']})\n\n"
        f"⏱️ Время роста: {grow_min} мин\n"
        f"💰 Семена: {plant['buy_price']}🪙 | 💵 Продажа: {plant['sell_price']}🪙\n\n"
        f"Выбери параметр для изменения:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# Обработчики редактирования параметров
@router.callback_query(F.data.startswith("edit_plant_"))
async def admin_plant_edit_field(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования поля"""
    field = callback.data.replace("edit_plant_", "")
    
    field_names = {
        "name": "названия",
        "emoji": "эмодзи",
        "growtime": "времени роста (минуты)",
        "seedprice": "цены семян (монеты)",
        "sellprice": "цены продажи (монеты)",
        "yield": "урожайности",
        "level": "требуемого уровня",
        "exp": "опыта за сбор"
    }
    
    await state.update_data(editing_field=field)
    
    if field in ["name", "emoji"]:
        await state.set_state(AdminFSM.plant_edit_text)
    else:
        await state.set_state(AdminFSM.plant_edit_number)
    
    await callback.message.edit_text(
        f"✏️ <b>Редактирование {field_names.get(field, 'параметра')}</b>\n\n"
        f"Введи новое значение:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_plants")]
        ]),
        parse_mode="HTML"
    )

@router.message(AdminFSM.plant_edit_text)
async def admin_plant_edit_text_value(message: Message, state: FSMContext):
    """Обработка текстового значения"""
    value = message.text.strip()
    data = await state.get_data()
    field = data['editing_field']
    plant_id = data['editing_plant_id']
    
    # Валидация
    if field == "emoji":
        value = value[:2]
    elif field == "name":
        if len(value) < 2:
            await message.answer("❌ Название должно быть не короче 2 символов!")
            return
    
    # Обновляем в БД
    db = await get_db()
    
    field_mapping = {
        "name": "item_name",
        "emoji": "item_icon"
    }
    
    try:
        await db.execute(
            f"UPDATE shop_config SET {field_mapping[field]} = ? WHERE item_code = ? AND category = 'seed'",
            (value, plant_id), commit=True
        )
        
        # Логируем
        await log_admin_action(
            message.from_user.id,
            "edit_plant",
            None,
            {"plant_id": plant_id, "field": field, "value": value}
        )
        
        await message.answer(
            f"✅ <b>Значение обновлено!</b>\n\n"
            f"Новое значение: {value}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 К списку", callback_data=f"admin_list_plants_0")],
                [InlineKeyboardButton(text="✏️ Ред. еще", callback_data=f"plant_edit_{plant_id}")],
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(
            f"❌ <b>Ошибка:</b> {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_plants")]
            ]),
            parse_mode="HTML"
        )
    
    await state.clear()

@router.message(AdminFSM.plant_edit_number)
async def admin_plant_edit_number_value(message: Message, state: FSMContext):
    """Обработка числового значения"""
    try:
        value = int(message.text.strip())
        if value < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи неотрицательное число!")
        return
    
    data = await state.get_data()
    field = data['editing_field']
    plant_id = data['editing_plant_id']
    
    # Валидация
    if field == "growtime" and value <= 0:
        await message.answer("❌ Время роста должно быть положительным!")
        return
    if field == "yield" and value <= 0:
        await message.answer("❌ Урожайность должна быть положительной!")
        return
    
    # Обновляем в БД
    db = await get_db()
    
    field_mapping = {
        "growtime": ("growth_time", value * 60),  # Конвертируем в секунды
        "seedprice": ("buy_price", value),
        "sellprice": ("sell_price", value),
        "yield": ("yield_amount", value),
        "level": ("required_level", value),
        "exp": ("exp_reward", value)
    }
    
    db_field, db_value = field_mapping[field]
    
    try:
        await db.execute(
            f"UPDATE shop_config SET {db_field} = ? WHERE item_code = ? AND category = 'seed'",
            (db_value, plant_id), commit=True
        )
        
        # Логируем
        await log_admin_action(
            message.from_user.id,
            "edit_plant",
            None,
            {"plant_id": plant_id, "field": field, "value": value}
        )
        
        await message.answer(
            f"✅ <b>Значение обновлено!</b>\n\n"
            f"Новое значение: {value}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 К списку", callback_data=f"admin_list_plants_0")],
                [InlineKeyboardButton(text="✏️ Ред. еще", callback_data=f"plant_edit_{plant_id}")],
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(
            f"❌ <b>Ошибка:</b> {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_plants")]
            ]),
            parse_mode="HTML"
        )
    
    await state.clear()

# Активация/деактивация растения
@router.callback_query(F.data.startswith("plant_toggle_"))
async def admin_plant_toggle(callback: CallbackQuery):
    """Переключение активности растения"""
    plant_id = callback.data.replace("plant_toggle_", "")
    
    db = await get_db()
    
    # Проверяем текущее состояние
    plant = await db.fetchone(
        "SELECT is_active FROM shop_config WHERE item_code = ? AND category = 'seed'",
        (plant_id,)
    )
    
    if not plant:
        await callback.answer("❌ Растение не найдено!", show_alert=True)
        return
    
    current_state = plant[0] if plant[0] is not None else 1
    new_state = 0 if current_state else 1
    
    try:
        await db.execute(
            "UPDATE shop_config SET is_active = ? WHERE item_code = ? AND category = 'seed'",
            (new_state, plant_id), commit=True
        )
        
        status = "активировано" if new_state else "деактивировано"
        await callback.answer(f"✅ Растение {status}!")
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {str(e)[:50]}")

# Статистика растения
@router.callback_query(F.data.startswith("plant_stat_"))
async def admin_plant_stat(callback: CallbackQuery):
    """Статистика использования растения"""
    plant_id = callback.data.replace("plant_stat_", "")
    
    db = await get_db()
    
    plant = await db.fetchone(
        """SELECT item_name, item_icon, buy_price, sell_price, growth_time 
           FROM shop_config WHERE item_code = ? AND category = 'seed'""",
        (plant_id,)
    )
    
    if not plant:
        await callback.answer("❌ Растение не найдено!", show_alert=True)
        return
    
    name, icon, buy_price, sell_price, grow_time = plant
    grow_min = grow_time // 60
    
    # Получаем статистику из логов (если есть)
    # Здесь можно добавить реальную статистику из БД
    
    text = f"""📊 <b>Статистика: {icon} {name}</b>

<b>Параметры:</b>
💰 Цена семян: {buy_price}🪙
💵 Цена продажи: {sell_price}🪙
⏱️ Время роста: {grow_min} мин
💸 Прибыль: {sell_price - buy_price}🪙

<b>Статистика использования:</b>
🌾 Посажено: ~0 раз
💰 Заработано: ~0🪙

<i>Статистика в разработке...</i>"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"admin_list_plants_0")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

# ==================== СПИСОК ПРОМОКОДОВ С ПАГИНАЦИЕЙ ====================

@router.callback_query(F.data.startswith("admin_list_promo_"))
async def admin_list_promo(callback: CallbackQuery, state: FSMContext):
    """Список промокодов с пагинацией"""
    await state.clear()
    
    try:
        page = int(callback.data.split("_")[3])
    except (IndexError, ValueError):
        page = 0
    
    per_page = 5
    
    db = await get_db()
    promos = await db.fetchall(
        """SELECT code, reward_json, max_uses, times_used, valid_until, is_active
           FROM promocodes ORDER BY created_at DESC"""
    )
    
    total_pages = max(1, (len(promos) + per_page - 1) // per_page)
    start = page * per_page
    end = min(start + per_page, len(promos))
    page_promos = promos[start:end]
    
    if not page_promos:
        await callback.answer("Нет промокодов на этой странице!")
        return
    
    text_lines = [f"🎁 <b>Промокоды (стр. {page + 1}/{total_pages})</b>\n"]
    keyboard_rows = []
    
    for promo in page_promos:
        code, reward_json, max_uses, times_used, valid_until, is_active = promo

        try:
            rewards = json.loads(reward_json) if reward_json else {}
            reward_text = []
            if 'coins' in rewards:
                reward_text.append(f"{rewards['coins']}🪙")
            if 'gems' in rewards:
                reward_text.append(f"{rewards['gems']}💎")
            if 'items' in rewards:
                reward_text.append(f"🌱")
        except:
            reward_text = ["?"]
        
        status = "✅" if is_active else "❌"
        limit_text = f"{times_used}/{max_uses}" if max_uses > 0 else f"{times_used}/∞"
        
        text_lines.append(
            f"{status} <code>{code}</code> | {' '.join(reward_text)}\n"
            f"   Использовано: {limit_text} | До: {valid_until[:10] if valid_until else '∞'}\n"
        )
        
        keyboard_rows.append([
            InlineKeyboardButton(text="✏️ Ред", callback_data=f"promo_edit_{code}"),
            InlineKeyboardButton(text="⏸️ Акт", callback_data=f"promo_toggle_{code}"),
            InlineKeyboardButton(text="🗑 Уд", callback_data=f"promo_delete_{code}"),
        ])
    
    # Кнопки навигации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"admin_list_promo_{page-1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"admin_list_promo_{page+1}"))
    
    if nav_buttons:
        keyboard_rows.append(nav_buttons)
    
    keyboard_rows.append([
        InlineKeyboardButton(text="➕ Создать", callback_data="admin_create_promo"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_promo")
    ])
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        parse_mode="HTML"
    )

# ==================== РЕДАКТИРОВАНИЕ ПРОМОКОДОВ ====================

@router.callback_query(F.data.startswith("promo_edit_"))
async def admin_promo_edit(callback: CallbackQuery, state: FSMContext):
    """Меню редактирования промокода"""
    promo_id = int(callback.data.replace("promo_edit_", ""))
    
    db = await get_db()
    promo = await db.get_promocode_by_id(promo_id) if hasattr(db, 'get_promocode_by_id') else None
    
    if not promo:
        # Альтернативный способ получения
        row = await db.fetchone("SELECT * FROM promocodes WHERE id = ?", (promo_id,))
        if not row:
            await callback.answer("❌ Промокод не найден!", show_alert=True)
            return
        
        import json
        promo = {
            "id": row[0],
            "code": row[1],
            "reward_json": row[2],
            "max_uses": row[3],
            "times_used": row[4],
            "valid_until": row[5],
            "is_active": bool(row[6]),
            "created_by": row[7],
            "created_at": row[8]
        }
    
    await state.update_data(editing_promo_id=promo_id, original_promo=dict(promo))
    
    # Парсим награды
    try:
        rewards = json.loads(promo['reward_json']) if promo['reward_json'] else {}
    except:
        rewards = {}
    
    reward_text = []
    if 'coins' in rewards:
        reward_text.append(f"{rewards['coins']}🪙")
    if 'gems' in rewards:
        reward_text.append(f"{rewards['gems']}💎")
    if 'items' in rewards:
        reward_text.append(f"🌱")
    
    status = "✅ Активен" if promo['is_active'] else "❌ Неактивен"
    limit_text = f"{promo['times_used']}/{promo['max_uses']}" if promo['max_uses'] > 0 else f"{promo['times_used']}/∞"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏷️ Код", callback_data="edit_promo_code")],
        [InlineKeyboardButton(text="🎁 Награды", callback_data="edit_promo_reward")],
        [InlineKeyboardButton(text="🔢 Лимит активаций", callback_data="edit_promo_uses")],
        [InlineKeyboardButton(text="📅 Срок действия", callback_data="edit_promo_date")],
        [InlineKeyboardButton(text="⏸️ Активность", callback_data=f"promo_toggle_{promo['code']}")],
        [InlineKeyboardButton(text="❌ Удалить", callback_data=f"promo_delete_{promo['code']}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_list_promo_0")],
    ])
    
    await callback.message.edit_text(
        f"✏️ <b>Редактирование промокода</b>\n\n"
        f"📝 Код: <code>{promo['code']}</code>\n"
        f"🎁 Награда: {' '.join(reward_text) if reward_text else 'Нет'}\n"
        f"🔢 Использовано: {limit_text}\n"
        f"📅 До: {promo['valid_until'][:10] if promo['valid_until'] else '∞'}\n"
        f"📊 Статус: {status}\n\n"
        f"Выбери параметр для изменения:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("edit_promo_"))
async def admin_promo_edit_field(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования поля"""
    field = callback.data.replace("edit_promo_", "")
    
    field_names = {
        "code": "кода",
        "reward": "награды",
        "uses": "лимита активаций",
        "date": "срока действия"
    }
    
    await state.update_data(editing_promo_field=field)
    
    if field == "reward":
        await state.set_state(AdminFSM.promo_edit_reward)
        await callback.message.edit_text(
            f"✏️ <b>Редактирование награды</b>\n\n"
            f"Формат: <code>тип:количество</code>\n"
            f"Доступные типы: coins, gems, items\n\n"
            f"<i>Например: coins:500</i>\n"
            f"<i>Или: gems:10</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_promo")]
            ]),
            parse_mode="HTML"
        )
    elif field == "date":
        await state.set_state(AdminFSM.promo_edit_date)
        await callback.message.edit_text(
            f"✏️ <b>Редактирование срока действия</b>\n\n"
            f"Введи дату окончания в формате:\n"
            f"<code>ДД.ММ.ГГГГ</code>\n\n"
            f"<i>Или 0 для бессрочного</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_promo")]
            ]),
            parse_mode="HTML"
        )
    elif field == "uses":
        await state.set_state(AdminFSM.promo_edit_uses)
        await callback.message.edit_text(
            f"✏️ <b>Редактирование лимита активаций</b>\n\n"
            f"Введи новый лимит:\n"
            f"<i>0 = безлимит</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_promo")]
            ]),
            parse_mode="HTML"
        )
    else:
        await state.set_state(AdminFSM.promo_edit_code)
        await callback.message.edit_text(
            f"✏️ <b>Редактирование кода</b>\n\n"
            f"Введи новый код промокода:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_promo")]
            ]),
            parse_mode="HTML"
        )

@router.message(AdminFSM.promo_edit_code)
async def admin_promo_edit_code_value(message: Message, state: FSMContext):
    """Редактирование кода"""
    code = message.text.strip().upper()
    
    if not code.replace("_", "").isalnum():
        await message.answer("❌ Код должен содержать только латиницу, цифры и _")
        return
    
    data = await state.get_data()
    promo_id = data['editing_promo_id']
    
    # Проверяем уникальность
    db = await get_db()
    existing = await db.fetchone(
        "SELECT 1 FROM promocodes WHERE code = ? AND id != ?",
        (code, promo_id)
    )
    if existing:
        await message.answer("❌ Такой код уже существует!")
        return
    
    # Обновляем
    await db.execute(
        "UPDATE promocodes SET code = ? WHERE id = ?",
        (code, promo_id), commit=True
    )
    
    await log_admin_action(
        message.from_user.id,
        "edit_promo",
        None,
        {"promo_id": promo_id, "field": "code", "new_value": code}
    )
    
    await message.answer(
        f"✅ <b>Код обновлен!</b>\n\n"
        f"Новый код: <code>{code}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 К списку", callback_data="admin_list_promo_0")],
        ]),
        parse_mode="HTML"
    )
    
    await state.clear()

@router.message(AdminFSM.promo_edit_reward)
async def admin_promo_edit_reward_value(message: Message, state: FSMContext):
    """Редактирование награды"""
    try:
        text = message.text.strip().lower()
        if ':' not in text:
            raise ValueError
        
        reward_type, value = text.split(':')
        reward_type = reward_type.strip()
        value = int(value.strip())
        
        if reward_type not in ['coins', 'gems', 'items']:
            raise ValueError
        
        if value <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Неверный формат! Используй: тип:количество (например: coins:500)")
        return
    
    data = await state.get_data()
    promo_id = data['editing_promo_id']
    db = await get_db()
    
    # Получаем текущие награды
    row = await db.fetchone("SELECT reward_json FROM promocodes WHERE id = ?", (promo_id,))
    import json
    rewards = json.loads(row[0]) if row and row[0] else {}
    
    # Обновляем
    rewards[reward_type] = value
    
    await db.execute(
        "UPDATE promocodes SET reward_json = ? WHERE id = ?",
        (json.dumps(rewards), promo_id), commit=True
    )
    
    await log_admin_action(
        message.from_user.id,
        "edit_promo",
        None,
        {"promo_id": promo_id, "field": "reward", "new_value": rewards}
    )
    
    await message.answer(
        f"✅ <b>Награда обновлена!</b>\n\n"
        f"{reward_type}: {value}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 К списку", callback_data="admin_list_promo_0")],
        ]),
        parse_mode="HTML"
    )
    
    await state.clear()

@router.message(AdminFSM.promo_edit_uses)
async def admin_promo_edit_uses_value(message: Message, state: FSMContext):
    """Редактирование лимита активаций"""
    try:
        max_uses = int(message.text.strip())
        if max_uses < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи неотрицательное число!")
        return
    
    data = await state.get_data()
    promo_id = data['editing_promo_id']
    db = await get_db()
    
    await db.execute(
        "UPDATE promocodes SET max_uses = ? WHERE id = ?",
        (max_uses, promo_id), commit=True
    )
    
    await log_admin_action(
        message.from_user.id,
        "edit_promo",
        None,
        {"promo_id": promo_id, "field": "max_uses", "new_value": max_uses}
    )
    
    limit_text = f"{max_uses} активаций" if max_uses > 0 else "Безлимит"
    
    await message.answer(
        f"✅ <b>Лимит обновлен!</b>\n\n"
        f"Новый лимит: {limit_text}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 К списку", callback_data="admin_list_promo_0")],
        ]),
        parse_mode="HTML"
    )
    
    await state.clear()

@router.message(AdminFSM.promo_edit_date)
async def admin_promo_edit_date_value(message: Message, state: FSMContext):
    """Редактирование срока действия"""
    text = message.text.strip()
    
    if text == "0":
        valid_until = None
    else:
        try:
            valid_until = datetime.strptime(text, "%d.%m.%Y").strftime("%Y-%m-%d 23:59:59")
        except ValueError:
            await message.answer("❌ Неверный формат! Используй: ДД.ММ.ГГГГ (или 0 для бессрочного)")
            return
    
    data = await state.get_data()
    promo_id = data['editing_promo_id']
    db = await get_db()
    
    await db.execute(
        "UPDATE promocodes SET valid_until = ? WHERE id = ?",
        (valid_until, promo_id), commit=True
    )
    
    await log_admin_action(
        message.from_user.id,
        "edit_promo",
        None,
        {"promo_id": promo_id, "field": "valid_until", "new_value": valid_until}
    )
    
    date_text = valid_until[:10] if valid_until else "Бессрочно"
    
    await message.answer(
        f"✅ <b>Срок действия обновлен!</b>\n\n"
        f"До: {date_text}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 К списку", callback_data="admin_list_promo_0")],
        ]),
        parse_mode="HTML"
    )
    
    await state.clear()

# Активация/деактивация промокода
@router.callback_query(F.data.startswith("promo_toggle_"))
async def admin_promo_toggle(callback: CallbackQuery):
    """Переключение активности промокода"""
    code = callback.data.replace("promo_toggle_", "")
    
    db = await get_db()
    
    # Получаем текущий статус
    row = await db.fetchone(
        "SELECT is_active FROM promocodes WHERE code = ?",
        (code,)
    )
    
    if not row:
        await callback.answer("❌ Промокод не найден!", show_alert=True)
        return
    
    current = row[0] if row[0] is not None else 1
    new_state = 0 if current else 1
    
    await db.execute(
        "UPDATE promocodes SET is_active = ? WHERE code = ?",
        (new_state, code), commit=True
    )
    
    await log_admin_action(
        callback.from_user.id,
        "toggle_promo",
        None,
        {"code": code, "new_state": new_state}
    )
    
    status = "активирован" if new_state else "деактивирован"
    await callback.answer(f"✅ Промокод {status}!")

# Удаление промокода
@router.callback_query(F.data.startswith("promo_delete_"))
async def admin_promo_delete_start(callback: CallbackQuery, state: FSMContext):
    """Начало удаления промокода"""
    code = callback.data.replace("promo_delete_", "")
    
    await state.update_data(deleting_promo_code=code)
    await state.set_state(AdminFSM.promo_delete_confirm)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Мягкое удаление (деактивация)", callback_data="confirm_delete_soft")],
        [InlineKeyboardButton(text="🔥 Полное удаление", callback_data="confirm_delete_hard")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_list_promo_0")],
    ])
    
    await callback.message.edit_text(
        f"⚠️ <b>Удаление промокода</b>\n\n"
        f"Код: <code>{code}</code>\n\n"
        f"Выбери тип удаления:\n"
        f"• <b>Мягкое:</b> просто деактивировать\n"
        f"• <b>Полное:</b> удалить из БД",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("confirm_delete_"))
async def admin_promo_delete_execute(callback: CallbackQuery, state: FSMContext):
    """Выполнение удаления"""
    delete_type = callback.data.replace("confirm_delete_", "")
    data = await state.get_data()
    code = data['deleting_promo_code']
    
    db = await get_db()
    
    try:
        if delete_type == "soft":
            # Мягкое удаление
            await db.execute(
                "UPDATE promocodes SET is_active = 0 WHERE code = ?",
                (code,), commit=True
            )
            result_text = "Промокод деактивирован"
        else:
            # Полное удаление
            await db.execute(
                "DELETE FROM promo_activations WHERE promo_id = (SELECT id FROM promocodes WHERE code = ?)",
                (code,), commit=True
            )
            await db.execute(
                "DELETE FROM promocodes WHERE code = ?",
                (code,), commit=True
            )
            result_text = "Промокод удален"
        
        await log_admin_action(
            callback.from_user.id,
            "delete_promo",
            None,
            {"code": code, "delete_type": delete_type}
        )
        
        await callback.message.edit_text(
            f"✅ <b>{result_text}!</b>\n\n"
            f"Код: <code>{code}</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 К списку", callback_data="admin_list_promo_0")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="admin_back_main")],
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ <b>Ошибка:</b> {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_list_promo_0")],
            ]),
            parse_mode="HTML"
        )
    
    await state.clear()

# Статистика промокодов
@router.callback_query(F.data == "admin_promo_stats")
async def admin_promo_stats(callback: CallbackQuery):
    """Статистика активаций промокодов"""
    db = await get_db()
    
    # Общая статистика
    total = await db.fetchone("SELECT COUNT(*) FROM promocodes")
    active = await db.fetchone("SELECT COUNT(*) FROM promocodes WHERE is_active = 1")
    total_uses = await db.fetchone("SELECT SUM(times_used) FROM promocodes")
    
    # Топ промокодов по активациям
    top_promos = await db.fetchall(
        """SELECT code, times_used, max_uses, is_active
           FROM promocodes
           ORDER BY times_used DESC
           LIMIT 10"""
    )
    
    text_lines = [
        f"📊 <b>Статистика промокодов</b>\n\n"
        f"<b>Общая:</b>\n"
        f"• Всего промокодов: {total[0]}\n"
        f"• Активных: {active[0]}\n"
        f"• Всего активаций: {total_uses[0] if total_uses[0] else 0}\n\n"
        f"<b>🏆 Топ по активациям:</b>\n"
    ]
    
    for i, promo in enumerate(top_promos, 1):
        status = "✅" if promo[3] else "❌"
        limit = promo[2] if promo[2] > 0 else "∞"
        text_lines.append(f"{i}. {status} <code>{promo[0]}</code> - {promo[1]}/{limit}")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_promo_stats")],
        get_nav_buttons("admin_promo"),
    ])
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# Активные промокоды
@router.callback_query(F.data == "admin_promo_active")
async def admin_promo_active(callback: CallbackQuery, state: FSMContext):
    """Список активных промокодов"""
    await state.clear()
    
    db = await get_db()
    promos = await db.fetchall(
        """SELECT id, code, reward_json, max_uses, times_used, valid_until
           FROM promocodes
           WHERE is_active = 1
           ORDER BY created_at DESC"""
    )
    
    if not promos:
        await callback.answer("Нет активных промокодов!")
        return
    
    text_lines = ["⚡️ <b>Активные промокоды</b>\n"]
    keyboard_rows = []
    
    import json
    for promo in promos:
        promo_id, code, reward_json, max_uses, times_used, valid_until = promo
        
        try:
            rewards = json.loads(reward_json) if reward_json else {}
            reward_text = []
            if 'coins' in rewards:
                reward_text.append(f"{rewards['coins']}🪙")
            if 'gems' in rewards:
                reward_text.append(f"{rewards['gems']}💎")
        except:
            reward_text = ["?"]
        
        limit_text = f"{times_used}/{max_uses}" if max_uses > 0 else f"{times_used}/∞"
        date_text = valid_until[:10] if valid_until else "∞"
        
        text_lines.append(
            f"• <code>{code}</code> | {' '.join(reward_text)}\n"
            f"  Использовано: {limit_text} | До: {date_text}"
        )
        
        keyboard_rows.append([
            InlineKeyboardButton(text="✏️ Ред", callback_data=f"promo_edit_{promo_id}"),
            InlineKeyboardButton(text="⏸️ Деакт", callback_data=f"promo_toggle_{code}"),
        ])
    
    keyboard_rows.append(get_nav_buttons("admin_promo"))
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        parse_mode="HTML"
    )

# Просроченные промокоды
@router.callback_query(F.data == "admin_promo_expired")
async def admin_promo_expired(callback: CallbackQuery, state: FSMContext):
    """Список просроченных промокодов"""
    await state.clear()
    
    db = await get_db()
    promos = await db.fetchall(
        """SELECT id, code, reward_json, max_uses, times_used, valid_until
           FROM promocodes
           WHERE valid_until < datetime('now')
           ORDER BY valid_until DESC"""
    )
    
    if not promos:
        await callback.answer("Нет просроченных промокодов!")
        return
    
    text_lines = ["🗑 <b>Просроченные промокоды</b>\n"]
    keyboard_rows = []
    
    import json
    for promo in promos:
        promo_id, code, reward_json, max_uses, times_used, valid_until = promo
        
        try:
            rewards = json.loads(reward_json) if reward_json else {}
            reward_text = []
            if 'coins' in rewards:
                reward_text.append(f"{rewards['coins']}🪙")
            if 'gems' in rewards:
                reward_text.append(f"{rewards['gems']}💎")
        except:
            reward_text = ["?"]
        
        limit_text = f"{times_used}/{max_uses}" if max_uses > 0 else f"{times_used}/∞"
        
        text_lines.append(
            f"• <code>{code}</code> | {' '.join(reward_text)}\n"
            f"  Использовано: {limit_text} | До: {valid_until[:10]}"
        )
        
        keyboard_rows.append([
            InlineKeyboardButton(text="✏️ Ред", callback_data=f"promo_edit_{promo_id}"),
            InlineKeyboardButton(text="⏸️ Акт", callback_data=f"promo_toggle_{code}"),
            InlineKeyboardButton(text="🗑 Уд", callback_data=f"promo_delete_{code}"),
        ])
    
    keyboard_rows.append(get_nav_buttons("admin_promo"))
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        parse_mode="HTML"
    )

# ==================== КОРЗИНА УДАЛЕННЫХ РАСТЕНИЙ ====================

@router.callback_query(F.data == "admin_plants_trash")
async def admin_plants_trash(callback: CallbackQuery, state: FSMContext):
    """Корзина удаленных растений"""
    await state.clear()
    
    db = await get_db()
    
    # Получаем неактивные растения
    plants = await db.fetchall(
        """SELECT item_code, item_name, item_icon, buy_price, sell_price, growth_time
           FROM shop_config
           WHERE category = 'seed' AND (is_active = 0 OR is_active IS NULL)
           ORDER BY item_name"""
    )
    
    if not plants:
        await callback.answer("Корзина пуста!")
        return
    
    text_lines = ["🗑 <b>Корзина (удаленные растения)</b>\n"]
    keyboard_rows = []
    
    for plant in plants:
        item_code, item_name, item_icon, buy_price, sell_price, growth_time = plant
        grow_min = growth_time // 60 if growth_time else 0
        
        text_lines.append(
            f"{item_icon} <b>{item_name}</b> ({item_code})\n"
            f"   ⏱️ {grow_min}мин | 💰 {buy_price}🪙 | 💵 {sell_price}🪙\n"
        )
        
        keyboard_rows.append([
            InlineKeyboardButton(text="♻️ Восстановить", callback_data=f"plant_restore_{item_code}"),
            InlineKeyboardButton(text="🔥 Удалить", callback_data=f"plant_delete_hard_{item_code}"),
        ])
    
    keyboard_rows.append(get_nav_buttons("admin_plants"))
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        parse_mode="HTML"
    )

# Восстановление растения
@router.callback_query(F.data.startswith("plant_restore_"))
async def admin_plant_restore(callback: CallbackQuery):
    """Восстановление растения из корзины"""
    item_code = callback.data.replace("plant_restore_", "")
    
    db = await get_db()
    await db.execute(
        "UPDATE shop_config SET is_active = 1 WHERE item_code = ?",
        (item_code,), commit=True
    )
    
    await log_admin_action(
        callback.from_user.id,
        "restore_plant",
        None,
        {"item_code": item_code}
    )
    
    await callback.answer("✅ Растение восстановлено!")
    
# Полное удаление растения
@router.callback_query(F.data.startswith("plant_delete_hard_"))
async def admin_plant_delete_hard(callback: CallbackQuery, state: FSMContext):
    """Полное удаление растения"""
    item_code = callback.data.replace("plant_delete_hard_", "")
    
    # Проверяем нет ли активных посадок
    db = await get_db()
    active_plots = await db.fetchone(
        "SELECT COUNT(*) FROM plots WHERE crop_type = ? AND status IN ('growing', 'ready')",
        (item_code,)
    )
    
    if active_plots and active_plots[0] > 0:
        await callback.answer(
            f"❌ Нельзя удалить! Есть {active_plots[0]} активных посадок этого растения.",
            show_alert=True
        )
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить удаление", callback_data=f"confirm_plant_hard_{item_code}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_plants_trash")],
    ])
    
    await callback.message.edit_text(
        f"⚠️ <b>Полное удаление растения</b>\n\n"
        f"Код: <code>{item_code}</code>\n\n"
        f"⚠️ Это действие нельзя отменить!\n\n"
        f"Подтвердить?",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("confirm_plant_hard_"))
async def admin_plant_delete_hard_confirm(callback: CallbackQuery):
    """Подтверждение полного удаления"""
    item_code = callback.data.replace("confirm_plant_hard_", "")
    
    db = await get_db()
    await db.execute(
        "DELETE FROM shop_config WHERE item_code = ?",
        (item_code,), commit=True
    )
    
    await log_admin_action(
        callback.from_user.id,
        "delete_plant",
        None,
        {"item_code": item_code}
    )
    
    await callback.message.edit_text(
        f"✅ <b>Растение удалено!</b>\n\n"
        f"Код: <code>{item_code}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_plants_trash")],
        ]),
        parse_mode="HTML"
    )

# ==================== СТАТИСТИКА ПОСАДОК ====================

@router.callback_query(F.data == "admin_plants_stats")
async def admin_plants_stats(callback: CallbackQuery):
    """Статистика посадок по растениям"""
    db = await get_db()
    
    # Общая статистика
    total_planted = await db.fetchone("SELECT SUM(total_planted) FROM users WHERE total_planted > 0")
    total_harvested = await db.fetchone("SELECT SUM(total_harvested) FROM users WHERE total_harvested > 0")
    total_earned = await db.fetchone("SELECT SUM(total_earned) FROM users WHERE total_earned > 0")
    
    # Получаем все растения
    plants = await db.fetchall(
        """SELECT item_code, item_name, item_icon, buy_price, sell_price, growth_time
           FROM shop_config WHERE category = 'seed' AND is_active = 1
           ORDER BY sort_order"""
    )
    
    text_lines = [
        f"📊 <b>Статистика посадок</b>\n\n"
        f"<b>Общая:</b>\n"
        f"🌱 Всего посадок: {total_planted[0] if total_planted else 0:,}\n"
        f"🌾 Всего собрано: {total_harvested[0] if total_harvested else 0:,}\n"
        f"💰 Всего заработано: {total_earned[0] if total_earned else 0:,}🪙\n\n"
        f"<b>По растениям:</b>\n"
    ]
    
    keyboard_rows = []
    
    for plant in plants:
        item_code, item_name, item_icon, buy_price, sell_price, growth_time = plant
        grow_min = growth_time // 60 if growth_time else 0
        profit = (sell_price or 0) - (buy_price or 0)
        
        # Приблизительная статистика (равномерное распределение)
        # В реальном проекте нужна отдельная таблица для детальной статистики
        total = total_planted[0] if total_planted else 0
        plant_count = len(plants)
        estimated_planted = total // plant_count if plant_count > 0 else 0
        estimated_harvested = estimated_planted  # Предполагаем что все собраны
        estimated_earned = estimated_harvested * profit
        
        text_lines.append(
            f"{item_icon} <b>{item_name}</b>\n"
            f"   📊 Посажено: ~{estimated_planted:,}\n"
            f"   🌾 Собрано: ~{estimated_harvested:,}\n"
            f"   💰 Заработано: ~{estimated_earned:,}🪙\n"
        )
        
        keyboard_rows.append([
            InlineKeyboardButton(text="📊 Детально", callback_data=f"plant_stat_{item_code}"),
        ])
    
    keyboard_rows.append([
        InlineKeyboardButton(text="🏆 Топ фермеров", callback_data="admin_top_farmers"),
        get_nav_buttons("admin_plants"),
    ])
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        parse_mode="HTML"
    )

# Топ фермеров
@router.callback_query(F.data == "admin_top_farmers")
async def admin_top_farmers(callback: CallbackQuery):
    """Топ фермеров по посадкам"""
    db = await get_db()
    
    rows = await db.fetchall(
        """SELECT user_id, first_name, username, total_planted, total_harvested, total_earned
           FROM users WHERE is_banned = 0 AND total_planted > 0
           ORDER BY total_planted DESC LIMIT 10"""
    )
    
    if not rows:
        await callback.answer("Нет данных!")
        return
    
    text_lines = ["🏆 <b>Топ-10 фермеров</b>\n"]
    keyboard_rows = []
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, row in enumerate(rows):
        user_id, name, username, planted, harvested, earned = row
        text_lines.append(
            f"{medals[i]} {name} (@{username or 'нет'})\n"
            f"   🌱 Посажено: {planted:,}\n"
            f"   🌾 Собрано: {harvested:,}\n"
            f"   💰 Заработано: {earned:,}🪙\n"
        )
        
        keyboard_rows.append([InlineKeyboardButton(
            text=f"👤 {name[:15]}",
            callback_data=f"admin_profile_{user_id}"
        )])
    
    keyboard_rows.append(get_nav_buttons("admin_plants_stats"))
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        parse_mode="HTML"
    )

# ==================== ЗАГЛУШКИ ДЛЯ НЕРЕАЛИЗОВАННЫХ РАЗДЕЛОВ ====================

@router.callback_query(F.data.in_([
    "admin_economy", "admin_daily", "admin_settings",
    "logs_analytics", "admin_broadcast_audience", "noop"
]))
async def admin_not_implemented(callback: CallbackQuery):
    """Заглушка для нереализованных разделов"""
    await callback.answer("🚧 Этот раздел в разработке", show_alert=True)

# Топ по балансу
@router.callback_query(F.data == "admin_top_balance")
async def admin_top_balance(callback: CallbackQuery):
    """Топ игроков по балансу"""
    db = await get_db()
    
    rows = await db.fetchall(
        """SELECT user_id, first_name, username, balance, prestige_level 
           FROM users WHERE is_banned = 0 
           ORDER BY balance DESC LIMIT 10"""
    )
    
    if not rows:
        await callback.answer("Нет игроков!")
        return
    
    text_lines = ["💰 <b>Топ-10 по балансу</b>\n"]
    keyboard_rows = []
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, row in enumerate(rows):
        user_id, name, username, balance, prestige = row
        text_lines.append(f"{medals[i]} {name}: {balance:,}🪙 (Престиж {prestige})")
        
        keyboard_rows.append([InlineKeyboardButton(
            text=f"👤 Профиль: {name[:15]}",
            callback_data=f"admin_profile_{user_id}"
        )])
    
    keyboard_rows.append(get_nav_buttons("admin_players"))
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        parse_mode="HTML"
    )

# Топ по уровню
@router.callback_query(F.data == "admin_top_level")
async def admin_top_level(callback: CallbackQuery):
    """Топ игроков по уровню престижа"""
    db = await get_db()
    
    rows = await db.fetchall(
        """SELECT user_id, first_name, username, prestige_level, total_harvested 
           FROM users WHERE is_banned = 0 
           ORDER BY prestige_level DESC, total_harvested DESC LIMIT 10"""
    )
    
    if not rows:
        await callback.answer("Нет игроков!")
        return
    
    text_lines = ["🏆 <b>Топ-10 по уровню престижа</b>\n"]
    keyboard_rows = []
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, row in enumerate(rows):
        user_id, name, username, prestige, harvested = row
        text_lines.append(f"{medals[i]} {name}: Престиж {prestige} ({harvested}🌾)")
        
        keyboard_rows.append([InlineKeyboardButton(
            text=f"👤 Профиль: {name[:15]}",
            callback_data=f"admin_profile_{user_id}"
        )])
    
    keyboard_rows.append(get_nav_buttons("admin_players"))
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        parse_mode="HTML"
    )

# Онлайн статистика
@router.callback_query(F.data == "admin_online_stats")
async def admin_online_stats(callback: CallbackQuery):
    """Статистика онлайна"""
    db = await get_db()
    
    # Всего игроков
    total = await db.fetchone("SELECT COUNT(*) FROM users WHERE is_banned = 0")
    
    # Активные сегодня
    today_active = await db.fetchone(
        "SELECT COUNT(*) FROM users WHERE last_activity >= date('now') AND is_banned = 0"
    )
    
    # Активные за неделю
    week_active = await db.fetchone(
        "SELECT COUNT(*) FROM users WHERE last_activity >= date('now', '-7 days') AND is_banned = 0"
    )
    
    # Новые за сегодня
    new_today = await db.fetchone(
        "SELECT COUNT(*) FROM users WHERE joined_date >= date('now') AND is_banned = 0"
    )
    
    # Новые за неделю
    new_week = await db.fetchone(
        "SELECT COUNT(*) FROM users WHERE joined_date >= date('now', '-7 days') AND is_banned = 0"
    )
    
    # Забаненные
    banned = await db.fetchone("SELECT COUNT(*) FROM users WHERE is_banned = 1")
    
    text = f"""📊 <b>Онлайн статистика</b>

<b>👥 Игроки:</b>
• Всего: {total[0]:,}
• Активны сегодня: {today_active[0]:,}
• Активны за неделю: {week_active[0]:,}

<b>🆕 Новые:</b>
• Сегодня: {new_today[0]:,}
• За неделю: {new_week[0]:,}

<b>🛡️ Модерация:</b>
• Забанено: {banned[0]:,}

<b>💰 Экономика:</b>"""
    
    # Общий баланс
    total_balance = await db.fetchone("SELECT COALESCE(SUM(balance), 0) FROM users WHERE is_banned = 0")
    text += f"\n• Всего монет: {total_balance[0]:,}🪙"
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_online_stats")],
            get_nav_buttons("admin_players"),
        ]),
        parse_mode="HTML"
    )

# Показ профиля игрока
async def show_user_profile(target, user_id: int):
    """Показывает полный профиль игрока"""
    db = await get_db()
    user = await db.get_user(user_id)
    
    if not user:
        if isinstance(target, CallbackQuery):
            await target.answer("❌ Игрок не найден!", show_alert=True)
        else:
            await target.answer("❌ Игрок не найден!")
        return
    
    # Получаем дополнительную информацию
    inventory = await db.get_inventory(user_id)
    
    # Получаем дату регистрации и последнюю активность
    user_info = await db.fetchone(
        "SELECT joined_date, last_activity, is_banned, ban_reason, ban_until, gems, xp, level FROM users WHERE user_id = ?",
        (user_id,)
    )
    
    if not user_info:
        if isinstance(target, CallbackQuery):
            await target.answer("❌ Ошибка загрузки данных!", show_alert=True)
        else:
            await target.answer("❌ Ошибка загрузки данных!")
        return
    
    joined_date = user_info[0] or "Неизвестно"
    last_activity = user_info[1] or "Неизвестно"
    is_banned = user_info[2] or False
    ban_reason = user_info[3] or None
    ban_until = user_info[4] or None
    gems = user_info[5] or 0
    xp = user_info[6] or 0
    level = user_info[7] or 1

    # Форматируем даты с обработкой ошибок
    if last_activity and last_activity != "Неизвестно":
        try:
            last_dt = datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
            delta = datetime.now() - last_dt.replace(tzinfo=None)
            # Проверяем что delta не отрицательное
            if delta.total_seconds() < 0:
                last_text = "Только что"
            elif delta.days > 0:
                last_text = f"{delta.days} дн. назад"
            elif delta.seconds // 3600 > 0:
                last_text = f"{delta.seconds // 3600} ч. назад"
            else:
                last_text = f"{delta.seconds // 60} мин. назад"
        except (ValueError, AttributeError, TypeError):
            last_text = str(last_activity)[:16] if last_activity else "Неизвестно"
    else:
        last_text = "Неизвестно"

    # Статус бана
    if is_banned:
        ban_status = "🔴 Забанен"
        if ban_until:
            ban_status += f"\n⏰ До: {ban_until}"
        if ban_reason:
            ban_status += f"\n📝 Причина: {ban_reason}"
    else:
        ban_status = "🟢 Активен"

    # Инвентарь (первые 5)
    inv_text = ""
    for i, (item, qty) in enumerate(list(inventory.items())[:5]):
        inv_text += f"• {item}: {qty} шт\n"

    text = f"""👤 <b>Профиль игрока</b>

🆔 ID: <code>{user_id}</code>
👤 Имя: {user['first_name']}
📱 Username: @{user['username'] or 'нет'}
📅 Регистрация: {joined_date or 'Неизвестно'}
🕐 Последний вход: {last_text}

💰 <b>Ресурсы:</b>
🪙 Монеты: {user['balance']:,}
💎 Кристаллы: {gems:,}
🏆 Престиж: {user['prestige_level']} (x{user['prestige_multiplier']:.1f})
⭐ Опыт: {xp:,} (Ур. {level})

🌾 <b>Инвентарь:</b>
{inv_text or 'Пусто'}

📊 <b>Статистика:</b>
🌾 Собрано урожая: {user['total_harvested']}
🌱 Посажено: {user['total_planted']}
🏙️ Уровень города: {user['city_level']}
💵 Всего заработано: {user.get('total_earned', 0):,}🪙

{ban_status}"""
    
    # Кнопки управления
    keyboard_rows = [
        [InlineKeyboardButton(text="💰 Выдать монеты", callback_data=f"admin_give_coins_{user_id}"),
         InlineKeyboardButton(text="💎 Выдать кристаллы", callback_data=f"admin_give_gems_{user_id}")],
        [InlineKeyboardButton(text="🌱 Выдать предмет", callback_data=f"admin_give_item_{user_id}"),
         InlineKeyboardButton(text="🔨 Забрать ресурсы", callback_data=f"admin_take_{user_id}")],
    ]
    
    # Бан/разбан
    if is_banned:
        keyboard_rows.append([InlineKeyboardButton(text="✅ Разбанить", callback_data=f"admin_unban_{user_id}")])
    else:
        keyboard_rows.append([InlineKeyboardButton(text="⛔️ Забанить", callback_data=f"admin_ban_{user_id}")])
    
    keyboard_rows.extend([
        [InlineKeyboardButton(text="📜 История действий", callback_data=f"admin_history_{user_id}"),
         InlineKeyboardButton(text="🏅 Ачивки игрока", callback_data=f"admin_user_ach_{user_id}")],
        [InlineKeyboardButton(text="💬 Отправить сообщение", callback_data=f"admin_msg_{user_id}")],
        get_nav_buttons("admin_players"),
    ])
    
    # Дополнительные кнопки для Creator
    role = await check_admin_access(target.from_user.id if isinstance(target, CallbackQuery) else target.from_user.id)
    if role == 'creator':
        keyboard_rows.insert(-1, [
            InlineKeyboardButton(text="⚠️ СБРОСИТЬ ПРОГРЕСС", callback_data=f"admin_reset_{user_id}"),
            InlineKeyboardButton(text="🗑 Удалить аккаунт", callback_data=f"admin_delete_{user_id}")
        ])
    
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows), parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows), parse_mode="HTML")

@router.callback_query(F.data.startswith("admin_profile_"))
async def admin_show_profile(callback: CallbackQuery):
    """Показ профиля по callback"""
    user_id = int(callback.data.split("_")[2])
    await show_user_profile(callback, user_id)

# ==================== ВЫДАЧА МОНЕТ ====================

@router.callback_query(F.data.startswith("admin_give_coins_"))
async def admin_give_coins_start(callback: CallbackQuery, state: FSMContext):
    """Начало выдачи монет"""
    user_id = int(callback.data.split("_")[3])
    await state.update_data(target_user_id=user_id)
    await state.set_state(AdminFSM.give_coins_amount)
    
    db = await get_db()
    user = await db.get_user(user_id)
    
    await callback.message.edit_text(
        f"💰 <b>Выдача монет</b>\n\n"
        f"Игрок: <b>{user['first_name']}</b>\n"
        f"Текущий баланс: {user['balance']:,}🪙\n\n"
        f"Введи количество монет:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin_profile_{user_id}")]
        ]),
        parse_mode="HTML"
    )

@router.message(AdminFSM.give_coins_amount)
async def admin_give_coins_amount(message: Message, state: FSMContext):
    """Количество монет"""
    try:
        amount = int(message.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи положительное число!")
        return
    
    await state.update_data(amount=amount)
    await state.set_state(AdminFSM.give_coins_reason)
    
    await message.answer(
        "📝 <b>Причина выдачи</b>\n\n"
        "Введи причину:\n"
        "<i>Например: Бонус за активность</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_players")]
        ]),
        parse_mode="HTML"
    )

@router.message(AdminFSM.give_coins_reason)
async def admin_give_coins_confirm(message: Message, state: FSMContext):
    """Подтверждение и выдача монет"""
    data = await state.get_data()
    target_id = data['target_user_id']
    amount = data['amount']
    reason = message.text.strip()
    
    db = await get_db()
    target = await db.get_user(target_id)
    
    if not target:
        await message.answer("❌ Игрок не найден!")
        await state.clear()
        return
    
    # Выдаем монеты
    await db.update_balance(target_id, amount)
    
    # Логируем
    await log_admin_action(
        message.from_user.id, 
        "give_coins", 
        target_id,
        {"amount": amount, "reason": reason}
    )
    
    await message.answer(
        f"✅ <b>Монеты выданы!</b>\n\n"
        f"👤 Игрок: {target['first_name']}\n"
        f"💰 Сумма: {amount:,}🪙\n"
        f"📝 Причина: {reason}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 К профилю", callback_data=f"admin_profile_{target_id}")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="admin_back_main")],
        ]),
        parse_mode="HTML"
    )
    
    await state.clear()

# ==================== ВЫДАЧА КРИСТАЛЛОВ ====================

@router.callback_query(F.data.startswith("admin_give_gems_"))
async def admin_give_gems_start(callback: CallbackQuery, state: FSMContext):
    """Начало выдачи кристаллов"""
    user_id = int(callback.data.split("_")[3])
    await state.update_data(target_user_id=user_id)
    await state.set_state(AdminFSM.give_gems_amount)
    
    db = await get_db()
    user = await db.get_user(user_id)
    
    await callback.message.edit_text(
        f"💎 <b>Выдача кристаллов</b>\n\n"
        f"Игрок: <b>{user['first_name']}</b>\n\n"
        f"Введи количество кристаллов:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin_profile_{user_id}")]
        ]),
        parse_mode="HTML"
    )

@router.message(AdminFSM.give_gems_amount)
async def admin_give_gems_amount(message: Message, state: FSMContext):
    """Количество кристаллов"""
    try:
        amount = int(message.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи положительное число!")
        return
    
    await state.update_data(amount=amount)
    await state.set_state(AdminFSM.give_gems_reason)
    
    await message.answer(
        "📝 <b>Причина выдачи</b>\n\n"
        "Введи причину:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_players")]
        ]),
        parse_mode="HTML"
    )

@router.message(AdminFSM.give_gems_reason)
async def admin_give_gems_confirm(message: Message, state: FSMContext):
    """Подтверждение и выдача кристаллов"""
    data = await state.get_data()
    target_id = data['target_user_id']
    amount = data['amount']
    reason = message.text.strip()
    
    db = await get_db()
    target = await db.get_user(target_id)
    
    if not target:
        await message.answer("❌ Игрок не найден!")
        await state.clear()
        return
    
    # Выдаем кристаллы
    await db.execute(
        "UPDATE users SET gems = COALESCE(gems, 0) + ? WHERE user_id = ?",
        (amount, target_id), commit=True
    )
    
    # Логируем
    await log_admin_action(
        message.from_user.id, 
        "give_gems", 
        target_id,
        {"amount": amount, "reason": reason}
    )
    
    await message.answer(
        f"✅ <b>Кристаллы выданы!</b>\n\n"
        f"👤 Игрок: {target['first_name']}\n"
        f"💎 Сумма: {amount:,}💎\n"
        f"📝 Причина: {reason}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 К профилю", callback_data=f"admin_profile_{target_id}")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="admin_back_main")],
        ]),
        parse_mode="HTML"
    )
    
    await state.clear()

# ==================== ВЫДАЧА ПРЕДМЕТОВ ====================

@router.callback_query(F.data.startswith("admin_give_item_"))
async def admin_give_item_start(callback: CallbackQuery, state: FSMContext):
    """Начало выдачи предмета"""
    user_id = int(callback.data.split("_")[3])
    await state.update_data(target_user_id=user_id)
    await state.set_state(AdminFSM.give_item_select)
    
    db = await get_db()
    items = await db.get_shop_items()
    
    keyboard_rows = []
    for item in items[:10]:  # Первые 10 предметов
        keyboard_rows.append([InlineKeyboardButton(
            text=f"{item['icon']} {item['name']}",
            callback_data=f"giveitem_{item['item_code']}"
        )])
    
    keyboard_rows.append(get_nav_buttons(f"admin_profile_{user_id}"))
    
    await callback.message.edit_text(
        "🌱 <b>Выдача предмета</b>\n\n"
        "Выбери предмет:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("giveitem_"))
async def admin_give_item_selected(callback: CallbackQuery, state: FSMContext):
    """Выбран предмет"""
    item_code = callback.data.replace("giveitem_", "")
    await state.update_data(item_code=item_code)
    await state.set_state(AdminFSM.give_item_quantity)
    
    await callback.message.edit_text(
        "🌱 <b>Количество</b>\n\n"
        "Введи количество:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_players")]
        ]),
        parse_mode="HTML"
    )

@router.message(AdminFSM.give_item_quantity)
async def admin_give_item_quantity(message: Message, state: FSMContext):
    """Количество предмета"""
    try:
        quantity = int(message.text.strip())
        if quantity <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи положительное число!")
        return
    
    await state.update_data(quantity=quantity)
    await state.set_state(AdminFSM.give_item_reason)
    
    await message.answer(
        "📝 <b>Причина выдачи</b>\n\n"
        "Введи причину:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_players")]
        ]),
        parse_mode="HTML"
    )

@router.message(AdminFSM.give_item_reason)
async def admin_give_item_confirm(message: Message, state: FSMContext):
    """Подтверждение и выдача предмета"""
    data = await state.get_data()
    target_id = data['target_user_id']
    item_code = data['item_code']
    quantity = data['quantity']
    reason = message.text.strip()
    
    db = await get_db()
    target = await db.get_user(target_id)
    
    if not target:
        await message.answer("❌ Игрок не найден!")
        await state.clear()
        return
    
    # Выдаем предмет
    await db.add_inventory(target_id, item_code, quantity)
    
    # Логируем
    await log_admin_action(
        message.from_user.id, 
        "give_item", 
        target_id,
        {"item": item_code, "quantity": quantity, "reason": reason}
    )
    
    await message.answer(
        f"✅ <b>Предмет выдан!</b>\n\n"
        f"👤 Игрок: {target['first_name']}\n"
        f"🌱 Предмет: {item_code} x{quantity}\n"
        f"📝 Причина: {reason}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 К профилю", callback_data=f"admin_profile_{target_id}")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="admin_back_main")],
        ]),
        parse_mode="HTML"
    )
    
    await state.clear()

# ==================== БАН СИСТЕМА ====================

@router.callback_query(F.data.startswith("admin_ban_"))
async def admin_ban_start(callback: CallbackQuery, state: FSMContext):
    """Начало бана"""
    user_id = int(callback.data.split("_")[2])
    
    role = await check_admin_access(callback.from_user.id)
    
    # Проверяем не админ ли цель
    db = await get_db()
    target_role = await db.get_admin_role(user_id)
    if target_role:
        await callback.answer("❌ Нельзя забанить администратора!", show_alert=True)
        return
    
    await state.update_data(target_user_id=user_id, admin_role=role)
    await state.set_state(AdminFSM.ban_reason)
    
    max_duration = "24 часов" if role == 'moderator' else "неограничено"
    
    await callback.message.edit_text(
        f"⛔️ <b>Бан игрока</b>\n\n"
        f"Твоя роль позволяет банить на: <b>{max_duration}</b>\n\n"
        f"Введи причину бана:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin_profile_{user_id}")]
        ]),
        parse_mode="HTML"
    )

@router.message(AdminFSM.ban_reason)
async def admin_ban_reason(message: Message, state: FSMContext):
    """Причина бана"""
    reason = message.text.strip()
    await state.update_data(reason=reason)
    
    data = await state.get_data()
    role = data['admin_role']
    
    if role == 'moderator':
        await state.set_state(AdminFSM.ban_duration)
        await message.answer(
            "⏰ <b>Длительность бана</b>\n\n"
            "Введи количество часов (1-24):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_players")]
            ]),
            parse_mode="HTML"
        )
    else:
        # Админы и Creator могут выбрать пермабан или время
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="♾️ Навсегда", callback_data="ban_permanent")],
            [InlineKeyboardButton(text="⏰ Указать время", callback_data="ban_temporary")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_players")],
        ])
        await message.answer(
            "⛔️ <b>Тип бана</b>\n\n"
            "Выбери тип бана:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

@router.callback_query(F.data.in_(["ban_permanent", "ban_temporary"]))
async def admin_ban_type(callback: CallbackQuery, state: FSMContext):
    """Выбор типа бана"""
    if callback.data == "ban_permanent":
        await execute_ban(callback, state, hours=None)
    else:
        await state.set_state(AdminFSM.ban_duration)
        await callback.message.edit_text(
            "⏰ <b>Длительность бана</b>\n\n"
            "Введи количество часов:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_players")]
            ]),
            parse_mode="HTML"
        )

@router.message(AdminFSM.ban_duration)
async def admin_ban_duration(message: Message, state: FSMContext):
    """Длительность бана"""
    try:
        hours = int(message.text.strip())
        data = await state.get_data()
        
        # Проверяем ограничение для модераторов
        if data['admin_role'] == 'moderator' and hours > 24:
            await message.answer("❌ Модераторы могут банить максимум на 24 часа!")
            return
        
        if hours <= 0:
            raise ValueError
            
    except ValueError:
        await message.answer("❌ Введи положительное число часов!")
        return
    
    await execute_ban(message, state, hours)

async def execute_ban(target, state: FSMContext, hours: int = None):
    """Выполняет бан"""
    data = await state.get_data()
    target_id = data['target_user_id']
    reason = data['reason']
    
    db = await get_db()
    
    # Рассчитываем дату окончания
    ban_until = None
    if hours:
        ban_until = (datetime.now() + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    
    # Баним
    await db.execute(
        "UPDATE users SET is_banned = 1, ban_reason = ?, ban_until = ? WHERE user_id = ?",
        (reason, ban_until, target_id), commit=True
    )
    
    # Логируем
    await log_admin_action(
        target.from_user.id if isinstance(target, CallbackQuery) else target.from_user.id,
        "ban_user",
        target_id,
        {"reason": reason, "hours": hours, "ban_until": ban_until}
    )
    
    duration_text = f"на {hours} часов" if hours else "навсегда"
    
    text = (
        f"🔨 <b>Игрок забанен</b>\n\n"
        f"Длительность: {duration_text}\n"
        f"Причина: {reason}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 К профилю", callback_data=f"admin_profile_{target_id}")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="admin_back_main")],
    ])
    
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=keyboard, parse_mode="HTML")
    
    await state.clear()

# Разбан
@router.callback_query(F.data.startswith("admin_unban_"))
async def admin_unban(callback: CallbackQuery):
    """Разбан игрока"""
    user_id = int(callback.data.split("_")[2])
    
    db = await get_db()
    await db.execute(
        "UPDATE users SET is_banned = 0, ban_reason = NULL, ban_until = NULL WHERE user_id = ?",
        (user_id,), commit=True
    )
    
    # Логируем
    await log_admin_action(callback.from_user.id, "unban_user", user_id)
    
    await callback.answer("✅ Игрок разбанен!")
    await show_user_profile(callback, user_id)

# ==================== ПОМОЩЬ ====================

@router.callback_query(F.data == "admin_help")
async def admin_help(callback: CallbackQuery):
    """Помощь по админ-панели"""
    role = await check_admin_access(callback.from_user.id)
    
    help_text = f"""❓ <b>Помощь по админ-панели</b>

Твоя роль: <b>{get_role_emoji(role)} {role.upper()}</b>

<b>👥 Игроки</b> - поиск, просмотр профилей, выдача ресурсов, баны
<b>🌱 Растения</b> - добавление и редактирование растений"""
    
    if role in ('admin', 'creator'):
        help_text += """
<b>🎁 Промо-акции</b> - создание промокодов
<b>⭐️ Ежедневный бонус</b> - настройка бонусов
<b>🏆 Ачивки</b> - управление достижениями
<b>💰 Экономика</b> - настройка цен и баланса"""
    
    help_text += """
<b>📢 Рассылка</b> - массовая отправка сообщений"""
    
    if role == 'creator':
        help_text += """
<b>👑 Управление админами</b> - назначение ролей
<b>📊 Логи</b> - история действий админов
<b>⚙️ Настройки</b> - системные параметры"""
    
    help_text += """

<b>⚠️ Важно:</b>
• Все действия логируются
• Модераторы могут банить только на 24ч
• Админы не могут банить друг друга
• Creator имеет полный доступ"""
    
    await callback.message.edit_text(
        help_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            get_nav_buttons(show_home=True)
        ]),
        parse_mode="HTML"
    )

# ==================== РАЗДЕЛ «РАСТЕНИЯ» ====================

@router.callback_query(F.data == "admin_plants")
async def admin_plants_menu(callback: CallbackQuery, state: FSMContext):
    """Меню управления растениями"""
    await state.clear()
    
    role = await check_admin_access(callback.from_user.id)
    if role not in ('admin', 'creator'):
        await callback.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    db = await get_db()
    plants_count = await db.fetchone("SELECT COUNT(*) FROM shop_config WHERE category = 'seed'")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить растение", callback_data="admin_add_plant")],
        [InlineKeyboardButton(text="📋 Список растений", callback_data="admin_list_plants_0")],
        [InlineKeyboardButton(text="🗑 Корзина (удаленные)", callback_data="admin_plants_trash")],
        [InlineKeyboardButton(text="📊 Статистика посадок", callback_data="admin_plants_stats")],
        get_nav_buttons(),
    ])
    
    await callback.message.edit_text(
        f"🌱 <b>Управление растениями</b>\n\n"
        f"Всего растений: {plants_count[0]}\n\n"
        f"Выбери действие:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# Добавление растения - пошаговый мастер
@router.callback_query(F.data == "admin_add_plant")
async def admin_add_plant_start(callback: CallbackQuery, state: FSMContext):
    """Шаг 1: ID растения"""
    await state.set_state(AdminFSM.plant_id)
    
    await callback.message.edit_text(
        "🌱 <b>Добавление растения - Шаг 1/10</b>\n\n"
        "🆔 <b>ID растения:</b>\n"
        "Уникальный код, латиница\n"
        "<i>Например: potato</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_plants")]
        ]),
        parse_mode="HTML"
    )

@router.message(AdminFSM.plant_id)
async def admin_plant_id(message: Message, state: FSMContext):
    """Шаг 2: Название"""
    plant_id = message.text.strip().lower()
    if not plant_id.replace("_", "").isalnum():
        await message.answer("❌ ID должен содержать только латинские буквы, цифры и _")
        return
    
    # Проверяем уникальность
    db = await get_db()
    exists = await db.fetchone(
        "SELECT 1 FROM shop_config WHERE item_code = ?", (plant_id,)
    )
    if exists:
        await message.answer("❌ Такой ID уже существует!")
        return
    
    await state.update_data(plant_id=plant_id)
    await state.set_state(AdminFSM.plant_name)
    
    await message.answer(
        "🌱 <b>Шаг 2/10</b> - Название\n\n"
        "Введи название растения:\n"
        "<i>Например: Картошка</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_plants")]
        ]),
        parse_mode="HTML"
    )

@router.message(AdminFSM.plant_name)
async def admin_plant_name(message: Message, state: FSMContext):
    """Шаг 3: Эмодзи"""
    await state.update_data(name=message.text.strip())
    await state.set_state(AdminFSM.plant_emoji)
    
    await message.answer(
        "🌱 <b>Шаг 3/10</b> - Эмодзи\n\n"
        "Введи эмодзи для растения:\n"
        "<i>Например: 🥔</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_plants")]
        ]),
        parse_mode="HTML"
    )

@router.message(AdminFSM.plant_emoji)
async def admin_plant_emoji(message: Message, state: FSMContext):
    """Шаг 4: Время роста"""
    await state.update_data(emoji=message.text.strip()[:2])
    await state.set_state(AdminFSM.plant_grow_time)
    
    await message.answer(
        "🌱 <b>Шаг 4/10</b> - Время роста\n\n"
        "Введи время роста в минутах:\n"
        "<i>Например: 5</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_plants")]
        ]),
        parse_mode="HTML"
    )

@router.message(AdminFSM.plant_grow_time)
async def admin_plant_grow_time(message: Message, state: FSMContext):
    """Шаг 5: Цена семян"""
    try:
        grow_time = int(message.text.strip())
        if grow_time <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи положительное число минут!")
        return
    
    await state.update_data(grow_time=grow_time)
    await state.set_state(AdminFSM.plant_seed_price)
    
    await message.answer(
        "🌱 <b>Шаг 5/10</b> - Цена семян\n\n"
        "Введи цену семян в монетах:\n"
        "<i>Например: 100</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_plants")]
        ]),
        parse_mode="HTML"
    )

@router.message(AdminFSM.plant_seed_price)
async def admin_plant_seed_price(message: Message, state: FSMContext):
    """Шаг 6: Цена продажи"""
    try:
        seed_price = int(message.text.strip())
        if seed_price < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи неотрицательное число!")
        return
    
    await state.update_data(seed_price=seed_price)
    await state.set_state(AdminFSM.plant_sell_price)
    
    await message.answer(
        "🌱 <b>Шаг 6/10</b> - Цена продажи\n\n"
        "Введи цену продажи урожая в монетах:\n"
        "<i>Например: 250</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_plants")]
        ]),
        parse_mode="HTML"
    )

@router.message(AdminFSM.plant_sell_price)
async def admin_plant_sell_price(message: Message, state: FSMContext):
    """Шаг 7: Урожайность"""
    try:
        sell_price = int(message.text.strip())
        if sell_price < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи неотрицательное число!")
        return
    
    await state.update_data(sell_price=sell_price)
    await state.set_state(AdminFSM.plant_yield)
    
    await message.answer(
        "🌱 <b>Шаг 7/10</b> - Урожайность\n\n"
        "Введи количество урожая с грядки:\n"
        "<i>Например: 3</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_plants")]
        ]),
        parse_mode="HTML"
    )

@router.message(AdminFSM.plant_yield)
async def admin_plant_yield(message: Message, state: FSMContext):
    """Шаг 8: Требуемый уровень"""
    try:
        yield_amount = int(message.text.strip())
        if yield_amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи положительное число!")
        return
    
    await state.update_data(yield_amount=yield_amount)
    await state.set_state(AdminFSM.plant_level)
    
    await message.answer(
        "🌱 <b>Шаг 8/10</b> - Требуемый уровень\n\n"
        "Введи требуемый уровень игрока:\n"
        "<i>Например: 1</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_plants")]
        ]),
        parse_mode="HTML"
    )

@router.message(AdminFSM.plant_level)
async def admin_plant_level(message: Message, state: FSMContext):
    """Шаг 9: Опыт"""
    try:
        required_level = int(message.text.strip())
        if required_level < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи неотрицательное число!")
        return
    
    await state.update_data(required_level=required_level)
    await state.set_state(AdminFSM.plant_exp)
    
    await message.answer(
        "🌱 <b>Шаг 9/10</b> - Опыт\n\n"
        "Введи опыт за сбор урожая:\n"
        "<i>Например: 10</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_plants")]
        ]),
        parse_mode="HTML"
    )

@router.message(AdminFSM.plant_exp)
async def admin_plant_exp(message: Message, state: FSMContext):
    """Шаг 10: Подтверждение"""
    try:
        exp_reward = int(message.text.strip())
        if exp_reward < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи неотрицательное число!")
        return
    
    await state.update_data(exp_reward=exp_reward)
    
    # Получаем все данные и показываем сводку
    data = await state.get_data()
    await state.set_state(AdminFSM.plant_confirm)
    
    summary = f"""🌱 <b>Шаг 10/10 - Подтверждение</b>

<b>Сводка:</b>
🆔 ID: {data['plant_id']}
🏷️ Название: {data['name']}
{data['emoji']} Эмодзи: {data['emoji']}
⏱️ Время роста: {data['grow_time']} мин
💰 Цена семян: {data['seed_price']}🪙
💵 Цена продажи: {data['sell_price']}🪙
🌾 Урожай: {data['yield_amount']} шт
⭐ Требуемый уровень: {data['required_level']}
✨ Опыт: {data['exp_reward']}"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Сохранить", callback_data="admin_save_plant")],
        [InlineKeyboardButton(text="🔄 Заново", callback_data="admin_add_plant")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_plants")],
    ])
    
    await message.answer(summary, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "admin_save_plant")
async def admin_save_plant(callback: CallbackQuery, state: FSMContext):
    """Сохранение растения"""
    data = await state.get_data()
    db = await get_db()
    
    try:
        # Сохраняем в БД
        await db.execute(
            """INSERT INTO shop_config 
               (item_code, item_name, item_icon, buy_price, sell_price, growth_time, category, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, 'seed', 99)""",
            (data['plant_id'], data['name'], data['emoji'], 
             data['seed_price'], data['sell_price'], data['grow_time'] * 60),
            commit=True
        )
        
        # Логируем
        await log_admin_action(
            callback.from_user.id,
            "create_plant",
            None,
            {"plant_id": data['plant_id'], "name": data['name']}
        )
        
        await callback.message.edit_text(
            f"✅ <b>Растение сохранено!</b>\n\n"
            f"{data['emoji']} {data['name']} добавлено в игру.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 К списку", callback_data="admin_list_plants_0")],
                [InlineKeyboardButton(text="➕ Добавить еще", callback_data="admin_add_plant")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="admin_back_main")],
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ <b>Ошибка сохранения:</b>\n<code>{str(e)}</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Повторить", callback_data="admin_add_plant")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_plants")],
            ]),
            parse_mode="HTML"
        )
    
    await state.clear()

# Список растений с пагинацией
@router.callback_query(F.data.startswith("admin_list_plants_"))
async def admin_list_plants(callback: CallbackQuery, state: FSMContext):
    """Список растений"""
    await state.clear()
    page = int(callback.data.split("_")[3])
    per_page = 5
    
    db = await get_db()
    plants = await db.get_shop_items("seed")
    
    total_pages = max(1, (len(plants) + per_page - 1) // per_page)
    start = page * per_page
    end = min(start + per_page, len(plants))
    page_plants = plants[start:end]
    
    if not page_plants:
        await callback.answer("Нет растений на этой странице!")
        return
    
    text_lines = [f"📋 <b>Список растений (стр. {page + 1}/{total_pages})</b>\n"]
    keyboard_rows = []
    
    for plant in page_plants:
        grow_min = plant['growth_time'] // 60
        text_lines.append(
            f"{plant['icon']} <b>{plant['name']}</b> ({plant['item_code']})\n"
            f"   ⏱️ {grow_min}мин | 💰 {plant['buy_price']}🪙 | 💵 {plant['sell_price']}🪙\n"
        )
        
        keyboard_rows.append([
            InlineKeyboardButton(text=f"✏️ Ред", callback_data=f"plant_edit_{plant['item_code']}"),
            InlineKeyboardButton(text="⏸️ Деакт", callback_data=f"plant_toggle_{plant['item_code']}"),
            InlineKeyboardButton(text="📊 Стат", callback_data=f"plant_stat_{plant['item_code']}"),
        ])
    
    # Кнопки навигации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"admin_list_plants_{page-1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"admin_list_plants_{page+1}"))
    
    if nav_buttons:
        keyboard_rows.append(nav_buttons)
    
    keyboard_rows.append([
        InlineKeyboardButton(text="➕ Добавить", callback_data="admin_add_plant"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_plants")
    ])
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        parse_mode="HTML"
    )
