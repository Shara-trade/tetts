from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from database import get_database
from keyboards import *
from states import PlayerStates
import asyncio
import logging
import os

router = Router()

# Получаем экземпляр базы данных (синглтон)
async def get_db():
    return await get_database()

@router.message(Command("start"))
async def start_handler(message: Message):
    db = await get_db()
    user = await db.get_user(message.from_user.id)
    
    # Проверяем реферальный код в аргументах
    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = int(args[1].replace("ref_", ""))
        except ValueError:
            referrer_id = None
    
    if not user:
        # Создаём нового пользователя
        await db.create_user(
            message.from_user.id,
            message.from_user.username or "",
            message.from_user.first_name or ""
        )
        
        # Регистрируем реферала если есть referrer_id
        if referrer_id and referrer_id != message.from_user.id:
            ref_result = await db.register_referral(message.from_user.id, referrer_id)
            if ref_result.get("success"):
                referrer_name = ref_result.get("referrer_username", "друг")
                
                # Приветственное сообщение с реферальным бонусом
                welcome_text = (
                    f"🎉 <b>Вас пригласил @{referrer_name}!</b>\n\n"
                    f"Добро пожаловать на ферму, {message.from_user.first_name}! 👋\n"
                    f"В подарок ты получаешь:\n"
                    f"• 100🪙 стартовых\n"
                    f"• 🌱 Набор семян\n"
                    f"• ⚡ Удобрение\n\n"
                    f"Начни игру прямо сейчас!"
                )
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Начать игру", callback_data="back_farm")]
                ])
                
                await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")
            else:
                # Обычное приветствие если реферал не зарегистрирован
                await message.answer(
                    f"Добро пожаловать на твою ферму, {message.from_user.first_name}! 👋\n"
                    "Начни с 🌾 Моя Ферма!",
                    reply_markup=get_main_keyboard()
                )
        else:
            # Обычное приветствие без реферала
            await message.answer(
                f"Добро пожаловать на твою ферму, {message.from_user.first_name}! 👋\n"
                "Начни с 🌾 Моя Ферма!",
                reply_markup=get_main_keyboard()
            )
    else:
        # Проверяем награды за рефералов при каждом входе
        if referrer_id is None:  # Не пришли по реферальной ссылке
            rewards = await db.check_referral_rewards(message.from_user.id)
            if rewards:
                rewards_text = []
                total_coins = 0
                total_gems = 0
                
                for reward in rewards:
                    total_coins += reward.get('coins', 0)
                    total_gems += reward.get('gems', 0)
                    
                    type_names = {
                        'prestige1': 'Престиж 1',
                        'prestige5': 'Престиж 5', 
                        'prestige10': 'Престиж 10'
                    }
                    type_name = type_names.get(reward['type'], reward['type'])
                    
                    reward_text = f"✅ {type_name}: +{reward['coins']}🪙"
                    if reward['gems'] > 0:
                        reward_text += f" + {reward['gems']}💎"
                    rewards_text.append(reward_text)
                
                # Отправляем уведомление о наградах
                await message.answer(
                    f"🎉 <b>Твои рефералы достигли новых высот!</b>\n\n"
                    f"Ты получил бонусы:\n" + "\n".join(rewards_text) + f"\n\n"
                    f"Итого: +{total_coins:,}🪙 + {total_gems}💎",
                    parse_mode="HTML"
                )
        
        await message.answer("Добро пожаловать обратно!", reply_markup=get_main_keyboard())
    
    await show_farm(message.from_user.id, message)

async def show_farm(user_id: int, obj: Message | CallbackQuery):
    """Отображение фермы согласно ТЗ v4.0 п.4.2"""
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
    plot_count = len(plots)
    max_plots = await db.get_max_plots(user_id)
    
    # Заголовок фермы согласно ТЗ
    prestige_level = user.get('prestige_level', 1)
    prestige_multiplier = user.get('prestige_multiplier', 1.0)
    balance = user.get('balance', 0)
    gems = user.get('gems', 0)
    
    text_lines = [
        f"🌾 <b>ТВОЯ ФЕРМА</b> (Ур.{user.get('city_level', 1)} | Престиж {prestige_level})",
        "",
        f"💰 {balance:,}🪙 | x{prestige_multiplier:.1f} множитель",
        f"💎 {gems}💎" if gems > 0 else "",
        ""
    ]
    
    # Убираем пустые строки если нет кристаллов
    if gems <= 0:
        text_lines = [
            f"🌾 <b>ТВОЯ ФЕРМА</b> (Ур.{user.get('city_level', 1)} | Престиж {prestige_level})",
            "",
            f"💰 {balance:,}🪙 | x{prestige_multiplier:.1f} множитель",
            ""
        ]
    
    # Ежедневный бонус
    try:
        bonus = await db.get_daily_bonus(user_id)
        if bonus and bonus.get('available', False):
            text_lines.append("🎁 <b>Ежедневный бонус: доступен!</b>")
        else:
            streak = bonus.get('streak', 1) if bonus else 1
            text_lines.append(f"🎁 Бонус: уже получен (серия: {streak} дней)")
    except Exception as e:
        import logging
        logging.error(f"Error getting daily bonus: {e}")
    
    text_lines.append("")  # Пустая строка перед грядками
    
    # Получаем информацию о культурах для иконок и имён
    crop_icons = {}
    crop_names = {}
    for plot in plots:
        if plot.get("crop_type") and plot["crop_type"] not in crop_icons:
            try:
                crop_info = await db.fetchone(
                    "SELECT item_icon, item_name FROM shop_config WHERE item_code = ?",
                    (plot["crop_type"],)
                )
                crop_icons[plot["crop_type"]] = crop_info[0] if crop_info and crop_info[0] else '🌱'
                crop_names[plot["crop_type"]] = crop_info[1] if crop_info and crop_info[1] else plot["crop_type"]
            except Exception:
                crop_icons[plot["crop_type"]] = '🌱'
                crop_names[plot["crop_type"]] = plot["crop_type"]
    
    # Отображение грядок согласно ТЗ
    for plot in plots:
        plot_number = plot.get('number', '?')
        fertilized = plot.get('fertilized', False)
        fertilizer_bonus = plot.get('fertilizer_bonus', 0.0)
        text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
        
        if plot.get("status") == "empty":
            text_lines.append(f"🟫 Грядка #{plot_number}: Пусто")
            
        elif plot.get("status") == "growing":
            icon = crop_icons.get(plot.get("crop_type", ""), "🌱")
            crop_name = crop_names.get(plot.get("crop_type", ""), "???")
            remaining = plot.get("remaining_time", 0)
            minutes = remaining // 60
            seconds = remaining % 60
            time_str = f"{minutes:02d}:{seconds:02d}"
            
            # Рассчитываем процент роста
            try:
                crop_data = await db.get_shop_item(plot.get("crop_type"))
                if crop_data and crop_data.get("growth_time", 0) > 0:
                    total_time = crop_data["growth_time"]
                    elapsed = total_time - remaining
                    progress_pct = min(100, int((elapsed / total_time) * 100))
                else:
                    progress_pct = 50
            except:
                progress_pct = 50
            
            # Индикатор удобрения
            fert_indicator = " 🧪" if fertilized else ""
            fert_bonus_text = f" (+{int(fertilizer_bonus*100)}%💰)" if fertilizer_bonus > 0 else ""
            
            text_lines.append(f"{icon} Грядка #{plot_number}: {crop_name}{fert_indicator}{fert_bonus_text}")
            text_lines.append(f"   ⬆️ Созреет через: {time_str}")
            text_lines.append(f"   🌱 Стадия: Рост {progress_pct}%")
            
        elif plot.get("status") == "ready":
            icon = crop_icons.get(plot.get("crop_type", ""), "🌱")
            crop_name = crop_names.get(plot.get("crop_type", ""), "???")
            fert_indicator = " 🧪" if fertilized else ""
            fert_bonus_text = f" (+{int(fertilizer_bonus*100)}%💰)" if fertilizer_bonus > 0 else ""
            text_lines.append(f"{icon} Грядка #{plot_number}: {crop_name}{fert_indicator}{fert_bonus_text}")
            text_lines.append(f"   ⚡ <b>ГОТОВО К СБОРУ!</b>")
    
    # Добавляем информацию о следующей грядке для покупки
    next_plot = await db.get_next_plot_to_buy(user_id)
    if next_plot:
        text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
        text_lines.append(f"🟫 Грядка #{next_plot['plot_number']}: Пусто (купить за {next_plot['price']:,}🪙)")
    
    text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Формируем клавиатуру
    keyboard = get_farm_keyboard(plots, next_plot)
    
    if isinstance(obj, Message):
        await obj.answer("\n".join(text_lines), reply_markup=get_main_keyboard(), parse_mode="HTML")
        if keyboard:
            await obj.answer("⚡ Действия:", reply_markup=keyboard)
    else:
        await obj.message.edit_text("\n".join(text_lines), reply_markup=keyboard, parse_mode="HTML")

# =================== ОБРАБОТЧИКИ КНОПОК ГЛАВНОГО МЕНЮ (ТЗ v4.0) ===================

@router.message(F.text == "🌾 Ферма")
@router.message(F.text == "🌾 Моя Ферма")  # Старый вариант для совместимости
@router.message(Command("farm"))  # Команда /farm согласно ТЗ v4.0 п.4.2
async def farm_handler(message: Message):
    await show_farm(message.from_user.id, message)

@router.message(F.text == "📦 Инв")
@router.message(F.text == "📦 Амбар")  # Старый вариант для совместимости
async def inventory_handler_new(message: Message):
    await inventory_handler(message)

@router.message(F.text == "📜 Квесты")
async def quests_handler_button(message: Message):
    await quests_handler(message)

@router.message(F.text == "🏆 Ачивки")
@router.message(F.text == "🏆 Достижения")  # Старый вариант для совместимости
async def achievements_handler_button(message: Message):
    await achievements_handler(message)

@router.message(F.text == "🚜 Прест")
@router.message(F.text == "🚜 Престиж")  # Старый вариант для совместимости
async def prestige_handler_button(message: Message):
    await prestige_handler(message)

@router.message(F.text == "👤 Профиль")
async def profile_handler_button(message: Message):
    """Профиль игрока согласно ТЗ v4.0"""
    await profile_handler(message)

@router.message(F.text == "🎁 Бонус")
async def bonus_handler_button(message: Message):
    """Ежедневный бонус через кнопку меню"""
    await bonus_menu_handler(message)

@router.callback_query(F.data.startswith("plant_"))
async def plant_crop(callback: CallbackQuery, state: FSMContext):
    """Процесс посадки согласно ТЗ v4.0 п.4.4"""
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
    
    # Проверяем, новичок ли игрок (менее 3 посадок)
    total_planted = await db.get_user_plant_count(callback.from_user.id)
    is_newbie = total_planted < 3
    
    crops = await db.get_shop_items("seed")
    
    # Фильтруем доступные по уровню семена
    user_level = user.get('city_level', 1)
    available_crops = [c for c in crops if c.get('required_level', 1) <= user_level and c.get('is_active', True)]
    
    if not available_crops:
        await callback.answer("❌ Нет доступных семян для твоего уровня!", show_alert=True)
        return
    
    # Получаем множитель для расчёта прибыли
    multiplier = user.get('prestige_multiplier', 1.0)
    
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
    
    # Формируем текст согласно ТЗ
    if is_newbie:
        # Сценарий для новичков - с подсказками
        text_lines = [
            f"🌱 <b>ПОСАДКА НА ГРЯДКЕ #{plot_num}</b>",
            "",
            f"У тебя есть {user.get('balance', 0):,}🪙",
            "Выбери, что посадить:",
            "",
        ]
    else:
        # Сценарий для опытных игроков - компактный
        text_lines = [
            f"🌱 <b>Посадка на грядке #{plot_num}</b>",
            f"💰 Баланс: {user.get('balance', 0):,}🪙",
            ""
        ]
    
    # Формируем клавиатуру без пустых строк
    keyboard_rows = []
    for i in range(0, len(buttons), 2):
        row = buttons[i:i+2]
        if row:  # Добавляем только непустые строки
            keyboard_rows.append(row)
    
    # Добавляем кнопку назад
    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад к грядкам", callback_data="back_farm")])
    
    # Добавляем подсказку для новичков
    if is_newbie:
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        await callback.message.edit_text(
            "\n".join(text_lines),
            reply_markup=keyboard
        )
        
        # Отправляем дополнительную подсказку
        await callback.message.answer(
            "💡 <b>Совет:</b> Чем дороже семена, тем выше прибыль!\n"
            "⏱️ Время роста указано в минутах.\n"
            "💰 При продаже ты получишь больше, чем потратил!",
            parse_mode="HTML"
        )
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        await callback.message.edit_text(
            "\n".join(text_lines),
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
    """Сбор урожая согласно ТЗ v4.0 п.4.5"""
    db = await get_db()
    
    # Получаем данные в одной транзакции
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Ошибка: пользователь не найден!", show_alert=True)
        return
    
    # Проверяем сезонное событие
    event = await db.get_active_event()
    multiplier = user.get('prestige_multiplier', 1.0)
    
    if event and event.get('is_active', False):
        event_multiplier = event.get('multiplier', 1.0)
        if event_multiplier > 1.0 and event_multiplier <= 10:
            multiplier *= event_multiplier
    
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
    
    # Группируем урожай по типам для детального отчёта
    crop_summary = {}
    for crop in ready_crops:
        crop_type = crop.get('crop_type', '???')
        if crop_type not in crop_summary:
            crop_summary[crop_type] = {
                'icon': crop.get('icon', '🌱'),
                'count': 0,
                'earned': 0
            }
        crop_summary[crop_type]['count'] += 1
        crop_summary[crop_type]['earned'] += crop.get('earned', 0)
    
    # Формируем детальный отчёт согласно ТЗ
    text_lines = [
        "✅ <b>СБОР УРОЖАЯ</b>",
        "",
        f"Собрано грядок: {ready_count}",
        "━━━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    for crop_type, data in crop_summary.items():
        text_lines.append(f"{data['icon']} {crop_type} x{data['count']}: +{data['earned']:,}🪙")
    
    text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Бонус от события
    if event and event.get('is_active', False) and event.get('multiplier', 1.0) > 1.0:
        text_lines.append(f"🎉 Бонус события: x{event.get('multiplier', 1.0):.1f}")
    
    text_lines.append(f"💰 <b>Итого: +{total:,}🪙</b> (с учетом x{multiplier:.1f} множителя)")
    text_lines.append(f"✨ Опыт: +{ready_count * 5}")
    text_lines.append("")
    
    # Получаем новый баланс
    user = await db.get_user(callback.from_user.id)
    if user:
        text_lines.append(f"Новый баланс: {user.get('balance', 0):,}🪙")
    
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
    
    # Отправляем детальный отчёт
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌾 На ферму", callback_data="back_farm"),
            InlineKeyboardButton(text="📦 В амбар", callback_data="back_main")
        ]
    ])
    
    await callback.message.edit_text(
        "\n".join(text_lines), 
        reply_markup=keyboard, 
        parse_mode="HTML"
    )
 

# =================== СИСТЕМА УДОБРЕНИЙ (ТЗ v4.0 п.10) ===================

@router.callback_query(F.data.startswith("fertilize_"))
async def fertilize_plot_handler(callback: CallbackQuery):
    """Выбор удобрения для грядки согласно ТЗ v4.0 п.10.2"""
    try:
        plot_num = int(callback.data.split("_")[1])
    except (IndexError, ValueError):
        await callback.answer("❌ Неверный формат данных!", show_alert=True)
        return
    
    db = await get_db()
    
    # Проверяем пользователя
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Пользователь не найден!", show_alert=True)
        return
    
    # Проверяем грядку
    plot = await db.get_plot_fertilizer_status(callback.from_user.id, plot_num)
    if not plot:
        await callback.answer("❌ Грядка не найдена!", show_alert=True)
        return
    
    if plot['status'] != 'growing':
        await callback.answer("❌ На грядке ничего не растёт!", show_alert=True)
        return
    
    if plot['fertilized']:
        await callback.answer("❌ Удобрение уже применено к этой грядке!", show_alert=True)
        return
    
    # Получаем доступные удобрения
    fertilizers = await db.get_available_fertilizers(callback.from_user.id)
    
    if not fertilizers:
        await callback.answer("❌ Нет удобрений в инвентаре! Купите в магазине.", show_alert=True)
        return
    
    # Получаем информацию о культуре для расчёта времени
    crop_data = await db.get_shop_item(plot['crop_type'])
    crop_name = crop_data.get('name', plot['crop_type']) if crop_data else plot['crop_type']
    crop_icon = crop_data.get('icon', '🌱') if crop_data else '🌱'
    
    # Рассчитываем оставшееся время
    from datetime import datetime as dt
    now = dt.now()
    planted = dt.fromisoformat(plot['planted_time']) if plot['planted_time'] else now
    elapsed = (now - planted).total_seconds()
    remaining_time = max(0, plot['growth_time_seconds'] - int(elapsed))
    
    minutes = remaining_time // 60
    seconds = remaining_time % 60
    time_str = f"{minutes:02d}:{seconds:02d}"
    
    # Формируем текст согласно ТЗ
    text_lines = [
        f"🧪 <b>ПРИМЕНЕНИЕ УДОБРЕНИЯ</b>",
        "",
        f"Грядка #{plot_num}: {crop_icon} {crop_name}",
        f"⏱️ Осталось времени: {time_str}",
        "",
        "Выбери удобрение:",
        "━━━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    # Формируем кнопки удобрений
    buttons = []
    for fert in fertilizers:
        icon = fert.get('icon', '🧪')
        name = fert.get('name', '???')
        qty = fert.get('quantity', 0)
        effect_type = fert.get('effect_type', 'speed')
        effect_value = fert.get('effect_value', 0.0)
        
        # Рассчитываем эффект
        time_result = await db.calculate_fertilized_time(remaining_time, effect_type, effect_value)
        
        if time_result['is_instant']:
            new_time_str = "⚡ ГОТОВО СЕЙЧАС!"
        else:
            new_minutes = time_result['new_time'] // 60
            new_seconds = time_result['new_time'] % 60
            new_time_str = f"⏱️ {new_minutes:02d}:{new_seconds:02d}"
        
        text_lines.append(f"{icon} <b>{name}</b> ({qty} шт)")
        text_lines.append(f"   {new_time_str}")
        if time_result['income_bonus'] > 0:
            text_lines.append(f"   💰 +{int(time_result['income_bonus'] * 100)}% к доходу")
        text_lines.append("")
        
        buttons.append(InlineKeyboardButton(
            text=f"{icon} {name}",
            callback_data=f"applyfert_{plot_num}_{fert['code']}"
        ))
    
    text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Формируем клавиатуру
    keyboard_rows = []
    for i in range(0, len(buttons), 2):
        row = buttons[i:i+2]
        if row:
            keyboard_rows.append(row)
    
    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад к грядкам", callback_data="back_farm")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )
 

@router.callback_query(F.data.startswith("applyfert_"))
async def apply_fertilizer_handler(callback: CallbackQuery):
    """Применение удобрения к грядке"""
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("❌ Неверный формат данных!", show_alert=True)
        return
    
    try:
        plot_num = int(parts[1])
        fertilizer_code = parts[2]
    except (ValueError, IndexError):
        await callback.answer("❌ Неверный формат данных!", show_alert=True)
        return
    
    db = await get_db()
    
    # Применяем удобрение
    result = await db.apply_fertilizer(callback.from_user.id, plot_num, fertilizer_code)
    
    if not result.get('success', False):
        await callback.answer(f"❌ {result.get('message', 'Ошибка применения удобрения')}", show_alert=True)
        return
    
    # Формируем результат согласно ТЗ
    text_lines = [
        "✅ <b>Удобрение применено!</b>",
        "",
        f"Грядка #{plot_num}: {result.get('fertilizer_icon', '🧪')} {result.get('crop_type', '???')}",
    ]
    
    if result.get('is_instant'):
        text_lines.append("⚡ <b>Урожай созрел мгновенно!</b>")
    else:
        original_min = result.get('original_time', 0) // 60
        new_min = result.get('new_time', 0) // 60
        reduced = original_min - new_min
        text_lines.append(f"⏱️ Новое время: {new_min} мин (ускорено на {reduced} мин)")
    
    if result.get('income_bonus', 0) > 0:
        text_lines.append(f"💰 Бонус к доходу: +{int(result['income_bonus'] * 100)}%")
    
    text_lines.append("")
    text_lines.append(f"Осталось удобрений: {result.get('fertilizer_name', '???')}")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌾 На ферму", callback_data="back_farm")]
    ])
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await callback.answer(result.get('message', 'Удобрение применено!'))


# =================== ПОКУПКА ГРЯДОК (ТЗ v4.0 п.4.6) ===================

@router.callback_query(F.data.startswith("buy_plot_"))
async def buy_plot_handler(callback: CallbackQuery):
    """Покупка новой грядки"""
    try:
        plot_num = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("❌ Неверный формат данных!", show_alert=True)
        return
    
    db = await get_db()
    
    # Получаем информацию о грядке
    next_plot = await db.get_next_plot_to_buy(callback.from_user.id)
    
    if not next_plot:
        await callback.answer("❌ Все грядки уже куплены!", show_alert=True)
        return
    
    if next_plot['plot_number'] != plot_num:
        await callback.answer(f"❌ Сначала купи грядку #{next_plot['plot_number']}!", show_alert=True)
        return
    
    price = next_plot['price']
    user = await db.get_user(callback.from_user.id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден!", show_alert=True)
        return
    
    # Показываем диалог подтверждения
    text = (
        f"🛒 <b>ПОКУПКА НОВОЙ ГРЯДКИ</b>\n\n"
        f"Грядка #{plot_num}: {price:,}🪙\n"
        f"Твой баланс: {user.get('balance', 0):,}🪙\n\n"
        f"После покупки у тебя будет {plot_num} грядок"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"✅ Купить за {price:,}🪙", callback_data=f"confirm_buy_plot_{plot_num}"),
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="back_farm"),
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("confirm_buy_plot_"))
async def confirm_buy_plot(callback: CallbackQuery):
    """Подтверждение покупки грядки"""
    try:
        plot_num = int(callback.data.split("_")[3])
    except (IndexError, ValueError):
        await callback.answer("❌ Неверный формат данных!", show_alert=True)
        return
    
    db = await get_db()
    
    # Выполняем покупку
    result = await db.buy_plot(callback.from_user.id, plot_num)
    
    if result.get('success', False):
        text = (
            f"✅ <b>Грядка #{plot_num} куплена!</b>\n\n"
            f"💰 Списано: {result['price']:,}🪙\n"
            f"💰 Новый баланс: {result['new_balance']:,}🪙\n\n"
            f"Теперь у тебя {plot_num} грядок!"
        )
        
        # Проверяем ачивки за покупку улучшений
        try:
            await db.check_and_update_achievements(
                callback.from_user.id, "buy_plot", count=1
            )
            await db.check_and_update_achievements(
                callback.from_user.id, "spend", count=result['price']
            )
        except Exception as e:
            import logging
            logging.error(f"Error checking achievements: {e}")
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌾 На ферму", callback_data="back_farm")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await callback.answer(f"❌ {result.get('message', 'Ошибка покупки')}", show_alert=True)
        await show_farm(callback.from_user.id, callback.message)

# Ежедневный бонус
@router.callback_query(F.data == "claim_daily")
async def claim_daily(callback: CallbackQuery):
    """Получение ежедневного бонуса с рулеткой (ТЗ v4.0 п.13)"""
    db = await get_db()
    
    # Получаем информацию о бонусе
    streak_data = await db.get_daily_bonus_streak(callback.from_user.id)
    
    # Проверяем доступность
    if not streak_data.get('can_claim', True):
        await callback.answer("❌ Бонус уже получен сегодня!", show_alert=True)
        return
    
    # Показываем анимацию рулетки
    await callback.message.edit_text(
        "🎁 <b>ЕЖЕДНЕВНЫЙ БОНУС</b>\n\n"
        "🎲 Крутим рулетку...\n"
        "⏳ Определяем награды...",
        parse_mode="HTML"
    )
 
    # Небольшая задержка для эффекта
    import asyncio
    await asyncio.sleep(1.5)
    
    # Получаем бонус с рулеткой
    result = await db.claim_daily_bonus(callback.from_user.id)
    
    if not result or not result.get('success', False):
        await callback.answer("❌ " + result.get('message', 'Ошибка получения бонуса'), show_alert=True)
        await show_farm(callback.from_user.id, callback.message)
        return
    
    streak = result.get('streak', 1)
    rewards = result.get('rewards', [])
    total_coins = result.get('total_coins', 0)
    total_gems = result.get('total_gems', 0)
    items = result.get('items', [])
    
    # Формируем текст наград
    text_lines = [
        "🎁 <b>ЕЖЕДНЕВНЫЙ БОНУС!</b>",
        "",
        f"🔥 Ты заходишь <b>{streak} дней подряд!</b>",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━",
        "🎲 <b>РОЗЫГРЫШ БОНУСА...</b>",
        "",
        "<b>Ты получаешь:</b>",
        ""
    ]
    
    # Добавляем награды
    for reward in rewards:
        icon = reward.get('icon', '🎁')
        name = reward.get('name', '???')
        amount = reward.get('amount', 0)
        text_lines.append(f"{icon} <b>+{amount}</b> {name}")
    
    text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Бонус за серию
    if streak >= 8:
        text_lines.append("\n🔥🔥 <b>СУПЕР СЕРИЯ!</b> Награды удвоены!")
    elif streak >= 4:
        text_lines.append("\n⭐ <b>Отличная серия!</b> Награды +50%!")
    
    # Итого
    text_lines.append("")
    text_lines.append("📊 <b>ИТОГО:</b>")
    if total_coins > 0:
        text_lines.append(f"💰 +{total_coins:,}🪙")
    if total_gems > 0:
        text_lines.append(f"💎 +{total_gems} кристаллов")
    if items:
        for item in items:
            text_lines.append(f"📦 +{item['amount']} {item['icon']} {item['name']}")
    
    # Время до следующего бонуса
    text_lines.append("")
    text_lines.append("⏳ Следующий бонус через: <b>24:00</b>")
    
    # Клавиатура
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌾 На ферму", callback_data="back_farm")]
    ])
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    # Проверяем ачивки за серию
    try:
        completed_achs = await db.check_and_update_achievements(
            callback.from_user.id, "streak_days", count=streak
        )
        
        for ach in completed_achs:
            rewards_text = f"{ach.get('reward_coins', 0):,}🪙"
            if ach.get('reward_gems', 0) > 0:
                rewards_text += f" + {ach['reward_gems']}💎"
            
            await callback.message.answer(
                f"🎉 <b>НОВОЕ ДОСТИЖЕНИЕ!</b>\n\n"
                f"{ach.get('icon', '🏆')} <b>{ach.get('name', '???')}</b>\n"
                f"🎁 Награда: {rewards_text}",
                parse_mode="HTML"
            )
    except Exception as e:
        import logging
        logging.error(f"Error checking achievements: {e}")
    
    # Отправляем уведомление
    reward_summary = f"+{total_coins:,}🪙" if total_coins > 0 else f"+{total_gems}💎"
    await callback.answer(f"✅ Бонус получен! {reward_summary}")

# Обновление фермы
@router.callback_query(F.data == "refresh_farm")
async def refresh_farm(callback: CallbackQuery):
    await callback.answer("🔄 Обновлено!")
    await show_farm(callback.from_user.id, callback.message)

# Магазин
@router.message(F.text == "🏪 Магазин")
@router.message(Command("shop"))
@router.message(Command("магазин"))
@router.message(Command("шоп"))
@router.message(Command("купить"))
@router.message(Command("покупки"))
async def shop_handler(message: Message):
    """Главное меню магазина согласно ТЗ v4.0 п.5.1"""
    db = await get_db()
    
    # Получаем данные пользователя
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден!")
        return
    
    balance = user.get('balance', 0)
    gems = user.get('gems', 0)
    prestige_level = user.get('prestige_level', 1)
    
    # Проверяем сезонное событие
    event = await db.get_active_event()
    
    # Формируем текст согласно ТЗ
    text_lines = [
        "🏪 <b>МАГАЗИН</b>",
        "",
        f"💰 Твой баланс: {balance:,}🪙 | 💎 {gems}💎",
        "",
        "Выбери категорию:",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━",
        "🌱 Семена — для посадки",
        "🧪 Удобрения — ускоряют рост",
        "🚜 Улучшения — навсегда",
    ]
    
    # Добавляем информацию о фермерах если престиж >= 10
    if prestige_level >= 10:
        text_lines.append("👤 Фермеры — автобот (с 10 прест)")
    
    text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Добавляем информацию о сезонном событии
    if event and event.get('is_active', False):
        try:
            from datetime import datetime, timezone
            end_date = event.get('end_date')
            
            if end_date:
                if isinstance(end_date, str):
                    try:
                        if 'T' in end_date:
                            end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                        else:
                            end_date = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
                    except (ValueError, AttributeError):
                        end_date = None
                
                if end_date:
                    if end_date.tzinfo is None:
                        now = datetime.now()
                    else:
                        now = datetime.now(end_date.tzinfo)
                    
                    time_left = end_date - now
                    days_left = time_left.days
                    hours_left = int(time_left.total_seconds() // 3600) % 24
                    
                    if days_left > 0:
                        time_str = f"{days_left} дн. {hours_left} ч."
                    else:
                        time_str = f"{hours_left} ч."
                    
                    event_icon = event.get('icon', '🎉')
                    event_name = event.get('name', 'Событие')
                    text_lines.append("")
                    text_lines.append(f"Сезонное: {event_icon} {event_name} (осталось {time_str})")
        except Exception as e:
            import logging
            logging.warning(f"Error parsing event date: {e}")
    
    await message.answer(
        "\n".join(text_lines),
        reply_markup=get_shop_keyboard(prestige_level, event),
        parse_mode="HTML"
    )
 
@router.callback_query(F.data.startswith("shop_"))
async def shop_category(callback: CallbackQuery):
    """Просмотр категории магазина"""
    category = callback.data.replace("shop_", "")

    # Валидация категории
    valid_categories = ['seed', 'fertilizer', 'upgrade', 'tool', 'sell']
    if category not in valid_categories:
        await callback.answer("❌ Неверная категория!")
        return
    
    db = await get_db()
    
    # Особый обработчик для продажи
    if category == 'sell':
        await show_sell_menu(callback)
        return
    
    # Получаем товары категории
    items = await db.get_shop_items(category)
    
    if not items:
        await callback.answer("📭 Категория пуста!")
        return
    
    # Получаем данные пользователя
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Пользователь не найден!")
        return
    
    user_level = user.get('city_level', 1)
    prestige_level = user.get('prestige_level', 1)
    multiplier = user.get('prestige_multiplier', 1.0)
    balance = user.get('balance', 0)
    gems = user.get('gems', 0)
    
    # Проверяем сезонное событие
    event = await db.get_active_event()
    event_multiplier = 1.0
    if event and event.get('is_active', False):
        event_multiplier = event.get('multiplier', 1.0)
        if event_multiplier > 1.0:
            multiplier *= event_multiplier
    
    # Заголовок категории
    category_names = {
        'seed': '🌱 СЕМЕНА',
        'fertilizer': '🧪 УДОБРЕНИЯ',
        'upgrade': '🚜 УЛУЧШЕНИЯ',
        'tool': '🔧 ИНСТРУМЕНТЫ'
    }
    
    text_lines = [
        f"{category_names.get(category, category.upper())} (доступно: {len(items)} видов)",
        "",
        f"Твой уровень: {user_level} | Престиж: {prestige_level}",
        ""
    ]
    
    # Формируем список товаров
    for item in items:
        icon = item.get('icon', '🌱')
        name = item.get('name', '???')
        item_code = item.get('item_code', '')
        buy_price = item.get('buy_price', 0)
        sell_price = item.get('sell_price', 0)
        growth_time = item.get('growth_time', 0)
        required_level = item.get('required_level', 1)
        effect_value = item.get('effect_value')
        effect_type = item.get('effect_type')
        
        # Проверяем доступность по уровню
        is_locked = user_level < required_level
        
        # Формируем строку товара
        if is_locked:
            text_lines.append(f"🔒 {icon} {name} — {buy_price:,}🪙")
            text_lines.append(f"   ⚠️ Требуется: Ур.{required_level}")
        else:
            text_lines.append(f"{icon} {name} — {buy_price:,}🪙")
            
            # Для семян показываем время роста и прибыль
            if category == 'seed':
                minutes = growth_time // 60
                text_lines.append(f"   • Растет: {minutes} мин")
                
                # Цена продажи с учётом множителя
                sell_with_multiplier = int(sell_price * multiplier)
                profit = sell_with_multiplier - buy_price
                
                text_lines.append(f"   • Продажа: {sell_price:,}🪙 ({sell_with_multiplier:,}🪙 с x{multiplier:.1f})")
                text_lines.append(f"   • Прибыль: +{profit:,}🪙")
            
            # Для удобрений показываем эффект
            elif category == 'fertilizer':
                if effect_type == 'speed':
                    text_lines.append(f"   • Ускоряет рост на {int(effect_value * 100)}%")
                elif effect_type == 'instant':
                    text_lines.append(f"   • Мгновенное созревание")
                elif effect_type == 'bonus':
                    text_lines.append(f"   • +{int(effect_value * 100)}% к доходу")
                
                # Особая цена для кристальных удобрений
                if buy_price > 100 and effect_type == 'instant':
                    text_lines.append(f"   • Цена: {buy_price}💎")
            
            # Для улучшений
            elif category == 'upgrade':
                if 'plot' in item_code.lower():
                    text_lines.append(f"   • +1 грядка на ферме")
                elif 'barn' in item_code.lower() or 'storage' in item_code.lower():
                    text_lines.append(f"   • +{effect_value}% вместимости инвентаря")
                elif 'auto' in item_code.lower():
                    text_lines.append(f"   • Автоматически удобряет при посадке")
        
        text_lines.append("")
    
    text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Формируем клавиатуру с товарами
    keyboard = get_shop_items_keyboard(category, items, user_level)
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )
 

async def show_sell_menu(callback: CallbackQuery):
    """Меню продажи предметов согласно ТЗ v4.0 п.5.6"""
    db = await get_db()
    
    # Получаем данные пользователя
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Пользователь не найден!")
        return
    
    multiplier = user.get('prestige_multiplier', 1.0)
    
    # Проверяем сезонное событие
    event = await db.get_active_event()
    if event and event.get('is_active', False):
        event_multiplier = event.get('multiplier', 1.0)
        if event_multiplier > 1.0:
            multiplier *= event_multiplier
    
    # Получаем инвентарь
    inventory = await db.get_inventory(callback.from_user.id)
    
    if not inventory:
        await callback.message.edit_text(
            "💰 <b>ПРОДАЖА ПРЕДМЕТОВ</b>\n\n"
            "📦 Твой инвентарь пуст!\n\n"
            "Сначала собери урожай или купи предметы.",
            reply_markup=get_back_keyboard("shop"),
            parse_mode="HTML"
        )
        return
    
    # Получаем информацию о предметах
    all_items = await db.get_shop_items()
    items_info = {item['item_code']: item for item in all_items}
    
    # Фильтруем только продаваемые предметы
    sellable_items = {}
    total_value = 0
    
    for item_code, quantity in inventory.items():
        if quantity <= 0:
            continue
        
        item = items_info.get(item_code)
        if not item:
            continue
        
        sell_price = item.get('sell_price', 0)
        if sell_price <= 0:
            continue
        
        # Вычисляем стоимость с множителем
        item_value = int(sell_price * quantity * multiplier)
        total_value += item_value
        
        sellable_items[item_code] = {
            'name': item.get('name', item_code),
            'icon': item.get('icon', '📦'),
            'quantity': quantity,
            'sell_price': sell_price,
            'value': item_value,
            'value_with_multiplier': int(sell_price * multiplier)
        }
    
    if not sellable_items:
        await callback.message.edit_text(
            "💰 <b>ПРОДАЖА ПРЕДМЕТОВ</b>\n\n"
            "📦 Нет предметов для продажи!\n\n"
            "Некоторые предметы нельзя продать.",
            reply_markup=get_back_keyboard("shop"),
            parse_mode="HTML"
        )
        return
    
    # Формируем текст
    text_lines = [
        "💰 <b>ПРОДАЖА ПРЕДМЕТОВ</b>",
        "",
        "Твой инвентарь:",
        "━━━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    for item_code, data in sellable_items.items():
        text_lines.append(
            f"{data['icon']} {data['name']}: {data['quantity']} шт — "
            f"{data['value_with_multiplier'] * data['quantity']:,}🪙 (с x{multiplier:.1f})"
        )
    
    text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    text_lines.append(f"💰 Всего: {total_value:,}🪙 (с учетом множителя)")
    text_lines.append("")
    text_lines.append("Что продаем?")
    
    # Формируем клавиатуру
    keyboard = get_sell_keyboard(sellable_items)
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("buyitem_"))
async def buy_item_handler(callback: CallbackQuery):
    """Покупка товара в магазине"""
    parts = callback.data.split("_")
    if len(parts) < 2:
        await callback.answer("❌ Неверный формат данных!")
        return
    
    item_code = parts[1]
    quantity = int(parts[2]) if len(parts) > 2 else 1
    
    db = await get_db()
    
    # Выполняем покупку
    result = await db.buy_shop_item(callback.from_user.id, item_code, quantity)
    
    if result.get('success', False):
        item_name = result.get('item_name', item_code)
        spent = result.get('spent', 0)
        currency = result.get('currency', 'coins')
        currency_icon = '💎' if currency == 'gems' else '🪙'
        
        await callback.answer(f"✅ Куплено {item_name} x{quantity} за {spent}{currency_icon}!")
        
        # Обновляем сообщение с категорией
        await shop_category(callback)
    else:
        await callback.answer(f"❌ {result.get('message', 'Ошибка покупки')}", show_alert=True)


@router.callback_query(F.data.startswith("sellitem_"))
async def sell_item_handler(callback: CallbackQuery):
    """Продажа предмета"""
    parts = callback.data.split("_")
    if len(parts) < 2:
        await callback.answer("❌ Неверный формат данных!")
        return
    
    item_code = parts[1]
    quantity = int(parts[2]) if len(parts) > 2 else 1
    
    db = await get_db()
    
    # Получаем множитель пользователя
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Пользователь не найден!")
        return
    
    multiplier = user.get('prestige_multiplier', 1.0)
    
    # Выполняем продажу
    result = await db.sell_inventory_item(callback.from_user.id, item_code, quantity, multiplier)
    
    if result.get('success', False):
        item_name = result.get('item_name', item_code)
        earned = result.get('earned', 0)
        
        await callback.answer(f"✅ Продано {item_name} x{quantity} за {earned:,}🪙!")
        
        # Обновляем меню продажи
        await show_sell_menu(callback)
    else:
        await callback.answer(f"❌ {result.get('message', 'Ошибка продажи')}", show_alert=True)


# =================== УЛУЧШЕНИЯ (ТЗ v4.0 п.12) ===================

@router.callback_query(F.data == "shop_upgrades")
async def shop_upgrades_handler(callback: CallbackQuery):
    """Меню улучшений согласно ТЗ v4.0 п.12"""
    db = await get_db()
    
    # Получаем данные пользователя
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Пользователь не найден!")
        return
    
    prestige_level = user.get('prestige_level', 1)
    balance = user.get('balance', 0)
    
    # Проверяем доступность (с 20 престижа)
    if prestige_level < 20:
        text = (
            "🔒 <b>УЛУЧШЕНИЯ</b>\n\n"
            f"Твой престиж: {prestige_level}\n"
            "Требуется: <b>20 престиж</b>\n\n"
            "Улучшения позволяют усилить фермера и хранилище!\n\n"
            "Достигни 20 престижа, чтобы открыть раздел."
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_shop")]
        ])
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        return
    
    # Получаем улучшения
    upgrades = await db.get_upgrades(required_prestige=prestige_level)
    
    text_lines = [
        "🚜 <b>УЛУЧШЕНИЯ</b>",
        f"Твой престиж: {prestige_level} ✅ доступно",
        "",
        "💰 Твой баланс: {:,}🪙".format(balance),
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    # Группируем по категориям
    farmer_upgrades = [u for u in upgrades if u['category'] == 'farmer']
    storage_upgrades = [u for u in upgrades if u['category'] == 'storage']
    
    buttons = []
    
    # Улучшения фермера
    if farmer_upgrades:
        text_lines.append("📈 <b>УЛУЧШЕНИЯ ФЕРМЕРА:</b>")
        for upg in farmer_upgrades:
            current_level = await db.get_upgrade_level(callback.from_user.id, upg['upgrade_code'])
            icon = upg.get('icon', '⬆️')
            name = upg.get('name', '???')
            max_level = upg.get('max_level', 10)
            
            # Рассчитываем цену
            price = int(upg['base_price'] * (upg['price_multiplier'] ** current_level))
            
            if current_level >= max_level:
                status = "✅ Макс"
            else:
                status = f"{current_level}/{max_level} ур. — {price:,}🪙"
            
            # Эффект
            effect_val = upg.get('effect_value', 0) * current_level
            if upg['effect_type'] == 'speed':
                effect_text = f"+{int(effect_val * 100)}% скорость"
            elif upg['effect_type'] == 'income':
                effect_text = f"+{int(effect_val * 100)}% доход"
            elif upg['effect_type'] == 'capacity':
                effect_text = f"+{int(effect_val * 100)}% вместимость"
            else:
                effect_text = f"+{effect_val}{upg.get('effect_unit', '')}"
            
            text_lines.append(f"{icon} {name} — {status}")
            text_lines.append(f"   Эффект: {effect_text}")
            text_lines.append("")
            
            # Кнопка улучшения
            if current_level < max_level:
                buttons.append(InlineKeyboardButton(
                    text=f"{icon} {name} (ур.{current_level + 1})",
                    callback_data=f"buy_upgrade_{upg['upgrade_code']}"
                ))
        
        text_lines.append("")
    
    # Улучшения хранилища
    if storage_upgrades:
        text_lines.append("🏭 <b>УЛУЧШЕНИЯ ХРАНИЛИЩА:</b>")
        for upg in storage_upgrades:
            current_level = await db.get_upgrade_level(callback.from_user.id, upg['upgrade_code'])
            icon = upg.get('icon', '⬆️')
            name = upg.get('name', '???')
            max_level = upg.get('max_level', 10)
            
            price = int(upg['base_price'] * (upg['price_multiplier'] ** current_level))
            
            if current_level >= max_level:
                status = "✅ Макс"
            else:
                status = f"{current_level}/{max_level} ур. — {price:,}🪙"
            
            # Эффект
            effect_val = upg.get('effect_value', 0)
            if upg['effect_type'] == 'capacity':
                effect_text = f"+{int(effect_val * current_level)}{upg.get('effect_unit', '')}"
            elif upg['effect_type'] == 'protection':
                effect_text = f"-{int(effect_val * current_level * 100)}% потерь"
            else:
                effect_text = f"+{effect_val}{upg.get('effect_unit', '')}"
            
            text_lines.append(f"{icon} {name} — {status}")
            text_lines.append(f"   Эффект: {effect_text}")
            text_lines.append("")
            
            if current_level < max_level:
                buttons.append(InlineKeyboardButton(
                    text=f"{icon} {name} (ур.{current_level + 1})",
                    callback_data=f"buy_upgrade_{upg['upgrade_code']}"
                ))
    
    text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Формируем клавиатуру
    keyboard_rows = [[btn] for btn in buttons]
    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад в магазин", callback_data="back_shop")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )
 

@router.callback_query(F.data.startswith("buy_upgrade_"))
async def buy_upgrade_handler(callback: CallbackQuery):
    """Покупка улучшения"""
    upgrade_code = callback.data.replace("buy_upgrade_", "")
    
    db = await get_db()
    
    # Покупаем улучшение
    result = await db.buy_upgrade(callback.from_user.id, upgrade_code)
    
    if result.get('success', False):
        name = result.get('name', '???')
        icon = result.get('icon', '⬆️')
        new_level = result.get('new_level', 1)
        price = result.get('price', 0)
        
        await callback.answer(f"✅ Улучшение куплено!")
        
        # Показываем результат
        effect_type = result.get('effect_type', '')
        effect_value = result.get('effect_value', 0)
        
        if effect_type == 'speed':
            effect_text = f"+{int(effect_value * 100)}% скорость работы"
        elif effect_type == 'income':
            effect_text = f"+{int(effect_value * 100)}% к доходу"
        elif effect_type == 'capacity':
            effect_text = f"+{int(effect_value * 100)}% вместимости"
        else:
            effect_text = f"+{effect_value}{result.get('effect_unit', '')}"
        
        text = (
            f"{icon} <b>УЛУЧШЕНИЕ ПРИОБРЕТЕНО!</b>\n\n"
            f"{name}\n"
            f"Новый уровень: <b>{new_level}</b>\n"
            f"💰 Списано: {price:,}🪙\n\n"
            f"📊 Новый эффект:\n"
            f"{effect_text}"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚜 Еще улучшения", callback_data="shop_upgrades")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_shop")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await callback.answer(f"❌ {result.get('message', 'Ошибка покупки')}", show_alert=True)


@router.callback_query(F.data.startswith("upgrades_category_"))
async def upgrades_category_handler(callback: CallbackQuery):
    """Просмотр улучшений категории"""
    category = callback.data.replace("upgrades_category_", "")
    
    db = await get_db()
    user = await db.get_user(callback.from_user.id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден!")
        return
    
    prestige_level = user.get('prestige_level', 1)
    balance = user.get('balance', 0)
    
    if prestige_level < 20:
        await callback.answer("🔒 Требуется 20 престиж!")
        return
    
    # Получаем улучшения категории
    all_upgrades = await db.get_upgrades(category=category, required_prestige=prestige_level)
    
    category_names = {'farmer': '🚜 ФЕРМЕРЫ', 'storage': '🏭 ХРАНИЛИЩЕ'}
    category_name = category_names.get(category, category.upper())
    
    text_lines = [
        f"{category_name}",
        "",
        f"💰 Баланс: {balance:,}🪙",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    buttons = []
    
    for upg in all_upgrades:
        code = upg['upgrade_code']
        current_level = await db.get_upgrade_level(callback.from_user.id, code)
        max_level = upg['max_level']
        
        icon = upg.get('icon', '⬆️')
        name = upg.get('name', '???')
        
        # Рассчитываем цену следующего уровня
        base_price = upg['base_price']
        multiplier = upg['price_multiplier']
        next_price = int(base_price * (multiplier ** current_level)) if current_level < max_level else 0
        
        # Эффекты
        effect_type = upg.get('effect_type', '')
        effect_value = upg.get('effect_value', 0) * current_level
        
        if effect_type == 'speed':
            effect_text = f"+{int(effect_value * 100)}% скорость"
        elif effect_type == 'income':
            effect_text = f"+{int(effect_value * 100)}% доход"
        elif effect_type == 'capacity':
            effect_text = f"+{int(effect_value * 100)}% вмест."
        elif effect_type == 'protection':
            effect_text = f"-{int(effect_value * 100)}% потерь"
        else:
            effect_text = f"+{effect_value}{upg.get('effect_unit', '')}"
        
        # Статус
        if current_level >= max_level:
            status = "✅ МАКС"
        elif balance < next_price:
            status = f"❌ {next_price:,}🪙"
        else:
            status = f"💰 {next_price:,}🪙"
        
        text_lines.append(f"{icon} <b>{name}</b> [{current_level}/{max_level}]")
        text_lines.append(f"   Эффект: {effect_text}")
        text_lines.append(f"   Статус: {status}")
        text_lines.append("")
    
        # Кнопка улучшения
        if current_level < max_level:
            buttons.append(InlineKeyboardButton(
                text=f"{icon} {name} (ур.{current_level + 1})",
                callback_data=f"upgrade_view_{code}"
            ))
    
    text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Формируем клавиатуру
    keyboard_rows = [[btn] for btn in buttons]
    keyboard_rows.append([InlineKeyboardButton(text="🔙 К улучшениям", callback_data="shop_upgrades")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )
 

@router.callback_query(F.data.startswith("upgrade_view_"))
async def upgrade_view_handler(callback: CallbackQuery):
    """Детальный просмотр улучшения"""
    upgrade_code = callback.data.replace("upgrade_view_", "")
    
    db = await get_db()
    user = await db.get_user(callback.from_user.id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден!")
        return
    
    prestige_level = user.get('prestige_level', 1)
    balance = user.get('balance', 0)
    
    if prestige_level < 20:
        await callback.answer("🔒 Требуется 20 престиж!")
        return
    
    # Получаем информацию об улучшении
    upgrades = await db.get_upgrades()
    upgrade = next((u for u in upgrades if u['upgrade_code'] == upgrade_code), None)
    
    if not upgrade:
        await callback.answer("❌ Улучшение не найдено!")
        return
    
    current_level = await db.get_upgrade_level(callback.from_user.id, upgrade_code)
    max_level = upgrade['max_level']
    
    icon = upgrade.get('icon', '⬆️')
    name = upgrade.get('name', '???')
    description = upgrade.get('description', '')
    
    # Рассчитываем цены и эффекты
    base_price = upgrade['base_price']
    multiplier = upgrade['price_multiplier']
    next_price = int(base_price * (multiplier ** current_level)) if current_level < max_level else 0
    
    effect_type = upgrade.get('effect_type', '')
    effect_value = upgrade.get('effect_value', 0)
    
    # Текущий эффект
    current_effect = effect_value * current_level
    next_effect = effect_value * (current_level + 1)
    
    text_lines = [
        f"{icon} <b>{name}</b>",
        f"Уровень: {current_level}/{max_level}",
        "",
        f"📋 {description}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━",
        "📊 ЭФФЕКТИВНОСТЬ:",
    ]
    
    if effect_type == 'speed':
        text_lines.append(f"Сейчас: +{int(current_effect * 100)}% скорости")
        if current_level < max_level:
            text_lines.append(f"После улучшения: +{int(next_effect * 100)}% скорости")
            text_lines.append(f"Бонус: +{int(effect_value * 100)}%")
    elif effect_type == 'income':
        text_lines.append(f"Сейчас: +{int(current_effect * 100)}% к доходу")
        if current_level < max_level:
            text_lines.append(f"После улучшения: +{int(next_effect * 100)}% к доходу")
    elif effect_type == 'capacity':
        unit = upgrade.get('effect_unit', '')
        text_lines.append(f"Сейчас: +{int(current_effect)}{unit}")
        if current_level < max_level:
            text_lines.append(f"После улучшения: +{int(next_effect)}{unit}")
    elif effect_type == 'protection':
        text_lines.append(f"Сейчас: -{int(current_effect * 100)}% потерь")
        if current_level < max_level:
            text_lines.append(f"После улучшения: -{int(next_effect * 100)}% потерь")
    
    # Расчёт окупаемости (примерно)
    if effect_type == 'speed' and current_level < max_level:
        text_lines.append("")
        text_lines.append("💡 Прирост: ~+3 посадки/час")
        text_lines.append("💡 Окупаемость: ~75 часов")
    
    text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Кнопки
    keyboard_rows = []
    category = upgrade.get('category', 'farmer')
    
    if current_level < max_level:
        if balance >= next_price:
            keyboard_rows.append([InlineKeyboardButton(
                text=f"⬆️ Улучшить за {next_price:,}🪙",
                callback_data=f"buy_upgrade_{upgrade_code}"
            )])
        else:
            keyboard_rows.append([InlineKeyboardButton(
                text=f"❌ Недостаточно монет ({next_price:,}🪙)",
                callback_data="noop"
            )])
    else:
        keyboard_rows.append([InlineKeyboardButton(
            text="✅ Максимальный уровень достигнут!",
            callback_data="noop"
        )])
    
    keyboard_rows.append([InlineKeyboardButton(
        text="🔙 Назад",
        callback_data=f"upgrades_category_{category}"
    )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("itemdetail_"))
async def item_detail_handler(callback: CallbackQuery):
    """Детальный просмотр товара согласно ТЗ v4.0 п.5.3"""
    item_code = callback.data.replace("itemdetail_", "")
    
    db = await get_db()
    
    # Получаем информацию о товаре
    item = await db.get_shop_item(item_code)
    if not item:
        await callback.answer("❌ Товар не найден!")
        return
    
    # Получаем данные пользователя
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Пользователь не найден!")
        return
    
    user_level = user.get('city_level', 1)
    multiplier = user.get('prestige_multiplier', 1.0)
    balance = user.get('balance', 0)
    
    icon = item.get('icon', '🌱')
    name = item.get('name', item_code)
    buy_price = item.get('buy_price', 0)
    sell_price = item.get('sell_price', 0)
    growth_time = item.get('growth_time', 0)
    required_level = item.get('required_level', 1)
    effect_value = item.get('effect_value')
    effect_type = item.get('effect_type')
    category = item.get('category', '')
    
    # Формируем детальный текст
    text_lines = [
        f"{icon} <b>{name.upper()}</b> (Детально)",
        "",
        "📊 <b>Характеристики:</b>"
    ]
    
    if category == 'seed':
        minutes = growth_time // 60
        sell_with_multiplier = int(sell_price * multiplier)
        profit = sell_with_multiplier - buy_price
        
        text_lines.append(f"• Время роста: {minutes} минут")
        text_lines.append(f"• Базовый доход: {sell_price:,}🪙")
        text_lines.append(f"• С учетом твоего множителя: {sell_with_multiplier:,}🪙")
        text_lines.append(f"• Чистая прибыль: {profit:,}🪙")
        text_lines.append("")
        
        # Эффективность
        income_per_minute = profit / minutes if minutes > 0 else 0
        text_lines.append("📈 <b>Эффективность:</b>")
        text_lines.append(f"• Доход в минуту: {income_per_minute:.1f}🪙")
        text_lines.append("")
        text_lines.append("🏆 <b>Достижения:</b>")
        text_lines.append(f"• \"{name} король\" — 1000 посадок")
        text_lines.append(f"• \"Золотое поле\" — 5000 собрано")
    
    elif category == 'fertilizer':
        if effect_type == 'speed':
            text_lines.append(f"• Ускоряет рост на {int(effect_value * 100)}%")
            text_lines.append(f"• Мгновенное применение")
        elif effect_type == 'instant':
            text_lines.append(f"• Мгновенное созревание")
            text_lines.append(f"• +{int(effect_value * 100)}% к доходу")
        
        text_lines.append("")
        text_lines.append("💡 <b>Совет:</b>")
        text_lines.append("Используй удобрения на дорогих культурах для максимальной выгоды!")
    
    elif category == 'upgrade':
        text_lines.append(f"• Покупается один раз")
        text_lines.append(f"• Действует навсегда")
        text_lines.append("")
        text_lines.append("💡 <b>Эффект:</b>")
        
        if 'plot' in item_code.lower():
            current_plots = await db.get_plot_count(callback.from_user.id)
            text_lines.append(f"• Сейчас у тебя {current_plots} грядок")
            text_lines.append(f"• После покупки: {current_plots + 1} грядок")
        elif 'barn' in item_code.lower() or 'storage' in item_code.lower():
            text_lines.append(f"• +{effect_value}% вместимости инвентаря")
    
    text_lines.append("")
    text_lines.append(f"💰 Твой баланс: {balance:,}🪙")
    
    # Формируем клавиатуру
    keyboard = get_item_detail_keyboard(item, user_level, balance)
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "back_shop")
async def back_to_shop(callback: CallbackQuery):
    """Возврат в главное меню магазина"""
    db = await get_db()
    
    # Получаем данные пользователя
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Пользователь не найден!")
        return
    
    prestige_level = user.get('prestige_level', 1)
    balance = user.get('balance', 0)
    gems = user.get('gems', 0)
    
    # Проверяем сезонное событие
    event = await db.get_active_event()
    
    # Формируем текст
    text_lines = [
        "🏪 <b>МАГАЗИН</b>",
        "",
        f"💰 Твой баланс: {balance:,}🪙 | 💎 {gems}💎",
        "",
        "Выбери категорию:",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━",
        "🌱 Семена — для посадки",
        "🧪 Удобрения — ускоряют рост",
        "🚜 Улучшения — навсегда",
    ]
    
    if prestige_level >= 10:
        text_lines.append("👤 Фермеры — автобот (с 10 прест)")
    
    text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Добавляем информацию о сезонном событии
    if event and event.get('is_active', False):
        try:
            from datetime import datetime
            end_date = event.get('end_date')
            
            if end_date:
                if isinstance(end_date, str):
                    try:
                        if 'T' in end_date:
                            end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                        else:
                            end_date = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
                    except (ValueError, AttributeError):
                        end_date = None
                
                if end_date:
                    if end_date.tzinfo is None:
                        now = datetime.now()
                    else:
                        now = datetime.now(end_date.tzinfo)
                    
                    time_left = end_date - now
                    days_left = time_left.days
                    hours_left = int(time_left.total_seconds() // 3600) % 24
                    
                    if days_left > 0:
                        time_str = f"{days_left} дн. {hours_left} ч."
                    else:
                        time_str = f"{hours_left} ч."
                    
                    event_icon = event.get('icon', '🎉')
                    event_name = event.get('name', 'Событие')
                    text_lines.append("")
                    text_lines.append(f"Сезонное: {event_icon} {event_name} (осталось {time_str})")
        except Exception as e:
            import logging
            logging.warning(f"Error parsing event date: {e}")
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=get_shop_keyboard(prestige_level, event),
        parse_mode="HTML"
    )
 
@router.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.delete()
    await show_farm(callback.from_user.id, callback.message)

# ==================== ИНВЕНТАРЬ (ТЗ v4.0 п.6) ===================

@router.message(Command("inv"))
@router.message(Command("инвентарь"))
@router.message(Command("амбар"))
@router.message(Command("склад"))
@router.message(F.text == "📦 Инв")
@router.message(F.text == "📦 Амбар")
async def inventory_handler(message: Message):
    """Инвентарь игрока согласно ТЗ v4.0 п.6.1"""
    db = await get_db()
    
    # Получаем данные пользователя
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден!")
        return
    
    # Получаем полный инвентарь
    inventory_data = await db.get_inventory_full(message.from_user.id)
    
    # Формируем текст согласно ТЗ
    total_items = inventory_data.get('total_items', 0)
    max_capacity = inventory_data.get('max_capacity', 100)
    total_value = inventory_data.get('total_value', 0)
    
    multiplier = user.get('prestige_multiplier', 1.0)
    total_value_with_multiplier = int(total_value * multiplier)
    
    text_lines = [
        f"📦 <b>ИНВЕНТАРЬ</b> (вместимость: {total_items}/{max_capacity})",
        ""
    ]
    
    # Семена
    seeds = inventory_data.get('seeds', {})
    if seeds:
        text_lines.append("🌱 <b>СЕМЕНА:</b>")
        for item_code, item in seeds.items():
            value = int(item.get('value', 0) * multiplier)
            text_lines.append(f"• {item.get('icon', '🌱')} {item.get('name', item_code)}: {item.get('quantity', 0)} шт — {value:,}🪙")
        text_lines.append("")
    
    # Удобрения
    fertilizers = inventory_data.get('fertilizers', {})
    if fertilizers:
        text_lines.append("🧪 <b>УДОБРЕНИЯ:</b>")
        for item_code, item in fertilizers.items():
            value = int(item.get('value', 0) * multiplier)
            text_lines.append(f"• {item.get('icon', '🧪')} {item.get('name', item_code)}: {item.get('quantity', 0)} шт — {value:,}🪙")
        text_lines.append("")
    
    # Улучшения (активные)
    upgrades = inventory_data.get('upgrades', {})
    if upgrades:
        text_lines.append("🚜 <b>УЛУЧШЕНИЯ (активны):</b>")
        for item_code, item in upgrades.items():
            effect = ""
            if 'plot' in item_code.lower():
                effect = "(+1 грядка)"
            elif 'barn' in item_code.lower() or 'storage' in item_code.lower():
                effect = f"(+{item.get('effect_value', 50)}% места)"
            text_lines.append(f"• {item.get('icon', '🚜')} {item.get('name', item_code)} {effect}")
        text_lines.append("")
    
    # Прочее
    other = inventory_data.get('other', {})
    if other:
        text_lines.append("🎁 <b>ПРОЧЕЕ:</b>")
        for item_code, item in other.items():
            text_lines.append(f"• {item.get('icon', '🎁')} {item.get('name', item_code)}: {item.get('quantity', 0)} шт")
        text_lines.append("")
    
    # Итоговая стоимость
    text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    text_lines.append(f"💰 Общая стоимость: {total_value_with_multiplier:,}🪙")
    
    # Если инвентарь пуст
    if total_items == 0:
        text_lines = [
            "📦 <b>ИНВЕНТАРЬ</b> (вместимость: 0/{max_capacity})",
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━",
            "Пусто! Купи семена в 🏪 Магазине.",
            "━━━━━━━━━━━━━━━━━━━━━━━"
        ]
    
    # Формируем клавиатуру
    keyboard = get_inventory_keyboard(inventory_data, multiplier)
    
    await message.answer(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )
 

@router.callback_query(F.data == "back_inventory")
async def back_to_inventory(callback: CallbackQuery):
    """Возврат в инвентарь"""
    db = await get_db()
    
    # Получаем данные пользователя
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Ошибка: пользователь не найден!")
        return
    
    # Получаем полный инвентарь
    inventory_data = await db.get_inventory_full(callback.from_user.id)
    
    # Формируем текст
    total_items = inventory_data.get('total_items', 0)
    max_capacity = inventory_data.get('max_capacity', 100)
    total_value = inventory_data.get('total_value', 0)
    
    multiplier = user.get('prestige_multiplier', 1.0)
    total_value_with_multiplier = int(total_value * multiplier)
    
    text_lines = [
        f"📦 <b>ИНВЕНТАРЬ</b> (вместимость: {total_items}/{max_capacity})",
        ""
    ]
    
    # Семена
    seeds = inventory_data.get('seeds', {})
    if seeds:
        text_lines.append("🌱 <b>СЕМЕНА:</b>")
        for item_code, item in seeds.items():
            value = int(item.get('value', 0) * multiplier)
            text_lines.append(f"• {item.get('icon', '🌱')} {item.get('name', item_code)}: {item.get('quantity', 0)} шт — {value:,}🪙")
        text_lines.append("")
    
    # Удобрения
    fertilizers = inventory_data.get('fertilizers', {})
    if fertilizers:
        text_lines.append("🧪 <b>УДОБРЕНИЯ:</b>")
        for item_code, item in fertilizers.items():
            value = int(item.get('value', 0) * multiplier)
            text_lines.append(f"• {item.get('icon', '🧪')} {item.get('name', item_code)}: {item.get('quantity', 0)} шт — {value:,}🪙")
        text_lines.append("")
    
    # Улучшения
    upgrades = inventory_data.get('upgrades', {})
    if upgrades:
        text_lines.append("🚜 <b>УЛУЧШЕНИЯ (активны):</b>")
        for item_code, item in upgrades.items():
            effect = ""
            if 'plot' in item_code.lower():
                effect = "(+1 грядка)"
            elif 'barn' in item_code.lower() or 'storage' in item_code.lower():
                effect = f"(+{item.get('effect_value', 50)}% места)"
            text_lines.append(f"• {item.get('icon', '🚜')} {item.get('name', item_code)} {effect}")
        text_lines.append("")
    
    # Прочее
    other = inventory_data.get('other', {})
    if other:
        text_lines.append("🎁 <b>ПРОЧЕЕ:</b>")
        for item_code, item in other.items():
            text_lines.append(f"• {item.get('icon', '🎁')} {item.get('name', item_code)}: {item.get('quantity', 0)} шт")
        text_lines.append("")
    
    text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    text_lines.append(f"💰 Общая стоимость: {total_value_with_multiplier:,}🪙")
    
    if total_items == 0:
        text_lines = [
            "📦 <b>ИНВЕНТАРЬ</b> (вместимость: 0/{max_capacity})",
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━",
            "Пусто! Купи семена в 🏪 Магазине.",
            "━━━━━━━━━━━━━━━━━━━━━━━"
        ]
    
    keyboard = get_inventory_keyboard(inventory_data, multiplier)
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("inv_category_"))
async def inventory_category(callback: CallbackQuery):
    """Просмотр категории инвентаря"""
    category = callback.data.replace("inv_category_", "")
    
    db = await get_db()
    
    # Получаем данные пользователя
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Ошибка: пользователь не найден!")
        return
    
    multiplier = user.get('prestige_multiplier', 1.0)
    
    # Получаем инвентарь
    inventory_data = await db.get_inventory_full(callback.from_user.id)
    
    # Получаем нужную категорию
    category_names = {
        'seed': '🌱 СЕМЕНА',
        'fertilizer': '🧪 УДОБРЕНИЯ',
        'upgrade': '🚜 УЛУЧШЕНИЯ',
        'other': '🎁 ПРОЧЕЕ'
    }
    
    items = inventory_data.get(f"{category}s", {}) if category != 'other' else inventory_data.get('other', {})
    
    if not items:
        await callback.answer("📭 Категория пуста!")
        return
    
    # Формируем текст
    text_lines = [
        f"{category_names.get(category, category.upper())}",
        ""
    ]
    
    for item_code, item in items.items():
        icon = item.get('icon', '📦')
        name = item.get('name', item_code)
        quantity = item.get('quantity', 0)
        value = int(item.get('value', 0) * multiplier)
        
        text_lines.append(f"{icon} {name}: {quantity} шт — {value:,}🪙")
    
    # Формируем клавиатуру
    keyboard = get_inventory_category_keyboard(category, items, multiplier)
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("inv_item_"))
async def inventory_item_detail(callback: CallbackQuery):
    """Детальный просмотр предмета согласно ТЗ v4.0 п.6.2"""
    item_code = callback.data.replace("inv_item_", "")
    
    db = await get_db()
    
    # Получаем данные пользователя
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Ошибка: пользователь не найден!")
        return
    
    multiplier = user.get('prestige_multiplier', 1.0)
    user_level = user.get('city_level', 1)
    
    # Получаем информацию о предмете
    item_data = await db.get_inventory_item(callback.from_user.id, item_code)
    
    if not item_data:
        await callback.answer("❌ Предмет не найден в инвентаре!")
        return
    
    # Получаем количество пустых грядок для семян
    empty_plots = 0
    if item_data.get('category') == 'seed':
        plots = await db.get_plots(callback.from_user.id)
        empty_plots = sum(1 for p in plots if p.get('status') == 'empty')
    
    # Формируем текст согласно ТЗ
    icon = item_data.get('icon', '📦')
    name = item_data.get('name', item_code)
    quantity = item_data.get('quantity', 0)
    sell_price = item_data.get('sell_price', 0)
    growth_time = item_data.get('growth_time', 0)
    required_level = item_data.get('required_level', 1)
    category = item_data.get('category', 'other')
    
    # Цена продажи с множителем
    value_with_multiplier = int(sell_price * quantity * multiplier)
    
    text_lines = [
        f"{icon} <b>{name.upper()}</b> ({quantity} шт)",
        "",
        "📊 <b>Информация:</b>"
    ]
    
    # Для семян и удобрений показываем цену продажи
    if category in ['seed', 'fertilizer'] and sell_price > 0:
        text_lines.append(f"• Можно продать за {value_with_multiplier:,}🪙 (с x{multiplier:.1f})")
    
    # Для семян показываем дополнительную информацию
    if category == 'seed':
        if empty_plots > 0:
            text_lines.append(f"• Можно посадить ({min(quantity, empty_plots)} грядок)")
        else:
            text_lines.append(f"• Нет свободных грядок для посадки")
        
        if required_level > 1:
            text_lines.append(f"• Требуется уровень: {required_level}")
        
        # Информация о доходе при посадке
        if growth_time > 0:
            minutes = growth_time // 60
            text_lines.append("")
            text_lines.append("📈 <b>При посадке даст:</b>")
            text_lines.append(f"• Доход: ~{value_with_multiplier:,}🪙 через {minutes} мин")
            text_lines.append(f"• Опыт: +{quantity * 5} за штуку")
    
    # Для удобрений показываем эффект
    elif category == 'fertilizer':
        effect_type = item_data.get('effect_type')
        effect_value = item_data.get('effect_value')
        
        if effect_type == 'speed':
            text_lines.append(f"• Ускоряет рост на {int(effect_value * 100)}%")
        elif effect_type == 'instant':
            text_lines.append(f"• Мгновенное созревание")
        elif effect_type == 'bonus':
            text_lines.append(f"• +{int(effect_value * 100)}% к доходу")
    
    # Формируем клавиатуру
    keyboard = get_inventory_item_keyboard(item_data, multiplier, empty_plots)
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("inv_sell_"))
async def inventory_sell_item(callback: CallbackQuery):
    """Продажа предмета из инвентаря"""
    data = callback.data.replace("inv_sell_", "")
    
    # Обработка продажи всех предметов
    if data == "all":
        db = await get_db()
        user = await db.get_user(callback.from_user.id)
        if not user:
            await callback.answer("❌ Ошибка: пользователь не найден!")
            return
        
        multiplier = user.get('prestige_multiplier', 1.0)
        inventory_data = await db.get_inventory_full(callback.from_user.id)
        
        # Продаём все семена и удобрения
        sellable = {**inventory_data.get('seeds', {}), **inventory_data.get('fertilizers', {})}
        
        if not sellable:
            await callback.answer("❌ Нет предметов для продажи!")
            return
        
        total_earned = 0
        sold_items = []
        
        for item_code, item in sellable.items():
            quantity = item.get('quantity', 0)
            if quantity > 0:
                result = await db.sell_inventory_item(
                    callback.from_user.id,
                    item_code,
                    quantity,
                    multiplier
                )
                
                if result.get('success'):
                    total_earned += result.get('earned', 0)
                    sold_items.append(f"{item.get('icon', '📦')} {item.get('name', item_code)} x{quantity}")
        
        if total_earned > 0:
            # Обновляем квесты
            await db.update_quest_progress(callback.from_user.id, 'sell', total_earned)
            
            # Проверяем ачивки
            await db.check_and_update_achievements(callback.from_user.id, 'sell', count=total_earned)
            await db.check_and_update_achievements(callback.from_user.id, 'earn', count=total_earned)
            
            text = (
                f"✅ <b>ПРОДАЖА ЗАВЕРШЕНА!</b>\n\n"
                f"Продано:\n{chr(10).join(['• ' + i for i in sold_items])}\n\n"
                f"💰 Итого: +{total_earned:,}🪙"
            )
            
            await callback.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📦 В инвентарь", callback_data="back_inventory")]
                ]),
                parse_mode="HTML"
            )
        else:
            await callback.answer("❌ Ошибка продажи!")
        return
    
    # Обработка продажи конкретного предмета
    parts = data.split("_")
    if len(parts) < 2:
        await callback.answer("❌ Неверный формат данных!")
        return
    
    item_code = parts[0]
    try:
        quantity = int(parts[1])
    except ValueError:
        await callback.answer("❌ Неверное количество!")
        return
    
    db = await get_db()
    
    # Получаем данные пользователя
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Ошибка: пользователь не найден!")
        return
    
    multiplier = user.get('prestige_multiplier', 1.0)
    
    # Продаём предмет
    result = await db.sell_inventory_item(
        callback.from_user.id,
        item_code,
        quantity,
        multiplier
    )
    
    if result.get('success'):
        earned = result.get('earned', 0)
        item_name = result.get('item_name', item_code)
        
        # Обновляем квесты
        await db.update_quest_progress(callback.from_user.id, 'sell', earned)
        
        # Проверяем ачивки
        await db.check_and_update_achievements(callback.from_user.id, 'sell', count=earned)
        await db.check_and_update_achievements(callback.from_user.id, 'earn', count=earned)
        
        await callback.answer(f"✅ Продано {item_name} x{quantity}! +{earned:,}🪙")
        
        # Возвращаемся в инвентарь
        await back_to_inventory(callback)
    else:
        await callback.answer(f"❌ {result.get('message', 'Ошибка продажи')}")


@router.callback_query(F.data == "inv_sell")
async def inventory_sell_menu(callback: CallbackQuery):
    """Меню продажи из инвентаря"""
    db = await get_db()
    
    # Получаем данные пользователя
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Ошибка: пользователь не найден!")
        return
    
    multiplier = user.get('prestige_multiplier', 1.0)
    
    # Получаем инвентарь
    inventory_data = await db.get_inventory_full(callback.from_user.id)
    
    # Продаём только семена и удобрения
    sellable = {**inventory_data.get('seeds', {}), **inventory_data.get('fertilizers', {})}
    
    if not sellable:
        await callback.answer("❌ Нет предметов для продажи!")
        return
    
    total_value = sum(int(d.get('value', 0) * multiplier) for d in sellable.values())
    
    text_lines = [
        "💰 <b>ПРОДАЖА ПРЕДМЕТОВ</b>",
        "",
        "Твой инвентарь:",
        "━━━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    for item_code, item in sellable.items():
        icon = item.get('icon', '📦')
        name = item.get('name', item_code)
        quantity = item.get('quantity', 0)
        value = int(item.get('value', 0) * multiplier)
        text_lines.append(f"{icon} {name}: {quantity} шт — {value:,}🪙")
    
    text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    text_lines.append(f"💰 Всего: {total_value:,}🪙 (с учетом множителя)")
    text_lines.append("")
    text_lines.append("Что продаем?")
    
    # Формируем клавиатуру
    keyboard = get_inventory_sell_keyboard(sellable, multiplier)
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("inv_plant_"))
async def inventory_plant_item(callback: CallbackQuery):
    """Посадка семян из инвентаря"""
    data = callback.data.replace("inv_plant_", "")
    parts = data.split("_")
    
    if len(parts) < 2:
        await callback.answer("❌ Неверный формат данных!")
        return
    
    item_code = parts[0]
    try:
        quantity = int(parts[1])
    except ValueError:
        await callback.answer("❌ Неверное количество!")
        return
    
    db = await get_db()
    
    # Получаем данные пользователя
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Ошибка: пользователь не найден!")
        return
    
    # Проверяем наличие в инвентаре
    item_data = await db.get_inventory_item(callback.from_user.id, item_code)
    
    if not item_data or item_data.get('quantity', 0) < quantity:
        await callback.answer("❌ Недостаточно семян в инвентаре!")
        return
    
    # Получаем пустые грядки
    plots = await db.get_plots(callback.from_user.id)
    empty_plots = [p for p in plots if p.get('status') == 'empty']
    
    if not empty_plots:
        await callback.answer("❌ Нет свободных грядок!")
        return
    
    # Получаем информацию о семенах
    crop_info = await db.get_shop_item(item_code)
    if not crop_info:
        await callback.answer("❌ Ошибка: культура не найдена!")
        return
    
    # Проверка уровня
    required_level = crop_info.get('required_level', 1)
    if user.get('city_level', 1) < required_level:
        await callback.answer(f"❌ Требуется уровень {required_level}!")
        return
    
    # Сажаем на доступные грядки
    planted = 0
    growth_time = crop_info.get('growth_time', 120)
    
    for plot in empty_plots[:quantity]:
        try:
            await db.plant_crop(callback.from_user.id, plot['number'], item_code, growth_time)
            planted += 1
        except Exception as e:
            import logging
            logging.error(f"Error planting crop: {e}")
    
    if planted > 0:
        # Удаляем из инвентаря
        await db.remove_inventory(callback.from_user.id, item_code, planted)
        
        # Обновляем статистику
        await db.execute(
            "UPDATE users SET total_planted = total_planted + ? WHERE user_id = ?",
            (planted, callback.from_user.id), commit=True
        )
        
        # Обновляем квесты
        await db.update_quest_progress(callback.from_user.id, 'plant', planted)
        
        # Проверяем ачивки
        await db.check_and_update_achievements(callback.from_user.id, 'plant', count=planted)
        
        crop_name = crop_info.get('name', item_code)
        crop_icon = crop_info.get('icon', '🌱')
        
        await callback.answer(f"✅ Посажено {crop_icon} {crop_name} x{planted}!")
        await show_farm(callback.from_user.id, callback.message)
    else:
        await callback.answer("❌ Не удалось посадить!")


@router.callback_query(F.data == "inv_sort")
async def inventory_sort(callback: CallbackQuery):
    """Сортировка инвентаря"""
    await callback.answer("📊 Сортировка в разработке!")

# =================== ПРЕСТИЖ (ТЗ v4.0 п.9) ===================

# Константы для системы престижа
PRESTIGE_REQUIRED_LEVEL = 50

@router.message(F.text == "🚜 Престиж")
async def prestige_handler(message: Message):
    """Главное меню престижа согласно ТЗ v4.0 п.9.1"""
    db = await get_db()
    user = await db.get_user(message.from_user.id)
    
    if not user:
        await message.answer("❌ Сначала начни игру командой /start")
        return
    
    current_prestige = user.get('prestige_level', 1)
    current_multiplier = user.get('prestige_multiplier', 1.0)
    current_level = user.get('level', 1)
    current_xp = user.get('xp', 0)
    
    # Проверяем готовность к престижу
    prestige_ready = await db.check_prestige_ready(message.from_user.id)
    
    # Получаем прогресс XP
    xp_progress = await db.get_xp_progress(message.from_user.id)
    
    # Прогресс-бар до 50 уровня
    xp_for_50 = await db.get_xp_for_level(PRESTIGE_REQUIRED_LEVEL)
    xp_progress_to_50 = min(100, (current_xp / xp_for_50 * 100)) if xp_for_50 > 0 else 0
    filled = int(xp_progress_to_50 / 10)
    empty = 10 - filled
    progress_bar = "█" * filled + "░" * empty
    
    # Формируем текст
    text_lines = [
        "🚜 <b>СИСТЕМА ПРЕСТИЖА</b>",
        "",
        f"🏆 <b>Текущий престиж: {current_prestige}</b>",
        f"📊 Множитель дохода: x{current_multiplier:.1f}",
        f"⭐ Уровень: {current_level}",
        f"💫 Опыт: {current_xp:,}",
        "",
        f"📈 <b>Прогресс до следующего престижа:</b>",
        f"   {progress_bar} {xp_progress_to_50:.1f}%",
        f"   Цель: {PRESTIGE_REQUIRED_LEVEL} уровень",
    ]
    
    if prestige_ready.get('is_ready'):
        text_lines.append("")
        text_lines.append("✅ <b>Ты готов к повышению престижа!</b>")
    else:
        levels_needed = prestige_ready.get('levels_needed', PRESTIGE_REQUIRED_LEVEL - current_level)
        text_lines.append(f"   Осталось уровней: {levels_needed}")
    
    text_lines.append("")
    text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    text_lines.append("💡 <b>Формула дохода:</b>")
    text_lines.append("   Доход = База × (1 + Престиж × 0.1)")
    text_lines.append(f"   Твой бонус: +{(current_prestige * 10)}% к доходу")
    
    # Клавиатура
    keyboard_rows = []
    
    if prestige_ready.get('is_ready'):
        keyboard_rows.append([
            InlineKeyboardButton(text="⬆️ Повысить престиж", callback_data="prestige_confirm")
        ])
    
    keyboard_rows.extend([
        [
            InlineKeyboardButton(text="ℹ️ Подробнее", callback_data="prestige_info"),
            InlineKeyboardButton(text="📊 Калькулятор", callback_data="prestige_calc")
        ],
        [InlineKeyboardButton(text="🔙 В меню", callback_data="back_main")]
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    await message.answer("\n".join(text_lines), reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "prestige_info")
async def prestige_info_callback(callback: CallbackQuery):
    """Детальная информация о системе престижа - ТЗ v4.0 п.9.2"""
    db = await get_db()
    user = await db.get_user(callback.from_user.id)
    
    current_prestige = user.get('prestige_level', 1) if user else 1
    
    text = """🚜 <b>СИСТЕМА ПРЕСТИЖА — ПОДРОБНЕЕ</b>

<b>📋 Как это работает:</b>
• Престиж повышается при достижении <b>50 уровня</b>
• При повышении уровень и опыт сбрасываются
• Множитель дохода увеличивается на +0.1 за каждый престиж

<b>📊 Формула дохода:</b>
<code>Доход = База × (1 + Престиж × 0.1)</code>

<b>Примеры:</b>
• Престиж 1: x1.1 (бонус +10%)
• Престиж 5: x1.5 (бонус +50%)
• Престиж 10: x2.0 (бонус +100%)
• Престиж 20: x3.0 (бонус +200%)

<b>🎁 Особые награды:</b>
━━━━━━━━━━━━━━━━━━━━━━━
• <b>Престиж 5</b> — Титул "Опытный фермер" + 50💎
• <b>Престиж 10</b> — Титул "Мастер фермер" + 100💎
• <b>Престиж 20</b> — Титул "Легенда фермерства" + 200💎
• <b>Престиж 50</b> — Титул "Божественный фермер" + 500💎
• <b>Престиж 100</b> — Титул "Фермер-бог" + 1000💎

<b>⚠️ Важно:</b>
• После престижа весь прогресс уровня сбрасывается
• Баланс и инвентарь сохраняются
• Множитель действует на весь доход"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Калькулятор дохода", callback_data="prestige_calc")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="prestige_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "prestige_calc")
async def prestige_calculator_callback(callback: CallbackQuery):
    """Калькулятор дохода - ТЗ v4.0 п.9.3"""
    db = await get_db()
    user = await db.get_user(callback.from_user.id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    current_prestige = user.get('prestige_level', 1)
    current_multiplier = user.get('prestige_multiplier', 1.0)
    next_prestige = current_prestige + 1
    next_multiplier = 1 + next_prestige * 0.1
    
    # Примеры расчёта дохода для разных культур
    # Получаем список растений из магазина
    plants = await db.get_shop_items(category='seed')
    
    # Берём первые 3 растения для примера
    example_plants = plants[:3] if plants else [
        {"name": "Картофель", "icon": "🥔", "sell_price": 5},
        {"name": "Помидор", "icon": "🍅", "sell_price": 12},
        {"name": "Клубника", "icon": "🍓", "sell_price": 60}
    ]
    
    text_lines = [
        "📊 <b>КАЛЬКУЛЯТОР ДОХОДА</b>",
        "",
        f"🏆 Твой престиж: <b>{current_prestige}</b>",
        f"📈 Текущий множитель: <b>x{current_multiplier:.1f}</b>",
        f"⬆️ Следующий престиж: <b>{next_prestige}</b>",
        f"📈 Множитель след. престижа: <b>x{next_multiplier:.1f}</b>",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━",
        "💰 <b>СРАВНЕНИЕ ДОХОДА:</b>",
        ""
    ]
    
    for plant in example_plants:
        name = plant.get('name', 'Растение')
        icon = plant.get('icon', '🌱')
        base_price = plant.get('sell_price', 10)
        
        current_income = int(base_price * current_multiplier)
        next_income = int(base_price * next_multiplier)
        diff = next_income - current_income
        
        text_lines.append(f"{icon} <b>{name}</b>")
        text_lines.append(f"   База: {base_price}🪙")
        text_lines.append(f"   Сейчас: {current_income}🪙 → После: {next_income}🪙")
        text_lines.append(f"   Разница: +{diff}🪙 ({(diff/current_income*100):.1f}%)")
        text_lines.append("")
    
    # Общий пример
    text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    text_lines.append("💡 <b>ПРИМЕР НА 100 СБОРОК:</b>")
    
    # Средний доход
    avg_base = sum(p.get('sell_price', 10) for p in example_plants) / len(example_plants)
    current_total = int(avg_base * current_multiplier * 100)
    next_total = int(avg_base * next_multiplier * 100)
    total_diff = next_total - current_total
    
    text_lines.append(f"   Сейчас: {current_total:,}🪙")
    text_lines.append(f"   После престижа: {next_total:,}🪙")
    text_lines.append(f"   Доп. доход: +{total_diff:,}🪙")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ℹ️ Подробнее о престиже", callback_data="prestige_info")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="prestige_back")]
    ])
    
    await callback.message.edit_text("\n".join(text_lines), reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "prestige_back")
async def prestige_back_callback(callback: CallbackQuery):
    """Возврат к главному меню престижа"""
    db = await get_db()
    user = await db.get_user(callback.from_user.id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    current_prestige = user.get('prestige_level', 1)
    current_multiplier = user.get('prestige_multiplier', 1.0)
    current_level = user.get('level', 1)
    current_xp = user.get('xp', 0)
    
    prestige_ready = await db.check_prestige_ready(callback.from_user.id)
    
    xp_for_50 = await db.get_xp_for_level(PRESTIGE_REQUIRED_LEVEL)
    xp_progress = min(100, (current_xp / xp_for_50 * 100)) if xp_for_50 > 0 else 0
    filled = int(xp_progress / 10)
    empty = 10 - filled
    progress_bar = "█" * filled + "░" * empty
    
    text_lines = [
        "🚜 <b>СИСТЕМА ПРЕСТИЖА</b>",
        "",
        f"🏆 <b>Текущий престиж: {current_prestige}</b>",
        f"📊 Множитель дохода: x{current_multiplier:.1f}",
        f"⭐ Уровень: {current_level}",
        f"💫 Опыт: {current_xp:,}",
        "",
        f"📈 <b>Прогресс до следующего престижа:</b>",
        f"   {progress_bar} {xp_progress:.1f}%",
        f"   Цель: {PRESTIGE_REQUIRED_LEVEL} уровень",
    ]
    
    if prestige_ready.get('is_ready'):
        text_lines.append("")
        text_lines.append("✅ <b>Ты готов к повышению престижа!</b>")
    else:
        levels_needed = prestige_ready.get('levels_needed', PRESTIGE_REQUIRED_LEVEL - current_level)
        text_lines.append(f"   Осталось уровней: {levels_needed}")
    
    keyboard_rows = []
    
    if prestige_ready.get('is_ready'):
        keyboard_rows.append([
            InlineKeyboardButton(text="⬆️ Повысить престиж", callback_data="prestige_confirm")
        ])
    
    keyboard_rows.extend([
        [
            InlineKeyboardButton(text="ℹ️ Подробнее", callback_data="prestige_info"),
            InlineKeyboardButton(text="📊 Калькулятор", callback_data="prestige_calc")
        ],
        [InlineKeyboardButton(text="🔙 В меню", callback_data="back_main")]
    ])
    
    await callback.message.edit_text("\n".join(text_lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "prestige_confirm")
async def prestige_confirm_callback(callback: CallbackQuery):
    """Подтверждение повышения престижа"""
    db = await get_db()
    user = await db.get_user(callback.from_user.id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    current_prestige = user.get('prestige_level', 1)
    current_level = user.get('level', 1)
    next_prestige = current_prestige + 1
    next_multiplier = 1 + next_prestige * 0.1
    
    # Проверяем готовность
    if current_level < PRESTIGE_REQUIRED_LEVEL:
        await callback.answer(f"❌ Нужно достичь {PRESTIGE_REQUIRED_LEVEL} уровня!", show_alert=True)
        return
    
    text = f"""⚠️ <b>ПОДТВЕРЖДЕНИЕ ПРЕСТИЖА</b>

<b>Текущий статус:</b>
• Престиж: {current_prestige}
• Уровень: {current_level}
• Множитель: x{user.get('prestige_multiplier', 1.0):.1f}

<b>После повышения:</b>
• Престиж: {next_prestige}
• Уровень: 1 (сброс)
• Опыт: 0 (сброс)
• Множитель: x{next_multiplier:.1f}

<b>Сохраняется:</b>
✅ Баланс и кристаллы
✅ Инвентарь
✅ Достижения

<b>Сбрасывается:</b>
❌ Уровень → 1
❌ Опыт → 0

Подтвердить повышение престижа?"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, повысить!", callback_data="prestige_do"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="prestige_back")
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "prestige_do")
async def prestige_do_callback(callback: CallbackQuery):
    """Выполнение повышения престижа"""
    db = await get_db()
    
    result = await db.do_prestige(callback.from_user.id)
    
    if result.get('success'):
        new_prestige = result.get('new_prestige')
        new_multiplier = result.get('new_multiplier')
        
        # Проверяем особые награды
        rewards = await db.get_prestige_rewards(new_prestige)
        
        text = f"""🎉 <b>ПОЗДРАВЛЯЕМ!</b>

🚜 <b>Престиж повышен до {new_prestige}!</b>
📈 Новый множитель дохода: x{new_multiplier:.1f}

<b>🎁 Награды:</b>
💰 {rewards.get('coins', 0):,} монет
💎 {rewards.get('gems', 0)} кристаллов"""
        
        # Выдаём награды
        if rewards.get('coins', 0) > 0:
            await db.update_balance(callback.from_user.id, rewards['coins'])
        if rewards.get('gems', 0) > 0:
            await db.execute(
                "UPDATE users SET gems = COALESCE(gems, 0) + ? WHERE user_id = ?",
                (rewards['gems'], callback.from_user.id), commit=True
            )
        
        # Особые предметы
        if rewards.get('items'):
            for item_code, qty in rewards['items'].items():
                await db.add_inventory(callback.from_user.id, item_code, qty)
                item_info = await db.get_shop_item(item_code)
                icon = item_info.get('icon', '📦') if item_info else '📦'
                text += f"\n{icon} x{qty}"
        
        # Особый титул
        if rewards.get('title'):
            text += f"\n\n🏅 Новый титул: {rewards['title']}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚜 К престижу", callback_data="prestige_back")],
            [InlineKeyboardButton(text="🌾 На ферму", callback_data="back_farm")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer("🎉 Престиж повышен!")
    else:
        await callback.answer(f"❌ {result.get('message', 'Ошибка')}", show_alert=True)

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
    
# =================== ТОП ИГРОКОВ (ТЗ v4.0 п.17) ===================

@router.message(Command("top"))
async def top_handler(message: Message):
    """Таблица лидеров - главное меню"""
    await show_leaderboard(message.from_user.id, message, 'balance')


async def show_leaderboard(user_id: int, obj: Message | CallbackQuery, category: str = 'balance'):
    """Показывает таблицу лидеров по категории
    
    Args:
        user_id: ID пользователя
        obj: Message или CallbackQuery
        category: Категория (balance, gems, harvest, prestige)
    """
    db = await get_db()
    
    # Получаем данные лидерборда
    leaderboard = await db.get_leaderboard(category, limit=10, user_id=user_id)
    
    if not leaderboard['players']:
        text = "🏆 Пока нет игроков в топе!"
        if isinstance(obj, CallbackQuery):
            await obj.message.edit_text(text)
        else:
            await obj.answer(text)
        return
    
    # Заголовки для категорий
    category_titles = {
        'balance': '💰 ПО БАЛАНСУ',
        'gems': '💎 ПО КРИСТАЛЛАМ',
        'harvest': '🌾 ПО УРОЖАЮ',
        'prestige': '🚜 ПО ПРЕСТИЖУ'
    }
    
    title = category_titles.get(category, '🏆 ТОП ИГРОКОВ')
    
    text_lines = [f"🏆 <b>ТОП ИГРОКОВ</b>\n", f"━━━━━━━━━━━━━━━━━━━━━━━", f"{title}:", ""]
    
    medals = ["🥇", "🥈", "🥉"]
    
    for player in leaderboard['players']:
        rank = player['rank']
        medal = medals[rank - 1] if rank <= 3 else f"{rank}."
        name = player['first_name'] or player['username'] or "Фермер"
        
        # Форматируем значение в зависимости от категории
        if category == 'balance':
            value = f"{player['balance']:,}🪙"
        elif category == 'gems':
            value = f"{player['gems']:,}💎"
        elif category == 'harvest':
            harvested = player['total_harvested']
            if harvested >= 1_000_000:
                value = f"{harvested / 1_000_000:.1f}M растений"
            elif harvested >= 1_000:
                value = f"{harvested / 1_000:.1f}K растений"
            else:
                value = f"{harvested} растений"
        else:  # prestige
            value = f"Престиж {player['prestige_level']} (x{player['prestige_multiplier']:.1f})"
        
        # Отмечаем текущего пользователя
        if player['is_current_user']:
            text_lines.append(f"{medal} <b>{name}</b> — {value} 👈")
        else:
            text_lines.append(f"{medal} {name} — {value}")
    
    # Добавляем информацию о месте пользователя
    if leaderboard['user_rank'] and leaderboard['user_stats']:
        user_stats = leaderboard['user_stats']
        rank = leaderboard['user_rank']
        
        text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
        
        if category == 'balance':
            your_value = f"{user_stats['balance']:,}🪙"
        elif category == 'gems':
            your_value = f"{user_stats['gems']:,}💎"
        elif category == 'harvest':
            your_value = f"{user_stats['total_harvested']:,} растений"
        else:
            your_value = f"Престиж {user_stats['prestige_level']}"
        
        text_lines.append(f"📍 Ты на <b>{rank}</b> месте с {your_value}")
    
    # Формируем клавиатуру с переключением категорий
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 Баланс", callback_data="top_balance"),
            InlineKeyboardButton(text="💎 Кристаллы", callback_data="top_gems"),
        ],
        [
            InlineKeyboardButton(text="🌾 Урожай", callback_data="top_harvest"),
            InlineKeyboardButton(text="🚜 Престиж", callback_data="top_prestige"),
        ],
        [InlineKeyboardButton(text="🔙 В меню", callback_data="back_main")]
    ])
    
    text = "\n".join(text_lines)
    
    if isinstance(obj, CallbackQuery):
        await obj.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await obj.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("top_"))
async def top_category_callback(callback: CallbackQuery):
    """Переключение категории в топе"""
    category = callback.data.replace("top_", "")
    
    if category in ['balance', 'gems', 'harvest', 'prestige']:
        await show_leaderboard(callback.from_user.id, callback, category)
    else:
        await callback.answer("❌ Неизвестная категория")


# =================== СИСТЕМА ФЕРМЕРОВ (ТЗ v4.0 п.11) ===================

@router.message(F.text == "👤 Фермер")
@router.message(Command("farmers"))
async def farmers_handler(message: Message):
    """Меню управления фермерами согласно ТЗ v4.0 п.11.2"""
    db = await get_db()
    user = await db.get_user(message.from_user.id)
    
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден!")
        return
    
    prestige_level = user.get('prestige_level', 1)
    
    # Проверяем доступность (с 10 престижа)
    if prestige_level < 10:
        text = (
            "🔒 <b>СИСТЕМА ФЕРМЕРОВ</b>\n\n"
            f"Твой престиж: {prestige_level}\n"
            "Требуется: <b>10 престиж</b>\n\n"
            "Фермеры помогают автоматически сажать и собирать урожай!\n\n"
            "Достигни 10 престижа, чтобы открыть возможность найма."
        )
        await message.answer(text, parse_mode="HTML")
        return
    
    # Проверяем есть ли фермер
    farmer = await db.get_user_farmer(message.from_user.id)
    
    if not farmer:
        # Показываем меню найма
        await show_farmer_hire_menu(message, user)
    else:
        # Показываем настройки фермера
        await show_farmer_settings(message, farmer, user)


async def show_farmer_hire_menu(message: Message, user: Dict):
    """Меню найма фермера"""
    db = await get_db()
    farmer_types = await db.get_farmer_types()
    
    balance = user.get('balance', 0)
    gems = user.get('gems', 0)
    prestige_level = user.get('prestige_level', 1)
    
    text_lines = [
        f"👤 <b>НАЕМ ФЕРМЕРОВ</b>",
        f"Твой престиж: {prestige_level} ✅ доступно",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    buttons = []
    for ft in farmer_types:
        icon = ft.get('icon', '👤')
        name = ft.get('name', '???')
        duration = ft.get('duration_days')
        duration_text = f"{duration} дней" if duration else "навсегда"
        bonus = ft.get('bonus_percent', 0)
        uses_fert = ft.get('uses_fertilizer', False)
        
        price_text = ""
        if ft.get('price_coins', 0) > 0:
            price_text = f"{ft['price_coins']:,}🪙"
        if ft.get('price_gems', 0) > 0:
            price_text += f" {ft['price_gems']}💎" if price_text else f"{ft['price_gems']}💎"
        
        text_lines.append(f"{icon} <b>{name}</b>")
        text_lines.append(f"   • Автосажает и автособирает урожай")
        if bonus > 0:
            text_lines.append(f"   • +{bonus}% к доходу")
        if uses_fert:
            text_lines.append(f"   • Использует удобрения")
        text_lines.append(f"   • Работает: {duration_text}")
        text_lines.append(f"   • Цена: {price_text}")
        text_lines.append("")
        
        # Кнопка найма
        can_afford = (balance >= ft.get('price_coins', 0) and 
                     gems >= ft.get('price_gems', 0))
        
        buttons.append(InlineKeyboardButton(
            text=f"{icon} Нанять ({price_text})",
            callback_data=f"hire_farmer_{ft['type_code']}",
        ))
    
    text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    text_lines.append(f"💰 Твой баланс: {balance:,}🪙 | {gems}💎")
    
    # Формируем клавиатуру
    keyboard_rows = [[btn] for btn in buttons]
    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    await message.answer("\n".join(text_lines), reply_markup=keyboard, parse_mode="HTML")


async def show_farmer_settings(message: Message, farmer: Dict, user: Dict):
    """Настройки фермера"""
    db = await get_db()
    
    farmer_id = farmer.get('farmer_id')
    status = farmer.get('status', 'active')
    config = farmer.get('config', {})
    
    # Рассчитываем оставшиеся дни
    from datetime import datetime
    expires_at = farmer.get('expires_at')
    days_left = None
    if expires_at:
        try:
            expires = datetime.fromisoformat(expires_at)
            days_left = (expires - datetime.now()).days + 1
        except:
            pass
    
    # Получаем статистику
    stats = await db.get_farmer_stats(farmer_id)
    
    status_icon = "✅" if status == 'active' else "⏸️" if status == 'paused' else "❌"
    status_text = "Активен" if status == 'active' else "Приостановлен" if status == 'paused' else "Истёк"
    
    text_lines = [
        f"{farmer.get('type_icon', '👤')} <b>НАСТРОЙКА ФЕРМЕРА</b>",
        f"ID: F-{farmer_id}",
        "",
        f"Статус: {status_icon} {status_text}",
    ]
    
    if days_left is not None:
        text_lines.append(f"Осталось дней: {days_left}")
    else:
        text_lines.append("Срок: навсегда")
    
    text_lines.extend([
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━",
        "📋 <b>ЧТО ДЕЛАТЬ?</b>",
        ""
    ])
    
    # Настройки
    preferred_crop = config.get('preferred_crop', 'Все подряд')
    harvest_mode = config.get('harvest_mode', 'sell')
    use_fert = "⚡ Да" if config.get('use_fertilizer', False) else "❌ Нет"
    
    text_lines.extend([
        f"Что сажать: {preferred_crop}",
        f"Что делать с урожаем: {harvest_mode}",
        f"Использовать удобрения: {use_fert}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━",
        "📊 <b>СТАТИСТИКА:</b>",
        f"• Посажено: {stats.get('total_planted', 0)}",
        f"• Собрано: {stats.get('total_harvested', 0)}",
        f"• Заработано: {stats.get('total_earned', 0):,}🪙",
        f"• Потрачено на з/п: {stats.get('total_salary_paid', 0):,}🪙",
    ])
    
    net_profit = stats.get('net_profit', 0)
    if net_profit > 0:
        text_lines.append(f"✅ Чистый доход: +{net_profit:,}🪙")
    else:
        text_lines.append(f"📉 Чистый доход: {net_profit:,}🪙")
    
    # Клавиатура настроек
    keyboard_rows = [
        [InlineKeyboardButton(text="🌱 Что сажать", callback_data=f"farmer_crop_{farmer_id}")],
        [InlineKeyboardButton(text="💰 Режим сбора", callback_data=f"farmer_mode_{farmer_id}")],
    ]
    
    # Кнопка удобрений только для профи
    if farmer.get('uses_fertilizer', False):
        fert_action = "❌ Не использовать удобрения" if config.get('use_fertilizer') else "⚡ Использовать удобрения"
        keyboard_rows.append([InlineKeyboardButton(text=fert_action, callback_data=f"farmer_fert_{farmer_id}")])
    
    # Кнопки управления
    if status == 'active':
        keyboard_rows.append([InlineKeyboardButton(text="⏸️ Приостановить", callback_data=f"farmer_pause_{farmer_id}")])
    else:
        keyboard_rows.append([InlineKeyboardButton(text="▶️ Возобновить", callback_data=f"farmer_resume_{farmer_id}")])
    
    keyboard_rows.append([InlineKeyboardButton(text="❌ Уволить", callback_data=f"farmer_fire_{farmer_id}")])
    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    await message.answer("\n".join(text_lines), reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("hire_farmer_"))
async def hire_farmer_handler(callback: CallbackQuery):
    """Найм фермера"""
    farmer_type = callback.data.replace("hire_farmer_", "")
    
    db = await get_db()
    user = await db.get_user(callback.from_user.id)
    
    if not user:
        await callback.answer("❌ Ошибка: пользователь не найден!", show_alert=True)
        return
    
    # Проверяем престиж
    if user.get('prestige_level', 1) < 10:
        await callback.answer("🔒 Нужен 10 престиж!", show_alert=True)
        return
    
    # Нанимаем фермера
    result = await db.hire_farmer(callback.from_user.id, farmer_type)
    
    if not result.get('success', False):
        await callback.answer(f"❌ {result.get('message', 'Ошибка найма')}", show_alert=True)
        return
    
    await callback.answer(result.get('message', 'Фермер нанят!'))
    
    # Показываем настройки
    farmer = await db.get_user_farmer(callback.from_user.id)
    if farmer:
        await show_farmer_settings(callback.message, farmer, user)


@router.callback_query(F.data.startswith("farmer_crop_"))
async def farmer_select_crop(callback: CallbackQuery):
    """Выбор культуры для фермера"""
    try:
        farmer_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка данных!", show_alert=True)
        return
    
    db = await get_db()
    
    # Получаем доступные семена
    seeds = await db.get_shop_items("seed")
    
    text_lines = [
        "🌱 <b>ВЫБОР КУЛЬТУРЫ</b>",
        "",
        "Выбери, что сажать фермеру:",
        ""
    ]
    
    buttons = []
    buttons.append(InlineKeyboardButton(
        text="🌾 Все подряд",
        callback_data=f"farmer_setcrop_{farmer_id}_all"
    ))
    
    for seed in seeds:
        if seed.get('is_active', True):
            buttons.append(InlineKeyboardButton(
                text=f"{seed.get('icon', '🌱')} {seed.get('name', '???')}",
                callback_data=f"farmer_setcrop_{farmer_id}_{seed['item_code']}"
            ))
    
    # Формируем клавиатуру по 2 в ряд
    keyboard_rows = []
    for i in range(0, len(buttons), 2):
        row = buttons[i:i+2]
        if row:
            keyboard_rows.append(row)
    
    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_farmers")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    await callback.message.edit_text("\n".join(text_lines), reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("farmer_setcrop_"))
async def farmer_set_crop(callback: CallbackQuery):
    """Установка культуры фермеру"""
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer("❌ Ошибка данных!", show_alert=True)
        return
    
    try:
        farmer_id = int(parts[2])
        crop_code = parts[3]
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка данных!", show_alert=True)
        return
    
    db = await get_db()
    
    preferred_crop = None if crop_code == "all" else crop_code
    await db.update_farmer_config(farmer_id, preferred_crop=preferred_crop)
    
    await callback.answer("✅ Культура изменена!")
    
    # Возвращаем к настройкам
    farmer = await db.get_user_farmer(callback.from_user.id)
    user = await db.get_user(callback.from_user.id)
    if farmer:
        await show_farmer_settings(callback.message, farmer, user)


@router.callback_query(F.data.startswith("farmer_mode_"))
async def farmer_set_mode(callback: CallbackQuery):
    """Установка режима сбора урожая"""
    try:
        farmer_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка данных!", show_alert=True)
        return
    
    db = await get_db()
    
    # Меняем режим
    farmer = await db.get_user_farmer(callback.from_user.id)
    if not farmer:
        await callback.answer("❌ Фермер не найден!", show_alert=True)
        return
    
    current_mode = farmer.get('config', {}).get('harvest_mode', 'sell')
    new_mode = 'inventory' if current_mode == 'sell' else 'sell' if current_mode == 'inventory' else 'sell'
    
    await db.update_farmer_config(farmer_id, harvest_mode=new_mode)
    
    mode_text = "в инвентарь" if new_mode == 'inventory' else "продавать"
    await callback.answer(f"✅ Режим: {mode_text}")
    
    # Обновляем сообщение
    user = await db.get_user(callback.from_user.id)
    farmer = await db.get_user_farmer(callback.from_user.id)
    if farmer:
        await show_farmer_settings(callback.message, farmer, user)


@router.callback_query(F.data.startswith("farmer_fert_"))
async def farmer_toggle_fertilizer(callback: CallbackQuery):
    """Включение/выключение удобрений для фермера"""
    try:
        farmer_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка данных!", show_alert=True)
        return
    
    db = await get_db()
    
    farmer = await db.get_user_farmer(callback.from_user.id)
    if not farmer:
        await callback.answer("❌ Фермер не найден!", show_alert=True)
        return
    
    current = farmer.get('config', {}).get('use_fertilizer', False)
    await db.update_farmer_config(farmer_id, use_fertilizer=not current)
    
    status = "включены" if not current else "выключены"
    await callback.answer(f"✅ Удобрения {status}!")
    
    # Обновляем сообщение
    user = await db.get_user(callback.from_user.id)
    farmer = await db.get_user_farmer(callback.from_user.id)
    if farmer:
        await show_farmer_settings(callback.message, farmer, user)


@router.callback_query(F.data.startswith("farmer_pause_"))
async def farmer_pause_handler(callback: CallbackQuery):
    """Приостановка фермера"""
    try:
        farmer_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка данных!", show_alert=True)
        return
    
    db = await get_db()
    await db.pause_farmer(farmer_id)
    
    await callback.answer("⏸️ Фермер приостановлен!")
    
    # Обновляем сообщение
    user = await db.get_user(callback.from_user.id)
    farmer = await db.get_user_farmer(callback.from_user.id)
    if farmer:
        await show_farmer_settings(callback.message, farmer, user)


@router.callback_query(F.data.startswith("farmer_resume_"))
async def farmer_resume_handler(callback: CallbackQuery):
    """Возобновление работы фермера"""
    try:
        farmer_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка данных!", show_alert=True)
        return
    
    db = await get_db()
    await db.resume_farmer(farmer_id)
    
    await callback.answer("▶️ Фермер возобновил работу!")
    
    # Обновляем сообщение
    user = await db.get_user(callback.from_user.id)
    farmer = await db.get_user_farmer(callback.from_user.id)
    if farmer:
        await show_farmer_settings(callback.message, farmer, user)


@router.callback_query(F.data.startswith("farmer_fire_"))
async def farmer_fire_handler(callback: CallbackQuery):
    """Увольнение фермера"""
    try:
        farmer_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка данных!", show_alert=True)
        return
    
    # Подтверждение
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Да, уволить", callback_data=f"farmer_confirm_fire_{farmer_id}")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="back_farmers")]
    ])
    
    await callback.message.edit_text(
        "⚠️ <b>УВОЛЬНЕНИЕ ФЕРМЕРА</b>\n\n"
        "Ты точно хочешь уволить фермера?\n"
        "Все настройки будут потеряны!\n\n"
        "⚠️ Деньги за найм не возвращаются!",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
 

@router.callback_query(F.data.startswith("farmer_confirm_fire_"))
async def farmer_confirm_fire(callback: CallbackQuery):
    """Подтверждение увольнения"""
    try:
        farmer_id = int(callback.data.split("_")[3])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка данных!", show_alert=True)
        return
    
    db = await get_db()
    await db.fire_farmer(farmer_id)
    
    await callback.answer("❌ Фермер уволен!")
    
    # Возвращаем к меню найма
    user = await db.get_user(callback.from_user.id)
    await show_farmer_hire_menu(callback.message, user)


@router.callback_query(F.data == "back_farmers")
async def back_to_farmers(callback: CallbackQuery):
    """Возврат к меню фермеров"""
    db = await get_db()
    user = await db.get_user(callback.from_user.id)
    farmer = await db.get_user_farmer(callback.from_user.id)
    
    if farmer:
        await show_farmer_settings(callback.message, farmer, user)
    else:
        await show_farmer_hire_menu(callback.message, user)


# =================== ПРОМОКОДЫ (ТЗ v4.0 п.14) ===================

@router.message(Command("promo"))
@router.message(F.text == "🎁 Промо")
async def promo_handler(message: Message):
    """Главное меню промокодов согласно ТЗ v4.0 п.14.1"""
    db = await get_db()
    
    text = (
        "🎁 <b>АКТИВАЦИЯ ПРОМОКОДА</b>\n\n"
        "Введи промокод:\n\n"
        "Примеры:\n"
        "• FARMER2024 — для новичков\n"
        "• HALLOWEEN — сезонный\n"
        "• TOP100 — для лидеров\n\n"
        "Или посмотри доступные промокоды ниже 👇"
    )
 
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Ввести код", callback_data="promo_enter")],
        [InlineKeyboardButton(text="📋 Доступные промо", callback_data="promo_list")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "promo_enter")
async def promo_enter_handler(callback: CallbackQuery):
    """Запрос ввода промокода"""
    await callback.message.edit_text(
        "🎁 <b>ВВЕДИ ПРОМОКОД</b>\n\n"
        "Напиши код в ответном сообщении.\n"
        "Примеры: FARMER2024, HALLOWEEN, TOP100\n\n"
        "Отправь код прямо сейчас!",
        parse_mode="HTML"
    )
    
    await callback.answer("Введи промокод")


@router.message(F.text.regexp(r'^[A-Z0-9]{4,20}$'))
async def promo_process_handler(message: Message):
    """Обработка введённого промокода (регистрация буквенно-цифровых кодов)"""
    code = message.text.strip().upper()
    
    db = await get_db()
    
    # Пытаемся активировать
    result = await db.activate_promocode(message.from_user.id, code)
    
    if result.get("success"):
        # Успешная активация - ТЗ п.14.2
        rewards = result.get("rewards", {})
        
        text_lines = [
            "🎉 <b>ПРОМОКОД АКТИВИРОВАН!</b>",
            f"Код: {code}",
            "",
            "Ты получил:"
        ]
        
        if rewards.get("coins", 0) > 0:
            text_lines.append(f"• 💰 {rewards['coins']:,}🪙")
        
        if rewards.get("gems", 0) > 0:
            text_lines.append(f"• 💎 {rewards['gems']} кристаллов")
        
        for item in rewards.get("items", []):
            item_info = await db.get_shop_item(item['code'])
            if item_info:
                icon = item_info.get('icon', '🎁')
                name = item_info.get('name', item['code'])
                text_lines.append(f"• {icon} {name} x{item['amount']}")
        
        # Получаем обновлённый баланс
        user = await db.get_user(message.from_user.id)
        if user:
            text_lines.append("")
            text_lines.append(f"Баланс обновлен: {user.get('balance', 0):,}🪙 | {user.get('gems', 0)}💎")
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Еще промо", callback_data="promo_list")],
            [InlineKeyboardButton(text="🌾 На ферму", callback_data="back_farm")]
        ])
        
        await message.answer("\n".join(text_lines), reply_markup=keyboard, parse_mode="HTML")
    else:
        # Ошибка активации - ТЗ п.14.3
        error_type = result.get("error", "")
        
        text_lines = [
            "❌ <b>Промокод недействителен</b>",
            "",
            "Возможные причины:"
        ]
        
        if error_type == "not_found":
            text_lines.append("• Код не существует")
        elif error_type == "expired":
            text_lines.append("• Код истёк")
        elif error_type == "limit_reached":
            text_lines.append("• Лимит активаций исчерпан")
        elif error_type == "already_used":
            text_lines.append("• Ты уже использовал этот код")
        elif error_type == "not_for_you":
            text_lines.append("• Код только для новых игроков")
        else:
            text_lines.append("• " + result.get("message", "Неизвестная ошибка"))
        
        text_lines.append("")
        text_lines.append("Попробуй другие коды или жди новых!")
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Доступные промо", callback_data="promo_list")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
        ])
    
        await message.answer("\n".join(text_lines), reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "promo_list")
async def promo_list_handler(callback: CallbackQuery):
    """Список доступных промокодов - ТЗ п.14.4"""
    db = await get_db()
    
    promos = await db.get_active_promocodes(callback.from_user.id)
    
    if not promos:
        await callback.message.edit_text(
            "📋 <b>ДОСТУПНЫЕ ПРОМОКОДЫ</b>\n\n"
            "Сейчас нет активных промокодов.\n"
            "Загляни позже или следи за новостями!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
            ]),
            parse_mode="HTML"
        )
        return
    
    # Группируем по типам
    daily = [p for p in promos if p['type'] == 'daily']
    event = [p for p in promos if p['type'] == 'event']
    starter = [p for p in promos if p['type'] == 'starter']
    
    text_lines = ["📋 <b>ДОСТУПНЫЕ ПРОМОКОДЫ</b>", ""]
    
    # Ежедневные
    if daily:
        text_lines.append("Ежедневные:")
        for p in daily:
            if p['already_used']:
                status = "✅ использован"
            else:
                days_left = p.get('days_left')
                if days_left:
                    status = f"до {p['code']} (осталось {days_left} дн.)"
                else:
                    status = "активен"
            
            text_lines.append(f"🎁 {p['code']} — {status}")
            if p['reward_coins'] > 0:
                text_lines.append(f"   💰 {p['reward_coins']:,}🪙")
            if p['reward_gems'] > 0:
                text_lines.append(f"   💎 {p['reward_gems']}💎")
        text_lines.append("")
    
    # Ивентовые
    if event:
        text_lines.append("Ивентовые (ограничено):")
        for p in event:
            remaining = p.get('remaining_activations')
            remaining_text = f"Осталось {remaining} активаций" if remaining else ""
            text_lines.append(f"🎃 {p['code']} — {remaining_text}")
        text_lines.append("")
    
    # Вечные
    if starter:
        text_lines.append("Вечные:")
        for p in starter:
            used_status = "✅ использован" if p['already_used'] else "доступен (1 раз)"
            text_lines.append(f"🌟 {p['code']} — {used_status}")
            if p['reward_coins'] > 0:
                text_lines.append(f"   💰 {p['reward_coins']:,}🪙")
        text_lines.append("")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Активировать", callback_data="promo_enter")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )
 

# =================== РЕФЕРАЛЬНАЯ СИСТЕМА (ТЗ v4.0 п.15) ===================

@router.message(Command("refer"))
@router.message(F.text == "👥 Рефералы")
async def referral_handler(message: Message):
    """Главное меню реферальной системы согласно ТЗ v4.0 п.15.1"""
    db = await get_db()
    user = await db.get_user(message.from_user.id)
    
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден!")
        return
    
    # Получаем статистику
    stats = await db.get_referral_stats(message.from_user.id)
    
    # Формируем ссылку
    ref_link = await db.get_referral_link(message.from_user.id)
    
    text_lines = [
        "👥 <b>РЕФЕРАЛЬНАЯ СИСТЕМА</b>",
        "",
        f"🔗 <b>Твоя реферальная ссылка:</b>",
        f"<code>{ref_link}</code>",
        "",
        "Приглашай друзей и получай бонусы!",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━",
        "📊 <b>ТВОЯ СТАТИСТИКА:</b>",
        f"Приглашено: {stats['total_referrals']} друзей",
        f"Достигли 5 престижа: {stats['prestige5_count']}",
        f"Заработано: {stats['total_earned_coins']:,}🪙 + {stats['total_earned_gems']}💎",
        "",
    ]
    
    # Топ рефералов
    text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    text_lines.append("🏆 <b>ТОП РЕФЕРАЛОВ:</b>")
    
    for i, top in enumerate(stats['top_referrers'][:5], 1):
        username = top.get('username', '???')
        count = top.get('count', 0)
        
        if i <= 3:
            medal = ['🥇', '🥈', '🥉'][i-1]
        else:
            medal = f"{i}."
        
        if top.get('user_id') == message.from_user.id:
            text_lines.append(f"{medal} @{username} — {count} друзей (ТЫ)")
        else:
            text_lines.append(f"{medal} @{username} — {count} друзей")
    
    if stats.get('my_place') and stats['my_place'] > 5:
        text_lines.append(f"...")
        text_lines.append(f"{stats['my_place']}. Ты — {stats['total_referrals']} друзей")
    
    # Награды
    text_lines.append("")
    text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    text_lines.append("🎁 <b>НАГРАДЫ ЗА РЕФЕРАЛОВ:</b>")
    text_lines.append("")
    text_lines.append("За каждого приглашенного:")
    text_lines.append("✅ Регистрация: 100🪙")
    text_lines.append("✅ Престиж 1: +50🪙")
    text_lines.append("✅ Престиж 5: +200🪙 + 5💎")
    text_lines.append("✅ Престиж 10: +500🪙 + 15💎")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Мои рефералы", callback_data="referral_list")],
        [InlineKeyboardButton(text="🔗 Копировать ссылку", callback_data="referral_copy")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])
    
    await message.answer("\n".join(text_lines), reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "referral_list")
async def referral_list_handler(callback: CallbackQuery):
    """Детальный список рефералов - ТЗ п.15.2"""
    db = await get_db()
    
    stats = await db.get_referral_stats(callback.from_user.id)
    referrals = stats.get('referrals', [])
    
    if not referrals:
        await callback.message.edit_text(
            "👥 <b>МОИ РЕФЕРАЛЫ</b>\n\n"
            "У тебя пока нет рефералов.\n"
            "Пригласи друзей по ссылке!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👥 Пригласить еще", callback_data="referral_copy")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
            ]),
            parse_mode="HTML"
        )
        return
    
    text_lines = [
        f"👥 <b>МОИ РЕФЕРАЛЫ</b> ({len(referrals)})",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    for ref in referrals[:10]:  # Показываем первые 10
        username = ref.get('username', '???')
        prestige = ref.get('prestige_level', 1)
        earned_coins = ref.get('earned_coins', 0)
        earned_gems = ref.get('earned_gems', 0)
        
        status_emoji = "✅" if prestige >= 1 else "⏳"
        
        text_lines.append(f"{status_emoji} @{username} — Престиж {prestige}")
        
        if earned_coins > 0 or earned_gems > 0:
            rewards_text = f"   Заработано: {earned_coins:,}🪙"
            if earned_gems > 0:
                rewards_text += f" + {earned_gems}💎"
            text_lines.append(rewards_text)
        else:
            text_lines.append("   Награда: 100🪙 ожидает")
        
        text_lines.append("")
    
    if len(referrals) > 10:
        text_lines.append(f"... и еще {len(referrals) - 10}")
    
    text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    text_lines.append(f"💰 Всего заработано: {stats['total_earned_coins']:,}🪙 + {stats['total_earned_gems']}💎")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Пригласить еще", callback_data="referral_copy")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )
 

@router.callback_query(F.data == "referral_copy")
async def referral_copy_handler(callback: CallbackQuery):
    """Копирование реферальной ссылки"""
    db = await get_db()
    ref_link = await db.get_referral_link(callback.from_user.id)
    
    await callback.answer("Ссылка скопирована! Отправь друзьям")
    
    # Отправляем сообщение для копирования
    text = (
        f"🔗 <b>ТВОЯ РЕФЕРАЛЬНАЯ ССЫЛКА</b>\n\n"
        f"<code>{ref_link}</code>\n\n"
        f"Отправь друзьям и получи бонусы:\n"
        f"• 100🪙 за каждую регистрацию\n"
        f"• +50🪙 за престиж 1\n"
        f"• +200🪙 + 5💎 за престиж 5\n"
        f"• +500🪙 + 15💎 за престиж 10\n\n"
        f"Твои друзья тоже получат бонус при регистрации!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Мои рефералы", callback_data="referral_list")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])
    
    await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")


# =================== СЕЗОННЫЕ ИВЕНТЫ (ТЗ v4.0 п.16) ===================

@router.message(Command("event"))
async def event_handler(message: Message):
    """Главное меню сезонных ивентов согласно ТЗ v4.0 п.16"""
    db = await get_db()
    
    # Получаем активные ивенты
    events = await db.get_active_events()
    
    if not events:
        await message.answer(
            "🎉 <b>СЕЗОННЫЕ ИВЕНТЫ</b>\n\n"
            "Сейчас нет активных ивентов.\n"
            "Загляни позже — скоро начнётся что-то интересное!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
            ]),
            parse_mode="HTML"
        )
        return
    
    # Показываем первый активный ивент (обычно их один)
    event = events[0]
    
    # Определяем тип ивента
    event_season = event.get('season', '').lower()
    
    if 'halloween' in event_season or 'pumpkin' in event_season:
        await show_halloween_event(message, event)
    elif 'newyear' in event_season or 'christmas' in event_season or 'winter' in event_season:
        await show_newyear_event(message, event)
    else:
        # Универсальное отображение для других ивентов
        await show_generic_event(message, event)


async def show_halloween_event(message: Message, event: Dict):
    """Отображение Хэллоуин ивента - ТЗ п.16.1"""
    db = await get_db()
    user = await db.get_user(message.from_user.id)
    
    # Получаем прогресс
    progress = await db.get_event_progress(message.from_user.id, event['event_id'])
    
    # Получаем количество тыкв
    event_items = await db.get_event_inventory(message.from_user.id, "halloween")
    pumpkins = event_items.get('pumpkin', 0)
    
    text_lines = [
        "🎃 <b>ХЭЛЛОУИН НА ФЕРМЕ!</b>",
        "",
        f"С {event.get('start_date', '???')} по {event.get('end_date', '???')}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━",
        "🎃 <b>ТЫКВЕННЫЙ СЕЗОН:</b>",
        "• Специальные семена тыквы",
        "• +50% дохода в темное время",
        "• Пугало (+10% к шансу кейсов)",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━",
        "🎁 <b>НАГРАДЫ:</b>",
        "• Собери 100 тыкв → титул \"Тыквенный король\"",
        "• Собери 500 тыкв → скин \"Пугало\"",
        "• Топ-10 по тыквам → 500💎",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━",
        f"🎃 <b>ТВОИ ТЫКВЫ:</b> {pumpkins}/100",
    ]
    
    # Прогресс-бар
    progress_pct = min(100, int((pumpkins / 100) * 100))
    filled = int(progress_pct / 10)
    empty = 10 - filled
    progress_bar = "█" * filled + "░" * empty
    text_lines.append(f"[{progress_bar}] {progress_pct}%")
    
    # Место в топе
    text_lines.append("")
    text_lines.append(f"🏆 <b>Твое место:</b> #{progress['rank']}")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎃 К тыквам", callback_data=f"event_crops_{event['event_id']}")],
        [InlineKeyboardButton(text="🏆 Топ ивента", callback_data=f"event_top_{event['event_id']}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])
    
    await message.answer("\n".join(text_lines), reply_markup=keyboard, parse_mode="HTML")


async def show_newyear_event(message: Message, event: Dict):
    """Отображение Новогоднего ивента - ТЗ п.16.3"""
    db = await get_db()
    
    # Получаем количество подарков
    event_items = await db.get_event_inventory(message.from_user.id, "newyear")
    gifts = event_items.get('gift', 0)
    trees = event_items.get('christmas_tree', 0)
    
    text_lines = [
        "🎄 <b>НОВОГОДНИЙ ИВЕНТ!</b>",
        "",
        f"С {event.get('start_date', '???')} по {event.get('end_date', '???')}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━",
        "🎄 <b>ПРАЗДНИЧНЫЙ СЕЗОН:</b>",
        "• Особые семена елок",
        "• Подарки под каждой грядкой",
        "• Елка (+15% к доходу)",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━",
        "🎁 <b>ПОДАРКИ:</b>",
        "• Открывай кейсы с подарками",
        "• Шанс получить кристаллы",
        "• Шанс получить эксклюзивный скин",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━",
        f"🎄 <b>ТВОИ ЕЛКИ:</b> {trees}",
        f"🎁 <b>ТВОИ ПОДАРКИ:</b> {gifts}/50",
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎄 К елкам", callback_data=f"event_crops_{event['event_id']}")],
        [InlineKeyboardButton(text="🎁 Открыть подарки", callback_data=f"event_gifts_{event['event_id']}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])
    
    await message.answer("\n".join(text_lines), reply_markup=keyboard, parse_mode="HTML")


async def show_generic_event(message: Message, event: Dict):
    """Универсальное отображение ивента"""
    text_lines = [
        f"🎉 <b>{event.get('name', 'ИВЕНТ').upper()}</b>",
        "",
        event.get('description', 'Описание ивента...'),
        "",
        f"📅 Период: {event.get('start_date', '???')} — {event.get('end_date', '???')}",
    ]
    
    if event.get('multiplier', 1.0) > 1.0:
        text_lines.append(f"⚡ Множитель: x{event['multiplier']}")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏆 Топ ивента", callback_data=f"event_top_{event['event_id']}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])
    
    await message.answer("\n".join(text_lines), reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("event_top_"))
async def event_top_handler(callback: CallbackQuery):
    """Показывает топ ивента"""
    try:
        event_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка данных!", show_alert=True)
        return
    
    db = await get_db()
    
    event = await db.get_event_by_id(event_id)
    if not event:
        await callback.answer("❌ Ивент не найден!", show_alert=True)
        return
    
    progress = await db.get_event_progress(callback.from_user.id, event_id)
    
    text_lines = [
        f"🏆 <b>ТОП ИВЕНТА: {event.get('name', '???').upper()}</b>",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    # Топ-10
    for i, player in enumerate(progress['top_10'], 1):
        username = player.get('username', '???')
        score = player.get('score', 0)
        
        if i <= 3:
            medal = ['🥇', '🥈', '🥉'][i-1]
        else:
            medal = f"{i}."
        
        if player.get('user_id') == callback.from_user.id:
            text_lines.append(f"{medal} @{username} — {score} (ТЫ)")
        else:
            text_lines.append(f"{medal} @{username} — {score}")
    
    # Место пользователя
    if progress['rank'] > 10:
        text_lines.append("...")
        text_lines.append(f"{progress['rank']}. Ты — {progress['score']}")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎉 К ивенту", callback_data=f"back_event_{event_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])
    
    await callback.message.edit_text("\n".join(text_lines), reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("event_crops_"))
async def event_crops_handler(callback: CallbackQuery):
    """Показывает ивентовые культуры в магазине"""
    try:
        event_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка данных!", show_alert=True)
        return
    
    db = await get_db()
    
    # Получаем семена из магазина (отфильтруем по is_seasonal)
    # Для демо покажем сообщение
    await callback.answer("🌱 Ивентовые семена доступны в магазине!")
    
    # Перенаправляем в магазин
    await shop_handler(callback.message)


@router.message(F.text == "🎉 Ивент")
async def event_menu_handler(message: Message):
    """Обработчик кнопки '🎉 Ивент' из меню"""
    await event_handler(message)


# =================== ПУГАЛО (ТЗ v4.0 п.16.2) ===================

@router.callback_query(F.data == "buy_scarecrow")
async def buy_scarecrow_handler(callback: CallbackQuery):
    """Покупка пугала за тыквы"""
    db = await get_db()
    user = await db.get_user(callback.from_user.id)
    
    if not user:
        await callback.answer("❌ Ошибка: пользователь не найден!", show_alert=True)
        return
    
    # Проверяем есть ли тыквы
    event_items = await db.get_event_inventory(callback.from_user.id, "halloween")
    pumpkins = event_items.get('pumpkin', 0)
    
    # Цена пугала - 100 тыкв
    price = 100
    
    if pumpkins < price:
        await callback.answer(f"❌ Недостаточно тыкв! Нужно {price}🎃, у тебя {pumpkins}", show_alert=True)
        return
    
    # Списываем тыквы и добавляем пугало
    await db.add_inventory(callback.from_user.id, "event_scarecrow", 1)
    await db.add_inventory(callback.from_user.id, "event_pumpkin", -price)
    
    await callback.answer("🎃 Пугало куплено!")
    
    # Показываем информацию о пугале
    text = (
        "🎃 <b>ПУГАЛО (Ивентовый предмет)</b>\n\n"
        "Эффект:\n"
        "• +10% к шансу нахождения кейсов\n"
        "• Действует только во время Хэллоуина\n"
        "• Можно улучшить до +20% за 100 тыкв\n\n"
        "Твое пугало: Ур.1 (+10%)\n\n"
        "💡 Совет: Пугало автоматически активируется при сборе урожая!"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬆️ Улучшить за 100🎃", callback_data="upgrade_scarecrow")],
        [InlineKeyboardButton(text="📦 В инвентарь", callback_data="inventory")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "upgrade_scarecrow")
async def upgrade_scarecrow_handler(callback: CallbackQuery):
    """Улучшение пугала"""
    db = await get_db()
    
    # Проверяем есть ли тыквы
    event_items = await db.get_event_inventory(callback.from_user.id, "halloween")
    pumpkins = event_items.get('pumpkin', 0)
    
    price = 100  # Цена улучшения
    
    if pumpkins < price:
        await callback.answer(f"❌ Нужно {price}🎃 для улучшения!", show_alert=True)
        return
    
    # Проверяем есть ли пугало
    inventory = await db.get_inventory(callback.from_user.id)
    if inventory.get('scarecrow', 0) <= 0:
        await callback.answer("❌ Сначала купи пугало!", show_alert=True)
        return
    
    # Списываем тыквы
    await db.add_inventory(callback.from_user.id, "event_pumpkin", -price)
    
    await callback.answer("🎃 Пугало улучшено до Ур.2!")
    
    text = (
        "🎃 <b>ПУГАЛО УЛУЧШЕНО!</b>\n\n"
        "Твое пугало: Ур.2 (+20%)\n\n"
        "Эффект:\n"
        "• +20% к шансу нахождения кейсов\n"
        "• Максимальный уровень достигнут!\n\n"
        "💡 Теперь шанс найти кейс увеличен вдвое!"
    )
 
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎃 К ивенту", callback_data="event_handler")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# =================== ОТКРЫТИЕ ПОДАРКОВ (Новый год) ===================

@router.callback_query(F.data.startswith("event_gifts_"))
async def open_gifts_handler(callback: CallbackQuery):
    """Открытие новогодних подарков"""
    try:
        event_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка данных!", show_alert=True)
        return
    
    db = await get_db()
    user = await db.get_user(callback.from_user.id)
    
    if not user:
        await callback.answer("❌ Ошибка!", show_alert=True)
        return
    
    # Проверяем количество подарков
    event_items = await db.get_event_inventory(callback.from_user.id, "newyear")
    gifts = event_items.get('gift', 0)
    
    if gifts <= 0:
        await callback.answer("❌ У тебя нет подарков! Собирай елки!", show_alert=True)
        return
    
    # Открываем подарок (рандомная награда)
    import random
    
    rewards_pool = [
        {"type": "coins", "min": 50, "max": 200, "chance": 40},
        {"type": "coins", "min": 200, "max": 500, "chance": 30},
        {"type": "gems", "min": 1, "max": 5, "chance": 20},
        {"type": "gems", "min": 5, "max": 10, "chance": 8},
        {"type": "item", "code": "fertilizer_premium", "amount": 1, "chance": 2}
    ]
    
    # Выбираем награду
    roll = random.randint(1, 100)
    cumulative = 0
    selected_reward = None
    
    for reward in rewards_pool:
        cumulative += reward["chance"]
        if roll <= cumulative:
            selected_reward = reward
            break
    
    if not selected_reward:
        selected_reward = rewards_pool[0]
    
    # Списываем подарок
    await db.add_inventory(callback.from_user.id, "event_gift", -1)
    
    # Выдаем награду
    if selected_reward["type"] == "coins":
        amount = random.randint(selected_reward["min"], selected_reward["max"])
        await db.update_balance(callback.from_user.id, amount)
        reward_text = f"💰 {amount:,}🪙"
    elif selected_reward["type"] == "gems":
        amount = random.randint(selected_reward["min"], selected_reward["max"])
        await db.update_gems(callback.from_user.id, amount)
        reward_text = f"💎 {amount} кристаллов"
    else:
        await db.add_inventory(callback.from_user.id, selected_reward["code"], selected_reward["amount"])
        item_info = await db.get_shop_item(selected_reward["code"])
        icon = item_info.get('icon', '🎁') if item_info else '🎁'
        name = item_info.get('name', selected_reward["code"]) if item_info else selected_reward["code"]
        reward_text = f"{icon} {name} x{selected_reward['amount']}"
    
    gifts -= 1  # Обновляем количество
    
    await callback.answer("🎁 Подарок открыт!")
    
    text = (
        "🎄 <b>ПОДАРОК ОТКРЫТ!</b>\n\n"
        f"🎁 Ты получил:\n"
        f"{reward_text}\n\n"
        f"Осталось подарков: {gifts}"
    )
    
    keyboard_buttons = []
    if gifts > 0:
        keyboard_buttons.append([InlineKeyboardButton(text=f"🎁 Открыть еще ({gifts})", callback_data=f"event_gifts_{event_id}")])
    keyboard_buttons.extend([
        [InlineKeyboardButton(text="🎄 К елкам", callback_data=f"event_crops_{event_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# =================== ПЕРЕВОДЫ МЕЖДУ ИГРОКАМИ (ТЗ v4.0 п.18) ===================

@router.message(Command("send"))
async def send_handler(message: Message):
    """Команда перевода монет - ТЗ v4.0 п.18.1"""
    db = await get_db()
    user = await db.get_user(message.from_user.id)
    
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден!")
        return
    
    # Проверяем престиж
    prestige_level = user.get('prestige_level', 1)
    if prestige_level < 2:
        await message.answer(
            f"🔒 <b>ПЕРЕВОДЫ ЗАКРЫТЫ</b>\n\n"
            f"Твой престиж: {prestige_level}\n"
            f"Требуется: <b>2 престиж</b>\n\n"
            f"Достигни 2 престижа, чтобы открыть переводы между игроками!",
            parse_mode="HTML"
        )
        return
    
    # Получаем лимиты
    limit_info = await db.get_transfer_limit(message.from_user.id)
    
    # Парсим аргументы команды
    args = message.text.split()
    if len(args) >= 3:
        # Формат: /send @username 1000
        receiver = args[1].replace("@", "")
        try:
            amount = int(args[2])
        except ValueError:
            await message.answer("❌ Неверная сумма! Используй: /send @username 1000")
            return
        
        # Ищем получателя
        receiver_user = await db.fetchone(
            "SELECT user_id, username FROM users WHERE username = ?",
            (receiver,)
        )
        
        if not receiver_user:
            await message.answer(f"❌ Пользователь @{receiver} не найден!")
            return
        
        receiver_id = receiver_user[0]
        receiver_username = receiver_user[1]
        
        # Проверяем возможность перевода
        check = await db.can_transfer(message.from_user.id, amount)
        
        if not check.get('can_transfer', False):
            await message.answer(f"❌ {check.get('reason', 'Ошибка перевода')}")
            return
        
        # Показываем подтверждение
        fee = check.get('fee', int(amount * 0.05))
        total = check.get('total', amount + fee)
        
        text = (
            f"⚠️ <b>ПОДТВЕРДИТЕ ПЕРЕВОД</b>\n\n"
            f"Отправитель: @{user.get('username', '???')}\n"
            f"Получатель: @{receiver_username}\n"
            f"Сумма: {amount:,}🪙\n"
            f"Комиссия (5%): {fee:,}🪙\n"
            f"Итого к списанию: {total:,}🪙\n\n"
            f"Баланс после: {check.get('available_after', user.get('balance', 0) - total):,}🪙"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтверждаю", callback_data=f"confirm_send_{receiver_id}_{amount}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="back_main")]
        ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        # Показываем форму для ввода
        text = (
            f"💰 <b>ПЕРЕВОД МОНЕТ</b>\n\n"
            f"Твой баланс: {user.get('balance', 0):,}🪙\n"
            f"Доступно для перевода сегодня: {limit_info['available']:,}🪙 ({limit_info['base_percentage']*100:.0f}%)\n"
            f"Уже переведено сегодня: {limit_info['used']:,}🪙\n\n"
            f"<b>Формат:</b> /send @username сумма\n"
            f"<b>Пример:</b> /send @friend 1000"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Мои переводы", callback_data="transfer_history")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
        ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("confirm_send_"))
async def confirm_send_handler(callback: CallbackQuery):
    """Подтверждение перевода - ТЗ v4.0 п.18.2"""
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer("❌ Ошибка данных!", show_alert=True)
        return
    
    try:
        receiver_id = int(parts[2])
        amount = int(parts[3])
    except ValueError:
        await callback.answer("❌ Неверные данные!", show_alert=True)
        return
    
    db = await get_db()
    
    # Выполняем перевод
    result = await db.make_transfer(callback.from_user.id, receiver_id, amount)
    
    if not result.get('success', False):
        await callback.answer(f"❌ {result.get('message', 'Ошибка перевода')}", show_alert=True)
        return
    
    await callback.answer("✅ Перевод выполнен!")
    
    # Отправитель видит - ТЗ п.18.3
    sender_text = (
        f"✅ <b>ПЕРЕВОД ВЫПОЛНЕН!</b>\n\n"
        f"{result['amount']:,}🪙 отправлено @{result['receiver_username']}\n"
        f"Комиссия: {result['fee']:,}🪙\n\n"
        f"Новый баланс: {result['sender_balance']:,}🪙"
    )
 
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 К профилю", callback_data="back_main")],
        [InlineKeyboardButton(text="💰 Перевести еще", callback_data="send_again")]
    ])
    
    await callback.message.edit_text(sender_text, reply_markup=keyboard, parse_mode="HTML")
    
    # Получатель видит уведомление - ТЗ п.18.4
    receiver_text = (
        f"🎁 <b>ВАМ ПЕРЕВЕЛИ МОНЕТЫ!</b>\n\n"
        f"@{result.get('sender_username', '???')} отправил вам {result['amount']:,}🪙\n"
        f"(с учетом комиссии 5%)\n\n"
        f"Новый баланс: {result['receiver_balance']:,}🪙"
    )
    
    try:
        await callback.bot.send_message(
            receiver_id,
            receiver_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👤 К профилю", callback_data="back_main")],
                [InlineKeyboardButton(text="💬 Написать отправителю", url=f"tg://user?id={callback.from_user.id}")]
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Failed to notify receiver {receiver_id}: {e}")


@router.callback_query(F.data == "transfer_history")
async def transfer_history_handler(callback: CallbackQuery):
    """История переводов"""
    db = await get_db()
    
    history = await db.get_transfer_history(callback.from_user.id, 10)
    
    if not history:
        await callback.message.edit_text(
            "📋 <b>ИСТОРИЯ ПЕРЕВОДОВ</b>\n\n"
            "У тебя пока нет переводов.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 Перевести", callback_data="send_again")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
            ]),
            parse_mode="HTML"
        )
        return
    
    text_lines = ["📋 <b>ИСТОРИЯ ПЕРЕВОДОВ</b>", ""]
    
    for transfer in history:
        amount = transfer['amount']
        fee = transfer.get('fee', 0)
        is_outgoing = transfer.get('is_outgoing', True)
        
        if is_outgoing:
            username = transfer.get('receiver_username', '???')
            text_lines.append(f"📤 @{username}: -{amount:,}🪙 (+{fee} комиссия)")
        else:
            username = transfer.get('sender_username', '???')
            text_lines.append(f"📥 @{username}: +{amount:,}🪙")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Перевести", callback_data="send_again")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])
    
    await callback.message.edit_text("\n".join(text_lines), reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "send_again")
async def send_again_handler(callback: CallbackQuery):
    """Новый перевод"""
    db = await get_db()
    user = await db.get_user(callback.from_user.id)
    limit_info = await db.get_transfer_limit(callback.from_user.id)
    
    text = (
        f"💰 <b>ПЕРЕВОД МОНЕТ</b>\n\n"
        f"Твой баланс: {user.get('balance', 0):,}🪙\n"
        f"Доступно для перевода: {limit_info['available']:,}🪙\n\n"
        f"<b>Формат:</b> /send @username сумма\n"
        f"<b>Пример:</b> /send @friend 1000"
    )
    
    await callback.message.edit_text(text, parse_mode="HTML")


# =================== ОФИЦИАЛЬНЫЙ ЧАТ (ТЗ v4.0 п.19) ===================

@router.message(Command("chat"))
@router.message(F.text == "💬 Чат")
async def chat_handler(message: Message):
    """Официальный чат фермеров - ТЗ v4.0 п.19.1"""
    
    chat_link = os.getenv("OFFICIAL_CHAT_LINK", "https://t.me/lazy_farmer_chat")
    chat_username = os.getenv("OFFICIAL_CHAT_USERNAME", "lazy_farmer_chat")
    
    text = (
        f"💬 <b>ОФИЦИАЛЬНЫЙ ЧАТ ФЕРМЕРОВ</b>\n\n"
        f"Присоединяйся к общению!\n"
        f"Обсуждай стратегии, делись урожаем,\n"
        f"находи друзей и соперников.\n\n"
        f"👉 @{chat_username}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 <b>ПРАВИЛА ЧАТА:</b>\n"
        f"• Без спама\n"
        f"• Без оскорблений\n"
        f"• Можно просить советы\n"
        f"• Можно хвастаться урожаем\n"
        f"• Обсуждать стратегии\n"
        f"• Находить рефералов"
    )
 
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Перейти в чат", url=chat_link)],
        [InlineKeyboardButton(text="📢 Поделиться ботом", callback_data="share_bot")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "back_main")
async def back_to_main_handler(callback: CallbackQuery):
    """Возврат в главное меню"""
    await callback.message.delete()
    await show_farm(callback.from_user.id, callback.message)


@router.callback_query(F.data == "share_bot")
async def share_bot_handler(callback: CallbackQuery):
    """Поделиться ботом"""
    db = await get_db()
    bot_username = os.getenv("BOT_USERNAME", "LazyFarmerBot")
    ref_link = await db.get_referral_link(callback.from_user.id)
    
    text = (
        f"🌾 <b>ПРИГЛАСИ ДРУЗЕЙ В ЛЕНИВУЮ ФЕРМУ!</b>\n\n"
        f"Твоя реферальная ссылка:\n"
        f"<code>{ref_link}</code>\n\n"
        f"За каждого друга ты получишь:\n"
        f"✅ 100🪙 за регистрацию\n"
        f"✅ +50🪙 за престиж 1\n"
        f"✅ +200🪙 + 5💎 за престиж 5\n\n"
        f"А друг получит стартовый бонус!"
    )
 
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Копировать ссылку", callback_data="referral_copy")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# =================== КВЕСТЫ (ТЗ v4.0 п.7) ===================

async def quests_handler(message: Message):
    """Ежедневные квесты согласно ТЗ v4.0 п.7.1"""
    db = await get_db()
    
    # Получаем квесты
    quests = await db.get_daily_quests(message.from_user.id)
    
    if not quests:
        await message.answer("❌ Ошибка загрузки квестов!")
        return
    
    # Получаем время до обновления
    time_left = await db.get_quest_time_left(is_weekly=False)
    time_str = f"{time_left['hours']:02d}:{time_left['minutes']:02d}"
    
    # Проверяем есть ли выполненные квесты для получения
    has_completed = any(q['completed'] and not q['claimed'] for q in quests)
    
    text_lines = [
        "📜 <b>ЕЖЕДНЕВНЫЕ КВЕСТЫ</b>",
        f"🔄 Обновятся через: {time_str}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    for quest in quests:
        # Прогресс-бар
        progress = quest.get('progress', 0)
        target = quest.get('target_count', 1)
        progress_pct = min(100, (progress / target) * 100) if target > 0 else 0
        filled = int(progress_pct / 10)
        empty = 10 - filled
        progress_bar = "█" * filled + "░" * empty
        
        # Статус
        if quest.get('claimed'):
            status = "✅"
            status_text = f"{progress}/{target} ✓"
        elif quest.get('completed'):
            status = "🎁"
            status_text = f"{progress}/{target} ✓"
        else:
            status = "⏳"
            status_text = f"{progress}/{target}"
        
        # Описание квеста
        description = quest.get('description', '???')
        
        # Формируем награду
        reward_parts = []
        if quest.get('reward_coins', 0) > 0:
            reward_parts.append(f"{quest['reward_coins']}🪙")
        if quest.get('reward_gems', 0) > 0:
            reward_parts.append(f"{quest['reward_gems']}💎")
        
        # Предметы из награды
        reward_items = quest.get('reward_items', {})
        if reward_items:
            for item, qty in reward_items.items():
                # Получаем иконку предмета
                item_info = await db.get_shop_item(item)
                icon = item_info.get('icon', '📦') if item_info else '📦'
                reward_parts.append(f"{icon} x{qty}")
        
        reward_text = " + ".join(reward_parts) if reward_parts else "Нет награды"
        
        text_lines.append(f"{status} {description}")
        text_lines.append(f"   {progress_bar} {status_text}")
        text_lines.append(f"   🎁 {reward_text}")
        text_lines.append("")
    
    text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Формируем клавиатуру
    keyboard = get_quests_keyboard(quests, has_completed, is_weekly=False)
    
    await message.answer(
        "\n".join(text_lines),
        parse_mode="HTML",
        reply_markup=keyboard
    )
 

async def weekly_quests_handler(message: Message):
    """Еженедельные квесты согласно ТЗ v4.0 п.7.2"""
    db = await get_db()
    
    # Получаем квесты
    quests = await db.get_weekly_quests(message.from_user.id)
    
    if not quests:
        await message.answer("❌ Ошибка загрузки квестов!")
        return
    
    # Получаем время до конца недели
    time_left = await db.get_quest_time_left(is_weekly=True)
    days = time_left['hours'] // 24
    hours = time_left['hours'] % 24
    time_str = f"{days} дней {hours:02d}:{time_left['minutes']:02d}"
    
    # Проверяем есть ли выполненные квесты для получения
    has_completed = any(q['completed'] and not q['claimed'] for q in quests)
    
    text_lines = [
        "📜 <b>ЕЖЕНЕДЕЛЬНЫЕ КВЕСТЫ</b>",
        f"⏰ До конца: {time_str}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    for quest in quests:
        # Прогресс-бар
        progress = quest.get('progress', 0)
        target = quest.get('target_count', 1)
        progress_pct = min(100, (progress / target) * 100) if target > 0 else 0
        filled = int(progress_pct / 10)
        empty = 10 - filled
        progress_bar = "█" * filled + "░" * empty
        
        # Статус
        if quest.get('claimed'):
            status = "✅"
            status_text = f"{progress:,}/{target:,} ✓"
        elif quest.get('completed'):
            status = "🎁"
            status_text = f"{progress:,}/{target:,} ✓"
        else:
            status = "⏳"
            status_text = f"{progress:,}/{target:,}"
        
        # Описание квеста
        description = quest.get('description', '???')
        
        # Формируем награду
        reward_parts = []
        if quest.get('reward_coins', 0) > 0:
            reward_parts.append(f"{quest['reward_coins']:,}🪙")
        if quest.get('reward_gems', 0) > 0:
            reward_parts.append(f"{quest['reward_gems']}💎")
        
        # Предметы из награды
        reward_items = quest.get('reward_items', {})
        if reward_items:
            for item, qty in reward_items.items():
                item_info = await db.get_shop_item(item)
                icon = item_info.get('icon', '📦') if item_info else '📦'
                reward_parts.append(f"{icon} x{qty}")
        
        reward_text = " + ".join(reward_parts) if reward_parts else "Нет награды"
        
        text_lines.append(f"{status} {description}")
        text_lines.append(f"   {progress_bar} {status_text}")
        text_lines.append(f"   🎁 {reward_text}")
        text_lines.append("")
    
    text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Формируем клавиатуру
    keyboard = get_quests_keyboard(quests, has_completed, is_weekly=True)
    
    await message.answer(
        "\n".join(text_lines),
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.message(F.text == "📜 Квесты")
async def quests_handler_button(message: Message):
    await quests_handler(message)


@router.message(Command("weekly", "недельные", "еженедельные"))
async def weekly_quests_command(message: Message):
    """Команда /weekly для еженедельных квестов"""
    await weekly_quests_handler(message)


@router.callback_query(F.data == "show_daily_quests")
async def show_daily_quests_callback(callback: CallbackQuery):
    """Показать ежедневные квесты"""
    # Создаём фейковое сообщение для вызова хендлера
    await quests_handler(callback.message)
    await callback.answer()


@router.callback_query(F.data == "show_weekly_quests")
async def show_weekly_quests_callback(callback: CallbackQuery):
    """Показать еженедельные квесты"""
    await weekly_quests_handler(callback.message)
    await callback.answer()


@router.callback_query(F.data == "claim_all_quests")
async def claim_all_daily_quests(callback: CallbackQuery):
    """Забрать все награды за ежедневные квесты"""
    db = await get_db()
    
    result = await db.claim_all_quest_rewards(callback.from_user.id, is_weekly=False)
    
    if not result.get('success'):
        await callback.answer("❌ Нет доступных наград!", show_alert=True)
        return
    
    # Формируем текст наград
    text_lines = [
        "🎁 <b>НАГРАДЫ ПОЛУЧЕНЫ!</b>",
        "",
        "Ежедневные квесты:"
    ]
    
    for quest in result.get('claimed_quests', []):
        status = "✅"
        text_lines.append(f"{status} {quest.get('description', '???')}")
    
    text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Итого
    total_parts = []
    if result.get('coins', 0) > 0:
        total_parts.append(f"💰 {result['coins']:,}🪙")
    if result.get('gems', 0) > 0:
        total_parts.append(f"💎 {result['gems']}💎")
    
    text_lines.append(f"💰 Итого: {' + '.join(total_parts)}")
    
    # Предметы
    items = result.get('items', {})
    if items:
        items_text = []
        for item, qty in items.items():
            item_info = await db.get_shop_item(item)
            icon = item_info.get('icon', '📦') if item_info else '📦'
            items_text.append(f"{icon} x{qty}")
        text_lines.append(f"📦 Предметы: {', '.join(items_text)}")
    
    # Новый баланс
    user = await db.get_user(callback.from_user.id)
    if user:
        text_lines.append(f"\nНовый баланс: {user.get('balance', 0):,}🪙 | {user.get('gems', 0)}💎")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📜 К квестам", callback_data="show_daily_quests"),
            InlineKeyboardButton(text="🌾 На ферму", callback_data="back_farm")
        ]
    ])
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "claim_all_weekly")
async def claim_all_weekly_quests(callback: CallbackQuery):
    """Забрать все награды за еженедельные квесты"""
    db = await get_db()
    
    result = await db.claim_all_quest_rewards(callback.from_user.id, is_weekly=True)
    
    if not result.get('success'):
        await callback.answer("❌ Нет доступных наград!", show_alert=True)
        return
    
    # Формируем текст наград
    text_lines = [
        "🎁 <b>НАГРАДЫ ПОЛУЧЕНЫ!</b>",
        "",
        "Еженедельные квесты:"
    ]
    
    for quest in result.get('claimed_quests', []):
        status = "✅"
        text_lines.append(f"{status} {quest.get('description', '???')}")
    
    text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Итого
    total_parts = []
    if result.get('coins', 0) > 0:
        total_parts.append(f"💰 {result['coins']:,}🪙")
    if result.get('gems', 0) > 0:
        total_parts.append(f"💎 {result['gems']}💎")
    
    text_lines.append(f"💰 Итого: {' + '.join(total_parts)}")
    
    # Предметы
    items = result.get('items', {})
    if items:
        items_text = []
        for item, qty in items.items():
            item_info = await db.get_shop_item(item)
            icon = item_info.get('icon', '📦') if item_info else '📦'
            items_text.append(f"{icon} x{qty}")
        text_lines.append(f"📦 Предметы: {', '.join(items_text)}")
    
    # Новый баланс
    user = await db.get_user(callback.from_user.id)
    if user:
        text_lines.append(f"\nНовый баланс: {user.get('balance', 0):,}🪙 | {user.get('gems', 0)}💎")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📜 К квестам", callback_data="show_weekly_quests"),
            InlineKeyboardButton(text="🌾 На ферму", callback_data="back_farm")
        ]
    ])
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "refresh_quests")
async def refresh_daily_quests(callback: CallbackQuery):
    """Обновление ежедневных квестов за кристаллы"""
    db = await get_db()
    
    # Проверяем баланс кристаллов
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Пользователь не найден!", show_alert=True)
        return
    
    cost = 50
    if user.get('gems', 0) < cost:
        await callback.answer(f"❌ Недостаточно кристаллов! Нужно {cost}💎", show_alert=True)
        return
    
    # Запрашиваем подтверждение
    text = f"""🔄 <b>ОБНОВЛЕНИЕ КВЕСТОВ</b>

Стоимость: {cost}💎
Твой баланс: {user.get('gems', 0)}💎

⚠️ Текущие квесты будут заменены новыми случайными квестами!

Обновить квесты?"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"✅ Обновить за {cost}💎", callback_data=f"confirm_refresh_{cost}")
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="show_daily_quests")
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("confirm_refresh_"))
async def confirm_refresh_quests(callback: CallbackQuery):
    """Подтверждение обновления квестов"""
    cost = int(callback.data.split("_")[2])
    
    db = await get_db()
    result = await db.refresh_daily_quests(callback.from_user.id, cost)
    
    if result.get('success'):
        await callback.answer("✅ Квесты обновлены!")
        await quests_handler(callback.message)
    else:
        await callback.answer(f"❌ {result.get('message', 'Ошибка')}", show_alert=True)


@router.callback_query(F.data.startswith("claim_quest_"))
async def claim_single_quest_reward(callback: CallbackQuery):
    """Получение награды за конкретный квест"""
    parts = callback.data.split("_")
    
    # Проверяем формат
    if len(parts) < 3:
        await callback.answer("❌ Неверный формат данных!", show_alert=True)
        return
    
    try:
        quest_id = int(parts[2])
    except ValueError:
        await callback.answer("❌ Неверный ID квеста!", show_alert=True)
        return
    
    # Проверяем, еженедельный ли квест
    is_weekly = len(parts) > 3 and parts[3] == "weekly"
    
    db = await get_db()
    result = await db.claim_quest_reward(callback.from_user.id, quest_id, is_weekly)
    
    if result.get('success'):
        # Формируем текст награды
        reward_parts = []
        if result.get('coins', 0) > 0:
            reward_parts.append(f"💰 {result['coins']:,}🪙")
        if result.get('gems', 0) > 0:
            reward_parts.append(f"💎 {result['gems']}💎")
        
        items = result.get('items', {})
        if items:
            for item, qty in items.items():
                item_info = await db.get_shop_item(item)
                icon = item_info.get('icon', '📦') if item_info else '📦'
                reward_parts.append(f"{icon} x{qty}")
        
        reward_text = " + ".join(reward_parts) if reward_parts else "Нет награды"
        
        await callback.answer(f"🎁 Получено: {reward_text}")
        
        # Обновляем список квестов
        if is_weekly:
            await weekly_quests_handler(callback.message)
        else:
            await quests_handler(callback.message)
    else:
        await callback.answer(f"❌ {result.get('message', 'Ошибка')}", show_alert=True)


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


# =================== ПРОФИЛЬ ИГРОКА (ТЗ v4.0) ===================

async def profile_handler(message: Message):
    """Профиль игрока согласно ТЗ v4.0"""
    db = await get_db()
    user = await db.get_user(message.from_user.id)
    
    if not user:
        await message.answer("❌ Сначала начни игру командой /start")
        return
    
    from datetime import datetime
    
    # Форматирование даты регистрации
    joined_date = user.get('joined_date', '')
    if joined_date:
        try:
            if isinstance(joined_date, str):
                dt = datetime.fromisoformat(joined_date.replace('Z', '+00:00'))
                joined_str = dt.strftime('%d.%m.%Y')
            else:
                joined_str = joined_date.strftime('%d.%m.%Y')
        except:
            joined_str = '???'
    else:
        joined_str = '???'
    
    # Последний визит
    last_activity = user.get('last_activity', '')
    if last_activity:
        try:
            if isinstance(last_activity, str):
                dt = datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
                now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
                diff = now - dt
                minutes = int(diff.total_seconds() // 60)
                if minutes < 1:
                    last_visit = "только что"
                elif minutes < 60:
                    last_visit = f"{minutes} мин назад"
                else:
                    hours = minutes // 60
                    if hours < 24:
                        last_visit = f"{hours} ч назад"
                    else:
                        days = hours // 24
                        last_visit = f"{days} дн назад"
            else:
                last_visit = "неизвестно"
        except:
            last_visit = "неизвестно"
    else:
        last_visit = "неизвестно"
    
    # Получаем выбранные ачивки для профиля
    selected_achievements = await db.get_profile_achievements(message.from_user.id if hasattr(message, 'from_user') else message.chat.id)
    
    # Формируем блок достижений
    ach_block = ""
    if selected_achievements:
        ach_icons = " ".join([f"{a['icon']}" for a in selected_achievements[:4]])
        ach_block = f"\n🏆 <b>Достижения:</b> {ach_icons}\n"
    
    # Получаем информацию о настройках уведомлений
    settings = user.get('settings', {}) or {}
    notif_enabled = settings.get('notifications', True)
    
    text = f"""👤 <b>ПРОФИЛЬ ФЕРМЕРА</b>

🆔 Ник: @{user.get('username', 'без ника')}
🏷️ Имя: {user.get('first_name', 'Игрок')}
📅 На ферме: с {joined_str}
⏳ Последний визит: {last_visit}
{ach_block}
━━━━━━━━━━━━━━━━━━━━━━━
📊 <b>СТАТИСТИКА:</b>
🎚️ Уровень: {user.get('level', 1)}
🚜 Престиж: {user.get('prestige_level', 1)} (x{user.get('prestige_multiplier', 1.0):.1f})
💰 Баланс: {user.get('balance', 0):,} 🪙
💎 Кристаллы: {user.get('gems', 0)} 💎
🌾 Собрано: {user.get('total_harvested', 0):,} урожаев
🌱 Посажено: {user.get('total_planted', 0):,} раз
📦 Всего заработано: {user.get('total_earned', 0):,} 🪙

━━━━━━━━━━━━━━━━━━━━━━━
⚙️ <b>НАСТРОЙКИ:</b>
🔔 Уведомления: {'Вкл' if notif_enabled else 'Выкл'}
📊 Лимит переводов: 20% (доступно: {int(user.get('balance', 0) * 0.2):,}🪙/день)"""
    
    # Кнопки под профилем (ТЗ v4.0 п.3.2)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Сменить ник", callback_data="profile_change_nick"),
            InlineKeyboardButton(text="🏆 Выбрать ачивки", callback_data="profile_achievements")
        ],
        [
            InlineKeyboardButton(text="🔔 Настройки", callback_data="profile_settings"),
            InlineKeyboardButton(text="📊 Подробно", callback_data="profile_stats")
        ],
        [
            InlineKeyboardButton(text="📜 История", callback_data="profile_history")
        ],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_farm")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "profile_change_nick")
async def profile_change_nick(callback: CallbackQuery, state: FSMContext):
    """Смена ника"""
    await callback.message.edit_text(
        "✏️ <b>СМЕНА НИКА</b>\n\n"
        "Введи новый ник (только латиница, цифры, _, от 3 до 20 символов):\n\n"
        "Для отмены напиши 'отмена'",
        parse_mode="HTML"
    )
    await state.set_state(PlayerStates.changing_nick)
 

@router.callback_query(F.data == "profile_settings")
async def profile_settings(callback: CallbackQuery):
    """Настройки уведомлений"""
    db = await get_db()
    user = await db.get_user(callback.from_user.id)
    settings = user.get('settings', {}) or {}
    
    notif_harvest = settings.get('notif_harvest', True)
    notif_daily = settings.get('notif_daily', True)
    notif_quests = settings.get('notif_quests', True)
    notif_marketing = settings.get('notif_marketing', False)
    
    text = """🔔 <b>НАСТРОЙКИ УВЕДОМЛЕНИЙ</b>

Какие уведомления присылать?"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{'✅' if notif_harvest else '❌'} Созревание урожая",
                callback_data=f"toggle_notif_harvest_{0 if notif_harvest else 1}"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{'✅' if notif_daily else '❌'} Ежедневный бонус",
                callback_data=f"toggle_notif_daily_{0 if notif_daily else 1}"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{'✅' if notif_quests else '❌'} Новые квесты",
                callback_data=f"toggle_notif_quests_{0 if notif_quests else 1}"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{'✅' if notif_marketing else '❌'} Маркетинговые рассылки",
                callback_data=f"toggle_notif_marketing_{0 if notif_marketing else 1}"
            )
        ],
        [InlineKeyboardButton(text="💾 Сохранить", callback_data="save_settings")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_profile")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("toggle_notif_"))
async def toggle_notification(callback: CallbackQuery):
    """Переключение настройки уведомлений"""
    parts = callback.data.split("_")
    notif_type = parts[2]
    value = int(parts[3]) == 1
    
    db = await get_db()
    user = await db.get_user(callback.from_user.id)
    settings = user.get('settings', {}) or {}
    
    settings[f'notif_{notif_type}'] = value
    await db.update_user_settings(callback.from_user.id, settings)
    
    await profile_settings(callback)


@router.callback_query(F.data == "save_settings")
async def save_settings(callback: CallbackQuery):
    """Сохранение настроек"""
    await callback.answer("✅ Настройки сохранены!")
    await profile_handler(callback.message)


@router.callback_query(F.data == "back_profile")
async def back_to_profile(callback: CallbackQuery):
    """Возврат к профилю"""
    await profile_handler(callback.message)


@router.callback_query(F.data == "profile_stats")
async def profile_detailed_stats(callback: CallbackQuery):
    """Подробная статистика"""
    db = await get_db()
    user = await db.get_user(callback.from_user.id)
    
    text = f"""📊 <b>ПОДРОБНАЯ СТАТИСТИКА</b>

👤 <b>Основное:</b>
• ID: {user.get('user_id')}
• Уровень: {user.get('level', 1)}
• Опыт: {user.get('xp', 0):,}

💰 <b>Финансы:</b>
• Баланс: {user.get('balance', 0):,} 🪙
• Кристаллы: {user.get('gems', 0)} 💎
• Всего заработано: {user.get('total_earned', 0):,} 🪙
• Всего потрачено: {user.get('total_spent', 0):,} 🪙

🌾 <b>Фермерство:</b>
• Собрано урожая: {user.get('total_harvested', 0):,}
• Посажено растений: {user.get('total_planted', 0):,}
• Престиж: {user.get('prestige_level', 1)}
• Множитель: x{user.get('prestige_multiplier', 1.0):.1f}

🎁 <b>Бонусы:</b>
• Серия заходов: {user.get('daily_streak', 0)} дней"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_profile")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "profile_history")
async def profile_history(callback: CallbackQuery):
    """История действий игрока (ТЗ v4.0 п.3.2)"""
    db = await get_db()
    
    # Получаем историю из логов
    history = await db.get_user_activity_history(callback.from_user.id, limit=15)
    
    if not history:
        text = """📜 <b>ИСТОРИЯ ДЕЙСТВИЙ</b>

История пока пуста. Начни играть, и здесь появятся записи о твоих достижениях!"""
    else:
        text_lines = ["📜 <b>ИСТОРИЯ ДЕЙСТВИЙ</b>\n"]
        text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━\n")
        
        for entry in history[:15]:
            timestamp = entry.get('timestamp', '')
            if timestamp:
                # Форматируем дату
                try:
                    if isinstance(timestamp, str):
                        date_part = timestamp[:10]
                        time_part = timestamp[11:16]
                    else:
                        date_part = timestamp.strftime('%Y-%m-%d')
                        time_part = timestamp.strftime('%H:%M')
                    text_lines.append(f"📅 {date_part} {time_part}")
                except:
                    text_lines.append(f"📅 ???")
            
            text_lines.append(f"{entry.get('action', '???')}\n")
        
        text_lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
        text = "\n".join(text_lines)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_profile")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# =================== ВЫБОР ДОСТИЖЕНИЙ ДЛЯ ПРОФИЛЯ (ТЗ v4.0) ===================

@router.callback_query(F.data == "profile_achievements")
async def profile_achievements_select(callback: CallbackQuery):
    """Выбор достижений для отображения в профиле"""
    db = await get_db()
    
    # Получаем выполненные достижения
    completed = await db.get_user_completed_achievements(callback.from_user.id)
    
    if not completed:
        await callback.answer("❌ У тебя пока нет выполненных достижений!", show_alert=True)
        return
    
    # Получаем текущий выбор
    selected = await db.get_profile_achievements(callback.from_user.id)
    selected_ids = [a['id'] for a in selected]
    
    text = f"""🏆 <b>ВЫБОР ДОСТИЖЕНИЙ</b>

Выбери до 4 достижений для отображения в профиле.

Текущий выбор: {len(selected_ids)}/4"""
    
    # Формируем кнопки по категориям
    buttons = []
    for ach in completed[:12]:  # Показываем первые 12
        is_selected = ach['id'] in selected_ids
        icon = "✅" if is_selected else "⬜"
        buttons.append(InlineKeyboardButton(
            text=f"{icon} {ach['icon']} {ach['name'][:15]}",
            callback_data=f"sel_ach_{ach['id']}"
        ))
    
    # Группируем по 2 в ряд
    keyboard_rows = []
    for i in range(0, len(buttons), 2):
        keyboard_rows.append(buttons[i:i+2])
    
    keyboard_rows.append([InlineKeyboardButton(text="💾 Сохранить", callback_data="save_profile_ach")])
    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_profile")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("sel_ach_"))
async def toggle_profile_achievement(callback: CallbackQuery, state: FSMContext):
    """Переключение выбора достижения"""
    ach_id = int(callback.data.split("_")[2])
    
    # Получаем текущий выбор из состояния
    data = await state.get_data()
    selected_ids = data.get('profile_ach_selected', None)
    
    # Если нет в состоянии, загружаем из БД
    if selected_ids is None:
        db = await get_db()
        selected = await db.get_profile_achievements(callback.from_user.id)
        selected_ids = [a['id'] for a in selected]
    
    # Переключаем
    if ach_id in selected_ids:
        selected_ids.remove(ach_id)
    else:
        if len(selected_ids) >= 4:
            await callback.answer("❌ Максимум 4 достижения!", show_alert=True)
            return
        selected_ids.append(ach_id)
    
    # Сохраняем в состояние
    await state.update_data(profile_ach_selected=selected_ids)
    
    # Обновляем отображение
    await profile_achievements_select(callback)


@router.callback_query(F.data == "save_profile_ach")
async def save_profile_achievements(callback: CallbackQuery, state: FSMContext):
    """Сохранение выбранных достижений"""
    db = await get_db()
    
    # Получаем выбор из состояния
    data = await state.get_data()
    selected_ids = data.get('profile_ach_selected', None)
    
    # Если нет в состоянии, загружаем из БД (ничего не менялось)
    if selected_ids is None:
        selected = await db.get_profile_achievements(callback.from_user.id)
        selected_ids = [a['id'] for a in selected]
    
    # Сохраняем в БД
    await db.set_profile_achievements(callback.from_user.id, selected_ids)
    
    await state.clear()
    await callback.answer(f"✅ Сохранено {len(selected_ids)} достижений!")
    await profile_handler(callback.message)


# =================== ОБРАБОТКА СМЕНЫ НИКА (FSM) ===================

@router.message(PlayerStates.changing_nick)
async def process_nick_change(message: Message, state: FSMContext):
    """Обработка ввода нового ника"""
    text = message.text.strip()
    
    # Отмена
    if text.lower() in ['отмена', 'cancel', '❌']:
        await state.clear()
        await message.answer("❌ Смена ника отменена.", reply_markup=get_main_keyboard())
        return
    
    db = await get_db()
    
    # Пытаемся обновить ник
    result = await db.update_username(message.from_user.id, text)
    
    if result.get('success'):
        await state.clear()
        await message.answer(
            f"✅ <b>Ник успешно изменён!</b>\n\n"
            f"Твой новый ник: @{result['username']}",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.answer(
            f"❌ <b>{result.get('message', 'Ошибка')}</b>\n\n"
            f"Попробуй другой ник или напиши 'отмена':",
            parse_mode="HTML"
        )


# =================== ЕЖЕДНЕВНЫЙ БОНУС (ТЗ v4.0 п.13) ===================

async def bonus_menu_handler(message: Message):
    """Ежедневный бонус через кнопку меню (ТЗ v4.0 п.13)"""
    db = await get_db()
    
    # Получаем информацию о бонусе
    streak_data = await db.get_daily_bonus_streak(message.from_user.id)
    streak = streak_data.get('streak', 0)
    can_claim = streak_data.get('can_claim', True)
    
    if can_claim:
        # Бонус доступен - показываем информацию о рулетке
        # Получаем настройки для отображения возможных наград
        rewards_config = await db.calculate_bonus_rewards(streak + 1)
        
        text_lines = [
            "🎁 <b>ЕЖЕДНЕВНЫЙ БОНУС</b>",
            "",
        ]
        
        if streak > 0:
            text_lines.append(f"🔥 Твоя серия: <b>{streak} дней!</b>")
        
        text_lines.extend([
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━",
            "🎲 <b>ЧТО МОЖЕТ ВЫПАСТЬ:</b>",
            ""
        ])
        
        # Показываем возможные награды
        for reward in rewards_config[:4]:  # Показываем первые 4 типа
            icon = reward.get('icon', '🎁')
            name = reward.get('name', '???')
            chance = reward.get('chance', 0) * 100
            text_lines.append(f"{icon} {name} (~{int(chance)}%)")
        
        # Бонус за серию
        text_lines.append("")
        if streak + 1 >= 8:
            text_lines.append("🔥🔥 <b>СУПЕР СЕРИЯ!</b> Награды удвоены!")
        elif streak + 1 >= 4:
            text_lines.append("⭐ <b>Отличная серия!</b> Награды +50%!")
        
        text_lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            "Забери бонус сейчас! 🎁"
        ])
    
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Забрать бонус!", callback_data="claim_daily")],
            [InlineKeyboardButton(text="🌾 На ферму", callback_data="back_farm")]
        ])
    else:
        # Бонус уже получен - считаем время до следующего
        from datetime import datetime, timedelta
        last_claim = streak_data.get('last_claim')
        
        if last_claim:
            try:
                last = datetime.fromisoformat(last_claim.replace('Z', '+00:00'))
                next_claim = last + timedelta(days=1)
                now = datetime.now()
                time_left = next_claim - now
                hours = int(time_left.total_seconds() // 3600)
                minutes = int((time_left.total_seconds() % 3600) // 60)
                time_str = f"{hours:02d}:{minutes:02d}"
            except:
                time_str = "24:00"
        else:
            time_str = "24:00"
        
        text_lines = [
            "🎁 <b>ЕЖЕДНЕВНЫЙ БОНУС</b>",
            "",
            f"⏳ Ты уже получил бонус сегодня!",
            f"",
            f"Следующий через: <b>{time_str}</b>",
            "",
            f"Твоя текущая серия: <b>{streak} {'день' if streak == 1 else 'дней'}</b>",
        ]
        
        # Завтрашний бонус
        if streak + 1 >= 8:
            text_lines.append("🔥 Завтра: <b>Супер-бонус (x2 награды!)</b>")
        elif streak + 1 >= 4:
            text_lines.append("⭐ Завтра: <b>+50% к наградам!</b>")
        else:
            text_lines.append("🎲 Завтра: <b>Обычный бонус</b>")
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔔 Напомнить", callback_data="bonus_remind")],
            [InlineKeyboardButton(text="🌾 На ферму", callback_data="back_farm")]
        ])
    
    await message.answer("\n".join(text_lines), reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "bonus_remind")
async def bonus_remind(callback: CallbackQuery):
    """Установка напоминания о бонусе"""
    # TODO: Добавить логику напоминания
    await callback.answer("🔔 Напоминание установлено!")


# =================== АЛИАСЫ КОМАНД (ТЗ v4.0) ===================

# Алиасы для /start
@router.message(Command("start", "старт", "начать", "привет"))
async def start_with_aliases(message: Message):
    await start_handler(message)

# Алиасы для /help
@router.message(Command("help", "помощь", "хелп", "как_играть", "инструкция"))
async def help_with_aliases(message: Message):
    await help_handler(message)

# Алиасы для /profile
@router.message(Command("profile", "профиль", "я", "моя_статистика", "стата"))
async def profile_with_aliases(message: Message):
    await profile_handler(message)

# Алиасы для /farm
@router.message(Command("farm", "ферма", "грядки", "огород", "моя_ферма"))
async def farm_with_aliases(message: Message):
    await show_farm(message.from_user.id, message)

# Алиасы для /shop
@router.message(Command("shop", "магазин", "шоп", "купить", "покупки"))
async def shop_with_aliases(message: Message):
    await shop_handler(message)

# Алиасы для /inv
@router.message(Command("inv", "инвентарь", "амбар", "склад", "мои_вещи"))
async def inv_with_aliases(message: Message):
    await inventory_handler(message)

# Алиасы для /quests
@router.message(Command("quests", "квесты", "задания", "ежедневки"))
async def quests_with_aliases(message: Message):
    await quests_handler(message)

# Алиасы для /ach
@router.message(Command("ach", "ачивки", "достижения", "успехи"))
async def ach_with_aliases(message: Message):
    await achievements_handler(message)

# Алиасы для /prestige
@router.message(Command("prestige", "престиж", "уровень", "прокачка"))
async def prestige_with_aliases(message: Message):
    await prestige_handler(message)

# Алиасы для /bonus
@router.message(Command("bonus", "бонус", "ежедневный_бонус", "награда"))
async def bonus_with_aliases(message: Message):
    await bonus_menu_handler(message)

# Алиасы для /promo
@router.message(Command("promo", "промо", "промокод", "код"))
async def promo_with_aliases(message: Message):
    await promo_handler(message)

# Алиасы для /top
@router.message(Command("top", "топ", "лидеры", "рейтинг"))
async def top_with_aliases(message: Message):
    await top_handler(message)


# =================== ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ (УМНЫЕ АЛИАСЫ) ===================

@router.message()
async def text_message_handler(message: Message):
    """Обработка текстовых сообщений - умные алиасы"""
    text = message.text.lower().strip()
    
    # Прямые совпадения
    if text in ["посади", "посадить", "сажай"]:
        db = await get_db()
        plots = await db.get_plots(message.from_user.id)
        empty_plots = [p for p in plots if p['status'] == 'empty']
        if empty_plots:
            await message.answer(
                f"🌱 Есть {len(empty_plots)} пустых грядок!\nНажми 🌾 Ферма и выбери грядку для посадки.",
                reply_markup=get_main_keyboard()
            )
        else:
            await message.answer(
                "❌ Нет пустых грядок! Собери урожай или купи новую грядку в магазине.",
                reply_markup=get_main_keyboard()
            )
        return
    
    if text in ["собери", "собрать", "сбор"]:
        await message.answer(
            "🌾 Нажми 🌾 Ферма и собери готовый урожай!",
            reply_markup=get_main_keyboard()
        )
        return
    
    if text in ["удобри", "удобрение", "ускорь"]:
        await message.answer(
            "🧪 Нажми 🌾 Ферма и используй удобрение на растущей грядке.",
            reply_markup=get_main_keyboard()
        )
        return
    
    if text in ["продай", "продать", "продажа"]:
        await message.answer(
            "💰 Нажми 🏪 Магазин → 💰 Продать для продажи урожая.",
            reply_markup=get_main_keyboard()
        )
        return
    
    if text in ["купи", "купить", "магазин", "шоп", "shop"]:
        await shop_handler(message)
        return
    
    if text.startswith("активируй "):
        # Попытка активировать промокод
        code = text.replace("активируй ", "").upper()
        # Создаем фейковое сообщение с командой промо
        message.text = f"/promo {code}"
        await promo_handler(message)
        return
    
    # Навигационные алиасы
    navigation_aliases = {
        "ферма": "🌾 Ферма",
        "ферму": "🌾 Ферма",
        "магазин": "🏪 Магазин",
        "инвентарь": "📦 Инв",
        "инв": "📦 Инв",
        "квесты": "📜 Квесты",
        "ачивки": "🏆 Ачивки",
        "достижения": "🏆 Ачивки",
        "престиж": "🚜 Прест",
        "профиль": "👤 Профиль",
        "бонус": "🎁 Бонус",
        "помощь": "❓ Помощь",
        "топ": "🏆 Топ",
    }
    
    if text in navigation_aliases:
        message.text = navigation_aliases[text]
        await text_message_handler(message)
        return
    
    # Неизвестный текст
    await message.answer(
        f"❓ Я не совсем понял \"{message.text}\"\n\n"
        "Попробуй:\n"
        "• Нажать кнопку в меню\n"
        "• Использовать /help для списка команд\n"
        "• Написать \"ферма\", \"профиль\" или \"бонус\"",
        reply_markup=get_main_keyboard()
    )
 