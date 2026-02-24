-- ============================================================
-- СИДЕР УДОБРЕНИЙ ДЛЯ ТЗ v4.0 п.10
-- ============================================================

-- Базовое удобрение (ускорение роста на 25%)
INSERT OR IGNORE INTO shop_config (
    item_code, item_name, item_icon, buy_price, sell_price,
    category, growth_time, required_level, effect_value, effect_type,
    description, is_active, sort_order
) VALUES (
    'fertilizer_basic', 'Обычное удобрение', '🧪', 100, 50,
    'fertilizer', 0, 1, 0.25, 'speed',
    'Ускоряет рост культуры на 25%. Используется один раз на грядку.',
    1, 1
);

-- Улучшенное удобрение (ускорение роста на 50%)
INSERT OR IGNORE INTO shop_config (
    item_code, item_name, item_icon, buy_price, sell_price,
    category, growth_time, required_level, effect_value, effect_type,
    description, is_active, sort_order
) VALUES (
    'fertilizer_advanced', 'Улучшенное удобрение', '🧪', 250, 125,
    'fertilizer', 0, 3, 0.50, 'speed',
    'Ускоряет рост культуры на 50%. Для опытных фермеров.',
    1, 2
);

-- Мгновенное удобрение (мгновенный рост + 10% к доходу)
INSERT OR IGNORE INTO shop_config (
    item_code, item_name, item_icon, buy_price, sell_price,
    category, growth_time, required_level, effect_value, effect_type,
    description, is_active, sort_order
) VALUES (
    'fertilizer_instant', 'Мгновенный рост', '⚡', 500, 250,
    'fertilizer', 0, 5, 0.10, 'instant',
    'Мгновенно созревает культуру и даёт +10% к доходу!',
    1, 3
);

-- Премиум удобрение (ускорение 75% + 15% к доходу)
INSERT OR IGNORE INTO shop_config (
    item_code, item_name, item_icon, buy_price, sell_price,
    category, growth_time, required_level, effect_value, effect_type,
    description, is_active, sort_order
) VALUES (
    'fertilizer_premium', 'Премиум удобрение', '✨', 1000, 500,
    'fertilizer', 0, 7, 0.75, 'speed',
    'Ультра-ускорение роста на 75%. Премиум качество для максимальной эффективности.',
    1, 4
);

-- Удобрение только для бонуса дохода (+25% к доходу)
INSERT OR IGNORE INTO shop_config (
    item_code, item_name, item_icon, buy_price, sell_price,
    category, growth_time, required_level, effect_value, effect_type,
    description, is_active, sort_order
) VALUES (
    'fertilizer_profit', 'Прибыльное удобрение', '💰', 750, 375,
    'fertilizer', 0, 6, 0.25, 'bonus',
    'Не ускоряет рост, но даёт +25% к доходу при сборе урожая!',
    1, 5
);

-- Кристальное удобрение (мгновенный рост + 25% к доходу, покупка за кристаллы)
INSERT OR IGNORE INTO shop_config (
    item_code, item_name, item_icon, buy_price, sell_price,
    category, growth_time, required_level, effect_value, effect_type,
    description, is_active, sort_order
) VALUES (
    'fertilizer_crystal', 'Кристальное удобрение', '💎', 50, 25,
    'fertilizer', 0, 10, 0.25, 'instant',
    'Мгновенный рост +25% к доходу! Можно купить только за кристаллы.',
    1, 6
);

-- ============================================================
-- АЧИВКА ДЛЯ УДОБРЕНИЙ
-- ============================================================

-- Категория ачивок для удобрений (если ещё не создана)
INSERT OR IGNORE INTO achievement_categories (category_id, name, icon, description, sort_order)
VALUES ('fertilizer', 'Удобрения', '🧪', 'Достижения за использование удобрений', 6);

-- Ачивка "Первое удобрение"
INSERT OR IGNORE INTO achievements (
    achievement_code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'first_fertilizer', 'Первое удобрение', 'Примени удобрение к грядке', 'fertilizer',
    'use_fertilizer', 1, 0,
    100, 0, 0.0,
    '🧪', 1
);

-- Ачивка "Мастер удобрений"
INSERT OR IGNORE INTO achievements (
    achievement_code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'fertilizer_master', 'Мастер удобрений', 'Используй удобрения 50 раз', 'fertilizer',
    'use_fertilizer', 50, 0,
    1000, 5, 0.0,
    '🧪', 2
);

-- Ачивка "Мгновенный фермер"
INSERT OR IGNORE INTO achievements (
    achievement_code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'instant_farmer', 'Мгновенный фермер', 'Используй мгновенное удобрение 10 раз', 'fertilizer',
    'use_instant_fertilizer', 10, 0,
    500, 10, 0.0,
    '⚡', 3
);
