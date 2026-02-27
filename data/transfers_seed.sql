-- ============================================================
-- СИДЕР ДЛЯ ПЕРЕВОДОВ (ТЗ v4.0 п.18)
-- ============================================================

-- ============================================================
-- АЧИВКИ ДЛЯ ПЕРЕВОДОВ
-- ============================================================

-- Категория ачивок для переводов
INSERT OR IGNORE INTO achievement_categories (category_id, name, icon, description, sort_order)
VALUES ('transfers', 'Переводы', '💰', 'Достижения за переводы между игроками', 12);

-- Ачивка "Первый перевод"
INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'first_transfer', 'Первый перевод', 'Отправь свои первые монеты другу', 'transfers',
    'send_transfer', 1, 0,
    200, 2, 0.0,
    '💰', 1
);

-- Ачивка "Щедрый фермер"
INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'generous_farmer', 'Щедрый фермер', 'Отправь друзьям 10,000 монет всего', 'transfers',
    'transfer_amount', 10000, 0,
    1000, 10, 0.0,
    '💸', 2
);

-- Ачивка "Благотворитель"
INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'philanthropist', 'Благотворитель', 'Отправь друзьям 100,000 монет всего', 'transfers',
    'transfer_amount', 100000, 0,
    5000, 50, 0.0,
    '🏆', 3
);

-- Ачивка "Популярный"
INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'popular', 'Популярный', 'Получи переводы от 10 разных игроков', 'transfers',
    'receive_transfers_from', 10, 0,
    1500, 15, 0.0,
    '👥', 4
);

-- ============================================================
-- КВЕСТЫ ДЛЯ ПЕРЕВОДОВ
-- ============================================================

-- Квест: Отправь перевод
INSERT OR IGNORE INTO quest_templates (
    quest_code, name, description, quest_type,
    requirement_type, requirement_value, reward_coins, reward_gems,
    reward_item_code, reward_item_amount,
    is_active, sort_order
) VALUES (
    'send_transfer', 'Делись богатством', 'Отправь перевод другому игроку', 'weekly',
    'send_transfer', 1, 300, 3,
    NULL, NULL,
    1, 130
);

-- Квест: Щедрая неделя
INSERT OR IGNORE INTO quest_templates (
    quest_code, name, description, quest_type,
    requirement_type, requirement_value, reward_coins, reward_gems,
    reward_item_code, reward_item_amount,
    is_active, sort_order
) VALUES (
    'generous_week', 'Щедрая неделя', 'Отправь друзьям 5,000 монет за неделю', 'weekly',
    'transfer_amount', 5000, 1000, 10,
    'fertilizer_premium', 2,
    1, 131
);
