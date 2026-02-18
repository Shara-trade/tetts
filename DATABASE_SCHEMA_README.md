# Структура базы данных «Ленивый Фермер» v2.0

## Обзор

Полная структура реляционной базы данных для Telegram-бота игры «Ленивый фермер».

### Характеристики
- **Тип БД**: SQLite (основная) / PostgreSQL (совместимость)
- **Нормализация**: 3NF с денормализацией для производительности
- **Связи**: Внешние ключи с каскадным удалением
- **Аудит**: Поля created_at/updated_at во всех таблицах
- **Soft Delete**: Поддержка мягкого удаления

---

## Схема данных

### 1. Пользователи (`users`)

| Поле | Тип | Описание | Индекс |
|------|-----|----------|--------|
| user_id | INTEGER PK | ID пользователя Telegram | ✅ |
| username | VARCHAR(100) | Username | ✅ |
| first_name | VARCHAR(100) | Имя | |
| balance | BIGINT | Монеты | ✅ |
| gems | INT | Кристаллы | |
| exp | INT | Опыт | |
| prestige_level | INT | Уровень престижа | ✅ |
| prestige_multiplier | DECIMAL | Множитель престижа | |
| city_level | INT | Уровень города | |
| total_harvested | BIGINT | Всего собрано | ✅ |
| is_banned | BOOLEAN | Забанен | ✅ |
| referrer_id | INT FK | Кто пригласил | ✅ |
| last_activity | TIMESTAMP | Последняя активность | ✅ |
| joined_date | TIMESTAMP | Дата регистрации | ✅ |

### 2. Администрирование

#### `admin_roles`
| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL PK | ID записи |
| user_id | INT FK | ID админа |
| role | VARCHAR(20) | creator/admin/moderator |
| assigned_by | INT FK | Кто назначил |
| assigned_at | TIMESTAMP | Дата назначения |

#### `admin_logs`
| Поле | Тип | Описание |
|------|-----|----------|
| log_id | BIGSERIAL PK | ID лога |
| admin_id | INT FK | Кто действовал |
| action_type | VARCHAR(50) | Тип действия |
| target_user_id | INT FK | Цель |
| old_value | JSON | Старое значение |
| new_value | JSON | Новое значение |
| reason | TEXT | Причина |
| created_at | TIMESTAMP | Время |

### 3. Растения и экономика

#### `plants_directory`
| Поле | Тип | Описание |
|------|-----|----------|
| plant_id | VARCHAR(50) PK | Уникальный код |
| name | VARCHAR(100) | Название |
| emoji | VARCHAR(10) | Эмодзи |
| grow_time | INT | Время роста (сек) |
| seed_price | INT | Цена семян |
| sell_price | INT | Цена продажи |
| yield_amount | INT | Урожайность |
| required_level | INT | Требуемый уровень |
| exp_reward | INT | Опыт за сбор |
| category | VARCHAR(30) | regular/seasonal/event |
| season | VARCHAR(20) | Сезон |
| rarity | VARCHAR(20) | Редкость |
| is_active | BOOLEAN | Активно |
| deleted_at | TIMESTAMP | Soft delete |

#### `economy_settings`
Хранилище key-value для настроек экономики:
- `tax_rate` — налог на продажу
- `market_fluctuation` — колебания цен
- `event_multiplier` — множитель события
- `season` — текущий сезон

#### `shop_items`
Ассортимент магазина с ценами и лимитами.

### 4. Игровой процесс

#### `inventory`
| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL PK | ID записи |
| user_id | INT FK | Владелец |
| item_type | VARCHAR(20) | Тип предмета |
| plant_id | VARCHAR FK | Растение |
| quantity | INT | Количество |
| quality | INT | Качество 1-5 |

#### `farming_plots`
Грядки игроков:
- `status`: empty/growing/ready/withered
- `planted_at`: время посадки
- `ready_at`: время созревания
- `water_count`: поливы
- `fertilized`: удобрено ли

#### `transactions`
История всех операций с балансом:
- Тип: earn/spend/purchase/sell/gift/admin/promo
- Валюта: coins/gems
- Источник: harvest/bonus/admin/promo/shop

### 5. Промо-акции

#### `promocodes`
| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL PK | ID |
| code | VARCHAR(50) | Код промо |
| promo_type | VARCHAR(20) | time/count/personal |
| reward_type | VARCHAR(20) | coins/gems/item/multiplier |
| reward_value | INT | Количество |
| max_uses | INT | Макс. активаций |
| used_count | INT | Использовано |
| per_user_limit | INT | Лимит на игрока |
| start_date | TIMESTAMP | Начало |
| end_date | TIMESTAMP | Конец |
| is_active | BOOLEAN | Активен |

#### `promo_activations`
Активации промокодов игроками.

### 6. Ежедневный бонус

#### `daily_bonus_config`
Настройка наград за дни 1-30:
- coins, gems — валюта
- item_id, item_quantity — предметы
- is_special — особый день

#### `daily_bonus_claims`
История получения бонусов с отслеживанием стрика.

### 7. Ачивки (Достижения)

#### `achievement_categories`
Категории: harvest, finance, prestige, activity, social, special, events

#### `achievements_directory`
| Поле | Тип | Описание |
|------|-----|----------|
| achievement_id | VARCHAR(50) PK | Уникальный код |
| category_id | VARCHAR FK | Категория |
| name | VARCHAR(100) | Название |
| description | TEXT | Описание |
| tier | INT | Уровень (для многоуровневых) |
| parent_id | VARCHAR FK | Родительская ачивка |
| goal_type | VARCHAR(30) | Тип цели |
| goal_value | BIGINT | Значение цели |
| reward_coins | INT | Награда монетами |
| reward_gems | INT | Награда кристаллами |
| is_secret | BOOLEAN | Секретная |
| is_event | BOOLEAN | Ивентовая |

#### `player_achievements`
Прогресс игроков по ачивкам:
- current_value — текущий прогресс
- progress_percent — процент выполнения
- is_completed — выполнена ли
- reward_claimed — получена ли награда

### 8. Логирование

#### `logs` — Универсальные логи
Группы: admin, economy, gameplay, system, security, achievements, promo, social
Уровни: DEBUG, INFO, WARNING, ERROR, CRITICAL

#### `economy_logs` — Экономические операции
Оптимизированная таблица для финансовой аналитики.

#### `security_logs` — Безопасность
Баны, подозрительная активность, входы.

#### `promo_logs` — История промо
Создание, активация, деактивация промокодов.

### 9. Социальные функции

#### `neighbors`
Соседи/друзья игроков:
- status: pending/active/blocked
- helped_at — последняя помощь
- helped_count — сколько раз помог

#### `leaderboards`
Кэшированные рейтинги:
- Типы: balance, harvest, prestige, exp, achievements
- Периоды: daily, weekly, monthly, alltime

#### `gifts`
Подарки между игроками с поддержкой анонимности.

### 10. Дополнительные таблицы

#### `notifications`
Уведомления игрокам:
- Типы: harvest_ready, daily_bonus, achievement, gift, etc.
- Приоритет 0-10
- Сроки действия

#### `quests` и `player_quests`
Система заданий (ежедневные, еженедельные, ивентовые).

#### `seasonal_events` и `event_participants`
Сезонные события с таблицами лидеров.

---

## Индексы

### Критические индексы
```sql
-- Пользователи
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_balance ON users(balance DESC);
CREATE INDEX idx_users_last_active ON users(last_activity);

-- Инвентарь и грядки
CREATE INDEX idx_inventory_user ON inventory(user_id);
CREATE INDEX idx_plots_user_status ON farming_plots(user_id, status);

-- Ачивки
CREATE INDEX idx_achievements_category ON achievements_directory(category_id);
CREATE INDEX idx_player_achievements_user ON player_achievements(user_id);

-- Промо
CREATE INDEX idx_promocodes_active ON promocodes(is_active, end_date);

-- Логи
CREATE INDEX idx_logs_group_date ON logs(log_group, created_at);
CREATE INDEX idx_logs_user_date ON logs(user_id, created_at);
```

---

## Триггеры

### Автообновление времени
```sql
-- Обновление updated_at при изменении записи
CREATE TRIGGER trg_users_updated_at
AFTER UPDATE ON users
BEGIN
    UPDATE users SET updated_at = datetime('now') WHERE user_id = NEW.user_id;
END;
```

### Логирование банов
```sql
CREATE TRIGGER trg_log_ban
AFTER UPDATE OF is_banned ON users
WHEN NEW.is_banned = 1 AND OLD.is_banned = 0
BEGIN
    INSERT INTO security_logs (event_type, user_id, ban_reason, ban_expires)
    VALUES ('ban', NEW.user_id, NEW.ban_reason, NEW.ban_until);
END;
```

---

## Представления (Views)

### `v_user_summary`
Полная сводка по пользователю:
- Количество ачивок
- Готовых грядок
- Предметов в инвентаре
- Соседей
- Максимальный стрик

### `v_active_promocodes`
Активные промокоды с проверкой сроков и лимитов.

### `v_player_achievements_detailed`
Ачивки игрока с деталями категорий.

---

## Примеры запросов

### Профиль игрока
```sql
SELECT u.*,
    (SELECT COUNT(*) FROM player_achievements 
     WHERE user_id = u.user_id AND is_completed = 1) as achievements_count,
    (SELECT COUNT(*) FROM farming_plots 
     WHERE user_id = u.user_id AND status = 'ready') as ready_plots
FROM users u
WHERE u.user_id = ?;
```

### Топ-10 по балансу
```sql
SELECT user_id, username, first_name, balance, prestige_level,
    ROW_NUMBER() OVER (ORDER BY balance DESC) as rank
FROM users
WHERE is_banned = 0
ORDER BY balance DESC
LIMIT 10;
```

### Статистика ачивок по категориям
```sql
SELECT ac.name, ac.icon,
    COUNT(DISTINCT ad.achievement_id) as total,
    COUNT(DISTINCT CASE WHEN pa.is_completed = 1 THEN pa.id END) as completed
FROM achievement_categories ac
LEFT JOIN achievements_directory ad ON ac.category_id = ad.category_id
LEFT JOIN player_achievements pa ON ad.achievement_id = pa.achievement_id AND pa.user_id = ?
GROUP BY ac.category_id;
```

---

## Файлы

| Файл | Описание |
|------|----------|
| `database_schema_full.sql` | Полная схема БД |
| `database_queries_examples.sql` | Примеры запросов |
| `init_db.sql` | Начальная инициализация |
| `DATABASE_SCHEMA_README.md` | Этот файл |

---

## Миграции

При обновлении структуры:
1. Создавайте новые таблицы через `CREATE TABLE IF NOT EXISTS`
2. Добавляйте колонки через `ALTER TABLE ... ADD COLUMN`
3. Обновляйте индексы
4. Тестируйте на копии данных

---

## Оптимизация

### Для SQLite:
- Используйте `PRAGMA foreign_keys = ON`
- Регулярно выполняйте `VACUUM`
- Анализируйте запросы через `EXPLAIN QUERY PLAN`

### Для PostgreSQL:
- Используйте партиционирование для больших таблиц логов
- Настройте `autovacuum`
- Создавайте частичные индексы для активных записей
