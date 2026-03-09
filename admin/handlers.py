"""
Игровые обработчики для Lazy Farmer Bot
Основные команды и взаимодействия игрока
Версия: 2.1 (исправлены ошибки, добавлены импорты)
"""

import asyncio
import datetime
import logging
from datetime import datetime as dt

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from admin import keyboards
from admin.database import get_database
from admin.keyboards import get_back_keyboard, get_inventory_category_keyboard, get_inventory_keyboard, get_item_detail_keyboard, get_main_keyboard, get_farm_keyboard, get_sell_keyboard, get_shop_items_keyboard, get_shop_keyboard, get_active_quests
from admin.states import PlayerStates
from admin.constants import TEXT_IN_DEVELOPMENT
from admin.utils import format_number, format_time

router = Router()

# Логгер
logger = logging.getLogger(__name__)

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
            f"У тебя есть {int(user.get('balance') or 0):,}🪙",
            "Выбери, что посадить:",
            "",
        ]
    else:
        # Сценарий для опытных игроков - компактный
        text_lines = [
            f"🌱 <b>Посадка на грядке #{plot_num}</b>",
            f"💰 Баланс: {int(user.get('balance') or 0):,}🪙",
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
        text_lines.append(f"Новый баланс: {int(user.get('balance') or 0):,}🪙")
    
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
        f"Твой баланс: {int(user.get('balance') or 0):,}🪙\n\n"
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
        f"📊 <b>Параметры:</b>",
        f"💰 Цена продажи: {sell_price}🪙 (x{multiplier})",
        f"⏱ Время роста: {growth_time} сек",
        f"📊 Требуемый уровень: {required_level}",
        f"📁 Категория: {category}",
        "",
        f"💵 Общая стоимость: {value_with_multiplier:,}🪙"
    ]
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        parse_mode="HTML",
        reply_markup=keyboards
    )


# ============ ОБРАБОТЧИКИ МЕНЮ (добавлены) ============

async def quests_handler(message: Message):
    """Обработчик квестов - ТЗ v4.0 п.7"""
    db = await get_database()
    
    # Получаем активные квесты
    active_quests = await db.get_active_quests(message.from_user.id)
    
    text = f"📜 <b>КВЕСТЫ</b>\n\n"
    
    if not active_quests:
        text += "Нет активных квестов. Новые квесты появятся завтра!"
    else:
        for quest in active_quests:
            progress = quest.get('progress', 0)
            required = quest.get('required', 1)
            status = "✅" if progress >= required else "⏳"
            text += f"{status} {quest.get('name', 'Квест')}: {progress}/{required}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="quests_refresh")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])
    
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


# ============ ОБРАБОТЧИКИ КНОПОК МЕНЮ (добавлены) ============

@router.message(F.text == "👤 Фермер")
async def farmer_handler_button(message: Message):
    """Обработчик кнопки Фермер - показывает информацию о фермерах"""
    db = await get_database()
    
    # Получаем информацию о фермерах пользователя
    farmers = await db.fetchall(
        """SELECT farmer_id, farmer_type, hired_at, plots_managed, total_harvests 
           FROM farmers WHERE user_id = ? AND is_active = 1""",
        (message.from_user.id,)
    )
    
    text = "👤 <b>ФЕРМЕРЫ</b>\n\n"
    
    if not farmers:
        text += (
            "У тебя пока нет фермеров!\n\n"
            "👨‍🌾 <b>Что такое фермер?</b>\n"
            "Фермер — это автоматический помощник, который собирает "
            "урожай за тебя!\n\n"
            "<b>Как нанять:</b>\n"
            "• Доступно с 10 престижа\n"
            "• Найми в разделе Улучшений\n"
            "• Максимум 5 фермеров\n\n"
            "👆 Нажми кнопку ниже, чтобы нанять первого фермера!"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👨‍🌾 Нанять фермера", callback_data="hire_farmer")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
        ])
    else:
        text += f"<b>Твои фермеры ({len(farmers)}):</b>\n\n"
        
        for i, farmer in enumerate(farmers, 1):
            farmer_id, farmer_type, hired_at, plots_managed, total_harvests = farmer
            type_names = {'basic': '👨‍🌾 Обычный', 'pro': '👩‍🌾 Профи', 'expert': '🤠 Эксперт'}
            type_name = type_names.get(farmer_type, '👨‍🌾 Фермер')
            
            text += f"{i}. {type_name}\n"
            text += f"   📅 Нанят: {hired_at[:10] if hired_at else '?'}\n"
            text += f"   🌱 Грядок: {plots_managed}\n"
            text += f"   🌾 Сборов: {total_harvests}\n\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Нанять ещё", callback_data="hire_farmer")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="farmers_stats")],
            [InlineKeyboardButton(text="⚙️ Управление", callback_data="farmers_manage")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
        ])
    
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.message(F.text == "👥 Рефералы")
async def referrals_handler_button(message: Message):
    """Обработчик кнопки Рефералы"""
    db = await get_database()
    
    # Получаем реферальную информацию
    user = await db.get_user(message.from_user.id)
    referral_code = user.get('referral_code', f"REF{message.from_user.id}")
    
    # Получаем статистику рефералов
    referrals_count = await db.fetchone(
        "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?",
        (message.from_user.id,)
    )
    referrals_count = referrals_count[0] if referrals_count else 0
    
    total_earned = await db.fetchone(
        "SELECT COALESCE(SUM(coins_earned), 0) FROM referrals WHERE referrer_id = ?",
        (message.from_user.id,)
    )
    total_earned = total_earned[0] if total_earned else 0
    
    text = (
        "👥 <b>РЕФЕРАЛЬНАЯ СИСТЕМА</b>\n\n"
        f"<b>Твоя реферальная ссылка:</b>\n"
        f"<code>https://t.me/{(await message.bot.get_me()).username}?start={referral_code}</code>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"👥 Приглашено друзей: {referrals_count}\n"
        f"💰 Заработано: {total_earned:,}🪙\n\n"
        "<b>Награды за рефералов:</b>\n"
        "• 1 друг = 500🪙 + 5💎\n"
        "• 5 друзей = 2000🪙 + 15💎\n"
        "• 10 друзей = бонус множитель\n\n"
        "👆 Поделись ссылкой с друзьями!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список рефералов", callback_data="referrals_list")],
        [InlineKeyboardButton(text="📊 Топ рефералов", callback_data="referrals_top")],
        [InlineKeyboardButton(text="🔗 Копировать ссылку", callback_data="referrals_copy")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])
    
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == "referrals_list")
async def referrals_list(callback: CallbackQuery):
    """Показывает список рефералов"""
    db = await get_database()
    
    referrals = await db.fetchall(
        """SELECT r.referred_id, r.created_at, r.coins_earned, u.username 
           FROM referrals r
           JOIN users u ON r.referred_id = u.user_id
           WHERE r.referrer_id = ?
           ORDER BY r.created_at DESC""",
        (callback.from_user.id,)
    )
    
    text = "👥 <b>СПИСОК РЕФЕРАЛОВ</b>\n\n"
    
    if not referrals:
        text += "У тебя пока нет рефералов.\n\n"
        text += "👆 Поделись своей реферальной ссылкой с друзьями!"
    else:
        text += f"Всего приглашено: {len(referrals)}\n\n"
        for i, ref in enumerate(referrals[:10], 1):
            ref_id, created_at, coins_earned, username = ref
            username = username or f"User{ref_id}"
            text += f"{i}. @{username}\n"
            text += f"   📅 {created_at[:10] if created_at else '?'}\n"
            text += f"   💰 +{coins_earned:,}🪙\n\n"
        
        if len(referrals) > 10:
            text += f"...и ещё {len(referrals) - 10} рефералов\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к рефералам", callback_data="back_referrals")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "referrals_top")
async def referrals_top(callback: CallbackQuery):
    """Показывает топ рефералов"""
    db = await get_database()
    
    top = await db.fetchall(
        """SELECT r.referrer_id, u.username, COUNT(*) as count, SUM(r.coins_earned) as earned
           FROM referrals r
           JOIN users u ON r.referrer_id = u.user_id
           GROUP BY r.referrer_id
           ORDER BY count DESC
           LIMIT 10"""
    )
    
    text = "🏆 <b>ТОП РЕФЕРАЛОВ</b>\n\n"
    
    if not top:
        text += "Пока никто не пригласил друзей!\n"
        text += "Будь первым! 🥇"
    else:
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        for i, row in enumerate(top, 1):
            user_id, username, count, earned = row
            username = username or f"User{user_id}"
            medal = medals[i-1] if i <= 10 else f"{i}."
            text += f"{medal} @{username}\n"
            text += f"   👥 {count} друзей | 💰 {earned:,}🪙\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к рефералам", callback_data="back_referrals")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "referrals_copy")
async def referrals_copy(callback: CallbackQuery):
    """Копирует реферальную ссылку"""
    db = await get_database()
    user = await db.get_user(callback.from_user.id)
    referral_code = user.get('referral_code', f"REF{callback.from_user.id}")
    
    bot_info = await callback.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={referral_code}"
    
    text = (
        "🔗 <b>ТВОЯ РЕФЕРАЛЬНАЯ ССЫЛКА</b>\n\n"
        f"<code>{link}</code>\n\n"
        "👆 Нажми, чтобы скопировать\n"
        "📤 Поделись с друзьями!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Поделиться", url=f"https://t.me/share/url?url={link}&text=Присоединяйся к Lazy Farmer!")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_referrals")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer("🔗 Ссылка готова!")


@router.callback_query(F.data == "back_referrals")
async def back_referrals(callback: CallbackQuery):
    """Возврат к рефералам"""
    await referrals_handler_button(callback.message)
    await callback.answer()


@router.message(F.text == "🎁 Бонус")
async def daily_bonus_handler(message: Message):
    """Обработчик кнопки Бонус - ежедневная награда"""
    db = await get_database()
    
    # Получаем информацию о последнем бонусе
    user_daily = await db.fetchone(
        """SELECT last_claim_date, streak FROM user_daily 
           WHERE user_id = ?""",
        (message.from_user.id,)
    )
    
    if not user_daily:
        # Создаем запись если нет
        await db.execute(
            """INSERT OR IGNORE INTO user_daily (user_id, last_claim_date, streak)
               VALUES (?, date('now', '-1 day'), 0)""",
            (message.from_user.id,)
        )
        last_claim = None
        streak = 0
    else:
        last_claim = user_daily[0]
        streak = user_daily[1] or 0
    
    # Проверяем можно ли забрать
    can_claim = True
    time_left = ""
    
    if last_claim:
        last_date = datetime.strptime(last_claim, "%Y-%m-%d %H:%M:%S") if " " in last_claim else datetime.strptime(last_claim, "%Y-%m-%d")
        now = datetime.now()
        
        # Проверяем прошло ли 24 часа
        time_diff = now - last_date
        if time_diff.total_seconds() < 86400:  # 24 часа
            can_claim = False
            hours_left = int((86400 - time_diff.total_seconds()) // 3600)
            mins_left = int((86400 - time_diff.total_seconds()) % 3600 // 60)
            time_left = f"{hours_left}ч {mins_left}м"
    
    # Получаем награду за текущий день
    day = (streak % 7) + 1
    rewards = {
        1: ("100🪙", "💰"),
        2: ("150🪙", "💰"),
        3: ("200🪙", "💰"),
        4: ("300🪙", "💰"),
        5: ("500🪙", "💰"),
        6: ("1💎", "💎"),
        7: ("1000🪙 + 5💎", "🎁")
    }
    reward, icon = rewards.get(day, ("100🪙", "💰"))
    
    # Формируем текст
    text_lines = [
        f"{icon} <b>ЕЖЕДНЕВНЫЙ БОНУС</b>",
        "",
        f"📅 День: {day}/7",
        f"🔥 Серия: {streak} дней",
        "",
        f"🎁 Сегодняшняя награда: <b>{reward}</b>",
        ""
    ]
    
    if can_claim:
        text_lines.append("✅ Бонус доступен!")
        button_text = "🎁 Забрать бонус"
        button_callback = "claim_daily_bonus"
    else:
        text_lines.append(f"⏳ До следующего бонуса: {time_left}")
        button_text = "⏳ Подождать"
        button_callback = "bonus_wait"
    
    text_lines.append("")
    text_lines.append("📈 Чем дольше серия, тем лучше награды!")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=button_text, callback_data=button_callback)],
        [InlineKeyboardButton(text="📊 История", callback_data="bonus_history")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])
    
    await message.answer("\n".join(text_lines), parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == "claim_daily_bonus")
async def claim_daily_bonus(callback: CallbackQuery):
    """Получение ежедневного бонуса"""
    db = await get_database()
    
    # Проверяем последний бонус
    user_daily = await db.fetchone(
        """SELECT last_claim_date, streak FROM user_daily 
           WHERE user_id = ?""",
        (callback.from_user.id,)
    )
    
    last_claim = user_daily[0] if user_daily else None
    streak = user_daily[1] if user_daily else 0
    
    # Проверяем можно ли забрать
    if last_claim:
        last_date = datetime.strptime(last_claim, "%Y-%m-%d %H:%M:%S") if " " in last_claim else datetime.strptime(last_claim, "%Y-%m-%d")
        now = datetime.now()
        time_diff = now - last_date
        
        if time_diff.total_seconds() < 86400:
            await callback.answer("⏳ Бонус уже получен! Приходи завтра.", show_alert=True)
            return
    
    # Определяем награду
    day = ((streak or 0) % 7) + 1
    rewards = {
        1: (100, 0),
        2: (150, 0),
        3: (200, 0),
        4: (300, 0),
        5: (500, 0),
        6: (0, 1),
        7: (1000, 5)
    }
    coins, gems = rewards.get(day, (100, 0))
    
    # Проверяем серию (если прошло больше 48 часов - сбрасываем)
    new_streak = 1
    if last_claim:
        last_date = datetime.strptime(last_claim, "%Y-%m-%d %H:%M:%S") if " " in last_claim else datetime.strptime(last_claim, "%Y-%m-%d")
        now = datetime.now()
        if (now - last_date).total_seconds() < 172800:  # 48 часов
            new_streak = (streak or 0) + 1
    
    # Начисляем награду
    await db.update_balance(callback.from_user.id, coins)
    if gems > 0:
        await db.execute(
            "UPDATE users SET gems = gems + ? WHERE user_id = ?",
            (gems, callback.from_user.id)
        )
    
    # Обновляем дату
    await db.execute(
        """INSERT INTO user_daily (user_id, last_claim_date, streak)
           VALUES (?, datetime('now'), ?)
           ON CONFLICT(user_id) DO UPDATE SET 
           last_claim_date = datetime('now'), streak = ?""",
        (callback.from_user.id, new_streak, new_streak)
    )
    
    # Логируем в историю
    await db.execute(
        """INSERT INTO daily_bonus_history (user_id, bonus_day, reward_type, reward_amount, streak_at_claim)
           VALUES (?, ?, 'coins', ?, ?)""",
        (callback.from_user.id, day, coins, new_streak)
    )
    
    await callback.answer(f"🎉 Получено: {coins}🪙 {gems}💎!", show_alert=True)
    await daily_bonus_handler(callback.message)


@router.callback_query(F.data == "bonus_wait")
async def bonus_wait(callback: CallbackQuery):
    """Показывает оставшееся время"""
    await callback.answer("⏳ Приходи через несколько часов!", show_alert=True)


@router.callback_query(F.data == "bonus_history")
async def bonus_history(callback: CallbackQuery):
    """История полученных бонусов"""
    db = await get_database()
    
    history = await db.fetchall(
        """SELECT bonus_day, reward_amount, streak_at_claim, claimed_at
           FROM daily_bonus_history
           WHERE user_id = ?
           ORDER BY claimed_at DESC
           LIMIT 10""",
        (callback.from_user.id,)
    )
    
    text = "📊 <b>ИСТОРИЯ БОНУСОВ</b>\n\n"
    
    if not history:
        text += "Ты ещё не получал бонусы.\n"
        text += "🎁 Нажми \"Забрать бонус\"!"
    else:
        for day, amount, streak, claimed_at in history:
            date_str = claimed_at[:10] if claimed_at else "?"
            text += f"📅 {date_str} | День {day} | {amount}🪙 | 🔥{streak}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к бонусу", callback_data="back_bonus")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "back_bonus")
async def back_bonus(callback: CallbackQuery):
    """Возврат к бонусу"""
    await daily_bonus_handler(callback.message)
    await callback.answer()


@router.message(F.text == "🎉 Ивент")
async def event_handler_button(message: Message):
    """Обработчик кнопки Ивент - показывает активные события"""
    db = await get_database()
    
    # Получаем активные события
    active_events = await db.fetchall(
        """SELECT event_id, name, description, event_type, start_date, end_date, reward_coins, reward_gems 
           FROM seasonal_events 
           WHERE is_active = 1 AND start_date <= datetime('now') AND end_date >= datetime('now')
           ORDER BY start_date DESC"""
    )
    
    text = "🎉 <b>СЕЗОННЫЕ СОБЫТИЯ</b>\n\n"
    
    if not active_events:
        text += (
            "Сейчас нет активных событий!\n\n"
            "🔔 <b>Следите за обновлениями!</b>\n"
            "Новые ивенты появляются регулярно:\n"
            "• 🎃 Хэллоуин (октябрь)\n"
            "• 🎄 Новый год (декабрь)\n"
            "• 🐰 Пасха (весна)\n"
            "• 🌞 Летний фестиваль\n\n"
            "Приходи позже!"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 История ивентов", callback_data="events_history")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
        ])
    else:
        text += "<b>Активные события:</b>\n\n"
    
        for event in active_events:
            event_id, name, description, event_type, start_date, end_date, reward_coins, reward_gems = event
            text += f"🎊 <b>{name}</b>\n"
            text += f"📝 {description[:100]}...\n" if len(description) > 100 else f"📝 {description}\n"
            text += f"⏱ До: {end_date[:10] if end_date else '?'}\n"
            text += f"🎁 Награды: {reward_coins}🪙 {reward_gems}💎\n\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Участвовать", callback_data="event_join")],
            [InlineKeyboardButton(text="🏆 Топ участников", callback_data="event_top")],
            [InlineKeyboardButton(text="📊 Мой прогресс", callback_data="event_progress")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
        ])
    
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == "event_join")
async def event_join(callback: CallbackQuery):
    """Участие в событии"""
    db = await get_database()
    
    # Получаем активное событие
    event = await db.fetchone(
        """SELECT event_id, name FROM seasonal_events 
           WHERE is_active = 1 AND start_date <= datetime('now') AND end_date >= datetime('now')
           LIMIT 1"""
    )
    
    if not event:
        await callback.answer("❌ Нет активных событий!", show_alert=True)
        return
    
    event_id, event_name = event
    
    # Проверяем, участвует ли уже
    existing = await db.fetchone(
        "SELECT 1 FROM event_participation WHERE event_id = ? AND user_id = ?",
        (event_id, callback.from_user.id)
    )
    
    if existing:
        await callback.answer("✅ Ты уже участвуешь!", show_alert=True)
    else:
        # Регистрируем участие
        await db.execute(
            """INSERT INTO event_participation (event_id, user_id, progress, joined_at)
               VALUES (?, ?, 0, datetime('now'))""",
            (event_id, callback.from_user.id)
        )
        await callback.answer(f"🎉 Ты участвуешь в '{event_name}'!", show_alert=True)
    
    await event_handler_button(callback.message)


@router.callback_query(F.data == "event_top")
async def event_top(callback: CallbackQuery):
    """Топ участников события"""
    db = await get_database()
    
    # Получаем активное событие
    event = await db.fetchone(
        """SELECT event_id, name FROM seasonal_events 
           WHERE is_active = 1 AND start_date <= datetime('now') AND end_date >= datetime('now')
           LIMIT 1"""
    )
    
    if not event:
        await callback.answer("❌ Нет активных событий!", show_alert=True)
        return
    
    event_id, event_name = event
    
    # Получаем топ
    top = await db.fetchall(
        """SELECT ep.user_id, u.username, ep.progress
           FROM event_participation ep
           JOIN users u ON ep.user_id = u.user_id
           WHERE ep.event_id = ?
           ORDER BY ep.progress DESC
           LIMIT 10""",
        (event_id,)
    )
    
    text = f"🏆 <b>ТОП УЧАСТНИКОВ: {event_name}</b>\n\n"
    
    if not top:
        text += "Пока никто не участвует!\n"
        text += "🎯 Будь первым!"
    else:
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        for i, row in enumerate(top, 1):
            user_id, username, progress = row
            username = username or f"User{user_id}"
            medal = medals[i-1] if i <= 10 else f"{i}."
            text += f"{medal} @{username} - {progress} очков\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к ивенту", callback_data="back_event")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "event_progress")
async def event_progress(callback: CallbackQuery):
    """Прогресс пользователя в событии"""
    db = await get_database()
    
    # Получаем активное событие
    event = await db.fetchone(
        """SELECT event_id, name, reward_coins, reward_gems, target_progress
           FROM seasonal_events 
           WHERE is_active = 1 AND start_date <= datetime('now') AND end_date >= datetime('now')
           LIMIT 1"""
    )
    
    if not event:
        await callback.answer("❌ Нет активных событий!", show_alert=True)
        return
    
    event_id, event_name, reward_coins, reward_gems, target_progress = event
    
    # Получаем прогресс
    progress_data = await db.fetchone(
        """SELECT progress, completed, reward_claimed FROM event_participation 
           WHERE event_id = ? AND user_id = ?""",
        (event_id, callback.from_user.id)
    )
    
    if not progress_data:
        text = (
            f"📊 <b>{event_name}</b>\n\n"
            "🎯 Ты ещё не участвуешь!\n\n"
            'Нажми "Участвовать" чтобы присоединиться.'
        )
    else:
        progress, completed, reward_claimed = progress_data
        target = target_progress or 100
        percent = min(int((progress / target) * 100), 100)
        bar = "█" * (percent // 10) + "░" * (10 - percent // 10)
        
        text = (
            f"📊 <b>МОЙ ПРОГРЕСС: {event_name}</b>\n\n"
            f"Прогресс: [{bar}] {percent}%\n"
            f"{progress} / {target} очков\n\n"
        )
        
        if completed:
            if reward_claimed:
                text += "✅ Награда получена!"
            else:
                text += "🎁 Награда доступна! Получи её!"
        else:
            text += f"🎁 Награда: {reward_coins}🪙 {reward_gems}💎"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к ивенту", callback_data="back_event")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "back_event")
async def back_event(callback: CallbackQuery):
    """Возврат к ивентам"""
    await event_handler_button(callback.message)
    await callback.answer()


@router.callback_query(F.data == "events_history")
async def events_history(callback: CallbackQuery):
    """История ивентов"""
    db = await get_database()
    
    events = await db.fetchall(
        """SELECT name, event_type, end_date FROM seasonal_events 
           WHERE end_date < datetime('now')
           ORDER BY end_date DESC
           LIMIT 5"""
    )
    
    text = "📋 <b>ИСТОРИЯ ИВЕНТОВ</b>\n\n"
    
    if not events:
        text += "История пуста.\n"
    else:
        for name, event_type, end_date in events:
            text += f"• {name} ({event_type})\n"
            text += f"  Завершён: {end_date[:10] if end_date else '?'}\n\n"
    
    text += "\n🔔 Следи за новыми ивентами!"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.message(F.text == "💰 Перевод")
async def transfer_handler_button(message: Message, state: FSMContext):
    """Обработчик кнопки Перевод - начинает процесс перевода"""
    text = (
        "💰 <b>ПЕРЕВОД МОНЕТ</b>\n\n"
        "Отправь монеты другому игроку!\n\n"
        "<b>Комиссия:</b> 5%\n"
        "<b>Минимум:</b> 100🪙\n"
        "<b>Максимум:</b> 100,000🪙\n\n"
        "👇 Введи ID или @username получателя:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="main_menu")]
    ])
    
    await state.set_state(PlayerStates.waiting_transfer_recipient)
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.message(F.text == "💬 Чат")
async def chat_handler_button(message: Message):
    """Обработчик кнопки Чат - показывает ссылку на чат"""
    text = (
        "💬 <b>ОФИЦИАЛЬНЫЙ ЧАТ</b>\n\n"
        "Присоединяйся к нашему сообществу!\n\n"
        "<b>В чате ты найдёшь:</b>\n"
        "• 💡 Советы по игре\n"
        "• 📢 Новости и обновления\n"
        "• 🎁 Эксклюзивные промокоды\n"
        "• 🤝 Помощь от других игроков\n"
        "• 💬 Общение с единомышленниками\n\n"
        "👇 Переходи по ссылке:"
    )
    
    # Ссылка на чат (можно изменить на реальную)
    chat_link = "https://t.me/lazyfarmer_chat"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Вступить в чат", url=chat_link)],
        [InlineKeyboardButton(text="✅ Проверить вступление", callback_data="chat_check")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])
    
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == "chat_check")
async def chat_check(callback: CallbackQuery):
    """Проверка вступления в чат - начисление награды"""
    db = await get_database()
    
    # Проверяем, получал ли уже награду
    claimed = await db.fetchone(
        "SELECT 1 FROM user_stats WHERE user_id = ? AND chat_reward_claimed = 1",
        (callback.from_user.id,)
    )
    
    if claimed:
        await callback.answer("ℹ️ Ты уже получил награду за вступление!", show_alert=True)
        return
    
    # Отмечаем награду как полученную
    await db.execute(
        """INSERT INTO user_stats (user_id, chat_reward_claimed, chat_reward_claimed_at)
           VALUES (?, 1, datetime('now'))
           ON CONFLICT(user_id) DO UPDATE SET 
           chat_reward_claimed = 1, chat_reward_claimed_at = datetime('now')""",
        (callback.from_user.id,)
    )
    
    # Начисляем награду
    await db.update_balance(callback.from_user.id, 500)
    
    await callback.answer("🎉 Награда получена: 500🪙", show_alert=True)
    
    text = (
        "💬 <b>СПАСИБО ЗА ВСТУПЛЕНИЕ!</b>\n\n"
        "🎁 Тебе начислено: <b>500🪙</b>\n\n"
        "Теперь ты будешь получать:\n"
        "• 📢 Новости первым\n"
        "• 🎁 Эксклюзивные промокоды\n"
        "• 💡 Советы от опытных игроков"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Перейти в чат", url="https://t.me/lazyfarmer_chat")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(F.text == "❓ Помощь")
async def help_handler_button(message: Message):
    """Обработчик кнопки Помощь - показывает справку"""
    text = (
        "❓ <b>ПОМОЩЬ И ИНСТРУКЦИИ</b>\n\n"
        "<b>🌾 Основные команды:</b>\n"
        "/start — Начать игру\n"
        "/farm — Твоя ферма\n"
        "/shop — Магазин семян\n"
        "/profile — Твой профиль\n"
        "/bonus — Ежедневный бонус\n\n"
        "<b>💰 Экономика:</b>\n"
        "• Сажай семена на грядках\n"
        "• Жди пока они вырастут\n"
        "• Собирай и продавай урожай\n"
        "• Купи больше грядок\n"
        "• Нанимай фермеров (с 10 престижа)\n\n"
        "<b>🚜 Престиж:</b>\n"
        "При наборе 100,000🪙 можно сбросить прогресс "
        "и получить +10% к доходу!\n\n"
        "<b>❓ Вопросы?</b>\n"
        "Обращайся к @support"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Полная инструкция", callback_data="help_full")],
        [InlineKeyboardButton(text="🎥 Видео-гайд", callback_data="help_video")],
        [InlineKeyboardButton(text="💬 Задать вопрос", url="https://t.me/support")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])
    
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == "help_full")
async def help_full(callback: CallbackQuery):
    """Полная инструкция"""
    text = (
        "📖 <b>ПОЛНАЯ ИНСТРУКЦИЯ</b>\n\n"
        "<b>🎯 Начало игры:</b>\n"
        "1. Нажми /start для регистрации\n"
        "2. Получи стартовый капитал\n"
        "3. Купи семена в магазине\n"
        "4. Посади на свободную грядку\n\n"
        "<b>🌾 Выращивание:</b>\n"
        "• Каждое растение имеет время роста\n"
        "• Используй удобрения для ускорения\n"
        "• Собирай урожай когда созреет\n"
        "• Продавай или используй для заданий\n\n"
        "<b>📈 Престиж:</b>\n"
        "• При накоплении 100,000🪙 можно сбросить прогресс\n"
        "• Получи +10% к доходу за каждый престиж\n"
        "• Максимум: 10 престиж (+100% дохода)\n\n"
        "<b>👨‍🌾 Фермеры:</b>\n"
        "• Доступны с 10 уровня престижа\n"
        "• Автоматически собирают урожай\n"
        "• Типы: Обычный, Профи, Эксперт\n\n"
        "<b>🏆 Ачивки:</b>\n"
        "• Выполняй задания для получения\n"
        "• Получай награды: монеты и кристаллы\n"
        "• Секретные ачивки за особые действия\n\n"
        "<b>🎉 Ивенты:</b>\n"
        "• Сезонные события с бонусами\n"
        "• Участвуй в топах и получай награды\n"
        "• Эксклюзивные предметы только во время ивентов"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к помощи", callback_data="back_help")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "help_video")
async def help_video(callback: CallbackQuery):
    """Видео-гайд"""
    text = (
        "🎥 <b>ВИДЕО-ГАЙДЫ</b>\n\n"
        "Скоро здесь появятся обучающие видео!\n\n"
        "📚 А пока изучи текстовую инструкцию:\n"
        "• /help - краткая справка\n"
        "• 📖 Полная инструкция (выше)\n"
        "• 💬 Задай вопрос в чате\n\n"
        "🔔 Подпишись на канал, чтобы не пропустить видео!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Канал новостей", url="https://t.me/lazyfarmer_news")],
        [InlineKeyboardButton(text="🔙 Назад к помощи", callback_data="back_help")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "back_help")
async def back_help(callback: CallbackQuery):
    """Возврат к помощи"""
    await help_handler_button(callback.message)
    await callback.answer()


@router.message(F.text == "🎁 Промо")
async def promo_handler_button(message: Message, state: FSMContext):
    """Обработчик кнопки Промо - активация промокода"""
    text = (
        "🎁 <b>ПРОМОКОДЫ</b>\n\n"
        "Активируй промокод и получи награду!\n\n"
        "<b>Где найти промокоды:</b>\n"
        "• 💬 В нашем чате\n"
        "• 📢 В канале новостей\n"
        "• 🎉 Во время ивентов\n"
        "• 👥 От друзей-рефералов\n\n"
        "👇 Введи промокод:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Мои промокоды", callback_data="promo_my")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="main_menu")]
    ])
    
    await state.set_state(PlayerStates.waiting_promo_code)
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == "promo_my")
async def promo_my(callback: CallbackQuery):
    """Показывает историю использованных промокодов"""
    db = await get_database()
    
    promos = await db.fetchall(
        """SELECT pc.code, ap.reward_coins, ap.reward_gems, pc.claimed_at
           FROM promocode_claims pc
           JOIN active_promocodes ap ON pc.promocode_id = ap.promocode_id
           WHERE pc.user_id = ?
           ORDER BY pc.claimed_at DESC
           LIMIT 10""",
        (callback.from_user.id,)
    )
    
    text = "📋 <b>ИСТОРИЯ ПРОМОКОДОВ</b>\n\n"
    
    if not promos:
        text += "Ты ещё не использовал промокоды.\n\n"
        text += "🎁 Введи промокод и получи награду!"
    else:
        text += f"Использовано промокодов: {len(promos)}\n\n"
        for code, coins, gems, claimed_at in promos:
            rewards = []
            if coins > 0:
                rewards.append(f"{coins:,}🪙")
            if gems > 0:
                rewards.append(f"{gems}💎")
            reward_str = " + ".join(rewards) if rewards else "Нет награды"
            date_str = claimed_at[:10] if claimed_at else "?"
            text += f"• <code>{code}</code>\n"
            text += f"  🎁 {reward_str} | 📅 {date_str}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Ввести промокод", callback_data="promo_enter")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "promo_enter")
async def promo_enter(callback: CallbackQuery, state: FSMContext):
    """Ввод промокода"""
    text = (
        "🎁 <b>АКТИВАЦИЯ ПРОМОКОДА</b>\n\n"
        "Введи промокод в чат:\n"
        "👇 Пример: <code>LAZY2024</code>"
    )
    
    await state.set_state(PlayerStates.waiting_promo_code)
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()


# ============ CALLBACK ОБРАБОТЧИКИ ДОСТИЖЕНИЙ ============

@router.callback_query(F.data.startswith("ach_category_"))
async def achievements_category(callback: CallbackQuery):
    """Показывает ачивки выбранной категории"""
    category = callback.data.replace("ach_category_", "")
    db = await get_database()
    
    # Получаем ачивки категории
    achievements = await db.fetchall(
        """SELECT a.code, a.name, a.description, a.reward_coins, a.reward_gems,
                  pa.completed, pa.reward_claimed
           FROM achievements a
           LEFT JOIN player_achievements pa ON a.code = pa.achievement_code AND pa.user_id = ?
           WHERE a.category_id = ? AND a.is_active = 1
           ORDER BY a.sort_order""",
        (callback.from_user.id, category)
    )
    
    category_names = {
        'farm': '🌾 Ферма',
        'economy': '💰 Экономика',
        'events': '🎉 События',
        'secret': '🔒 Секретные'
    }
    
    text = f"🏆 <b>{category_names.get(category, 'АЧИВКИ')}</b>\n\n"
    
    if not achievements:
        text += "В этой категории пока нет достижений!"
    else:
        for ach in achievements:
            code, name, description, reward_coins, reward_gems, completed, reward_claimed = ach
            status = "✅" if completed else "⏳"
            reward = f"{reward_coins}🪙" if reward_coins else ""
            if reward_gems:
                reward += f" {reward_gems}💎"
            
            text += f"{status} <b>{name}</b>\n"
            text += f"   {description}\n"
            text += f"   🎁 {reward}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к категориям", callback_data="achievements_back")],
        [InlineKeyboardButton(text="🏆 Главное меню", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "back_achievements")
async def achievements_back(callback: CallbackQuery):
    """Возврат к категориям ачивок"""
    await achievements_handler(callback.message)
    await callback.answer()


async def achievements_handler(message: Message):
    """Обработчик ачивок - ТЗ v4.0 п.15"""
    db = await get_database()
    
    # Получаем статистику ачивок пользователя
    stats = await db.get_achievement_stats(message.from_user.id)
    
    text = f"🏆 <b>ДОСТИЖЕНИЯ</b>\n\n"
    text += f"📊 Всего: {stats.get('total', 0)}\n"
    text += f"✅ Получено: {stats.get('completed', 0)}\n"
    text += f"🎁 Награды: {stats.get('rewards_claimed', 0)}\n\n"
    text += "Выберите категорию:"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌾 Ферма", callback_data="achievements_category:farm")],
        [InlineKeyboardButton(text="💰 Экономика", callback_data="achievements_category:economy")],
        [InlineKeyboardButton(text="🎉 События", callback_data="achievements_category:events")],
        [InlineKeyboardButton(text="🔒 Секретные", callback_data="achievements_category:secret")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])
    
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


async def prestige_handler(message: Message):
    """Обработчик престижа - ТЗ v4.0 п.12"""
    db = await get_database()
    user = await db.get_user(message.from_user.id)
    
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден!")
        return
    
    prestige = user.get('prestige', 0)
    balance = user.get('balance', 0)
    required_balance = 100000 * (prestige + 1)
    
    text = f"🚜 <b>ПРЕСТИЖ</b>\n\n"
    text += f"Текущий престиж: {prestige}\n"
    text += f"Множитель: x{1.0 + (prestige * 0.1):.1f}\n\n"
    
    if balance >= required_balance:
        text += f"✅ Вы можете повысить престиж!\n"
        text += f"Стоимость: {required_balance:,}🪙\n\n"
        text += "⚠️ Престиж сбросит ваш прогресс, но даст бонусы!"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🆙 Повысить престиж", callback_data="prestige_confirm")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
        ])
    else:
        text += f"❌ Недостаточно средств\n"
        text += f"У вас: {balance:,}🪙\n"
        text += f"Нужно: {required_balance:,}🪙\n\n"
        text += f"Осталось: {required_balance - balance:,}🪙"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
        ])
    
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


async def profile_handler(message: Message):
    """Обработчик профиля - ТЗ v4.0 п.5"""
    db = await get_database()
    user = await db.get_user(message.from_user.id)
    
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден!")
        return
    
    username = user.get('username') or message.from_user.username or "Игрок"
    first_name = user.get('first_name') or message.from_user.first_name or "Фермер"
    balance = user.get('balance', 0)
    gems = user.get('gems', 0)
    prestige = user.get('prestige', 0)
    level = user.get('level', 1)
    xp = user.get('xp', 0)
    
    text = f"👤 <b>ПРОФИЛЬ</b>\n\n"
    text += f"🙂 Имя: {first_name}\n"
    text += f"🆔 ID: <code>{message.from_user.id}</code>\n"
    if username:
        text += f"👤 Username: @{username}\n"
    text += f"💰 Баланс: {balance:,}🪙\n"
    text += f"💎 Самоцветы: {gems}💎\n"
    text += f"🚜 Престиж: {prestige}\n"
    text += f"📊 Уровень: {level} ({xp} XP)\n\n"
    text += f"🌾 Начало: {user.get('created_at', 'Неизвестно')[:10]}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="profile_stats")],
        [InlineKeyboardButton(text="🏆 Ачивки", callback_data="profile_achievements")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])
    
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


async def bonus_menu_handler(message: Message):
    """Обработчик бонусного меню - ТЗ v4.0 п.13"""
    db = await get_database()
    
    # Получаем информацию о бонусе
    bonus_info = await db.get_daily_bonus_info(message.from_user.id)
    
    streak = bonus_info.get('streak', 0)
    last_claim = bonus_info.get('last_claim')
    can_claim = bonus_info.get('can_claim', False)
    
    text = f"🎁 <b>ЕЖЕДНЕВНЫЙ БОНУС</b>\n\n"
    text += f"🔥 Серия: {streak} дней\n"
    
    if can_claim:
        text += "✅ Бонус доступен!\n\n"
        text += "Нажмите кнопку ниже, чтобы получить награду."
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Получить бонус", callback_data="daily_bonus_claim")],
            [InlineKeyboardButton(text="📋 История", callback_data="daily_bonus_history")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
        ])
    else:
        time_left = bonus_info.get('time_left', 0)
        if time_left > 0:
            hours = time_left // 3600
            minutes = (time_left % 3600) // 60
            next_bonus = f"{hours}ч {minutes}м"
        else:
            next_bonus = "завтра"
        text += f"⏳ Следующий бонус через: {next_bonus}\n\n"
        text += "Возвращайтесь позже!"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 История", callback_data="daily_bonus_history")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
        ])
    
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == "daily_bonus_claim")
async def daily_bonus_claim(callback: CallbackQuery):
    """Получение ежедневного бонуса"""
    db = await get_database()
    
    result = await db.claim_daily_bonus(callback.from_user.id)
    
    if result["success"]:
        coins = result.get("coins", 0)
        gems = result.get("gems", 0)
        streak = result.get("streak", 1)
        
        text = (
            f"🎉 <b>БОНУС ПОЛУЧЕН!</b>\n\n"
            f"💰 Монет: +{coins:,}\n"
        )
        if gems > 0:
            text += f"💎 Кристаллов: +{gems}\n"
        text += f"🔥 Серия: {streak} дней\n\n"
        text += "Приходи завтра за следующим бонусом!"
        
        await callback.answer(f"✅ Получено: {coins}🪙 {gems}💎!", show_alert=True)
    else:
        time_left = result.get("time_left", 0)
        hours = time_left // 3600
        mins = (time_left % 3600) // 60
        
        text = (
            "⏳ <b>БОНУС УЖЕ ПОЛУЧЕН!</b>\n\n"
            f"Следующий бонус через: {hours}ч {mins}м\n\n"
            "Приходи позже!"
        )
        await callback.answer("⏳ Бонус уже получен!", show_alert=True)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 История", callback_data="daily_bonus_history")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "daily_bonus_history")
async def daily_bonus_history_handler(callback: CallbackQuery):
    """История полученных бонусов"""
    db = await get_database()
    
    history = await db.fetchall(
        """SELECT bonus_day, reward_amount, streak_at_claim, claimed_at
           FROM daily_bonus_history
           WHERE user_id = ?
           ORDER BY claimed_at DESC
           LIMIT 10""",
        (callback.from_user.id,)
    )
    
    text = "📋 <b>ИСТОРИЯ БОНУСОВ</b>\n\n"
    
    if not history:
        text += "Ты ещё не получал бонусы.\n"
        text += "🎁 Нажми \"Получить бонус\"!"
    else:
        for day, amount, streak, claimed_at in history:
            date_str = claimed_at[:10] if claimed_at else "?"
            text += f"📅 {date_str} | День {day} | {amount}🪙 | 🔥{streak}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Получить бонус", callback_data="daily_bonus_claim")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


# ============ CALLBACK ОБРАБОТЧИКИ ФЕРМЕРОВ ============

@router.callback_query(F.data == "hire_farmer")
async def hire_farmer(callback: CallbackQuery):
    """Нанять фермера"""
    db = await get_database()
    
    # Проверяем престиж
    user = await db.get_user(callback.from_user.id)
    prestige = user.get('prestige', 0)
    
    if prestige < 10:
        await callback.answer("❌ Требуется 10 престижа!", show_alert=True)
        return
    
    # Проверяем количество фермеров
    farmers_count = await db.fetchone(
        "SELECT COUNT(*) FROM farmers WHERE user_id = ? AND is_active = 1",
        (callback.from_user.id,)
    )
    farmers_count = farmers_count[0] if farmers_count else 0
    
    if farmers_count >= 5:
        await callback.answer("❌ Максимум 5 фермеров!", show_alert=True)
        return
    
    # Проверяем баланс
    balance = user.get('balance', 0)
    cost = 5000 * (farmers_count + 1)
    
    if balance < cost:
        await callback.answer(f"❌ Нужно {cost:,}🪙!", show_alert=True)
        return
    
    # Нанимаем фермера
    await db.update_balance(callback.from_user.id, -cost)
    await db.execute(
        """INSERT INTO farmers (user_id, farmer_type, hired_at, is_active, plots_managed)
           VALUES (?, 'basic', datetime('now'), 1, 0)""",
        (callback.from_user.id,)
    )
    
    await callback.answer(f"✅ Фермер нанят за {cost:,}🪙!", show_alert=True)
    await farmer_handler_button(callback.message)


@router.callback_query(F.data == "farmers_stats")
async def farmers_stats(callback: CallbackQuery):
    """Статистика фермеров"""
    db = await get_database()
    
    # Получаем общую статистику
    stats = await db.fetchone(
        """SELECT 
            COUNT(*) as total_farmers,
            SUM(total_harvests) as total_harvests,
            SUM(plots_managed) as total_plots
           FROM farmers WHERE user_id = ? AND is_active = 1""",
        (callback.from_user.id,)
    )
    
    total_farmers, total_harvests, total_plots = stats if stats else (0, 0, 0)
    
    text = (
        "📊 <b>СТАТИСТИКА ФЕРМЕРОВ</b>\n\n"
        f"👨‍🌾 Всего фермеров: {total_farmers}\n"
        f"🌾 Собрано урожая: {total_harvests or 0}\n"
        f"🌱 Обслуживают грядок: {total_plots or 0}\n\n"
        "💡 Фермеры работают 24/7!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_farmers")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "farmers_manage")
async def farmers_manage(callback: CallbackQuery):
    """Управление фермерами"""
    text = (
        "⚙️ <b>УПРАВЛЕНИЕ ФЕРМЕРАМИ</b>\n\n"
        "📋 Здесь можно:\n"
        "• 🔄 Переназначить грядки\n"
        "• ❌ Уволить фермера\n"
        "• 📊 Смотреть статистику\n\n"
        "Выбери действие:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Переназначить", callback_data="farmers_reassign")],
        [InlineKeyboardButton(text="❌ Уволить", callback_data="farmers_fire")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_farmers")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "farmers_reassign")
async def farmers_reassign(callback: CallbackQuery):
    """Переназначение грядок"""
    await callback.answer("🔄 Функция в разработке!", show_alert=True)


@router.callback_query(F.data == "farmers_fire")
async def farmers_fire(callback: CallbackQuery):
    """Увольнение фермера"""
    await callback.answer("❌ Функция в разработке!", show_alert=True)


@router.callback_query(F.data == "back_farmers")
async def back_farmers(callback: CallbackQuery):
    """Возврат к фермерам"""
    await farmer_handler_button(callback.message)
    await callback.answer()


# ==================== НЕДОСТАЮЩИЕ ОБРАБОТЧИКИ ====================


@router.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery):
    """Возврат в главное меню"""
    db = await get_db()
    user = await db.get_user(callback.from_user.id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден!", show_alert=True)
        return
    
    # Формируем текст главного меню
    prestige_level = user.get('prestige_level', 1)
    prestige_mult = user.get('prestige_multiplier', 1.0)
    
    text = f"""🌾 <b>Lazy Farmer</b>

👋 Привет, <b>{user.get('first_name', 'Фермер')}</b>!

💰 <b>Баланс:</b> {format_number(user.get('balance', 0))} монет
💎 <b>Кристаллы:</b> {user.get('gems', 0)}
🏆 <b>Престиж:</b> Уровень {prestige_level} (x{prestige_mult:.1f})

Выбери действие:"""
    
    keyboard = get_main_keyboard(prestige_level)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "profile_stats")
async def profile_stats(callback: CallbackQuery):
    """Просмотр статистики профиля"""
    db = await get_db()
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден!", show_alert=True)
        return
    
    # Получаем дополнительную статистику
    plot_count = await db.get_plot_count(user_id)
    achievements = await db.get_achievement_stats(user_id)
    
    text = f"""📊 <b>Статистика профиля</b>

👤 <b>Игрок:</b> {user.get('first_name', 'Неизвестно')}
📅 <b>В игре с:</b> {user.get('joined_date', 'Неизвестно')[:10] if user.get('joined_date') else 'Неизвестно'}

<b>📈 Основные показатели:</b>
🌾 Всего собрано: {format_number(user.get('total_harvested', 0))}
🌱 Всего посажено: {format_number(user.get('total_planted', 0))}
💰 Заработано: {format_number(user.get('total_earned', 0))} монет
💸 Потрачено: {format_number(user.get('total_spent', 0))} монет

<b>🏆 Достижения:</b>
✅ Получено: {achievements.get('completed', 0)}
🎯 Всего: {achievements.get('total', 0)}
💎 Наград: {achievements.get('rewards_claimed', 0)}

<b>🌱 Ферма:</b>
🟫 Грядок: {plot_count}
🏆 Престиж: Уровень {user.get('prestige_level', 1)}"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "profile_achievements")
async def profile_achievements(callback: CallbackQuery):
    """Просмотр достижений профиля"""
    db = await get_db()
    user_id = callback.from_user.id
    
    # Получаем достижения
    categories = await db.get_achievement_categories()
    user_achievements = await db.get_profile_achievements(user_id)
    
    text = """🏆 <b>Достижения</b>

Выбери категорию для просмотра:"""
    
    keyboard_rows = []
    for cat in categories:
        icon = cat.get('icon', '📌')
        name = cat.get('name', 'Категория')
        code = cat.get('code', 'unknown')
        
        # Считаем выполненные в категории
        completed = sum(1 for a in user_achievements if a.get('category') == code and a.get('completed'))
        total = sum(1 for a in user_achievements if a.get('category') == code)
        
        keyboard_rows.append([
            InlineKeyboardButton(text=f"{icon} {name} ({completed}/{total})", callback_data=f"ach_cat_{code}")
        ])
    
    # Добавляем кнопку "Все"
    total_completed = sum(1 for a in user_achievements if a.get('completed'))
    total_count = len(user_achievements)
    keyboard_rows.insert(0, [
        InlineKeyboardButton(text=f"📋 Все достижения ({total_completed}/{total_count})", callback_data="ach_all")
    ])
    
    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "achievements_back")
async def achievements_back(callback: CallbackQuery):
    """Возврат к списку достижений"""
    # Переиспользуем функцию profile_achievements
    await profile_achievements(callback)


@router.callback_query(F.data.startswith("ach_cat_"))
async def achievements_category(callback: CallbackQuery):
    """Просмотр достижений по категории"""
    db = await get_db()
    user_id = callback.from_user.id
    category = callback.data.replace("ach_cat_", "")
    
    achievements = await db.get_achievements_by_category(category)
    
    if not achievements:
        await callback.answer("❌ Достижений в этой категории нет!", show_alert=True)
        return
    
    text = f"🏆 <b>Достижения: {category}</b>\n\n"
    
    for ach in achievements[:10]:  # Показываем первые 10
        icon = ach.get('icon', '🏆')
        name = ach.get('name', 'Неизвестно')
        desc = ach.get('description', '')
        completed = ach.get('completed', False)
        
        status = "✅" if completed else "⬜"
        text += f"{status} {icon} <b>{name}</b>\n{desc}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="achievements_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "ach_all")
async def achievements_all(callback: CallbackQuery):
    """Просмотр всех достижений"""
    db = await get_db()
    user_id = callback.from_user.id
    
    achievements = await db.get_achievements(user_id)
    
    if not achievements:
        await callback.answer("❌ Достижений нет!", show_alert=True)
        return
    
    text = "🏆 <b>Все достижения</b>\n\n"
    
    completed_count = 0
    for ach in achievements[:15]:  # Показываем первые 15
        icon = ach.get('icon', '🏆')
        name = ach.get('name', 'Неизвестно')
        completed = ach.get('completed', False)
        
        if completed:
            completed_count += 1
            status = "✅"
        else:
            status = "⬜"
        
        text += f"{status} {icon} {name}\n"
    
    text += f"\n📊 Выполнено: {completed_count}/{len(achievements)}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="achievements_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "quests_refresh")
async def quests_refresh(callback: CallbackQuery):
    """Обновление списка квестов"""
    db = await get_db()
    user_id = callback.from_user.id
    
    # Получаем квесты
    daily_quests = await db.get_daily_quests(user_id)
    weekly_quests = await db.get_weekly_quests(user_id)
    
    text = "📋 <b>Квесты</b>\n\n"
    
    text += "<b>Ежедневные:</b>\n"
    if daily_quests:
        for quest in daily_quests:
            status = "✅" if quest.get('completed') else "⬜"
            name = quest.get('name', 'Квест')
            progress = quest.get('progress', 0)
            target = quest.get('target', 1)
            text += f"{status} {name} ({progress}/{target})\n"
    else:
        text += "Нет активных квестов\n"
    
    text += "\n<b>Еженедельные:</b>\n"
    if weekly_quests:
        for quest in weekly_quests:
            status = "✅" if quest.get('completed') else "⬜"
            name = quest.get('name', 'Квест')
            progress = quest.get('progress', 0)
            target = quest.get('target', 1)
            text += f"{status} {name} ({progress}/{target})\n"
    else:
        text += "Нет активных квестов\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Забрать награды", callback_data="claim_all_quest_rewards")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="quests_refresh")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "prestige_confirm")
async def prestige_confirm(callback: CallbackQuery):
    """Подтверждение престижа"""
    db = await get_db()
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден!", show_alert=True)
        return
    
    current_level = user.get('prestige_level', 1)
    balance = user.get('balance', 0)
    
    # Рассчитываем стоимость
    from admin.config import get_prestige_cost
    cost = get_prestige_cost(current_level)
    
    if balance < cost:
        await callback.answer(f"❌ Нужно {format_number(cost)} монет!", show_alert=True)
        return
    
    # Выполняем престиж
    success = await db.do_prestige(user_id)
    
    if success:
        new_level = current_level + 1
        new_mult = 1.0 + (new_level - 1) * 0.1
        
        text = f"""🎉 <b>Престиж повышен!</b>

🏆 Новый уровень: {new_level}
📊 Множитель: x{new_mult:.1f}

Награды:
💎 +{new_level} кристаллов
🆓 Грядки разблокированы"""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer("🎉 Престиж повышен!")
    else:
        await callback.answer("❌ Ошибка при повышении престижа!", show_alert=True)


@router.callback_query(F.data == "claim_all_quest_rewards")
async def claim_all_quest_rewards(callback: CallbackQuery):
    """Забрать все награды за квесты"""
    db = await get_db()
    user_id = callback.from_user.id
    
    # Получаем награды
    result = await db.claim_all_quest_rewards(user_id)
    
    if result.get('success'):
        rewards = result.get('rewards', [])
        total_coins = sum(r.get('coins', 0) for r in rewards)
        total_gems = sum(r.get('gems', 0) for r in rewards)
        
        text = f"""🎁 <b>Награды получены!</b>

💰 Монеты: +{format_number(total_coins)}
💎 Кристаллы: +{total_gems}
📋 Квестов выполнено: {len(rewards)}"""
        
        await callback.message.answer(text, parse_mode="HTML")
        await quests_refresh(callback)
    else:
        await callback.answer(result.get('message', "❌ Нет наград для получения!"), show_alert=True)