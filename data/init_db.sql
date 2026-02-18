-- ============================================================
-- ПОЛНАЯ СХЕМА БАЗЫ ДАННЫХ - ЛЕНИВЫЙ ФЕРМЕР v3.0
-- SQLite с поддержкой внешних ключей
-- ============================================================
-- 
-- Содержимое:
-- 1. Все таблицы БД
-- 2. Индексы для производительности
-- 3. Триггеры для автоматизации
-- 4. Представления (Views) для аналитики
-- 5. Начальные данные (настройки, магазин, ачивки)
--
-- Использование:
--   sqlite3 farm_v3.db < data/init_db.sql
--   или в Python:
--   with open('data/init_db.sql', 'r') as f:
--       cursor.executescript(f.read())
-- ============================================================

-- Включаем поддержку внешних ключей
PRAGMA foreign_keys = ON;

-- ============================================================
-- 1. ТАБЛИЦА ПОЛЬЗОВАТЕЛЕЙ (users)
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    first_name TEXT DEFAULT 'Игрок',
    username TEXT,
    balance INTEGER DEFAULT 100,
    gems INTEGER DEFAULT 0,
    prestige_level INTEGER DEFAULT 1,
    prestige_multiplier REAL DEFAULT 1.0,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    city_level INTEGER DEFAULT 1,
    total_harvested INTEGER DEFAULT 0,
    total_planted INTEGER DEFAULT 0,
    total_earned INTEGER DEFAULT 0,
    total_spent INTEGER DEFAULT 0,
    joined_date TEXT DEFAULT CURRENT_TIMESTAMP,
    last_activity TEXT DEFAULT CURRENT_TIMESTAMP,
    is_banned INTEGER DEFAULT 0,
    ban_reason TEXT,
    ban_until TEXT,
    last_daily_claim TEXT,
    daily_streak INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username) WHERE username IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_joined ON users(joined_date);
CREATE INDEX IF NOT EXISTS idx_users_last_activity ON users(last_activity);
CREATE INDEX IF NOT EXISTS idx_users_balance ON users(balance DESC);
CREATE INDEX IF NOT EXISTS idx_users_prestige ON users(prestige_level DESC);

-- ============================================================
-- 2. ТАБЛИЦА АДМИНИСТРАТОРОВ (admin_roles)
-- ============================================================
CREATE TABLE IF NOT EXISTS admin_roles (
    user_id INTEGER PRIMARY KEY,
    role TEXT NOT NULL,
    assigned_by INTEGER,
    assigned_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_by) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_admin_roles_role ON admin_roles(role);
CREATE INDEX IF NOT EXISTS idx_admin_roles_assigned_by ON admin_roles(assigned_by);

-- ============================================================
-- 3. ТАБЛИЦА ИНВЕНТАРЯ (inventory)
-- ============================================================
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    item_code TEXT NOT NULL,
    quantity INTEGER DEFAULT 1,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (item_code) REFERENCES shop_config(item_code) ON DELETE CASCADE,
    UNIQUE(user_id, item_code)
);

CREATE INDEX IF NOT EXISTS idx_inventory_user ON inventory(user_id);
CREATE INDEX IF NOT EXISTS idx_inventory_item ON inventory(item_code);

-- ============================================================
-- 4. ТАБЛИЦА МАГАЗИНА/КОНФИГУРАЦИЯ ПРЕДМЕТОВ (shop_config)
-- ============================================================
CREATE TABLE IF NOT EXISTS shop_config (
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
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,
    FOREIGN KEY (created_by) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_shop_config_category ON shop_config(category, is_active);
CREATE INDEX IF NOT EXISTS idx_shop_config_active ON shop_config(is_active, sort_order);
CREATE INDEX IF NOT EXISTS idx_shop_config_level ON shop_config(required_level);

-- ============================================================
-- 5. ТАБЛИЦА ГРЯДОК (plots)
-- ============================================================
CREATE TABLE IF NOT EXISTS plots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    plot_number INTEGER NOT NULL,
    status TEXT DEFAULT 'empty',
    crop_type TEXT,
    planted_time TEXT,
    growth_time_seconds INTEGER DEFAULT 0,
    fertilized INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (crop_type) REFERENCES shop_config(item_code),
    UNIQUE(user_id, plot_number)
);

CREATE INDEX IF NOT EXISTS idx_plots_user ON plots(user_id);
CREATE INDEX IF NOT EXISTS idx_plots_plot ON plots(user_id, plot_number);
CREATE INDEX IF NOT EXISTS idx_plots_status ON plots(user_id, status);

-- ============================================================
-- 6. ТАБЛИЦА ПРОМОКОДОВ (promocodes)
-- ============================================================
CREATE TABLE IF NOT EXISTS promocodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    reward_json TEXT NOT NULL,
    description TEXT,
    max_uses INTEGER DEFAULT 0,
    times_used INTEGER DEFAULT 0,
    valid_from TEXT DEFAULT CURRENT_TIMESTAMP,
    valid_until TEXT,
    is_active INTEGER DEFAULT 1,
    created_by INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_promocodes_valid ON promocodes(valid_until, is_active);
CREATE INDEX IF NOT EXISTS idx_promocodes_active ON promocodes(is_active);
CREATE INDEX IF NOT EXISTS idx_promocodes_code ON promocodes(code);

-- ============================================================
-- 7. ТАБЛИЦА АКТИВАЦИЙ ПРОМОКОДОВ (promo_activations)
-- ============================================================
CREATE TABLE IF NOT EXISTS promo_activations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    promo_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    activated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (promo_id) REFERENCES promocodes(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    UNIQUE(promo_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_promo_activations_promo ON promo_activations(promo_id);
CREATE INDEX IF NOT EXISTS idx_promo_activations_user ON promo_activations(user_id);
CREATE INDEX IF NOT EXISTS idx_promo_activations_date ON promo_activations(activated_at);

-- ============================================================
-- 8. ТАБЛИЦА ЛОГОВ ДЕЙСТВИЙ АДМИНОВ (admin_logs)
-- ============================================================
CREATE TABLE IF NOT EXISTS admin_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    admin_role TEXT,
    action_type TEXT NOT NULL,
    target_user_id INTEGER,
    target_entity_id TEXT,
    old_value TEXT,
    new_value TEXT,
    reason TEXT,
    details TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    ip TEXT,
    FOREIGN KEY (admin_id) REFERENCES users(user_id),
    FOREIGN KEY (target_user_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_admin_logs_admin ON admin_logs(admin_id);
CREATE INDEX IF NOT EXISTS idx_admin_logs_action ON admin_logs(action_type);
CREATE INDEX IF NOT EXISTS idx_admin_logs_target ON admin_logs(target_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_logs_date ON admin_logs(created_at);

-- ============================================================
-- 9. ТАБЛИЦА ЕЖЕДНЕВНЫХ БОНУСОВ ПОЛЬЗОВАТЕЛЕЙ (user_daily)
-- ============================================================
CREATE TABLE IF NOT EXISTS user_daily (
    user_id INTEGER PRIMARY KEY,
    current_streak INTEGER DEFAULT 0,
    last_claim_date TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_daily_claim_date ON user_daily(last_claim_date);

-- ============================================================
-- 10. ТАБЛИЦА КОНФИГУРАЦИИ ЕЖЕДНЕВНЫХ БОНУСОВ (daily_rewards)
-- ============================================================
CREATE TABLE IF NOT EXISTS daily_rewards (
    day_number INTEGER PRIMARY KEY,
    coins INTEGER DEFAULT 0,
    gems INTEGER DEFAULT 0,
    items_json TEXT
);

-- ============================================================
-- 11. ТАБЛИЦА КВЕСТОВ (quests)
-- ============================================================
CREATE TABLE IF NOT EXISTS quests (
    quest_id INTEGER PRIMARY KEY AUTOINCREMENT,
    quest_type TEXT NOT NULL,
    target_item TEXT,
    target_count INTEGER NOT NULL,
    description TEXT NOT NULL,
    reward_coins INTEGER DEFAULT 0,
    reward_items_json TEXT,
    is_daily INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_quests_type ON quests(quest_type);
CREATE INDEX IF NOT EXISTS idx_quests_daily ON quests(is_daily, is_active);

-- ============================================================
-- 12. ТАБЛИЦА ПРОГРЕССА КВЕСТОВ ПОЛЬЗОВАТЕЛЕЙ (user_quests)
-- ============================================================
CREATE TABLE IF NOT EXISTS user_quests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    quest_id INTEGER NOT NULL,
    assigned_date TEXT NOT NULL,
    progress INTEGER DEFAULT 0,
    completed INTEGER DEFAULT 0,
    claimed INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (quest_id) REFERENCES quests(quest_id) ON DELETE CASCADE,
    UNIQUE(user_id, quest_id, assigned_date)
);

CREATE INDEX IF NOT EXISTS idx_user_quests_user ON user_quests(user_id);
CREATE INDEX IF NOT EXISTS idx_user_quests_quest ON user_quests(quest_id);
CREATE INDEX IF NOT EXISTS idx_user_quests_assigned ON user_quests(assigned_date);

-- ============================================================
-- 13. ТАБЛИЦА КАТЕГОРИЙ ДОСТИЖЕНИЙ (achievement_categories)
-- ============================================================
CREATE TABLE IF NOT EXISTS achievement_categories (
    category_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    icon TEXT DEFAULT '🏆',
    description TEXT,
    sort_order INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_achievement_categories_sort ON achievement_categories(sort_order);

-- ============================================================
-- 14. ТАБЛИЦА ДОСТИЖЕНИЙ (achievements)
-- ============================================================
CREATE TABLE IF NOT EXISTS achievements (
    achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    icon TEXT DEFAULT '🏆',
    category_id TEXT NOT NULL,
    achievement_type TEXT DEFAULT 'regular',
    parent_achievement_id INTEGER,
    level INTEGER DEFAULT 1,
    event_end_date TEXT,
    requirement_type TEXT NOT NULL,
    requirement_count INTEGER NOT NULL,
    requirement_item TEXT,
    reward_coins INTEGER DEFAULT 0,
    reward_gems INTEGER DEFAULT 0,
    reward_items_json TEXT,
    reward_multiplier REAL DEFAULT 0,
    is_secret INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES achievement_categories(category_id),
    FOREIGN KEY (parent_achievement_id) REFERENCES achievements(achievement_id)
);

CREATE INDEX IF NOT EXISTS idx_achievements_code ON achievements(code);
CREATE INDEX IF NOT EXISTS idx_achievements_category ON achievements(category_id);
CREATE INDEX IF NOT EXISTS idx_achievements_type ON achievements(requirement_type);
CREATE INDEX IF NOT EXISTS idx_achievements_parent ON achievements(parent_achievement_id);
CREATE INDEX IF NOT EXISTS idx_achievements_active ON achievements(is_active);

-- ============================================================
-- 15. ТАБЛИЦА ПРОГРЕССА ДОСТИЖЕНИЙ ИГРОКОВ (player_achievements)
-- ============================================================
CREATE TABLE IF NOT EXISTS player_achievements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    achievement_id INTEGER NOT NULL,
    progress INTEGER DEFAULT 0,
    completed INTEGER DEFAULT 0,
    reward_claimed INTEGER DEFAULT 0,
    completed_at TEXT,
    claimed_at TEXT,
    notified INTEGER DEFAULT 0,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (achievement_id) REFERENCES achievements(achievement_id) ON DELETE CASCADE,
    UNIQUE(user_id, achievement_id)
);

CREATE INDEX IF NOT EXISTS idx_player_achievements_user ON player_achievements(user_id);
CREATE INDEX IF NOT EXISTS idx_player_achievements_achievement ON player_achievements(achievement_id);
CREATE INDEX IF NOT EXISTS idx_player_achievements_completed ON player_achievements(user_id, completed);
CREATE INDEX IF NOT EXISTS idx_player_achievements_claimed ON player_achievements(user_id, completed, reward_claimed);

-- ============================================================
-- 16. ТАБЛИЦА ЛОГОВ ДОСТИЖЕНИЙ (achievement_logs)
-- ============================================================
CREATE TABLE IF NOT EXISTS achievement_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    achievement_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    progress_before INTEGER DEFAULT 0,
    progress_after INTEGER DEFAULT 0,
    reward_claimed TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (achievement_id) REFERENCES achievements(achievement_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_achievement_logs_user ON achievement_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_achievement_logs_achievement ON achievement_logs(achievement_id);
CREATE INDEX IF NOT EXISTS idx_achievement_logs_action ON achievement_logs(action);
CREATE INDEX IF NOT EXISTS idx_achievement_logs_created ON achievement_logs(created_at);

-- ============================================================
-- 17. ТАБЛИЦА ИСТОРИИ РАССЫЛОК (broadcast_history)
-- ============================================================
CREATE TABLE IF NOT EXISTS broadcast_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER,
    audience_type TEXT NOT NULL,
    message_text TEXT NOT NULL,
    sent_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    total_target INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (admin_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_broadcast_history_admin ON broadcast_history(admin_id);
CREATE INDEX IF NOT EXISTS idx_broadcast_history_date ON broadcast_history(created_at);

-- ============================================================
-- 18. ТАБЛИЦА СИСТЕМНЫХ НАСТРОЕК (system_settings)
-- ============================================================
CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 19. ТАБЛИЦА ОБЩИХ ЛОГОВ (logs)
-- ============================================================
CREATE TABLE IF NOT EXISTS logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_group TEXT NOT NULL,
    log_level TEXT NOT NULL,
    user_id INTEGER,
    username TEXT,
    action TEXT NOT NULL,
    target_id INTEGER,
    target_type TEXT,
    details TEXT,
    ip_address TEXT,
    session_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_logs_group ON logs(log_group);
CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(log_level);
CREATE INDEX IF NOT EXISTS idx_logs_user ON logs(user_id);
CREATE INDEX IF NOT EXISTS idx_logs_action ON logs(action);
CREATE INDEX IF NOT EXISTS idx_logs_created ON logs(created_at);

-- ============================================================
-- 20. ТАБЛИЦА УВЕДОМЛЕНИЙ (notifications)
-- ============================================================
CREATE TABLE IF NOT EXISTS notifications (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    message TEXT NOT NULL,
    sent INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_sent ON notifications(user_id, sent);
CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications(created_at);

-- ============================================================
-- 20. ТАБЛИЦА ЭКОНОМИЧЕСКИХ ЛОГОВ (economy_logs)
-- ============================================================
CREATE TABLE IF NOT EXISTS economy_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    operation_type TEXT NOT NULL,
    currency_type TEXT NOT NULL,
    amount INTEGER NOT NULL,
    item_id TEXT,
    balance_after INTEGER,
    source TEXT,
    source_id TEXT,
    details TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_economy_logs_user ON economy_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_economy_logs_action ON economy_logs(operation_type);
CREATE INDEX IF NOT EXISTS idx_economy_logs_created ON economy_logs(created_at);

-- ============================================================
-- 21. ТАБЛИЦА ЛОГОВ ПРОГРЕССА (progression_logs)
-- ============================================================
CREATE TABLE IF NOT EXISTS progression_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    progression_type TEXT NOT NULL,
    old_value INTEGER,
    new_value INTEGER,
    achievement_id TEXT,
    reward_claimed INTEGER DEFAULT 0,
    details TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_progression_logs_user ON progression_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_progression_logs_type ON progression_logs(progression_type);
CREATE INDEX IF NOT EXISTS idx_progression_logs_created ON progression_logs(created_at);

-- ============================================================
-- 22. ТАБЛИЦА ЛОГОВ БЕЗОПАСНОСТИ (security_logs)
-- ============================================================
CREATE TABLE IF NOT EXISTS security_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    user_id INTEGER,
    admin_id INTEGER,
    is_automated INTEGER DEFAULT 0,
    ban_reason TEXT,
    ban_duration INTEGER,
    ip_address TEXT,
    user_agent TEXT,
    details TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_security_logs_type ON security_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_security_logs_user ON security_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_security_logs_admin ON security_logs(admin_id);
CREATE INDEX IF NOT EXISTS idx_security_logs_created ON security_logs(created_at);

-- ============================================================
-- 23. ТАБЛИЦА ЛОГОВ ПРОМОКОДОВ (promo_logs)
-- ============================================================
CREATE TABLE IF NOT EXISTS promo_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    promo_code TEXT NOT NULL,
    user_id INTEGER,
    admin_id INTEGER,
    action TEXT NOT NULL,
    reward_given TEXT,
    success INTEGER DEFAULT 1,
    error_reason TEXT,
    details TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_promo_logs_code ON promo_logs(promo_code);
CREATE INDEX IF NOT EXISTS idx_promo_logs_action ON promo_logs(action);
CREATE INDEX IF NOT EXISTS idx_promo_logs_created ON promo_logs(created_at);

-- ============================================================
-- 24. ТАБЛИЦА СЕЗОННЫХ СОБЫТИЙ (seasonal_events)
-- ============================================================
CREATE TABLE IF NOT EXISTS seasonal_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    season TEXT,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    multiplier REAL DEFAULT 1.0,
    is_active INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_seasonal_events_active ON seasonal_events(is_active);
CREATE INDEX IF NOT EXISTS idx_seasonal_events_dates ON seasonal_events(start_date, end_date);

-- ============================================================
-- 25. ТАБЛИЦА ЛИДЕРБОРДА СОБЫТИЙ (event_leaderboard)
-- ============================================================
CREATE TABLE IF NOT EXISTS event_leaderboard (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    score INTEGER DEFAULT 0,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES seasonal_events(event_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    UNIQUE(event_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_event_leaderboard_event ON event_leaderboard(event_id);
CREATE INDEX IF NOT EXISTS idx_event_leaderboard_user ON event_leaderboard(user_id);
CREATE INDEX IF NOT EXISTS idx_event_leaderboard_score ON event_leaderboard(event_id, score DESC);

-- ============================================================
-- НАЧАЛЬНЫЕ ДАННЫЕ
-- ============================================================

-- Системные настройки
INSERT OR IGNORE INTO system_settings (key, value, description) VALUES
('start_balance', '100', 'Стартовый баланс новых игроков'),
('max_plots', '6', 'Максимальное количество грядок'),
('prestige_formula', '{"base": 1000, "multiplier": 1.5}', 'Формула расчета престижа'),
('maintenance_mode', 'false', 'Режим обслуживания (true/false)'),
('referral_bonus', '50', 'Бонус за приглашение друга'),
('daily_bonus_streak_multiplier', '1.1', 'Множитель наград за стрик ежедневных бонусов');

-- Магазин (семена и бустеры)
INSERT OR IGNORE INTO shop_config (item_code, item_name, item_icon, category, buy_price, sell_price, growth_time, yield_amount, required_level, exp_reward, sort_order) VALUES
('potato', 'Картофель', '🥔', 'seed', 10, 5, 60, 2, 1, 10, 1),
('tomato', 'Помидор', '🍅', 'seed', 20, 12, 120, 3, 1, 20, 2),
('carrot', 'Морковь', '🥕', 'seed', 30, 18, 180, 3, 2, 30, 3),
('corn', 'Кукуруза', '🌽', 'seed', 50, 30, 300, 4, 3, 50, 4),
('strawberry', 'Клубника', '🍓', 'seed', 100, 60, 600, 5, 5, 100, 5),
('water_can', 'Лейка', '🚿', 'booster', 50, 25, 0, 0, 1, 0, 10),
('fertilizer', 'Удобрение', '💩', 'booster', 20, 0, 0, 0, 1, 0, 11);

-- Ежедневные бонусы (по дням стрика)
INSERT OR IGNORE INTO daily_rewards (day_number, coins, gems, items_json) VALUES
(1, 100, 0, '[]'),
(2, 150, 0, '[]'),
(3, 200, 0, '[]'),
(4, 250, 1, '[]'),
(5, 300, 0, '[]'),
(6, 400, 2, '{"fertilizer": 3}'),
(7, 500, 5, '{"water_can": 1}');

-- Категории достижений
INSERT OR IGNORE INTO achievement_categories (category_id, name, icon, description, sort_order) VALUES
('harvest', 'Урожай', '🌾', 'Собирайте урожай', 1),
('planting', 'Посадка', '🌱', 'Сажайте культуры', 2),
('economy', 'Экономика', '💰', 'Зарабатывайте монеты', 3),
('social', 'Социальное', '👥', 'Взаимодействуйте с другими', 4),
('special', 'Особое', '⭐', 'Уникальные достижения', 5);

-- Квесты
INSERT OR IGNORE INTO quests (quest_type, target_count, description, reward_coins, is_daily, is_active, sort_order) VALUES
('harvest', 5, 'Соберите 5 урожаев', 100, 1, 1, 1),
('plant', 3, 'Посадите 3 семени', 50, 1, 1, 2),
('earn', 200, 'Заработайте 200 монет', 150, 1, 1, 3);

-- Достижения
INSERT OR IGNORE INTO achievements (code, name, description, icon, category_id, achievement_type, requirement_type, requirement_count, reward_coins, reward_gems, is_secret, sort_order) VALUES
('first_harvest', 'Первый урожай', 'Соберите первый урожай', '🌱', 'harvest', 'regular', 'harvest', 1, 50, 0, 0, 1),
('harvest_100', 'Зеленая рука', 'Соберите 100 урожаев', '🌿', 'harvest', 'regular', 'harvest', 100, 500, 5, 0, 2),
('harvest_1000', 'Мастер фермерства', 'Соберите 1000 урожаев', '🏆', 'harvest', 'regular', 'harvest', 1000, 5000, 50, 0, 3),
('plant_100', 'Садовник', 'Посадите 100 семян', '🌻', 'planting', 'regular', 'plant', 100, 300, 3, 0, 4),
('earn_10000', 'Богатый фермер', 'Заработайте 10000 монет', '💰', 'economy', 'regular', 'earn', 10000, 1000, 10, 0, 5),
('earn_100000', 'Миллионер', 'Заработайте 100000 монет', '💎', 'economy', 'regular', 'earn', 100000, 10000, 100, 0, 6);

-- ============================================================
-- ТРИГГЕРЫ ДЛЯ АВТОМАТИЗАЦИИ
-- ============================================================

-- Триггер 1: Обновление last_activity при любом действии пользователя
CREATE TRIGGER IF NOT EXISTS update_user_last_activity
AFTER UPDATE ON users
FOR EACH ROW
WHEN NEW.last_activity != OLD.last_activity OR NEW.last_activity IS NULL
BEGIN
    UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE user_id = NEW.user_id;
END;

-- Триггер 2: Автоматический пересчет уровня при изменении опыта
CREATE TRIGGER IF NOT EXISTS update_user_level_on_xp
AFTER UPDATE OF xp ON users
FOR EACH ROW
WHEN NEW.xp != OLD.xp
BEGIN
    UPDATE users 
    SET level = CAST(SQRT(NEW.xp / 100.0) AS INTEGER) + 1
    WHERE user_id = NEW.user_id;
END;

-- Триггер 3: Каскадное обновление times_used в promocodes при активации
CREATE TRIGGER IF NOT EXISTS increment_promo_times_used
AFTER INSERT ON promo_activations
FOR EACH ROW
BEGIN
    UPDATE promocodes 
    SET times_used = times_used + 1 
    WHERE id = NEW.promo_id;
END;

-- ============================================================
-- ПРЕДСТАВЛЕНИЯ (VIEWS) ДЛЯ УДОБСТВА
-- ============================================================

-- View 1: Сводка по пользователям с ачивками
CREATE VIEW IF NOT EXISTS v_user_stats AS
SELECT 
    u.user_id,
    u.username,
    u.first_name,
    u.balance,
    u.gems,
    u.level,
    u.prestige_level,
    u.total_harvested,
    u.total_planted,
    u.total_earned,
    u.joined_date,
    u.last_activity,
    u.is_banned,
    (SELECT COUNT(*) FROM player_achievements WHERE user_id = u.user_id AND completed = 1) as achievements_count,
    (SELECT COUNT(*) FROM plots WHERE user_id = u.user_id AND status IN ('growing', 'ready')) as active_plots,
    (SELECT COUNT(*) FROM promo_activations WHERE user_id = u.user_id) as promos_used
FROM users u;

-- View 2: Активные промокоды
CREATE VIEW IF NOT EXISTS v_active_promocodes AS
SELECT 
    p.id,
    p.code,
    p.reward_json,
    p.description,
    p.max_uses,
    p.times_used,
    p.valid_from,
    p.valid_until,
    p.created_at,
    (SELECT username FROM users WHERE user_id = p.created_by) as created_by_name,
    CASE 
        WHEN p.is_active = 0 THEN 'disabled'
        WHEN p.valid_until IS NOT NULL AND datetime(p.valid_until) < datetime('now') THEN 'expired'
        WHEN p.max_uses > 0 AND p.times_used >= p.max_uses THEN 'exhausted'
        ELSE 'active'
    END as status
FROM promocodes p;

-- View 3: Статистика использования культур
CREATE VIEW IF NOT EXISTS v_crop_usage_stats AS
SELECT 
    sc.item_code,
    sc.item_name,
    sc.item_icon,
    COUNT(p.id) as total_planted,
    COUNT(CASE WHEN p.status = 'ready' THEN 1 END) as total_harvested,
    ROUND(CAST(COUNT(CASE WHEN p.status = 'ready' THEN 1 END) AS FLOAT) * 100.0 / NULLIF(COUNT(p.id), 0), 2) as harvest_rate_percent
FROM shop_config sc
LEFT JOIN plots p ON sc.item_code = p.crop_type
WHERE sc.category = 'seed'
GROUP BY sc.item_code
ORDER BY total_planted DESC;

-- View 4: Логи админов с именами
CREATE VIEW IF NOT EXISTS v_admin_logs_detailed AS
SELECT 
    al.id,
    al.admin_id,
    u_admin.username as admin_username,
    u_admin.first_name as admin_name,
    al.action,
    al.target_id,
    u_target.username as target_username,
    al.details_json,
    al.created_at,
    al.ip
FROM admin_logs al
LEFT JOIN users u_admin ON al.admin_id = u_admin.user_id
LEFT JOIN users u_target ON al.target_id = u_target.user_id
ORDER BY al.created_at DESC;

-- View 5: Топ игроков по балансу
CREATE VIEW IF NOT EXISTS v_top_players_balance AS
SELECT 
    user_id,
    username,
    first_name,
    balance,
    gems,
    level,
    prestige_level,
    total_earned
FROM users
WHERE is_banned = 0
ORDER BY balance DESC
LIMIT 100;

-- View 6: Топ игроков по престижу
CREATE VIEW IF NOT EXISTS v_top_players_prestige AS
SELECT 
    user_id,
    username,
    first_name,
    prestige_level,
    prestige_multiplier,
    level,
    balance
FROM users
WHERE is_banned = 0
ORDER BY prestige_level DESC, prestige_multiplier DESC
LIMIT 100;

-- ============================================================
-- КОНЕЦ СХЕМЫ БАЗЫ ДАННЫХ
-- ============================================================
