from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict, Optional

def get_main_keyboard():
    """Постоянная Reply-клавиатура согласно ТЗ v4.0
    
    Клавиатура НИКОГДА не меняется.
    Все динамические действия — через инлайн-кнопки.
    """
    keyboard_rows = [
        [
            KeyboardButton(text="🌾 Ферма"), 
            KeyboardButton(text="🏪 Магазин"), 
            KeyboardButton(text="📦 Инв")
        ],
        [
            KeyboardButton(text="📜 Квесты"), 
            KeyboardButton(text="🏆 Ачивки"), 
            KeyboardButton(text="🚜 Прест")
        ],
        [
            KeyboardButton(text="👤 Профиль"), 
            KeyboardButton(text="🎁 Бонус"), 
            KeyboardButton(text="🎁 Промо")
        ],
        [
            KeyboardButton(text="👤 Фермер"),
            KeyboardButton(text="👥 Рефералы"),
            KeyboardButton(text="🎉 Ивент")
        ],
        [
            KeyboardButton(text="💰 Перевод"),
            KeyboardButton(text="💬 Чат"),
            KeyboardButton(text="❓ Помощь")
        ],
    ]
    
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

def get_farm_keyboard(plots: List[Dict], next_plot: Dict = None):
    """Динамические кнопки фермы согласно ТЗ v4.0 п.4.3 и п.10
    
    Args:
        plots: Список грядок пользователя
        next_plot: Информация о следующей грядке для покупки (если есть)
    """
    inline_rows = []
    
    # Кнопка сбора урожая если есть готовые грядки
    ready_plots = [p for p in plots if p["status"] == "ready"]
    if ready_plots:
        inline_rows.append([InlineKeyboardButton(
            text=f"✅ Собрать всё ({len(ready_plots)})", 
            callback_data="harvest_all"
        )])
    
    # Кнопки посадки для пустых грядок
    empty_plots = [p for p in plots if p["status"] == "empty"]
    if empty_plots:
        plant_buttons = []
        for plot in empty_plots[:4]:  # Максимум 4 кнопки посадки
            plant_buttons.append(InlineKeyboardButton(
                text=f"🌱 Посадить #{plot['number']}", 
                callback_data=f"plant_{plot['number']}"
            ))
        
        # Добавляем кнопки посадки по 2 в ряд
        for i in range(0, len(plant_buttons), 2):
            row = plant_buttons[i:i+2]
            if row:
                inline_rows.append(row)

    # Кнопки удобрений для растущих грядок (только не удобренные)
    growing_plots = [p for p in plots if p["status"] == "growing" and not p.get("fertilized", False)]
    if growing_plots:
        fertilize_buttons = []
        for plot in growing_plots[:2]:  # Максимум 2 кнопки удобрений
            fertilize_buttons.append(InlineKeyboardButton(
                text=f"🧪 Удобрить #{plot['number']}", 
                callback_data=f"fertilize_{plot['number']}"
            ))
        if fertilize_buttons:
            inline_rows.append(fertilize_buttons)
    
    # Кнопка покупки новой грядки
    if next_plot:
        inline_rows.append([InlineKeyboardButton(
            text=f"🛒 Купить грядку #{next_plot['plot_number']} ({next_plot['price']:,}🪙)", 
            callback_data=f"buy_plot_{next_plot['plot_number']}"
        )])
    
    # Основные кнопки (обновить и бонус)
    action_row = [
        InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_farm")
    ]
    
    # Проверяем доступность бонуса
    inline_rows.append(action_row)
 
    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_rows)
    return keyboard

def get_shop_categories(categories: Optional[List[Dict]] = None, seasonal_categories: List[str] = None):
    """Клавиатура категорий магазина (устаревшая, используется get_shop_keyboard)"""
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


def get_shop_keyboard(prestige_level: int = 1, event: Dict = None):
    """Клавиатура главного меню магазина согласно ТЗ v4.0 п.5.2 и п.12
    
    Args:
        prestige_level: Уровень престижа игрока
        event: Информация о сезонном событии
    """
    inline_rows = [
        [
            InlineKeyboardButton(text="🌱 Семена", callback_data="shop_seed"),
            InlineKeyboardButton(text="🧪 Удобрения", callback_data="shop_fertilizer")
        ]
    ]
    
    # Вторая строка - улучшения (с 5 престижа) и фермеры (с 10 престижа)
    second_row = []
    
    # Улучшения доступны с 5 престижа (было 20 - слишком высоко)
    if prestige_level >= 5:
        second_row.append(InlineKeyboardButton(text="⬆️ Улучшения", callback_data="shop_upgrades"))
    
    # Фермеры доступны с 10 престижа
    if prestige_level >= 10:
        second_row.append(InlineKeyboardButton(text="👤 Фермеры", callback_data="shop_farmers"))
    
    if second_row:
        inline_rows.append(second_row)
    
    # Добавляем сезонную категорию если есть событие
    if event and event.get('is_active', False):
        event_icon = event.get('icon', '🎉')
        inline_rows.append([
            InlineKeyboardButton(text=f"{event_icon} Сезонное", callback_data="shop_seasonal")
        ])
    
    # Добавляем продажу и назад
    inline_rows.append([
        InlineKeyboardButton(text="💰 Продать", callback_data="shop_sell"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")
    ])
 
    return InlineKeyboardMarkup(inline_keyboard=inline_rows)


def get_shop_items_keyboard(category: str, items: List[Dict], user_level: int):
    """Клавиатура товаров категории
    
    Args:
        category: Категория товаров
        items: Список товаров
        user_level: Уровень пользователя
    """
    inline_rows = []
    
    for item in items:
        item_code = item.get('item_code', '')
        name = item.get('name', '???')
        icon = item.get('icon', '📦')
        buy_price = item.get('buy_price', 0)
        required_level = item.get('required_level', 1)
        
        # Проверяем доступность по уровню
        is_locked = user_level < required_level
        
        if is_locked:
            button_text = f"🔒 {icon} {name}"
        else:
            # Определяем валюту
            effect_type = item.get('effect_type')
            currency = '💎' if effect_type == 'instant' and buy_price > 100 else '🪙'
            button_text = f"{icon} {name} ({buy_price}{currency})"
        
        inline_rows.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"itemdetail_{item_code}" if not is_locked else f"locked_{item_code}"
            )
        ])
    
    # Кнопка назад
    inline_rows.append([InlineKeyboardButton(text="🔙 В магазин", callback_data="back_shop")])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_rows)


def get_sell_keyboard(sellable_items: Dict):
    """Клавиатура меню продажи
    
    Args:
        sellable_items: Словарь продаваемых предметов
    """
    inline_rows = []
    
    # Кнопки продажи по типам
    for item_code, data in sellable_items.items():
        icon = data.get('icon', '📦')
        name = data.get('name', item_code)
        quantity = data.get('quantity', 0)
        value = data.get('value', 0)
        
        inline_rows.append([
            InlineKeyboardButton(
                text=f"{icon} Продать {name} (x{quantity}) — {value:,}🪙",
                callback_data=f"sellitem_{item_code}_{quantity}"
            )
        ])
    
    # Кнопка продажи по одному
    if len(sellable_items) > 1:
        inline_rows.append([
            InlineKeyboardButton(text="📦 Продать по одному", callback_data="sell_one_by_one")
        ])
    
    # Кнопка назад
    inline_rows.append([InlineKeyboardButton(text="🔙 В магазин", callback_data="back_shop")])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_rows)


def get_item_detail_keyboard(item: Dict, user_level: int, balance: int):
    """Клавиатура детального просмотра товара
    
    Args:
        item: Информация о товаре
        user_level: Уровень пользователя
        balance: Баланс пользователя
    """
    item_code = item.get('item_code', '')
    buy_price = item.get('buy_price', 0)
    required_level = item.get('required_level', 1)
    effect_type = item.get('effect_type')
    
    # Определяем валюту
    currency = '💎' if effect_type == 'instant' and buy_price > 100 else '🪙'
    
    inline_rows = []
    
    # Проверяем доступность
    if user_level < required_level:
        inline_rows.append([
            InlineKeyboardButton(
                text=f"🔒 Требуется уровень {required_level}",
                callback_data="locked"
            )
        ])
    elif balance < buy_price:
        inline_rows.append([
            InlineKeyboardButton(
                text=f"❌ Недостаточно {currency}",
                callback_data="insufficient_funds"
            )
        ])
    else:
        # Кнопки покупки
        inline_rows.append([
            InlineKeyboardButton(
                text=f"🏷️ Купить 1 ({buy_price}{currency})",
                callback_data=f"buyitem_{item_code}_1"
            )
        ])
        
        # Для семян добавляем покупку 10 штук
        if item.get('category') == 'seed':
            price_10 = buy_price * 10
            if balance >= price_10:
                inline_rows.append([
                    InlineKeyboardButton(
                        text=f"🏷️ Купить 10 ({price_10:,}{currency})",
                        callback_data=f"buyitem_{item_code}_10"
                    )
                ])
    
    # Кнопка сравнения для семян
    if item.get('category') == 'seed':
        inline_rows.append([
            InlineKeyboardButton(text="📊 Сравнить", callback_data=f"compare_{item_code}")
        ])
    
    # Кнопка назад
    inline_rows.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"shop_{item.get('category', 'seed')}")
    ])
    
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
 

# ==================== КЛАВИАТУРЫ ИНВЕНТАРЯ (ТЗ v4.0 п.6) ====================

def get_inventory_keyboard(inventory_data: Dict, multiplier: float = 1.0):
    """Клавиатура главного меню инвентаря согласно ТЗ v4.0 п.6.1
    
    Args:
        inventory_data: Данные инвентаря из get_inventory_full
        multiplier: Множитель престижа для расчёта стоимости
    """
    inline_rows = []
    
    # Кнопки для каждой категории с предметами
    seeds = inventory_data.get('seeds', {})
    fertilizers = inventory_data.get('fertilizers', {})
    upgrades = inventory_data.get('upgrades', {})
    other = inventory_data.get('other', {})
    
    # Кнопка продажи если есть что продавать
    sellable_items = {**seeds, **fertilizers}
    if sellable_items:
        inline_rows.append([
            InlineKeyboardButton(text="💰 Продать", callback_data="inv_sell")
        ])
    
    # Кнопки действий
    action_row = []
    if seeds:
        action_row.append(InlineKeyboardButton(text="🌱 Семена", callback_data="inv_category_seed"))
    if fertilizers:
        action_row.append(InlineKeyboardButton(text="🧪 Удобрения", callback_data="inv_category_fertilizer"))
    
    if action_row:
        inline_rows.append(action_row)
    
    # Кнопка сортировки
    inline_rows.append([
        InlineKeyboardButton(text="📊 Сортировать", callback_data="inv_sort")
    ])
    
    # Кнопка назад
    inline_rows.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_rows)


def get_inventory_category_keyboard(category: str, items: Dict, multiplier: float = 1.0):
    """Клавиатура для просмотра категории инвентаря
    
    Args:
        category: Категория (seed, fertilizer, upgrade, other)
        items: Словарь предметов категории
        multiplier: Множитель престижа
    """
    inline_rows = []
    
    for item_code, data in items.items():
        icon = data.get('icon', '📦')
        name = data.get('name', item_code)
        quantity = data.get('quantity', 0)
        value = int(data.get('value', 0) * multiplier)
        
        inline_rows.append([
            InlineKeyboardButton(
                text=f"{icon} {name} (x{quantity}) — {value:,}🪙",
                callback_data=f"inv_item_{item_code}"
            )
        ])
    
    # Кнопка назад
    inline_rows.append([
        InlineKeyboardButton(text="🔙 В инвентарь", callback_data="back_inventory")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_rows)


def get_inventory_item_keyboard(item_data: Dict, multiplier: float = 1.0, empty_plots: int = 0):
    """Клавиатура для детального просмотра предмета согласно ТЗ v4.0 п.6.2
    
    Args:
        item_data: Данные о предмете
        multiplier: Множитель престижа
        empty_plots: Количество пустых грядок (для семян)
    """
    item_code = item_data.get('code', '')
    quantity = item_data.get('quantity', 0)
    category = item_data.get('category', 'other')
    
    inline_rows = []
    
    # Для семян - кнопка посадки
    if category == 'seed' and empty_plots > 0:
        plant_qty = min(quantity, empty_plots)
        inline_rows.append([
            InlineKeyboardButton(
                text=f"🌱 Посадить всё ({plant_qty})",
                callback_data=f"inv_plant_{item_code}_{plant_qty}"
            )
        ])
    
    # Кнопка продажи (для семян и удобрений)
    if category in ['seed', 'fertilizer'] and item_data.get('sell_price', 0) > 0:
        value = int(item_data.get('sell_price', 0) * quantity * multiplier)
        inline_rows.append([
            InlineKeyboardButton(
                text=f"💰 Продать всё (+{value:,}🪙)",
                callback_data=f"inv_sell_{item_code}_{quantity}"
            )
        ])
        
        # Кнопка продажи по одному если больше 1
        if quantity > 1:
            inline_rows.append([
                InlineKeyboardButton(
                    text="📦 Продать 1 шт.",
                    callback_data=f"inv_sell_{item_code}_1"
                )
            ])
    
    # Для удобрений - кнопка использования
    if category == 'fertilizer':
        inline_rows.append([
            InlineKeyboardButton(
                text="🧪 Использовать",
                callback_data=f"inv_use_{item_code}"
            )
        ])
    
    # Кнопка назад
    inline_rows.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_inventory")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_rows)


def get_inventory_sell_keyboard(items: Dict, multiplier: float = 1.0):
    """Клавиатура для продажи предметов из инвентаря
    
    Args:
        items: Словарь продаваемых предметов
        multiplier: Множитель престижа
    """
    inline_rows = []
    
    for item_code, data in items.items():
        icon = data.get('icon', '📦')
        name = data.get('name', item_code)
        quantity = data.get('quantity', 0)
        value = int(data.get('value', 0) * multiplier)
        
        inline_rows.append([
            InlineKeyboardButton(
                text=f"{icon} {name} (x{quantity}) — {value:,}🪙",
                callback_data=f"inv_sell_{item_code}_{quantity}"
            )
        ])
    
    # Кнопка продать всё
    if len(items) > 1:
        total_value = sum(int(d.get('value', 0) * multiplier) for d in items.values())
        inline_rows.append([
            InlineKeyboardButton(
                text=f"💰 Продать всё (+{total_value:,}🪙)",
                callback_data="inv_sell_all"
            )
        ])
    
    # Кнопка назад
    inline_rows.append([
        InlineKeyboardButton(text="🔙 В инвентарь", callback_data="back_inventory")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_rows)
 

# ==================== КЛАВИАТУРЫ ФЕРМЕРОВ (ТЗ v4.0 п.11) ====================

def get_farmers_menu_keyboard(farmer_types: List[Dict], user_balance: int, 
                               user_gems: int, prestige_level: int,
                               has_active_farmer: bool = False):
    """Клавиатура меню найма фермеров согласно ТЗ v4.0 п.11.2
    
    Args:
        farmer_types: Список типов фермеров из БД
        user_balance: Баланс пользователя в монетах
        user_gems: Баланс пользователя в кристаллах
        prestige_level: Уровень престижа
        has_active_farmer: Есть ли уже активный фермер
    """
    inline_rows = []
    
    if prestige_level < 10:
        # Фермеры недоступны
        inline_rows.append([
            InlineKeyboardButton(
                text="🔒 Требуется 10 престиж",
                callback_data="farmer_locked"
            )
        ])
    elif has_active_farmer:
        # Уже есть фермер - показываем кнопку управления
        inline_rows.append([
            InlineKeyboardButton(
                text="👤 Мой фермер",
                callback_data="farmer_manage"
            )
        ])
    else:
        # Показываем доступных фермеров
        for ft in farmer_types:
            type_code = ft.get('type_code', '')
            name = ft.get('name', 'Фермер')
            icon = ft.get('icon', '👤')
            price_coins = ft.get('price_coins', 0)
            price_gems = ft.get('price_gems', 0)
            duration_days = ft.get('duration_days')
            bonus_percent = ft.get('bonus_percent', 0)
            
            # Определяем доступность по цене
            can_afford = (price_coins <= user_balance) and (price_gems <= user_gems)
            
            # Формируем текст кнопки
            if price_coins > 0:
                price_text = f"{price_coins:,}🪙"
            else:
                price_text = f"{price_gems}💎"
            
            duration_text = f"{duration_days} дн." if duration_days else "навсегда"
            bonus_text = f" +{bonus_percent}%" if bonus_percent > 0 else ""
            
            button_text = f"{icon} {name} ({price_text}, {duration_text}{bonus_text})"
            
            if not can_afford:
                button_text = f"🔒 {icon} {name}"
            
            inline_rows.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"farmer_hire_{type_code}" if can_afford else f"farmer_cant_afford_{type_code}"
                )
            ])
    
    # Кнопка назад
    inline_rows.append([
        InlineKeyboardButton(text="🔙 В магазин", callback_data="back_shop")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_rows)


def get_farmer_detail_keyboard(farmer_type: Dict, user_balance: int, user_gems: int):
    """Клавиатура детального просмотра типа фермера перед наймом
    
    Args:
        farmer_type: Информация о типе фермера
        user_balance: Баланс пользователя
        user_gems: Кристаллы пользователя
    """
    inline_rows = []
    
    type_code = farmer_type.get('type_code', '')
    price_coins = farmer_type.get('price_coins', 0)
    price_gems = farmer_type.get('price_gems', 0)
    
    can_afford = (price_coins <= user_balance) and (price_gems <= user_gems)
    
    if can_afford:
        price_text = f"{price_coins:,}🪙" if price_coins > 0 else f"{price_gems}💎"
        inline_rows.append([
            InlineKeyboardButton(
                text=f"✅ Нанять за {price_text}",
                callback_data=f"farmer_confirm_{type_code}"
            )
        ])
    else:
        inline_rows.append([
            InlineKeyboardButton(
                text="❌ Недостаточно средств",
                callback_data="farmer_insufficient"
            )
        ])
    
    inline_rows.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="shop_farmers")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_rows)


def get_farmer_manage_keyboard(farmer: Dict, user_inventory: Dict = None):
    """Клавиатура управления фермером согласно ТЗ v4.0 п.11.3
    
    Args:
        farmer: Информация о фермере
        user_inventory: Инвентарь пользователя (для проверки семян)
    """
    inline_rows = []
    
    status = farmer.get('status', 'active')
    config = farmer.get('config', {})
    
    # Кнопки настроек
    # Что сажать
    preferred_crop = config.get('preferred_crop')
    crop_text = preferred_crop if preferred_crop else "🌾 Все подряд"
    inline_rows.append([
        InlineKeyboardButton(
            text=f"🌱 Сажать: {crop_text}",
            callback_data="farmer_config_crop"
        )
    ])
    
    # Что делать с урожаем
    harvest_mode = config.get('harvest_mode', 'sell')
    mode_names = {'sell': '💰 Продавать', 'inventory': '📦 В инвентарь', 'ask': '❓ Спрашивать'}
    mode_text = mode_names.get(harvest_mode, '💰 Продавать')
    inline_rows.append([
        InlineKeyboardButton(
            text=f"📦 Урожай: {mode_text}",
            callback_data="farmer_config_harvest"
        )
    ])
    
    # Использовать удобрения
    use_fert = config.get('use_fertilizer', False)
    fert_text = "✅ Да" if use_fert else "❌ Нет"
    inline_rows.append([
        InlineKeyboardButton(
            text=f"🧪 Удобрения: {fert_text}",
            callback_data="farmer_config_fertilizer"
        )
    ])
    
    # Кнопки управления
    action_row = []
    if status == 'active':
        action_row.append(InlineKeyboardButton(
            text="⏸️ Приостановить",
            callback_data="farmer_pause"
        ))
    elif status == 'paused':
        action_row.append(InlineKeyboardButton(
            text="▶️ Возобновить",
            callback_data="farmer_resume"
        ))
    
    action_row.append(InlineKeyboardButton(
        text="❌ Уволить",
        callback_data="farmer_fire"
    ))
    
    inline_rows.append(action_row)
    
    # Кнопка статистики
    inline_rows.append([
        InlineKeyboardButton(
            text="📊 Подробная статистика",
            callback_data="farmer_stats"
        )
    ])
    
    # Кнопка назад
    inline_rows.append([
        InlineKeyboardButton(text="🔙 В магазин", callback_data="back_shop")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_rows)
 

def get_farmer_crop_select_keyboard(seeds: List[Dict], current_crop: str = None):
    """Клавиатура выбора культуры для посадки фермером
    
    Args:
        seeds: Список доступных семян
        current_crop: Текущая выбранная культура
    """
    inline_rows = []
    
    # Кнопка "Все подряд"
    all_text = "✅ 🌾 Все подряд" if not current_crop else "🌾 Все подряд"
    inline_rows.append([
        InlineKeyboardButton(
            text=all_text,
            callback_data="farmer_crop_all"
        )
    ])
    
    # Кнопки культур
    for seed in seeds[:6]:  # Максимум 6 культур
        item_code = seed.get('item_code', '')
        name = seed.get('name', '???')
        icon = seed.get('icon', '🌱')
        
        is_selected = current_crop == item_code
        status = "✅ " if is_selected else ""
        
        inline_rows.append([
            InlineKeyboardButton(
                text=f"{status}{icon} {name}",
                callback_data=f"farmer_crop_{item_code}"
            )
        ])
    
    # Кнопка назад
    inline_rows.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="farmer_manage")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_rows)


def get_farmer_harvest_mode_keyboard(current_mode: str = 'sell'):
    """Клавиатура выбора режима сбора урожая
    
    Args:
        current_mode: Текущий режим ('sell', 'inventory', 'ask')
    """
    inline_rows = []
    
    modes = [
        ('sell', '💰 Продавать', 'Автоматически продавать урожай'),
        ('inventory', '📦 В инвентарь', 'Складывать в инвентарь'),
        ('ask', '❓ Спрашивать', 'Спрашивать каждый раз')
    ]
    
    for mode_code, mode_name, _ in modes:
        is_selected = current_mode == mode_code
        status = "✅ " if is_selected else ""
        
        inline_rows.append([
            InlineKeyboardButton(
                text=f"{status}{mode_name}",
                callback_data=f"farmer_harvest_{mode_code}"
            )
        ])
    
    # Кнопка назад
    inline_rows.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="farmer_manage")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_rows)


def get_farmer_confirm_fire_keyboard():
    """Клавиатура подтверждения увольнения фермера"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, уволить", callback_data="farmer_fire_confirm"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="farmer_manage")
        ]
    ])


def get_farmer_work_result_keyboard():
    """Клавиатура после отчёта о работе фермера"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👤 Управление фермером", callback_data="farmer_manage"),
            InlineKeyboardButton(text="🌾 На ферму", callback_data="back_farm")
        ]
    ])

# ==================== КЛАВИАТУРЫ КВЕСТОВ (ТЗ v4.0 п.7) ====================

def get_quests_keyboard(quests: List[Dict], has_completed: bool = False, is_weekly: bool = False):
    """Клавиатура для ежедневных/еженедельных квестов
    
    Args:
        quests: Список квестов с прогрессом
        has_completed: Есть ли выполненные квесты для получения
        is_weekly: Еженедельные квесты
    """
    inline_rows = []
    
    # Кнопка забрать все если есть выполненные
    if has_completed:
        inline_rows.append([
            InlineKeyboardButton(
                text="🎁 Забрать все награды",
                callback_data="claim_all_quests" if not is_weekly else "claim_all_weekly"
            )
        ])
    
    # Для ежедневных квестов - кнопка обновления
    if not is_weekly:
        inline_rows.append([
            InlineKeyboardButton(
                text="🔄 Обновить за 50💎",
                callback_data="refresh_quests"
            )
        ])
    
    # Кнопка переключения между ежедневными и еженедельными
    if is_weekly:
        inline_rows.append([
            InlineKeyboardButton(
                text="📜 Ежедневные",
                callback_data="show_daily_quests"
            )
        ])
    else:
        inline_rows.append([
            InlineKeyboardButton(
                text="📅 Еженедельные",
                callback_data="show_weekly_quests"
            )
        ])
    
    # Кнопка назад
    inline_rows.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_rows)


def get_quest_detail_keyboard(quest: Dict, is_weekly: bool = False):
    """Клавиатура для детального просмотра квеста
    
    Args:
        quest: Данные о квесте
        is_weekly: Еженедельный квест
    """
    inline_rows = []
    
    quest_id = quest.get('quest_id', 0)
    completed = quest.get('completed', False)
    claimed = quest.get('claimed', False)
    
    if completed and not claimed:
        inline_rows.append([
            InlineKeyboardButton(
                text="🎁 Забрать награду",
                callback_data=f"claim_quest_{quest_id}" + ("_weekly" if is_weekly else "")
            )
        ])
    
    inline_rows.append([
        InlineKeyboardButton(
            text="🔙 К квестам",
            callback_data="show_weekly_quests" if is_weekly else "show_daily_quests"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_rows)
 

# ==================== КЛАВИАТУРЫ ДОСТИЖЕНИЙ (ТЗ v4.0 п.8) ====================

def get_achievements_keyboard(stats: Dict, pending_rewards: int = 0):
    """Клавиатура главного меню достижений согласно ТЗ v4.0 п.8.1
    
    Args:
        stats: Статистика достижений по категориям
        pending_rewards: Количество невостребованных наград
    """
    inline_rows = []
    
    # Кнопка забрать все если есть награды
    if pending_rewards > 0:
        inline_rows.append([
            InlineKeyboardButton(
                text=f"🎁 Забрать все ({pending_rewards})",
                callback_data="claim_all_achievements"
            )
        ])
    
    # Кнопки категорий
    category_buttons = []
    for cat_id, cat_data in stats.items():
        icon = cat_data.get('icon', '🏆')
        name = cat_data.get('name', cat_id)
        completed = cat_data.get('completed', 0)
        total = cat_data.get('total', 0)
        
        category_buttons.append(
            InlineKeyboardButton(
                text=f"{icon} {name} ({completed}/{total})",
                callback_data=f"ach_category_{cat_id}"
            )
        )
    
    # Добавляем по 2 кнопки в ряд
    for i in range(0, len(category_buttons), 2):
        inline_rows.append(category_buttons[i:i+2])
    
    # Кнопка просмотра всех ачивок
    inline_rows.append([
        InlineKeyboardButton(text="📋 Все ачивки", callback_data="ach_all"),
        InlineKeyboardButton(text="🏆 Выбрать в профиль", callback_data="ach_select_profile")
    ])
    
    # Кнопка истории
    inline_rows.append([
        InlineKeyboardButton(text="📜 История", callback_data="ach_history")
    ])
    
    # Кнопка назад
    inline_rows.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_rows)


def get_achievement_category_keyboard(category_id: str, achievements: List[Dict], 
                                       pending_count: int = 0, page: int = 0):
    """Клавиатура для просмотра достижений категории
    
    Args:
        category_id: ID категории
        achievements: Список достижений с прогрессом
        pending_count: Количество доступных наград
        page: Номер страницы
    """
    inline_rows = []
    
    # Кнопка забрать доступные
    if pending_count > 0:
        inline_rows.append([
            InlineKeyboardButton(
                text=f"🎁 Забрать доступные ({pending_count})",
                callback_data=f"ach_claim_category_{category_id}"
            )
        ])
    
    # Кнопки достижений
    for ach in achievements[:8]:  # Максимум 8 на страницу
        ach_id = ach.get('id', 0)
        icon = ach.get('icon', '🏆')
        name = ach.get('name', '???')
        progress = ach.get('progress', 0)
        target = ach.get('requirement_count', 1)
        completed = ach.get('completed', False)
        claimed = ach.get('reward_claimed', False)
        
        if completed and not claimed:
            status = "🎁"
        elif completed:
            status = "✅"
        else:
            pct = min(100, int(progress / target * 100)) if target > 0 else 0
            status = f"{pct}%"
        
        inline_rows.append([
            InlineKeyboardButton(
                text=f"{icon} {name} [{status}]",
                callback_data=f"ach_view_{ach_id}"
            )
        ])
    
    # Пагинация
    if len(achievements) > 8:
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(
                text="◀️", callback_data=f"ach_page_{category_id}_{page-1}"
            ))
        nav_row.append(InlineKeyboardButton(
            text=f"{page+1}", callback_data="noop"
        ))
        if len(achievements) > (page + 1) * 8:
            nav_row.append(InlineKeyboardButton(
                text="▶️", callback_data=f"ach_page_{category_id}_{page+1}"
            ))
        inline_rows.append(nav_row)
    
    # Кнопка назад
    inline_rows.append([
        InlineKeyboardButton(text="🔙 К категориям", callback_data="back_achievements")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_rows)


def get_achievement_detail_keyboard(achievement: Dict, completed: bool = False, 
                                     claimed: bool = False):
    """Клавиатура для детального просмотра достижения
    
    Args:
        achievement: Данные о достижении
        completed: Выполнено ли
        claimed: Получена ли награда
    """
    inline_rows = []
    ach_id = achievement.get('id', 0)
    category_id = achievement.get('category_id', '')
    
    if completed and not claimed:
        inline_rows.append([
            InlineKeyboardButton(
                text="🎁 Забрать награду",
                callback_data=f"ach_claim_{ach_id}"
            )
        ])
    
    # Кнопка выбора в профиль (если выполнено)
    if completed:
        inline_rows.append([
            InlineKeyboardButton(
                text="🏆 Выбрать в профиль",
                callback_data=f"ach_to_profile_{ach_id}"
            )
        ])
    
    inline_rows.append([
        InlineKeyboardButton(
            text="🔙 К категории",
            callback_data=f"ach_category_{category_id}"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_rows)


def get_achievement_all_keyboard(achievements: List[Dict], page: int = 0):
    """Клавиатура для просмотра всех достижений с пагинацией
    
    Args:
        achievements: Список всех достижений
        page: Номер страницы
    """
    inline_rows = []
    
    per_page = 6
    start = page * per_page
    end = start + per_page
    page_achievements = achievements[start:end]
    
    for ach in page_achievements:
        ach_id = ach.get('id', 0)
        icon = ach.get('icon', '🏆')
        name = ach.get('name', '???')
        category = ach.get('category_id', '')
        completed = ach.get('completed', False)
        
        status = "✅" if completed else "⬜"
        
        inline_rows.append([
            InlineKeyboardButton(
                text=f"{status} {icon} {name}",
                callback_data=f"ach_view_{ach_id}"
            )
        ])
    
    # Пагинация
    total_pages = (len(achievements) + per_page - 1) // per_page
    if total_pages > 1:
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(
                text="◀️", callback_data=f"ach_all_page_{page-1}"
            ))
        nav_row.append(InlineKeyboardButton(
            text=f"{page+1}/{total_pages}", callback_data="noop"
        ))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton(
                text="▶️", callback_data=f"ach_all_page_{page+1}"
            ))
        inline_rows.append(nav_row)
    
    inline_rows.append([
        InlineKeyboardButton(text="🔙 К достижениям", callback_data="back_achievements")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_rows)


def get_profile_select_keyboard(completed_achievements: List[Dict], 
                                 selected: List[int] = None, page: int = 0):
    """Клавиатура для выбора достижений в профиль
    
    Args:
        completed_achievements: Список выполненных достижений
        selected: Список выбранных ID
        page: Номер страницы
    """
    if selected is None:
        selected = []
    
    inline_rows = []
    per_page = 6
    start = page * per_page
    end = start + per_page
    
    for ach in completed_achievements[start:end]:
        ach_id = ach.get('id', 0)
        icon = ach.get('icon', '🏆')
        name = ach.get('name', '???')
        
        is_selected = ach_id in selected
        status = "✅" if is_selected else "⬜"
        
        inline_rows.append([
            InlineKeyboardButton(
                text=f"{status} {icon} {name}",
                callback_data=f"ach_toggle_{ach_id}"
            )
        ])
    
    # Пагинация
    total_pages = (len(completed_achievements) + per_page - 1) // per_page
    if total_pages > 1:
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(
                text="◀️", callback_data=f"ach_sel_page_{page-1}"
            ))
        nav_row.append(InlineKeyboardButton(
            text=f"{page+1}/{total_pages}", callback_data="noop"
        ))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton(
                text="▶️", callback_data=f"ach_sel_page_{page+1}"
            ))
        inline_rows.append(nav_row)
    
    # Кнопки действий
    inline_rows.append([
        InlineKeyboardButton(text="💾 Сохранить", callback_data="ach_save_profile"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="back_achievements")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_rows)
 

# ==================== КЛАВИАТУРЫ УЛУЧШЕНИЙ (ТЗ v4.0 п.12) ====================

def get_upgrades_menu_keyboard(prestige_level: int, upgrades: List[Dict] = None):
    """Клавиатура главного меню улучшений согласно ТЗ v4.0 п.12.2
    
    Args:
        prestige_level: Уровень престижа игрока
        upgrades: Список улучшений с уровнями пользователя
    """
    inline_rows = []
    
    if prestige_level < 20:
        # Улучшения недоступны
        inline_rows.append([
            InlineKeyboardButton(
                text="🔒 Требуется 20 престиж",
                callback_data="upgrade_locked"
            )
        ])
    else:
        # Разделяем по категориям
        farmer_upgrades = [u for u in (upgrades or []) if u.get('category') == 'farmer']
        storage_upgrades = [u for u in (upgrades or []) if u.get('category') == 'storage']
        
        # Категория фермеров
        if farmer_upgrades:
            inline_rows.append([
                InlineKeyboardButton(
                    text="🚜 Улучшения фермеров",
                    callback_data="upgrades_category_farmer"
                )
            ])
        
        # Категория хранилища
        if storage_upgrades:
            inline_rows.append([
                InlineKeyboardButton(
                    text="📦 Улучшения хранилища",
                    callback_data="upgrades_category_storage"
                )
            ])
        
        # Если нет улучшений, показываем заглушку
        if not farmer_upgrades and not storage_upgrades:
            inline_rows.append([
                InlineKeyboardButton(
                    text="📭 Улучшения скоро будут...",
                    callback_data="noop"
                )
            ])
    
    # Кнопка назад
    inline_rows.append([
        InlineKeyboardButton(text="🔙 В магазин", callback_data="back_shop")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_rows)


def get_upgrades_category_keyboard(category: str, upgrades: List[Dict], 
                                    user_balance: int, prestige_level: int):
    """Клавиатура для просмотра улучшений категории
    
    Args:
        category: Категория ('farmer' или 'storage')
        upgrades: Список улучшений с уровнями пользователя
        user_balance: Баланс пользователя
        prestige_level: Уровень престижа
    """
    inline_rows = []
    
    for upgrade in upgrades:
        code = upgrade.get('upgrade_code', '')
        name = upgrade.get('name', '???')
        icon = upgrade.get('icon', '⬆️')
        current_level = upgrade.get('current_level', 0)
        max_level = upgrade.get('max_level', 10)
        next_price = upgrade.get('next_price', 0)
        is_maxed = upgrade.get('is_maxed', False)
        required_prestige = upgrade.get('required_prestige', 20)
        
        # Проверяем доступность
        if prestige_level < required_prestige:
            status = f"🔒 Престиж {required_prestige}"
        elif is_maxed:
            status = "✅ МАКС"
        elif user_balance < next_price:
            status = f"❌ {next_price:,}🪙"
        else:
            status = f"💰 {next_price:,}🪙"
        
        # Уровень
        level_text = f"[{current_level}/{max_level}]"
        
        button_text = f"{icon} {name} {level_text} — {status}"
        
        inline_rows.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"upgrade_view_{code}" if not is_maxed and prestige_level >= required_prestige else f"upgrade_locked_{code}"
            )
        ])
    
    # Кнопка назад
    inline_rows.append([
        InlineKeyboardButton(text="🔙 К улучшениям", callback_data="shop_upgrades")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_rows)


def get_upgrade_detail_keyboard(upgrade: Dict, user_balance: int, prestige_level: int):
    """Клавиатура для детального просмотра улучшения
    
    Args:
        upgrade: Информация об улучшении
        user_balance: Баланс пользователя
        prestige_level: Уровень престижа
    """
    inline_rows = []
    
    code = upgrade.get('upgrade_code', '')
    current_level = upgrade.get('current_level', 0)
    max_level = upgrade.get('max_level', 10)
    next_price = upgrade.get('next_price', 0)
    is_maxed = upgrade.get('is_maxed', False)
    required_prestige = upgrade.get('required_prestige', 20)
    category = upgrade.get('category', 'farmer')
    
    # Проверяем возможность покупки
    if is_maxed:
        inline_rows.append([
            InlineKeyboardButton(
                text="✅ Достигнут максимальный уровень",
                callback_data="noop"
            )
        ])
    elif prestige_level < required_prestige:
        inline_rows.append([
            InlineKeyboardButton(
                text=f"🔒 Требуется {required_prestige} престиж",
                callback_data="upgrade_prestige_lock"
            )
        ])
    elif user_balance < next_price:
        inline_rows.append([
            InlineKeyboardButton(
                text=f"❌ Недостаточно монет ({next_price:,}🪙)",
                callback_data="upgrade_no_money"
            )
        ])
    else:
        inline_rows.append([
            InlineKeyboardButton(
                text=f"⬆️ Улучшить за {next_price:,}🪙",
                callback_data=f"upgrade_buy_{code}"
            )
        ])
        
        # Кнопка купить максимум (если хватает денег)
        if current_level < max_level - 1:
            # Считаем сколько уровней можно купить
            total_cost = 0
            levels_to_buy = 0
            base_price = upgrade.get('base_price', 100)
            multiplier = upgrade.get('price_multiplier', 2.0)
            
            for i in range(current_level, max_level):
                level_price = int(base_price * (multiplier ** i))
                if total_cost + level_price <= user_balance:
                    total_cost += level_price
                    levels_to_buy += 1
                else:
                    break
            
            if levels_to_buy > 1:
                inline_rows.append([
                    InlineKeyboardButton(
                        text=f"⬆️⬆️ Купить {levels_to_buy} ур. за {total_cost:,}🪙",
                        callback_data=f"upgrade_buy_max_{code}"
                    )
                ])
    
    # Кнопка назад
    inline_rows.append([
        InlineKeyboardButton(
            text="🔙 Назад", 
            callback_data=f"upgrades_category_{category}"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_rows)


def get_upgrade_confirm_keyboard(upgrade_code: str, price: int, levels: int = 1):
    """Клавиатура подтверждения покупки улучшения
    
    Args:
        upgrade_code: Код улучшения
        price: Цена
        levels: Количество уровней
    """
    inline_rows = []
    
    if levels == 1:
        inline_rows.append([
            InlineKeyboardButton(
                text=f"✅ Купить за {price:,}🪙",
                callback_data=f"upgrade_confirm_{upgrade_code}"
            )
        ])
    else:
        inline_rows.append([
            InlineKeyboardButton(
                text=f"✅ Купить {levels} ур. за {price:,}🪙",
                callback_data=f"upgrade_confirm_max_{upgrade_code}"
            )
        ])
    
    inline_rows.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"upgrade_view_{upgrade_code}")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_rows)


def get_upgrade_success_keyboard(upgrade_code: str, category: str):
    """Клавиатура после успешной покупки улучшения"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="⬆️ Ещё улучшить", 
                callback_data=f"upgrade_view_{upgrade_code}"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔙 К улучшениям", 
                callback_data=f"upgrades_category_{category}"
            )
        ]
    ])
 