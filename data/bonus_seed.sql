-- ============================================================
-- СИДЕР ДЛЯ ЕЖЕДНЕВНОГО БОНУСА (ТЗ v4.0 п.13)
-- ============================================================

-- Настройки рулетки (шансы по ТЗ)
INSERT OR IGNORE INTO daily_bonus_config (reward_type, name, icon, min_amount, max_amount, base_chance, item_code, sort_order) VALUES
('coins', 'Монеты', '💰', 50, 200, 0.60, NULL, 1),
('fertilizer', 'Удобрение', '⚡', 1, 3, 0.25, 'fertilizer_basic', 2),
('gems', 'Кристаллы', '💎', 1, 5, 0.10, NULL, 3),
('gold_fert', 'Золотое удобрение', '✨', 1, 1, 0.04, 'fertilizer_premium', 4),
('jackpot', 'Джекпот', '🎰', 500, 500, 0.01, NULL, 5);

-- ============================================================
-- АЧИВКИ ДЛЯ ЕЖЕДНЕВНОГО БОНУСА
-- ============================================================

INSERT OR IGNORE INTO achievement_categories (category_id, name, icon, description, sort_order)
VALUES ('daily_bonus', 'Ежедневный бонус', '🎁', 'Достижения за серию бонусов', 10);

-- Ачивка "Первая награда"
INSERT OR IGNORE INTO achievements (
    achievement_code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'first_bonus', 'Первая награда', 'Получи ежедневный бонус', 'daily_bonus',
    'claim_daily_bonus', 1, 0,
    100, 0, 0.0,
    '🎁', 1
);

-- Ачивка "Недельная серия"
INSERT OR IGNORE INTO achievements (
    achievement_code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'weekly_streak', 'Недельная серия', 'Получай бонус 7 дней подряд', 'daily_bonus',
    'streak_days', 7, 0,
    500, 10, 0.0,
    '🔥', 2
);

-- Ачивка "Месячный герой"
INSERT OR IGNORE INTO achievements (
    achievement_code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'monthly_streak', 'Месячный герой', 'Получай бонус 30 дней подряд', 'daily_bonus',
    'streak_days', 30, 0,
    5000, 50, 0.0,
    '👑', 3
);

-- Ачивка "Джекпотер"
INSERT OR IGNORE INTO achievements (
    achievement_code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'jackpot_winner', 'Джекпотер', 'Выиграй джекпот в ежедневном бонусе', 'daily_bonus',
    'win_jackpot', 1, 0,
    1000, 100, 0.0,
    '🎰', 4
);

-- ============================================================
-- КВЕСТЫ ДЛЯ ЕЖЕДНЕВНОГО БОНУСА
-- ============================================================

INSERT OR IGNORE INTO quest_templates (
    quest_code, name, description, quest_type,
    requirement_type, requirement_value, reward_coins, reward_gems,
    reward_item_code, reward_item_amount,
    is_active, sort_order
) VALUES (
    'claim_daily', 'Ежедневный бонус', 'Забери ежедневный бонус', 'daily',
    'claim_daily_bonus', 1, 100, 0,
    NULL, NULL,
    1, 1
);

INSERT OR IGNORE INTO quest_templates (
    quest_code, name, description, quest_type,
    requirement_type, requirement_value, reward_coins, reward_gems,
    reward_item_code, reward_item_amount,
    is_active, sort_order
) VALUES (
    'three_day_streak', 'Трехдневка', 'Поддерживай серию бонусов 3 дня', 'weekly',
    'streak_days', 3, 300, 5,
    NULL, NULL,
    1, 20
);
