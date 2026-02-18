-- ============================================================
-- ПРИМЕРЫ СЛОЖНЫХ SQL-ЗАПРОСОВ
-- Игра «Ленивый Фермер» v2.0
-- ============================================================

-- ------------------------------------------------------------
-- 1. ПРОФИЛИ И СТАТИСТИКА ПОЛЬЗОВАТЕЛЕЙ
-- ------------------------------------------------------------

-- 1.1 Полный профиль игрока со всей статистикой
SELECT 
    u.user_id,
    u.username,
    u.first_name,
    u.balance,
    u.gems,
    u.prestige_level,
    u.prestige_multiplier,
    u.city_level,
    u.exp,
    u.total_harvested,
    u.total_planted,
    u.last_activity,
    u.joined_date,
    u.is_banned,
    -- Количество ачивок
    (SELECT COUNT(*) FROM player_achievements pa 
     WHERE pa.user_id = u.user_id AND pa.is_completed = 1) as achievements_count,
    -- Готовых грядок
    (SELECT COUNT(*) FROM farming_plots fp 
     WHERE fp.user_id = u.user_id AND fp.status = 'ready') as ready_plots,
    -- Всего предметов в инвентаре
    (SELECT COALESCE(SUM(quantity), 0) FROM inventory i 
     WHERE i.user_id = u.user_id) as total_items,
    -- Количество соседей
    (SELECT COUNT(*) FROM neighbors n 
     WHERE n.user_id = u.user_id AND n.status = 'active') as neighbors_count,
    -- Максимальный стрик
    (SELECT COALESCE(MAX(current_streak), 0) FROM daily_bonus_claims dbc 
     WHERE dbc.user_id = u.user_id) as max_streak,
    -- Позиция в рейтинге
    (SELECT rank FROM leaderboards lb 
     WHERE lb.user_id = u.user_id AND lb.leaderboard_type = 'balance' AND lb.period = 'alltime') as balance_rank
FROM users u
WHERE u.user_id = ?;

-- 1.2 Топ-10 игроков по балансу с доп. статистикой
SELECT 
    u.user_id,
    u.username,
    u.first_name,
    u.balance,
    u.prestige_level,
    u.total_harvested,
    (SELECT COUNT(*) FROM player_achievements pa 
     WHERE pa.user_id = u.user_id AND pa.is_completed = 1) as achievements_count,
    ROW_NUMBER() OVER (ORDER BY u.balance DESC) as rank_position
FROM users u
WHERE u.is_banned = 0
ORDER BY u.balance DESC
LIMIT 10;

-- 1.3 Топ-10 по уровню престижа
SELECT 
    u.user_id,
    u.username,
    u.first_name,
    u.prestige_level,
    u.total_harvested,
    u.balance,
    ROW_NUMBER() OVER (ORDER BY u.prestige_level DESC, u.total_harvested DESC) as rank_position
FROM users u
WHERE u.is_banned = 0
ORDER BY u.prestige_level DESC, u.total_harvested DESC
LIMIT 10;

-- ------------------------------------------------------------
-- 2. ИНВЕНТАРЬ И ГРЯДКИ
-- ------------------------------------------------------------

-- 2.1 Инвентарь игрока с деталями растений
SELECT 
    i.id,
    i.item_type,
    i.plant_id,
    p.name as plant_name,
    p.emoji,
    i.quantity,
    p.sell_price,
    (i.quantity * p.sell_price) as total_value,
    i.quality
FROM inventory i
LEFT JOIN plants_directory p ON i.plant_id = p.plant_id
WHERE i.user_id = ?
ORDER BY i.item_type, p.sort_order;

-- 2.2 Все грядки игрока с временем до сбора
SELECT 
    fp.id,
    fp.plot_number,
    fp.status,
    p.name as plant_name,
    p.emoji,
    fp.planted_at,
    fp.ready_at,
    CASE 
        WHEN fp.status = 'growing' THEN 
            MAX(0, CAST((julianday(fp.ready_at) - julianday('now')) * 24 * 60 * 60 AS INTEGER))
        ELSE 0
    END as seconds_remaining,
    fp.water_count,
    fp.fertilized,
    fp.expected_yield
FROM farming_plots fp
LEFT JOIN plants_directory p ON fp.plant_id = p.plant_id
WHERE fp.user_id = ?
ORDER BY fp.plot_number;

-- 2.3 Готовые к сбору грядки всех игроков (для уведомлений)
SELECT 
    fp.user_id,
    u.username,
    COUNT(*) as ready_plots,
    GROUP_CONCAT(p.name || ' ' || p.emoji) as crops_ready
FROM farming_plots fp
JOIN plants_directory p ON fp.plant_id = p.plant_id
JOIN users u ON fp.user_id = u.user_id
WHERE fp.status = 'ready'
AND fp.user_id NOT IN (
    -- Исключаем тех, кому уже отправлено уведомление
    SELECT user_id FROM notifications 
    WHERE type = 'harvest_ready' AND is_read = 0
)
GROUP BY fp.user_id;

-- ------------------------------------------------------------
-- 3. АЧИВКИ И ДОСТИЖЕНИЯ
-- ------------------------------------------------------------

-- 3.1 Все ачивки игрока с прогрессом
SELECT 
    ad.achievement_id,
    ad.name,
    ad.description,
    ad.icon,
    ac.name as category_name,
    ac.icon as category_icon,
    ad.goal_type,
    ad.goal_value,
    COALESCE(pa.current_value, 0) as current_value,
    COALESCE(pa.progress_percent, 0) as progress_percent,
    COALESCE(pa.is_completed, 0) as is_completed,
    pa.completed_at,
    pa.reward_claimed,
    ad.reward_coins,
    ad.reward_gems,
    ad.is_secret,
    CASE 
        WHEN ad.is_secret = 1 AND COALESCE(pa.is_completed, 0) = 0 THEN '???'
        ELSE ad.name
    END as display_name
FROM achievements_directory ad
JOIN achievement_categories ac ON ad.category_id = ac.category_id
LEFT JOIN player_achievements pa 
    ON ad.achievement_id = pa.achievement_id AND pa.user_id = ?
WHERE ad.is_active = 1
ORDER BY ac.sort_order, ad.sort_order, ad.tier;

-- 3.2 Статистика ачивок по категориям
SELECT 
    ac.category_id,
    ac.name,
    ac.icon,
    COUNT(DISTINCT ad.achievement_id) as total_achievements,
    COUNT(DISTINCT CASE WHEN pa.is_completed = 1 THEN pa.id END) as completed_by_user,
    COUNT(DISTINCT pa_all.id) as total_completions,
    COUNT(DISTINCT pa_all.user_id) as unique_players
FROM achievement_categories ac
LEFT JOIN achievements_directory ad 
    ON ac.category_id = ad.category_id AND ad.is_active = 1
LEFT JOIN player_achievements pa 
    ON ad.achievement_id = pa.achievement_id AND pa.user_id = ? AND pa.is_completed = 1
LEFT JOIN player_achievements pa_all 
    ON ad.achievement_id = pa_all.achievement_id AND pa_all.is_completed = 1
GROUP BY ac.category_id, ac.name, ac.icon
ORDER BY ac.sort_order;

-- 3.3 Топ-5 редких ачивок (< 1% игроков имеют)
WITH total_players AS (
    SELECT COUNT(*) as cnt FROM users WHERE is_banned = 0
)
SELECT 
    ad.achievement_id,
    ad.name,
    ad.icon,
    COUNT(pa.id) as earned_count,
    ROUND(COUNT(pa.id) * 100.0 / (SELECT cnt FROM total_players), 2) as percent_players
FROM achievements_directory ad
LEFT JOIN player_achievements pa 
    ON ad.achievement_id = pa.achievement_id AND pa.is_completed = 1
WHERE ad.is_active = 1
GROUP BY ad.achievement_id, ad.name, ad.icon
HAVING percent_players < 1
ORDER BY earned_count ASC
LIMIT 5;

-- 3.4 Следующие ачивки для получения (сортировка по близости к цели)
SELECT 
    ad.achievement_id,
    ad.name,
    ad.icon,
    ad.goal_value,
    COALESCE(pa.current_value, 0) as current_value,
    (ad.goal_value - COALESCE(pa.current_value, 0)) as remaining,
    ROUND(COALESCE(pa.current_value, 0) * 100.0 / ad.goal_value, 1) as progress_percent,
    ad.reward_coins,
    ad.reward_gems
FROM achievements_directory ad
LEFT JOIN player_achievements pa 
    ON ad.achievement_id = pa.achievement_id AND pa.user_id = ?
WHERE ad.is_active = 1
AND ad.is_secret = 0
AND COALESCE(pa.is_completed, 0) = 0
ORDER BY progress_percent DESC
LIMIT 5;

-- ------------------------------------------------------------
-- 4. ЭКОНОМИКА И ТРАНЗАКЦИИ
-- ------------------------------------------------------------

-- 4.1 Баланс доходов и расходов игрока за период
SELECT 
    DATE(t.created_at) as date,
    SUM(CASE WHEN t.type = 'earn' AND t.currency = 'coins' THEN t.amount ELSE 0 END) as earned_coins,
    SUM(CASE WHEN t.type = 'spend' AND t.currency = 'coins' THEN ABS(t.amount) ELSE 0 END) as spent_coins,
    SUM(CASE WHEN t.type = 'earn' AND t.currency = 'gems' THEN t.amount ELSE 0 END) as earned_gems,
    SUM(CASE WHEN t.type = 'spend' AND t.currency = 'gems' THEN ABS(t.amount) ELSE 0 END) as spent_gems,
    COUNT(*) as transactions_count
FROM transactions t
WHERE t.user_id = ?
AND t.created_at >= datetime('now', '-7 days')
GROUP BY DATE(t.created_at)
ORDER BY date DESC;

-- 4.2 Экономическая статистика за неделю (для админки)
SELECT 
    DATE(created_at) as date,
    COUNT(CASE WHEN operation_type = 'earn' THEN 1 END) as earn_operations,
    SUM(CASE WHEN operation_type = 'earn' THEN amount ELSE 0 END) as total_earned,
    COUNT(CASE WHEN operation_type = 'spend' THEN 1 END) as spend_operations,
    SUM(CASE WHEN operation_type = 'spend' THEN amount ELSE 0 END) as total_spent,
    COUNT(DISTINCT user_id) as active_users
FROM economy_logs
WHERE created_at >= datetime('now', '-7 days')
GROUP BY DATE(created_at)
ORDER BY date;

-- 4.3 Источники дохода игрока
SELECT 
    source,
    COUNT(*) as operations_count,
    SUM(amount) as total_amount,
    ROUND(AVG(amount), 2) as avg_amount
FROM economy_logs
WHERE user_id = ?
AND operation_type = 'earn'
AND created_at >= datetime('now', '-30 days')
GROUP BY source
ORDER BY total_amount DESC;

-- 4.4 Общая экономическая статистика (для админки)
SELECT 
    (SELECT COUNT(*) FROM users WHERE is_banned = 0) as total_users,
    (SELECT SUM(balance) FROM users WHERE is_banned = 0) as total_coins_in_circulation,
    (SELECT SUM(gems) FROM users WHERE is_banned = 0) as total_gems_in_circulation,
    (SELECT AVG(balance) FROM users WHERE is_banned = 0) as avg_balance,
    (SELECT COUNT(DISTINCT user_id) FROM economy_logs 
     WHERE created_at >= datetime('now', '-1 day')) as active_today,
    (SELECT COUNT(DISTINCT user_id) FROM economy_logs 
     WHERE created_at >= datetime('now', '-7 days')) as active_this_week;

-- ------------------------------------------------------------
-- 5. ПРОМО-АКЦИИ
-- ------------------------------------------------------------

-- 5.1 Статистика промокода
SELECT 
    p.id,
    p.code,
    p.promo_type,
    p.reward_type,
    p.reward_value,
    p.max_uses,
    p.used_count,
    p.per_user_limit,
    p.start_date,
    p.end_date,
    p.is_active,
    COUNT(DISTINCT pa.user_id) as unique_activators,
    COUNT(pa.id) as total_activations,
    MAX(pa.activated_at) as last_activation,
    -- Топ активаторы
    (SELECT GROUP_CONCAT(u.username, ', ') 
     FROM (SELECT DISTINCT u.username FROM promo_activations pa2 
           JOIN users u ON pa2.user_id = u.user_id 
           WHERE pa2.promo_id = p.id LIMIT 5)) as top_users
FROM promocodes p
LEFT JOIN promo_activations pa ON p.id = pa.promo_id
WHERE p.code = ?
GROUP BY p.id;

-- 5.2 Активные промокоды с оставшимися активациями
SELECT 
    code,
    reward_type,
    reward_value,
    (max_uses - used_count) as remaining_uses,
    end_date,
    CASE 
        WHEN end_date IS NULL THEN 'Бессрочно'
        WHEN end_date < datetime('now') THEN 'Истек'
        ELSE CAST(ROUND((julianday(end_date) - julianday('now'))) AS INTEGER) || ' дн.'
    END as time_remaining
FROM promocodes
WHERE is_active = 1
AND (max_uses IS NULL OR used_count < max_uses)
AND (end_date IS NULL OR end_date > datetime('now'));

-- ------------------------------------------------------------
-- 6. ЛОГИ И МОДЕРАЦИЯ
-- ------------------------------------------------------------

-- 6.1 Последние действия администраторов
SELECT 
    al.created_at,
    u.username as admin_name,
    al.admin_role,
    al.action_type,
    tu.username as target_name,
    al.target_entity,
    al.reason,
    al.details
FROM admin_logs al
JOIN users u ON al.admin_id = u.user_id
LEFT JOIN users tu ON al.target_user_id = tu.user_id
WHERE al.created_at >= datetime('now', '-1 day')
ORDER BY al.created_at DESC
LIMIT 50;

-- 6.2 История действий над конкретным игроком
SELECT 
    al.created_at,
    u.username as admin_name,
    al.action_type,
    al.old_value,
    al.new_value,
    al.reason,
    al.details
FROM admin_logs al
JOIN users u ON al.admin_id = u.user_id
WHERE al.target_user_id = ?
ORDER BY al.created_at DESC;

-- 6.3 Статистика логов по группам
SELECT 
    log_group,
    log_level,
    COUNT(*) as count,
    COUNT(DISTINCT user_id) as unique_users,
    MIN(created_at) as first_entry,
    MAX(created_at) as last_entry
FROM logs
WHERE created_at >= datetime('now', '-7 days')
GROUP BY log_group, log_level
ORDER BY count DESC;

-- 6.4 Подозрительная активность (более 100 действий за час)
SELECT 
    user_id,
    username,
    COUNT(*) as actions_count,
    COUNT(DISTINCT action) as unique_actions,
    MIN(created_at) as first_action,
    MAX(created_at) as last_action
FROM logs
WHERE created_at >= datetime('now', '-1 hour')
GROUP BY user_id, username
HAVING COUNT(*) > 100
ORDER BY actions_count DESC;

-- ------------------------------------------------------------
-- 7. СОЦИАЛЬНЫЕ ФУНКЦИИ
-- ------------------------------------------------------------

-- 7.1 Список соседей игрока с активностью
SELECT 
    n.id,
    n.neighbor_id,
    u.username,
    u.first_name,
    u.farm_name,
    n.status,
    n.helped_count,
    n.helped_at,
    CASE 
        WHEN n.helped_at IS NULL THEN 'Никогда'
        WHEN datetime(n.helped_at) > datetime('now', '-1 day') THEN 'Сегодня'
        WHEN datetime(n.helped_at) > datetime('now', '-7 days') THEN 'На этой неделе'
        ELSE 'Давно'
    END as last_help_text,
    (SELECT COUNT(*) FROM farming_plots WHERE user_id = n.neighbor_id AND status = 'ready') as neighbor_ready_plots
FROM neighbors n
JOIN users u ON n.neighbor_id = u.user_id
WHERE n.user_id = ? AND n.status = 'active'
ORDER BY n.helped_at DESC NULLS LAST;

-- 7.2 Поиск потенциальных соседей (кто недавно был активен)
SELECT 
    u.user_id,
    u.username,
    u.first_name,
    u.farm_name,
    u.prestige_level,
    u.last_activity
FROM users u
WHERE u.is_banned = 0
AND u.user_id != ?
AND u.user_id NOT IN (
    SELECT neighbor_id FROM neighbors WHERE user_id = ?
    UNION
    SELECT user_id FROM neighbors WHERE neighbor_id = ?
)
AND u.last_activity >= datetime('now', '-7 days')
ORDER BY u.last_activity DESC
LIMIT 20;

-- ------------------------------------------------------------
-- 8. АНАЛИТИКА И ОТЧЕТЫ
-- ------------------------------------------------------------

-- 8.1 Активность игроков по часам (для выбора времени рассылки)
SELECT 
    strftime('%H', created_at) as hour,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(*) as total_actions
FROM logs
WHERE created_at >= datetime('now', '-7 days')
GROUP BY hour
ORDER BY hour;

-- 8.2 Удержание игроков (retention)
WITH cohorts AS (
    SELECT 
        user_id,
        DATE(joined_date) as join_date,
        CASE 
            WHEN last_activity >= datetime('now', '-1 day') THEN 'active_today'
            WHEN last_activity >= datetime('now', '-7 days') THEN 'active_week'
            WHEN last_activity >= datetime('now', '-30 days') THEN 'active_month'
            ELSE 'inactive'
        END as activity_status
    FROM users
    WHERE is_banned = 0
)
SELECT 
    join_date,
    COUNT(*) as total_registered,
    SUM(CASE WHEN activity_status = 'active_today' THEN 1 ELSE 0 END) as active_today,
    SUM(CASE WHEN activity_status IN ('active_today', 'active_week') THEN 1 ELSE 0 END) as active_week,
    SUM(CASE WHEN activity_status IN ('active_today', 'active_week', 'active_month') THEN 1 ELSE 0 END) as active_month
FROM cohorts
WHERE join_date >= DATE('now', '-30 days')
GROUP BY join_date
ORDER BY join_date DESC;

-- 8.3 Воронка прогресса новых игроков
SELECT 
    'Зарегистрировались' as stage,
    COUNT(*) as count,
    100.0 as percentage
FROM users
WHERE joined_date >= datetime('now', '-7 days')

UNION ALL

SELECT 
    'Посадили первое растение' as stage,
    COUNT(DISTINCT fp.user_id),
    ROUND(COUNT(DISTINCT fp.user_id) * 100.0 / (
        SELECT COUNT(*) FROM users WHERE joined_date >= datetime('now', '-7 days')
    ), 2)
FROM farming_plots fp
WHERE fp.user_id IN (SELECT user_id FROM users WHERE joined_date >= datetime('now', '-7 days'))

UNION ALL

SELECT 
    'Собрали первый урожай' as stage,
    COUNT(DISTINCT t.user_id),
    ROUND(COUNT(DISTINCT t.user_id) * 100.0 / (
        SELECT COUNT(*) FROM users WHERE joined_date >= datetime('now', '-7 days')
    ), 2)
FROM transactions t
WHERE t.source = 'harvest'
AND t.user_id IN (SELECT user_id FROM users WHERE joined_date >= datetime('now', '-7 days'))

UNION ALL

SELECT 
    'Получили первую ачивку' as stage,
    COUNT(DISTINCT pa.user_id),
    ROUND(COUNT(DISTINCT pa.user_id) * 100.0 / (
        SELECT COUNT(*) FROM users WHERE joined_date >= datetime('now', '-7 days')
    ), 2)
FROM player_achievements pa
WHERE pa.is_completed = 1
AND pa.user_id IN (SELECT user_id FROM users WHERE joined_date >= datetime('now', '-7 days'));

-- 8.4 Самые прибыльные растения
SELECT 
    p.plant_id,
    p.name,
    p.emoji,
    p.seed_price,
    p.sell_price,
    p.yield_amount,
    (p.sell_price * p.yield_amount - p.seed_price) as profit_per_cycle,
    ROUND((p.sell_price * p.yield_amount - p.seed_price) * 1.0 / p.grow_time * 3600, 2) as profit_per_hour,
    (SELECT COUNT(*) FROM farming_plots WHERE plant_id = p.plant_id) as times_planted,
    (SELECT COUNT(*) FROM economy_logs WHERE item_id = p.plant_id AND operation_type = 'sell') as times_sold
FROM plants_directory p
WHERE p.is_active = 1
ORDER BY profit_per_hour DESC;

-- ------------------------------------------------------------
-- 9. ЕЖЕДНЕВНЫЙ БОНУС
-- ------------------------------------------------------------

-- 9.1 Статистика получения бонусов
SELECT 
    dbc.claim_date,
    COUNT(DISTINCT dbc.user_id) as users_claimed,
    AVG(dbc.current_streak) as avg_streak,
    MAX(dbc.current_streak) as max_streak,
    SUM(dbc.coins_received) as total_coins_given,
    SUM(dbc.gems_received) as total_gems_given
FROM daily_bonus_claims dbc
WHERE dbc.claim_date >= DATE('now', '-30 days')
GROUP BY dbc.claim_date
ORDER BY dbc.claim_date DESC;

-- 9.2 Топ-10 по стрику
SELECT 
    u.user_id,
    u.username,
    u.first_name,
    dbc.current_streak,
    dbc.claim_date as last_claim
FROM daily_bonus_claims dbc
JOIN users u ON dbc.user_id = u.user_id
WHERE dbc.claim_date = (
    SELECT MAX(claim_date) FROM daily_bonus_claims WHERE user_id = dbc.user_id
)
ORDER BY dbc.current_streak DESC
LIMIT 10;

-- ------------------------------------------------------------
-- 10. КВЕСТЫ
-- ------------------------------------------------------------

-- 10.1 Активные квесты игрока
SELECT 
    q.quest_id,
    q.title,
    q.description,
    q.quest_type,
    q.target_type,
    q.target_count,
    COALESCE(pq.progress, 0) as progress,
    ROUND(COALESCE(pq.progress, 0) * 100.0 / q.target_count, 1) as progress_percent,
    pq.is_completed,
    q.reward_coins,
    q.reward_gems,
    CASE 
        WHEN q.quest_type = 'daily' THEN 'Ежедневное'
        WHEN q.quest_type = 'weekly' THEN 'Еженедельное'
        WHEN q.quest_type = 'event' THEN 'Событие'
        ELSE 'Основное'
    END as quest_type_name
FROM quests q
LEFT JOIN player_quests pq ON q.quest_id = pq.quest_id 
    AND pq.user_id = ? 
    AND (q.quest_type != 'daily' OR pq.assigned_date = CURRENT_DATE)
WHERE q.is_active = 1
AND (q.end_date IS NULL OR q.end_date > datetime('now'))
AND (pq.id IS NOT NULL OR q.quest_type = 'daily')
ORDER BY q.quest_type, progress_percent DESC;
