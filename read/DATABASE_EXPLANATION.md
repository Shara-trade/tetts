# Объяснение: SQL файлы vs файл БД

## Разница между файлами

### 1. SQL файлы (схема базы данных)
Это текстовые файлы с SQL-командами для создания структуры базы данных:

- **`data/init_db.sql`** - основной файл инициализации базы данных
- **`data/database_schema_full.sql`** - полная схема с дополнительными таблицами
- **`data/init_db_full.sql`** - альтернативная полная инициализация

**Что они делают:**
- Определяют структуру таблиц (CREATE TABLE)
- Создают индексы (CREATE INDEX)
- Вставляют начальные данные (INSERT INTO)
- Настраивают связи между таблицами (FOREIGN KEY)

**Пример содержимого:**
```sql
CREATE TABLE IF NOT EXISTS admin_roles (
    user_id INTEGER PRIMARY KEY,
    role TEXT CHECK(role IN ('creator', 'admin', 'moderator')),
    assigned_by INTEGER,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
```

### 2. Файл БД (farm_v3.db)
Это бинарный файл SQLite с реальными данными:

- **`farm_v3.db`** - файл базы данных с таблицами и данными

**Что он содержит:**
- Реальные таблицы (созданные из SQL файлов)
- Данные игроков
- Транзакции
- Логи
- и т.д.

## Как таблицы попадают в файл БД

### Способ 1: Через скрипт инициализации
```python
# При запуске бота
import sqlite3

# Читаем SQL файл и выполняем его
with open('data/init_db.sql', 'r', encoding='utf-8') as f:
    sql = f.read()

# Подключаемся к БД и создаем таблицы
conn = sqlite3.connect('farm_v3.db')
conn.executescript(sql)
conn.commit()
conn.close()
```

### Способ 2: Через aiosqlite (используется в проекте)
```python
# В admin/database.py
async def init_from_sql(self, sql_file: str):
    """Выполняет SQL скрипт инициализации"""
    db = await aiosqlite.connect(self.db_path)
    try:
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql = f.read()
        await db.executescript(sql)
        await db.commit()
    finally:
        await db.close()
```

## Таблицы, используемые в админ-панели

### ✅ Правильные таблицы (используются в базе данных):

| Таблица | Описание | SQL файл |
|---------|----------|----------|
| `admin_roles` | Роли администраторов | `data/init_db.sql` |
| `admin_logs` | Логи действий админов | `data/init_db.sql` |
| `shop_config` | Магазин (семена, удобрения) | `data/init_db.sql` |
| `promocodes` | Промокоды | `data/init_db.sql` |
| `users` | Пользователи | `data/init_db.sql` |
| `plots` | Грядки | `data/init_db.sql` |
| `inventory` | Инвентарь | `data/init_db.sql` |

### ❌ Неправильные таблицы (были в коде, исправлены):

| Неправильно | Правильно | Исправлено в |
|-------------|-----------|--------------|
| `admin_users` | `admin_roles` | `admin/admin_panel_full.py` |

## Проверка существования таблиц

### Способ 1: Через Python
```python
import sqlite3

conn = sqlite3.connect('farm_v3.db')
cursor = conn.cursor()

# Получаем список всех таблиц
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

for table in tables:
    print(table[0])

conn.close()
```

### Способ 2: Через SQLite CLI
```bash
sqlite3 farm_v3.db ".tables"
```

### Способ 3: Через aiogram
```python
from admin.database import get_database

async def check_tables():
    db = await get_database()
    rows = await db.fetchall("SELECT name FROM sqlite_master WHERE type='table'")
    print("Таблицы в БД:")
    for row in rows:
        print(f"  - {row[0]}")
```

## Методы в database.py для работы с админами

```python
# Получить роль пользователя
role = await db.get_admin_role(user_id)

# Проверить является ли админом
is_admin = await db.is_admin(user_id)

# Получить список всех админов
admins = await db.get_admins()

# Назначить роль
await db.assign_admin_role(admin_id, target_id, role)

# Удалить роль
await db.remove_admin_role(admin_id, target_id)

# Логировать действие админа
await db.log_admin_action(admin_id, action, target_id, details)
```

## Структура таблицы admin_roles

```sql
CREATE TABLE IF NOT EXISTS admin_roles (
    user_id INTEGER PRIMARY KEY,           -- ID пользователя (Primary Key)
    role TEXT CHECK(role IN ('creator', 'admin', 'moderator')),  -- Роль
    assigned_by INTEGER,                   -- Кто назначил (ID админа)
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- Когда назначили
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
```

### Поля:
- **user_id**: ID пользователя Telegram (уникальный)
- **role**: Роль - creator, admin или moderator
- **assigned_by**: ID админа, который назначил роль
- **assigned_at**: Дата и время назначения

## Структура таблицы admin_logs

```sql
CREATE TABLE IF NOT EXISTS admin_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    target_user_id INTEGER,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (admin_id) REFERENCES users(user_id)
);
```

### Поля:
- **log_id**: Уникальный ID записи
- **admin_id**: ID администратора
- **action**: Тип действия (assign_role, remove_role, ban, give_coins и т.д.)
- **target_user_id**: ID целевого пользователя (если есть)
- **details**: Дополнительная информация (JSON)
- **created_at**: Дата и время действия

## Резюме

1. **SQL файлы** = инструкции для создания структуры БД
2. **Файл БД (farm_v3.db)** = реальная БД с данными
3. **Таблицы создаются** в farm_v3.db при выполнении SQL файлов
4. **Код обращается** к таблицам в farm_v3.db через database.py
5. **Исправления**: В admin_panel_full.py заменены все `admin_users` на `admin_roles`

## Как проверить что все работает

```python
# Проверка таблицы admin_roles
async def test_admin_tables():
    db = await get_database()
    
    # Проверяем существование таблицы
    tables = await db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='admin_roles'"
    )
    
    if tables:
        print("✅ Таблица admin_roles существует")
        
        # Проверяем админов
        admins = await db.get_admins()
        print(f"📋 Всего админов: {len(admins)}")
        for admin in admins:
            print(f"   - {admin['role']}: {admin['username'] or admin['user_id']}")
    else:
        print("❌ Таблица admin_roles не найдена!")
```

## Частые проблемы

### Проблема: "no such table: admin_users"
**Решение:** Используйте `admin_roles` вместо `admin_users`

### Проблема: "no such table: admin_logs"
**Решение:** Запустите инициализацию БД из `data/init_db.sql`

### Проблема: Метод не найден
**Решение:** Проверьте, что метод существует в `admin/database.py`

```python
# Правильно
await db.get_admin_role(user_id)
await db.get_admins()

# Неправильно (такого метода нет)
await db.get_admin_user()
```
