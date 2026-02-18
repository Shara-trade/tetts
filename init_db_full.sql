-- ============================================================
-- ПОЛНАЯ СТРУКТУРА БАЗЫ ДАННЫХ
-- Игра «Ленивый Фермер» v2.0
-- Поддержка: SQLite (основная) / PostgreSQL (альтернатива)
-- ============================================================

-- ============================================================
-- 1. ТАБЛИЦА ПОЛЬЗОВАТЕЛЕЙ
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,                          -- ID пользователя Telegram
    username VARCHAR(100),                                -- Username Telegram
    first_name VARCHAR(100),                              -- Имя пользователя
    last_name VARCHAR(100),                               -- Фамилия
    balance BIGINT DEFAULT 0,                             -- Монеты
    gems INTEGER DEFAULT 0,                               -- Кристаллы (премиум валюта)
    exp INTEGER DEFAULT 0,                                -- Опыт
    prestige_level INTEGER DEFAULT 1,                     -- Уровень престижа
    prestige_multiplier DECIMAL(3,2) DEFAULT 1.0,         -- Множитель престижа
    city_level INTEGER DEFAULT 1,                         -- Уровень города
    total_harvested BIGINT DEFAULT 0,                     -- Всего собрано урожая
    total_planted BIGINT DEFAULT 0,                       -- Всего посажено
    total_earned BIGINT DEFAULT 0,                        -- Всего заработано
    total_spent BIGINT DEFAULT 0,                         -- Всего потрачено
    is_banned BOOLEAN DEFAULT FALSE,                      -- Забанен ли
    ban_reason TEXT,                                      -- Причина бана
    ban_until TIMESTAMP,                                  -- До какого времени бан
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,    -- Последняя активность
    joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,      -- Дата регистрации
    referrer_id INTEGER REFERENCES users(user_id),        -- Кто пригласил
    language VARCHAR(10) DEFAULT 'ru',                    -- Язык
    
    -- Поля для социальных функций
    farm_name VARCHAR(100),                               -- Название фермы
    avatar_url TEXT,                                      -- URL аватара
    
    -- Настройки
    notifications_enabled BOOLEAN DEFAULT TRUE,           -- Уведомления включены
    sound_enabled BOOLEAN DEFAULT TRUE,                   -- Звуки включены
    
    -- Аудит
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для users
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_balance ON users(balance DESC);
CREATE INDEX IF NOT EXISTS idx_users_prestige ON users(prestige_level DESC);
CREATE INDEX IF NOT EXISTS idx_users_last_active ON users(last_activity);
CREATE INDEX IF NOT EXISTS idx_users_joined ON users(joined_date);
CREATE INDEX IF NOT EXISTS idx_users_banned ON users(is_banned);
CREATE INDEX IF NOT EXISTS idx_users_referrer ON users(referrer_id);

-- ============================================================
-- 2. ТАБЛИЦЫ АДМИНИСТРИРОВАНИЯ
-- ============================================================

-- 2.1 Роли администраторов
CREATE TABLE IF NOT EXISTS admin_roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK(role IN ('creator', 'admin', 'moderator')),
    assigned_by INTEGER REFERENCES users(user_id),
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT                                              -- Заметки о назначении
);

CREATE INDEX IF NOT EXISTS idx_admin_roles_user ON admin_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_admin_roles_role ON admin_roles(role);

-- 2.2 Логи действий админов (расширенные)
CREATE TABLE IF NOT EXISTS admin_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL REFERENCES users(user_id),
    admin_role VARCHAR(20),                                 -- Роль на момент действия
    action_type VARCHAR(50) NOT NULL,                       -- Тип действия
    target_user_id INTEGER REFERENCES users(user_id),       -- Цель (игрок)
    target_entity VARCHAR(100),                             -- ID предмета/растения/ачивки
    entity_type VARCHAR(30),                                -- Тип сущности: user/plant/achievement/promo/etc
    old_value TEXT,                                         -- JSON: старое значение
    new_value TEXT,                                         -- JSON: новое значение
    reason TEXT,                                            -- Причина
    details TEXT,                                           -- JSON: доп. данные
    ip_address VARCHAR(45),                                 -- IP адрес (если доступно)
    user_agent TEXT,                                        -- User-Agent
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_admin_logs_admin ON admin_logs(admin_id, created_at);
CREATE INDEX IF NOT EXISTS idx_admin_logs_action ON admin_logs(action_type, created_at);
CREATE INDEX IF NOT EXISTS idx_admin_logs_target ON admin_logs(target_user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_admin_logs_date ON admin_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_admin_logs_entity ON admin_logs(entity_type, target_entity);

-- ============================================================
-- 3. ТАБЛИЦЫ РАСТЕНИЙ И ЭКОНОМИКИ
-- ============================================================

-- 3.1 Справочник растений
CREATE TABLE IF NOT EXISTS plants_directory (
    plant_id VARCHAR(50) PRIMARY KEY,                       -- Уникальный код (potato)
    name VARCHAR(100) NOT NULL,                             -- Название (Картошка)
    name_en VARCHAR(100),                                   -- Название на английском
    description TEXT,                                       -- Описание
    emoji VARCHAR(10) DEFAULT '🌱',                        -- Эмодзи (🥔)
    
    -- Характеристики роста
    grow_time INTEGER NOT NULL,                             -- Время роста в секундах
    grow_time_min INTEGER,                                  -- Мин. время (с удобрениями)
    
    -- Экономика
    seed_price INTEGER DEFAULT 0,                           -- Цена семян
    sell_price INTEGER DEFAULT 0,                           -- Цена продажи урожая
    yield_amount INTEGER DEFAULT 1,                         -- Урожай с грядки
    
    -- Требования
    required_level INTEGER DEFAULT 1,                       -- Требуемый уровень игрока
    required_prestige INTEGER DEFAULT 0,                    -- Требуемый престиж
    
    -- Награды
    exp_reward INTEGER DEFAULT 10,                          -- Опыт за сбор
    coins_reward INTEGER DEFAULT 0,                         -- Доп. монеты за сбор
    
    -- Категоризация
    category VARCHAR(30) DEFAULT 'regular',                 -- regular/seasonal/event
    season VARCHAR(20),                                     -- summer/autumn/winter/spring
    rarity VARCHAR(20) DEFAULT 'common',                    -- common/rare/epic/legendary
    
    -- Настройки
    is_active BOOLEAN DEFAULT TRUE,                         -- Активно ли
    is_sellable BOOLEAN DEFAULT TRUE,                       -- Можно ли продавать
    is_tradable BOOLEAN DEFAULT TRUE,                       -- Можно ли торговать
    sort_order INTEGER DEFAULT 0,                           -- Порядок сортировки
    
    -- Soft delete
    deleted_at TIMESTAMP,                                   -- Для soft delete
    
    -- Аудит
    created_by INTEGER REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by INTEGER REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_plants_category ON plants_directory(category, is_active);
CREATE INDEX IF NOT EXISTS idx_plants_season ON plants_directory(season, is_active);
CREATE INDEX IF NOT EXISTS idx_plants_level ON plants_directory(required_level, is_active);
CREATE INDEX IF NOT EXISTS idx_plants_rarity ON plants_directory(rarity, is_active);
CREATE INDEX IF NOT EXISTS idx_plants_active ON plants_directory(is_active, sort_order);

-- 3.2 Настройки экономики (key-value хранилище)
CREATE TABLE IF NOT EXISTS economy_settings (
    key VARCHAR(50) PRIMARY KEY,                            -- Ключ настройки
    value TEXT NOT NULL,                                    -- Значение
    value_type VARCHAR(20) DEFAULT 'string',                -- string/int/float/bool/json
    description VARCHAR(200),                               -- Описание
    category VARCHAR(30) DEFAULT 'general',                 -- general/market/balance/events
    
    -- Аудит
    updated_by INTEGER REFERENCES users(user_id),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Начальные настройки экономики
INSERT OR IGNORE INTO economy_settings (key, value, value_type, description, category) VALUES
('tax_rate', '0.05', 'float', 'Налог на продажу урожая', 'market'),
('market_fluctuation', '0.1', 'float', 'Максимальное колебание цен на рынке', 'market'),
('min_price_multiplier', '0.5', 'float', 'Минимальный множитель цены', 'market'),
('max_price_multiplier', '2.0', 'float', 'Максимальный множитель цены', 'market'),
('new_player_bonus', '100', 'int', 'Стартовый бонус нового игрока', 'general'),
('referral_bonus', '50', 'int', 'Бонус за приглашение друга', 'general'),
('maintenance_mode', 'false', 'bool', 'Режим обслуживания', 'general'),
('event_multiplier', '1.0', 'float', 'Текущий множитель события', 'events'),
('season', 'summer', 'string', 'Текущий сезон', 'general');

-- 3.3 Магазин (ассортимент)
CREATE TABLE IF NOT EXISTS shop_items (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_type VARCHAR(20) NOT NULL CHECK(item_type IN ('seed', 'boost', 'decor', 'tool', 'special')),  -- Тип товара
    
    -- Связь с растением (для семян)
    plant_id VARCHAR(50) REFERENCES plants_directory(plant_id),
    
    -- Цены
    price_coins INTEGER DEFAULT 0,                          -- Цена в монетах
    price_gems INTEGER DEFAULT 0,                           -- Цена в кристаллах
    
    -- Требования
    required_level INTEGER DEFAULT 1,
    required_prestige INTEGER DEFAULT 0,
    required_achievement VARCHAR(50),                       -- Требуемая ачивка для покупки
    
    -- Лимиты
    is_limited BOOLEAN DEFAULT FALSE,                       -- Ограниченный товар
    limit_total INTEGER,                                    -- Общий лимит (NULL = безлимит)
    limit_per_user INTEGER,                                 -- Лимит на игрока
    sold_count INTEGER DEFAULT 0,                           -- Сколько продано
    
    -- Статус
    in_shop BOOLEAN DEFAULT TRUE,                           -- В продаже ли
    featured BOOLEAN DEFAULT FALSE,                         -- Рекомендуемый товар
    discount_percent INTEGER DEFAULT 0,                     -- Скидка %
    
    -- Аудит
    added_by INTEGER REFERENCES users(user_id),
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    removed_at TIMESTAMP,                                   -- Когда убрали из магазина
    
    -- Период доступности
    available_from TIMESTAMP,
    available_until TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_shop_type ON shop_items(item_type, in_shop);
CREATE INDEX IF NOT EXISTS idx_shop_plant ON shop_items(plant_id);
CREATE INDEX IF NOT EXISTS idx_shop_level ON shop_items(required_level, in_shop);
CREATE INDEX IF NOT EXISTS idx_shop_featured ON shop_items(featured, in_shop);

-- ============================================================
-- 4. ТАБЛИЦЫ ИГРОВОГО ПРОЦЕССА
-- ============================================================

-- 4.1 Инвентарь игроков
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    item_type VARCHAR(20) DEFAULT 'seed' CHECK(item_type IN ('seed', 'harvest', 'tool', 'boost', 'special')),  -- Тип предмета
    plant_id VARCHAR(50) REFERENCES plants_directory(plant_id),
    item_code VARCHAR(50),                                  -- Код предмета (если не растение)
    quantity INTEGER DEFAULT 0 NOT NULL CHECK(quantity >= 0),
    
    -- Дополнительные характеристики предметов
    quality INTEGER DEFAULT 1 CHECK(quality BETWEEN 1 AND 5),  -- Качество 1-5
    durability INTEGER,                                     -- Прочность (для инструментов)
    metadata TEXT,                                          -- JSON с доп. данными
    
    -- Аудит
    acquired_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(user_id, item_type, plant_id, item_code)
);

CREATE INDEX IF NOT EXISTS idx_inventory_user ON inventory(user_id);
CREATE INDEX IF NOT EXISTS idx_inventory_plant ON inventory(plant_id);
CREATE INDEX IF NOT EXISTS idx_inventory_type ON inventory(user_id, item_type);

-- 4.2 Грядки игроков
CREATE TABLE IF NOT EXISTS farming_plots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    plot_number INTEGER NOT NULL,                           -- Номер грядки (1-12)
    
    -- Состояние
    status VARCHAR(20) DEFAULT 'empty' CHECK(status IN ('empty', 'growing', 'ready', 'withered')),
    
    -- Что посажено
    plant_id VARCHAR(50) REFERENCES plants_directory(plant_id),
    
    -- Время
    planted_at TIMESTAMP,                                   -- Когда посажено
    ready_at TIMESTAMP,                                     -- Когда созреет
    harvested_at TIMESTAMP,                                 -- Когда собрано
    withered_at TIMESTAMP,                                  -- Когда завяло
    
    -- Уход
    water_count INTEGER DEFAULT 0,                          -- Сколько раз полито
    last_watered_at TIMESTAMP,                              -- Когда последний раз поливали
    fertilized BOOLEAN DEFAULT FALSE,                       -- Удобрено ли
    fertilized_at TIMESTAMP,                                -- Когда удобряли
    boosted BOOLEAN DEFAULT FALSE,                          -- Ускорено ли
    boost_multiplier DECIMAL(3,2) DEFAULT 1.0,             -- Множитель ускорения
    
    -- Награды (запоминаем что было посажено)
    expected_yield INTEGER DEFAULT 0,                       -- Ожидаемый урожай
    expected_exp INTEGER DEFAULT 0,                         -- Ожидаемый опыт
    
    -- Уникальность грядки для пользователя
    UNIQUE(user_id, plot_number)
);

CREATE INDEX IF NOT EXISTS idx_plots_user ON farming_plots(user_id);
CREATE INDEX IF NOT EXISTS idx_plots_status ON farming_plots(user_id, status);
CREATE INDEX IF NOT EXISTS idx_plots_ready ON farming_plots(status, ready_at);
CREATE INDEX IF NOT EXISTS idx_plots_plant ON farming_plots(plant_id);

-- 4.3 Транзакции (история операций)
CREATE TABLE IF NOT EXISTS transactions (
    tx_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    -- Тип операции
    type VARCHAR(30) NOT NULL CHECK(type IN ('earn', 'spend', 'purchase', 'sell', 'gift', 'admin', 'promo', 'refund')),
    
    -- Валюта
    currency VARCHAR(10) NOT NULL CHECK(currency IN ('coins', 'gems')),
    amount BIGINT NOT NULL,                                 -- Сумма (положительная для earn, отрицательная для spend)
    
    -- Баланс после операции
    balance_after BIGINT NOT NULL,
    
    -- Источник
    source VARCHAR(50),                                     -- harvest/bonus/admin/promo/shop/player
    source_id VARCHAR(100),                                 -- ID источника (например, ID админа)
    source_details TEXT,                                    -- JSON с деталями
    
    -- Описание
    description TEXT,
    
    -- Связанные сущности
    related_user_id INTEGER REFERENCES users(user_id),      -- Для переводов между игроками
    item_id VARCHAR(50),                                    -- ID предмета (для покупок/продаж)
    item_quantity INTEGER,                                  -- Количество предметов
    
    -- Аудит
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45)
);

CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(type, created_at);
CREATE INDEX IF NOT EXISTS idx_transactions_source ON transactions(source, created_at);
CREATE INDEX IF NOT EXISTS idx_transactions_currency ON transactions(user_id, currency, created_at);

-- ============================================================
-- 5. ТАБЛИЦЫ ПРОМО-АКЦИЙ
-- ============================================================

-- 5.1 Промо-коды (расширенная версия)
CREATE TABLE IF NOT EXISTS promocodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(50) UNIQUE NOT NULL,                       -- Код промо
    
    -- Тип промо
    promo_type VARCHAR(20) NOT NULL CHECK(promo_type IN ('time', 'count', 'personal')),
    
    -- Награда (JSON для гибкости)
    reward_type VARCHAR(20) NOT NULL CHECK(reward_type IN ('coins', 'gems', 'item', 'mixed', 'multiplier')),
    reward_value INTEGER DEFAULT 0,                         -- Количество
    reward_item VARCHAR(50),                                -- ID предмета (если item)
    reward_item_qty INTEGER DEFAULT 1,                      -- Количество предметов
    reward_multiplier DECIMAL(3,2) DEFAULT 1.0,            -- Множитель (если тип multiplier)
    reward_json TEXT,                                       -- JSON для сложных наград
    
    -- Лимиты
    max_uses INTEGER,                                       -- Макс. активаций (NULL = безлимит)
    used_count INTEGER DEFAULT 0,                           -- Сколько активировано
    per_user_limit INTEGER DEFAULT 1,                       -- Лимит на игрока
    
    -- Срок действия
    start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_date TIMESTAMP,                                     -- NULL = бессрочно
    
    -- Ограничения по уровню
    min_level INTEGER DEFAULT 1,
    min_prestige INTEGER DEFAULT 0,
    
    -- Статус
    is_active BOOLEAN DEFAULT TRUE,
    is_vip_only BOOLEAN DEFAULT FALSE,                      -- Только для VIP
    
    -- Аудит
    created_by INTEGER REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by INTEGER REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_promocodes_code ON promocodes(code);
CREATE INDEX IF NOT EXISTS idx_promocodes_active ON promocodes(is_active, end_date);
CREATE INDEX IF NOT EXISTS idx_promocodes_type ON promocodes(promo_type, is_active);

-- 5.2 Активации промо-кодов
CREATE TABLE IF NOT EXISTS promo_activations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    promo_id INTEGER NOT NULL REFERENCES promocodes(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    -- Данные активации
    activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reward_received TEXT,                                   -- JSON с полученной наградой
    
    -- Контекст
    user_level INTEGER,                                     -- Уровень игрока на момент активации
    user_prestige INTEGER,                                  -- Престиг на момент активации
    ip_address VARCHAR(45),
    
    UNIQUE(promo_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_promo_activations_promo ON promo_activations(promo_id);
CREATE INDEX IF NOT EXISTS idx_promo_activations_user ON promo_activations(user_id);
CREATE INDEX IF NOT EXISTS idx_promo_activations_date ON promo_activations(activated_at);

-- ============================================================
-- 6. ТАБЛИЦЫ ЕЖЕДНЕВНОГО БОНУСА
-- ============================================================

-- 6.1 Настройки бонуса (конфигурация наград)
CREATE TABLE IF NOT EXISTS daily_bonus_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day_number INTEGER UNIQUE NOT NULL CHECK(day_number BETWEEN 1 AND 30),
    
    -- Награды
    coins INTEGER DEFAULT 0,
    gems INTEGER DEFAULT 0,
    
    -- Предмет
    item_type VARCHAR(20) DEFAULT 'seed',
    item_id VARCHAR(50) REFERENCES plants_directory(plant_id),
    item_quantity INTEGER DEFAULT 0,
    
    -- Особый день
    is_special BOOLEAN DEFAULT FALSE,
    special_message TEXT,
    
    -- Бонусы
    exp_bonus INTEGER DEFAULT 0,
    multiplier DECIMAL(3,2) DEFAULT 1.0,                   -- Множитель наград
    
    -- Визуал
    icon VARCHAR(10) DEFAULT '📅',
    background_color VARCHAR(7),                            -- HEX цвет
    
    -- Активность
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Аудит
    updated_by INTEGER REFERENCES users(user_id),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6.2 Получения бонуса (история)
CREATE TABLE IF NOT EXISTS daily_bonus_claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    -- Данные получения
    claim_date DATE NOT NULL,
    day_claimed INTEGER NOT NULL,                           -- Какой день стрика (1-30)
    current_streak INTEGER NOT NULL,                        -- Текущий стрик
    
    -- Награда
    coins_received INTEGER DEFAULT 0,
    gems_received INTEGER DEFAULT 0,
    items_received TEXT,                                    -- JSON с предметами
    
    -- Статус
    was_missed BOOLEAN DEFAULT FALSE,                       -- Пропущен ли (не заходил)
    streak_broken BOOLEAN DEFAULT FALSE,                    -- Обрыв стрика
    streak_restored BOOLEAN DEFAULT FALSE,                  -- Восстановлен ли стрик (через кристаллы)
    
    -- Контекст
    ip_address VARCHAR(45),
    
    UNIQUE(user_id, claim_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_claims_user ON daily_bonus_claims(user_id);
CREATE INDEX IF NOT EXISTS idx_daily_claims_date ON daily_bonus_claims(claim_date);
CREATE INDEX IF NOT EXISTS idx_daily_claims_streak ON daily_bonus_claims(user_id, current_streak);

-- ============================================================
-- 7. ТАБЛИЦЫ АЧИВОК (ДОСТИЖЕНИЙ)
-- ============================================================

-- 7.1 Категории ачивок
CREATE TABLE IF NOT EXISTS achievement_categories (
    category_id VARCHAR(30) PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    name_en VARCHAR(50),
    icon VARCHAR(10) DEFAULT '🏆',
    description VARCHAR(200),
    description_en VARCHAR(200),
    color VARCHAR(7) DEFAULT '#FFD700',                    -- HEX цвет категории
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE
);

-- 7.2 Справочник ачивок
CREATE TABLE IF NOT EXISTS achievements_directory (
    achievement_id VARCHAR(50) PRIMARY KEY,                 -- Уникальный код
    category_id VARCHAR(30) NOT NULL REFERENCES achievement_categories(category_id),
    
    -- Основная информация
    name VARCHAR(100) NOT NULL,
    name_en VARCHAR(100),
    description TEXT NOT NULL,
    description_en TEXT,
    icon VARCHAR(10) DEFAULT '🏆',
    
    -- Тип и уровень
    tier INTEGER DEFAULT 1,                                 -- Уровень (для многоуровневых)
    parent_id VARCHAR(50) REFERENCES achievements_directory(achievement_id),  -- Родительская ачивка
    achievement_type VARCHAR(20) DEFAULT 'regular' CHECK(achievement_type IN ('regular', 'multi', 'secret', 'event', 'seasonal')),
    
    -- Цель
    goal_type VARCHAR(30) NOT NULL,                         -- harvest/plant/earn/spend/prestige/streak/etc
    goal_value BIGINT NOT NULL,                             -- Значение цели
    goal_item VARCHAR(50),                                  -- Конкретный предмет (если нужно)
    
    -- Награда
    reward_coins INTEGER DEFAULT 0,
    reward_gems INTEGER DEFAULT 0,
    reward_exp INTEGER DEFAULT 0,
    reward_item_type VARCHAR(20),
    reward_item_id VARCHAR(50),
    reward_item_qty INTEGER DEFAULT 0,
    reward_title VARCHAR(50),                               -- Титул за ачивку
    reward_multiplier DECIMAL(3,2) DEFAULT 0,              -- Бонус к множителю
    
    -- Ограничения
    is_secret BOOLEAN DEFAULT FALSE,                        -- Секретная (скрыта до выполнения)
    is_event BOOLEAN DEFAULT FALSE,                         -- Ивентовая
    event_end_date TIMESTAMP,                               -- Для ивентовых
    min_level INTEGER DEFAULT 1,
    
    -- Настройки
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    
    -- Статистика (денормализация)
    times_achieved INTEGER DEFAULT 0,                       -- Сколько раз получена
    
    -- Аудит
    created_by INTEGER REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by INTEGER REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_achievements_category ON achievements_directory(category_id, is_active);
CREATE INDEX IF NOT EXISTS idx_achievements_goal ON achievements_directory(goal_type, is_active);
CREATE INDEX IF NOT EXISTS idx_achievements_type ON achievements_directory(achievement_type, is_active);
CREATE INDEX IF NOT EXISTS idx_achievements_parent ON achievements_directory(parent_id);
CREATE INDEX IF NOT EXISTS idx_achievements_active ON achievements_directory(is_active, sort_order);

-- 7.3 Прогресс игроков по ачивкам
CREATE TABLE IF NOT EXISTS player_achievements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    achievement_id VARCHAR(50) NOT NULL REFERENCES achievements_directory(achievement_id) ON DELETE CASCADE,
    
    -- Прогресс
    current_value BIGINT DEFAULT 0,
    target_value BIGINT,                                    -- Денормализация для быстрого доступа
    progress_percent INTEGER DEFAULT 0,                     -- Процент выполнения (0-100)
    
    -- Статус
    is_completed BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMP,
    
    -- Награда
    reward_claimed BOOLEAN DEFAULT FALSE,
    reward_claimed_at TIMESTAMP,
    rewards_received TEXT,                                  -- JSON с полученными наградами
    
    -- Уведомления
    notification_sent BOOLEAN DEFAULT FALSE,                -- Отправлено ли уведомление
    notification_sent_at TIMESTAMP,
    
    -- Аудит
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,         -- Когда начал выполнять
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(user_id, achievement_id)
);

CREATE INDEX IF NOT EXISTS idx_player_achievements_user ON player_achievements(user_id);
CREATE INDEX IF NOT EXISTS idx_player_achievements_achievement ON player_achievements(achievement_id);
CREATE INDEX IF NOT EXISTS idx_player_achievements_completed ON player_achievements(user_id, is_completed);
CREATE INDEX IF NOT EXISTS idx_player_achievements_claimed ON player_achievements(is_completed, reward_claimed);

-- 7.4 Логи прогресса ачивок (детальная история)
CREATE TABLE IF NOT EXISTS achievement_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    achievement_id VARCHAR(50) NOT NULL REFERENCES achievements_directory(achievement_id),
    
    -- Действие
    action VARCHAR(30) NOT NULL CHECK(action IN ('progress', 'completed', 'reward_claimed', 'reset')),
    old_value BIGINT,
    new_value BIGINT,
    delta BIGINT,                                           -- Изменение
    
    -- Контекст
    source VARCHAR(50),                                     -- Что вызвало изменение
    source_id VARCHAR(100),
    details TEXT,                                           -- JSON
    
    -- Время
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_achievement_logs_user ON achievement_logs(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_achievement_logs_achievement ON achievement_logs(achievement_id);

-- ============================================================
-- 8. ТАБЛИЦЫ ЛОГИРОВАНИЯ (ПОЛНАЯ СИСТЕМА)
-- ============================================================

-- 8.1 Основные логи (универсальная таблица)
CREATE TABLE IF NOT EXISTS logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Классификация
    log_group VARCHAR(50) NOT NULL CHECK(log_group IN ('admin', 'economy', 'gameplay', 'system', 'security', 'achievements', 'promo', 'social')),
    log_level VARCHAR(20) NOT NULL DEFAULT 'INFO' CHECK(log_level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')),
    
    -- Кто совершил
    user_id INTEGER REFERENCES users(user_id),
    username VARCHAR(100),                                  -- Денормализация
    
    -- Действие
    action VARCHAR(100) NOT NULL,
    
    -- Цель
    target_id INTEGER,                                      -- ID цели
    target_type VARCHAR(50),                                -- Тип цели: user/plant/achievement/promo/etc
    target_name VARCHAR(100),                               -- Имя/название цели (денормализация)
    
    -- Контекст
    details TEXT,                                           -- JSON с деталями
    old_state TEXT,                                         -- JSON: старое состояние
    new_state TEXT,                                         -- JSON: новое состояние
    
    -- Технические данные
    ip_address VARCHAR(45),
    session_id VARCHAR(100),
    user_agent TEXT,
    
    -- Время
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_logs_group_date ON logs(log_group, created_at);
CREATE INDEX IF NOT EXISTS idx_logs_user_date ON logs(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_logs_action ON logs(action, created_at);
CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(log_level, created_at);
CREATE INDEX IF NOT EXISTS idx_logs_target ON logs(target_type, target_id);

-- 8.2 Экономические логи (оптимизированная таблица)
CREATE TABLE IF NOT EXISTS economy_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    operation_type VARCHAR(30) NOT NULL CHECK(operation_type IN ('earn', 'spend', 'purchase', 'sell', 'gift', 'trade', 'admin')),
    
    -- Что изменилось
    currency_type VARCHAR(20) NOT NULL CHECK(currency_type IN ('coins', 'gems', 'item')),
    amount BIGINT NOT NULL,
    item_id VARCHAR(50),
    item_quantity INTEGER,
    
    -- Результат
    balance_after BIGINT,
    inventory_after TEXT,                                   -- JSON состояния инвентаря
    
    -- Источник
    source VARCHAR(50) NOT NULL,
    source_id VARCHAR(100),
    source_details TEXT,
    
    -- Описание
    description TEXT,
    
    -- Время
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_economy_user ON economy_logs(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_economy_operation ON economy_logs(operation_type, created_at);
CREATE INDEX IF NOT EXISTS idx_economy_source ON economy_logs(source, created_at);
CREATE INDEX IF NOT EXISTS idx_economy_currency ON economy_logs(user_id, currency_type, created_at);

-- 8.3 Логи безопасности
CREATE TABLE IF NOT EXISTS security_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    event_type VARCHAR(30) NOT NULL CHECK(event_type IN ('login', 'logout', 'ban', 'unban', 'suspicious', 'failed_action', 'permission_denied')),
    
    -- Участники
    user_id INTEGER REFERENCES users(user_id),
    admin_id INTEGER REFERENCES users(user_id),
    
    -- Автоматика
    is_automated BOOLEAN DEFAULT FALSE,
    
    -- Данные бана
    ban_reason TEXT,
    ban_duration INTEGER,                                   -- Часы
    ban_expires TIMESTAMP,
    
    -- Технические данные
    ip_address VARCHAR(45),
    user_agent TEXT,
    device_fingerprint VARCHAR(100),
    
    -- Контекст
    details TEXT,
    risk_score INTEGER,                                     -- Оценка риска (0-100)
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_security_user ON security_logs(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_security_event ON security_logs(event_type, created_at);
CREATE INDEX IF NOT EXISTS idx_security_admin ON security_logs(admin_id, created_at);
CREATE INDEX IF NOT EXISTS idx_security_ip ON security_logs(ip_address);

-- 8.4 Логи промо-акций
CREATE TABLE IF NOT EXISTS promo_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    promo_id INTEGER REFERENCES promocodes(id),
    promo_code VARCHAR(50) NOT NULL,
    
    -- Кто
    user_id INTEGER REFERENCES users(user_id),
    admin_id INTEGER REFERENCES users(user_id),
    
    -- Действие
    action VARCHAR(30) NOT NULL CHECK(action IN ('create', 'activate', 'deactivate', 'expire', 'update')),
    
    -- Результат
    success BOOLEAN DEFAULT TRUE,
    error_reason TEXT,
    reward_given TEXT,                                      -- JSON
    
    -- Контекст
    user_level INTEGER,
    user_prestige INTEGER,
    ip_address VARCHAR(45),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_promo_logs_code ON promo_logs(promo_code);
CREATE INDEX IF NOT EXISTS idx_promo_logs_user ON promo_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_promo_logs_action ON promo_logs(action);

-- ============================================================
-- 9. СОЦИАЛЬНЫЕ ТАБЛИЦЫ
-- ============================================================

-- 9.1 Соседи (друзья)
CREATE TABLE IF NOT EXISTS neighbors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    neighbor_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    -- Статус дружбы
    status VARCHAR(20) DEFAULT 'active' CHECK(status IN ('pending', 'active', 'blocked')),
    
    -- Взаимодействие
    helped_at TIMESTAMP,                                    -- Когда последний раз помог
    helped_count INTEGER DEFAULT 0,                         -- Сколько раз помог
    stolen_from_count INTEGER DEFAULT 0,                    -- Сколько раз украл урожай (шалость)
    
    -- Статистика
    gifts_sent INTEGER DEFAULT 0,
    gifts_received INTEGER DEFAULT 0,
    
    -- Даты
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    accepted_at TIMESTAMP,
    
    UNIQUE(user_id, neighbor_id)
);

CREATE INDEX IF NOT EXISTS idx_neighbors_user ON neighbors(user_id, status);
CREATE INDEX IF NOT EXISTS idx_neighbors_neighbor ON neighbors(neighbor_id);

-- 9.2 Рейтинги (кэшированные)
CREATE TABLE IF NOT EXISTS leaderboards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    leaderboard_type VARCHAR(30) NOT NULL CHECK(leaderboard_type IN ('balance', 'harvest', 'prestige', 'exp', 'achievements')),
    period VARCHAR(20) NOT NULL CHECK(period IN ('daily', 'weekly', 'monthly', 'alltime')),
    
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    rank INTEGER NOT NULL,                                  -- Место в рейтинге
    value BIGINT NOT NULL,                                  -- Значение для сортировки
    previous_rank INTEGER,                                  -- Предыдущее место (для отслеживания роста/падения)
    
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(leaderboard_type, period, user_id)
);

CREATE INDEX IF NOT EXISTS idx_leaderboards_type ON leaderboards(leaderboard_type, period, rank);
CREATE INDEX IF NOT EXISTS idx_leaderboards_user ON leaderboards(user_id);

-- 9.3 Подарки между игроками
CREATE TABLE IF NOT EXISTS gifts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    from_user_id INTEGER NOT NULL REFERENCES users(user_id),
    to_user_id INTEGER NOT NULL REFERENCES users(user_id),
    
    -- Содержимое
    gift_type VARCHAR(20) NOT NULL CHECK(gift_type IN ('coins', 'gems', 'item', 'boost')),
    amount INTEGER,
    item_id VARCHAR(50),
    item_quantity INTEGER,
    
    -- Сообщение
    message TEXT,
    
    -- Статус
    status VARCHAR(20) DEFAULT 'pending' CHECK(status IN ('pending', 'accepted', 'declined', 'expired')),
    
    -- Даты
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    accepted_at TIMESTAMP,
    
    -- Ограничения
    is_anonymous BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_gifts_from ON gifts(from_user_id, status);
CREATE INDEX IF NOT EXISTS idx_gifts_to ON gifts(to_user_id, status);

-- ============================================================
-- 10. ДОПОЛНИТЕЛЬНЫЕ ТАБЛИЦЫ
-- ============================================================

-- 10.1 Уведомления
CREATE TABLE IF NOT EXISTS notifications (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    type VARCHAR(30) NOT NULL CHECK(type IN ('harvest_ready', 'daily_bonus', 'achievement', 'gift', 'neighbor_help', 'promo', 'system')),
    
    -- Содержимое
    title VARCHAR(100),
    message TEXT NOT NULL,
    icon VARCHAR(10) DEFAULT '🔔',
    
    -- Действие при клике
    action_type VARCHAR(30),
    action_data TEXT,                                       -- JSON
    
    -- Статус
    is_read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMP,
    sent BOOLEAN DEFAULT FALSE,
    sent_at TIMESTAMP,
    
    -- Срок
    expires_at TIMESTAMP,
    priority INTEGER DEFAULT 0,                             -- 0-10, чем выше - тем важнее
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read, created_at);
CREATE INDEX IF NOT EXISTS idx_notifications_sent ON notifications(sent, created_at);

-- 10.2 Квесты (задания)
CREATE TABLE IF NOT EXISTS quests (
    quest_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Тип квеста
    quest_type VARCHAR(30) NOT NULL CHECK(quest_type IN ('daily', 'weekly', 'event', 'tutorial')),
    
    -- Цель
    target_type VARCHAR(30) NOT NULL,                       -- harvest/plant/earn/etc
    target_item VARCHAR(50),                                -- Конкретный предмет
    target_count INTEGER NOT NULL,
    
    -- Описание
    title VARCHAR(100) NOT NULL,
    description TEXT,
    
    -- Награда
    reward_coins INTEGER DEFAULT 0,
    reward_gems INTEGER DEFAULT 0,
    reward_exp INTEGER DEFAULT 0,
    reward_items TEXT,                                      -- JSON
    
    -- Ограничения
    required_level INTEGER DEFAULT 1,
    required_prestige INTEGER DEFAULT 0,
    
    -- Сроки
    start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_date TIMESTAMP,
    
    -- Статус
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Статистика
    completions_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 10.3 Прогресс квестов игроков
CREATE TABLE IF NOT EXISTS player_quests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    quest_id INTEGER NOT NULL REFERENCES quests(quest_id) ON DELETE CASCADE,
    
    -- Прогресс
    progress INTEGER DEFAULT 0,
    is_completed BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMP,
    
    -- Награда
    reward_claimed BOOLEAN DEFAULT FALSE,
    claimed_at TIMESTAMP,
    
    -- Дата назначения (для ежедневных)
    assigned_date DATE DEFAULT CURRENT_DATE,
    
    UNIQUE(user_id, quest_id, assigned_date)
);

CREATE INDEX IF NOT EXISTS idx_player_quests_user ON player_quests(user_id, is_completed);

-- 10.4 Сезонные события
CREATE TABLE IF NOT EXISTS seasonal_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Информация
    name VARCHAR(100) NOT NULL,
    description TEXT,
    event_type VARCHAR(30) CHECK(event_type IN ('season', 'holiday', 'special')),
    season VARCHAR(20),                                     -- summer/autumn/winter/spring
    
    -- Сроки
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    
    -- Настройки
    multiplier DECIMAL(3,2) DEFAULT 1.0,                   -- Множитель наград
    special_plant_id VARCHAR(50) REFERENCES plants_directory(plant_id),
    
    -- Статус
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Таблица лидеров
    has_leaderboard BOOLEAN DEFAULT FALSE,
    
    created_by INTEGER REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 10.5 Участники событий
CREATE TABLE IF NOT EXISTS event_participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    event_id INTEGER NOT NULL REFERENCES seasonal_events(event_id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    -- Статистика
    score BIGINT DEFAULT 0,
    rank INTEGER,
    
    -- Прогресс
    actions_count INTEGER DEFAULT 0,
    
    -- Награды
    rewards_claimed TEXT,                                   -- JSON
    
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(event_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_event_participants_event ON event_participants(event_id, score DESC);
CREATE INDEX IF NOT EXISTS idx_event_participants_user ON event_participants(user_id);

-- ============================================================
-- 11. ПРЕДСТАВЛЕНИЯ (VIEWS) ДЛЯ УДОБСТВА
-- ============================================================

-- 11.1 Сводка по пользователю
CREATE VIEW IF NOT EXISTS v_user_summary AS
SELECT 
    u.*,
    (SELECT COUNT(*) FROM player_achievements WHERE user_id = u.user_id AND is_completed = 1) as achievements_count,
    (SELECT COUNT(*) FROM farming_plots WHERE user_id = u.user_id AND status = 'ready') as ready_plots,
    (SELECT SUM(quantity) FROM inventory WHERE user_id = u.user_id) as total_items,
    (SELECT COUNT(*) FROM neighbors WHERE user_id = u.user_id AND status = 'active') as neighbors_count,
    (SELECT MAX(current_streak) FROM daily_bonus_claims WHERE user_id = u.user_id) as max_streak
FROM users u;

-- 11.2 Активные промокоды
CREATE VIEW IF NOT EXISTS v_active_promocodes AS
SELECT *
FROM promocodes
WHERE is_active = 1
AND (end_date IS NULL OR end_date > datetime('now'))
AND (max_uses IS NULL OR used_count < max_uses);

-- 11.3 Достижения игрока с деталями
CREATE VIEW IF NOT EXISTS v_player_achievements_detailed AS
SELECT 
    pa.*,
    ad.name as achievement_name,
    ad.icon,
    ad.category_id,
    ac.name as category_name,
    ac.icon as category_icon,
    ad.goal_type,
    ad.goal_value,
    ad.reward_coins,
    ad.reward_gems,
    ad.is_secret
FROM player_achievements pa
JOIN achievements_directory ad ON pa.achievement_id = ad.achievement_id
JOIN achievement_categories ac ON ad.category_id = ac.category_id;

-- ============================================================
-- 12. НАЧАЛЬНЫЕ ДАННЫЕ
-- ============================================================

-- Категории ачивок
INSERT OR IGNORE INTO achievement_categories (category_id, name, icon, description, sort_order) VALUES
('harvest', 'Сбор урожая', '🌾', 'Достижения за сбор растений', 1),
('finance', 'Финансы', '💰', 'Достижения за накопление и трату монет', 2),
('prestige', 'Престиж', '🏆', 'Достижения за повышение престижа', 3),
('activity', 'Активность', '📅', 'Достижения за ежедневные входы', 4),
('social', 'Социальные', '👥', 'Достижения за взаимодействие с соседями', 5),
('special', 'Особые', '🎯', 'Уникальные достижения', 6),
('events', 'Ивенты', '🎮', 'Временные события', 7);

-- Базовые растения
INSERT OR IGNORE INTO plants_directory (plant_id, name, emoji, grow_time, seed_price, sell_price, yield_amount, required_level, exp_reward, category, sort_order) VALUES
('corn_seed', 'Кукуруза', '🌽', 120, 10, 20, 1, 1, 5, 'regular', 1),
('carrot_seed', 'Морковь', '🥕', 300, 20, 50, 1, 1, 10, 'regular', 2),
('strawberry_seed', 'Клубника', '🍓', 900, 50, 150, 2, 3, 20, 'regular', 3),
('tomato_seed', 'Помидор', '🍅', 1800, 80, 200, 2, 5, 30, 'regular', 4),
('pumpkin_seed', 'Тыква', '🎃', 3600, 150, 400, 3, 8, 50, 'regular', 5);

-- Настройки ежедневного бонуса
INSERT OR IGNORE INTO daily_bonus_config (day_number, coins, is_special) VALUES
(1, 50, 0),
(2, 75, 0),
(3, 100, 1),
(4, 150, 0),
(5, 200, 0),
(6, 250, 0),
(7, 500, 1);

-- ============================================================
-- 13. ТРИГГЕРЫ (SQLite совместимые)
-- ============================================================

-- Автообновление updated_at для users
CREATE TRIGGER IF NOT EXISTS trg_users_updated_at
AFTER UPDATE ON users
BEGIN
    UPDATE users SET updated_at = datetime('now') WHERE user_id = NEW.user_id;
END;

-- Автообновление updated_at для inventory
CREATE TRIGGER IF NOT EXISTS trg_inventory_updated_at
AFTER UPDATE ON inventory
BEGIN
    UPDATE inventory SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- Автообновление updated_at для player_achievements
CREATE TRIGGER IF NOT EXISTS trg_player_achievements_updated_at
AFTER UPDATE ON player_achievements
BEGIN
    UPDATE player_achievements SET last_updated = datetime('now') WHERE id = NEW.id;
END;

-- Логирование банов
CREATE TRIGGER IF NOT EXISTS trg_log_ban
AFTER UPDATE OF is_banned ON users
WHEN NEW.is_banned = 1 AND OLD.is_banned = 0
BEGIN
    INSERT INTO security_logs (event_type, user_id, ban_reason, ban_expires, details)
    VALUES ('ban', NEW.user_id, NEW.ban_reason, NEW.ban_until, 
            json_object('old_value', OLD.is_banned, 'new_value', NEW.is_banned));
END;

-- Подсчет использований промокода
CREATE TRIGGER IF NOT EXISTS trg_promo_usage_count
AFTER INSERT ON promo_activations
BEGIN
    UPDATE promocodes 
    SET used_count = used_count + 1 
    WHERE id = NEW.promo_id;
END;

-- ============================================================
-- КОНЕЦ СХЕМЫ
-- ============================================================
