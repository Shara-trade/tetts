"""
Админ-панель для управления системой достижений
Все управление через инлайн-кнопки
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from datetime import datetime
try:
    from database import get_database
    from states import AchievementCreateStates, AchievementEditStates, AchievementGiveStates
except ImportError:
    from admin.database import get_database
    from admin.states import AchievementCreateStates, AchievementEditStates, AchievementGiveStates
import json

router = Router()

async def get_db():
    return await get_database()

async def check_admin_access(user_id: int) -> str:
    """Проверяет доступ и возвращает роль"""
    db = await get_db()
    return await db.get_admin_role(user_id)

def get_role_emoji(role: str) -> str:
    return {'creator': '👑', 'admin': '⚡', 'moderator': '🛡️'}.get(role, '❓')

# ==================== ГЛАВНОЕ МЕНЮ АЧИВОК ====================

@router.callback_query(F.data == "admin_achievements")
async def admin_achievements_menu(callback: CallbackQuery, state: FSMContext):
    """Главное меню управления ачивками"""
    await state.clear()
    
    role = await check_admin_access(callback.from_user.id)
    if role not in ('admin', 'creator'):
        await callback.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    db = await get_db()
    stats = await db.admin_get_achievement_stats()
    
    # Получаем количество ачивок
    all_achievements = await db.admin_get_all_achievements()
    active_count = sum(1 for a in all_achievements if a['is_active'])
    
    text = f"""🏆 <b>Управление достижениями</b>

📊 <b>Статистика:</b>
• Всего ачивок: {len(all_achievements)}
• Активных: {active_count}
• Категорий: 6

📈 <b>Получения:</b>
• Всего получений: {stats['total_completions']:,}
• Игроков с ачивками: {stats['unique_players']:,}
• В среднем: {stats['avg_per_player']:.1f} ачивки/игрок

Выбери действие:"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать ачивку", callback_data="ach_create_start")],
        [InlineKeyboardButton(text="📋 Список ачивок", callback_data="ach_list_0")],
        [InlineKeyboardButton(text="📁 Категории", callback_data="ach_categories")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="ach_stats")],
        [InlineKeyboardButton(text="👤 Выдать игроку", callback_data="ach_give_start")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back_main")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

# ==================== СОЗДАНИЕ АЧИВКИ (ПОШАГОВЫЙ МАСТЕР) ====================

@router.callback_query(F.data == "ach_create_start")
async def ach_create_start(callback: CallbackQuery, state: FSMContext):
    """Начало создания ачивки - Шаг 1: Категория"""
    await state.set_state(AchievementCreateStates.step_category)
    
    db = await get_db()
    categories = await db.get_achievement_categories()
    
    buttons = []
    for cat in categories:
        buttons.append([InlineKeyboardButton(
            text=f"{cat['icon']} {cat['name']}",
            callback_data=f"ach_cat_{cat['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="admin_achievements")])
    
    await callback.message.edit_text(
        "🏆 <b>Создание ачивки - Шаг 1/9</b>\n\n"
        "📁 <b>Выбери категорию:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("ach_cat_"), AchievementCreateStates.step_category)
async def ach_create_category(callback: CallbackQuery, state: FSMContext):
    """Сохранение категории - переход к базовым параметрам"""
    category_id = callback.data.replace("ach_cat_", "")
    await state.update_data(category_id=category_id)
    await state.set_state(AchievementCreateStates.step_basic_info)
    
    await callback.message.edit_text(
        "🏆 <b>Создание ачивки - Шаг 2/9</b>\n\n"
        "📝 <b>Базовые параметры:</b>\n\n"
        "Введи через запятую:\n"
        "<code>ID, Название, Описание</code>\n\n"
        "<i>Пример: harvest_1000, Опытный фермер, Собрать 1000 растений</i>\n\n"
        "⚠️ ID должен быть уникальным, латиницей, без пробелов",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_achievements")]
        ]),
        parse_mode="HTML"
    )

@router.message(AchievementCreateStates.step_basic_info)
async def ach_create_basic_info(message: Message, state: FSMContext):
    """Обработка базовых параметров"""
    try:
        parts = message.text.split(",", 2)
        if len(parts) < 3:
            raise ValueError("Нужно 3 параметра через запятую")
        
        code = parts[0].strip().lower()
        name = parts[1].strip()
        description = parts[2].strip()
        
        # Проверка ID
        if not code.replace("_", "").isalnum():
            await message.answer("❌ ID должен содержать только латинские буквы, цифры и _")
            return
        
        await state.update_data(code=code, name=name, description=description)
        await state.set_state(AchievementCreateStates.step_icon)
        
        await message.answer(
            "🏆 <b>Создание ачивки - Шаг 3/9</b>\n\n"
            "🏅 <b>Иконка:</b>\n\n"
            "Введи эмодзи для ачивки:\n"
            "<i>Например: 🥈 или оставь стандартную 🏅</i>\n\n"
            "Отправь «стандарт» для 🏅",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_achievements")]
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}\nПопробуй снова.")

@router.message(AchievementCreateStates.step_icon)
async def ach_create_icon(message: Message, state: FSMContext):
    """Сохранение иконки - переход к цели"""
    icon = "🏅" if message.text.lower() == "стандарт" else message.text.strip()[:2]
    await state.update_data(icon=icon)
    await state.set_state(AchievementCreateStates.step_goal_type)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌾 Собрано урожая", callback_data="goal_harvest")],
        [InlineKeyboardButton(text="💰 Достигнут баланс", callback_data="goal_balance")],
        [InlineKeyboardButton(text="🌱 Посажено растений", callback_data="goal_plant")],
        [InlineKeyboardButton(text="🏆 Уровень престижа", callback_data="goal_prestige")],
        [InlineKeyboardButton(text="📅 Дней подряд", callback_data="goal_streak_days")],
        [InlineKeyboardButton(text="💎 Накоплено кристаллов", callback_data="goal_gems_total")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_achievements")],
    ])
    
    await message.answer(
        "🏆 <b>Создание ачивки - Шаг 4/9</b>\n\n"
        "🎯 <b>Тип цели:</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("goal_"), AchievementCreateStates.step_goal_type)
async def ach_create_goal_type(callback: CallbackQuery, state: FSMContext):
    """Сохранение типа цели"""
    goal_type = callback.data.replace("goal_", "")
    await state.update_data(requirement_type=goal_type)
    await state.set_state(AchievementCreateStates.step_goal_value)
    
    goal_names = {
        'harvest': '🌾 Собрано урожая',
        'balance': '💰 Достигнут баланс',
        'plant': '🌱 Посажено растений',
        'prestige': '🏆 Уровень престижа',
        'streak_days': '📅 Дней подряд',
        'gems_total': '💎 Накоплено кристаллов'
    }
    
    await callback.message.edit_text(
        f"🏆 <b>Создание ачивки - Шаг 5/9</b>\n\n"
        f"📊 <b>{goal_names.get(goal_type, 'Цель')}:</b>\n\n"
        f"Введи требуемое значение:\n"
        f"<i>Например: 1000</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_achievements")]
        ]),
        parse_mode="HTML"
    )

@router.message(AchievementCreateStates.step_goal_value)
async def ach_create_goal_value(message: Message, state: FSMContext):
    """Сохранение значения цели - переход к наградам"""
    try:
        value = int(message.text.strip())
        if value <= 0:
            raise ValueError("Значение должно быть положительным")
        
        await state.update_data(requirement_count=value)
        await state.set_state(AchievementCreateStates.step_reward_type)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Монеты", callback_data="reward_coins")],
            [InlineKeyboardButton(text="💎 Кристаллы", callback_data="reward_gems")],
            [InlineKeyboardButton(text="🌱 Предмет", callback_data="reward_item")],
            [InlineKeyboardButton(text="📈 Множитель", callback_data="reward_multiplier")],
            [InlineKeyboardButton(text="✅ Далее (без наград)", callback_data="reward_none")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_achievements")],
        ])
        
        await message.answer(
            "🏆 <b>Создание ачивки - Шаг 6/9</b>\n\n"
            "🎁 <b>Выбери тип награды:</b>\n"
            "(можно добавить несколько)",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Введи положительное число!")

@router.callback_query(F.data.startswith("reward_"), AchievementCreateStates.step_reward_type)
async def ach_create_reward_type(callback: CallbackQuery, state: FSMContext):
    """Обработка типа награды"""
    reward_type = callback.data.replace("reward_", "")
    
    if reward_type == "none":
        # Без наград - переходим к типу ачивки
        await state.update_data(reward_coins=0, reward_gems=0, reward_items={}, reward_multiplier=0)
        await ach_create_achievement_type(callback, state)
        return
    
    await state.update_data(current_reward_type=reward_type)
    
    reward_names = {
        'coins': '💰 Монеты',
        'gems': '💎 Кристаллы',
        'item': '🌱 Предмет (код:количество)',
        'multiplier': '📈 Множитель (0.1 = +10%)'
    }
    
    await callback.message.edit_text(
        f"🏆 <b>Создание ачивки - Шаг 6/9</b>\n\n"
        f"{reward_names.get(reward_type, 'Награда')}:\n\n"
        f"Введи значение:\n"
        f"<i>Например: 2000</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить →", callback_data="reward_skip")]
        ]),
        parse_mode="HTML"
    )

@router.message(AchievementCreateStates.step_reward_type)
async def ach_create_reward_value(message: Message, state: FSMContext):
    """Обработка значения награды"""
    data = await state.get_data()
    reward_type = data.get('current_reward_type')
    
    try:
        if reward_type == 'item':
            # Предмет в формате код:количество
            parts = message.text.split(':')
            item_code = parts[0].strip()
            qty = int(parts[1]) if len(parts) > 1 else 1
            reward_items = data.get('reward_items', {})
            reward_items[item_code] = qty
            await state.update_data(reward_items=reward_items)
        elif reward_type == 'multiplier':
            value = float(message.text.strip())
            await state.update_data(reward_multiplier=value)
        else:
            value = int(message.text.strip())
            if reward_type == 'coins':
                await state.update_data(reward_coins=value)
            elif reward_type == 'gems':
                await state.update_data(reward_gems=value)
        
        # Спрашиваем еще награды или идем дальше
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 +Монеты", callback_data="reward_coins")],
            [InlineKeyboardButton(text="💎 +Кристаллы", callback_data="reward_gems")],
            [InlineKeyboardButton(text="🌱 +Предмет", callback_data="reward_item")],
            [InlineKeyboardButton(text="📈 +Множитель", callback_data="reward_multiplier")],
            [InlineKeyboardButton(text="✅ Далее →", callback_data="reward_done")],
        ])
        
        # Показываем текущие награды
        current_rewards = []
        if data.get('reward_coins'):
            current_rewards.append(f"💰 {data['reward_coins']:,} монет")
        if data.get('reward_gems'):
            current_rewards.append(f"💎 {data['reward_gems']} кристаллов")
        if data.get('reward_items'):
            for item, qty in data['reward_items'].items():
                current_rewards.append(f"🌱 {item} x{qty}")
        if data.get('reward_multiplier'):
            current_rewards.append(f"📈 +x{data['reward_multiplier']:.1f} множитель")
        
        rewards_text = "\n".join(current_rewards) if current_rewards else "Пока нет наград"
        
        await message.answer(
            f"🏆 <b>Создание ачивки - Шаг 6/9</b>\n\n"
            f"🎁 <b>Текущие награды:</b>\n{rewards_text}\n\n"
            f"Добавить еще или продолжить?",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Введи корректное число!")

@router.callback_query(F.data == "reward_done", AchievementCreateStates.step_reward_type)
async def ach_create_achievement_type(callback: CallbackQuery, state: FSMContext):
    """Шаг 8: Выбор типа ачивки"""
    await state.set_state(AchievementCreateStates.step_achievement_type)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📌 Обычная", callback_data="type_regular")],
        [InlineKeyboardButton(text="📊 Многоуровневая", callback_data="type_multi")],
        [InlineKeyboardButton(text="🤫 Секретная", callback_data="type_secret")],
        [InlineKeyboardButton(text="🎪 Ивентовая", callback_data="type_event")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_achievements")],
    ])
    
    await callback.message.edit_text(
        "🏆 <b>Создание ачивки - Шаг 7/9</b>\n\n"
        "📋 <b>Тип достижения:</b>\n\n"
        "📌 <b>Обычная</b> - стандартное достижение\n"
        "📊 <b>Многоуровневая</b> - несколько этапов\n"
        "🤫 <b>Секретная</b> - скрыта до выполнения\n"
        "🎪 <b>Ивентовая</b> - временное событие",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("type_"), AchievementCreateStates.step_achievement_type)
async def ach_create_type_selected(callback: CallbackQuery, state: FSMContext):
    """Обработка типа ачивки"""
    ach_type = callback.data.replace("type_", "")
    await state.update_data(achievement_type=ach_type)
    
    if ach_type == "event":
        # Для ивентовой - запрашиваем дату окончания
        await state.set_state(AchievementCreateStates.step_event_date)
        await callback.message.edit_text(
            "🏆 <b>Создание ачивки - Шаг 8/9</b>\n\n"
            "📅 <b>Дата окончания ивента:</b>\n\n"
            "Введи дату в формате ДД.ММ.ГГГГ\n"
            "<i>Например: 31.12.2024</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_achievements")]
            ]),
            parse_mode="HTML"
        )
    elif ach_type == "multi":
        # Для многоуровневой - запрашиваем родителя
        await state.set_state(AchievementCreateStates.step_parent_achievement)
        db = await get_db()
        all_achievements = await db.admin_get_all_achievements(active_only=True)
        
        buttons = [[InlineKeyboardButton(text="🆕 Новая линейка", callback_data="parent_new")]]
        for ach in all_achievements[:10]:  # Показываем первые 10
            buttons.append([InlineKeyboardButton(
                text=f"{ach['icon']} {ach['name']}",
                callback_data=f"parent_{ach['id']}"
            )])
        
        buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="admin_achievements")])
        
        await callback.message.edit_text(
            "🏆 <b>Создание ачивки - Шаг 8/9</b>\n\n"
            "🔗 <b>Родительская ачивка:</b>\n\n"
            "Выбери предыдущий уровень или создай новую линейку:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )
    else:
        # Для обычной и секретной - сразу к сортировке
        await state.update_data(parent_id=None, level=1)
        await ach_create_sort_order(callback, state)

@router.callback_query(F.data.startswith("parent_"), AchievementCreateStates.step_parent_achievement)
async def ach_create_parent_selected(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора родительской ачивки"""
    parent_data = callback.data.replace("parent_", "")
    
    if parent_data == "new":
        await state.update_data(parent_id=None, level=1)
    else:
        parent_id = int(parent_data)
        # Определяем уровень
        db = await get_db()
        parent = await db.get_achievement_by_id(parent_id)
        level = parent['level'] + 1 if parent else 1
        await state.update_data(parent_id=parent_id, level=level)
    
    await ach_create_sort_order(callback, state)

@router.message(AchievementCreateStates.step_event_date)
async def ach_create_event_date(message: Message, state: FSMContext):
    """Обработка даты ивента"""
    try:
        date_str = message.text.strip()
        date_obj = datetime.strptime(date_str, "%d.%m.%Y")
        await state.update_data(event_end_date=date_obj.strftime("%Y-%m-%d"))
        await ach_create_sort_order(message, state)
    except ValueError:
        await message.answer("❌ Неверный формат! Используй ДД.ММ.ГГГГ")

async def ach_create_sort_order(target, state: FSMContext):
    """Шаг 9: Порядок сортировки"""
    await state.set_state(AchievementCreateStates.step_sort_order)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 (в начало)", callback_data="sort_1")],
        [InlineKeyboardButton(text="10", callback_data="sort_10")],
        [InlineKeyboardButton(text="50", callback_data="sort_50")],
        [InlineKeyboardButton(text="100 (в конец)", callback_data="sort_100")],
    ])
    
    text = "🏆 <b>Создание ачивки - Шаг 9/9</b>\n\n📊 <b>Порядок сортировки:</b>\n\nЧем меньше число, тем выше в списке."
    
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("sort_"), AchievementCreateStates.step_sort_order)
async def ach_create_sort_selected(callback: CallbackQuery, state: FSMContext):
    """Сохранение сортировки - показ превью"""
    sort_order = int(callback.data.replace("sort_", ""))
    await state.update_data(sort_order=sort_order)
    await ach_create_preview(callback, state)

async def ach_create_preview(callback: CallbackQuery, state: FSMContext):
    """Показ превью ачивки"""
    await state.set_state(AchievementCreateStates.step_confirm)
    data = await state.get_data()
    
    # Формируем текст превью
    category_names = {
        'harvest': '🌾 Сбор урожая', 'finance': '💰 Финансы',
        'prestige': '🏆 Престиж', 'activity': '📅 Активность',
        'special': '🎯 Особые', 'events': '🎮 Ивенты'
    }
    
    type_names = {
        'regular': '📌 Обычная', 'multi': '📊 Многоуровневая',
        'secret': '🤫 Секретная', 'event': '🎪 Ивентовая'
    }
    
    rewards = []
    if data.get('reward_coins', 0) > 0:
        rewards.append(f"💰 {data['reward_coins']:,} монет")
    if data.get('reward_gems', 0) > 0:
        rewards.append(f"💎 {data['reward_gems']} кристаллов")
    if data.get('reward_items'):
        for item, qty in data['reward_items'].items():
            rewards.append(f"🌱 {item} x{qty}")
    if data.get('reward_multiplier', 0) > 0:
        rewards.append(f"📈 +x{data['reward_multiplier']:.1f} множитель")
    
    rewards_text = "\n".join(rewards) if rewards else "Нет наград"
    
    preview = f"""🏆 <b>Предпросмотр ачивки</b>

📁 Категория: {category_names.get(data['category_id'], data['category_id'])}
🆔 ID: <code>{data['code']}</code>
🏅 Название: {data['icon']} {data['name']}
📝 Описание: {data['description']}

🎯 Цель: {data['requirement_type']} = {data['requirement_count']:,}

🎁 Награды:
{rewards_text}

📋 Тип: {type_names.get(data.get('achievement_type', 'regular'))}
🔢 Уровень: {data.get('level', 1)}
📊 Порядок: {data.get('sort_order', 0)}"""
    
    if data.get('parent_id'):
        preview += f"\n🔗 Родитель: ID {data['parent_id']}"
    if data.get('event_end_date'):
        preview += f"\n📅 Дата окончания: {data['event_end_date']}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Создать", callback_data="ach_create_confirm")],
        [InlineKeyboardButton(text="🔄 Начать заново", callback_data="ach_create_start")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_achievements")],
    ])
    
    await callback.message.edit_text(preview, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "ach_create_confirm", AchievementCreateStates.step_confirm)
async def ach_create_final(callback: CallbackQuery, state: FSMContext):
    """Финальное создание ачивки"""
    data = await state.get_data()
    db = await get_db()
    
    try:
        achievement_id = await db.admin_create_achievement({
            'code': data['code'],
            'name': data['name'],
            'description': data['description'],
            'icon': data.get('icon', '🏅'),
            'category_id': data['category_id'],
            'type': data.get('achievement_type', 'regular'),
            'parent_id': data.get('parent_id'),
            'level': data.get('level', 1),
            'event_end_date': data.get('event_end_date'),
            'requirement_type': data['requirement_type'],
            'requirement_count': data['requirement_count'],
            'reward_coins': data.get('reward_coins', 0),
            'reward_gems': data.get('reward_gems', 0),
            'reward_items': data.get('reward_items', {}),
            'reward_multiplier': data.get('reward_multiplier', 0),
            'is_secret': data.get('achievement_type') == 'secret',
            'sort_order': data.get('sort_order', 0)
        })
        
        # Логируем
        await db.log_admin_action(
            callback.from_user.id, "create_achievement", None,
            details={"achievement_id": achievement_id, "name": data['name']}
        )
        
        await callback.message.edit_text(
            f"✅ <b>Ачивка создана!</b>\n\n"
            f"{data.get('icon', '🏅')} {data['name']} (ID: {achievement_id})",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 К списку", callback_data="ach_list_0")],
                [InlineKeyboardButton(text="➕ Создать еще", callback_data="ach_create_start")],
                [InlineKeyboardButton(text="🏆 Меню ачивок", callback_data="admin_achievements")],
            ]),
            parse_mode="HTML"
        )
        await state.clear()
        
    except Exception as e:
        await callback.message.edit_text(
            f"❌ <b>Ошибка создания:</b>\n<code>{str(e)}</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Повторить", callback_data="ach_create_start")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_achievements")],
            ]),
            parse_mode="HTML"
        )

# ==================== СПИСОК АЧИВОК ====================

@router.callback_query(F.data.startswith("ach_list_"))
async def ach_list(callback: CallbackQuery, state: FSMContext):
    """Список ачивок с пагинацией"""
    await state.clear()
    
    page = int(callback.data.replace("ach_list_", ""))
    per_page = 5
    
    db = await get_db()
    all_achievements = await db.admin_get_all_achievements()
    
    total_pages = (len(all_achievements) + per_page - 1) // per_page
    start = page * per_page
    end = start + per_page
    page_achievements = all_achievements[start:end]
    
    if not page_achievements:
        await callback.answer("Нет ачивок на этой странице!")
        return
    
    text_lines = [f"🏆 <b>Список ачивок (стр. {page + 1}/{total_pages})</b>\n"]
    
    keyboard_rows = []
    
    for i, ach in enumerate(page_achievements, start + 1):
        status = "✅" if ach['is_active'] else "⏸️"
        text_lines.append(
            f"{ach['icon']} [{i}] <b>{ach['name']}</b>\n"
            f"   🎯 {ach['requirement_type']}: {ach['requirement_count']:,}\n"
            f"   🎁 {ach['reward_coins']:,}🪙"
        )
        if ach['reward_gems'] > 0:
            text_lines.append(f" + {ach['reward_gems']}💎")
        text_lines.append(f"\n   {status} Активно | Получили: {ach['completed_count']:,}\n")
        
        keyboard_rows.append([
            InlineKeyboardButton(text=f"✏️ Ред {ach['name'][:10]}", callback_data=f"ach_edit_{ach['id']}"),
            InlineKeyboardButton(text="👥 Стат", callback_data=f"ach_stat_{ach['id']}"),
        ])
        keyboard_rows.append([
            InlineKeyboardButton(text="⏸ Деакт" if ach['is_active'] else "▶️ Актив", 
                               callback_data=f"ach_toggle_{ach['id']}"),
            InlineKeyboardButton(text="🗑 Удал", callback_data=f"ach_del_{ach['id']}"),
        ])
    
    # Кнопки навигации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"ach_list_{page-1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"ach_list_{page+1}"))
    
    keyboard_rows.append(nav_buttons)
    keyboard_rows.append([
        InlineKeyboardButton(text="➕ Добавить", callback_data="ach_create_start"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_achievements")
    ])
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("ach_toggle_"))
async def ach_toggle(callback: CallbackQuery):
    """Активация/деактивация ачивки"""
    ach_id = int(callback.data.replace("ach_toggle_", ""))
    
    db = await get_db()
    ach = await db.get_achievement_by_id(ach_id)
    
    if not ach:
        await callback.answer("Ачивка не найдена!")
        return
    
    new_status = not ach.get('is_active', True)
    await db.admin_update_achievement(ach_id, {'is_active': 1 if new_status else 0})
    
    status_text = "активирована" if new_status else "деактивирована"
    await callback.answer(f"✅ Ачивка {status_text}!")
    
    # Возвращаемся к списку
    await ach_list(callback, None)

@router.callback_query(F.data.startswith("ach_del_"))
async def ach_delete_prompt(callback: CallbackQuery, state: FSMContext):
    """Запрос на удаление ачивки"""
    ach_id = int(callback.data.replace("ach_del_", ""))
    await state.update_data(delete_ach_id=ach_id)
    await state.set_state(AchievementEditStates.confirm_delete)
    
    db = await get_db()
    ach = await db.get_achievement_by_id(ach_id)
    
    if not ach:
        await callback.answer("Ачивка не найдена!")
        return
    
    # Получаем статистику
    progress_count = await db.fetchone(
        "SELECT COUNT(*) FROM player_achievements WHERE achievement_id = ?",
        (ach_id,)
    )
    completed_count = await db.fetchone(
        "SELECT COUNT(*) FROM player_achievements WHERE achievement_id = ? AND completed = 1",
        (ach_id,)
    )
    
    await callback.message.edit_text(
        f"⚠️ <b>Удаление ачивки</b>\n\n"
        f"{ach['icon']} <b>{ach['name']}</b>\n\n"
        f"Будет удалено:\n"
        f"• Сама ачивка\n"
        f"• Прогресс {progress_count[0]:,} игроков\n"
        f"• История получений ({completed_count[0]:,} выполнений)\n\n"
        f"<b>Это действие нельзя отменить!</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Полное удаление", callback_data="ach_delete_full")],
            [InlineKeyboardButton(text="⏸ Только деактивировать", callback_data="ach_delete_deact")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="ach_list_0")],
        ]),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("ach_delete_"), AchievementEditStates.confirm_delete)
async def ach_delete_confirm(callback: CallbackQuery, state: FSMContext):
    """Подтверждение удаления"""
    data = await state.get_data()
    ach_id = data.get('delete_ach_id')
    
    if not ach_id:
        await callback.answer("Ошибка!")
        return
    
    db = await get_db()
    delete_type = callback.data.replace("ach_delete_", "")
    
    if delete_type == "full":
        await db.admin_delete_achievement(ach_id, full_delete=True)
        await callback.answer("🗑 Ачивка полностью удалена!")
    else:
        await db.admin_delete_achievement(ach_id, full_delete=False)
        await callback.answer("⏸ Ачивка деактивирована!")
    
    await state.clear()
    await ach_list(callback, None)

# ==================== СТАТИСТИКА ====================

@router.callback_query(F.data == "ach_stats")
async def ach_stats(callback: CallbackQuery):
    """Статистика ачивок"""
    db = await get_db()
    stats = await db.admin_get_achievement_stats()
    
    text = f"""📊 <b>Статистика ачивок</b>

<b>Общая:</b>
• Всего получений: {stats['total_completions']:,}
• Игроков с ачивками: {stats['unique_players']:,}
• Среднее: {stats['avg_per_player']:.1f} ачивки/игрок

<b>🔥 Популярные:</b>"""
    
    for i, pop in enumerate(stats['popular'][:3], 1):
        text += f"\n{i}. {pop['icon']} {pop['name']}: {pop['count']:,}"
    
    text += f"\n\n<b>💎 Редкие (&lt;1%):</b>"
    for i, rare in enumerate(stats['rare'][:3], 1):
        text += f"\n{i}. {rare['icon']} {rare['name']}: {rare['count']:,}"
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="ach_stats")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_achievements")],
        ]),
        parse_mode="HTML"
    )

# ==================== ВЫДАЧА АЧИВКИ ИГРОКУ ====================

@router.callback_query(F.data == "ach_give_start")
async def ach_give_start(callback: CallbackQuery, state: FSMContext):
    """Начало выдачи ачивки"""
    await state.set_state(AchievementGiveStates.waiting_player)
    
    await callback.message.edit_text(
        "👤 <b>Выдача ачивки игроку</b>\n\n"
        "Шаг 1/3: Введи ID или @username игрока:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_achievements")]
        ]),
        parse_mode="HTML"
    )

@router.message(AchievementGiveStates.waiting_player)
async def ach_give_player(message: Message, state: FSMContext):
    """Поиск игрока"""
    search = message.text.strip()
    db = await get_db()
    
    # Поиск по ID или username
    if search.isdigit():
        user = await db.get_user(int(search))
    else:
        search = search.replace("@", "")
        user = await db.get_user_by_username(search)
    
    if not user:
        await message.answer("❌ Игрок не найден! Попробуй снова.")
        return
    
    await state.update_data(target_user_id=user['user_id'], target_user_name=user['first_name'])
    await state.set_state(AchievementGiveStates.waiting_achievement)
    
    # Получаем список ачивок
    all_achievements = await db.admin_get_all_achievements(active_only=True)
    
    buttons = []
    for ach in all_achievements[:20]:  # Первые 20
        buttons.append([InlineKeyboardButton(
            text=f"{ach['icon']} {ach['name']}",
            callback_data=f"giveach_{ach['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="admin_achievements")])
    
    await message.answer(
        f"👤 <b>Игрок:</b> {user['first_name']} (ID: {user['user_id']})\n\n"
        f"Шаг 2/3: Выбери ачивку:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("giveach_"), AchievementGiveStates.waiting_achievement)
async def ach_give_select(callback: CallbackQuery, state: FSMContext):
    """Выбор ачивки для выдачи"""
    ach_id = int(callback.data.replace("giveach_", ""))
    
    db = await get_db()
    ach = await db.get_achievement_by_id(ach_id)
    data = await state.get_data()
    
    if not ach:
        await callback.answer("Ачивка не найдена!")
        return
    
    await state.update_data(achievement_id=ach_id, achievement_name=ach['name'])
    await state.set_state(AchievementGiveStates.confirm_give)
    
    # Формируем текст наград
    rewards = []
    if ach['reward_coins'] > 0:
        rewards.append(f"• {ach['reward_coins']:,}🪙")
    if ach['reward_gems'] > 0:
        rewards.append(f"• {ach['reward_gems']}💎")
    for item, qty in ach.get('reward_items', {}).items():
        rewards.append(f"• {item} x{qty}")
    
    rewards_text = "\n".join(rewards) if rewards else "Нет наград"
    
    await callback.message.edit_text(
        f"⚠️ <b>Подтверждение выдачи</b>\n\n"
        f"Выдать ачивку <b>{ach['icon']} {ach['name']}</b>\n"
        f"игроку <b>{data['target_user_name']}</b>?\n\n"
        f"🎁 Награды:\n{rewards_text}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Выдать", callback_data="giveach_confirm")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_achievements")],
        ]),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "giveach_confirm", AchievementGiveStates.confirm_give)
async def ach_give_confirm(callback: CallbackQuery, state: FSMContext):
    """Финальная выдача ачивки"""
    data = await state.get_data()
    db = await get_db()
    
    result = await db.admin_give_achievement(
        callback.from_user.id,
        data['target_user_id'],
        data['achievement_id']
    )
    
    if result['success']:
        await callback.message.edit_text(
            f"✅ <b>Ачивка выдана!</b>\n\n"
            f"{result['achievement_icon']} <b>{result['achievement_name']}</b>\n"
            f"Игроку: {data['target_user_name']}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👤 Выдать еще", callback_data="ach_give_start")],
                [InlineKeyboardButton(text="🏆 Меню ачивок", callback_data="admin_achievements")],
            ]),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            f"❌ <b>Ошибка:</b> {result['message']}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_achievements")],
            ]),
            parse_mode="HTML"
        )
    
    await state.clear()

# ==================== КАТЕГОРИИ ====================

@router.callback_query(F.data == "ach_categories")
async def ach_categories(callback: CallbackQuery):
    """Список категорий"""
    db = await get_db()
    categories = await db.get_achievement_categories()
    
    text_lines = ["📁 <b>Категории достижений</b>\n"]
    buttons = []
    
    for cat in categories:
        # Считаем ачивки в категории
        count = await db.fetchone(
            "SELECT COUNT(*) FROM achievements WHERE category_id = ? AND is_active = 1",
            (cat['id'],)
        )
        text_lines.append(f"{cat['icon']} <b>{cat['name']}</b> ({count[0]} ачивок)")
        buttons.append([InlineKeyboardButton(
            text=f"{cat['icon']} {cat['name']}",
            callback_data=f"ach_cat_view_{cat['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_achievements")])
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("ach_cat_view_"))
async def ach_category_view(callback: CallbackQuery):
    """Просмотр ачивок в категории"""
    category_id = callback.data.replace("ach_cat_view_", "")
    
    db = await get_db()
    achievements = await db.get_achievements_by_category(0, category_id)
    
    # Ищем категорию
    categories = await db.get_achievement_categories()
    cat_info = next((c for c in categories if c['id'] == category_id), None)
    
    if not achievements:
        await callback.answer("В этой категории пока нет ачивок!")
        return
    
    text_lines = [f"{cat_info['icon'] if cat_info else '📁'} <b>{cat_info['name'] if cat_info else category_id}</b>\n"]
    
    for ach in achievements:
        if ach.get('is_locked'):
            text_lines.append(f"🔒 ??? (секретная)")
        else:
            status = "✅" if ach['completed'] else "⏳"
            text_lines.append(f"{status} {ach['icon']} {ach['name']}")
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 К категориям", callback_data="ach_categories")],
        ]),
        parse_mode="HTML"
    )
