-- ============================================================
-- СИДЕР ДЛЯ РЕФЕРАЛЬНОЙ СИСТЕМЫ (ТЗ v4.0 п.15)
-- ============================================================

-- ============================================================
-- АЧИВКИ ДЛЯ РЕФЕРАЛОВ
-- ============================================================

-- Категория ачивок для рефералов
INSERT OR IGNORE INTO achievement_categories (category_id, name, icon, description, sort_order)
VALUES ('referrals', 'Рефералы', '👥', 'Достижения за приглашение друзей', 10);

-- Ачивка "Первый друг"
INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'first_friend', 'Первый друг', 'Пригласи своего первого друга', 'referrals',
    'refer_friend', 1, 0,
    500, 5, 0.0,
    '👥', 1
);

-- Ачивка "Социальный фермер"
INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'social_farmer', 'Социальный фермер', 'Пригласи 5 друзей', 'referrals',
    'refer_friend', 5, 0,
    2000, 15, 0.0,
    '👥', 2
);

-- Ачивка "Лидер мнений"
INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'opinion_leader', 'Лидер мнений', 'Пригласи 20 друзей', 'referrals',
    'refer_friend', 20, 0,
    10000, 50, 0.0,
    '🌟', 3
);

-- Ачивка "Фермерская династия"
INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'dynasty_master', 'Фермерская династия', 'Пригласи 50 друзей', 'referrals',
    'refer_friend', 50, 0,
    50000, 100, 0.1,
    '👑', 4
);

-- Ачивка "Ментор"
INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'mentor', 'Ментор', '5 твоих рефералов достигли 10 престижа', 'referrals',
    'referral_prestige_10', 5, 0,
    25000, 75, 0.0,
    '🎓', 5
);

-- Ачивка "Золотой реферал"
INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'golden_referral', 'Золотой реферал', 'Заработай 10,000 монет через реферальную систему', 'referrals',
    'referral_earnings', 10000, 0,
    5000, 25, 0.0,
    '💰', 6
);

-- ============================================================
-- КВЕСТЫ ДЛЯ РЕФЕРАЛОВ
-- ============================================================

-- Квест: Пригласи друга
INSERT OR IGNORE INTO quest_templates (
    quest_code, name, description, quest_type,
    requirement_type, requirement_value, reward_coins, reward_gems,
    reward_item_code, reward_item_amount,
    is_active, sort_order
) VALUES (
    'invite_friend', 'Пригласи друга', 'Пригласи друга по реферальной ссылке', 'weekly',
    'refer_friend', 1, 300, 3,
    'fertilizer_basic', 2,
    1, 110
);

-- Квест: Активные рефералы
INSERT OR IGNORE INTO quest_templates (
    quest_code, name, description, quest_type,
    requirement_type, requirement_value, reward_coins, reward_gems,
    reward_item_code, reward_item_amount,
    is_active, sort_order
) VALUES (
    'active_referrals', 'Активные рефералы', 'Получи награды за достижения рефералов', 'weekly',
    'referral_rewards', 3, 500, 5,
    NULL, NULL,
    1, 111
);

-- ============================================================
-- НАСТРОЙКИ РЕФЕРАЛЬНОЙ СИСТЕМЫ
-- ============================================================

-- Таблица для хранения настроек (если нужно изменить награды)
-- Награды за рефералов:
-- registration: 100 coins
-- prestige1: 50 coins  
-- prestige5: 200 coins + 5 gems
-- prestige10: 500 coins + 15 gems

-- Для нового пользователя (реферала):
-- start_bonus: 100 coins + seeds + fertilizer
