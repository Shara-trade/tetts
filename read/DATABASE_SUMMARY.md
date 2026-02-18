# Резюме структуры базы данных «Ленивый Фермер» v2.0

## 📊 Статистика

| Категория | Количество |
|-----------|-----------|
| Таблиц | 30+ |
| Представлений (Views) | 3 |
| Триггеров | 5+ |
| Индексов | 50+ |

## 📁 Таблицы по категориям

### 1. Пользователи (2 таблицы)
- `users` — основная таблица игроков (30+ полей)
- `admin_roles` — роли администраторов

### 2. Администрирование (2 таблицы)
- `admin_logs` — логи действий админов (JSON поля)
- `admin_roles` — назначение ролей

### 3. Растения и экономика (4 таблицы)
- `plants_directory` — справочник растений (soft delete)
- `economy_settings` — key-value настройки
- `shop_items` — ассортимент магазина
- `transactions` — история операций

### 4. Игровой процесс (3 таблицы)
- `inventory` — инвентарь с качеством предметов
- `farming_plots` — грядки игроков (4 статуса)
- `economy_logs` — детальные финансовые логи

### 5. Промо-акции (2 таблицы)
- `promocodes` — промокоды с лимитами и сроками
- `promo_activations` — активации игроками
- `promo_logs` — история операций

### 6. Ежедневный бонус (2 таблицы)
- `daily_bonus_config` — настройка наград (дни 1-30)
- `daily_bonus_claims` — история получений со стриками

### 7. Ачивки (4 таблицы)
- `achievement_categories` — категории (7 шт.)
- `achievements_directory` — справочник ачивок
- `player_achievements` — прогресс игроков
- `achievement_logs` — детальная история

### 8. Логирование (4 таблицы)
- `logs` — универсальные логи (8 групп)
- `economy_logs` — финансовые операции
- `security_logs` — безопасность и баны
- `promo_logs` — операции с промо

### 9. Социальные функции (4 таблицы)
- `neighbors` — соседи/друзья
- `leaderboards` — кэшированные рейтинги
- `gifts` — подарки между игроками
- `notifications` — уведомления

### 10. Дополнительно (4 таблицы)
- `quests` + `player_quests` — система заданий
- `seasonal_events` + `event_participants` — ивенты

## 🔑 Ключевые особенности

### Нормализация
- ✅ 3NF (третья нормальная форма)
- ✅ Внешние ключи с `ON DELETE CASCADE`
- ✅ Составные первичные ключи где нужно

### Денормализация для производительности
- `username` в таблицах логов
- `times_achieved` в справочнике ачивок
- `progress_percent` в прогрессе ачивок
- Кэшированные рейтинги в `leaderboards`

### Soft Delete
- `plants_directory.deleted_at`
- `shop_items.removed_at`
- `promocodes.is_active`

### JSON поля
- `old_value/new_value` в логах
- `reward_json` в промокодах
- `details` в различных таблицах
- `metadata` в инвентаре

## 📈 Индексы

### Критические индексы
```sql
-- Поиск пользователей
idx_users_username, idx_users_balance, idx_users_last_active

-- Игровой процесс
idx_inventory_user, idx_plots_user_status

-- Ачивки
idx_achievements_category, idx_player_achievements_user

-- Промо
idx_promocodes_code, idx_promocodes_active

-- Логи
idx_logs_group_date, idx_logs_user_date, idx_logs_action
```

## 🔄 Триггеры

| Триггер | Действие |
|---------|----------|
| `trg_users_updated_at` | Обновление времени изменения |
| `trg_inventory_updated_at` | Обновление времени инвентаря |
| `trg_player_achievements_updated_at` | Обновление прогресса |
| `trg_log_ban` | Логирование банов |
| `trg_promo_usage_count` | Подсчет активаций |

## 👁️ Представления (Views)

1. **`v_user_summary`** — полный профиль игрока
2. **`v_active_promocodes`** — активные промокоды
3. **`v_player_achievements_detailed`** — ачивки с категориями

## 🔒 Безопасность

### Аудит
- `created_at` во всех таблицах
- `updated_at` с автоматическим обновлением
- `created_by/updated_by` для админских таблиц

### Логирование
- Все действия админов записываются
- Финансовые операции неизменяемы
- Security logs для подозрительной активности

### Права доступа
- Роли: creator > admin > moderator
- Проверка ролей на уровне приложения
- Нельзя забанить админа

## 📊 Примеры аналитики

### Топ-10 игроков по балансу
```sql
SELECT user_id, username, balance,
    ROW_NUMBER() OVER (ORDER BY balance DESC) as rank
FROM users WHERE is_banned = 0
ORDER BY balance DESC LIMIT 10;
```

### Удержание игроков (retention)
```sql
SELECT DATE(joined_date) as cohort,
    COUNT(*) as registered,
    SUM(CASE WHEN last_activity >= datetime('now', '-1 day') THEN 1 END) as d1_retention
FROM users
GROUP BY DATE(joined_date);
```

### Активность по часам
```sql
SELECT strftime('%H', created_at) as hour,
    COUNT(DISTINCT user_id) as active_users
FROM logs
WHERE created_at >= datetime('now', '-7 days')
GROUP BY hour ORDER BY hour;
```

## 📁 Файлы

| Файл | Размер | Назначение |
|------|--------|------------|
| `database_schema_full.sql` | ~700 строк | Полная схема |
| `database_queries_examples.sql` | ~600 строк | Примеры запросов |
| `DATABASE_SCHEMA_README.md` | Документация | Описание таблиц |
| `DATABASE_ER_DIAGRAM.md` | Диаграмма | ER-диаграмма |
| `DATABASE_SUMMARY.md` | Резюме | Этот файл |
| `init_db_full.sql` | Копия | Для инициализации |

## 🚀 Быстрый старт

```bash
# Инициализация базы данных
sqlite3 farm_game.db < database_schema_full.sql

# Или через Python
from database import init_db
await init_db()
```

## 📱 Использование в коде

```python
from database import get_database

db = await get_database()

# Получить профиль
user = await db.get_user(user_id)

# Топ игроков
top = await db.fetchall("""
    SELECT user_id, username, balance 
    FROM users 
    WHERE is_banned = 0 
    ORDER BY balance DESC 
    LIMIT 10
""")
```

## ✅ Проверка целостности

```sql
-- Проверить внешние ключи
PRAGMA foreign_key_check;

-- Анализ запроса
EXPLAIN QUERY PLAN 
SELECT * FROM users WHERE user_id = ?;

-- Статистика таблиц
SELECT name, COUNT(*) as rows 
FROM sqlite_master 
WHERE type = 'table';
```

---

**Версия**: 2.0  
**Дата**: 2024  
**Совместимость**: SQLite 3.35+, PostgreSQL 12+
