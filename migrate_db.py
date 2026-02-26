#!/usr/bin/env python3
"""
Скрипт миграции базы данных Lazy Farmer v4.0
Автоматически добавляет отсутствующие колонки и таблицы
"""

import asyncio
import aiosqlite
import os

DB_PATH = os.environ.get('DB_PATH', 'farm_v3.db')


async def check_column_exists(db: aiosqlite.Connection, table: str, column: str) -> bool:
    """Проверяет существование колонки в таблице"""
    cursor = await db.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in await cursor.fetchall()]
    return column in columns


async def check_table_exists(db: aiosqlite.Connection, table: str) -> bool:
    """Проверяет существование таблицы"""
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    )
    return await cursor.fetchone() is not None


async def add_column_if_not_exists(db: aiosqlite.Connection, table: str, column: str, 
                                    col_type: str = "INTEGER", default=None):
    """Добавляет колонку если она не существует"""
    if not await check_column_exists(db, table, column):
        try:
            if default is not None:
                await db.execute(
                    f"ALTER TABLE {table} ADD COLUMN {column} {col_type} DEFAULT {default}"
                )
            else:
                await db.execute(
                    f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
                )
            await db.commit()
            print(f"  ✅ Добавлена колонка {column} в {table}")
            return True
        except Exception as e:
            print(f"  ❌ Ошибка добавления {column} в {table}: {e}")
            return False
    else:
        print(f"  ℹ️  Колонка {column} уже существует в {table}")
        return True


async def create_table_if_not_exists(db: aiosqlite.Connection, table: str, schema: str):
    """Создаёт таблицу если она не существует"""
    if not await check_table_exists(db, table):
        try:
            await db.execute(schema)
            await db.commit()
            print(f"  ✅ Создана таблица {table}")
            return True
        except Exception as e:
            print(f"  ❌ Ошибка создания {table}: {e}")
            return False
    else:
        print(f"  ℹ️  Таблица {table} уже существует")
        return True


async def migrate():
    """Основная функция миграции"""
    print("=" * 60)
    print("МИГРАЦИЯ БАЗЫ ДАННЫХ Lazy Farmer v4.0")
    print("=" * 60)
    
    if not os.path.exists(DB_PATH):
        print(f"\n⚠️  База данных {DB_PATH} не найдена!")
        print("Запустите инициализацию: sqlite3 bot.db < data/init_db.sql")
        return
    
    async with aiosqlite.connect(DB_PATH) as db:
        print("\n📋 Проверка колонок...")
        
        # Добавляем is_active в shop_config
        await add_column_if_not_exists(db, 'shop_config', 'is_active', 'INTEGER', 1)
        
        # Добавляем другие потенциально отсутствующие колонки
        await add_column_if_not_exists(db, 'shop_config', 'sort_order', 'INTEGER', 0)
        await add_column_if_not_exists(db, 'shop_config', 'effect_type', 'TEXT')
        await add_column_if_not_exists(db, 'shop_config', 'effect_value', 'REAL')
        await add_column_if_not_exists(db, 'shop_config', 'description', 'TEXT')
        
        print("\n📊 Проверка таблиц...")
        
        # Создаём отсутствующие таблицы
        
        # quest_templates
        await create_table_if_not_exists(db, 'quest_templates', '''
            CREATE TABLE IF NOT EXISTS quest_templates (
                quest_id INTEGER PRIMARY KEY AUTOINCREMENT,
                quest_code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                quest_type TEXT NOT NULL DEFAULT 'daily',
                requirement_type TEXT NOT NULL,
                requirement_value INTEGER NOT NULL DEFAULT 1,
                reward_coins INTEGER DEFAULT 0,
                reward_gems INTEGER DEFAULT 0,
                reward_item_code TEXT,
                reward_item_amount INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # daily_bonus_history
        await create_table_if_not_exists(db, 'daily_bonus_history', '''
            CREATE TABLE IF NOT EXISTS daily_bonus_history (
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                bonus_day INTEGER DEFAULT 1,
                reward_type TEXT NOT NULL,
                reward_amount INTEGER NOT NULL,
                streak_at_claim INTEGER DEFAULT 1,
                claimed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        
        # user_referrals
        await create_table_if_not_exists(db, 'user_referrals', '''
            CREATE TABLE IF NOT EXISTS user_referrals (
                referral_id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL UNIQUE,
                referral_code TEXT,
                referral_level INTEGER DEFAULT 1,
                total_earned_coins INTEGER DEFAULT 0,
                total_earned_gems INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (referrer_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (referred_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        
        # referral_reward_settings
        await create_table_if_not_exists(db, 'referral_reward_settings', '''
            CREATE TABLE IF NOT EXISTS referral_reward_settings (
                reward_id INTEGER PRIMARY KEY AUTOINCREMENT,
                level INTEGER NOT NULL,
                referrer_coins INTEGER DEFAULT 0,
                referrer_gems INTEGER DEFAULT 0,
                referred_coins INTEGER DEFAULT 0,
                referred_gems INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # farmer_logs
        await create_table_if_not_exists(db, 'farmer_logs', '''
            CREATE TABLE IF NOT EXISTS farmer_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                farmer_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                plot_number INTEGER,
                item_code TEXT,
                coins_earned INTEGER DEFAULT 0,
                performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (farmer_id) REFERENCES farmers(farmer_id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        
        print("\n🔍 Проверка индексов...")
        
        # Создаём важные индексы
        indexes = [
            ("idx_plots_user_status", "CREATE INDEX IF NOT EXISTS idx_plots_user_status ON plots(user_id, status)"),
            ("idx_plots_user_ready", "CREATE INDEX IF NOT EXISTS idx_plots_user_ready ON plots(user_id, status) WHERE status = 'ready'"),
            ("idx_player_achievements_progress", "CREATE INDEX IF NOT EXISTS idx_player_achievements_progress ON player_achievements(user_id, completed, reward_claimed)"),
            ("idx_shop_config_category", "CREATE INDEX IF NOT EXISTS idx_shop_config_category ON shop_config(category, is_active)"),
            ("idx_shop_config_active", "CREATE INDEX IF NOT EXISTS idx_shop_config_active ON shop_config(is_active, sort_order)"),
            ("idx_quest_templates_type", "CREATE INDEX IF NOT EXISTS idx_quest_templates_type ON quest_templates(quest_type, is_active)"),
            ("idx_user_referrals_referrer", "CREATE INDEX IF NOT EXISTS idx_user_referrals_referrer ON user_referrals(referrer_id)"),
            ("idx_daily_bonus_history_user", "CREATE INDEX IF NOT EXISTS idx_daily_bonus_history_user ON daily_bonus_history(user_id, claimed_at)"),
        ]
        
        for name, sql in indexes:
            try:
                await db.execute(sql)
                await db.commit()
                print(f"  ✅ Создан индекс {name}")
            except Exception as e:
                print(f"  ⚠️  Индекс {name}: {e}")
        
        print("\n" + "=" * 60)
        print("✅ МИГРАЦИЯ ЗАВЕРШЕНА")
        print("=" * 60)
        print(f"\nБаза данных: {DB_PATH}")
        print("\nТеперь можно запускать бота!")


if __name__ == "__main__":
    asyncio.run(migrate())
