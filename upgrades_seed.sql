-- ============================================================
-- СИДЕР ДЛЯ ПРОМОКОДОВ (ТЗ v4.0 п.14)
-- ============================================================

-- Ежедневные промокоды
INSERT OR IGNORE INTO promocodes (code, type, reward_coins, reward_gems, reward_items, valid_until, max_activations, is_active, created_by) VALUES
('LAZY2024', 'daily', 200, 0, NULL, datetime('now', '+2 days'), 1000, 1, 1),
('FARMER', 'daily', 500, 0, '[{"code": "fertilizer_basic", "amount": 3}]', datetime('now', '+2 days'), 1000, 1, 1),
('BOOST', 'daily', 0, 5, NULL, datetime('now', '+2 days'), 500, 1, 1);

-- Ивентовые промокоды
INSERT OR IGNORE INTO promocodes (code, type, reward_coins, reward_gems, reward_items, valid_until, max_activations, is_active, created_by) VALUES
('HALLOWEEN', 'event', 1000, 10, '[{"code": "pumpkin", "amount": 5}]', datetime('now', '+5 days'), 500, 1, 1),
('NEWYEAR', 'event', 2025, 20, '[{"code": "gift_box", "amount": 3}]', datetime('now', '+7 days'), 300, 1, 1),
('SUMMER', 'event', 0, 50, '[{"code": "sunflower", "amount": 10}]', datetime('now', '+3 days'), 200, 1, 1);

-- Стартовый промокод (вечный, только для новичков)
INSERT OR IGNORE INTO promocodes (code, type, reward_coins, reward_gems, reward_items, valid_until, max_activations, is_active, created_by) VALUES
('STARTER', 'starter', 500, 5, '[{"code": "seed_corn", "amount": 5}, {"code": "fertilizer_basic", "amount": 2}]', NULL, 0, 1, 1),
('WELCOME', 'starter', 300, 3, '[{"code": "seed_potato", "amount": 3}]', NULL, 0, 1, 1);

-- VIP промокоды
INSERT OR IGNORE INTO promocodes (code, type, reward_coins, reward_gems, reward_items, valid_until, max_activations, is_active, created_by) VALUES
('VIP100', 'event', 5000, 100, '[{"code": "fertilizer_instant", "amount": 5}, {"code": "fertilizer_premium", "amount": 3}]', datetime('now', '+30 days'), 100, 1, 1),
('MEGA', 'event', 10000, 200, NULL, datetime('now', '+1 days'), 10, 1, 1);

-- ============================================================
-- АЧИВКИ ДЛЯ ПРОМОКОДОВ
-- ============================================================

-- Категория ачивок для промокодов
INSERT OR IGNORE INTO achievement_categories (category_id, name, icon, description, sort_order)
VALUES ('promo', 'Промокоды', '🎁', 'Достижения за использование промокодов', 9);

-- Ачивка "Первый промокод"
INSERT OR IGNORE INTO achievements (
    achievement_code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'first_promo', 'Первый промокод', 'Активируй свой первый промокод', 'promo',
    'use_promocode', 1, 0,
    100, 1, 0.0,
    '🎁', 1
);

-- Ачивка "Промо-охотник"
INSERT OR IGNORE INTO achievements (
    achievement_code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'promo_hunter', 'Промо-охотник', 'Активируй 10 разных промокодов', 'promo',
    'use_promocode', 10, 0,
    500, 5, 0.0,
    '🎯', 2
);

-- Ачивка "Богатый на бонусы"
INSERT OR IGNORE INTO achievements (
    achievement_code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'bonus_king', 'Богатый на бонусы', 'Получи 10,000 монет через промокоды', 'promo',
    'promo_coins', 10000, 0,
    1000, 10, 0.0,
    '💰', 3
);

-- ============================================================
-- КВЕСТЫ ДЛЯ ПРОМОКОДОВ
-- ============================================================

-- Квест: Активируй промокод
INSERT OR IGNORE INTO quest_templates (
    quest_code, name, description, quest_type,
    requirement_type, requirement_value, reward_coins, reward_gems,
    reward_item_code, reward_item_amount,
    is_active, sort_order
) VALUES (
    'activate_promo', 'Промо-день', 'Активируй любой промокод', 'daily',
    'use_promocode', 1, 200, 2,
    NULL, NULL,
    1, 60
);
