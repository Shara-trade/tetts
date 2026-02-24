# Структура базы данных Lazy Farmer Bot

## Общая информация
- **Тип:** SQLite
- **Версия схемы:** 4.0
- **Количество таблиц:** 45+

## Основные таблицы

### 1. users - Пользователи
Основная таблица с данными игроков.

| Поле | Тип | Описание |
|------|-----|----------|
| user_id | INTEGER PRIMARY KEY | Telegram ID |
| username | TEXT | Имя пользователя |
| first_name | TEXT | Имя |
| nickname | TEXT UNIQUE | Кастомный ник |
| balance | INTEGER DEFAULT 100 | Баланс монет |
| gems | INTEGER DEFAULT 0 | Кристаллы |
| level | INTEGER DEFAULT 1 | Уровень города |
| xp | INTEGER DEFAULT 0 | Опыт |
| prestige_level | INTEGER DEFAULT 1 | Уровень престижа |
| prestige_multiplier | REAL DEFAULT 1.0 | Множитель престижа |
| settings | TEXT | JSON настроек |

### 2. plots - Грядки
Грядки пользователей.

| Поле | Тип | Описание |
|------|-----|----------|
| plot_id | INTEGER PRIMARY KEY | ID грядки |
| user_id | INTEGER | Владелец |
| plot_number | INTEGER | Номер грядки |
| status | TEXT | empty/growing/ready |
| crop_type | TEXT | Тип культуры |
| planted_time | TEXT | Время посадки |
| fertilized | INTEGER | 0/1 - удобрено |

### 3. inventory - Инвентарь
Предметы игроков.

| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PRIMARY KEY | ID записи |
| user_id | INTEGER | Владелец |
| item_code | TEXT | Код предмета |
| quantity | INTEGER | Количество |

### 4. shop_config - Магазин
Конфигурация товаров.

| Поле | Тип | Описание |
|------|-----|----------|
| item_code | TEXT PRIMARY KEY | Уникальный код |
| item_name | TEXT | Название |
| category | TEXT | seed/fertilizer/upgrade |
| buy_price | INTEGER | Цена покупки |
| sell_price | INTEGER | Цена продажи |
| growth_time | INTEGER | Время роста (сек) |
| is_seasonal | INTEGER | Сезонный товар |

## Игровые системы

### 5-7. Квесты (quests, user_quests)
- **quests** - Шаблоны квестов
- **user_quests** - Прогресс игроков

### 8-11. Ачивки (achievements, player_achievements)
- **achievement_categories** - Категории
- **achievements** - Шаблоны ачивок
- **player_achievements** - Прогресс игроков
- **user_profile_achievements** - Выбранные ачивки в профиль

### 12-16. Фермеры (farmers, farmer_types)
- **farmer_types** - Типы фермеров
- **farmers** - Нанятые фермеры
- **farmer_config** - Настройки фермеров
- **farmer_logs** - Логи работы

### 17-18. Улучшения (upgrades, user_upgrades)
- **upgrades** - Доступные улучшения
- **user_upgrades** - Купленные улучшения

### 19-21. Промокоды (promocodes, promo_activations)
- **promocodes** - Список промокодов
- **promo_activations** - Активации игроками
- **promo_logs** - Логи использования

### 22-23. Рефералы (referrals, referral_rewards)
- **referrals** - Связи реферрал-приглашенный
- **referral_rewards** - Выданные награды

### 24-25. Переводы (transfers, transfer_limits)
- **transfers** - История переводов
- **transfer_limits** - Лимиты пользователей

### 26-28. Ивенты (seasonal_events)
- **seasonal_events** - Сезонные ивенты
- **event_leaderboard** - Таблица лидеров
- **fertilizer_logs** - Логи удобрений

### 29-30. Ежедневный бонус
- **daily_bonus_config** - Настройки
- **daily_bonus_history** - История получения

## Системные таблицы

### 31-40. Логирование
- **admin_logs** - Действия админов
- **economy_logs** - Экономические операции
- **progression_logs** - Прогресс игроков
- **security_logs** - Безопасность
- **achievement_logs** - Получение ачивок
- **broadcast_history** - История рассылок

### 41-45. Настройки и служебные
- **system_settings** - Глобальные настройки
- **notifications** - Очередь уведомлений
- **admin_roles** - Роли администраторов
- **logs** - Общие логи

## Индексы

Все таблицы имеют индексы для часто используемых полей:
- user_id во всех связанных таблицах
- created_at для логов
- status для активных записей

## Миграции

При обновлении схемы:
1. Использовать `IF NOT EXISTS`
2. Сохранять совместимость
3. Логировать изменения

## Бэкапы

Рекомендуется:
- Ежедневный бэкап в 03:00
- Хранение 7 последних бэкапов
- Отдельный бэкап перед миграциями
