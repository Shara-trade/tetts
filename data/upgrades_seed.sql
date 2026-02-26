-- ============================================================
-- СИДЕР ДЛЯ УЛУЧШЕНИЙ (ТЗ v4.0 п.12)
-- ============================================================

-- Улучшения фермера (доступны с 20 престижа)
INSERT OR IGNORE INTO upgrades (
    upgrade_code, name, icon, description, category,
    max_level, base_price, price_multiplier, effect_type, effect_value, effect_unit,
    required_prestige, sort_order, is_active
) VALUES
-- Скорость фермера (+25% за уровень)
('farmer_speed', 'Скорость фермера', '⚡', 
 'Увеличивает скорость работы фермера на 25% за уровень. Фермер выполняет действия быстрее.',
 'farmer', 10, 10000, 1.5, 'speed', 0.25, '%', 20, 1, 1),

-- Доход фермера (+10% за уровень)
('farmer_income', 'Доход фермера', '💰',
 'Увеличивает доход от работы фермера на 10% за уровень. Больше монет за каждый собранный урожай.',
 'farmer', 10, 15000, 1.6, 'income', 0.10, '%', 20, 2, 1),

-- Вместимость фермера (+50% за уровень)
('farmer_capacity', 'Вместимость фермера', '📦',
 'Увеличивает количество одновременно обрабатываемых грядок на 50% за уровень.',
 'farmer', 10, 20000, 1.7, 'capacity', 0.50, '%', 20, 3, 1),

-- Улучшения хранилища (доступны с 20 престижа)
('storage_capacity', 'Вместимость инвентаря', '🎒',
 'Увеличивает максимальную вместимость инвентаря на 100 единиц за уровень.',
 'storage', 20, 5000, 1.4, 'capacity', 100, 'ед.', 20, 10, 1),

('storage_protection', 'Защита от потерь', '🛡️',
 'Уменьшает потери при передачах и операциях на 25% за уровень.',
 'storage', 10, 10000, 1.5, 'protection', 0.25, '%', 20, 11, 1);

-- ============================================================
-- КАТЕГОРИИ ДЛЯ УЛУЧШЕНИЙ (если не созданы)
-- ============================================================

INSERT OR IGNORE INTO achievement_categories (category_id, name, icon, description, sort_order)
VALUES 
('farmer', 'Фермер', '👤', 'Улучшения для автоматизации фермера', 10),
('storage', 'Хранилище', '📦', 'Улучшения для инвентаря и хранилища', 11);

-- ============================================================
-- АЧИВКИ ДЛЯ УЛУЧШЕНИЙ
-- ============================================================

INSERT OR IGNORE INTO achievement_categories (category_id, name, icon, description, sort_order)
VALUES ('upgrades', 'Улучшения', '⬆️', 'Достижения за прокачку улучшений', 9);

-- Первая прокачка
INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'first_upgrade', 'Первая прокачка', 'Купи любое улучшение', 'upgrades',
    'buy_upgrade', 1, 0,
    500, 0, 0.0,
    '⬆️', 1
);

-- Мастер улучшений
INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'upgrade_master', 'Мастер улучшений', 'Достигни 5 уровня любого улучшения', 'upgrades',
    'upgrade_level_5', 1, 0,
    2000, 10, 0.0,
    '⭐', 2
);

-- Легенда прокачки
INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'upgrade_legend', 'Легенда прокачки', 'Достигни максимального уровня любого улучшения', 'upgrades',
    'max_upgrade', 1, 0,
    10000, 50, 0.0,
    '🏆', 3
);

-- Инвестор
INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'upgrade_investor', 'Инвестор', 'Потрать 100,000🪙 на улучшения', 'upgrades',
    'upgrade_spend', 100000, 0,
    5000, 25, 0.0,
    '💎', 4
);

-- ============================================================
-- КВЕСТЫ ДЛЯ УЛУЧШЕНИЙ
-- ============================================================

INSERT OR IGNORE INTO quest_templates (
    quest_code, name, description, quest_type,
    requirement_type, requirement_value, reward_coins, reward_gems,
    reward_item_code, reward_item_amount,
    is_active, sort_order
) VALUES (
    'buy_first_upgrade', 'Первая инвестиция', 'Купи любое улучшение в магазине', 'daily',
    'buy_upgrade', 1, 300, 3,
    NULL, NULL,
    1, 60
);

INSERT OR IGNORE INTO quest_templates (
    quest_code, name, description, quest_type,
    requirement_type, requirement_value, reward_coins, reward_gems,
    reward_item_code, reward_item_amount,
    is_active, sort_order
) VALUES (
    'upgrade_spending_week', 'Инвестиционная неделя', 'Потрать 50,000🪙 на улучшения', 'weekly',
    'upgrade_spend', 50000, 2000, 20,
    NULL, NULL,
    1, 120
);
