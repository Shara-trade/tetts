"""
Полноценная админ-панель для Lazy Farmer Bot
Все управление через инлайн-кнопки, единая команда /admin
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import get_database
import asyncio

router = Router()

# FSM состояния для админ-панели
class AdminStates(StatesGroup):
    # Поиск игроков
    waiting_for_user_id = State()
    waiting_for_username = State()
    
    # Выдача ресурсов
    waiting_for_give_coins_amount = State()
    waiting_for_give_coins_reason = State()
    waiting_for_give_gems_amount = State()
    waiting_for_give_gems_reason = State()
    waiting_for_give_item_select = State()
    waiting_for_give_item_quantity = State()
    waiting_for_give_item_reason = State()
    
    # Бан
    waiting_for_ban_reason = State()
    waiting_for_ban_duration = State()
    
    # Растения
    waiting_for_plant_id = State()
    waiting_for_plant_name = State()
    waiting_for_plant_emoji = State()
    waiting_for_plant_grow_time = State()
    waiting_for_plant_seed_price = State()
    waiting_for_plant_sell_price = State()
    waiting_for_plant_yield = State()
    waiting_for_plant_level = State()
    waiting_for_plant_exp = State()
    
    # Промо
    waiting_for_promo_code = State()
    waiting_for_promo_reward_type = State()
    waiting_for_promo_reward_value = State()
    waiting_for_promo_limit = State()
    
    # Рассылка
    waiting_for_broadcast_content = State()
    waiting_for_broadcast_confirm = State()
    
    # Назначение админов
    waiting_for_new_admin_username = State()

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

async def get_db():
    return await get_database()

async def check_admin_access(user_id: int) -> str:
    """Проверяет доступ и возвращает роль"""
    db = await get_db()
    role = await db.get_admin_role(user_id)
    return role

def get_role_emoji(role: str) -> str:
    return {'creator': '👑', 'admin': '⚡', 'moderator': '🛡️'}.get(role, '❓')

# ==================== ГЛАВНОЕ МЕНЮ ====================

@router.message(Command("admin"))
async def admin_main_menu(message: Message, state: FSMContext):
    """Главное меню админ-панели"""
    await state.clear()
    
    role = await check_admin_access(message.from_user.id)
    if not role:
        await message.answer("⛔ У тебя нет доступа к админ-панели!")
        return
    
    # Формируем кнопки в зависимости от роли
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
        buttons.insert(3, [InlineKeyboardButton(text="⭐ Ежедневный бонус", callback_data="admin_daily")])
    
    # Только Creator видит управление админами и логи
    if role == 'creator':
        buttons.append([InlineKeyboardButton(text="👑 Управление админами", callback_data="admin_manage_admins")])
        buttons.append([InlineKeyboardButton(text="📊 Логи действий", callback_data="admin_logs")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await message.answer(
        f"{get_role_emoji(role)} <b>Админ-панель</b>\n\n"
        f"Твоя роль: <b>{role.upper()}</b>\n\n"
        f"Выбери раздел:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# ==================== РАЗДЕЛ «ИГРОКИ» ====================

@router.callback_query(F.data == "admin_players")
async def admin_players_menu(callback: CallbackQuery, state: FSMContext):
    """Меню игроков"""
    await state.clear()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Поиск по ID", callback_data="admin_search_id")],
        [InlineKeyboardButton(text="🔍 Поиск по @username", callback_data="admin_search_username")],
        [InlineKeyboardButton(text="📋 Последние 10 игроков", callback_data="admin_last_players")],
        [InlineKeyboardButton(text="💰 Топ по балансу", callback_data="admin_top_balance")],
        [InlineKeyboardButton(text="🏆 Топ по уровню", callback_data="admin_top_level")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back_main")],
    ])
    
    await callback.message.edit_text(
        "👥 <b>Управление игроками</b>\n\nВыбери действие:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_search_id")
async def admin_search_by_id(callback: CallbackQuery, state: FSMContext):
    """Поиск по ID"""
    await state.set_state(AdminStates.waiting_for_user_id)
    await callback.message.edit_text(
        "🔍 <b>Поиск по ID</b>\n\n"
        "Введи числовой ID пользователя:\n"
        "<i>Например: 123456789</i>",
        parse_mode="HTML"
    )

@router.message(AdminStates.waiting_for_user_id)
async def admin_process_user_id(message: Message, state: FSMContext):
    """Обработка введенного ID"""
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введи числовой ID!")
        return
    
    db = await get_db()
    user = await db.get_user(user_id)
    
    if not user:
        await message.answer("❌ Игрок с таким ID не найден!")
        await state.clear()
        return
    
    await show_user_profile(message, user_id)
    await state.clear()

@router.callback_query(F.data == "admin_search_username")
async def admin_search_by_username(callback: CallbackQuery, state: FSMContext):
    """Поиск по username"""
    await state.set_state(AdminStates.waiting_for_username)
    await callback.message.edit_text(
        "🔍 <b>Поиск по username</b>\n\n"
        "Введи username игрока:\n"
        "<i>Например: @ivanov или ivanov</i>",
        parse_mode="HTML"
    )

@router.message(AdminStates.waiting_for_username)
async def admin_process_username(message: Message, state: FSMContext):
    """Обработка введенного username"""
    username = message.text.strip().replace('@', '')
    
    db = await get_db()
    user = await db.get_user_by_username(username)
    
    if not user:
        await message.answer(f"❌ Игрок @{username} не найден!")
        await state.clear()
        return
    
    await show_user_profile(message, user['user_id'])
    await state.clear()

async def show_user_profile(message_or_callback, user_id: int):
    """Показывает полный профиль игрока"""
    db = await get_db()
    user = await db.get_user(user_id)
    inventory = await db.get_inventory(user_id)
    
    if not user:
        await message_or_callback.answer("❌ Игрок не найден!")
        return
    
    # Формируем список инвентаря (первые 5)
    inv_text = ""
    for i, (item, qty) in enumerate(list(inventory.items())[:5]):
        inv_text += f"• {item}: {qty} шт\n"
    
    ban_status = "🔴 Забанен"
    if user.get('is_banned'):
        ban_status += f"\n📝 Причина: {user.get('ban_reason', 'Не указана')}"
    else:
        ban_status = "🟢 Активен"
    
    text = f"""👤 <b>Профиль игрока</b>

🆔 ID: <code>{user['user_id']}</code>
👤 Имя: {user['first_name']}
📱 Username: @{user['username'] or 'нет'}
📅 Регистрация: {user.get('joined_date', 'Неизвестно')}

💰 <b>Ресурсы:</b>
🪙 Монеты: {user['balance']:,}
🏆 Престиж: {user['prestige_level']} (x{user['prestige_multiplier']:.1f})

🌾 <b>Инвентарь:</b>
{inv_text or 'Пусто'}

📊 <b>Статистика:</b>
🌾 Собрано урожая: {user['total_harvested']}
🏙️ Уровень города: {user['city_level']}

{ban_status}"""
    
    # Кнопки управления
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Выдать монеты", callback_data=f"admin_give_coins_{user_id}")],
        [InlineKeyboardButton(text="🌱 Выдать предмет", callback_data=f"admin_give_item_{user_id}")],
        [InlineKeyboardButton(text="⛔ Забанить" if not user.get('is_banned') else "✅ Разбанить", 
                             callback_data=f"admin_ban_{user_id}" if not user.get('is_banned') else f"admin_unban_{user_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_players")],
    ])
    
    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message_or_callback.answer(text, reply_markup=keyboard, parse_mode="HTML")

# ==================== ВЫДАЧА РЕСУРСОВ ====================

@router.callback_query(F.data.startswith("admin_give_coins_"))
async def admin_give_coins_start(callback: CallbackQuery, state: FSMContext):
    """Начало выдачи монет"""
    user_id = int(callback.data.split("_")[3])
    await state.update_data(target_user_id=user_id)
    await state.set_state(AdminStates.waiting_for_give_coins_amount)
    
    await callback.message.edit_text(
        "💰 <b>Выдача монет</b>\n\n"
        "Введи количество монет:\n"
        "<i>Например: 1000</i>",
        parse_mode="HTML"
    )

@router.message(AdminStates.waiting_for_give_coins_amount)
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
    await state.set_state(AdminStates.waiting_for_give_coins_reason)
    
    await message.answer(
        "📝 <b>Причина выдачи</b>\n\n"
        "Введи причину выдачи монет:\n"
        "<i>Например: Бонус за активность</i>",
        parse_mode="HTML"
    )

@router.message(AdminStates.waiting_for_give_coins_reason)
async def admin_give_coins_confirm(message: Message, state: FSMContext):
    """Подтверждение выдачи монет"""
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
    await db.give_coins(message.from_user.id, target_id, amount, reason)
    
    await message.answer(
        f"✅ <b>Успешно!</b>\n\n"
        f"Выдано {amount:,}🪙 игроку {target['first_name']}\n"
        f"Причина: {reason}",
        parse_mode="HTML"
    )
    
    await state.clear()

# ==================== БАН ====================

@router.callback_query(F.data.startswith("admin_ban_"))
async def admin_ban_start(callback: CallbackQuery, state: FSMContext):
    """Начало бана"""
    user_id = int(callback.data.split("_")[2])
    
    role = await check_admin_access(callback.from_user.id)
    await state.update_data(target_user_id=user_id, admin_role=role)
    await state.set_state(AdminStates.waiting_for_ban_reason)
    
    max_duration = "24 часов" if role == 'moderator' else "неограничено"
    
    await callback.message.edit_text(
        f"⛔ <b>Бан игрока</b>\n\n"
        f"Твоя роль позволяет банить на: <b>{max_duration}</b>\n\n"
        f"Введи причину бана:",
        parse_mode="HTML"
    )

@router.message(AdminStates.waiting_for_ban_reason)
async def admin_ban_reason(message: Message, state: FSMContext):
    """Причина бана"""
    reason = message.text.strip()
    await state.update_data(reason=reason)
    
    data = await state.get_data()
    role = data['admin_role']
    
    if role == 'moderator':
        # Модераторы сразу банят на выбранное время (до 24ч)
        await state.set_state(AdminStates.waiting_for_ban_duration)
        await message.answer(
            "⏰ <b>Длительность бана</b>\n\n"
            "Введи количество часов (1-24):",
            parse_mode="HTML"
        )
    else:
        # Админы и Creator могут выбрать пермабан или время
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="♾️ Навсегда", callback_data="ban_permanent")],
            [InlineKeyboardButton(text="⏰ Указать время", callback_data="ban_temporary")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")],
        ])
        await message.answer(
            "⛔ <b>Тип бана</b>\n\n"
            "Выбери тип бана:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

@router.message(AdminStates.waiting_for_ban_duration)
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

async def execute_ban(message_or_callback, state: FSMContext, hours: int = None):
    """Выполняет бан"""
    data = await state.get_data()
    target_id = data['target_user_id']
    reason = data['reason']
    
    db = await get_db()
    
    # Проверяем не админ ли
    if await db.is_admin(target_id):
        await message_or_callback.answer("❌ Нельзя забанить администратора!")
        await state.clear()
        return
    
    await db.ban_user(message_or_callback.from_user.id, target_id, reason, hours)
    
    duration_text = f"на {hours} часов" if hours else "навсегда"
    await message_or_callback.answer(
        f"🔨 <b>Игрок забанен</b>\n\n"
        f"Длительность: {duration_text}\n"
        f"Причина: {reason}",
        parse_mode="HTML"
    )
    
    await state.clear()

# ==================== НАЗАД ====================

@router.callback_query(F.data == "admin_back_main")
async def admin_back_to_main(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    await admin_main_menu(callback.message, state)

@router.callback_query(F.data == "admin_cancel")
async def admin_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена действия"""
    await state.clear()
    await callback.message.edit_text("❌ Действие отменено")

# ==================== СИСТЕМА ЛОГИРОВАНИЯ ====================

@router.callback_query(F.data == "admin_logs")
async def admin_logs_menu(callback: CallbackQuery):
    """Меню логирования"""
    role = await check_admin_access(callback.from_user.id)
    if role != 'creator':
        await callback.answer("Только для создателя!", show_alert=True)
        return
    
    db = await get_db()
    
    # Получаем статистику
    stats = await db.get_logs_stats(1)  # За сегодня
    week_stats = await db.get_logs_stats(7)  # За неделю
    
    text = f"""📊 <b>Система логирования</b>

📅 Сегодня: {stats.get('total', 0)} событий
📅 За неделю: {week_stats.get('total', 0)} событий

<b>Группы логов:</b>
👑 Админ-действия: {stats.get('groups', {}).get('admin', {}).get('count', 0)}
💰 Экономика: {stats.get('groups', {}).get('economy', {}).get('count', 0)}
🌱 Прогресс: {stats.get('groups', {}).get('gameplay', {}).get('count', 0)}
🛡️ Безопасность: {stats.get('groups', {}).get('security', {}).get('count', 0)}
🏆 Ачивки: {stats.get('groups', {}).get('achievements', {}).get('count', 0)}
🎁 Промо: {stats.get('groups', {}).get('promo', {}).get('count', 0)}"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👑 Админ", callback_data="logs_group_admin"),
         InlineKeyboardButton(text="💰 Экономика", callback_data="logs_group_economy")],
        [InlineKeyboardButton(text="🌱 Прогресс", callback_data="logs_group_gameplay"),
         InlineKeyboardButton(text="🛡️ Безопасность", callback_data="logs_group_security")],
        [InlineKeyboardButton(text="🏆 Ачивки", callback_data="logs_group_achievements"),
         InlineKeyboardButton(text="🎁 Промо", callback_data="logs_group_promo")],
        [InlineKeyboardButton(text="📊 Аналитика", callback_data="logs_analytics"),
         InlineKeyboardButton(text="⚙️ Очистка", callback_data="logs_cleanup")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back_main")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("logs_group_"))
async def admin_logs_filtered(callback: CallbackQuery):
    """Просмотр логов по группам"""
    group = callback.data.replace("logs_group_", "")
    
    db = await get_db()
    logs = await db.get_filtered_logs(log_group=group, limit=10)
    
    if not logs:
        await callback.message.edit_text(f"Логов группы {group} нет")
        return
    
    text_lines = [f"📋 <b>Логи: {group.upper()}</b>\n"]
    
    for log in logs:
        emoji = {'DEBUG': '🐞', 'INFO': 'ℹ️', 'WARNING': '⚠️', 'ERROR': '❌', 'CRITICAL': '🚨'}.get(log['level'], '•')
        
        text_lines.append(
            f"\n{emoji} {log['created_at'][11:19]}\n"
            f"👤 {log.get('username') or log['user_id'] or 'System'}\n"
            f"🔹 {log['action']}\n"
        )
        if log.get('details'):
            details_str = str(log['details'])[:100]
            text_lines.append(f"📝 {details_str}\n")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"logs_group_{group}")],
        [InlineKeyboardButton(text="🔍 Фильтры", callback_data="logs_filters")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_logs")],
    ])
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "logs_analytics")
async def admin_logs_analytics(callback: CallbackQuery):
    """Аналитика логов"""
    db = await get_db()
    
    # Получаем статистику по часам
    hour_stats = await db.get_active_hours_stats()
    
    # Строим простую гистограмму
    chart = "\n<b>Активность по часам:</b>\n"
    for stat in hour_stats:
        hour = stat['hour']
        bars = "█" * min(10, stat['actions'] // 10)
        chart += f"{hour:>2}: {bars} {stat['users']}👤\n"
    
    # Экономика
    economy = await db.get_economy_stats(7)
    top_earners = "\n<b>Топ-5 по заработку (7 дней):</b>\n"
    for i, player in enumerate(economy[:5], 1):
        top_earners += f"{i}. @{player['username']}: +{player['earned']:,}🪙\n"
    
    # Безопасность
    security = await db.get_security_stats(7)
    sec_stats = "\n<b>Безопасность (7 дней):</b>\n"
    for day in security[-3:]:  # Последние 3 дня
        sec_stats += f"{day['date']}: {day['bans']} банов, {day['auto']} авто\n"
    
    text = f"""📊 <b>Аналитика логов</b>

{chart}
{top_earners}
{sec_stats}"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="logs_analytics")],
        [InlineKeyboardButton(text="📥 Экспорт", callback_data="logs_export")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_logs")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "logs_cleanup")
async def admin_logs_cleanup(callback: CallbackQuery):
    """Очистка старых логов"""
    await callback.message.edit_text(
        "⚠️ <b>Очистка логов</b>\n\n"
        "Выберите период очистки:\n\n"
        "⚠️ Внимание: удаленные логи нельзя восстановить!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="30 дней", callback_data="logs_cleanup_30")],
            [InlineKeyboardButton(text="60 дней", callback_data="logs_cleanup_60")],
            [InlineKeyboardButton(text="90 дней", callback_data="logs_cleanup_90")],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_logs")],
        ]),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("logs_cleanup_"))
async def admin_logs_cleanup_confirm(callback: CallbackQuery):
    """Подтверждение очистки"""
    days = int(callback.data.split("_")[2])
    
    db = await get_db()
    await db.cleanup_old_logs(days)
    
    await callback.message.edit_text(
        f"✅ Логи старше {days} дней удалены!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_logs")],
        ])
    )


# ==================== РАЗДЕЛ «РАСТЕНИЯ» ====================

@router.callback_query(F.data == "admin_plants")
async def admin_plants_menu(callback: CallbackQuery):
    """Меню растений"""
    role = await check_admin_access(callback.from_user.id)
    if role not in ('admin', 'creator'):
        await callback.answer("Нет доступа!", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить растение", callback_data="admin_add_plant")],
        [InlineKeyboardButton(text="Список растений", callback_data="admin_list_plants")],
        [InlineKeyboardButton(text="Назад", callback_data="admin_back_main")],
    ])
    
    await callback.message.edit_text(
        "<b>Управление растениями</b>\n\nВыбери действие:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_add_plant")
async def admin_add_plant_start(callback: CallbackQuery, state: FSMContext):
    """Начало добавления растения"""
    await state.set_state(AdminStates.waiting_for_plant_id)
    await callback.message.edit_text(
        "<b>Добавление растения - Шаг 1/10</b>\n\n"
        "Введи уникальный ID растения:\n"
        "<i>Латиница, без пробелов. Например: potato</i>",
        parse_mode="HTML"
    )


@router.message(AdminStates.waiting_for_plant_id)
async def admin_plant_id(message: Message, state: FSMContext):
    """ID растения"""
    plant_id = message.text.strip().lower()
    if not plant_id.isalnum():
        await message.answer("ID должен содержать только латинские буквы и цифры!")
        return
    
    await state.update_data(plant_id=plant_id)
    await state.set_state(AdminStates.waiting_for_plant_name)
    
    await message.answer(
        "<b>Шаг 2/10</b> - Название\n\n"
        "Введи название растения:\n"
        "<i>Например: Картошка</i>",
        parse_mode="HTML"
    )


@router.message(AdminStates.waiting_for_plant_name)
async def admin_plant_name(message: Message, state: FSMContext):
    """Название растения"""
    await state.update_data(name=message.text.strip())
    await state.set_state(AdminStates.waiting_for_plant_emoji)
    
    await message.answer(
        "<b>Шаг 3/10</b> - Эмодзи\n\n"
        "Введи эмодзи для растения:\n"
        "<i>Например: 🥔</i>",
        parse_mode="HTML"
    )


@router.message(AdminStates.waiting_for_plant_emoji)
async def admin_plant_emoji(message: Message, state: FSMContext):
    """Эмодзи растения"""
    await state.update_data(emoji=message.text.strip())
    await state.set_state(AdminStates.waiting_for_plant_grow_time)
    
    await message.answer(
        "<b>Шаг 4/10</b> - Время роста\n\n"
        "Введи время роста в минутах:\n"
        "<i>Например: 5</i>",
        parse_mode="HTML"
    )


@router.message(AdminStates.waiting_for_plant_grow_time)
async def admin_plant_grow_time(message: Message, state: FSMContext):
    """Время роста"""
    try:
        grow_time = int(message.text.strip())
        if grow_time <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введи положительное число минут!")
        return
    
    await state.update_data(grow_time=grow_time)
    await state.set_state(AdminStates.waiting_for_plant_seed_price)
    
    await message.answer(
        "<b>Шаг 5/10</b> - Цена семян\n\n"
        "Введи цену семян в монетах:\n"
        "<i>Например: 100</i>",
        parse_mode="HTML"
    )


@router.message(AdminStates.waiting_for_plant_seed_price)
async def admin_plant_seed_price(message: Message, state: FSMContext):
    """Цена семян"""
    try:
        seed_price = int(message.text.strip())
        if seed_price < 0:
            raise ValueError
    except ValueError:
        await message.answer("Введи неотрицательное число!")
        return
    
    await state.update_data(seed_price=seed_price)
    await state.set_state(AdminStates.waiting_for_plant_sell_price)
    
    await message.answer(
        "<b>Шаг 6/10</b> - Цена продажи\n\n"
        "Введи цену продажи урожая в монетах:\n"
        "<i>Например: 250</i>",
        parse_mode="HTML"
    )


@router.message(AdminStates.waiting_for_plant_sell_price)
async def admin_plant_sell_price(message: Message, state: FSMContext):
    """Цена продажи"""
    try:
        sell_price = int(message.text.strip())
        if sell_price < 0:
            raise ValueError
    except ValueError:
        await message.answer("Введи неотрицательное число!")
        return
    
    await state.update_data(sell_price=sell_price)
    await state.set_state(AdminStates.waiting_for_plant_yield)
    
    await message.answer(
        "<b>Шаг 7/10</b> - Урожай\n\n"
        "Введи количество урожая с грядки:\n"
        "<i>Например: 3</i>",
        parse_mode="HTML"
    )


@router.message(AdminStates.waiting_for_plant_yield)
async def admin_plant_yield(message: Message, state: FSMContext):
    """Урожайность"""
    try:
        yield_amount = int(message.text.strip())
        if yield_amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введи положительное число!")
        return
    
    await state.update_data(yield_amount=yield_amount)
    await state.set_state(AdminStates.waiting_for_plant_level)
    
    await message.answer(
        "<b>Шаг 8/10</b> - Требуемый уровень\n\n"
        "Введи требуемый уровень игрока:\n"
        "<i>Например: 1</i>",
        parse_mode="HTML"
    )


@router.message(AdminStates.waiting_for_plant_level)
async def admin_plant_level(message: Message, state: FSMContext):
    """Требуемый уровень"""
    try:
        required_level = int(message.text.strip())
        if required_level < 0:
            raise ValueError
    except ValueError:
        await message.answer("Введи неотрицательное число!")
        return
    
    await state.update_data(required_level=required_level)
    await state.set_state(AdminStates.waiting_for_plant_exp)
    
    await message.answer(
        "<b>Шаг 9/10</b> - Опыт\n\n"
        "Введи опыт за сбор урожая:\n"
        "<i>Например: 10</i>",
        parse_mode="HTML"
    )


@router.message(AdminStates.waiting_for_plant_exp)
async def admin_plant_exp(message: Message, state: FSMContext):
    """Опыт за сбор"""
    try:
        exp_reward = int(message.text.strip())
        if exp_reward < 0:
            raise ValueError
    except ValueError:
        await message.answer("Введи неотрицательное число!")
        return
    
    await state.update_data(exp_reward=exp_reward)
    
    # Получаем все данные и показываем сводку
    data = await state.get_data()
    
    summary = f"""<b>Шаг 10/10 - Подтверждение</b>

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
        [InlineKeyboardButton(text="Сохранить", callback_data="admin_save_plant")],
        [InlineKeyboardButton(text="Заново", callback_data="admin_add_plant")],
        [InlineKeyboardButton(text="Отмена", callback_data="admin_plants")],
    ])
    
    await message.answer(summary, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "admin_save_plant")
async def admin_save_plant(callback: CallbackQuery, state: FSMContext):
    """Сохранение растения"""
    data = await state.get_data()
    
    db = await get_db()
    
    # Сохраняем в БД
    await db.execute(
        """INSERT OR REPLACE INTO shop_config 
           (item_code, item_name, item_icon, buy_price, sell_price, growth_time, category, sort_order)
           VALUES (?, ?, ?, ?, ?, ?, 'seed', 99)""",
        (data['plant_id'], data['name'], data['emoji'], 
         data['seed_price'], data['sell_price'], data['grow_time'] * 60),
        commit=True
    )
    
    await callback.message.edit_text(
        f"<b>Растение сохранено!</b>\n\n"
        f"{data['emoji']} {data['name']} добавлено в игру.",
        parse_mode="HTML"
    )
    
    await state.clear()


# ==================== ПОМОЩЬ ====================

@router.callback_query(F.data == "admin_help")
async def admin_help(callback: CallbackQuery):
    """Помощь по админ-панели"""
    role = await check_admin_access(callback.from_user.id)
    
    help_text = f"""<b>Помощь по админ-панели</b>

Твоя роль: <b>{role.upper()}</b>

<b>Доступные функции:</b>
👥 Игроки - поиск, просмотр профилей, выдача ресурсов, баны
🌱 Растения - добавление новых растений"""
    
    if role in ('admin', 'creator'):
        help_text += "\n🎁 Промо-акции - создание промокодов"
        help_text += "\n⭐ Ежедневный бонус - настройка бонусов"
        help_text += "\n💰 Экономика - настройка цен"
    
    help_text += "\n📢 Рассылка - массовая отправка сообщений"
    
    if role == 'creator':
        help_text += "\n👑 Управление админами - назначение ролей"
        help_text += "\n📊 Логи - история действий админов"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="admin_back_main")],
    ])
    
    await callback.message.edit_text(help_text, reply_markup=keyboard, parse_mode="HTML")
