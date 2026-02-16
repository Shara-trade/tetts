-- Создание всех таблиц

-- Пользователи (обновленная)
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    balance INTEGER DEFAULT 100,
    prestige_level INTEGER DEFAULT 0,
    prestige_multiplier REAL DEFAULT 1.0,
    city_level INTEGER DEFAULT 0,
    total_harvested INTEGER DEFAULT 0,
    total_planted INTEGER DEFAULT 0,
    total_earned INTEGER DEFAULT 0,
    joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_banned INTEGER DEFAULT 0,
    ban_reason TEXT,
    ban_until TIMESTAMP
);

-- Роли администраторов
CREATE TABLE IF NOT EXISTS admin_roles (
    user_id INTEGER PRIMARY KEY,
    role TEXT CHECK(role IN ('creator', 'admin', 'moderator')),
    assigned_by INTEGER,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Грядки
CREATE TABLE IF NOT EXISTS plots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    plot_number INTEGER NOT NULL,
    status TEXT CHECK(status IN ('empty', 'growing', 'ready')) DEFAULT 'empty',
    crop_type TEXT,
    planted_time TIMESTAMP,
    growth_time_seconds INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    UNIQUE(user_id, plot_number)
);

-- Инвентарь
CREATE TABLE IF NOT EXISTS inventory (
    user_id INTEGER NOT NULL,
    item_code TEXT NOT NULL,
    quantity INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, item_code),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Магазин (обновленная)
CREATE TABLE IF NOT EXISTS shop_config (
    item_code TEXT PRIMARY KEY,
    item_name TEXT,
    item_icon TEXT,
    buy_price INTEGER,
    sell_price INTEGER,
    growth_time INTEGER,
    category TEXT,
    sort_order INTEGER DEFAULT 0,
    is_seasonal INTEGER DEFAULT 0,
    season TEXT
);

-- Промокоды
CREATE TABLE IF NOT EXISTS promocodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    reward_json TEXT NOT NULL,
    max_uses INTEGER DEFAULT 1,
    times_used INTEGER DEFAULT 0,
    valid_until TIMESTAMP,
    is_active INTEGER DEFAULT 1,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Активации промокодов
CREATE TABLE IF NOT EXISTS promo_activations (
    promo_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(promo_id, user_id),
    FOREIGN KEY (promo_id) REFERENCES promocodes(id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Ежедневные бонусы
CREATE TABLE IF NOT EXISTS daily_rewards (
    day_number INTEGER PRIMARY KEY CHECK(day_number BETWEEN 1 AND 7),
    coins INTEGER DEFAULT 0,
    items_json TEXT DEFAULT '{}'
);

-- Прогресс пользователя по ежедневным бонусам
CREATE TABLE IF NOT EXISTS user_daily (
    user_id INTEGER PRIMARY KEY,
    current_streak INTEGER DEFAULT 0,
    last_claim_date DATE,
    next_claim_date DATE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- КВЕСТЫ И ДОСТИЖЕНИЯ
CREATE TABLE IF NOT EXISTS quests (
    quest_id INTEGER PRIMARY KEY AUTOINCREMENT,
    quest_type TEXT NOT NULL,
    target_item TEXT,
    target_count INTEGER NOT NULL,
    description TEXT NOT NULL,
    reward_coins INTEGER DEFAULT 0,
    reward_items_json TEXT DEFAULT '{}',
    is_daily INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS user_quests (
    user_id INTEGER NOT NULL,
    quest_id INTEGER NOT NULL,
    progress INTEGER DEFAULT 0,
    completed INTEGER DEFAULT 0,
    claimed INTEGER DEFAULT 0,
    assigned_date DATE DEFAULT CURRENT_DATE,
    PRIMARY KEY (user_id, quest_id, assigned_date),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (quest_id) REFERENCES quests(quest_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS achievements (
    achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    icon TEXT DEFAULT '🏆',
    requirement_type TEXT NOT NULL,
    requirement_count INTEGER NOT NULL,
    reward_coins INTEGER DEFAULT 0,
    reward_multiplier REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_achievements (
    user_id INTEGER NOT NULL,
    achievement_id INTEGER NOT NULL,
    unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, achievement_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (achievement_id) REFERENCES achievements(achievement_id) ON DELETE CASCADE
);

-- СЕЗОННЫЕ СОБЫТИЯ
CREATE TABLE IF NOT EXISTS seasonal_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    season TEXT NOT NULL,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    multiplier REAL DEFAULT 2.0,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS event_leaderboard (
    event_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    score INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (event_id, user_id),
    FOREIGN KEY (event_id) REFERENCES seasonal_events(event_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- УВЕДОМЛЕНИЯ
CREATE TABLE IF NOT EXISTS notifications (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sent INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- ==================== СИСТЕМА ЛОГИРОВАНИЯ ====================

-- Основная таблица логов
CREATE TABLE IF NOT EXISTS logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_group TEXT NOT NULL, -- admin/economy/gameplay/system/security/achievements/promo
    log_level TEXT NOT NULL, -- DEBUG/INFO/WARNING/ERROR/CRITICAL
    user_id INTEGER,
    username TEXT,
    action TEXT NOT NULL,
    target_id INTEGER,
    target_type TEXT,
    details TEXT, -- JSON
    ip_address TEXT,
    session_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_logs_group ON logs(log_group, created_at);
CREATE INDEX IF NOT EXISTS idx_logs_user ON logs(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_logs_action ON logs(action, created_at);
CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(log_level, created_at);
CREATE INDEX IF NOT EXISTS idx_logs_date ON logs(created_at);
CREATE INDEX IF NOT EXISTS idx_logs_target ON logs(target_id, target_type);

-- Админ-логи (все действия модераторов/админов)
CREATE TABLE IF NOT EXISTS admin_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    admin_role TEXT,
    action_type TEXT NOT NULL,
    target_user_id INTEGER,
    target_entity_id TEXT,
    old_value TEXT, -- JSON
    new_value TEXT, -- JSON
    reason TEXT,
    details TEXT, -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (admin_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_admin_logs_admin ON admin_logs(admin_id, created_at);
CREATE INDEX IF NOT EXISTS idx_admin_logs_action ON admin_logs(action_type, created_at);
CREATE INDEX IF NOT EXISTS idx_admin_logs_target ON admin_logs(target_user_id, created_at);

-- Экономические логи (движение ресурсов)
CREATE TABLE IF NOT EXISTS economy_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    operation_type TEXT NOT NULL, -- earn/spend/purchase/sell
    currency_type TEXT, -- coins/gems/item
    amount INTEGER,
    item_id TEXT,
    balance_after INTEGER,
    source TEXT, -- harvest/bonus/admin/promo/shop
    source_id TEXT,
    details TEXT, -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_economy_user ON economy_logs(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_economy_operation ON economy_logs(operation_type, created_at);
CREATE INDEX IF NOT EXISTS idx_economy_source ON economy_logs(source, created_at);

-- Логи прогресса (достижения, уровни)
CREATE TABLE IF NOT EXISTS progression_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    progression_type TEXT NOT NULL, -- level_up/prestige_up/achievement
    old_value INTEGER,
    new_value INTEGER,
    achievement_id TEXT,
    reward_claimed INTEGER DEFAULT 0,
    details TEXT, -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_progression_user ON progression_logs(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_progression_type ON progression_logs(progression_type, created_at);

-- Логи безопасности (баны, входы, подозрения)
CREATE TABLE IF NOT EXISTS security_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL, -- ban/unban/login/failed_action/suspicious
    user_id INTEGER,
    admin_id INTEGER,
    is_automated INTEGER DEFAULT 0,
    ban_reason TEXT,
    ban_duration INTEGER,
    ip_address TEXT,
    user_agent TEXT,
    details TEXT, -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (admin_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_security_user ON security_logs(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_security_event ON security_logs(event_type, created_at);
CREATE INDEX IF NOT EXISTS idx_security_admin ON security_logs(admin_id, created_at);

-- Логи ачивок (получение, прогресс)
CREATE TABLE IF NOT EXISTS achievement_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    achievement_id TEXT NOT NULL,
    achievement_name TEXT,
    category_id TEXT,
    progress_before INTEGER,
    progress_after INTEGER,
    is_completed INTEGER DEFAULT 0,
    reward_earned TEXT, -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_achievement_user ON achievement_logs(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_achievement_id ON achievement_logs(achievement_id, created_at);

-- Логи промо (активации, создания)
CREATE TABLE IF NOT EXISTS promo_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    promo_code TEXT NOT NULL,
    user_id INTEGER,
    admin_id INTEGER,
    action TEXT NOT NULL, -- create/activate/deactivate/expire
    reward_given TEXT, -- JSON
    success INTEGER DEFAULT 1,
    error_reason TEXT,
    details TEXT, -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (admin_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_promo_code ON promo_logs(promo_code, created_at);
CREATE INDEX IF NOT EXISTS idx_promo_user ON promo_logs(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_promo_action ON promo_logs(action, created_at);

-- ============================================
-- НАЧАЛЬНЫЕ ДАННЫЕ
-- ============================================

-- Администраторы (роли)
INSERT OR REPLACE INTO admin_roles (user_id, role, assigned_by) VALUES
(7852152665, 'creator', 7852152665),
(701414064, 'admin', 7852152665);

-- Магазин
INSERT OR REPLACE INTO shop_config (item_code, item_name, item_icon, buy_price, sell_price, growth_time, category, sort_order) VALUES
('corn_seed', 'Кукуруза', '🌽', 10, 20, 120, 'seed', 1),
('carrot_seed', 'Морковь', '🥕', 20, 50, 300, 'seed', 2),
('strawberry_seed', 'Клубника', '🍓', 50, 150, 900, 'seed', 3),
('tomato_seed', 'Помидор', '🍅', 80, 200, 1800, 'seed', 4),
('pumpkin_seed', 'Тыква', '🎃', 150, 400, 3600, 'seed', 5),
('fast_fertilizer', 'Быстрое удобрение', '🧪', 30, 0, 0, 'fertilizer', 1),
('super_fertilizer', 'Супер удобрение', '💣', 100, 0, 0, 'fertilizer', 2),
('new_plot', 'Новая грядка', '🚜', 200, 0, 0, 'upgrade', 1);

-- Ежедневные бонусы
INSERT OR REPLACE INTO daily_rewards (day_number, coins, items_json) VALUES
(1, 50, '{}'),
(2, 75, '{}'),
(3, 100, '{"fast_fertilizer":1}'),
(4, 150, '{}'),
(5, 200, '{"super_fertilizer":1}'),
(6, 250, '{}'),
(7, 500, '{"corn_seed":20}');

-- Ежедневные квесты
INSERT OR REPLACE INTO quests (quest_type, target_item, target_count, description, reward_coins, reward_items_json, is_daily) VALUES
('harvest', 'corn_seed', 10, 'Собери 10 кукурузы', 100, '{"fast_fertilizer":1}', 1),
('harvest', NULL, 20, 'Собери 20 любых растений', 150, '{}', 1),
('plant', NULL, 5, 'Посади 5 семян', 50, '{}', 1),
('plant', NULL, 10, 'Посади 10 семян', 100, '{"fast_fertilizer":1}', 1),
('earn', NULL, 500, 'Заработай 500 монет', 50, '{}', 1),
('earn', NULL, 1000, 'Заработай 1000 монет', 100, '{"super_fertilizer":1}', 1),
('login', NULL, 1, 'Зайди в игру сегодня', 25, '{}', 1);

-- Достижения
INSERT OR REPLACE INTO achievements (code, name, description, icon, requirement_type, requirement_count, reward_coins, reward_multiplier) VALUES
('first_harvest', 'Первый урожай', 'Собери свой первый урожай', '🌾', 'harvest', 1, 50, 0),
('harvester_10', 'Сборщик', 'Собери 10 растений', '🌾', 'harvest', 10, 100, 0),
('harvester_100', 'Опытный фермер', 'Собери 100 растений', '🚜', 'harvest', 100, 500, 0.1),
('harvester_1000', 'Фермер месяца', 'Собери 1000 растений', '👑', 'harvest', 1000, 5000, 0.5),
('rich_1000', 'Богач', 'Заработай 1000 монет', '💰', 'earn', 1000, 200, 0),
('rich_10000', 'Миллионер', 'Заработай 10000 монет', '💎', 'earn', 10000, 1000, 0.2),
('planter_50', 'Сеятель', 'Посади 50 семян', '🌱', 'plant', 50, 200, 0),
('planter_500', 'Мастер посадок', 'Посади 500 семян', '🌳', 'plant', 500, 1000, 0.1),
('prestige_1', 'Престиж I', 'Достигни 1 уровня престижа', '⭐', 'prestige', 1, 1000, 0),
('prestige_5', 'Престиж V', 'Достигни 5 уровня престижа', '🌟', 'prestige', 5, 10000, 0);

-- Сезонные семена
INSERT OR REPLACE INTO shop_config (item_code, item_name, item_icon, buy_price, sell_price, growth_time, category, sort_order, is_seasonal, season) VALUES
('sunflower_seed', 'Подсолнух (Лето)', '🌻', 200, 500, 2400, 'seed', 10, 1, 'summer'),
('watermelon_seed', 'Арбуз (Лето)', '🍉', 300, 800, 3600, 'seed', 11, 1, 'summer'),
('snowman_seed', 'Снеговик (Зима)', '☃️', 500, 1500, 7200, 'seed', 12, 1, 'winter'),
('christmas_tree_seed', 'Елка (Зима)', '🎄', 1000, 3000, 14400, 'seed', 13, 1, 'winter'); 