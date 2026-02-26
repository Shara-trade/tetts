-- ============================================================
-- СИДЕР ДЛЯ СИСТЕМЫ ФЕРМЕРОВ (ТЗ v4.0 п.11)
-- ============================================================

-- Типы фермеров
INSERT OR IGNORE INTO farmer_types (type_code, name, icon, description, duration_days, price_coins, price_gems, bonus_percent, uses_fertilizer, salary_per_hour, work_interval_seconds, sort_order) VALUES
('basic', 'Базовый фермер', '👤', 'Автоматически сажает и собирает урожай', 7, 5000, 0, 0, 0, 50, 300, 1),
('experienced', 'Опытный фермер', '👨‍🌾', 'Все функции + 10% к доходу', 30, 0, 50, 10, 0, 100, 180, 2),
('pro', 'Профи фермер', '👩‍🌾', 'Все функции + 25% к доходу + удобрения', NULL, 0, 200, 25, 1, 200, 120, 3);

-- ============================================================
-- УЛУЧШЕНИЯ ДЛЯ ФЕРМЕРОВ (ТЗ v4.0 п.12)
-- ============================================================

-- Улучшения фермера
INSERT OR IGNORE INTO upgrades (upgrade_code, name, icon, description, category, max_level, base_price, price_multiplier, effect_type, effect_value, effect_unit, required_prestige, sort_order) VALUES
('farmer_speed', 'Скорость фермера', '⚡', 'Увеличивает скорость работы фермера на 25% за уровень', 'farmer', 10, 10000, 1.5, 'speed', 0.25, '%', 20, 1),
('farmer_income', 'Доход фермера', '💰', 'Увеличивает доход от фермера на 10% за уровень', 'farmer', 10, 15000, 1.6, 'income', 0.10, '%', 20, 2),
('farmer_capacity', 'Вместимость фермера', '📦', 'Увеличивает количество одновременно обрабатываемых грядок на 50% за уровень', 'farmer', 10, 20000, 1.7, 'capacity', 0.50, '%', 20, 3);

-- Улучшения хранилища
INSERT OR IGNORE INTO upgrades (upgrade_code, name, icon, description, category, max_level, base_price, price_multiplier, effect_type, effect_value, effect_unit, required_prestige, sort_order) VALUES
('storage_capacity', 'Вместимость инвентаря', '🎒', 'Увеличивает вместимость инвентаря на 100 единиц за уровень', 'storage', 20, 5000, 1.4, 'capacity', 100, 'ед.', 20, 10),
('storage_protection', 'Защита от краж', '🛡️', 'Уменьшает потери при передачах на 25% за уровень', 'storage', 10, 10000, 1.5, 'protection', 0.25, '%', 20, 11);

-- ============================================================
-- АЧИВКИ ДЛЯ ФЕРМЕРОВ
-- ============================================================

-- Категория ачивок для фермеров
INSERT OR IGNORE INTO achievement_categories (category_id, name, icon, description, sort_order)
VALUES ('farmers', 'Фермеры', '👤', 'Достижения за найм и использование фермеров', 8);

-- Ачивка "Первый фермер"
INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'first_farmer', 'Первый фермер', 'Нанми своего первого фермера', 'farmers',
    'hire_farmer', 1, 0,
    200, 0, 0.0,
    '👤', 1
);

-- Ачивка "Фермерская династия"
INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'farmer_dynasty', 'Фермерская династия', 'Найми 10 фермеров за всё время', 'farmers',
    'hire_farmer', 10, 0,
    1000, 10, 0.0,
    '👥', 2
);

-- Ачивка "Автоматизация"
INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'automation_master', 'Мастер автоматизации', 'Собери 1000 урожаев с помощью фермеров', 'farmers',
    'farmer_harvest', 1000, 0,
    5000, 25, 0.0,
    '🤖', 3
);

-- Ачивка "Профессионал"
INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'pro_farmer', 'Профессионал', 'Найми Профи фермера', 'farmers',
    'hire_pro_farmer', 1, 0,
    2000, 20, 0.0,
    '👩‍🌾', 4
);

-- Ачивка "Терпеливый"
INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'patient_farmer', 'Терпеливый фермер', 'Держи одного фермера 30 дней', 'farmers',
    'farmer_days', 30, 0,
    3000, 30, 0.0,
    '⏳', 5
);

-- ============================================================
-- КВЕСТЫ ДЛЯ ФЕРМЕРОВ
-- ============================================================

-- Квест: Найми фермера
INSERT OR IGNORE INTO quest_templates (
    quest_code, name, description, quest_type,
    requirement_type, requirement_value, reward_coins, reward_gems,
    reward_item_code, reward_item_amount,
    is_active, sort_order
) VALUES (
    'hire_first_farmer', 'Найми помощника', 'Найми своего первого фермера в магазине', 'daily',
    'hire_farmer', 1, 500, 5,
    NULL, NULL,
    1, 50
);

-- Квест: Используй фермера
INSERT OR IGNORE INTO quest_templates (
    quest_code, name, description, quest_type,
    requirement_type, requirement_value, reward_coins, reward_gems,
    reward_item_code, reward_item_amount,
    is_active, sort_order
) VALUES (
    'use_farmer', 'Автоматизация', 'Пусть фермер соберёт 10 урожаев', 'daily',
    'farmer_harvest', 10, 300, 3,
    NULL, NULL,
    1, 51
);

-- Квест: Продуктивный день (еженедельный)
INSERT OR IGNORE INTO quest_templates (
    quest_code, name, description, quest_type,
    requirement_type, requirement_value, reward_coins, reward_gems,
    reward_item_code, reward_item_amount,
    is_active, sort_order
) VALUES (
    'farmer_productive_week', 'Продуктивная неделя', 'Собери 100 урожаев с помощью фермеров', 'weekly',
    'farmer_harvest', 100, 2000, 20,
    NULL, NULL,
    1, 100
);
