-- ============================================================
-- МИГРАЦИЯ: Добавление поля is_active в shop_config
-- Этот скрипт безопасно добавляет отсутствующее поле
-- ============================================================

-- Проверяем существование поля is_active и добавляем если отсутствует
PRAGMA foreign_keys=OFF;

BEGIN TRANSACTION;

-- Создаём временную таблицу с правильной структурой
CREATE TABLE IF NOT EXISTS shop_config_new (
    item_code TEXT PRIMARY KEY,
    item_name TEXT NOT NULL,
    item_icon TEXT DEFAULT '🌱',
    category TEXT NOT NULL,
    buy_price INTEGER DEFAULT 0,
    sell_price INTEGER DEFAULT 0,
    growth_time INTEGER DEFAULT 0,
    yield_amount INTEGER DEFAULT 1,
    required_level INTEGER DEFAULT 1,
    exp_reward INTEGER DEFAULT 10,
    sort_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    effect_type TEXT,
    effect_value REAL,
    description TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,
    FOREIGN KEY (created_by) REFERENCES users(user_id)
);

-- Копируем данные из старой таблицы
INSERT INTO shop_config_new (
    item_code, item_name, item_icon, category, 
    buy_price, sell_price, growth_time, yield_amount,
    required_level, exp_reward, sort_order, is_active,
    effect_type, effect_value, description, created_at, created_by
)
SELECT 
    item_code, item_name, 
    COALESCE(item_icon, '🌱') as item_icon,
    category,
    COALESCE(buy_price, 0) as buy_price,
    COALESCE(sell_price, 0) as sell_price,
    COALESCE(growth_time, 0) as growth_time,
    COALESCE(yield_amount, 1) as yield_amount,
    COALESCE(required_level, 1) as required_level,
    COALESCE(exp_reward, 10) as exp_reward,
    COALESCE(sort_order, 0) as sort_order,
    1 as is_active,  -- Все существующие записи активны по умолчанию
    effect_type,
    effect_value,
    description,
    COALESCE(created_at, CURRENT_TIMESTAMP) as created_at,
    created_by
FROM shop_config;

-- Удаляем старую таблицу
DROP TABLE IF EXISTS shop_config;

-- Переименовываем новую таблицу
ALTER TABLE shop_config_new RENAME TO shop_config;

-- Пересоздаём индексы
CREATE INDEX IF NOT EXISTS idx_shop_config_category ON shop_config(category, is_active);
CREATE INDEX IF NOT EXISTS idx_shop_config_active ON shop_config(is_active, sort_order);
CREATE INDEX IF NOT EXISTS idx_shop_config_level ON shop_config(required_level);

COMMIT;

PRAGMA foreign_keys=ON;

-- ============================================================
-- Проверка результата
-- ============================================================
SELECT 'Миграция завершена. Количество записей:' as status, COUNT(*) as count FROM shop_config;
