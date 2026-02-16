from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from database import get_database
from keyboards import *
from states import PlayerStates
import asyncio

router = Router()

# Получаем экземпляр базы данных (синглтон)
async def get_db():
    return await get_database()

@router.message(Command("start"))
async def start_handler(message: Message):
    db = await get_db()
    user = await db.get_user(message.from_user.id)
    if not user:
        await db.create_user(
            message.from_user.id,
            message.from_user.username or "",
            message.from_user.first_name or ""
        )
        await message.answer(
            f"Добро пожаловать на твою ферму, {message.from_user.first_name}! 👋\n"
            "Начни с 🌾 Моя Ферма!",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.answer("Добро пожаловать обратно!", reply_markup=get_main_keyboard())
    await show_farm(message.from_user.id, message)

async def show_farm(user_id: int, obj: Message | CallbackQuery):
    db = await get_db()
    user = await db.get_user(user_id)
    plots = await db.get_plots(user_id)
    
    # Проверка готовых грядок
    city_name = "Деревня" if user['city_level'] == 0 else f"Город {user['city_level']}"
    text_lines = [
        f"🧑‍🌾 <b>Твоя Ферма ({city_name}):</b>\n",
        f"Баланс: 🪙 {user['balance']:,}\n",
        f"Множитель дохода: x{user['prestige_multiplier']:.1f}"
    ]
    
    # Ежедневный бонус
    bonus = await db.get_daily_bonus(user_id)
    streak_text = f"Заходишь {bonus['streak']} {'день' if bonus['streak']==1 else 'дня подряд'}. Завтра: +{bonus['coins']} монет."
    if bonus['available']:
        text_lines.append(f"\n🎁 <b>Ежедневный бонус:</b> {streak_text}")
    else:
        text_lines.append(f"\n🎁 Ежедневный бонус: {bonus.get('message', streak_text)}")
    
    # Грядки
    for plot in plots:
        if plot["status"] == "empty":
            text_lines.append(f"🟫 Грядка #{plot['number']}: Пусто")
        elif plot["status"] == "growing":
            minutes = plot["remaining_time"] // 60
            seconds = plot["remaining_time"] % 60
            time_str = f"{minutes:02d}:{seconds:02d}"
            text_lines.append(f"{plot.get('icon', '🌱')} Грядка #{plot['number']}: {plot['crop_type']} (⬆️ Созреет через {time_str})")
        else:  # ready
            text_lines.append(f"{plot.get('icon', '✅')} Грядка #{plot['number']}: {plot['crop_type']} (✅ ГОТОВО!)")
    
    keyboard = get_farm_keyboard(plots)
    
    if isinstance(obj, Message):
        await obj.answer("\n".join(text_lines), reply_markup=get_main_keyboard(), parse_mode="HTML")
        await obj.answer("Действия:", reply_markup=keyboard)
    else:
        await obj.message.edit_text("\n".join(text_lines), reply_markup=keyboard, parse_mode="HTML")

@router.message(F.text == "🌾 Моя Ферма")
async def farm_handler(message: Message):
    await show_farm(message.from_user.id, message)

@router.callback_query(F.data.startswith("plant_"))
async def plant_crop(callback: CallbackQuery, state: FSMContext):
    plot_num = int(callback.data.split("_")[1])
    db = await get_db()
    crops = await db.get_shop_items("seed")
    
    buttons = []
    for crop in crops:
        buttons.append(InlineKeyboardButton(
            text=f"{crop['icon']} {crop['name']} ({crop['buy_price']}🪙)",
            callback_data=f"buy_plant_{plot_num}_{crop['item_code']}"
        ))
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        buttons[:2],
        buttons[2:] if len(buttons) > 2 else [],
        [InlineKeyboardButton(text="🔙 Назад к грядкам", callback_data="back_farm")]
    ])
    
    await callback.message.edit_text(
        f"Выбери культуру для посадки на грядке #{plot_num}:",
        reply_markup=keyboard
    )
    await state.set_state(PlayerStates.planting_crop)
    await state.update_data(plot_number=plot_num)

@router.callback_query(F.data == "back_farm")
async def back_to_farm(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_farm(callback.from_user.id, callback.message)

@router.callback_query(F.data.startswith("buy_plant_"))
async def buy_plant(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    plot_num = int(parts[2])
    item_code = parts[3]
    
    db = await get_db()
    # Получаем данные о культуре из БД
    crops = await db.get_shop_items("seed")
    crop = next((c for c in crops if c["item_code"] == item_code), None)
    
    if not crop:
        await callback.answer("Ошибка: культура не найдена!")
        return
    
    user = await db.get_user(callback.from_user.id)
    if user["balance"] < crop["buy_price"]:
        await callback.answer(f"❌ Недостаточно монет! Нужно {crop['buy_price']}🪙", show_alert=True)
        return
    
    # Списываем деньги и сажаем
    await db.update_balance(callback.from_user.id, -crop["buy_price"])
    await db.plant_crop(callback.from_user.id, plot_num, item_code, crop["growth_time"])
    
    # Обновляем квесты и достижения
    await db.execute(
        "UPDATE users SET total_planted = total_planted + 1 WHERE user_id = ?",
        (callback.from_user.id,), commit=True
    )
    await db.update_quest_progress(callback.from_user.id, 'plant', 1)
    new_achievements = await db.check_achievements(callback.from_user.id)
    
    # Показываем уведомления о достижениях
    if new_achievements:
        for ach in new_achievements:
            await callback.message.answer(
                f"🎉 <b>Новое достижение!</b>\n\n"
                f"{ach['icon']} <b>{ach['name']}</b>\n"
                f"🎁 Награда: {ach['reward_coins']}🪙",
                parse_mode="HTML"
            )
    
    await callback.answer(f"✅ Посажено {crop['icon']} {crop['name']}!")
    await show_farm(callback.from_user.id, callback.message)
    await state.clear()


# Сбор урожая
@router.callback_query(F.data == "harvest_all")
async def harvest_all(callback: CallbackQuery):
    db = await get_db()
    
    # Получаем список созревших культур перед сбором
    plots = await db.get_plots(callback.from_user.id)
    ready_crops = [p['crop_type'] for p in plots if p['status'] == 'ready']
    
    # Проверяем сезонное событие
    event = await db.get_active_event()
    multiplier = event['multiplier'] if event else 1.0
    
    total = await db.harvest_plots(callback.from_user.id)
    
    if total > 0:
        # Учитываем множитель события
        if event:
            bonus = int(total * (multiplier - 1))
            total_with_bonus = int(total * multiplier)
            bonus_text = f" (включая бонус события +{bonus}🪙)"
        else:
            total_with_bonus = int(total)
            bonus_text = ""
        
        # Обновляем статистику
        await db.execute(
            "UPDATE users SET total_earned = total_earned + ? WHERE user_id = ?",
            (total_with_bonus, callback.from_user.id), commit=True
        )
    
        # Обновляем квесты по каждой культуре
        for crop_type in ready_crops:
            await db.update_quest_progress(callback.from_user.id, 'harvest', 1, crop_type)
        await db.update_quest_progress(callback.from_user.id, 'harvest', len(ready_crops))
        
        # Обновляем событие
        if event:
            await db.update_event_score(callback.from_user.id, total_with_bonus)
        
        # Проверяем достижения
        new_achievements = await db.check_achievements(callback.from_user.id)
        
        await callback.answer(f"✅ Собрано на {total_with_bonus}🪙{bonus_text}!")
        
        # Показываем уведомления о достижениях
        if new_achievements:
            for ach in new_achievements:
                await callback.message.answer(
                    f"🎉 <b>Новое достижение!</b>\n\n"
                    f"{ach['icon']} <b>{ach['name']}</b>\n"
                    f"🎁 Награда: {ach['reward_coins']}🪙",
                    parse_mode="HTML"
                )
    else:
        await callback.answer("❌ Нет готовых грядок!")
    
    await show_farm(callback.from_user.id, callback.message)

# Ежедневный бонус
@router.callback_query(F.data == "claim_daily")
async def claim_daily(callback: CallbackQuery):
    db = await get_db()
    result = await db.claim_daily_bonus(callback.from_user.id)
    if result:
        bonus = await db.get_daily_bonus(callback.from_user.id)
        await callback.answer(f"🎁 Бонус получен! +{bonus.get('coins', 50)}🪙")
    else:
        await callback.answer("❌ Бонус уже получен сегодня!", show_alert=True)
    await show_farm(callback.from_user.id, callback.message)

# Обновление фермы
@router.callback_query(F.data == "refresh_farm")
async def refresh_farm(callback: CallbackQuery):
    await callback.answer("🔄 Обновлено!")
    await show_farm(callback.from_user.id, callback.message)

# Магазин
@router.message(F.text == "🏪 Магазин")
async def shop_handler(message: Message):
    db = await get_db()
    
    # Проверяем сезонное событие
    event = await db.get_active_event()
    
    text = "🏪 <b>Магазин</b>\n\nВыбери категорию:"
    
    if event:
        from datetime import datetime
        time_left = event['end_date'] - datetime.now()
        hours_left = int(time_left.total_seconds() // 3600)
        
        text = (
            f"🏪 <b>Магазин</b>\n\n"
            f"🎉 <b>{event['name']}</b> активно!\n"
            f"💰 x{event['multiplier']} награды за урожай!\n"
            f"⏰ Осталось: {hours_left} часов\n\n"
            f"Выбери категорию:"
        )
    
    await message.answer(
        text,
        reply_markup=get_shop_categories(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("shop_"))
async def shop_category(callback: CallbackQuery):
    category = callback.data.replace("shop_", "")
    db = await get_db()
    
    # Получаем обычные товары
    items = await db.get_shop_items(category)
    
    # Добавляем сезонные товары если есть событие
    event = await db.get_active_event()
    if event and category == 'seed':
        seasonal_items = await db.fetchall(
            """SELECT * FROM shop_config 
               WHERE category = ? AND is_seasonal = 1 AND season = ?""",
            (category, event['season'])
        )
        # Преобразуем в тот же формат
        for row in seasonal_items:
            items.append({
                "item_code": row[0],
                "name": row[1],
                "icon": row[2],
                "buy_price": row[3],
                "sell_price": row[4],
                "growth_time": row[5],
                "category": row[6],
                "is_seasonal": True
            })
    
    if not items:
        await callback.answer("Категория пуста!")
        return
    
    text_lines = [f"🏪 <b>{category.capitalize()}</b>\n"]
    
    if event and category == 'seed':
        text_lines.append(f"🎉 {event['name']} - x{event['multiplier']} награды!\n")
    
    for item in items:
        seasonal_mark = "🌟 " if item.get('is_seasonal') else ""
        text_lines.append(f"{seasonal_mark}{item['icon']} <b>{item['name']}</b>")
        if item['buy_price'] > 0:
            text_lines.append(f"   💰 Покупка: {item['buy_price']}🪙")
        if item['sell_price'] > 0:
            sell_price = int(item['sell_price'] * event['multiplier']) if event else item['sell_price']
            text_lines.append(f"   💵 Продажа: {sell_price}🪙")
        if item['growth_time'] > 0:
            minutes = item['growth_time'] // 60
            text_lines.append(f"   ⏱️ Рост: {minutes} мин")
        text_lines.append("")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_shop")]
    ])
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "back_shop")
async def back_to_shop(callback: CallbackQuery):
    await callback.message.edit_text(
        "🏪 <b>Магазин</b>\n\nВыбери категорию:",
        reply_markup=get_shop_categories(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.delete()
    await show_farm(callback.from_user.id, callback.message)

# Амбар (инвентарь)
@router.message(F.text == "📦 Амбар")
async def inventory_handler(message: Message):
    db = await get_db()
    inventory = await db.get_inventory(message.from_user.id)
    
    if not inventory:
        await message.answer("📦 <b>Твой Амбар</b>\n\nПусто! Купи семена в магазине.", parse_mode="HTML")
        return
    
    text_lines = ["📦 <b>Твой Амбар</b>\n"]
    for item_code, quantity in inventory.items():
        text_lines.append(f"• {item_code}: {quantity} шт.")
    
    await message.answer("\n".join(text_lines), parse_mode="HTML")

# Престиж
@router.message(F.text == "🚜 Престиж")
async def prestige_handler(message: Message):
    db = await get_db()
    user = await db.get_user(message.from_user.id)
    
    text = (
        f"🚜 <b>Система Престижа</b>\n\n"
        f"Текущий уровень: {user['prestige_level']}\n"
        f"Множитель дохода: x{user['prestige_multiplier']:.1f}\n\n"
        f"Собрано урожая: {user['total_harvested']}\n\n"
        f"Для повышения престижа нужно собрать больше урожая!"
    )
    
    await message.answer(text, parse_mode="HTML")

# Команда помощи
@router.message(Command("help"))
async def help_handler(message: Message):
    help_text = """📖 <b>Помощь по игре Lazy Farmer</b>

<b>Основные команды:</b>
/start - Начать игру / Главное меню
/help - Показать эту справку
/stats - Твоя статистика
/top - Топ игроков
/promo КОД - Активировать промокод

<b>Кнопки меню:</b>
🌾 Моя Ферма - Посмотреть грядки и собрать урожай
🏪 Магазин - Купить семена и улучшения
📦 Амбар - Твой инвентарь
🚜 Престиж - Информация о престиже

<b>Как играть:</b>
1. Нажми "🌾 Моя Ферма"
2. Выбери пустую грядку и посади культуру
3. Жди пока созреет (или используй удобрения)
4. Собирай урожай и получай монеты!
5. Заходи каждый день за бонусом

<b>Советы:</b>
• Чем дороже семена, тем больше прибыль
• Не забывай забирать ежедневный бонус
• Престиж увеличивает множитель дохода
• Используй промокоды для бонусов

Удачной игры! 🌾"""
    
    await message.answer(help_text, parse_mode="HTML", reply_markup=get_main_keyboard())

# Команда статистики
@router.message(Command("stats"))
async def stats_handler(message: Message):
    db = await get_db()
    user = await db.get_user(message.from_user.id)
    
    if not user:
        await message.answer("Сначала начни игру командой /start")
        return
    
    # Получаем количество собранного урожая
    total_earned = user['balance'] + (user['total_harvested'] * 10)  # Примерная формула
    
    stats_text = f"""📊 <b>Твоя статистика</b>

👤 Имя: {user['first_name']}
🆔 ID: {user['user_id']}

💰 Баланс: {user['balance']:,} 🪙
🌾 Собрано урожая: {user['total_harvested']}
🏆 Уровень престижа: {user['prestige_level']}
📈 Множитель: x{user['prestige_multiplier']:.1f}
🏙️ Уровень города: {user['city_level']}

Всего заработано: ~{total_earned:,} 🪙"""
    
    await message.answer(stats_text, parse_mode="HTML", reply_markup=get_main_keyboard())

# Команда промокода
@router.message(Command("promo"))
async def promo_handler(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "🎁 <b>Активация промокода</b>\n\n"
            "Использование: <code>/promo КОД</code>\n\n"
            "Пример: <code>/promo START2024</code>",
            parse_mode="HTML"
        )
        return
    
    code = args[1].upper()
    db = await get_db()
    
    result = await db.activate_promo(message.from_user.id, code)
    
    if result['success']:
        rewards_text = ""
        if 'coins' in result['rewards']:
            rewards_text += f"💰 {result['rewards']['coins']} монет\n"
        if 'items' in result['rewards']:
            for item, qty in result['rewards']['items'].items():
                rewards_text += f"📦 {item}: {qty} шт.\n"
        
        await message.answer(
            f"✅ <b>Промокод активирован!</b>\n\n"
            f"🎁 Награды:\n{rewards_text}",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"❌ {result['message']}",
            parse_mode="HTML"
        )

# Топ игроков
@router.message(Command("top"))
async def top_handler(message: Message):
    db = await get_db()
    
    # Получаем топ-10 по балансу
    rows = await db.fetchall(
        """SELECT first_name, balance, prestige_level, total_harvested 
           FROM users WHERE is_banned = 0 
           ORDER BY balance DESC LIMIT 10"""
    )
    
    if not rows:
        await message.answer("🏆 Пока нет игроков в топе!")
        return
    
    text_lines = ["🏆 <b>Топ-10 богачей</b>\n"]
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, row in enumerate(rows):
        name = row[0] or "Игрок"
        balance = row[1]
        prestige = row[2]
        text_lines.append(f"{medals[i]} {name} - {balance:,}🪙 (Престиж {prestige})")
    
    # Показываем место пользователя
    user = await db.get_user(message.from_user.id)
    if user:
        user_rank = await db.fetchone(
            """SELECT COUNT(*) + 1 FROM users 
               WHERE balance > ? AND is_banned = 0""",
            (user['balance'],)
        )
        if user_rank:
            text_lines.append(f"\n📍 Ты на {user_rank[0]} месте с {user['balance']:,}🪙")
    
    await message.answer("\n".join(text_lines), parse_mode="HTML", reply_markup=get_main_keyboard())

# Использование удобрений (ускорение роста)
@router.callback_query(F.data.startswith("fertilize_"))
async def fertilize_plot(callback: CallbackQuery):
    plot_num = int(callback.data.split("_")[1])
    db = await get_db()
    
    # Проверяем есть ли удобрения в инвентаре
    inventory = await db.get_inventory(callback.from_user.id)
    if 'fertilizer' not in inventory or inventory['fertilizer'] <= 0:
        await callback.answer("❌ У тебя нет удобрений! Купи в магазине.", show_alert=True)
        return
    
    # Получаем информацию о грядке
    plots = await db.get_plots(callback.from_user.id)
    plot = next((p for p in plots if p['number'] == plot_num), None)
    
    if not plot or plot['status'] != 'growing':
        await callback.answer("❌ На этой грядке ничего не растёт!", show_alert=True)
        return
    
    # Ускоряем рост на 50%
    await db.execute(
        """UPDATE plots SET planted_time = datetime(planted_time, '-30 seconds') 
           WHERE user_id = ? AND plot_number = ?""",
        (callback.from_user.id, plot_num), commit=True
    )
    
    # Уменьшаем количество удобрений
    await db.remove_inventory(callback.from_user.id, 'fertilizer', 1)
    
    await callback.answer("⚡ Удобрение применено! Рост ускорен на 30 секунд!")
    await show_farm(callback.from_user.id, callback.message)


# =================== КВЕСТЫ ===================

@router.message(F.text == "📜 Квесты")
async def quests_handler(message: Message):
    db = await get_db()
    quests = await db.get_daily_quests(message.from_user.id)
    
    if not quests:
        await message.answer("❌ Ошибка загрузки квестов!")
        return
    
    text_lines = ["📜 <b>Ежедневные квесты</b>\n"]
    
    for quest in quests:
        # Прогресс-бар
        progress_pct = min(100, (quest['progress'] / quest['target_count']) * 100)
        filled = int(progress_pct / 10)
        empty = 10 - filled
        progress_bar = "█" * filled + "░" * empty
        
        status = "✅" if quest['claimed'] else ("🎯" if quest['completed'] else "⏳")
        
        text_lines.append(
            f"{status} <b>{quest['description']}</b>\n"
            f"   {progress_bar} {quest['progress']}/{quest['target_count']}\n"
            f"   🎁 Награда: {quest['reward_coins']}🪙"
        )
        if quest['reward_items']:
            for item, qty in quest['reward_items'].items():
                text_lines.append(f"   📦 {item}: {qty}")
        text_lines.append("")
    
    # Кнопки для сбора наград
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    for quest in quests:
        if quest['completed'] and not quest['claimed']:
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"🎁 Забрать: {quest['description'][:20]}...",
                    callback_data=f"claim_quest_{quest['quest_id']}"
                )
            ])
    
    await message.answer(
        "\n".join(text_lines),
        parse_mode="HTML",
        reply_markup=keyboard if keyboard.inline_keyboard else None
    )

@router.callback_query(F.data.startswith("claim_quest_"))
async def claim_quest_reward(callback: CallbackQuery):
    quest_id = int(callback.data.split("_")[2])
    db = await get_db()
    
    result = await db.claim_quest_reward(callback.from_user.id, quest_id)
    
    if result['success']:
        rewards_text = f"💰 {result['coins']}🪙"
        if result['items']:
            for item, qty in result['items'].items():
                rewards_text += f", {item} x{qty}"
        
        await callback.answer(f"🎁 Получено: {rewards_text}!")
        await quests_handler(callback.message)
    else:
        await callback.answer(f"❌ {result['message']}", show_alert=True)


# =================== ДОСТИЖЕНИЯ ===================

@router.message(F.text == "🏆 Достижения")
async def achievements_handler(message: Message):
    db = await get_db()
    achievements = await db.get_achievements(message.from_user.id)
    
    if not achievements:
        await message.answer("❌ Ошибка загрузки достижений!")
        return
    
    text_lines = ["🏆 <b>Твои достижения</b>\n"]
    
    unlocked_count = sum(1 for a in achievements if a['unlocked'])
    text_lines.append(f"Разблокировано: {unlocked_count}/{len(achievements)}\n")
    
    for ach in achievements:
        status = "✅" if ach['unlocked'] else "🔒"
        text_lines.append(
            f"{status} {ach['icon']} <b>{ach['name']}</b>\n"
            f"   {ach['description']}\n"
            f"   🎁 Награда: {ach['reward_coins']}🪙"
        )
        if ach['reward_multiplier'] > 0:
            text_lines.append(f"   📈 +x{ach['reward_multiplier']:.1f} множитель")
        text_lines.append("")
    
    await message.answer("\n".join(text_lines), parse_mode="HTML")


# =================== ASCII ГРАФИКА ===================

def get_crop_ascii(crop_type: str, stage: str) -> str:
    """Возвращает ASCII-арт для растения на разных стадиях"""
    
    arts = {
        'corn_seed': {
            'seed': """🌱
     .
    /|\\
    """,
            'growing': """🌽
      |
     /|\\
    / | \\
      |
    """,
            'ready': """🌽
    🟡🟡🟡
    🟡🌽🟡
    🟡🟡🟡
      |
    """
        },
        'carrot_seed': {
            'seed': """🌱
     .
    """,
            'growing': """🥕
      🌿
     🌿🌿
    """,
            'ready': """🥕
      🌿
     🌿🌿
    🟠🟠🟠
    """
        },
        'default': {
            'seed': "🌱",
            'growing': "🌿",
            'ready': "✅"
        }
    }
    
    crop_arts = arts.get(crop_type, arts['default'])
    return crop_arts.get(stage, arts['default'][stage])


def format_growth_bar(remaining: int, total: int) -> str:
    """Создает прогресс-бар роста"""
    if total == 0:
        return "✅ Готово!"
    
    elapsed = total - remaining
    pct = max(0, min(100, (elapsed / total) * 100))
    
    filled = int(pct / 10)
    empty = 10 - filled
    
    bar = "█" * filled + "░" * empty
    return f"⏳ [{bar}] {int(pct)}%"


# Обновленная функция отображения фермы с ASCII-артом
async def show_farm_with_ascii(user_id: int, obj: Message | CallbackQuery):
    db = await get_db()
    user = await db.get_user(user_id)
    plots = await db.get_plots(user_id)
    
    city_name = "Деревня" if user['city_level'] == 0 else f"Город {user['city_level']}"
    text_lines = [
        f"🧑‍🌾 <b>Твоя Ферма ({city_name})</b>",
        f"💰 Баланс: {user['balance']:,}🪙 | Множитель: x{user['prestige_multiplier']:.1f}\n"
    ]
    
    # Проверяем сезонное событие
    event = await db.get_active_event()
    if event:
        from datetime import datetime
        time_left = event['end_date'] - datetime.now()
        hours_left = int(time_left.total_seconds() // 3600)
        text_lines.append(
            f"🎉 <b>{event['name']}</b> | x{event['multiplier']} награды\n"
            f"   Осталось: {hours_left}ч | {event['description']}\n"
        )
    
    # Грядки с ASCII
    for plot in plots:
        if plot["status"] == "empty":
            text_lines.append(f"\n🟫 <b>Грядка #{plot['number']}</b>: Пусто")
        elif plot["status"] == "growing":
            # Получаем общее время роста
            crop_info = await db.fetchone(
                "SELECT growth_time FROM shop_config WHERE item_code = ?",
                (plot['crop_type'],)
            )
            total_time = crop_info[0] if crop_info else 120
            
            ascii_art = get_crop_ascii(plot['crop_type'], 'growing')
            progress_bar = format_growth_bar(plot['remaining_time'], total_time)
            
            minutes = plot["remaining_time"] // 60
            seconds = plot["remaining_time"] % 60
            
            text_lines.append(
                f"\n{ascii_art}\n"
                f"🌱 <b>Грядка #{plot['number']}</b>: {plot['crop_type']}\n"
                f"   {progress_bar}\n"
                f"   ⏱️ Осталось: {minutes:02d}:{seconds:02d}"
            )
        else:  # ready
            ascii_art = get_crop_ascii(plot['crop_type'], 'ready')
            text_lines.append(
                f"\n{ascii_art}\n"
                f"✅ <b>Грядка #{plot['number']}</b>: {plot['crop_type']} ГОТОВО!\n"
                f"   🎁 Можно собирать!"
            )
    
    # Ежедневный бонус
    bonus = await db.get_daily_bonus(user_id)
    if bonus['available']:
        text_lines.append(f"\n🎁 <b>Ежедневный бонус готов!</b>")
    
    keyboard = get_farm_keyboard(plots)
    
    text = "\n".join(text_lines)
    
    if isinstance(obj, Message):
        await obj.answer(text, reply_markup=get_main_keyboard(), parse_mode="HTML")
        await obj.answer("Действия:", reply_markup=keyboard)
    else:
        await obj.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
