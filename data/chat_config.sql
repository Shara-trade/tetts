-- ============================================================
-- КОНФИГУРАЦИЯ ОФИЦИАЛЬНОГО ЧАТА (ТЗ v4.0 п.19)
-- ============================================================

-- ============================================================
-- НАСТРОЙКИ ЧАТА
-- ============================================================

-- Создаем таблицу настроек чата если её нет
CREATE TABLE IF NOT EXISTS chat_config (
    config_key TEXT PRIMARY KEY,
    config_value TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Базовые настройки чата
INSERT OR REPLACE INTO chat_config (config_key, config_value) VALUES
('chat_link', 'https://t.me/lazy_farmer_chat'),
('chat_username', 'lazy_farmer_chat'),
('chat_name', 'Lazy Farmer - Официальный чат'),
('notifications_enabled', 'true'),
('notification_cooldown_hours', '1');

-- ============================================================
-- АЧИВКИ СВЯЗАННЫЕ С ЧАТОМ
-- ============================================================

-- Категория для чат-ачивок
INSERT OR IGNORE INTO achievement_categories (category_id, name, icon, description, sort_order)
VALUES ('community', 'Сообщество', '💬', 'Достижения за активность в сообществе', 13);

-- Ачивка "Чатер"
INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'chatter', 'Общительный фермер', 'Вступи в официальный чат', 'community',
    'join_chat', 1, 0,
    100, 1, 0.0,
    '💬', 1
);

-- Ачивка "Помощник"
INSERT OR IGNORE INTO achievements (
    code, name, description, category_id,
    requirement_type, requirement_count, is_secret,
    reward_coins, reward_gems, reward_multiplier,
    icon, sort_order
) VALUES (
    'helper', 'Помощник', 'Помоги 10 новичкам в чате', 'community',
    'help_newbies', 10, 0,
    500, 5, 0.0,
    '🆘', 2
);

-- ============================================================
-- КВЕСТЫ СВЯЗАННЫЕ С ЧАТОМ
-- ============================================================

-- Квест: Вступи в чат
INSERT OR IGNORE INTO quest_templates (
    quest_code, name, description, quest_type,
    requirement_type, requirement_value, reward_coins, reward_gems,
    reward_item_code, reward_item_amount,
    is_active, sort_order
) VALUES (
    'join_chat', 'Стань частью сообщества', 'Вступи в официальный чат фермеров', 'weekly',
    'join_chat', 1, 200, 2,
    NULL, NULL,
    1, 140
);

-- ============================================================
-- ENV ПЕРЕМЕННЫЕ ДЛЯ ЧАТА (добавьте в .env файл)
-- ============================================================

-- OFFICIAL_CHAT_LINK=https://t.me/lazy_farmer_chat
-- OFFICIAL_CHAT_USERNAME=lazy_farmer_chat
-- OFFICIAL_CHAT_ID=-1001234567890  -- ID чата для бота (если нужно отправлять уведомления)
-- CHAT_NOTIFICATIONS_ENABLED=true
