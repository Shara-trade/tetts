-- ============================================================
-- СИДЕР ДЛЯ СЕЗОННЫХ ИВЕНТОВ (ТЗ v4.0 п.16)
-- ============================================================

-- ============================================================
-- ИВЕНТОВЫЕ КУЛЬТУРЫ И ПРЕДМЕТЫ
-- ============================================================

-- Хэллоуин: Тыква
INSERT OR IGNORE INTO shop_config (
    item_code, item_name, item_icon, category, 
    buy_price, sell_price, growth_time, yield_amount,
    required_level, is_active, is_seasonal, season,
    description, exp_reward, sort_order
) VALUES (
    'pumpkin', 'Тыква', '🎃', 'seed',
    100, 250, 600, 1,
    1, 1, 1, 'halloween',
    'Хэллоуинская тыква! Продается дороже обычных культур.',
    50, 100
);

-- Хэллоуин: Пугало (ивентовый предмет)
INSERT OR IGNORE INTO shop_config (
    item_code, item_name, item_icon, category,
    buy_price, sell_price, growth_time, yield_amount,
    required_level, is_active, is_seasonal, season,
    description, effect_type, effect_value, sort_order
) VALUES (
    'scarecrow', 'Пугало', '🎃', 'decor',
    500, 0, 0, 0,
    1, 1, 1, 'halloween',
    'Пугало для Хэллоуина! +10% к шансу нахождения кейсов. Работает только во время ивента.',
    'case_chance', 0.10, 101
);

-- Новый Год: Елка
INSERT OR IGNORE INTO shop_config (
    item_code, item_name, item_icon, category,
    buy_price, sell_price, growth_time, yield_amount,
    required_level, is_active, is_seasonal, season,
    description, exp_reward, sort_order
) VALUES (
    'christmas_tree', 'Новогодняя елка', '🎄', 'seed',
    150, 400, 900, 1,
    1, 1, 1, 'newyear',
    'Праздничная елка! Приносит подарки при сборе.',
    75, 102
);

-- Новый Год: Подарок
INSERT OR IGNORE INTO shop_config (
    item_code, item_name, item_icon, category,
    buy_price, sell_price, growth_time, yield_amount,
    required_level, is_active, is_seasonal, season,
    description, sort_order
) VALUES (
    'gift_box', 'Подарок', '🎁', 'special',
    0, 0, 0, 0,
    1, 1, 1, 'newyear',
    'Новогодний подарок! Можно открыть за кристаллы или продать.',
    103
);

-- ============================================================
-- АЧИВКИ ДЛЯ ИВЕНТОВ
-- ============================================================

-- Категория ачивок для ивентов
INSERT OR IGNORE INTO achievement_categories (category_id, name, icon, description, sort_order)
VALUES ('events', 'Ивенты', '🎉', 'Достижения за участие в сезонных ивентах', 11);

-- Хэллоуин ачивки
INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'pumpkin_king', 'Тыквенный король', 'Собери 100 тыкв за Хэллоуин', 'events',
    'harvest_pumpkin', 100, 0,
    1000, 10, 0.0,
    '🎃', 1
);

INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'pumpkin_master', 'Тыквенный мастер', 'Собери 500 тыкв за Хэллоуин', 'events',
    'harvest_pumpkin', 500, 0,
    5000, 50, 0.0,
    '👑', 2
);

INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'scarecrow_owner', 'Владелец пугала', 'Купи пугало на Хэллоуин', 'events',
    'buy_scarecrow', 1, 0,
    500, 5, 0.0,
    '🎃', 3
);

-- Новый год ачивки
INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'gift_collector', 'Собиратель подарков', 'Собери 50 подарков на Новый год', 'events',
    'collect_gift', 50, 0,
    2000, 20, 0.0,
    '🎁', 4
);

INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'christmas_spirit', 'Новогоднее настроение', 'Посади 20 елок на Новый год', 'events',
    'plant_christmas_tree', 20, 0,
    1500, 15, 0.0,
    '🎄', 5
);

-- Универсальные ивентовые ачивки
INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'event_participant', 'Участник ивентов', 'Примите участие в 3 разных ивентах', 'events',
    'participate_event', 3, 0,
    500, 5, 0.0,
    '🎉', 6
);

INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'event_winner', 'Победитель ивентов', 'Зайди в топ-10 любого ивента', 'events',
    'event_top_10', 1, 0,
    2000, 25, 0.0,
    '🏆', 7
);

-- ============================================================
-- КВЕСТЫ ДЛЯ ИВЕНТОВ
-- ============================================================

-- Хэллоуин квест
INSERT OR IGNORE INTO quest_templates (
    quest_code, name, description, quest_type,
    requirement_type, requirement_value, reward_coins, reward_gems,
    reward_item_code, reward_item_amount,
    is_active, sort_order
) VALUES (
    'halloween_pumpkins', 'Тыквенный сбор', 'Собери 10 тыкв за Хэллоуин', 'weekly',
    'harvest_pumpkin', 10, 500, 5,
    'fertilizer_premium', 1,
    1, 120
);

-- Новый год квест
INSERT OR IGNORE INTO quest_templates (
    quest_code, name, description, quest_type,
    requirement_type, requirement_value, reward_coins, reward_gems,
    reward_item_code, reward_item_amount,
    is_active, sort_order
) VALUES (
    'newyear_trees', 'Новогодние елки', 'Посади 5 новогодних елок', 'weekly',
    'plant_christmas_tree', 5, 600, 6,
    'gift_box', 3,
    1, 121
);

-- ============================================================
-- ПРИМЕРЫ ИВЕНТОВ (раскомментируйте для активации)
-- ============================================================

-- Хэллоуин 2024 (25 октября - 5 ноября)
-- INSERT OR IGNORE INTO seasonal_events (name, description, season, start_date, end_date, multiplier, is_active) VALUES
-- ('Хэллоуин 2024', 'Особые тыквы, пугала и +50% дохода ночью!', 'halloween', '2024-10-25', '2024-11-05', 1.5, 1);

-- Новый Год 2024-2025 (25 декабря - 10 января)
-- INSERT OR IGNORE INTO seasonal_events (name, description, season, start_date, end_date, multiplier, is_active) VALUES
-- ('Новый Год 2025', 'Елки, подарки и праздничное настроение!', 'newyear', '2024-12-25', '2025-01-10', 1.3, 1);
