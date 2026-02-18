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
    
    # Проверка что пользователь существует
    if not user:
        text = "❌ Ошибка: пользователь не найден. Начни с /start"
        if isinstance(obj, Message):
            await obj.answer(text)
        else:
            await obj.message.edit_text(text)
        return
    
    plots = await db.get_plots(user_id)
    
    # Исправлено: правильная проверка для Деревни (city_level == 0)
    city_name = "Деревня" if user.get('city_level', 0) == 0 else f"Город {user.get('city_level', 0)}"
    text_lines = [
        f"🧑‍🌾 <b>Твоя Ферма ({city_name}):</b>\n",
        f"Баланс: 🪙 {user.get('balance', 0):,}\n",
        f"Множитель дохода: x{user.get('prestige_multiplier', 1.0):.1f}"
    ]
    
    # Ежедневный бонус
    try:
        bonus = await db.get_daily_bonus(user_id)
        streak = bonus.get('streak', 1) if bonus else 1
        streak_text = f"Заходишь {streak} {'день' if streak == 1 else 'дня подряд'}. Завтра: +{bonus.get('coins', 50) if bonus else 50} монет."
        if bonus and bonus.get('available', False):
            text_lines.append(f"\n🎁 <b>Ежедневный бонус:</b> {streak_text}")
        else:
            text_lines.append(f"\n🎁 Ежедневный бонус: {bonus.get('message', streak_text) if bonus else streak_text}")
    except Exception as e:
        import logging
        logging.error(f"Error getting daily bonus: {e}")
        text_lines.append(f"\n🎁 Ежедневный бонус: ошибка загрузки")
    
    # Грядки
    if not plots:
        text_lines.append("\n🟫 Пока нет грядок!")
    else:
        # Получаем информацию о культурах для иконок
        crop_icons = {}
        for plot in plots:
            if plot.get("crop_type") and plot["crop_type"] not in crop_icons:
                try:
                    crop_info = await db.fetchone(
                        "SELECT item_icon FROM shop_config WHERE item_code = ?",
                        (plot["crop_type"],)
                    )
                    crop_icons[plot["crop_type"]] = crop_info[0] if crop_info and crop_info[0] else '🌱'
                except Exception:
                    crop_icons[plot["crop_type"]] = '🌱'

        for plot in plots:
            plot_number = plot.get('number', '?')
            if plot.get("status") == "empty":
                text_lines.append(f"🟫 Грядка #{plot_number}: Пусто")
            elif plot.get("status") == "growing":
                icon = crop_icons.get(plot.get("crop_type", ""), "🌱")
                minutes = plot.get("remaining_time", 0) // 60
                seconds = plot.get("remaining_time", 0) % 60
                time_str = f"{minutes:02d}:{seconds:02d}"
                crop_type = plot.get('crop_type', '???')
                text_lines.append(f"{icon} Грядка #{plot_number}: {crop_type} (⬆️ Созреет через {time_str})")
            elif plot.get("status") == "ready":
                icon = crop_icons.get(plot.get("crop_type", ""), "🌱")
                crop_type = plot.get('crop_type', '???')
                text_lines.append(f"{icon} Грядка #{plot_number}: {crop_type} (✅ ГОТОВО!)")
    
    keyboard = get_farm_keyboard(plots) if plots else None
    
    if isinstance(obj, Message):
        await obj.answer("\n".join(text_lines), reply_markup=get_main_keyboard(), parse_mode="HTML")
        if keyboard:
            await obj.answer("Действия:", reply_markup=keyboard)
    else:
        await obj.message.edit_text("\n".join(text_lines), reply_markup=keyboard, parse_mode="HTML")

@router.message(F.text == "🌾 Моя Ферма")
async def farm_handler(message: Message):
    await show_farm(message.from_user.id, message)

@router.callback_query(F.data.startswith("plant_"))
async def plant_crop(callback: CallbackQuery, state: FSMContext):
    try:
        plot_num = int(callback.data.split("_")[1])
    except (IndexError, ValueError):
        await callback.answer("❌ Неверный формат данных!", show_alert=True)
        return
    
    db = await get_db()
    
    # Проверка что пользователь существует
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Ошибка: пользователь не найден!", show_alert=True)
        return
    
    # Проверка что грядка пустая
    plots = await db.get_plots(callback.from_user.id)
    if not plots:
        await callback.answer("❌ Ошибка: грядки не найдены!", show_alert=True)
        return
    
    plot = next((p for p in plots if p['number'] == plot_num), None)
    if not plot or plot['status'] != 'empty':
        await callback.answer("❌ Эта грядка уже занята!", show_alert=True)
        return
    
    crops = await db.get_shop_items("seed")
    
    # Фильтруем доступные по уровню семена
    user_level = user.get('city_level', 1)
    available_crops = [c for c in crops if c.get('required_level', 1) <= user_level and c.get('is_active', True)]
    
    if not available_crops:
        await callback.answer("❌ Нет доступных семян для твоего уровня!", show_alert=True)
        return
    
    buttons = []
    for crop in available_crops:
        # Дополнительная проверка что культура активна
        if crop.get('is_active', True):
            buttons.append(InlineKeyboardButton(
                text=f"{crop.get('icon', '🌱')} {crop.get('name', '???')} ({crop.get('buy_price', 0)}🪙)",
                callback_data=f"buy_plant_{plot_num}_{crop['item_code']}"
            ))
    
    # Проверка что кнопки не пустые перед созданием клавиатуры
    if not buttons:
        await callback.answer("❌ Нет доступных семян!", show_alert=True)
        return
    
    # Формируем клавиатуру без пустых строк
    keyboard_rows = []
    for i in range(0, len(buttons), 2):
        row = buttons[i:i+2]
        if row:  # Добавляем только непустые строки
            keyboard_rows.append(row)
    
    # Добавляем кнопку назад
    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад к грядкам", callback_data="back_farm")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
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
    # Парсинг callback_data с обработкой ошибок
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer("❌ Неверный формат данных!", show_alert=True)
        return
    
    try:
        plot_num = int(parts[2])
        item_code = parts[3]
    except (ValueError, IndexError):
        await callback.answer("❌ Неверный формат данных!", show_alert=True)
        return
    
    db = await get_db()
    
    # Получаем данные о культуре из БД
    crops = await db.get_shop_items("seed")
    crop = next((c for c in crops if c["item_code"] == item_code), None)
    
    if not crop:
        await callback.answer("❌ Ошибка: культура не найдена!", show_alert=True)
        return
    
    # Проверка что культура активна
    if not crop.get('is_active', True):
        await callback.answer("❌ Эти семена временно недоступны!", show_alert=True)
        return
    
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Ошибка: пользователь не найден!", show_alert=True)
        return
    
    # Проверка баланса
    buy_price = crop.get('buy_price', 0)
    if user.get('balance', 0) < buy_price:
        await callback.answer(f"❌ Недостаточно монет! Нужно {buy_price}🪙", show_alert=True)
        return
    
    # Проверка уровня
    user_level = user.get('city_level', 1)
    required_level = crop.get('required_level', 1)
    if user_level < required_level:
        await callback.answer(f"❌ Требуется уровень {required_level}!", show_alert=True)
        return
    
    # Проверка что грядка пустая (двойная проверка)
    plots = await db.get_plots(callback.from_user.id)
    plot = next((p for p in plots if p['number'] == plot_num), None)
    if not plot or plot.get('status') != 'empty':
        await callback.answer("❌ Грядка уже занята!", show_alert=True)
        return
    
    # Транзакционная операция: сначала проверяем баланс, потом списываем и сажаем
    try:
        # Проверяем и списываем деньги в одной транзакции
        new_balance = await db.update_balance(callback.from_user.id, -buy_price)
        if new_balance is None:
            await callback.answer("❌ Ошибка списания средств! Попробуй снова.", show_alert=True)
            return
        
        # Сажаем культуру
        growth_time = crop.get("growth_time", 120)
        await db.plant_crop(callback.from_user.id, plot_num, item_code, growth_time)
        
        # Логирование операции
        try:
            await db.log_economy(
                callback.from_user.id,
                'spend',
                'coins',
                buy_price,
                new_balance,
                'plant',
                item_code,
                f"Посадка {crop.get('name', item_code)} на грядку #{plot_num}"
            )
        except Exception as log_error:
            import logging
            logging.error(f"Error logging economy: {log_error}")
        
    except Exception as e:
        # При ошибке пробуем вернуть деньги
        try:
            await db.update_balance(callback.from_user.id, buy_price)
        except:
            pass
        import logging
        logging.error(f"Error in buy_plant: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:80]}!", show_alert=True)
        return
    
    # Обновляем квесты
    try:
        await db.execute(
            "UPDATE users SET total_planted = total_planted + 1 WHERE user_id = ?",
            (callback.from_user.id,), commit=True
        )
        await db.update_quest_progress(callback.from_user.id, 'plant', 1)
    except Exception as e:
        import logging
        logging.error(f"Error updating quests: {e}")

    # ===== ПРОВЕРКА АЧИВОК =====
    try:
        completed_achs = await db.check_and_update_achievements(
            callback.from_user.id, "plant", count=1
        )

        # Проверяем трату монет для финансовых ачивок
        spend_achs = await db.check_and_update_achievements(
            callback.from_user.id, "spend", count=buy_price
        )
        completed_achs.extend(spend_achs)

        # Отправляем уведомления о новых ачивках
        for ach in completed_achs:
            rewards_text = f"{ach.get('reward_coins', 0):,}🪙"
            if ach.get('reward_gems', 0) > 0:
                rewards_text += f" + {ach['reward_gems']}💎"
            
            await callback.message.answer(
                f"🎉 <b>НОВОЕ ДОСТИЖЕНИЕ!</b>\n\n"
                f"{ach.get('icon', '🏆')} <b>{ach.get('name', '???')}</b>\n"
                f"🎁 Награда: {rewards_text}\n\n"
                f"🏆 <b>Мои ачивки</b> - чтобы забрать награду!",
                parse_mode="HTML"
            )
    except Exception as e:
        import logging
        logging.error(f"Error checking achievements: {e}")
    
    crop_icon = crop.get('icon', '🌱')
    crop_name = crop.get('name', item_code)
    await callback.answer(f"✅ Посажено {crop_icon} {crop_name}!")
    await show_farm(callback.from_user.id, callback.message)
    await state.clear()


# Сбор урожая
@router.callback_query(F.data == "harvest_all")
async def harvest_all(callback: CallbackQuery):
    db = await get_db()
    
    # Получаем данные в одной транзакции
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Ошибка: пользователь не найден!", show_alert=True)
        return
    
    # Проверяем сезонное событие
    event = await db.get_active_event()
    multiplier = 1.0
    
    if event and event.get('is_active', False):
        multiplier = event.get('multiplier', 1.0)
        if multiplier <= 0 or multiplier > 10:  # Защита от некорректных значений
            multiplier = 1.0
    
    # Собираем урожай (внутри происходит сбор и возврат информации)
    result = await db.harvest_plots(callback.from_user.id, multiplier)
    
    if not result or not result.get('success', False):
        await callback.answer("❌ Нет готовых грядок!")
        await show_farm(callback.from_user.id, callback.message)
        return
    
    total = result.get('total', 0)
    ready_count = result.get('harvested_count', 0)
    ready_crops = result.get('crops', [])
    
    if total <= 0 or ready_count <= 0:
        await callback.answer("❌ Нет готовых грядок!")
        await show_farm(callback.from_user.id, callback.message)
        return
    
    # Проверяем что ready_count совпадает с количеством культур
    if len(ready_crops) != ready_count:
        import logging
        logging.warning(f"Mismatch: ready_crops count {len(ready_crops)} != ready_count {ready_count}")
    
    # Формируем текст бонуса
    bonus_text = ""
    if event and multiplier > 1.0:
        bonus = int(total - (total / multiplier))
        if bonus > 0:
            bonus_text = f" (включая бонус события +{bonus}🪙)"
    
    # Обновляем квесты (объединённый вызов с пакетной обработкой)
    try:
        if ready_crops:
            # Используем пакетное обновление квестов
            await db.update_quest_progress_batch(
                callback.from_user.id, 
                'harvest', 
                ready_crops
            )
            # Обновляем общий квест
            await db.update_quest_progress(callback.from_user.id, 'harvest', ready_count)

        # Обновляем событие
        if event and event.get('is_active', False):
            try:
                await db.update_event_score(callback.from_user.id, total)
            except Exception as e:
                import logging
                logging.error(f"Error updating event score: {e}")
    except Exception as e:
        import logging
        logging.error(f"Error updating quests: {e}")
    
    # ===== ПРОВЕРКА АЧИВОК =====
    completed_achs = []
    try:
        harvest_achs = await db.check_and_update_achievements(
            callback.from_user.id, "harvest", count=ready_count
        )
        completed_achs.extend(harvest_achs)
        
        # Проверяем заработок монет
        earn_achs = await db.check_and_update_achievements(
            callback.from_user.id, "earn", count=total
        )
        completed_achs.extend(earn_achs)
        
        # Отправляем уведомления о новых ачивках
        for ach in completed_achs:
            rewards_text = f"{ach.get('reward_coins', 0):,}🪙"
            if ach.get('reward_gems', 0) > 0:
                rewards_text += f" + {ach['reward_gems']}💎"
            
            await callback.message.answer(
                f"🎉 <b>НОВОЕ ДОСТИЖЕНИЕ!</b>\n\n"
                f"{ach.get('icon', '🏆')} <b>{ach.get('name', '???')}</b>\n"
                f"🎁 Награда: {rewards_text}\n\n"
                f"🏆 <b>Мои ачивки</b> - чтобы забрать награду!",
                parse_mode="HTML"
            )
    except Exception as e:
        import logging
        logging.error(f"Error checking achievements: {e}")
    
    await callback.answer(f"✅ Собрано {ready_count} грядок на {total}🪙{bonus_text}!")
    await show_farm(callback.from_user.id, callback.message)

# Ежедневный бонус
@router.callback_query(F.data == "claim_daily")
async def claim_daily(callback: CallbackQuery):
    db = await get_db()
    
    # Получаем информацию о бонусе до получения (кэшируем)
    bonus_info = await db.get_daily_bonus(callback.from_user.id)
    
    # Проверяем что bonus_info валиден
    if not bonus_info:
        await callback.answer("❌ Ошибка загрузки бонуса!", show_alert=True)
        await show_farm(callback.from_user.id, callback.message)
        return
    
    if not bonus_info.get('available', False):
        await callback.answer("❌ Бонус уже получен сегодня!", show_alert=True)
        await show_farm(callback.from_user.id, callback.message)
        return
    
    # Получаем бонус
    result = await db.claim_daily_bonus(callback.from_user.id)
    
    if not result or not result.get('success', False):
        await callback.answer("❌ Ошибка получения бонуса!", show_alert=True)
        await show_farm(callback.from_user.id, callback.message)
        return
    
    # Используем кэшированные данные о бонусе
    streak = bonus_info.get('streak', 1)
    if streak is None:
        streak = 1
    
    coins = result.get('coins', 0)
    items = result.get('items', {})
    
    # Проверяем что награда действительно выдана
    if coins <= 0 and not items:
        await callback.answer("❌ Ошибка: награда не выдана!", show_alert=True)
        return
    
    # ===== ПРОВЕРКА АЧИВОК =====
    try:
        completed_achs = await db.check_and_update_achievements(
            callback.from_user.id, "streak_days", count=streak
        )
        
        # Отправляем уведомления о новых ачивках
        for ach in completed_achs:
            rewards_text = f"{ach.get('reward_coins', 0):,}🪙"
            if ach.get('reward_gems', 0) > 0:
                rewards_text += f" + {ach['reward_gems']}💎"
            
            await callback.message.answer(
                f"🎉 <b>НОВОЕ ДОСТИЖЕНИЕ!</b>\n\n"
                f"{ach.get('icon', '🏆')} <b>{ach.get('name', '???')}</b>\n"
                f"🎁 Награда: {rewards_text}\n\n"
                f"🏆 <b>Мои ачивки</b> - чтобы забрать награду!",
                parse_mode="HTML"
            )
    except Exception as e:
        import logging
        logging.error(f"Error checking achievements: {e}")
    
    # Формируем текст награды
    reward_text = f"{coins}🪙"
    if items:
        for item, qty in items.items():
            reward_text += f", {item} x{qty}"
    
    await callback.answer(f"🎁 Бонус получен! +{reward_text}")
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
    
    if event and event.get('is_active', False):
        try:
            from datetime import datetime, timezone
            end_date = event.get('end_date')
            
            if end_date:
                # Обработка разных форматов даты
                if isinstance(end_date, str):
                    try:
                        # Пробуем разные форматы
                        if 'T' in end_date:
                            end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                        else:
                            end_date = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
                    except (ValueError, AttributeError):
                        end_date = None
                
                if end_date:
                    # Убеждаемся что datetime имеет timezone
                    if end_date.tzinfo is None:
                        now = datetime.now()
                    else:
                        now = datetime.now(end_date.tzinfo)
                    
                    time_left = end_date - now
                    hours_left = int(time_left.total_seconds() // 3600)
                    
                    # Защита от отрицательных значений
                    if hours_left > 0:
                        multiplier = event.get('multiplier', 1.0)
                        event_name = event.get('name', 'Событие')
                        text = (
                            f"🏪 <b>Магазин</b>\n\n"
                            f"🎉 <b>{event_name}</b> активно!\n"
                            f"💰 x{multiplier:.1f} награды за урожай!\n"
                            f"⏰ Осталось: {hours_left} часов\n\n"
                            f"Выбери категорию:"
                        )
        except Exception as e:
            import logging
            logging.warning(f"Error parsing event date: {e}")
    
    await message.answer(
        text,
        reply_markup=get_shop_categories(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("shop_"))
async def shop_category(callback: CallbackQuery):
    category = callback.data.replace("shop_", "")

    # Валидация категории
    valid_categories = ['seed', 'boost', 'decor', 'tool']
    if category not in valid_categories:
        await callback.answer("❌ Неверная категория!")
        return
    
    db = await get_db()
    
    # Получаем обычные товары
    items = await db.get_shop_items(category)
    
    # Добавляем сезонные товары если есть событие
    event = await db.get_active_event()
    multiplier = 1.0
    
    if event and event.get('is_active', False) and category == 'seed':
        try:
            seasonal_items = await db.fetchall(
                """SELECT item_code, item_name, item_icon, buy_price, sell_price, growth_time 
                   FROM shop_config 
                   WHERE category = ? AND is_seasonal = 1 AND season = ?""",
                (category, event.get('season', 'summer'))
            )
            # Преобразуем в тот же формат (row - tuple, индексы 0-5)
            for row in seasonal_items:
                items.append({
                    "item_code": row[0],
                    "name": row[1],
                    "icon": row[2],
                    "buy_price": row[3],
                    "sell_price": row[4],
                    "growth_time": row[5],
                    "category": category,
                    "is_seasonal": True
                })
            multiplier = event.get('multiplier', 1.0)
        except Exception as e:
            import logging
            logging.error(f"Error loading seasonal items: {e}")
    
    if not items:
        await callback.answer("📭 Категория пуста!")
        return
    
    text_lines = [f"🏪 <b>{category.capitalize()}</b>\n"]
    
    if event and event.get('is_active', False) and category == 'seed':
        text_lines.append(f"🎉 {event.get('name', 'Событие')} - x{multiplier} награды!\n")
    
    for item in items:
        seasonal_mark = "🌟 " if item.get('is_seasonal') else ""
        icon = item.get('icon', '🌱')
        name = item.get('name', '???')
        text_lines.append(f"{seasonal_mark}{icon} <b>{name}</b>")
        
        buy_price = item.get('buy_price', 0)
        if buy_price > 0:
            text_lines.append(f"   💰 Покупка: {buy_price}🪙")
        
        sell_price = item.get('sell_price', 0)
        if sell_price > 0:
            final_sell_price = int(sell_price * multiplier) if multiplier > 1.0 else sell_price
            text_lines.append(f"   💵 Продажа: {final_sell_price}🪙")
        
        growth_time = item.get('growth_time', 0)
        if growth_time > 0:
            minutes = growth_time // 60
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
    
    # Получаем информацию о предметах из магазина
    all_items = await db.get_shop_items()

    # Создаем словарь с информацией о предметах
    items_info = {item['item_code']: item for item in all_items}

    # Разделяем по категориям
    seeds = {}
    fertilizers = {}
    upgrades = {}
    other = {}

    total_value = 0

    for item_code, quantity in inventory.items():
        if quantity <= 0:
            continue

        item = items_info.get(item_code, {})
        category = item.get('category', 'other')
        icon = item.get('icon', '📦')
        name = item.get('name', item_code)
        sell_price = item.get('sell_price', 0)

        # Вычисляем стоимость
        item_value = sell_price * quantity
        total_value += item_value

        item_entry = {
            'name': name,
            'icon': icon,
            'quantity': quantity,
            'value': item_value
        }

        if category == 'seed':
            seeds[item_code] = item_entry
        elif category == 'fertilizer':
            fertilizers[item_code] = item_entry
        elif category == 'upgrade':
            upgrades[item_code] = item_entry
        else:
            other[item_code] = item_entry

    # Формируем текст
    text_lines = [f"📦 <b>Твой Амбар</b>\n"]
    text_lines.append(f"💰 Общая стоимость: {total_value:,}🪙\n")

    if seeds:
        text_lines.append("🌱 <b>Семена:</b>")
        for item_code, item in seeds.items():
            text_lines.append(f"   {item['icon']} {item['name']}: {item['quantity']} шт. (~{item['value']:,}🪙)")
        text_lines.append("")

    if fertilizers:
        text_lines.append("🧪 <b>Удобрения:</b>")
        for item_code, item in fertilizers.items():
            text_lines.append(f"   {item['icon']} {item['name']}: {item['quantity']} шт. (~{item['value']:,}🪙)")
        text_lines.append("")

    if upgrades:
        text_lines.append("🚜 <b>Улучшения:</b>")
        for item_code, item in upgrades.items():
            text_lines.append(f"   {item['icon']} {item['name']}: {item['quantity']} шт.")
        text_lines.append("")

    if other:
        text_lines.append("📦 <b>Другое:</b>")
        for item_code, item in other.items():
            text_lines.append(f"   {item['icon']} {item['name']}: {item['quantity']} шт.")

    await message.answer("\n".join(text_lines), parse_mode="HTML")

# Престиж
@router.message(F.text == "🚜 Престиж")
async def prestige_handler(message: Message):
    db = await get_db()
    user = await db.get_user(message.from_user.id)
    
    # Требования для уровней престижа
    prestige_requirements = {
        1: (0, 1.0, "Новичок"),
        2: (100, 1.1, "Фермер"),
        3: (300, 1.2, "Опытный фермер"),
        4: (600, 1.4, "Мастер"),
        5: (1000, 1.6, "Эксперт"),
        6: (1500, 1.8, "Легенда"),
        7: (2500, 2.0, "Великий фермер"),
        8: (4000, 2.3, "Грандмастер"),
        9: (6000, 2.6, "Фермер-бог"),
        10: (10000, 3.0, "Божественный фермер")
    }

    current_level = user['prestige_level']
    current_harvested = user['total_harvested']

    # Определяем следующий уровень
    next_level = current_level + 1
    if next_level in prestige_requirements:
        next_harvest, next_multiplier, next_title = prestige_requirements[next_level]
        remaining = next_harvest - current_harvested
        progress_pct = min(100, (current_harvested / next_harvest) * 100)

        # Прогресс-бар
        filled = int(progress_pct / 10)
        empty = 10 - filled
        progress_bar = "█" * filled + "░" * empty
        
        next_level_text = (
            f"\n📈 <b>Следующий уровень: {next_level} - {next_title}</b>\n"
            f"   {progress_bar} {int(progress_pct)}%\n"
            f"   Осталось собрать: {remaining:,} урожая\n"
            f"   Новый множитель: x{next_multiplier:.1f}"
        )
    else:
        next_level_text = "\n🎉 <b>Ты достиг максимального уровня престижа!</b>"

    # Текущий уровень
    if current_level in prestige_requirements:
        _, _, current_title = prestige_requirements[current_level]
    else:
        current_title = "Неизвестный"

    text = (
        f"🚜 <b>Система Престижа</b>\n\n"
        f"🏆 <b>Текущий уровень: {current_level} - {current_title}</b>\n"
        f"📊 Множитель дохода: x{user['prestige_multiplier']:.1f}\n"
        f"🌾 Собрано урожая: {user['total_harvested']:,}\n"
        f"{next_level_text}\n\n"
        f"💡 <b>Уровни престижа:</b>\n"
    )

    # Показываем таблицу уровней
    for level, (harvest, multiplier, title) in prestige_requirements.items():
        if level <= current_level:
            status = "✅"
        elif level == next_level:
            status = "🎯"
        else:
            status = "🔒"

        text += f"{status} Ур.{level} - {title}: x{multiplier:.1f} ({harvest:,})\n"

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

# Кнопка помощи
@router.message(F.text == "❓ Помощь")
async def help_button_handler(message: Message):
    await help_handler(message)

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
    
    # Валидация формата промокода
    if len(code) < 4 or len(code) > 20:
        await message.answer(
            "❌ <b>Неверный формат промокода!</b>\n\n"
            "Промокод должен содержать от 4 до 20 символов.",
            parse_mode="HTML"
        )
        return
    
    # Проверка на допустимые символы (только буквы и цифры)
    if not code.replace('-', '').replace('_', '').isalnum():
        await message.answer(
            "❌ <b>Неверный формат промокода!</b>\n\n"
            "Промокод может содержать только буквы, цифры, дефис и нижнее подчеркивание.",
            parse_mode="HTML"
        )
        return
    
    db = await get_db()
    
    result = await db.activate_promo(message.from_user.id, code)
    
    if result.get('success', False):
        rewards = result.get('rewards', {})
        rewards_text = ""
        
        if 'coins' in rewards:
            coins = rewards['coins']
            if isinstance(coins, (int, float)) and coins > 0:
                rewards_text += f"💰 {int(coins)} монет\n"
        
        if 'items' in rewards and isinstance(rewards['items'], dict):
            for item, qty in rewards['items'].items():
                if isinstance(qty, int) and qty > 0:
                    rewards_text += f"📦 {item}: {qty} шт.\n"
        
        if not rewards_text:
            rewards_text = "Нет наград\n"
        
        await message.answer(
            f"✅ <b>Промокод активирован!</b>\n\n"
            f"🎁 Награды:\n{rewards_text}",
            parse_mode="HTML"
        )
    else:
        error_message = result.get('message', 'Неизвестная ошибка')
        await message.answer(
            f"❌ {error_message}",
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
        try:
            user_rank = await db.fetchone(
                """SELECT COUNT(*) + 1 FROM users 
                   WHERE balance > ? AND is_banned = 0""",
                (user.get('balance', 0),)
            )
            if user_rank and user_rank[0]:
                text_lines.append(f"\n📍 Ты на {user_rank[0]} месте с {user.get('balance', 0):,}🪙")
        except Exception as e:
            import logging
            logging.error(f"Error getting user rank: {e}")
    
    await message.answer("\n".join(text_lines), parse_mode="HTML", reply_markup=get_main_keyboard())

# Использование удобрений (ускорение роста)
@router.callback_query(F.data.startswith("fertilize_"))
async def fertilize_plot(callback: CallbackQuery):
    try:
        plot_num = int(callback.data.split("_")[1])
    except (IndexError, ValueError):
        await callback.answer("❌ Неверный формат данных!", show_alert=True)
        return
    
    db = await get_db()
    
    # Проверяем есть ли удобрения в инвентаре
    inventory = await db.get_inventory(callback.from_user.id)
    if not inventory or inventory.get('fertilizer', 0) <= 0:
        await callback.answer("❌ У тебя нет удобрений! Купи в магазине.", show_alert=True)
        return
    
    # Получаем информацию о грядке
    plots = await db.get_plots(callback.from_user.id)
    if not plots:
        await callback.answer("❌ Ошибка загрузки грядок!", show_alert=True)
        return
    
    plot = next((p for p in plots if p['number'] == plot_num), None)
    
    if not plot:
        await callback.answer("❌ Грядка не найдена!", show_alert=True)
        return
    
    if plot.get('status') != 'growing':
        await callback.answer("❌ На этой грядке ничего не растёт!", show_alert=True)
        return
    
    # Проверяем что удобрение ещё не применено
    if plot.get('fertilized', False):
        await callback.answer("❌ На эту грядку уже применено удобрение!", show_alert=True)
        return
    
    # Ускоряем рост на 50% от оставшегося времени (минимум 30 секунд)
    remaining_time = plot.get('remaining_time', 0)
    if remaining_time <= 0:
        await callback.answer("❌ Растение уже созрело!", show_alert=True)
        return
    
    # Ускорение: 50% от оставшегося времени, минимум 30 секунд, максимум 300 секунд
    acceleration = max(30, min(300, int(remaining_time * 0.5)))

    try:
        # Применяем ускорение и помечаем как удобренную
        await db.execute(
            """UPDATE plots
               SET planted_time = datetime(planted_time, '-{} seconds'),
                   fertilized = 1
               WHERE user_id = ? AND plot_number = ?""".format(acceleration),
            (callback.from_user.id, plot_num), commit=True
        )

        # Уменьшаем количество удобрений
        await db.remove_inventory(callback.from_user.id, 'fertilizer', 1)

        # Получаем новое время созревания
        new_plots = await db.get_plots(callback.from_user.id)
        new_plot = next((p for p in new_plots if p['number'] == plot_num), None)
        new_remaining = new_plot.get('remaining_time', 0) if new_plot else 0
        
        # Проверяем что грядка всё ещё растёт
        if new_plot and new_plot.get('status') == 'growing':
            minutes = new_remaining // 60
            seconds = new_remaining % 60
            await callback.answer(
                f"⚡ Удобрение применено! Рост ускорен на {acceleration} сек. "
                f"Осталось: {minutes:02d}:{seconds:02d}"
            )
        else:
            await callback.answer(
                f"⚡ Удобрение применено! Рост ускорен на {acceleration} сек. "
                f"Растение созрело!"
            )
    except Exception as e:
        import logging
        logging.error(f"Error fertilizing plot: {e}")
        await callback.answer("❌ Ошибка применения удобрения!", show_alert=True)
        return
    
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
    try:
        quest_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("❌ Неверный формат данных!", show_alert=True)
        return
    
    db = await get_db()
    
    # Проверяем что квест действительно выполнен перед выдачей награды
    quest = await db.fetchone(
        """SELECT quest_id, completed, claimed FROM user_quests 
           WHERE user_id = ? AND quest_id = ?""",
        (callback.from_user.id, quest_id)
    )

    if not quest:
        await callback.answer("❌ Квест не найден!", show_alert=True)
        return
    
    if not quest['completed']:
        await callback.answer("❌ Квест ещё не выполнен!", show_alert=True)
        return
    
    if quest['claimed']:
        await callback.answer("❌ Награда уже получена!", show_alert=True)
        return
    
    result = await db.claim_quest_reward(callback.from_user.id, quest_id)
    
    if result.get('success', False):
        rewards_text = f"💰 {result.get('coins', 0)}🪙"
        items = result.get('items', {})
        if items and isinstance(items, dict):
            for item, qty in items.items():
                rewards_text += f", {item} x{qty}"
        
        await callback.answer(f"🎁 Получено: {rewards_text}!")
        # Перерисовываем список квестов (используем callback.message)
        await quests_handler(callback.message)
    else:
        error_message = result.get('message', 'Неизвестная ошибка')
        await callback.answer(f"❌ {error_message}", show_alert=True)


# =================== ДОСТИЖЕНИЯ (НОВАЯ СИСТЕМА) ===================

@router.message(F.text == "🏆 Достижения")
async def achievements_handler(message: Message):
    """Главное меню достижений"""
    db = await get_db()
    stats = await db.get_achievement_stats(message.from_user.id)
    
    # Проверяем невостребованные награды
    pending = await db.get_pending_rewards(message.from_user.id)
    
    text_lines = [
        "🏆 <b>Достижения</b>\n",
        f"📊 Прогресс: {stats['completed']}/{stats['total']} ачивок"
    ]
    
    if stats['total_coins'] > 0 or stats['total_gems'] > 0:
        rewards_text = f"🏅 Всего наград: {stats['total_coins']:,}🪙"
        if stats['total_gems'] > 0:
            rewards_text += f" + {stats['total_gems']}💎"
        text_lines.append(rewards_text)
    
    if pending:
        text_lines.append(f"\n🎁 <b>Ожидают награды: {len(pending)}</b>")
    
    text_lines.append("\n<b>Категории:</b>")
    
    # Формируем кнопки категорий
    category_buttons = []
    row = []
    
    for cat in stats['categories']:
        cat_text = f"{cat['icon']} {cat['name']} ({cat['completed']}/{cat['total']})"
        text_lines.append(cat_text)
        
        button = InlineKeyboardButton(
            text=f"{cat['icon']} {cat['name']}",
            callback_data=f"ach_cat_{cat['id']}"
        )
        row.append(button)
        if len(row) == 2:
            category_buttons.append(row)
            row = []
    
    if row:
        category_buttons.append(row)
    
    # Добавляем кнопки действий
    action_buttons = [
        [InlineKeyboardButton(text="📋 Все достижения", callback_data="ach_all_0")],
        [InlineKeyboardButton(text="🏅 Лента достижений", callback_data="ach_history")],
    ]
    
    if pending:
        action_buttons.insert(0, [InlineKeyboardButton(
            text=f"🎁 Забрать награды ({len(pending)})", 
            callback_data="ach_claim_all"
        )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=category_buttons + action_buttons)
    
    await message.answer("\n".join(text_lines), reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("ach_cat_"))
async def achievements_by_category(callback: CallbackQuery):
    """Просмотр ачивок по категории"""
    category_id = callback.data.replace("ach_cat_", "")
    
    db = await get_db()
    achievements = await db.get_achievements_by_category(callback.from_user.id, category_id)
    categories = await db.get_achievement_categories()
    
    cat_info = next((c for c in categories if c['id'] == category_id), None)
    cat_name = cat_info['name'] if cat_info else category_id
    cat_icon = cat_info['icon'] if cat_info else '🏆'
    
    # Считаем прогресс
    total = len(achievements)
    completed = sum(1 for a in achievements if a['completed'])
    
    text_lines = [f"{cat_icon} <b>{cat_name}</b>\n", f"Прогресс: {completed}/{total}\n"]
    
    keyboard_rows = []
    
    for ach in achievements:
        if ach.get('is_locked'):
            # Секретная ачивка
            text_lines.append(
                f"━━━━━━━━━━━━━━━━\n"
                f"🔒 <b>???</b>\n"
                f"Секретное достижение\n"
                f"🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥 (???/???)"
            )
        else:
            # Прогресс-бар
            progress_pct = min(100, (ach['progress'] / ach['requirement_count']) * 100) if ach['requirement_count'] > 0 else 0
            filled = int(progress_pct / 10)
            empty = 10 - filled
            progress_bar = "🟩" * filled + "⬜" * empty
            
            # Статус
            if ach['completed']:
                if ach['reward_claimed']:
                    status = "✅"
                    status_text = "Получена"
                else:
                    status = "🎁"
                    status_text = "Награда доступна!"
            else:
                status = "⏳"
                status_text = f"{ach['progress']:,}/{ach['requirement_count']:,}"
            
            text_lines.append(
                f"━━━━━━━━━━━━━━━━\n"
                f"{status} <b>{ach['name']}</b>\n"
                f"{ach['description']}\n"
                f"{progress_bar}\n"
                f"{status_text}"
            )
    
            # Кнопка для забора награды или просмотра
            if ach['completed'] and not ach['reward_claimed']:
                keyboard_rows.append([InlineKeyboardButton(
                    text=f"🎁 Забрать: {ach['name'][:20]}",
                    callback_data=f"ach_reward_{ach['id']}"
                )])
            else:
                keyboard_rows.append([InlineKeyboardButton(
                    text=f"ℹ️ {ach['name'][:25]}",
                    callback_data=f"ach_view_{ach['id']}"
                )])
    
    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_achievements")])
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "back_achievements")
async def back_to_achievements(callback: CallbackQuery):
    """Возврат к главному меню ачивок"""
    # Симулируем нажатие кнопки достижений
    from aiogram.types import Message
    msg = callback.message
    msg.from_user = callback.from_user
    await achievements_handler(msg)


@router.callback_query(F.data.startswith("ach_view_"))
async def view_achievement_detail(callback: CallbackQuery):
    """Детальный просмотр ачивки"""
    ach_id = int(callback.data.replace("ach_view_", ""))
    
    db = await get_db()
    pa = await db.get_player_achievement(callback.from_user.id, ach_id)
    
    if not pa:
        # Пробуем получить просто инфу об ачивке
        ach = await db.get_achievement_by_id(ach_id)
        if not ach:
            await callback.answer("Ачивка не найдена!")
            return
        # Показываем без прогресса
        pa = {'achievement': ach, 'progress': 0, 'completed': False, 'reward_claimed': False}
    
    ach = pa['achievement']
    
    # Прогресс-бар
    progress_pct = min(100, (pa['progress'] / ach['requirement_count']) * 100) if ach['requirement_count'] > 0 else 0
    filled = int(progress_pct / 10)
    empty = 10 - filled
    progress_bar = "🟩" * filled + "⬜" * empty
    
    # Награды
    rewards = []
    if ach['reward_coins'] > 0:
        rewards.append(f"• 💰 {ach['reward_coins']:,} монет")
    if ach['reward_gems'] > 0:
        rewards.append(f"• 💎 {ach['reward_gems']} кристаллов")
    for item, qty in ach.get('reward_items', {}).items():
        rewards.append(f"• 🌱 {item} x{qty}")
    if ach['reward_multiplier'] > 0:
        rewards.append(f"• 📈 +x{ach['reward_multiplier']:.1f} множитель")
    
    rewards_text = "\n".join(rewards) if rewards else "Нет наград"
    
    # Формируем текст
    text = f"""{ach['icon']} <b>{ach['name']}</b>

📝 {ach['description']}

📊 Прогресс: {pa['progress']:,}/{ach['requirement_count']:,} ({int(progress_pct)}%)
{progress_bar}

🎁 <b>Награда:</b>
{rewards_text}"""
    
    # Кнопки в зависимости от статуса
    buttons = []
    
    if pa['completed']:
        if pa['reward_claimed']:
            text += "\n\n✅ <b>Ачивка получена!</b>"
            text += f"\n📅 Дата: {pa.get('claimed_at', 'Неизвестно')[:10] if pa.get('claimed_at') else 'Неизвестно'}"
        else:
            text += "\n\n🎁 <b>Награда ожидает получения!</b>"
            buttons.append([InlineKeyboardButton(text="🎁 Забрать награду", callback_data=f"ach_reward_{ach_id}")])
    else:
        text += "\n\n⏳ <b>Продолжай выполнять условия!</b>"
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"ach_cat_{ach['category_id']}")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


@router.callback_query(F.data.startswith("ach_reward_"))
async def claim_achievement_reward(callback: CallbackQuery):
    """Получение награды за ачивку"""
    ach_id = int(callback.data.replace("ach_reward_", ""))
    
    db = await get_db()
    result = await db.claim_achievement_reward(callback.from_user.id, ach_id)
    
    if result['success']:
        rewards_text = "\n".join([f"• {r}" for r in result['rewards']])
        
        await callback.message.edit_text(
            f"🎉 <b>Награда получена!</b>\n\n"
            f"{result['achievement_icon']} <b>{result['achievement_name']}</b>\n\n"
            f"🎁 Ты получил:\n{rewards_text}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏆 К ачивкам", callback_data="back_achievements")],
                [InlineKeyboardButton(text="🌾 На ферму", callback_data="back_farm")],
            ]),
            parse_mode="HTML"
        )
    else:
        await callback.answer(f"❌ {result['message']}", show_alert=True)


@router.callback_query(F.data == "ach_claim_all")
async def claim_all_rewards(callback: CallbackQuery):
    """Забрать все награды"""
    db = await get_db()
    pending = await db.get_pending_rewards(callback.from_user.id)
    
    if not pending:
        await callback.answer("Нет доступных наград!")
        return
    
    claimed = []
    for ach in pending:
        result = await db.claim_achievement_reward(callback.from_user.id, ach['id'])
        if result['success']:
            claimed.append(f"{result['achievement_icon']} {result['achievement_name']}")
    
    if claimed:
        await callback.message.edit_text(
            f"🎉 <b>Все награды получены!</b>\n\n"
            f"Забрано ачивок: {len(claimed)}\n\n"
            f"{chr(10).join(['✅ ' + c for c in claimed])}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏆 К ачивкам", callback_data="back_achievements")],
            ]),
            parse_mode="HTML"
        )


@router.callback_query(F.data == "ach_history")
async def achievement_history(callback: CallbackQuery):
    """Лента достижений"""
    db = await get_db()
    history = await db.get_achievement_history(callback.from_user.id, limit=15)
    
    if not history:
        await callback.answer("История пуста!")
        return
    
    text_lines = ["🏅 <b>Мои достижения</b>\n"]
    
    for entry in history:
        date_str = entry['created_at'][:10] if entry['created_at'] else '???'
        text_lines.append(f"🎉 {date_str} - {entry['icon']} {entry['name']}")
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_achievements")],
        ]),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("ach_all_"))
async def achievements_all(callback: CallbackQuery):
    """Список всех ачивок с пагинацией"""
    page = int(callback.data.replace("ach_all_", ""))
    per_page = 5
    
    db = await get_db()
    achievements = await db.get_achievements_by_category(callback.from_user.id)
    
    # Фильтруем секретные неполученные
    visible_achievements = [a for a in achievements if not a.get('is_locked')]
    
    total_pages = (len(visible_achievements) + per_page - 1) // per_page
    start = page * per_page
    end = start + per_page
    page_achievements = visible_achievements[start:end]
    
    if not page_achievements:
        await callback.answer("Нет ачивок на этой странице!")
        return
    
    text_lines = [f"📋 <b>Все достижения (стр. {page + 1}/{total_pages})</b>\n"]
    
    for ach in page_achievements:
        if ach['completed']:
            if ach['reward_claimed']:
                status = "✅"
            else:
                status = "🎁"
        else:
            progress_pct = int((ach['progress'] / ach['requirement_count']) * 100) if ach['requirement_count'] > 0 else 0
            status = f"{progress_pct}%"
        
        text_lines.append(f"{status} {ach['icon']} {ach['name']}")
    
    # Кнопки навигации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"ach_all_{page-1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"ach_all_{page+1}"))
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        nav_buttons,
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_achievements")]
    ])
    
    await callback.message.edit_text("\n".join(text_lines), reply_markup=keyboard, parse_mode="HTML")


# =================== УНИВЕРСАЛЬНЫЕ ОБРАБОТЧИКИ "НАЗАД" ===================

@router.callback_query(F.data.startswith("back_"))
async def universal_back_handler(callback: CallbackQuery):
    """Универсальный обработчик для кнопок назад"""
    target = callback.data.replace("back_", "")

    if target == "farm":
        await show_farm(callback.from_user.id, callback.message)
    elif target == "main":
        await callback.message.answer(
            "Главное меню",
            reply_markup=get_main_keyboard()
        )
    elif target == "achievements":
        from aiogram.types import Message
        msg = callback.message
        msg.from_user = callback.from_user
        await achievements_handler(msg)
    else:
        await callback.answer("Функция в разработке")


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
