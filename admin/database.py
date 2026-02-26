from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import aiosqlite
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import json
import logging
import os

# Синглтон для базы данных
_db_instance = None
_db_lock = asyncio.Lock()

async def get_database(db_path: str = "farm_v3.db") -> 'Database':
    """Получить единственный экземпляр базы данных"""
    global _db_instance
    async with _db_lock:
        if _db_instance is None:
            _db_instance = Database(db_path)
        return _db_instance

class Database:
    def __init__(self, db_path: str = "farm_v2.db"):
        self.db_path = db_path
        self.lock = asyncio.Lock()
        self._db = None
        # Кэш для ролей админов (user_id -> role)
        self._admin_roles_cache = {}
        # Кэш для категорий ачивок
        self._achievement_categories_cache = None
    
    async def connect(self):
        """Установить соединение с базой данных"""
        if self._db is None:
            self._db = await aiosqlite.connect(self.db_path)
            self._db.row_factory = aiosqlite.Row
        return self._db
    
    async def close(self):
        """Закрыть соединение с базой данных"""
        if self._db:
            await self._db.close()
            self._db = None
    
    async def init_db(self, sql_file_path: str = "data/init_db.sql") -> bool:
        """Инициализация базы данных - создаёт все таблицы"""
        print("🔧 Инициализация БД...")
        
        async with aiosqlite.connect(self.db_path) as db:
            # Таблица users
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    first_name TEXT DEFAULT 'Игрок',
                    username TEXT,
                    balance INTEGER DEFAULT 100,
                    gems INTEGER DEFAULT 0,
                    prestige_level INTEGER DEFAULT 1,
                    prestige_multiplier REAL DEFAULT 1.0,
                    city_level INTEGER DEFAULT 1,
                    total_harvested INTEGER DEFAULT 0,
                    total_planted INTEGER DEFAULT 0,
                    total_earned INTEGER DEFAULT 0,
                    total_spent INTEGER DEFAULT 0,
                    joined_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_activity TEXT DEFAULT CURRENT_TIMESTAMP,
                    is_banned INTEGER DEFAULT 0,
                    settings TEXT DEFAULT '{}'
                )
            ''')
            
            # Таблица plots (с ВСЕМИ колонками)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS plots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    plot_number INTEGER NOT NULL,
                    status TEXT DEFAULT 'empty',
                    crop_type TEXT,
                    planted_time TEXT,
                    growth_time_seconds INTEGER DEFAULT 0,
                    fertilized INTEGER DEFAULT 0,
                    fertilizer_type TEXT,
                    fertilizer_bonus REAL DEFAULT 0.0,
                    UNIQUE(user_id, plot_number)
                )
            ''')
            
            # Таблица inventory
            await db.execute('''
                CREATE TABLE IF NOT EXISTS inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    item_code TEXT NOT NULL,
                    quantity INTEGER DEFAULT 1,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, item_code)
                )
            ''')
            
            # Таблица shop_config
            await db.execute('''
                CREATE TABLE IF NOT EXISTS shop_config (
                    item_code TEXT PRIMARY KEY,
                    item_name TEXT NOT NULL,
                    item_icon TEXT DEFAULT '🌱',
                    category TEXT NOT NULL,
                    buy_price INTEGER DEFAULT 0,
                    sell_price INTEGER DEFAULT 0,
                    growth_time INTEGER DEFAULT 0,
                    required_level INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 1,
                    effect_type TEXT,
                    effect_value REAL,
                    description TEXT
                )
            ''')
            
            # Таблица admin_roles
            await db.execute('''
                CREATE TABLE IF NOT EXISTS admin_roles (
                    user_id INTEGER PRIMARY KEY,
                    role TEXT NOT NULL,
                    assigned_by INTEGER,
                    assigned_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица promocodes
            await db.execute('''
                CREATE TABLE IF NOT EXISTS promocodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    reward_json TEXT NOT NULL,
                    description TEXT,
                    max_uses INTEGER DEFAULT 0,
                    times_used INTEGER DEFAULT 0,
                    valid_from TEXT DEFAULT CURRENT_TIMESTAMP,
                    valid_until TEXT,
                    is_active INTEGER DEFAULT 1
                )
            ''')
            
            # Таблица promo_activations
            await db.execute('''
                CREATE TABLE IF NOT EXISTS promo_activations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    promo_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    activated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(promo_id, user_id)
                )
            ''')
        
            # Таблица admin_logs
            await db.execute('''
                CREATE TABLE IF NOT EXISTS admin_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    target_user_id INTEGER,
                    target_entity_id TEXT,
                    old_value TEXT,
                    new_value TEXT,
                    reason TEXT,
                    details TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица user_daily
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_daily (
                    user_id INTEGER PRIMARY KEY,
                    current_streak INTEGER DEFAULT 0,
                    last_claim_date TEXT
                )
            ''')
                
            # Таблица daily_rewards
            await db.execute('''
                CREATE TABLE IF NOT EXISTS daily_rewards (
                    day_number INTEGER PRIMARY KEY,
                    coins INTEGER DEFAULT 0,
                    gems INTEGER DEFAULT 0,
                    items_json TEXT
                )
            ''')
                
            # Таблица quests
            await db.execute('''
                CREATE TABLE IF NOT EXISTS quests (
                    quest_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    quest_type TEXT NOT NULL,
                    target_item TEXT,
                    target_count INTEGER NOT NULL,
                    description TEXT NOT NULL,
                    reward_coins INTEGER DEFAULT 0,
                    reward_gems INTEGER DEFAULT 0,
                    reward_items_json TEXT,
                    is_daily INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 1
                )
            ''')
                
            # Таблица user_quests
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_quests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    quest_id INTEGER NOT NULL,
                    assigned_date TEXT NOT NULL,
                    progress INTEGER DEFAULT 0,
                    completed INTEGER DEFAULT 0,
                    claimed INTEGER DEFAULT 0,
                    UNIQUE(user_id, quest_id, assigned_date)
                )
            ''')
                
            # Таблица achievement_categories
            await db.execute('''
                CREATE TABLE IF NOT EXISTS achievement_categories (
                    category_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    icon TEXT DEFAULT '🏆',
                    description TEXT,
                    sort_order INTEGER DEFAULT 0
                )
            ''')
                
            # Таблица achievements
            await db.execute('''
                CREATE TABLE IF NOT EXISTS achievements (
                    achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    icon TEXT DEFAULT '🏆',
                    category_id TEXT NOT NULL,
                    requirement_type TEXT NOT NULL,
                    requirement_count INTEGER NOT NULL,
                    reward_coins INTEGER DEFAULT 0,
                    reward_gems INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1
                )
            ''')
            
            # Таблица player_achievements
            await db.execute('''
                CREATE TABLE IF NOT EXISTS player_achievements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    achievement_id INTEGER NOT NULL,
                    progress INTEGER DEFAULT 0,
                    completed INTEGER DEFAULT 0,
                    reward_claimed INTEGER DEFAULT 0,
                    completed_at TEXT,
                    claimed_at TEXT,
                    UNIQUE(user_id, achievement_id)
                )
            ''')
                
            # Таблица notifications
            await db.execute('''
                CREATE TABLE IF NOT EXISTS notifications (
                    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    sent INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
                
            # Таблица economy_logs
            await db.execute('''
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
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
                
            # Таблица farmers
            await db.execute('''
                CREATE TABLE IF NOT EXISTS farmers (
                    farmer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    farmer_type TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    bonus_percent INTEGER DEFAULT 0,
                    uses_fertilizer INTEGER DEFAULT 0,
                    hired_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT,
                    last_work TEXT,
                    total_planted INTEGER DEFAULT 0,
                    total_harvested INTEGER DEFAULT 0,
                    total_earned INTEGER DEFAULT 0,
                    total_salary_paid INTEGER DEFAULT 0
                )
            ''')
                
            # Таблица farmer_types
            await db.execute('''
                CREATE TABLE IF NOT EXISTS farmer_types (
                    type_code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    icon TEXT DEFAULT '👤',
                    description TEXT,
                    duration_days INTEGER,
                    price_coins INTEGER DEFAULT 0,
                    price_gems INTEGER DEFAULT 0,
                    bonus_percent INTEGER DEFAULT 0,
                    salary_per_hour INTEGER DEFAULT 0,
                    work_interval_seconds INTEGER DEFAULT 60,
                    is_active INTEGER DEFAULT 1
                )
            ''')
            
            # Таблица upgrades
            await db.execute('''
                CREATE TABLE IF NOT EXISTS upgrades (
                    upgrade_code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    icon TEXT DEFAULT '⬆️',
                    description TEXT,
                    category TEXT NOT NULL,
                    max_level INTEGER DEFAULT 10,
                    base_price INTEGER DEFAULT 1000,
                    price_multiplier REAL DEFAULT 1.5,
                    effect_type TEXT NOT NULL,
                    effect_value REAL DEFAULT 0.1,
                    required_prestige INTEGER DEFAULT 20,
                    is_active INTEGER DEFAULT 1
                )
            ''')
                
            # Таблица user_upgrades
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_upgrades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    upgrade_code TEXT NOT NULL,
                    current_level INTEGER DEFAULT 0,
                    total_spent INTEGER DEFAULT 0,
                    UNIQUE(user_id, upgrade_code)
                )
            ''')
                
            # Таблица seasonal_events
            await db.execute('''
                CREATE TABLE IF NOT EXISTS seasonal_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    season TEXT,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    multiplier REAL DEFAULT 1.0,
                    is_active INTEGER DEFAULT 1
                )
            ''')
            
            # Таблица event_leaderboard
            await db.execute('''
                CREATE TABLE IF NOT EXISTS event_leaderboard (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    score INTEGER DEFAULT 0,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(event_id, user_id)
                )
            ''')
                
            # Таблица system_settings
            await db.execute('''
                CREATE TABLE IF NOT EXISTS system_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    description TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
                
            # Таблица referrals
            await db.execute('''
                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_id INTEGER NOT NULL,
                    referred_id INTEGER NOT NULL,
                    joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(referrer_id, referred_id)
                )
            ''')
                
            # Таблица referral_rewards
            await db.execute('''
                CREATE TABLE IF NOT EXISTS referral_rewards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_id INTEGER NOT NULL,
                    referred_id INTEGER NOT NULL,
                    reward_type TEXT NOT NULL,
                    reward_coins INTEGER DEFAULT 0,
                    reward_gems INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
                
            # Таблица transfers
            await db.execute('''
                CREATE TABLE IF NOT EXISTS transfers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id INTEGER NOT NULL,
                    receiver_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    fee INTEGER DEFAULT 0,
                    total_amount INTEGER NOT NULL,
                    status TEXT DEFAULT 'completed',
                    description TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
                
            # Таблица transfer_limits
            await db.execute('''
                CREATE TABLE IF NOT EXISTS transfer_limits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    daily_limit INTEGER DEFAULT 0,
                    base_percentage REAL DEFAULT 0.20,
                    prestige_bonus REAL DEFAULT 0.0,
                    used_today INTEGER DEFAULT 0,
                    last_reset TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
                
            # Таблица achievement_logs (логи получения достижений)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS achievement_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    achievement_id INTEGER NOT NULL,
                    level INTEGER DEFAULT 1,
                    progress_before INTEGER DEFAULT 0,
                    progress_after INTEGER,
                    completed INTEGER DEFAULT 0,
                    action TEXT,
                    reward_claimed TEXT,
                    reward_coins INTEGER DEFAULT 0,
                    reward_gems INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
                
            await db.commit()
        
        # Запускаем миграции для старых БД
        await self._migrate_database()
        
        print("✅ Все таблицы созданы!")
        return True
    
    async def _migrate_database(self):
        """Выполняет миграции базы данных - добавляет недостающие колонки во все таблицы"""
        db = await self.connect()
        
        try:
            logging.info("🔧 Начинаем миграцию базы данных...")
            
            # ========== МИГРАЦИЯ ТАБЛИЦЫ PLOTS ==========
            try:
                cursor = await db.execute("PRAGMA table_info(plots)")
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                plots_migrations = [
                    ('fertilized', 'INTEGER DEFAULT 0'),
                    ('fertilizer_type', 'TEXT'),
                    ('fertilizer_bonus', 'REAL DEFAULT 0.0'),
                ]
                
                for col_name, col_type in plots_migrations:
                    if col_name not in column_names:
                        await db.execute(f"ALTER TABLE plots ADD COLUMN {col_name} {col_type}")
                        await db.commit()
                        logging.info(f"✅ plots: добавлена колонка {col_name}")
            except Exception as e:
                logging.warning(f"⚠️ Ошибка миграции plots: {e}")
            
            # ========== МИГРАЦИЯ ТАБЛИЦЫ USERS ==========
            try:
                cursor = await db.execute("PRAGMA table_info(users)")
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                users_migrations = [
                    ('settings', "TEXT DEFAULT '{}'"),
                    ('first_name', "TEXT DEFAULT 'Игрок'"),
                    ('total_spent', 'INTEGER DEFAULT 0'),
                    ('gems', 'INTEGER DEFAULT 0'),
                ]
                
                for col_name, col_type in users_migrations:
                    if col_name not in column_names:
                        await db.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                        await db.commit()
                        logging.info(f"✅ users: добавлена колонка {col_name}")
            except Exception as e:
                logging.warning(f"⚠️ Ошибка миграции users: {e}")
            
            # ========== МИГРАЦИЯ ТАБЛИЦЫ SHOP_CONFIG ==========
            try:
                cursor = await db.execute("PRAGMA table_info(shop_config)")
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                shop_migrations = [
                    ('item_icon', "TEXT DEFAULT '🌱'"),
                    ('yield_amount', 'INTEGER DEFAULT 1'),
                    ('required_level', 'INTEGER DEFAULT 1'),
                    ('exp_reward', 'INTEGER DEFAULT 10'),
                    ('sort_order', 'INTEGER DEFAULT 0'),
                    ('is_seasonal', 'INTEGER DEFAULT 0'),
                    ('season', 'TEXT'),
                    ('effect_type', 'TEXT'),
                    ('effect_value', 'REAL'),
                    ('description', 'TEXT'),
                    ('created_at', 'TEXT DEFAULT CURRENT_TIMESTAMP'),
                    ('created_by', 'INTEGER'),
                ]
                
                for col_name, col_type in shop_migrations:
                    if col_name not in column_names:
                        await db.execute(f"ALTER TABLE shop_config ADD COLUMN {col_name} {col_type}")
                        await db.commit()
                        logging.info(f"✅ shop_config: добавлена колонка {col_name}")
            except Exception as e:
                logging.warning(f"⚠️ Ошибка миграции shop_config: {e}")
            
            # ========== МИГРАЦИЯ ТАБЛИЦЫ NOTIFICATIONS ==========
            try:
                cursor = await db.execute("PRAGMA table_info(notifications)")
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                if 'user_id' not in column_names:
                    # Если нет user_id, нужно добавить и создать правильную структуру
                    await db.execute(f"ALTER TABLE notifications ADD COLUMN user_id INTEGER")
                    await db.commit()
                    logging.info(f"✅ notifications: добавлена колонка user_id")
            except Exception as e:
                logging.warning(f"⚠️ Ошибка миграции notifications: {e}")
            
            # ========== МИГРАЦИЯ ТАБЛИЦЫ QUESTS ==========
            try:
                cursor = await db.execute("PRAGMA table_info(quests)")
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                quests_migrations = [
                    ('reward_gems', 'INTEGER DEFAULT 0'),
                    ('is_weekly', 'INTEGER DEFAULT 0'),
                    ('sort_order', 'INTEGER DEFAULT 0'),
                ]
                
                for col_name, col_type in quests_migrations:
                    if col_name not in column_names:
                        await db.execute(f"ALTER TABLE quests ADD COLUMN {col_name} {col_type}")
                        await db.commit()
                        logging.info(f"✅ quests: добавлена колонка {col_name}")
            except Exception as e:
                logging.warning(f"⚠️ Ошибка миграции quests: {e}")
            
            # ========== МИГРАЦИЯ ТАБЛИЦЫ USER_DAILY ==========
            try:
                cursor = await db.execute("PRAGMA table_info(user_daily)")
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                if 'last_claim_date' not in column_names:
                    await db.execute("ALTER TABLE user_daily ADD COLUMN last_claim_date TEXT")
                    await db.commit()
                    logging.info(f"✅ user_daily: добавлена колонка last_claim_date")
            except Exception as e:
                logging.warning(f"⚠️ Ошибка миграции user_daily: {e}")
            
            # ========== МИГРАЦИЯ ТАБЛИЦЫ DAILY_REWARDS ==========
            try:
                cursor = await db.execute("PRAGMA table_info(daily_rewards)")
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                if 'gems' not in column_names:
                    await db.execute("ALTER TABLE daily_rewards ADD COLUMN gems INTEGER DEFAULT 0")
                    await db.commit()
                    logging.info(f"✅ daily_rewards: добавлена колонка gems")
            except Exception as e:
                logging.warning(f"⚠️ Ошибка миграции daily_rewards: {e}")
            
            # ========== МИГРАЦИЯ ТАБЛИЦЫ ACHIEVEMENTS ==========
            try:
                cursor = await db.execute("PRAGMA table_info(achievements)")
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                achievements_migrations = [
                    ('achievement_type', "TEXT DEFAULT 'regular'"),
                    ('parent_achievement_id', 'INTEGER'),
                    ('level', 'INTEGER DEFAULT 1'),
                    ('event_end_date', 'TEXT'),
                    ('requirement_item', 'TEXT'),
                    ('reward_items_json', "TEXT DEFAULT '{}'"),
                    ('reward_multiplier', 'REAL DEFAULT 0'),
                    ('is_secret', 'INTEGER DEFAULT 0'),
                    ('sort_order', 'INTEGER DEFAULT 0'),
                    ('created_at', 'TEXT DEFAULT CURRENT_TIMESTAMP'),
                    ('updated_at', 'TEXT DEFAULT CURRENT_TIMESTAMP'),
                ]
                
                for col_name, col_type in achievements_migrations:
                    if col_name not in column_names:
                        await db.execute(f"ALTER TABLE achievements ADD COLUMN {col_name} {col_type}")
                        await db.commit()
                        logging.info(f"✅ achievements: добавлена колонка {col_name}")
            except Exception as e:
                logging.warning(f"⚠️ Ошибка миграции achievements: {e}")
            
            # ========== МИГРАЦИЯ ТАБЛИЦЫ PLAYER_ACHIEVEMENTS ==========
            try:
                cursor = await db.execute("PRAGMA table_info(player_achievements)")
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                player_ach_migrations = [
                    ('notified', 'INTEGER DEFAULT 0'),
                    ('created_at', 'TEXT DEFAULT CURRENT_TIMESTAMP'),
                    ('updated_at', 'TEXT DEFAULT CURRENT_TIMESTAMP'),
                ]
                
                for col_name, col_type in player_ach_migrations:
                    if col_name not in column_names:
                        await db.execute(f"ALTER TABLE player_achievements ADD COLUMN {col_name} {col_type}")
                        await db.commit()
                        logging.info(f"✅ player_achievements: добавлена колонка {col_name}")
            except Exception as e:
                logging.warning(f"⚠️ Ошибка миграции player_achievements: {e}")
            
            logging.info("✅ Миграции базы данных завершены!")
            
        except Exception as e:
            logging.error(f"❌ Критическая ошибка миграции: {e}")

    async def _create_basic_tables(self):
        """Создаёт базовые таблицы если SQL файл недоступен"""
        db = await self.connect()
        
        # Базовые таблицы
        await db.executescript('''
            PRAGMA foreign_keys = ON;
            
            -- Таблица пользователей
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT DEFAULT 'Игрок',
                username TEXT,
                balance INTEGER DEFAULT 100,
                gems INTEGER DEFAULT 0,
                prestige_level INTEGER DEFAULT 1,
                prestige_multiplier REAL DEFAULT 1.0,
                city_level INTEGER DEFAULT 1,
                total_harvested INTEGER DEFAULT 0,
                total_planted INTEGER DEFAULT 0,
                total_earned INTEGER DEFAULT 0,
                total_spent INTEGER DEFAULT 0,
                joined_date TEXT DEFAULT CURRENT_TIMESTAMP,
                last_activity TEXT DEFAULT CURRENT_TIMESTAMP,
                is_banned INTEGER DEFAULT 0,
                settings TEXT DEFAULT '{}'
            );
            
            -- Таблица администраторов
            CREATE TABLE IF NOT EXISTS admin_roles (
                user_id INTEGER PRIMARY KEY,
                role TEXT NOT NULL,
                assigned_by INTEGER,
                assigned_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Таблица инвентаря
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                item_code TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, item_code)
            );
            
            -- Таблица магазина
            CREATE TABLE IF NOT EXISTS shop_config (
                item_code TEXT PRIMARY KEY,
                item_name TEXT NOT NULL,
                item_icon TEXT DEFAULT '🌱',
                category TEXT NOT NULL,
                buy_price INTEGER DEFAULT 0,
                sell_price INTEGER DEFAULT 0,
                growth_time INTEGER DEFAULT 0,
                required_level INTEGER DEFAULT 1,
                is_active INTEGER DEFAULT 1,
                effect_type TEXT,
                effect_value REAL,
                description TEXT
            );
            
            -- Таблица грядок
            CREATE TABLE IF NOT EXISTS plots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                plot_number INTEGER NOT NULL,
                status TEXT DEFAULT 'empty',
                crop_type TEXT,
                planted_time TEXT,
                growth_time_seconds INTEGER DEFAULT 0,
                fertilized INTEGER DEFAULT 0,
                fertilizer_type TEXT,
                fertilizer_bonus REAL DEFAULT 0.0,
                UNIQUE(user_id, plot_number)
            );
            
            -- Таблица промокодов
            CREATE TABLE IF NOT EXISTS promocodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                reward_json TEXT NOT NULL,
                description TEXT,
                max_uses INTEGER DEFAULT 0,
                times_used INTEGER DEFAULT 0,
                valid_from TEXT DEFAULT CURRENT_TIMESTAMP,
                valid_until TEXT,
                is_active INTEGER DEFAULT 1
            );
            
            -- Таблица активаций промокодов
            CREATE TABLE IF NOT EXISTS promo_activations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                promo_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                activated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(promo_id, user_id)
            );
            
            -- Таблица логов админов
            CREATE TABLE IF NOT EXISTS admin_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                target_user_id INTEGER,
                target_entity_id TEXT,
                old_value TEXT,
                new_value TEXT,
                reason TEXT,
                details TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Таблица ежедневных бонусов
            CREATE TABLE IF NOT EXISTS user_daily (
                user_id INTEGER PRIMARY KEY,
                current_streak INTEGER DEFAULT 0,
                last_claim_date TEXT
            );
            
            -- Таблица конфигурации ежедневных бонусов
            CREATE TABLE IF NOT EXISTS daily_rewards (
                day_number INTEGER PRIMARY KEY,
                coins INTEGER DEFAULT 0,
                gems INTEGER DEFAULT 0,
                items_json TEXT
            );
            
            -- Таблица квестов
            CREATE TABLE IF NOT EXISTS quests (
                quest_id INTEGER PRIMARY KEY AUTOINCREMENT,
                quest_type TEXT NOT NULL,
                target_item TEXT,
                target_count INTEGER NOT NULL,
                description TEXT NOT NULL,
                reward_coins INTEGER DEFAULT 0,
                reward_gems INTEGER DEFAULT 0,
                reward_items_json TEXT,
                is_daily INTEGER DEFAULT 1,
                is_active INTEGER DEFAULT 1
            );
            
            -- Таблица прогресса квестов
            CREATE TABLE IF NOT EXISTS user_quests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                quest_id INTEGER NOT NULL,
                assigned_date TEXT NOT NULL,
                progress INTEGER DEFAULT 0,
                completed INTEGER DEFAULT 0,
                claimed INTEGER DEFAULT 0,
                UNIQUE(user_id, quest_id, assigned_date)
            );
            
            -- Таблица категорий достижений
            CREATE TABLE IF NOT EXISTS achievement_categories (
                category_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                icon TEXT DEFAULT '🏆',
                description TEXT,
                sort_order INTEGER DEFAULT 0
            );
            
            -- Таблица достижений
            CREATE TABLE IF NOT EXISTS achievements (
                achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                icon TEXT DEFAULT '🏆',
                category_id TEXT NOT NULL,
                requirement_type TEXT NOT NULL,
                requirement_count INTEGER NOT NULL,
                reward_coins INTEGER DEFAULT 0,
                reward_gems INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1
            );
            
            -- Таблица прогресса достижений
            CREATE TABLE IF NOT EXISTS player_achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                achievement_id INTEGER NOT NULL,
                progress INTEGER DEFAULT 0,
                completed INTEGER DEFAULT 0,
                reward_claimed INTEGER DEFAULT 0,
                completed_at TEXT,
                claimed_at TEXT,
                UNIQUE(user_id, achievement_id)
            );
            
            -- Таблица уведомлений
            CREATE TABLE IF NOT EXISTS notifications (
                notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                message TEXT NOT NULL,
                sent INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Таблица экономических логов
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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Таблица фермеров
            CREATE TABLE IF NOT EXISTS farmers (
                farmer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                farmer_type TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                bonus_percent INTEGER DEFAULT 0,
                uses_fertilizer INTEGER DEFAULT 0,
                hired_at TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT,
                last_work TEXT,
                total_planted INTEGER DEFAULT 0,
                total_harvested INTEGER DEFAULT 0,
                total_earned INTEGER DEFAULT 0,
                total_salary_paid INTEGER DEFAULT 0
            );
            
            -- Таблица типов фермеров
            CREATE TABLE IF NOT EXISTS farmer_types (
                type_code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                icon TEXT DEFAULT '👤',
                description TEXT,
                duration_days INTEGER,
                price_coins INTEGER DEFAULT 0,
                price_gems INTEGER DEFAULT 0,
                bonus_percent INTEGER DEFAULT 0,
                salary_per_hour INTEGER DEFAULT 0,
                work_interval_seconds INTEGER DEFAULT 60,
                is_active INTEGER DEFAULT 1
            );
            
            -- Таблица улучшений
            CREATE TABLE IF NOT EXISTS upgrades (
                upgrade_code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                icon TEXT DEFAULT '⬆️',
                description TEXT,
                category TEXT NOT NULL,
                max_level INTEGER DEFAULT 10,
                base_price INTEGER DEFAULT 1000,
                price_multiplier REAL DEFAULT 1.5,
                effect_type TEXT NOT NULL,
                effect_value REAL DEFAULT 0.1,
                required_prestige INTEGER DEFAULT 20,
                is_active INTEGER DEFAULT 1
            );
            
            -- Таблица уровней улучшений игроков
            CREATE TABLE IF NOT EXISTS user_upgrades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                upgrade_code TEXT NOT NULL,
                current_level INTEGER DEFAULT 0,
                total_spent INTEGER DEFAULT 0,
                UNIQUE(user_id, upgrade_code)
            );
            
            -- Таблица сезонных событий
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
            
            -- Таблица лидерборда событий
            CREATE TABLE IF NOT EXISTS event_leaderboard (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                score INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(event_id, user_id)
            );
            
            -- Таблица системных настроек
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                description TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Таблица рефералов
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL,
                joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(referrer_id, referred_id)
            );
            
            -- Таблица наград рефералов
            CREATE TABLE IF NOT EXISTS referral_rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL,
                reward_type TEXT NOT NULL,
                reward_coins INTEGER DEFAULT 0,
                reward_gems INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Таблица переводов
            CREATE TABLE IF NOT EXISTS transfers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                fee INTEGER DEFAULT 0,
                total_amount INTEGER NOT NULL,
                status TEXT DEFAULT 'completed',
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Таблица лимитов переводов
            CREATE TABLE IF NOT EXISTS transfer_limits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                daily_limit INTEGER DEFAULT 0,
                base_percentage REAL DEFAULT 0.20,
                prestige_bonus REAL DEFAULT 0.0,
                used_today INTEGER DEFAULT 0,
                last_reset TEXT DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Начальные данные
            INSERT OR IGNORE INTO system_settings (key, value, description) VALUES
            ('start_balance', '100', 'Стартовый баланс новых игроков'),
            ('max_plots', '6', 'Максимальное количество грядок'),
            ('referral_bonus', '50', 'Бонус за приглашение друга');
            
            INSERT OR IGNORE INTO farmer_types (type_code, name, icon, description, duration_days, price_coins, price_gems, bonus_percent, salary_per_hour, work_interval_seconds) VALUES
            ('basic', 'Базовый фермер', '👤', 'Автоматически сажает и собирает урожай', 7, 5000, 0, 0, 50, 300),
            ('experienced', 'Опытный фермер', '👨‍🌾', 'Все функции + 10% к доходу', 30, 0, 50, 10, 100, 180),
            ('pro', 'Профи фермер', '👩‍🌾', 'Все функции + 25% к доходу + удобрения', NULL, 0, 200, 25, 200, 120);
            
            INSERT OR IGNORE INTO daily_rewards (day_number, coins, gems, items_json) VALUES
            (1, 100, 0, '[]'),
            (2, 150, 0, '[]'),
            (3, 200, 0, '[]'),
            (4, 250, 1, '[]'),
            (5, 300, 0, '[]'),
            (6, 400, 2, '{"fertilizer": 3}'),
            (7, 500, 5, '{"water_can": 1}');
            
            INSERT OR IGNORE INTO achievement_categories (category_id, name, icon, description) VALUES
            ('harvest', 'Урожай', '🌾', 'Собирайте урожай'),
            ('planting', 'Посадка', '🌱', 'Сажайте культуры'),
            ('economy', 'Экономика', '💰', 'Зарабатывайте монеты'),
            ('social', 'Социальное', '👥', 'Взаимодействуйте с другими'),
            ('special', 'Особое', '⭐', 'Уникальные достижения');
        ''')
        
        await db.commit()
        logging.info("✅ Базовые таблицы созданы")
    
    async def execute(self, query: str, params=(), commit=False):
        async with self.lock:
            db = await self.connect()
            await db.execute(query, params)
            if commit:
                await db.commit()
                
    async def fetchall(self, query: str, params=()):
        async with self.lock:
            db = await self.connect()
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [tuple(row) for row in rows]
    
    async def fetchone(self, query: str, params=()):
        async with self.lock:
            db = await self.connect()
            async with db.execute(query, params) as cursor:
                row = await cursor.fetchone()
                return tuple(row) if row else None
    
    # Пользователи
    async def create_user(self, user_id: int, username: str, first_name: str):
        await self.execute(
            """INSERT OR IGNORE INTO users (user_id, username, first_name) 
               VALUES (?, ?, ?)""", (user_id, username, first_name), commit=True
        )
        # Создать 4 грядки
        for i in range(1, 5):
            await self.execute(
                "INSERT OR IGNORE INTO plots (user_id, plot_number) VALUES (?, ?)",
                (user_id, i), commit=True
            )
        # Создать user_daily
        await self.execute(
            "INSERT OR IGNORE INTO user_daily (user_id) VALUES (?)",
            (user_id,), commit=True
        )
        
    async def get_user(self, user_id: int) -> Optional[Dict]:
        # Явно указываем поля в нужном порядке вместо SELECT *
        row = await self.fetchone(
            """SELECT user_id, first_name, username, balance, gems, 
                prestige_level, prestige_multiplier, xp, level, city_level,
                total_harvested, total_planted, total_earned, total_spent,
                joined_date, last_activity, is_banned, ban_reason, ban_until,
                last_daily_claim, daily_streak, settings, selected_achievements
            FROM users WHERE user_id = ? AND is_banned = 0""", 
            (user_id,)
        )
        if row:
            # Парсим settings JSON
            settings = {}
            if row[21]:  # settings column
                try:
                    settings = json.loads(row[21])
                except (json.JSONDecodeError, TypeError):
                    settings = {}
            
            # Парсим selected_achievements JSON
            selected_achievements = []
            if row[22]:  # selected_achievements column
                try:
                    selected_achievements = json.loads(row[22])
                except (json.JSONDecodeError, TypeError):
                    selected_achievements = []
        
            return {
                "user_id": row[0],
                "first_name": row[1] or 'Игрок', 
                "username": row[2],
                "balance": row[3] or 0, 
                "gems": row[4] or 0,
                "prestige_level": row[5] or 1, 
                "prestige_multiplier": row[6] or 1.0,
                "xp": row[7] or 0,
                "level": row[8] or 1,
                "city_level": row[9] or 1, 
                "total_harvested": row[10] or 0,
                "total_planted": row[11] or 0, 
                "total_earned": row[12] or 0, 
                "total_spent": row[13] or 0,
                "joined_date": row[14],
                "last_activity": row[15],
                "is_banned": row[16] or 0,
                "daily_streak": row[20] or 0,
                "settings": settings,
                "selected_achievements": selected_achievements
            }
        return None
    
    async def update_user_settings(self, user_id: int, settings: Dict) -> bool:
        """Обновляет настройки пользователя
        
        Args:
            user_id: ID пользователя
            settings: Словарь с настройками
            
        Returns:
            True если успешно, False если пользователь не найден
        """
        # Проверяем существование пользователя
        user = await self.get_user(user_id)
        if not user:
            return False
        
        # Сериализуем настройки в JSON
        settings_json = json.dumps(settings)
        
        # Пробуем обновить поле settings
        try:
            await self.execute(
                "UPDATE users SET settings = ? WHERE user_id = ?",
                (settings_json, user_id), commit=True
            )
            return True
        except Exception as e:
            # Если поля settings нет, добавляем его через ALTER TABLE
            logging.warning(f"Settings column not found, attempting to add: {e}")
            try:
                await self.execute(
                    "ALTER TABLE users ADD COLUMN settings TEXT DEFAULT '{}'",
                    commit=True
                )
                await self.execute(
                    "UPDATE users SET settings = ? WHERE user_id = ?",
                    (settings_json, user_id), commit=True
                )
                return True
            except Exception as alter_error:
                logging.error(f"Failed to add settings column: {alter_error}")
                return False
    
    async def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Поиск пользователя по username (без @)"""
        row = await self.fetchone(
            "SELECT * FROM users WHERE username = ? AND is_banned = 0", (username,)
        )
        if row:
            return {
                "user_id": row[0], "username": row[1], "first_name": row[2],
                "balance": row[3], "gems": row[4],
                "prestige_level": row[5], "prestige_multiplier": row[6],
                "city_level": row[7], "total_harvested": row[8],
                "total_planted": row[9], "total_earned": row[10], "total_spent": row[11]
            }
        return None
        
    async def update_balance(self, user_id: int, amount: int, transaction: bool = True) -> Optional[int]:
        """Обновляет баланс пользователя с проверкой на отрицательный баланс

        Args:
            user_id: ID пользователя
            amount: Сумма для добавления (может быть отрицательной)
            transaction: Использовать транзакцию (по умолчанию True)

        Returns:
            Новый баланс или None при ошибке
        """
        async with self.lock:
            db = await self.connect()
            await db.execute("BEGIN")
            try:
                user = await self.get_user(user_id)
                if not user:
                    await db.rollback()
                    return None
                
                current_balance = user.get("balance", 0)
                new_balance = current_balance + amount
                
                # Проверка на отрицательный баланс
                if new_balance < 0:
                    await db.rollback()
                    logging.warning(f"Insufficient funds for user {user_id}: {current_balance} + {amount} = {new_balance}")
                    return None
                
                await db.execute(
                    "UPDATE users SET balance = ?, last_activity = CURRENT_TIMESTAMP WHERE user_id = ?",
                    (new_balance, user_id)
                )
                await db.commit()

                # Логирование транзакции
                action = 'spend' if amount < 0 else 'earn'
                await self.log_economy(
                    user_id, action, 'coins', abs(amount), new_balance,
                    'balance_update', None, f"Balance {'decreased' if amount < 0 else 'increased'} by {abs(amount)}"
                )
                
                return new_balance
            except Exception as e:
                await db.rollback()
                logging.error(f"Error updating balance for user {user_id}: {e}")
                raise
    
    async def update_prestige(self, user_id: int, level: int, multiplier: float):
        await self.execute(
            "UPDATE users SET prestige_level = ?, prestige_multiplier = ?, city_level = ? WHERE user_id = ?",
            (level, multiplier, level, user_id), commit=True
        )
        
    async def log_economy(self, user_id: int, action: str, currency: str, amount: int, 
                          balance_after: int, source: str, item_code: str = None, description: str = None):
        """Логирует экономические транзакции

        Args:
            user_id: ID пользователя
            action: Тип действия (earn, spend, harvest, plant)
            currency: Валюта (coins, gems)
            amount: Сумма транзакции
            balance_after: Баланс после транзакции
            source: Источник транзакции
            item_code: Код предмета (опционально)
            description: Описание (опционально)
        """
        try:
            await self.execute(
                """INSERT INTO economy_logs 
                   (user_id, action, currency, amount, balance_after, source, item_code, description, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (user_id, action, currency, amount, balance_after, source, item_code, description),
                commit=True
            )
        except Exception as e:
            logging.error(f"Error logging economy transaction: {e}")

    # Грядки
    async def get_plots(self, user_id: int) -> List[Dict]:
        # Сначала обновим созревшие грядки
        await self._update_ready_plots(user_id)
        
        rows = await self.fetchall(
            """SELECT plot_number, status, crop_type, planted_time, growth_time_seconds,
                      fertilized, fertilizer_type, fertilizer_bonus
               FROM plots WHERE user_id = ? ORDER BY plot_number""", (user_id,)
        )
        plots = []
        now = datetime.now()
        for row in rows:
            plot = {
                "number": row[0], 
                "status": row[1],
                "fertilized": bool(row[5]),
                "fertilizer_type": row[6],
                "fertilizer_bonus": row[7] or 0.0
            }
            if row[1] == "growing":
                planted = datetime.fromisoformat(row[3])
                remaining = max(0, (planted + timedelta(seconds=row[4]) - now).total_seconds())
                plot.update({
                    "crop_type": row[2],
                    "remaining_time": int(remaining),
                    "ready": remaining == 0
                })
            elif row[1] == "ready":
                plot.update({
                    "crop_type": row[2],
                    "ready": True
                })
            plots.append(plot)
        return plots
        
    async def _update_ready_plots(self, user_id: int):
        """Обновляет статус грядок, у которых прошло время роста"""
        await self.execute(
            """UPDATE plots 
               SET status = 'ready' 
               WHERE user_id = ? 
               AND status = 'growing' 
               AND datetime(planted_time, '+' || growth_time_seconds || ' seconds') <= datetime('now')""",
            (user_id,), commit=True
        )
        
    async def plant_crop(self, user_id: int, plot_number: int, crop_type: str, growth_time: int):
        await self.execute(
            """UPDATE plots SET status = 'growing', crop_type = ?, 
               planted_time = CURRENT_TIMESTAMP, growth_time_seconds = ? 
               WHERE user_id = ? AND plot_number = ? AND status = 'empty'""",
            (crop_type, growth_time, user_id, plot_number), commit=True
        )
        
    async def harvest_plots(self, user_id: int, multiplier: float = None) -> Dict:
        """Собирает урожай и возвращает информацию о собранном

        Args:
            user_id: ID пользователя
            multiplier: Множитель награды (если None, берётся из пользователя)

        Returns:
            Dict с полями:
                - success: bool - успешность операции
                - total: int - общая сумма заработка
                - harvested_count: int - количество собранных грядок
                - crops: List[Dict] - список собранных культур
        """
        async with self.lock:
            db = await self.connect()
            await db.execute("BEGIN")
            try:
                # Получить готовые грядки с учётом удобрений
                async with db.execute(
                    """SELECT p.plot_number, p.crop_type, s.sell_price, s.item_icon,
                              p.fertilized, p.fertilizer_type, p.fertilizer_bonus
                       FROM plots p JOIN shop_config s ON p.crop_type = s.item_code 
                       WHERE p.user_id = ? AND p.status = 'ready'""", (user_id,)
                ) as cursor:
                    rows = await cursor.fetchall()
                
                if not rows:
                    await db.commit()
                    return {"success": True, "total": 0, "harvested_count": 0, "crops": []}

                # Получаем множитель
                if multiplier is None:
                    user = await self.get_user(user_id)
                    if not user:
                        await db.rollback()
                        return {"success": False, "error": "User not found"}
                    multiplier = user["prestige_multiplier"]

                # Проверяем множитель
                if multiplier <= 0:
                    multiplier = 1.0

                total = 0
                crops = []
                for row in rows:
                    plot_num, crop_type, sell_price, icon = row[0], row[1], row[2], row[3]
                    fertilized = bool(row[4])
                    fertilizer_type = row[5]
                    fertilizer_bonus = row[6] or 0.0
                    
                    # Рассчитываем доход с учётом множителя и бонуса от удобрения
                    base_earned = sell_price * multiplier
                    bonus_multiplier = 1.0 + fertilizer_bonus
                    earned = int(base_earned * bonus_multiplier)
                    total += earned
                    
                    crops.append({
                        "plot_number": plot_num,
                        "crop_type": crop_type,
                        "sell_price": sell_price,
                        "earned": earned,
                        "icon": icon,
                        "fertilized": fertilized,
                        "fertilizer_bonus": fertilizer_bonus
                    })

                # Обновить баланс и сбросить грядки (включая удобрения)
                await db.execute(
                    "UPDATE users SET balance = balance + ?, total_harvested = total_harvested + ?, last_activity = CURRENT_TIMESTAMP WHERE user_id = ?",
                    (total, len(rows), user_id)
                )
                # Сбрасываем грядки включая данные об удобрениях
                await db.execute(
                    """UPDATE plots SET status = 'empty', crop_type = NULL, planted_time = NULL, 
                       growth_time_seconds = NULL, fertilized = 0, fertilizer_type = NULL, 
                       fertilizer_bonus = 0.0 
                       WHERE user_id = ? AND status = 'ready'""",
                    (user_id,)
                )
                
                # ==================== СЕЗОННЫЕ ИВЕНТЫ (ТЗ v4.0 п.16) ====================
                # Проверяем активные ивенты и начисляем очки/предметы
                active_events = await self.get_active_events()
                event_points_earned = 0
                event_items_earned = []
                
                for event in active_events:
                    event_id = event.get('event_id')
                    season = event.get('season', '').lower()
                    
                    # Начисляем очки за сбор урожая (1 очко за каждую культуру)
                    points = len(rows)
                    
                    # Бонус за ивентовые культуры
                    for crop in crops:
                        crop_type = crop.get('crop_type', '')
                        
                        # Хэллоуин: тыквы
                        if 'halloween' in season and 'pumpkin' in crop_type:
                            points += 4  # 5 очков всего за тыкву (1 базовое + 4 бонус)
                            # Добавляем тыкву в инвентарь
                            await self.add_inventory(user_id, 'event_pumpkin', 1)
                            event_items_earned.append({'item': 'pumpkin', 'amount': 1})
                        
                        # Новый год: елки
                        elif 'newyear' in season and 'christmas_tree' in crop_type:
                            points += 4
                            await self.add_inventory(user_id, 'event_christmas_tree', 1)
                            event_items_earned.append({'item': 'christmas_tree', 'amount': 1})
                            # Шанс найти подарок
                            import random
                            if random.random() < 0.3:  # 30% шанс
                                await self.add_inventory(user_id, 'event_gift', 1)
                                event_items_earned.append({'item': 'gift', 'amount': 1})
                    
                    # Обновляем счёт в ивенте
                    await self.update_event_score(user_id, event_id, points)
                    event_points_earned += points
                
                await db.commit()

                result = {
                    "success": True,
                    "total": total,
                    "harvested_count": len(rows),
                    "crops": crops
                }
                
                # Добавляем ивентовые данные если есть
                if event_points_earned > 0:
                    result["event_points"] = event_points_earned
                if event_items_earned:
                    result["event_items"] = event_items_earned
                
                return result
            except Exception as e:
                await db.rollback()
                raise
    
    # Инвентарь
    async def get_inventory(self, user_id: int) -> Dict[str, int]:
        rows = await self.fetchall("SELECT item_code, quantity FROM inventory WHERE user_id = ?", (user_id,))
        return {row[0]: row[1] for row in rows}
    
    async def get_inventory_full(self, user_id: int) -> Dict:
        """Получает полную информацию об инвентаре с разбивкой по категориям
        
        Returns:
            Dict с полями:
                - total_items: int - общее количество предметов
                - max_capacity: int - максимальная вместимость
                - total_value: int - общая стоимость
                - seeds: Dict - семена
                - fertilizers: Dict - удобрения
                - upgrades: Dict - улучшения (активные)
                - other: Dict - прочее
        """
        # Получаем инвентарь
        inventory = await self.get_inventory(user_id)
        
        if not inventory:
            return {
                "total_items": 0,
                "max_capacity": 100,
                "total_value": 0,
                "seeds": {},
                "fertilizers": {},
                "upgrades": {},
                "other": {}
            }
        
        # Получаем информацию о всех предметах из магазина
        all_items = await self.fetchall(
            """SELECT item_code, item_name, item_icon, buy_price, sell_price, 
                      growth_time, category, required_level, effect_value, effect_type
               FROM shop_config"""
        )
        
        # Создаём словарь с информацией о предметах
        items_info = {}
        for row in all_items:
            items_info[row[0]] = {
                "name": row[1],
                "icon": row[2],
                "buy_price": row[3],
                "sell_price": row[4],
                "growth_time": row[5],
                "category": row[6],
                "required_level": row[7] if len(row) > 7 else 1,
                "effect_value": row[8] if len(row) > 8 else None,
                "effect_type": row[9] if len(row) > 9 else None
            }
        
        # Разделяем по категориям
        seeds = {}
        fertilizers = {}
        upgrades = {}
        other = {}
        
        total_items = 0
        total_value = 0
        
        for item_code, quantity in inventory.items():
            if quantity <= 0:
                continue
            
            total_items += quantity
            
            item = items_info.get(item_code, {})
            category = item.get('category', 'other')
            icon = item.get('icon', '📦')
            name = item.get('name', item_code)
            sell_price = item.get('sell_price', 0)
            growth_time = item.get('growth_time', 0)
            required_level = item.get('required_level', 1)
            effect_value = item.get('effect_value')
            effect_type = item.get('effect_type')
            
            # Вычисляем стоимость
            item_value = sell_price * quantity
            total_value += item_value
            
            item_entry = {
                "code": item_code,
                "name": name,
                "icon": icon,
                "quantity": quantity,
                "value": item_value,
                "sell_price": sell_price,
                "growth_time": growth_time,
                "required_level": required_level,
                "effect_value": effect_value,
                "effect_type": effect_type
            }
            
            if category == 'seed':
                seeds[item_code] = item_entry
            elif category == 'fertilizer':
                fertilizers[item_code] = item_entry
            elif category == 'upgrade':
                upgrades[item_code] = item_entry
            else:
                other[item_code] = item_entry
        
        # Получаем вместимость инвентаря (из настроек пользователя)
        user = await self.get_user(user_id)
        max_capacity = 100  # Базовая вместимость
        if user and user.get('settings'):
            max_capacity = user['settings'].get('inventory_capacity', 100)
        
        return {
            "total_items": total_items,
            "max_capacity": max_capacity,
            "total_value": total_value,
            "seeds": seeds,
            "fertilizers": fertilizers,
            "upgrades": upgrades,
            "other": other
        }
    
    async def add_inventory(self, user_id: int, item_code: str, quantity: int):
        """Добавляет предмет в инвентарь"""
        await self.execute(
            """INSERT INTO inventory (user_id, item_code, quantity) 
               VALUES (?, ?, ?) 
               ON CONFLICT(user_id, item_code) DO UPDATE SET quantity = quantity + excluded.quantity""",
            (user_id, item_code, quantity), commit=True
        )
        
    async def remove_inventory(self, user_id: int, item_code: str, quantity: int):
        await self.execute(
            "UPDATE inventory SET quantity = quantity - ? WHERE user_id = ? AND item_code = ? AND quantity >= ?",
            (quantity, user_id, item_code, quantity), commit=True
        )
    
    async def get_inventory_item(self, user_id: int, item_code: str) -> Optional[Dict]:
        """Получает информацию о конкретном предмете в инвентаре
        
        Args:
            user_id: ID пользователя
            item_code: Код предмета
            
        Returns:
            Dict с информацией о предмете или None
        """
        # Получаем количество в инвентаре
        row = await self.fetchone(
            "SELECT quantity FROM inventory WHERE user_id = ? AND item_code = ?",
            (user_id, item_code)
        )
        
        if not row or row[0] <= 0:
            return None
        
        quantity = row[0]
        
        # Получаем информацию о предмете
        item = await self.get_shop_item(item_code)
        if not item:
            return None
        
        return {
            "code": item_code,
            "name": item.get('name', item_code),
            "icon": item.get('icon', '📦'),
            "quantity": quantity,
            "sell_price": item.get('sell_price', 0),
            "buy_price": item.get('buy_price', 0),
            "growth_time": item.get('growth_time', 0),
            "required_level": item.get('required_level', 1),
            "category": item.get('category', 'other'),
            "effect_value": item.get('effect_value'),
            "effect_type": item.get('effect_type')
        }
        
    # ==================== СИСТЕМА ГРЯДОК (ТЗ v4.0 п.4) ====================
    
    async def get_plot_count(self, user_id: int) -> int:
        """Получает текущее количество грядок пользователя"""
        row = await self.fetchone(
            "SELECT COUNT(*) FROM plots WHERE user_id = ?", (user_id,)
        )
        return row[0] if row else 0

    async def get_max_plots(self, user_id: int) -> int:
        """Получает максимальное количество грядок (из настроек или по умолчанию 10)"""
        # Проверяем настройки пользователя
        user = await self.get_user(user_id)
        if user and user.get('settings'):
            max_plots = user['settings'].get('max_plots', 10)
            return max_plots
        return 10  # По умолчанию максимум 10 грядок
    
    async def get_plot_price(self, plot_number: int) -> int:
        """Получает цену грядки по её номеру
        
        Цена растёт экспоненциально:
        - Грядка 5: 500🪙
        - Грядка 6: 1,000🪙
        - Грядка 7: 2,000🪙
        - Грядка 8: 4,000🪙
        - Грядка 9: 8,000🪙
        - Грядка 10: 15,000🪙
        """
        # Базовые цены для грядок 5-10
        base_prices = {
            5: 500,
            6: 1000,
            7: 2000,
            8: 4000,
            9: 8000,
            10: 15000
        }
        return base_prices.get(plot_number, 500 * (2 ** (plot_number - 5)))
    
    async def buy_plot(self, user_id: int, plot_number: int) -> Dict:
        """Покупка новой грядки
        
        Args:
            user_id: ID пользователя
            plot_number: Номер грядки для покупки
            
        Returns:
            Dict с результатом операции
        """
        # Проверяем что грядка ещё не куплена
        existing = await self.fetchone(
            "SELECT 1 FROM plots WHERE user_id = ? AND plot_number = ?",
            (user_id, plot_number)
        )
        if existing:
            return {"success": False, "message": "Эта грядка уже куплена!"}
        
        # Проверяем максимальное количество грядок
        max_plots = await self.get_max_plots(user_id)
        if plot_number > max_plots:
            return {"success": False, "message": f"Максимальное количество грядок: {max_plots}"}
        
        # Проверяем что покупается следующая по порядку грядка
        current_count = await self.get_plot_count(user_id)
        if plot_number != current_count + 1:
            return {"success": False, "message": f"Сначала купи грядку #{current_count + 1}"}
        
        # Получаем цену
        price = await self.get_plot_price(plot_number)
        
        # Проверяем баланс
        user = await self.get_user(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        if user.get('balance', 0) < price:
            return {"success": False, "message": f"Недостаточно монет! Нужно {price:,}🪙"}
        
        # Списываем деньги и создаём грядку
        try:
            new_balance = await self.update_balance(user_id, -price)
            if new_balance is None:
                return {"success": False, "message": "Ошибка списания средств"}
            
            await self.execute(
                "INSERT INTO plots (user_id, plot_number, status) VALUES (?, ?, 'empty')",
                (user_id, plot_number), commit=True
            )
            
            # Логируем покупку
            await self.log_economy(
                user_id, 'spend', 'coins', price, new_balance,
                'buy_plot', f'plot_{plot_number}', f"Покупка грядки #{plot_number}"
            )
        
            return {
                "success": True,
                "plot_number": plot_number,
                "price": price,
                "new_balance": new_balance
            }
        except Exception as e:
            logging.error(f"Error buying plot for user {user_id}: {e}")
            return {"success": False, "message": "Ошибка покупки грядки"}
    
    async def get_next_plot_to_buy(self, user_id: int) -> Optional[Dict]:
        """Получает информацию о следующей грядке для покупки"""
        current_count = await self.get_plot_count(user_id)
        max_plots = await self.get_max_plots(user_id)
        
        if current_count >= max_plots:
            return None  # Все грядки куплены
        
        next_plot = current_count + 1
        price = await self.get_plot_price(next_plot)
        
        return {
            "plot_number": next_plot,
            "price": price,
            "max_plots": max_plots,
            "current_count": current_count
        }
    
    async def get_user_plant_count(self, user_id: int) -> int:
        """Получает общее количество посадок пользователя (для подсказок новичкам)"""
        row = await self.fetchone(
            "SELECT total_planted FROM users WHERE user_id = ?", (user_id,)
        )
        return row[0] if row else 0
        
    async def get_shop_item(self, item_code: str) -> Optional[Dict]:
        """Получает информацию о товаре по коду"""
        row = await self.fetchone(
            "SELECT item_code, item_name, item_icon, buy_price, sell_price, growth_time, category, required_level FROM shop_config WHERE item_code = ?",
            (item_code,)
        )
        if row:
            return {
                "item_code": row[0],
                "name": row[1],
                "icon": row[2],
                "buy_price": row[3],
                "sell_price": row[4],
                "growth_time": row[5],
                "category": row[6],
                "required_level": row[7] if len(row) > 7 else 1
            }
        return None
        
    # ==================== СИСТЕМА МАГАЗИНА (ТЗ v4.0 п.5) ====================
    
    async def get_shop_items(self, category: str = None) -> List[Dict]:
        """Получает список товаров с полной информацией"""
        # Проверяем наличие поля is_active
        try:
            if category:
                rows = await self.fetchall(
                    """SELECT item_code, item_name, item_icon, buy_price, sell_price, 
                              growth_time, category, required_level, effect_value, 
                              effect_type, description, is_active, sort_order
                       FROM shop_config 
                       WHERE category = ? AND is_active = 1 
                       ORDER BY sort_order, required_level""", 
                    (category,)
                )
            else:
                rows = await self.fetchall(
                    """SELECT item_code, item_name, item_icon, buy_price, sell_price, 
                              growth_time, category, required_level, effect_value, 
                              effect_type, description, is_active, sort_order
                       FROM shop_config 
                       WHERE is_active = 1
                       ORDER BY category, sort_order, required_level"""
                )
        except Exception:
            # Fallback: запрос без поля is_active для старых БД
            if category:
                rows = await self.fetchall(
                    """SELECT item_code, item_name, item_icon, buy_price, sell_price, 
                              growth_time, category, required_level, effect_value, 
                              effect_type, description, sort_order
                       FROM shop_config 
                       WHERE category = ?
                       ORDER BY sort_order, required_level""", 
                    (category,)
                )
            else:
                rows = await self.fetchall(
                    """SELECT item_code, item_name, item_icon, buy_price, sell_price, 
                              growth_time, category, required_level, effect_value, 
                              effect_type, description, sort_order
                       FROM shop_config 
                       ORDER BY category, sort_order, required_level"""
                )
        
        items = []
        for r in rows:
            # Определяем есть ли поле is_active по количеству колонок
            has_is_active = len(r) >= 12
            
            item = {
                "item_code": r[0],
                "name": r[1],
                "icon": r[2],
                "buy_price": r[3],
                "sell_price": r[4],
                "growth_time": r[5],
                "category": r[6],
                "required_level": r[7] if len(r) > 7 else 1,
                "effect_value": r[8] if len(r) > 8 else None,
                "effect_type": r[9] if len(r) > 9 else None,
                "description": r[10] if len(r) > 10 else None,
            }
            
            if has_is_active:
                item["is_active"] = r[11]
                item["sort_order"] = r[12] if len(r) > 12 else 0
            else:
                item["is_active"] = True
                item["sort_order"] = r[11] if len(r) > 11 else 0
                
            items.append(item)
        return items
    
    async def get_shop_categories(self) -> List[Dict]:
        """Получает список категорий магазина"""
        rows = await self.fetchall(
            """SELECT DISTINCT category, 
                      CASE category
                        WHEN 'seed' THEN 'Семена'
                        WHEN 'fertilizer' THEN 'Удобрения'
                        WHEN 'upgrade' THEN 'Улучшения'
                        WHEN 'tool' THEN 'Инструменты'
                        ELSE category
                      END as name,
                      CASE category
                        WHEN 'seed' THEN '🌱'
                        WHEN 'fertilizer' THEN '🧪'
                        WHEN 'upgrade' THEN '🚜'
                        WHEN 'tool' THEN '🔧'
                        ELSE '📦'
                      END as icon
               FROM shop_config 
               WHERE is_active = 1 
               ORDER BY 
                 CASE category
                   WHEN 'seed' THEN 1
                   WHEN 'fertilizer' THEN 2
                   WHEN 'upgrade' THEN 3
                   WHEN 'tool' THEN 4
                   ELSE 5
                 END"""
        )
        categories = []
        for r in rows:
            categories.append({
                "code": r[0],
                "name": r[1],
                "icon": r[2]
            })
        return categories
        
    async def buy_shop_item(self, user_id: int, item_code: str, quantity: int = 1) -> Dict:
        """Покупка товара в магазине
        
        Args:
            user_id: ID пользователя
            item_code: Код товара
            quantity: Количество
            
        Returns:
            Dict с результатом операции
        """
        # Получаем информацию о товаре
        item = await self.get_shop_item(item_code)
        if not item:
            return {"success": False, "message": "Товар не найден"}
        
        if not item.get('is_active', True):
            return {"success": False, "message": "Товар недоступен для покупки"}
        
        # Получаем пользователя
        user = await self.get_user(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        # Проверка уровня
        required_level = item.get('required_level', 1)
        if user.get('city_level', 1) < required_level:
            return {"success": False, "message": f"Требуется уровень {required_level}"}
        
        # Проверка баланса
        buy_price = item.get('buy_price', 0) * quantity
        currency = 'gems' if item.get('category') == 'fertilizer' and 'crystal' in item_code.lower() else 'coins'
        
        # Особая проверка для кристальных удобрений (плата в кристаллах)
        if item.get('effect_type') == 'instant' and item.get('buy_price', 0) > 100:
            currency = 'gems'
        
        if currency == 'gems':
            if user.get('gems', 0) < buy_price:
                return {"success": False, "message": f"Недостаточно кристаллов! Нужно {buy_price}💎"}
        else:
            if user.get('balance', 0) < buy_price:
                return {"success": False, "message": f"Недостаточно монет! Нужно {buy_price:,}🪙"}
        
        # Списываем средства
        try:
            if currency == 'gems':
                new_balance = await self.update_gems(user_id, -buy_price)
            else:
                new_balance = await self.update_balance(user_id, -buy_price)
            
            if new_balance is None:
                return {"success": False, "message": "Ошибка списания средств"}
            
            # Добавляем товар в инвентарь
            await self.add_inventory(user_id, item_code, quantity)
            
            # Логируем покупку
            await self.log_economy(
                user_id, 'spend', currency, buy_price, new_balance,
                'shop_buy', item_code, f"Покупка {item.get('name', item_code)} x{quantity}"
            )
        
            # Обновляем квесты
            await self.update_quest_progress(user_id, 'spend', buy_price)
            
            # Проверяем ачивки
            await self.check_and_update_achievements(user_id, 'spend', count=buy_price)
            
            return {
                "success": True,
                "item_code": item_code,
                "item_name": item.get('name', item_code),
                "quantity": quantity,
                "spent": buy_price,
                "currency": currency,
                "new_balance": new_balance
            }
        except Exception as e:
            logging.error(f"Error buying item {item_code} for user {user_id}: {e}")
            return {"success": False, "message": "Ошибка покупки"}
    
    async def sell_inventory_item(self, user_id: int, item_code: str, quantity: int = 1, multiplier: float = 1.0) -> Dict:
        """Продажа предмета из инвентаря
        
        Args:
            user_id: ID пользователя
            item_code: Код товара
            quantity: Количество
            multiplier: Множитель престижа
            
        Returns:
            Dict с результатом операции
        """
        # Получаем информацию о товаре
        item = await self.get_shop_item(item_code)
        if not item:
            return {"success": False, "message": "Товар не найден"}
        
        # Проверяем наличие в инвентаре
        inventory = await self.get_inventory(user_id)
        if inventory.get(item_code, 0) < quantity:
            return {"success": False, "message": f"Недостаточно товара! Есть: {inventory.get(item_code, 0)}"}
        
        # Рассчитываем цену с учётом множителя
        base_price = item.get('sell_price', 0)
        total_price = int(base_price * quantity * multiplier)
        
        try:
            # Удаляем из инвентаря
            await self.remove_inventory(user_id, item_code, quantity)
            
            # Добавляем монеты
            new_balance = await self.update_balance(user_id, total_price)
            
            if new_balance is None:
                # Возвращаем товар если не удалось добавить монеты
                await self.add_inventory(user_id, item_code, quantity)
                return {"success": False, "message": "Ошибка начисления монет"}
            
            # Логируем продажу
            await self.log_economy(
                user_id, 'earn', 'coins', total_price, new_balance,
                'shop_sell', item_code, f"Продажа {item.get('name', item_code)} x{quantity}"
            )
            
            # Обновляем квесты
            await self.update_quest_progress(user_id, 'sell', total_price)
            
            # Проверяем ачивки
            await self.check_and_update_achievements(user_id, 'sell', count=total_price)
            await self.check_and_update_achievements(user_id, 'earn', count=total_price)
            
            return {
                "success": True,
                "item_code": item_code,
                "item_name": item.get('name', item_code),
                "quantity": quantity,
                "earned": total_price,
                "base_price": base_price,
                "multiplier": multiplier,
                "new_balance": new_balance
            }
        except Exception as e:
            logging.error(f"Error selling item {item_code} for user {user_id}: {e}")
            return {"success": False, "message": "Ошибка продажи"}
    
    async def update_gems(self, user_id: int, amount: int) -> Optional[int]:
        """Обновляет количество кристаллов пользователя
        
        Args:
            user_id: ID пользователя
            amount: Количество для добавления (может быть отрицательным)
            
        Returns:
            Новое количество кристаллов или None при ошибке
        """
        async with self.lock:
            db = await self.connect()
            await db.execute("BEGIN")
            try:
                user = await self.get_user(user_id)
                if not user:
                    await db.rollback()
                    return None
                
                current_gems = user.get("gems", 0)
                new_gems = current_gems + amount
                
                # Проверка на отрицательное количество
                if new_gems < 0:
                    await db.rollback()
                    return None
                
                await db.execute(
                    "UPDATE users SET gems = ? WHERE user_id = ?",
                    (new_gems, user_id)
                )
                await db.commit()
                
                return new_gems
            except Exception as e:
                await db.rollback()
                logging.error(f"Error updating gems for user {user_id}: {e}")
                return None
    
    # Ежедневные бонусы
    async def get_daily_bonus(self, user_id: int) -> Dict:
        today = datetime.now().date()
        
        row = await self.fetchone("SELECT * FROM user_daily WHERE user_id = ?", (user_id,))
        if not row:
            streak = 0
            last_date = None
        else:
            streak, last_date = row[1], row[2]
            if last_date == today:
                return {"available": False, "streak": streak, "message": "Бонус уже получен сегодня!"}
        
        if last_date and (today - datetime.strptime(last_date, '%Y-%m-%d').date()).days > 1:
            streak = 0
        
        new_streak = streak + 1
        reward = await self.fetchone("SELECT coins, items_json FROM daily_rewards WHERE day_number = ?", (new_streak,))
        
        return {
            "available": True,
            "streak": new_streak,
            "coins": reward[0] if reward else 50,
            "items": json.loads(reward[1]) if reward and reward[1] else {}
        }
    
    async def claim_daily_bonus(self, user_id: int) -> Dict:
        """Выдаёт ежедневный бонус

        Returns:
            Dict с полями:
                - success: bool - успешность операции
                - coins: int - выданные монеты
                - items: dict - выданные предметы
        """
        bonus = await self.get_daily_bonus(user_id)
        if not bonus.get("available", False):
            return {"success": False, "message": "Бонус недоступен"}
        
        coins = bonus.get("coins", 0)
        items = bonus.get("items", {})
        
        # Проверяем что награда существует
        if coins <= 0 and not items:
            return {"success": False, "message": "Ошибка конфигурации награды"}
        
        try:
            # Выдать награду
            if coins > 0:
                new_balance = await self.update_balance(user_id, coins)
                if new_balance is None:
                    return {"success": False, "message": "Ошибка выдачи монет"}
            
            items_given = {}
            for item, qty in items.items():
                if qty > 0:
                    await self.add_inventory(user_id, item, qty)
                    items_given[item] = qty
            
            # Обновить прогресс
            today = datetime.now().date()
            streak = bonus.get("streak", 1)
            await self.execute(
                """INSERT INTO user_daily (user_id, current_streak, last_claim_date) 
                   VALUES (?, ?, ?) 
                   ON CONFLICT(user_id) DO UPDATE SET 
                   current_streak = ?, last_claim_date = ?""",
                (user_id, streak, today, streak, today), commit=True
            )
            
            return {
                "success": True,
                "coins": coins,
                "items": items_given
            }
        except Exception as e:
            logging.error(f"Error claiming daily bonus for user {user_id}: {e}")
            return {"success": False, "message": "Ошибка выдачи бонуса"}
    
    # Промокоды
    async def activate_promo(self, user_id: int, code: str) -> Dict:
        """Активирует промокод для пользователя

        Returns:
            Dict с информацией о результате активации
        """
        promo = await self.fetchone(
            "SELECT * FROM promocodes WHERE code = ? AND is_active = 1 AND valid_until > CURRENT_TIMESTAMP AND (max_uses = 0 OR times_used < max_uses)",
            (code.upper(),)
        )
        if not promo:
            return {"success": False, "message": "Промокод недействителен или истек"}
        
        # Проверка активации
        exists = await self.fetchone("SELECT 1 FROM promo_activations WHERE promo_id = ? AND user_id = ?", (promo[0], user_id))
        if exists:
            return {"success": False, "message": "Промокод уже активирован"}
        
        # Проверка валидности JSON наград
        try:
            rewards = json.loads(promo[2])
            if not isinstance(rewards, dict):
                return {"success": False, "message": "Ошибка конфигурации промокода"}
        except (json.JSONDecodeError, TypeError):
            return {"success": False, "message": "Ошибка конфигурации промокода"}
        
        try:
            rewards_given = {"coins": 0, "items": {}}
            
            # Выдать награды
            coins = rewards.get("coins", 0)
            if coins > 0:
                new_balance = await self.update_balance(user_id, coins)
                if new_balance is None:
                    return {"success": False, "message": "Ошибка выдачи награды"}
                rewards_given["coins"] = coins
            
            items = rewards.get("items", {})
            if isinstance(items, dict):
                for item, qty in items.items():
                    if qty > 0:
                        await self.add_inventory(user_id, item, qty)
                        rewards_given["items"][item] = qty
            
            # Обновить счетчик
            await self.execute(
                "UPDATE promocodes SET times_used = times_used + 1 WHERE id = ?", (promo[0],), commit=True
            )
            await self.execute(
                "INSERT INTO promo_activations (promo_id, user_id) VALUES (?, ?)", (promo[0], user_id), commit=True
            )
            
            # Логирование
            await self.log_economy(
                user_id, 'earn', 'coins', coins,
                await self.fetchone("SELECT balance FROM users WHERE user_id = ?", (user_id,))[0] if coins else 0,
                'promo', code, f"Activated promo code: {code}"
            )
            
            return {"success": True, "rewards": rewards_given}
        except Exception as e:
            logging.error(f"Error activating promo {code} for user {user_id}: {e}")
            return {"success": False, "message": "Ошибка активации промокода"}
    
    async def get_promo_codes(self) -> List[Dict]:
        rows = await self.fetchall("SELECT * FROM promocodes WHERE is_active = 1 AND valid_until > CURRENT_TIMESTAMP")
        return [{"id": r[0], "code": r[1], "description": r[3], "coins": r[4], "items": json.loads(r[5])} for r in rows]
    
    async def get_promo_activations(self, user_id: int) -> List[Dict]:
        rows = await self.fetchall("SELECT * FROM promo_activations WHERE user_id = ?", (user_id,))
        return [{"promo_id": r[0], "promo_code": r[1]} for r in rows]
    
    # КВЕСТЫ
    async def get_daily_quests(self, user_id: int) -> List[Dict]:
        """Получает или создает ежедневные квесты для пользователя"""
        today = datetime.now().date()
        
        # Проверяем есть ли квесты на сегодня
        rows = await self.fetchall(
            """SELECT q.quest_id, q.quest_type, q.target_item, q.target_count, 
                      q.description, q.reward_coins, q.reward_items_json,
                      COALESCE(uq.progress, 0) as progress,
                      COALESCE(uq.completed, 0) as completed,
                      COALESCE(uq.claimed, 0) as claimed
               FROM quests q
               LEFT JOIN user_quests uq ON q.quest_id = uq.quest_id 
                   AND uq.user_id = ? AND uq.assigned_date = ?
               WHERE q.is_daily = 1 AND q.is_active = 1""",
            (user_id, today)
        )
        
        quests = []
        for row in rows:
            quests.append({
                "quest_id": row[0],
                "type": row[1],
                "target_item": row[2],
                "target_count": row[3],
                "description": row[4],
                "reward_coins": row[5],
                "reward_items": json.loads(row[6]) if row[6] else {},
                "progress": row[7],
                "completed": row[8],
                "claimed": row[9]
            })
        
        # Если квестов нет, создаем их
        if not quests:
            all_quests = await self.fetchall(
                "SELECT quest_id FROM quests WHERE is_daily = 1 AND is_active = 1"
            )
            for q in all_quests[:3]:  # 3 случайных квеста
                await self.execute(
                    """INSERT OR IGNORE INTO user_quests 
                       (user_id, quest_id, assigned_date) VALUES (?, ?, ?)""",
                    (user_id, q[0], today), commit=True
                )
            # Получаем заново
            return await self.get_daily_quests(user_id)
        
        return quests
    
    async def update_quest_progress(self, user_id: int, quest_type: str, count: int = 1, item_code: str = None):
        """Обновляет прогресс квестов указанного типа"""
        today = datetime.now().date()
        
        # Находим активные квесты этого типа
        if item_code:
            rows = await self.fetchall(
                """SELECT uq.quest_id, q.target_count, uq.progress 
                   FROM user_quests uq
                   JOIN quests q ON uq.quest_id = q.quest_id
                   WHERE uq.user_id = ? AND uq.assigned_date = ? 
                   AND uq.completed = 0 AND q.quest_type = ?
                   AND (q.target_item = ? OR q.target_item IS NULL)""",
                (user_id, today, quest_type, item_code)
            )
        else:
            rows = await self.fetchall(
                """SELECT uq.quest_id, q.target_count, uq.progress 
                   FROM user_quests uq
                   JOIN quests q ON uq.quest_id = q.quest_id
                   WHERE uq.user_id = ? AND uq.assigned_date = ? 
                   AND uq.completed = 0 AND q.quest_type = ?""",
                (user_id, today, quest_type)
            )
        
        completed_quests = []
        for row in rows:
            quest_id, target, current = row[0], row[1], row[2]
            new_progress = current + count
            
            if new_progress >= target:
                await self.execute(
                    """UPDATE user_quests SET progress = ?, completed = 1 
                       WHERE user_id = ? AND quest_id = ? AND assigned_date = ?""",
                    (target, user_id, quest_id, today), commit=True
                )
                completed_quests.append(quest_id)
            else:
                await self.execute(
                    """UPDATE user_quests SET progress = ? 
                       WHERE user_id = ? AND quest_id = ? AND assigned_date = ?""",
                    (new_progress, user_id, quest_id, today), commit=True
                )
        
        return completed_quests
    
    async def update_quest_progress_batch(self, user_id: int, quest_type: str, crops: List[Dict]):
        """Обновляет прогресс квестов пакетом для нескольких культур

        Args:
            user_id: ID пользователя
            quest_type: Тип квеста
            crops: Список культур с информацией о типе
        """
        today = datetime.now().date()
        
        # Группируем по типам культур
        crop_types = {}
        for crop in crops:
            crop_type = crop.get('crop_type')
            if crop_type:
                crop_types[crop_type] = crop_types.get(crop_type, 0) + 1

        # Обновляем квесты для каждого типа культуры
        for crop_type, count in crop_types.items():
            await self.update_quest_progress(user_id, quest_type, count, crop_type)

    async def claim_quest_reward(self, user_id: int, quest_id: int, is_weekly: bool = False) -> Dict:
        """Выдает награду за выполненный квест
        
        Args:
            user_id: ID пользователя
            quest_id: ID квеста
            is_weekly: Еженедельный квест (по умолчанию False - ежедневный)
        """
        if is_weekly:
            # Для еженедельных квестов используем начало недели
            week_start = self._get_week_start()
            assigned_date = week_start
        else:
            assigned_date = datetime.now().date()
        
        row = await self.fetchone(
            """SELECT q.reward_coins, q.reward_gems, q.reward_items_json, uq.completed, uq.claimed
               FROM user_quests uq
               JOIN quests q ON uq.quest_id = q.quest_id
               WHERE uq.user_id = ? AND uq.quest_id = ? AND uq.assigned_date = ?""",
            (user_id, quest_id, assigned_date)
        )

        if not row:
            return {"success": False, "message": "Квест не найден"}
        
        coins, gems, items_json, completed, claimed = row
        
        if not completed:
            return {"success": False, "message": "Квест еще не выполнен"}
        
        if claimed:
            return {"success": False, "message": "Награда уже получена"}
        
        rewards_given = {"coins": 0, "gems": 0, "items": {}}
        
        # Выдаем монеты
        if coins and coins > 0:
            await self.update_balance(user_id, coins)
            rewards_given["coins"] = coins
        
        # Выдаем кристаллы
        if gems and gems > 0:
            await self.update_gems(user_id, gems)
            rewards_given["gems"] = gems
        
        # Выдаем предметы
        items = json.loads(items_json) if items_json else {}
        for item, qty in items.items():
            if qty > 0:
                await self.add_inventory(user_id, item, qty)
                rewards_given["items"][item] = qty
        
        # Помечаем как полученную
        await self.execute(
            """UPDATE user_quests SET claimed = 1 
               WHERE user_id = ? AND quest_id = ? AND assigned_date = ?""",
            (user_id, quest_id, assigned_date), commit=True
        )
        
        return {"success": True, **rewards_given}
    
    def _get_week_start(self) -> str:
        """Возвращает дату начала текущей недели (понедельник)"""
        today = datetime.now().date()
        # Понедельник = 0, Воскресенье = 6
        days_since_monday = today.weekday()
        week_start = today - timedelta(days=days_since_monday)
        return week_start.isoformat()
    
    def _get_week_end(self) -> datetime:
        """Возвращает дату конца текущей недели (воскресенье 23:59:59)"""
        today = datetime.now().date()
        days_until_sunday = 6 - today.weekday()
        week_end = today + timedelta(days=days_until_sunday)
        return datetime.combine(week_end, datetime.max.time())
    
    async def get_weekly_quests(self, user_id: int) -> List[Dict]:
        """Получает или создает еженедельные квесты для пользователя"""
        week_start = self._get_week_start()
        
        # Проверяем есть ли квесты на эту неделю
        rows = await self.fetchall(
            """SELECT q.quest_id, q.quest_type, q.target_item, q.target_count, 
                      q.description, q.reward_coins, q.reward_gems, q.reward_items_json,
                      COALESCE(uq.progress, 0) as progress,
                      COALESCE(uq.completed, 0) as completed,
                      COALESCE(uq.claimed, 0) as claimed
               FROM quests q
               LEFT JOIN user_quests uq ON q.quest_id = uq.quest_id 
                   AND uq.user_id = ? AND uq.assigned_date = ?
               WHERE q.is_weekly = 1 AND q.is_active = 1
               ORDER BY q.sort_order""",
            (user_id, week_start)
        )
        
        quests = []
        for row in rows:
            quests.append({
                "quest_id": row[0],
                "type": row[1],
                "target_item": row[2],
                "target_count": row[3],
                "description": row[4],
                "reward_coins": row[5],
                "reward_gems": row[6] if len(row) > 6 else 0,
                "reward_items": json.loads(row[7]) if row[7] else {},
                "progress": row[8],
                "completed": row[9],
                "claimed": row[10]
            })
        
        # Если квестов нет, создаем их
        if not quests:
            all_quests = await self.fetchall(
                "SELECT quest_id FROM quests WHERE is_weekly = 1 AND is_active = 1 ORDER BY sort_order"
            )
            for q in all_quests[:5]:  # До 5 еженедельных квестов
                await self.execute(
                    """INSERT OR IGNORE INTO user_quests 
                       (user_id, quest_id, assigned_date) VALUES (?, ?, ?)""",
                    (user_id, q[0], week_start), commit=True
                )
            # Получаем заново
            return await self.get_weekly_quests(user_id)
        
        return quests
    
    async def update_weekly_quest_progress(self, user_id: int, quest_type: str, count: int = 1, item_code: str = None):
        """Обновляет прогресс еженедельных квестов указанного типа"""
        week_start = self._get_week_start()
        
        # Находим активные квесты этого типа
        if item_code:
            rows = await self.fetchall(
                """SELECT uq.quest_id, q.target_count, uq.progress 
                   FROM user_quests uq
                   JOIN quests q ON uq.quest_id = q.quest_id
                   WHERE uq.user_id = ? AND uq.assigned_date = ? 
                   AND uq.completed = 0 AND q.quest_type = ?
                   AND (q.target_item = ? OR q.target_item IS NULL)""",
                (user_id, week_start, quest_type, item_code)
            )
        else:
            rows = await self.fetchall(
                """SELECT uq.quest_id, q.target_count, uq.progress 
                   FROM user_quests uq
                   JOIN quests q ON uq.quest_id = q.quest_id
                   WHERE uq.user_id = ? AND uq.assigned_date = ? 
                   AND uq.completed = 0 AND q.quest_type = ?""",
                (user_id, week_start, quest_type)
            )
        
        completed_quests = []
        for row in rows:
            quest_id, target, current = row[0], row[1], row[2]
            new_progress = current + count
            
            if new_progress >= target:
                await self.execute(
                    """UPDATE user_quests SET progress = ?, completed = 1 
                       WHERE user_id = ? AND quest_id = ? AND assigned_date = ?""",
                    (target, user_id, quest_id, week_start), commit=True
                )
                completed_quests.append(quest_id)
            else:
                await self.execute(
                    """UPDATE user_quests SET progress = ? 
                       WHERE user_id = ? AND quest_id = ? AND assigned_date = ?""",
                    (new_progress, user_id, quest_id, week_start), commit=True
                )
        
        return completed_quests
    
    async def claim_all_quest_rewards(self, user_id: int, is_weekly: bool = False) -> Dict:
        """Забирает все доступные награды за квесты
        
        Args:
            user_id: ID пользователя
            is_weekly: Еженедельные квесты (по умолчанию False - ежедневные)
            
        Returns:
            Dict с суммарными наградами
        """
        if is_weekly:
            quests = await self.get_weekly_quests(user_id)
        else:
            quests = await self.get_daily_quests(user_id)
        
        total_coins = 0
        total_gems = 0
        total_items = {}
        claimed_quests = []
        
        for quest in quests:
            if quest.get('completed') and not quest.get('claimed'):
                result = await self.claim_quest_reward(user_id, quest['quest_id'], is_weekly)
                if result.get('success'):
                    total_coins += result.get('coins', 0)
                    total_gems += result.get('gems', 0)
                    for item, qty in result.get('items', {}).items():
                        total_items[item] = total_items.get(item, 0) + qty
                    claimed_quests.append(quest)
        
        return {
            "success": len(claimed_quests) > 0,
            "coins": total_coins,
            "gems": total_gems,
            "items": total_items,
            "claimed_count": len(claimed_quests),
            "claimed_quests": claimed_quests
        }
    
    async def get_quest_time_left(self, is_weekly: bool = False) -> Dict:
        """Возвращает время до обновления квестов
        
        Args:
            is_weekly: Для еженедельных квестов
            
        Returns:
            Dict с полями: hours, minutes, seconds, total_seconds
        """
        now = datetime.now()
        
        if is_weekly:
            # До конца недели (воскресенье 23:59:59)
            week_end = self._get_week_end()
            time_left = week_end - now
        else:
            # До конца дня
            tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            time_left = tomorrow - now
        
        total_seconds = int(time_left.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        return {
            "hours": hours,
            "minutes": minutes,
            "seconds": seconds,
            "total_seconds": total_seconds
        }
    
    async def refresh_daily_quests(self, user_id: int, cost_gems: int = 50) -> Dict:
        """Обновляет ежедневные квесты за кристаллы
        
        Args:
            user_id: ID пользователя
            cost_gems: Стоимость обновления в кристаллах
            
        Returns:
            Dict с результатом операции
        """
        # Проверяем баланс кристаллов
        user = await self.get_user(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        if user.get('gems', 0) < cost_gems:
            return {"success": False, "message": f"Недостаточно кристаллов! Нужно {cost_gems}💎"}
        
        # Списываем кристаллы
        new_gems = await self.update_gems(user_id, -cost_gems)
        if new_gems is None:
            return {"success": False, "message": "Ошибка списания кристаллов"}
        
        # Удаляем текущие квесты
        today = datetime.now().date()
        await self.execute(
            "DELETE FROM user_quests WHERE user_id = ? AND assigned_date = ?",
            (user_id, today), commit=True
        )
        
        # Создаем новые квесты
        all_quests = await self.fetchall(
            "SELECT quest_id FROM quests WHERE is_daily = 1 AND is_active = 1 ORDER BY RANDOM()"
        )
        for q in all_quests[:3]:  # 3 случайных квеста
            await self.execute(
                """INSERT INTO user_quests 
                   (user_id, quest_id, assigned_date) VALUES (?, ?, ?)""",
                (user_id, q[0], today), commit=True
            )
        
        return {
            "success": True,
            "new_gems": new_gems,
            "message": "Квесты обновлены!"
        }
    
    # ==================== СИСТЕМА ДОСТИЖЕНИЙ (АЧИВОК) ====================
    
    async def get_achievement_categories(self, use_cache: bool = True) -> List[Dict]:
        """Получает все категории достижений с кэшированием

        Args:
            use_cache: Использовать кэш (по умолчанию True)

        Returns:
            Список категорий достижений
        """
        if use_cache and self._achievement_categories_cache is not None:
            return self._achievement_categories_cache

        rows = await self.fetchall(
            "SELECT category_id, name, icon, description, sort_order FROM achievement_categories ORDER BY sort_order"
        )
        categories = [{"id": r[0], "name": r[1], "icon": r[2], "description": r[3], "sort_order": r[4]} for r in rows]
        
        if use_cache:
            self._achievement_categories_cache = categories

        return categories
        
    async def get_achievements_by_category(self, user_id: int, category_id: str = None) -> List[Dict]:
        """Получает достижения по категории с прогрессом игрока"""
        if category_id:
            rows = await self.fetchall(
                """SELECT a.achievement_id, a.code, a.name, a.description, a.icon, a.category_id,
                          ac.name as category_name, ac.icon as category_icon,
                          a.achievement_type, a.parent_achievement_id, a.level, a.is_secret,
                          a.requirement_type, a.requirement_count, a.requirement_item,
                          a.reward_coins, a.reward_gems, a.reward_items_json, a.reward_multiplier,
                          a.sort_order, a.is_active,
                          COALESCE(pa.progress, 0) as progress,
                          COALESCE(pa.completed, 0) as completed,
                          COALESCE(pa.reward_claimed, 0) as reward_claimed,
                          pa.completed_at, pa.claimed_at
                   FROM achievements a
                   JOIN achievement_categories ac ON a.category_id = ac.category_id
                   LEFT JOIN player_achievements pa ON a.achievement_id = pa.achievement_id AND pa.user_id = ?
                   WHERE a.category_id = ? AND a.is_active = 1
                   ORDER BY a.sort_order, a.level""",
                (user_id, category_id)
            )
        else:
            rows = await self.fetchall(
                """SELECT a.achievement_id, a.code, a.name, a.description, a.icon, a.category_id,
                          ac.name as category_name, ac.icon as category_icon,
                          a.achievement_type, a.parent_achievement_id, a.level, a.is_secret,
                          a.requirement_type, a.requirement_count, a.requirement_item,
                          a.reward_coins, a.reward_gems, a.reward_items_json, a.reward_multiplier,
                          a.sort_order, a.is_active,
                          COALESCE(pa.progress, 0) as progress,
                          COALESCE(pa.completed, 0) as completed,
                          COALESCE(pa.reward_claimed, 0) as reward_claimed,
                          pa.completed_at, pa.claimed_at
                   FROM achievements a
                   JOIN achievement_categories ac ON a.category_id = ac.category_id
                   LEFT JOIN player_achievements pa ON a.achievement_id = pa.achievement_id AND pa.user_id = ?
                   WHERE a.is_active = 1
                   ORDER BY ac.sort_order, a.sort_order, a.level""",
                (user_id,)
            )
        
        achievements = []
        for row in rows:
            # Для секретных ачивок скрываем информацию если не выполнена
            is_secret = bool(row[11])
            is_completed = bool(row[23])
            
            if is_secret and not is_completed:
                achievements.append({
                    "id": row[0],
                    "code": row[1],
                    "name": "???",
                    "description": "Секретное достижение",
                    "icon": "🔒",
                    "category_id": row[5],
                    "category_name": row[6],
                    "category_icon": row[7],
                    "achievement_type": row[8],
                    "parent_id": row[9],
                    "level": row[10],
                    "is_secret": True,
                    "is_locked": True,
                    "requirement_type": row[12],
                    "requirement_count": row[13],
                    "progress": row[21],
                    "completed": False,
                    "reward_claimed": False,
                    "completed_at": None,
                    "claimed_at": None
                })
            else:
                achievements.append({
                    "id": row[0],
                    "code": row[1],
                    "name": row[2],
                    "description": row[3],
                    "icon": row[4],
                    "category_id": row[5],
                    "category_name": row[6],
                    "category_icon": row[7],
                    "achievement_type": row[8],
                    "parent_id": row[9],
                    "level": row[10],
                    "is_secret": is_secret,
                    "is_locked": False,
                    "requirement_type": row[12],
                    "requirement_count": row[13],
                    "requirement_item": row[14],
                    "reward_coins": row[15],
                    "reward_gems": row[16],
                    "reward_items": json.loads(row[17]) if row[17] else {},
                    "reward_multiplier": row[18],
                    "sort_order": row[19],
                    "is_active": bool(row[20]),
                    "progress": row[21],
                    "completed": is_completed,
                    "reward_claimed": bool(row[24]),
                    "completed_at": row[25],
                    "claimed_at": row[26]
                })
        
        return achievements
    
    async def get_achievement_by_id(self, achievement_id: int) -> Optional[Dict]:
        """Получает ачивку по ID"""
        row = await self.fetchone(
            """SELECT a.*, ac.name as category_name, ac.icon as category_icon
               FROM achievements a
               JOIN achievement_categories ac ON a.category_id = ac.category_id
               WHERE a.achievement_id = ?""",
            (achievement_id,)
        )
        if row:
            return {
                "id": row[0],
                "code": row[1],
                "name": row[2],
                "description": row[3],
                "icon": row[4],
                "category_id": row[5],
                "category_name": row[22],
                "category_icon": row[23],
                "achievement_type": row[6],
                "parent_id": row[7],
                "level": row[8],
                "event_end_date": row[9],
                "requirement_type": row[10],
                "requirement_count": row[11],
                "requirement_item": row[12],
                "reward_coins": row[13],
                "reward_gems": row[14],
                "reward_items": json.loads(row[15]) if row[15] else {},
                "reward_multiplier": row[16],
                "is_active": bool(row[17]),
                "is_secret": bool(row[18]),
                "sort_order": row[19]
            }
        return None
    
    async def get_player_achievement(self, user_id: int, achievement_id: int) -> Optional[Dict]:
        """Получает прогресс игрока по конкретной ачивке"""
        row = await self.fetchone(
            """SELECT pa.*, a.*, ac.name as category_name, ac.icon as category_icon
               FROM player_achievements pa
               JOIN achievements a ON pa.achievement_id = a.achievement_id
               JOIN achievement_categories ac ON a.category_id = ac.category_id
               WHERE pa.user_id = ? AND pa.achievement_id = ?""",
            (user_id, achievement_id)
        )
        if row:
            return {
                "progress_id": row[0],
                "user_id": row[1],
                "achievement_id": row[2],
                "progress": row[3],
                "completed": bool(row[4]),
                "reward_claimed": bool(row[5]),
                "completed_at": row[6],
                "claimed_at": row[7],
                "notified": bool(row[8]),
                "achievement": {
                    "id": row[11],
                    "code": row[12],
                    "name": row[13],
                    "description": row[14],
                    "icon": row[15],
                    "category_id": row[16],
                    "achievement_type": row[17],
                    "requirement_type": row[20],
                    "requirement_count": row[21],
                    "reward_coins": row[23],
                    "reward_gems": row[24],
                    "reward_items": json.loads(row[25]) if row[25] else {},
                    "reward_multiplier": row[26],
                    "is_secret": bool(row[28])
                }
            }
        return None
        
    async def check_and_update_achievements(self, user_id: int, trigger_type: str, 
                                             count: int = 1, item_code: str = None) -> List[Dict]:
        """Проверяет и обновляет достижения по триггеру"""
        user = await self.get_user(user_id)
        if not user:
            return []
        
        completed_achievements = []
        
        # Получаем все активные ачивки данного типа
        if item_code:
            rows = await self.fetchall(
                """SELECT a.* FROM achievements a
                   WHERE a.requirement_type = ? 
                   AND a.is_active = 1
                   AND (a.requirement_item IS NULL OR a.requirement_item = ?)""",
                (trigger_type, item_code)
            )
        else:
            rows = await self.fetchall(
                """SELECT a.* FROM achievements a
                   WHERE a.requirement_type = ? AND a.is_active = 1""",
                (trigger_type,)
            )
        
        for row in rows:
            ach_id = row[0]
            req_count = row[11]
            
            # Проверяем существование прогресса
            pa_row = await self.fetchone(
                "SELECT progress, completed FROM player_achievements WHERE user_id = ? AND achievement_id = ?",
                (user_id, ach_id)
            )
            
            if pa_row:
                if pa_row[1]:  # Уже выполнена
                    continue
                current_progress = pa_row[0]
            else:
                # Создаем запись прогресса
                await self.execute(
                    "INSERT INTO player_achievements (user_id, achievement_id, progress) VALUES (?, ?, 0)",
                    (user_id, ach_id), commit=True
                )
                current_progress = 0
            
            # Обновляем прогресс
            new_progress = current_progress + count
            
            # Проверяем выполнение
            if new_progress >= req_count:
                # Ачивка выполнена!
                await self.execute(
                    """UPDATE player_achievements 
                       SET progress = ?, completed = 1, completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                       WHERE user_id = ? AND achievement_id = ?""",
                    (req_count, user_id, ach_id), commit=True
                )
                
                # Логируем
                await self.log_achievement_progress(user_id, ach_id, current_progress, req_count, completed=True)
                
                # Получаем данные ачивки
                ach_data = await self.get_achievement_by_id(ach_id)
                completed_achievements.append(ach_data)
                
                # Разблокируем следующий уровень для многоуровневых
                if ach_data.get("achievement_type") == "multi":
                    await self._unlock_next_level(user_id, ach_id)
            else:
                # Обновляем прогресс
                await self.execute(
                    """UPDATE player_achievements 
                       SET progress = ?, updated_at = CURRENT_TIMESTAMP
                       WHERE user_id = ? AND achievement_id = ?""",
                    (new_progress, user_id, ach_id), commit=True
                )
        
        return completed_achievements
    
    async def _unlock_next_level(self, user_id: int, current_ach_id: int):
        """Разблокирует следующий уровень многоуровневой ачивки"""
        # Находим следующий уровень
        next_ach = await self.fetchone(
            """SELECT achievement_id FROM achievements 
               WHERE parent_achievement_id = ? AND level = (
                   SELECT level + 1 FROM achievements WHERE achievement_id = ?
               ) AND is_active = 1""",
            (current_ach_id, current_ach_id)
        )

        if next_ach:
            # Создаем запись для следующего уровня
            await self.execute(
                """INSERT OR IGNORE INTO player_achievements 
                   (user_id, achievement_id, progress) VALUES (?, ?, 0)""",
                (user_id, next_ach[0]), commit=True
            )
    
    async def claim_achievement_reward(self, user_id: int, achievement_id: int) -> Dict:
        """Выдает награду за выполненную ачивку"""
        pa = await self.get_player_achievement(user_id, achievement_id)
        
        if not pa:
            return {"success": False, "message": "Достижение не найдено"}
        
        if not pa["completed"]:
            return {"success": False, "message": "Достижение еще не выполнено"}
        
        if pa["reward_claimed"]:
            return {"success": False, "message": "Награда уже получена"}
        
        ach = pa["achievement"]
        rewards_given = []
        
        # Выдаем монеты
        if ach["reward_coins"] > 0:
            await self.update_balance(user_id, ach["reward_coins"])
            rewards_given.append(f"{ach['reward_coins']:,}🪙")
        
        # Выдаем кристаллы
        if ach["reward_gems"] > 0:
            await self.execute(
                "UPDATE users SET gems = COALESCE(gems, 0) + ? WHERE user_id = ?",
                (ach["reward_gems"], user_id), commit=True
            )
            rewards_given.append(f"{ach['reward_gems']:,}💎")
        
        # Выдаем предметы
        if ach["reward_items"]:
            for item_code, qty in ach["reward_items"].items():
                await self.add_inventory(user_id, item_code, qty)
                rewards_given.append(f"{item_code} x{qty}")
        
        # Обновляем множитель
        if ach["reward_multiplier"] > 0:
            await self.execute(
                "UPDATE users SET prestige_multiplier = prestige_multiplier + ? WHERE user_id = ?",
                (ach["reward_multiplier"], user_id), commit=True
            )
            rewards_given.append(f"+x{ach['reward_multiplier']:.1f} множитель")
        
        # Помечаем награду как полученную
        await self.execute(
            """UPDATE player_achievements 
               SET reward_claimed = 1, claimed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
               WHERE user_id = ? AND achievement_id = ?""",
            (user_id, achievement_id), commit=True
        )
        
        # Логируем
        await self.log_achievement_progress(
            user_id, achievement_id, pa["progress"], pa["progress"], 
            reward_claimed={"rewards": rewards_given}
        )
        
        return {
            "success": True,
            "rewards": rewards_given,
            "achievement_name": ach["name"],
            "achievement_icon": ach["icon"]
        }
    
    async def get_pending_rewards(self, user_id: int) -> List[Dict]:
        """Получает список ачивок с невостребованными наградами"""
        rows = await self.fetchall(
            """SELECT pa.achievement_id, a.name, a.icon, a.reward_coins, a.reward_gems
               FROM player_achievements pa
               JOIN achievements a ON pa.achievement_id = a.achievement_id
               WHERE pa.user_id = ? AND pa.completed = 1 AND pa.reward_claimed = 0""",
            (user_id,)
        )
        return [{"id": r[0], "name": r[1], "icon": r[2], "coins": r[3], "gems": r[4]} for r in rows]
    
    async def get_achievement_stats(self, user_id: int) -> Dict:
        """Получает статистику ачивок игрока"""
        # Всего ачивок
        total = await self.fetchone(
            "SELECT COUNT(*) FROM achievements WHERE is_active = 1 AND is_secret = 0"
        )
        
        # Выполнено ачивок
        completed = await self.fetchone(
            """SELECT COUNT(*) FROM player_achievements pa
               JOIN achievements a ON pa.achievement_id = a.achievement_id
               WHERE pa.user_id = ? AND pa.completed = 1 AND a.is_secret = 0""",
            (user_id,)
        )
        
        # Ожидают награды
        pending = await self.fetchone(
            """SELECT COUNT(*) FROM player_achievements 
               WHERE user_id = ? AND completed = 1 AND reward_claimed = 0""",
            (user_id,)
        )
        
        # Общая сумма наград
        rewards = await self.fetchone(
            """SELECT COALESCE(SUM(a.reward_coins), 0), COALESCE(SUM(a.reward_gems), 0)
               FROM player_achievements pa
               JOIN achievements a ON pa.achievement_id = a.achievement_id
               WHERE pa.user_id = ? AND pa.reward_claimed = 1""",
            (user_id,)
        )
        
        # По категориям
        categories = await self.fetchall(
            """SELECT ac.category_id, ac.name, ac.icon,
                       COUNT(DISTINCT a.achievement_id) as total,
                       COUNT(DISTINCT CASE WHEN pa.completed = 1 THEN a.achievement_id END) as completed
               FROM achievement_categories ac
               JOIN achievements a ON ac.category_id = a.category_id AND a.is_active = 1 AND a.is_secret = 0
               LEFT JOIN player_achievements pa ON a.achievement_id = pa.achievement_id AND pa.user_id = ?
               GROUP BY ac.category_id
               ORDER BY ac.sort_order""",
            (user_id,)
        )
        
        return {
            "total": total[0] if total else 0,
            "completed": completed[0] if completed else 0,
            "pending": pending[0] if pending else 0,
            "total_coins": rewards[0] if rewards else 0,
            "total_gems": rewards[1] if rewards else 0,
            "categories": [{"id": r[0], "name": r[1], "icon": r[2], "total": r[3], "completed": r[4]} for r in categories]
        }
    
    async def get_achievement_history(self, user_id: int, limit: int = 20) -> List[Dict]:
        """Получает историю получения ачивок"""
        rows = await self.fetchall(
            """SELECT al.*, a.name, a.icon, a.category_id, ac.name as category_name
               FROM achievement_logs al
               JOIN achievements a ON al.achievement_id = a.achievement_id
               JOIN achievement_categories ac ON a.category_id = ac.category_id
               WHERE al.user_id = ? AND al.action = 'completed'
               ORDER BY al.created_at DESC
               LIMIT ?""",
            (user_id, limit)
        )
        return [{
            "id": r[0],
            "achievement_id": r[2],
            "action": r[3],
            "created_at": r[7],
            "name": r[8],
            "icon": r[9],
            "category_id": r[10],
            "category_name": r[11]
        } for r in rows]
    
    async def log_achievement_progress(self, user_id: int, achievement_id: int, 
                                        progress_before: int, progress_after: int,
                                        completed: bool = False, reward_claimed: dict = None):
        """Логирует прогресс достижения"""
        action = "completed" if completed else ("reward_claimed" if reward_claimed else "progress_updated")
        await self.execute(
            """INSERT INTO achievement_logs 
               (user_id, achievement_id, action, progress_before, progress_after, reward_claimed)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, achievement_id, action, progress_before, progress_after,
             json.dumps(reward_claimed) if reward_claimed else None), commit=True
        )
    
    # ==================== АДМИН-МЕТОДЫ ДЛЯ АЧИВОК ====================
    
    async def admin_create_achievement(self, data: Dict) -> int:
        """Создает новое достижение (для админки)"""
        await self.execute(
            """INSERT INTO achievements 
               (code, name, description, icon, category_id, achievement_type, 
                parent_achievement_id, level, event_end_date,
                requirement_type, requirement_count, requirement_item,
                reward_coins, reward_gems, reward_items_json, reward_multiplier,
                is_secret, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data['code'], data['name'], data['description'], data.get('icon', '🏅'),
             data['category_id'], data.get('type', 'regular'),
             data.get('parent_id'), data.get('level', 1), data.get('event_end_date'),
             data['requirement_type'], data['requirement_count'], data.get('requirement_item'),
             data.get('reward_coins', 0), data.get('reward_gems', 0),
             json.dumps(data.get('reward_items', {})), data.get('reward_multiplier', 0),
             1 if data.get('is_secret') else 0, data.get('sort_order', 0)),
            commit=True
        )
        row = await self.fetchone("SELECT last_insert_rowid()")
        return row[0] if row else None
    
    def clear_cache(self):
        """Очищает все кэши"""
        self._admin_roles_cache.clear()
        self._achievement_categories_cache = None
    
    async def admin_update_achievement(self, achievement_id: int, data: Dict) -> bool:
        """Обновляет достижение"""
        fields = []
        values = []
        
        field_map = {
            'name': 'name', 'description': 'description', 'icon': 'icon',
            'category_id': 'category_id', 'requirement_type': 'requirement_type',
            'requirement_count': 'requirement_count', 'requirement_item': 'requirement_item',
            'reward_coins': 'reward_coins', 'reward_gems': 'reward_gems',
            'reward_multiplier': 'reward_multiplier', 'is_active': 'is_active',
            'is_secret': 'is_secret', 'sort_order': 'sort_order'
        }
        
        for key, db_field in field_map.items():
            if key in data:
                fields.append(f"{db_field} = ?")
                values.append(data[key])
        
        if 'reward_items' in data:
            fields.append("reward_items_json = ?")
            values.append(json.dumps(data['reward_items']))
        
        if not fields:
            return False
        
        values.append(achievement_id)
        
        await self.execute(
            f"UPDATE achievements SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE achievement_id = ?",
            tuple(values), commit=True
        )
        return True
    
    async def admin_delete_achievement(self, achievement_id: int, full_delete: bool = False) -> bool:
        """Удаляет или деактивирует ачивку"""
        if full_delete:
            await self.execute(
                "DELETE FROM player_achievements WHERE achievement_id = ?",
                (achievement_id,), commit=True
            )
            await self.execute(
                "DELETE FROM achievements WHERE achievement_id = ?",
                (achievement_id,), commit=True
            )
        else:
            await self.execute(
                "UPDATE achievements SET is_active = 0 WHERE achievement_id = ?",
                (achievement_id,), commit=True
            )
        return True
    
    async def admin_get_all_achievements(self, active_only: bool = False) -> List[Dict]:
        """Получает все ачивки для админки"""
        if active_only:
            rows = await self.fetchall(
                """SELECT a.*, ac.name as category_name,
                          COUNT(DISTINCT pa.user_id) as players_count,
                          COUNT(DISTINCT CASE WHEN pa.completed = 1 THEN pa.user_id END) as completed_count
                   FROM achievements a
                   JOIN achievement_categories ac ON a.category_id = ac.category_id
                   LEFT JOIN player_achievements pa ON a.achievement_id = pa.achievement_id
                   WHERE a.is_active = 1
                   GROUP BY a.achievement_id
                   ORDER BY ac.sort_order, a.sort_order"""
            )
        else:
            rows = await self.fetchall(
                """SELECT a.*, ac.name as category_name,
                          COUNT(DISTINCT pa.user_id) as players_count,
                          COUNT(DISTINCT CASE WHEN pa.completed = 1 THEN pa.user_id END) as completed_count
                   FROM achievements a
                   JOIN achievement_categories ac ON a.category_id = ac.category_id
                   LEFT JOIN player_achievements pa ON a.achievement_id = pa.achievement_id
                   GROUP BY a.achievement_id
                   ORDER BY a.is_active DESC, ac.sort_order, a.sort_order"""
            )
        
        return [{
            "id": r[0], "code": r[1], "name": r[2], "description": r[3], "icon": r[4],
            "category_id": r[5], "category_name": r[22],
            "type": r[6], "parent_id": r[7], "level": r[8],
            "requirement_type": r[10], "requirement_count": r[11],
            "reward_coins": r[13], "reward_gems": r[14],
            "is_active": bool(r[17]), "is_secret": bool(r[18]),
            "players_count": r[23], "completed_count": r[24]
        } for r in rows]
    
    async def admin_give_achievement(self, admin_id: int, user_id: int, achievement_id: int) -> Dict:
        """Выдает ачивку игроку вручную"""
        ach = await self.get_achievement_by_id(achievement_id)
        if not ach:
            return {"success": False, "message": "Ачивка не найдена"}
        
        # Проверяем существование
        exists = await self.fetchone(
            "SELECT 1 FROM player_achievements WHERE user_id = ? AND achievement_id = ?",
            (user_id, achievement_id)
        )
        
        if exists:
            return {"success": False, "message": "Игрок уже имеет эту ачивку"}
        
        # Создаем запись
        await self.execute(
            """INSERT INTO player_achievements 
               (user_id, achievement_id, progress, completed, completed_at)
               VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)""",
            (user_id, achievement_id, ach["requirement_count"]), commit=True
        )
        
        # Логируем админ-действие
        await self.log_admin_action(admin_id, "give_achievement", user_id, 
                                     details={"achievement_id": achievement_id, "achievement_name": ach["name"]})
        
        return {
            "success": True,
            "achievement_name": ach["name"],
            "achievement_icon": ach["icon"],
            "rewards": {
                "coins": ach["reward_coins"],
                "gems": ach["reward_gems"],
                "items": ach.get("reward_items", {})
            }
        }
    
    async def admin_get_achievement_stats(self) -> Dict:
        """Получает статистику по ачивкам"""
        # Всего получений
        total_completions = await self.fetchone(
            "SELECT COUNT(*) FROM player_achievements WHERE completed = 1"
        )
        
        # Уникальных игроков с ачивками
        unique_players = await self.fetchone(
            "SELECT COUNT(DISTINCT user_id) FROM player_achievements WHERE completed = 1"
        )
        
        # Среднее количество ачивок на игрока
        avg_achievements = await self.fetchone(
            """SELECT AVG(ach_count) FROM (
                SELECT COUNT(*) as ach_count 
                FROM player_achievements 
                WHERE completed = 1 
                GROUP BY user_id
            )"""
        )
        
        # Топ-5 популярных
        popular = await self.fetchall(
            """SELECT a.name, a.icon, COUNT(*) as count
               FROM player_achievements pa
               JOIN achievements a ON pa.achievement_id = a.achievement_id
               WHERE pa.completed = 1
               GROUP BY a.achievement_id
               ORDER BY count DESC
               LIMIT 5"""
        )
        
        # Редкие ачивки (< 1%)
        total_players = await self.fetchone("SELECT COUNT(*) FROM users WHERE is_banned = 0")
        rare = await self.fetchall(
            """SELECT a.name, a.icon, COUNT(*) as count
               FROM player_achievements pa
               JOIN achievements a ON pa.achievement_id = a.achievement_id
               WHERE pa.completed = 1
               GROUP BY a.achievement_id
               HAVING CAST(COUNT(*) AS REAL) / ? < 0.01
               ORDER BY count ASC
               LIMIT 5""",
            (total_players[0] if total_players else 1,)
        )
        
        return {
            "total_completions": total_completions[0] if total_completions else 0,
            "unique_players": unique_players[0] if unique_players else 0,
            "avg_per_player": round(avg_achievements[0], 2) if avg_achievements and avg_achievements[0] else 0,
            "popular": [{"name": r[0], "icon": r[1], "count": r[2]} for r in popular],
            "rare": [{"name": r[0], "icon": r[1], "count": r[2]} for r in rare]
        }
    
    # Старые методы для обратной совместимости
    async def get_achievements(self, user_id: int) -> List[Dict]:
        """Устаревший метод - используйте get_achievements_by_category"""
        return await self.get_achievements_by_category(user_id)
    
    async def check_achievements(self, user_id: int) -> List[Dict]:
        """Устаревший метод - используйте check_and_update_achievements"""
        return await self.check_and_update_achievements(user_id, "legacy")
    
    # АДМИНИСТРАТОРЫ
    async def get_admin_role(self, user_id: int, use_cache: bool = True) -> Optional[str]:
        """Получает роль администратора с кэшированием

        Args:
            user_id: ID пользователя
            use_cache: Использовать кэш (по умолчанию True)

        Returns:
            Роль администратора или None
        """
        if use_cache and user_id in self._admin_roles_cache:
            return self._admin_roles_cache[user_id]

        row = await self.fetchone(
            "SELECT role FROM admin_roles WHERE user_id = ?",
            (user_id,)
        )
        role = row[0] if row else None

        if use_cache:
            self._admin_roles_cache[user_id] = role

        return role
    
    async def is_admin(self, user_id: int) -> bool:
        """Проверяет является ли пользователь админом"""
        role = await self.get_admin_role(user_id)
        return role in ('creator', 'admin', 'moderator')
    
    async def is_creator(self, user_id: int) -> bool:
        """Проверяет является ли пользователь создателем"""
        role = await self.get_admin_role(user_id)
        return role == 'creator'
    
    async def can_assign_moderator(self, user_id: int) -> bool:
        """Проверяет может ли пользователь назначать модераторов"""
        role = await self.get_admin_role(user_id)
        return role in ('creator', 'admin')
    
    async def assign_admin_role(self, admin_id: int, target_id: int, role: str) -> bool:
        """Назначает роль администратора"""
        if role == 'moderator' and not await self.can_assign_moderator(admin_id):
            return False
        if role in ('admin', 'creator') and not await self.is_creator(admin_id):
            return False
        
        await self.execute(
            """INSERT OR REPLACE INTO admin_roles (user_id, role, assigned_by, assigned_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)""",
            (target_id, role, admin_id), commit=True
        )
        
        # Обновляем кэш
        self._admin_roles_cache[target_id] = role

        # Логируем
        await self.log_admin_action(admin_id, f"assign_{role}", target_id, f"Assigned role {role}")
        return True
    
    async def remove_admin_role(self, admin_id: int, target_id: int) -> bool:
        """Удаляет роль администратора"""
        if not await self.can_assign_moderator(admin_id):
            return False
        
        # Нельзя удалить создателя
        if await self.is_creator(target_id):
            return False
        
        await self.execute(
            "DELETE FROM admin_roles WHERE user_id = ?",
            (target_id,), commit=True
        )
        
        # Обновляем кэш
        if target_id in self._admin_roles_cache:
            del self._admin_roles_cache[target_id]

        await self.log_admin_action(admin_id, "remove_role", target_id, "Removed admin role")
        return True
    
    async def get_admins(self) -> List[Dict]:
        """Получает список всех администраторов"""
        rows = await self.fetchall(
            """SELECT ar.user_id, ar.role, u.username, u.first_name
               FROM admin_roles ar
               JOIN users u ON ar.user_id = u.user_id
               ORDER BY CASE ar.role 
                   WHEN 'creator' THEN 1 
                   WHEN 'admin' THEN 2 
                   WHEN 'moderator' THEN 3 
               END"""
        )
        
        return [{"user_id": r[0], "role": r[1], "username": r[2], "first_name": r[3]} for r in rows]
    
    async def log_admin_action(self, admin_id: int, action: str, target_id: int = None, details: str = None):
        """Логирует действие администратора"""
        await self.execute(
            """INSERT INTO admin_logs (admin_id, action, target_user_id, details)
               VALUES (?, ?, ?, ?)""",
            (admin_id, action, target_id, details), commit=True
        )
    
    async def get_admin_logs(self, limit: int = 50) -> List[Dict]:
        """Получает последние логи администраторов"""
        rows = await self.fetchall(
            """SELECT al.*, u.username as admin_name, tu.username as target_name
               FROM admin_logs al
               JOIN users u ON al.admin_id = u.user_id
               LEFT JOIN users tu ON al.target_user_id = tu.user_id
               ORDER BY al.created_at DESC
               LIMIT ?""",
            (limit,)
        )
        
        logs = []
        for r in rows:
            logs.append({
                "log_id": r[0],
                "admin_id": r[1],
                "admin_name": r[5],
                "action": r[2],
                "target_id": r[3],
                "target_name": r[6],
                "details": r[4],
                "created_at": r[5]
            })
        return logs
    
    # УПРАВЛЕНИЕ ИГРОКАМИ (для админов)
    async def give_coins(self, admin_id: int, target_id: int, amount: int, reason: str = None) -> bool:
        """Выдает монеты игроку"""
        user = await self.get_user(target_id)
        old_balance = user['balance'] if user else 0
        
        await self.update_balance(target_id, amount)
        
        new_balance = old_balance + amount
        
        # Логируем админ-действие
        await self.log_admin_action(
            admin_id, "give_coins", target_id,
            old_value={'balance': old_balance},
            new_value={'balance': new_balance},
            reason=reason,
            details={'amount': amount}
        )
        
        # Логируем экономику
        await self.log_economy(
            target_id, 'earn', amount, 'coins',
            balance_after=new_balance, source='admin', source_id=str(admin_id),
            details={'reason': reason, 'admin_id': admin_id}
        )
        
        return True
    
    async def give_item(self, admin_id: int, target_id: int, item_code: str, quantity: int, reason: str = None) -> bool:
        """Выдает предмет игроку"""
        await self.add_inventory(target_id, item_code, quantity)
        
        # Логируем админ-действие
        await self.log_admin_action(
            admin_id, "give_item", target_id,
            new_value={'item': item_code, 'quantity': quantity},
            reason=reason
        )
        
        # Логируем экономику
        await self.log_economy(
            target_id, 'earn', quantity, 'item', item_id=item_code,
            source='admin', source_id=str(admin_id),
            details={'reason': reason, 'admin_id': admin_id}
        )
    
        return True
    
    async def ban_user(self, admin_id: int, target_id: int, reason: str, duration_hours: int = None) -> bool:
        """Банит пользователя"""
        old_user = await self.get_user(target_id)
        
        if duration_hours:
            ban_until = datetime.now() + timedelta(hours=duration_hours)
            await self.execute(
                """UPDATE users SET is_banned = 1, ban_reason = ?, ban_until = ?
                   WHERE user_id = ?""",
                (reason, ban_until, target_id), commit=True
            )
        else:
            ban_until = None
            await self.execute(
                """UPDATE users SET is_banned = 1, ban_reason = ?, ban_until = NULL
                   WHERE user_id = ?""",
                (reason, target_id), commit=True
            )
        
        # Логируем админ-действие
        await self.log_admin_action(
            admin_id, "ban", target_id,
            old_value={'is_banned': 0},
            new_value={'is_banned': 1, 'ban_reason': reason, 'ban_until': str(ban_until) if ban_until else None},
            reason=reason,
            details={'duration_hours': duration_hours}
        )
    
        # Логируем безопасность
        await self.log_security(
            'ban', user_id=target_id, admin_id=admin_id,
            ban_reason=reason, ban_duration=duration_hours
        )
        
        return True
    
    async def unban_user(self, admin_id: int, target_id: int) -> bool:
        """Разбанивает пользователя"""
        await self.execute(
            """UPDATE users SET is_banned = 0, ban_reason = NULL, ban_until = NULL
               WHERE user_id = ?""",
            (target_id,), commit=True
        )
        
        # Логируем админ-действие
        await self.log_admin_action(
            admin_id, "unban", target_id,
            old_value={'is_banned': 1},
            new_value={'is_banned': 0}
        )
        
        # Логируем безопасность
        await self.log_security('unban', user_id=target_id, admin_id=admin_id)
        
        return True
    
    # СЕЗОННЫЕ СОБЫТИЯ
    async def get_active_event(self) -> Optional[Dict]:
        """Получает активное сезонное событие"""
        row = await self.fetchone(
            """SELECT * FROM seasonal_events 
               WHERE is_active = 1 
               AND start_date <= CURRENT_TIMESTAMP 
               AND end_date > CURRENT_TIMESTAMP
               ORDER BY start_date DESC LIMIT 1"""
        )
        
        if row:
            return {
                "event_id": row[0],
                "name": row[1],
                "description": row[2],
                "season": row[3],
                "start_date": row[4],
                "end_date": row[5],
                "multiplier": row[6]
            }
        return None
    
    async def update_event_score(self, user_id: int, score: int):
        """Обновляет счет в событии"""
        event = await self.get_active_event()
        if not event:
            return
            
        await self.execute(
            """INSERT INTO event_leaderboard (event_id, user_id, score)
               VALUES (?, ?, ?)
               ON CONFLICT(event_id, user_id) DO UPDATE SET
               score = score + ?, updated_at = CURRENT_TIMESTAMP""",
            (event['event_id'], user_id, score, score), commit=True
        )
    
    async def get_event_leaderboard(self, limit: int = 10) -> List[Dict]:
        """Получает лидерборд события"""
        event = await self.get_active_event()
        if not event:
            return []
        
        rows = await self.fetchall(
            """SELECT el.user_id, u.username, u.first_name, el.score
               FROM event_leaderboard el
               JOIN users u ON el.user_id = u.user_id
               WHERE el.event_id = ?
               ORDER BY el.score DESC
               LIMIT ?""",
            (event['event_id'], limit)
        )
        
        return [{"user_id": r[0], "username": r[1], "name": r[2], "score": r[3]} for r in rows]
    
    # ==================== СИСТЕМА ЛОГИРОВАНИЯ ====================
    
    async def log_event(self, log_group: str, log_level: str, action: str, 
                       user_id: int = None, target_id: int = None, target_type: str = None,
                       details: dict = None, ip_address: str = None, session_id: str = None):
        """Универсальная функция для записи лога"""
        import json
        username = None
        if user_id:
            user = await self.get_user(user_id)
            username = user.get('username') if user else None
        
        await self.execute(
            """INSERT INTO logs 
               (log_group, log_level, user_id, username, action, target_id, target_type, details, ip_address, session_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (log_group, log_level, user_id, username, action, target_id, target_type,
             json.dumps(details) if details else None, ip_address, session_id),
            commit=True
        )
    
    
    
    async def log_progression(self, user_id: int, progression_type: str,
                             old_value: int = None, new_value: int = None,
                             achievement_id: str = None, reward_claimed: bool = False,
                             details: dict = None):
        """Логирует прогресс игрока"""
        import json
        
        await self.execute(
            """INSERT INTO progression_logs 
               (user_id, progression_type, old_value, new_value, achievement_id, reward_claimed, details)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, progression_type, old_value, new_value, achievement_id,
             1 if reward_claimed else 0, json.dumps(details) if details else None),
            commit=True
        )
    
    async def log_security(self, event_type: str, user_id: int = None, admin_id: int = None,
                          is_automated: bool = False, ban_reason: str = None, 
                          ban_duration: int = None, ip_address: str = None,
                          user_agent: str = None, details: dict = None):
        """Логирует события безопасности"""
        import json
        
        level = 'WARNING' if event_type in ('ban', 'failed_action') else 'INFO'
        if event_type == 'suspicious':
            level = 'WARNING'
        
        await self.execute(
            """INSERT INTO security_logs 
               (event_type, user_id, admin_id, is_automated, ban_reason, 
                ban_duration, ip_address, user_agent, details)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (event_type, user_id, admin_id, 1 if is_automated else 0, ban_reason,
             ban_duration, ip_address, user_agent, json.dumps(details) if details else None),
            commit=True
        )
        
        # Пишем в общий лог
        await self.log_event('security', level, event_type, user_id or admin_id, user_id, 'user', details)
    
    async def log_achievement(self, user_id: int, achievement_id: str, achievement_name: str,
                             category_id: str = None, progress_before: int = None,
                             progress_after: int = None, is_completed: bool = False,
                             reward_earned: dict = None):
        """Логирует достижения"""
        import json
        
        await self.execute(
            """INSERT INTO achievement_logs 
               (user_id, achievement_id, achievement_name, category_id, 
                progress_before, progress_after, is_completed, reward_earned)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, achievement_id, achievement_name, category_id,
             progress_before, progress_after, 1 if is_completed else 0,
             json.dumps(reward_earned) if reward_earned else None),
            commit=True
        )
        
        if is_completed:
            await self.log_event('achievements', 'INFO', 'achievement_unlocked', user_id, None, None, {
                'achievement_id': achievement_id, 'achievement_name': achievement_name
            })
    
    async def log_promo(self, promo_code: str, action: str, user_id: int = None,
                       admin_id: int = None, reward_given: dict = None,
                       success: bool = True, error_reason: str = None, details: dict = None):
        """Логирует промо-акции"""
        import json
        
        await self.execute(
            """INSERT INTO promo_logs 
               (promo_code, user_id, admin_id, action, reward_given, success, error_reason, details)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (promo_code, user_id, admin_id, action,
             json.dumps(reward_given) if reward_given else None,
             1 if success else 0, error_reason, json.dumps(details) if details else None),
            commit=True
        )
    
    # АНАЛИТИКА И СТАТИСТИКА
    
    async def get_logs_stats(self, days: int = 7) -> dict:
        """Получает статистику по логам"""
        # Общее количество по группам
        rows = await self.fetchall(
            """SELECT log_group, COUNT(*) as count, COUNT(DISTINCT user_id) as unique_users
               FROM logs
               WHERE created_at > datetime('now', '-{} days')
               GROUP BY log_group
               ORDER BY count DESC""".format(days)
        )
        
        stats = {
            'groups': {row[0]: {'count': row[1], 'unique_users': row[2]} for row in rows},
            'total': sum(row[1] for row in rows)
        }
        
        return stats
    
    async def get_economy_stats(self, days: int = 30) -> list:
        """Статистика экономики"""
        rows = await self.fetchall(
            """SELECT 
                u.username,
                SUM(CASE WHEN e.operation_type = 'earn' THEN e.amount ELSE 0 END) as total_earned,
                SUM(CASE WHEN e.operation_type = 'spend' THEN e.amount ELSE 0 END) as total_spent,
                COUNT(*) as transactions
               FROM economy_logs e
               JOIN users u ON e.user_id = u.user_id
               WHERE e.created_at > datetime('now', '-{} days')
               GROUP BY e.user_id, u.username
               ORDER BY total_earned DESC
               LIMIT 10""".format(days)
        )
        
        return [{'username': row[0], 'earned': row[1], 'spent': row[2], 'transactions': row[3]} for row in rows]
    
    async def get_active_hours_stats(self) -> list:
        """Активность по часам"""
        rows = await self.fetchall(
            """SELECT 
                strftime('%H', created_at) as hour,
                COUNT(DISTINCT user_id) as active_users,
                COUNT(*) as total_actions
               FROM logs
               WHERE created_at > datetime('now', '-1 day')
               AND user_id IS NOT NULL
               GROUP BY hour
               ORDER BY hour"""
        )
        
        return [{'hour': row[0], 'users': row[1], 'actions': row[2]} for row in rows]
    
    async def get_security_stats(self, days: int = 7) -> list:
        """Статистика безопасности"""
        rows = await self.fetchall(
            """SELECT 
                date(created_at) as date,
                COUNT(*) as total_events,
                SUM(CASE WHEN event_type = 'ban' THEN 1 ELSE 0 END) as bans,
                SUM(CASE WHEN is_automated = 1 THEN 1 ELSE 0 END) as auto_actions,
                COUNT(DISTINCT admin_id) as admins_active
               FROM security_logs
               WHERE created_at > datetime('now', '-{} days')
               GROUP BY date
               ORDER BY date""".format(days)
        )
        
        return [{'date': row[0], 'total': row[1], 'bans': row[2], 'auto': row[3], 'admins': row[4]} for row in rows]
    
    async def get_filtered_logs(self, log_group: str = None, log_level: str = None,
                                user_id: int = None, action: str = None,
                                start_date: str = None, end_date: str = None,
                                limit: int = 50, offset: int = 0) -> list:
        """Получает логи с фильтрацией"""
        query = "SELECT * FROM logs WHERE 1=1"
        params = []
        
        if log_group:
            query += " AND log_group = ?"
            params.append(log_group)
        if log_level:
            query += " AND log_level = ?"
            params.append(log_level)
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if action:
            query += " AND action LIKE ?"
            params.append(f"%{action}%")
        if start_date:
            query += " AND created_at >= ?"
            params.append(start_date)
        if end_date:
            query += " AND created_at <= ?"
            params.append(end_date)
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        rows = await self.fetchall(query, params)
        
        import json
        logs = []
        for row in rows:
            logs.append({
                'log_id': row[0],
                'group': row[1],
                'level': row[2],
                'user_id': row[3],
                'username': row[4],
                'action': row[5],
                'target_id': row[6],
                'target_type': row[7],
                'details': json.loads(row[8]) if row[8] else None,
                'created_at': row[11]
            })
        
        return logs
    
    async def cleanup_old_logs(self, days: int = 90):
        """Очищает старые логи"""
        import logging
        
        for table in ['logs', 'admin_logs', 'economy_logs', 'progression_logs', 
                      'security_logs', 'achievement_logs', 'promo_logs']:
            await self.execute(
                f"DELETE FROM {table} WHERE created_at < datetime('now', '-{days} days')",
                commit=True
            )
        
        logging.info(f"Cleaned up logs older than {days} days")
    
    # УВЕДОМЛЕНИЯ
    async def add_notification(self, user_id: int, notif_type: str, message: str):
        """Добавляет уведомление"""
        await self.execute(
            """INSERT INTO notifications (user_id, type, message)
               VALUES (?, ?, ?)""",
            (user_id, notif_type, message), commit=True
        )
    
    async def get_pending_notifications(self, user_id: int = None) -> List[Dict]:
        """Получает неотправленные уведомления"""
        if user_id:
            rows = await self.fetchall(
                """SELECT * FROM notifications 
                   WHERE user_id = ? AND sent = 0
                   ORDER BY created_at""",
                (user_id,)
            )
        else:
            rows = await self.fetchall(
                """SELECT * FROM notifications 
                   WHERE sent = 0
                   ORDER BY created_at"""
            )
        
        return [{"id": r[0], "user_id": r[1], "type": r[2], "message": r[3], "created_at": r[4]} for r in rows]
    
    async def mark_notification_sent(self, notification_id: int):
        """Помечает уведомление как отправленное"""
        await self.execute(
            "UPDATE notifications SET sent = 1 WHERE notification_id = ?",
            (notification_id,), commit=True
        )
    
    async def _run_migrations(self, db: aiosqlite.Connection):
        """Проверяет и выполняет необходимые миграции схемы БД"""
        # Получаем список существующих таблиц
        async with db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
            tables = {row[0] for row in await cursor.fetchall()}
        
        # Проверяем структуру таблицы achievements
        if 'achievements' in tables:
            try:
                async with db.execute("PRAGMA table_info(achievements)") as cursor:
                    columns = {row[1] for row in await cursor.fetchall()}
                
                # Если нет category_id, нужна миграция
                if 'category_id' not in columns:
                    logging.info("Migration needed: adding category_id to achievements table")
                    await self._migrate_achievements_v1(db)
            except Exception as e:
                logging.warning(f"Could not check achievements schema: {e}")
        
        # Проверяем существование таблицы achievement_categories
        if 'achievement_categories' not in tables:
            logging.info("Migration needed: creating achievement_categories table")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS achievement_categories (
                    category_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    icon TEXT DEFAULT '🏆',
                    description TEXT,
                    sort_order INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()
    
    async def _migrate_achievements_v1(self, db: aiosqlite.Connection):
        """Миграция: добавление category_id в таблицу achievements"""
        try:
            # Создаем временную таблицу с новой структурой
            await db.execute("""
                CREATE TABLE achievements_new (
                    achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    icon TEXT DEFAULT '🏅',
                    category_id TEXT NOT NULL DEFAULT 'harvest',
                    achievement_type TEXT DEFAULT 'regular' CHECK(achievement_type IN ('regular', 'multi', 'secret', 'event')),
                    parent_achievement_id INTEGER DEFAULT NULL,
                    level INTEGER DEFAULT 1,
                    event_end_date TIMESTAMP DEFAULT NULL,
                    requirement_type TEXT NOT NULL,
                    requirement_count INTEGER NOT NULL,
                    requirement_item TEXT DEFAULT NULL,
                    reward_coins INTEGER DEFAULT 0,
                    reward_gems INTEGER DEFAULT 0,
                    reward_items_json TEXT DEFAULT '{}',
                    reward_multiplier REAL DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    is_secret INTEGER DEFAULT 0,
                    sort_order INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (category_id) REFERENCES achievement_categories(category_id) ON DELETE CASCADE,
                    FOREIGN KEY (parent_achievement_id) REFERENCES achievements_new(achievement_id) ON DELETE CASCADE
                )
            """)
            
            # Переносим данные, если возможно
            try:
                await db.execute("""
                    INSERT INTO achievements_new (achievement_id, code, name, description, icon, category_id, requirement_type, requirement_count)
                    SELECT achievement_id, code, name, description, icon, 'harvest', requirement_type, requirement_count 
                    FROM achievements
                """)
                logging.info("Data migrated from old achievements table")
            except Exception as e:
                logging.warning(f"Could not migrate old achievements data: {e}")
            
            # Удаляем старую таблицу
            await db.execute("DROP TABLE achievements")
            # Переименовываем новую
            await db.execute("ALTER TABLE achievements_new RENAME TO achievements")
            
            # Создаем индексы
            await db.execute("CREATE INDEX IF NOT EXISTS idx_achievements_category ON achievements(category_id, is_active)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_achievements_type ON achievements(achievement_type, is_active)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_achievements_requirement ON achievements(requirement_type, is_active)")
            
            await db.commit()
            logging.info("Migration completed: achievements table updated")
        except Exception as e:
            logging.error(f"Migration failed: {e}")
            raise
    
    async def init_from_sql(self, sql_file: str):
        """Выполняет SQL скрипт инициализации с автомиграцией"""
        import os
        if not os.path.exists(sql_file):
            logging.warning(f"SQL file {sql_file} not found, skipping DB initialization")
            return
            
        async with self.lock:
            # Закрываем текущее соединение если есть
            if self._db:
                await self._db.close()
                self._db = None
            
            # Создаем новое соединение для выполнения скрипта
            db = await aiosqlite.connect(self.db_path)
            try:
                # Сначала выполняем миграции
                await self._run_migrations(db)
                
                # Затем выполняем основной SQL скрипт
                with open(sql_file, 'r', encoding='utf-8') as f:
                    sql = f.read()
                await db.executescript(sql)
                await db.commit()
                logging.info(f"Database initialized from {sql_file}")
            finally:
                await db.close()

    
# Дополнительные методы для админ-панели
    
    
    
    async def get_all_promocodes(self, active_only: bool = False) -> List[Dict]:
        """Получает все промокоды"""
        query = "SELECT * FROM promocodes"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY created_at DESC"
        
        rows = await self.fetchall(query)
        
        import json
        promos = []
        for r in rows:
            promos.append({
                "id": r[0],
                "code": r[1],
                "reward_json": r[2],
                "max_uses": r[3],
                "times_used": r[4],
                "valid_until": r[5],
                "is_active": bool(r[6]),
                "created_by": r[7],
                "created_at": r[8]
            })
        return promos
    
    async def get_promocode_by_code(self, code: str) -> Optional[Dict]:
        """Получает промокод по коду"""
        row = await self.fetchone(
            "SELECT * FROM promocodes WHERE code = ?",
            (code,)
        )
        
        if not row:
            return None
        
        import json
        return {
            "id": row[0],
            "code": row[1],
            "reward_json": row[2],
            "max_uses": row[3],
            "times_used": row[4],
            "valid_until": row[5],
            "is_active": bool(row[6]),
            "created_by": row[7],
            "created_at": row[8]
        }
    
    async def create_promocode(self, admin_id: int, code: str, reward: dict, 
                              max_uses: int, valid_until: str = None) -> int:
        """Создает новый промокод"""
        import json
        await self.execute(
            """INSERT INTO promocodes (code, reward_json, max_uses, valid_until, created_by)
               VALUES (?, ?, ?, ?, ?)""",
            (code, json.dumps(reward), max_uses, valid_until, admin_id),
            commit=True
        )
        
        row = await self.fetchone("SELECT last_insert_rowid()")
        promo_id = row[0] if row else None
        
        # Логируем
        await self.log_promo(code, "create", admin_id=admin_id, reward_given=reward, 
                           details={"max_uses": max_uses, "valid_until": valid_until})
        
        return promo_id
    
    async def update_promocode(self, promo_id: int, code: str = None, reward: dict = None,
                             max_uses: int = None, valid_until: str = None, 
                             is_active: bool = None) -> bool:
        """Обновляет промокод"""
        import json
        updates = []
        params = []
        
        if code is not None:
            updates.append("code = ?")
            params.append(code)
        if reward is not None:
            updates.append("reward_json = ?")
            params.append(json.dumps(reward))
        if max_uses is not None:
            updates.append("max_uses = ?")
            params.append(max_uses)
        if valid_until is not None:
            updates.append("valid_until = ?")
            params.append(valid_until)
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)
        
        if not updates:
            return False
        
        params.append(promo_id)
        await self.execute(
            f"UPDATE promocodes SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
            commit=True
        )
        
        await self.log_promo(str(promo_id), "update", details={"fields": updates})
        return True
    
    async def toggle_promocode(self, promo_id: int) -> bool:
        """Переключает активность промокода"""
        await self.execute(
            "UPDATE promocodes SET is_active = NOT is_active WHERE id = ?",
            (promo_id,),
            commit=True
        )
        
        await self.log_promo(str(promo_id), "toggle")
        return True
    
    async def delete_promocode(self, promo_id: int, hard_delete: bool = False) -> bool:
        """Удаляет промокод (мягкое или полное удаление)"""
        if hard_delete:
            await self.execute(
                "DELETE FROM promocodes WHERE id = ?",
                (promo_id,),
                commit=True
            )
        else:
            await self.execute(
                "UPDATE promocodes SET is_active = 0 WHERE id = ?",
                (promo_id,),
                commit=True
            )
        
        await self.log_promo(str(promo_id), "delete", details={"hard": hard_delete})
        return True
    
    async def get_promocode_stats(self, promo_id: int = None) -> Dict:
        """Возвращает статистику промокодов"""
        stats = {}
        
        if promo_id:
            row = await self.fetchone(
                """SELECT p.code, p.max_uses, p.times_used, COUNT(pa.id) as activations
                   FROM promocodes p 
                   LEFT JOIN promo_activations pa ON p.code = pa.promo_code
                   WHERE p.id = ?
                   GROUP BY p.id""",
                (promo_id,)
            )
            if row:
                stats = {
                    "code": row[0],
                    "max_uses": row[1],
                    "times_used": row[2],
                    "activations": row[3]
                }
        else:
            rows = await self.fetchall(
                """SELECT p.code, p.max_uses, p.times_used, COUNT(pa.id) as activations
                   FROM promocodes p 
                   LEFT JOIN promo_activations pa ON p.code = pa.promo_code
                   GROUP BY p.id
                   ORDER BY p.times_used DESC"""
            )
            stats["promos"] = [
                {
                    "code": r[0],
                    "max_uses": r[1],
                    "times_used": r[2],
                    "activations": r[3]
                }
                for r in rows
            ]
        
        return stats
    
    # === Методы для статистики растений ===
    
    async def get_plant_stats(self, plant_code: str = None, days: int = 30) -> Dict:
        """Возвращает статистику растений"""
        stats = {}
        
        if plant_code:
            # Статистика по конкретному растению
            row = await self.fetchone(
                """SELECT 
                    COUNT(*) as total_planted,
                    SUM(CASE WHEN status = 'ready' THEN 1 ELSE 0 END) as ready_count,
                    SUM(CASE WHEN status = 'growing' THEN 1 ELSE 0 END) as growing_count,
                    SUM(CASE WHEN status = 'dead' THEN 1 ELSE 0 END) as dead_count
                   FROM farm_plots 
                   WHERE plant_type = ?""",
                (plant_code,)
            )
            if row:
                stats = {
                    "plant_code": plant_code,
                    "total_planted": row[0] or 0,
                    "ready_count": row[1] or 0,
                    "growing_count": row[2] or 0,
                    "dead_count": row[3] or 0
                }
        else:
            # Общая статистика по всем растениям
            rows = await self.fetchall(
                """SELECT 
                    plant_type,
                    COUNT(*) as total_planted,
                    SUM(CASE WHEN status = 'ready' THEN 1 ELSE 0 END) as ready_count,
                    SUM(CASE WHEN status = 'growing' THEN 1 ELSE 0 END) as growing_count
                   FROM farm_plots 
                   WHERE plant_type IS NOT NULL
                   GROUP BY plant_type
                   ORDER BY total_planted DESC"""
            )
            stats["plants"] = [
                {
                    "plant_code": r[0],
                    "total_planted": r[1] or 0,
                    "ready_count": r[2] or 0,
                    "growing_count": r[3] or 0
                }
                for r in rows
            ]
        
        return stats
    
    async def get_planting_leaderboard(self, plant_code: str = None, limit: int = 10) -> List[Dict]:
        """Возвращает лидерборд по посадкам"""
        if plant_code:
            rows = await self.fetchall(
                """SELECT u.user_id, u.username, COUNT(f.id) as plant_count
                   FROM users u
                   JOIN farm_plots f ON u.user_id = f.user_id
                   WHERE f.plant_type = ?
                   GROUP BY u.user_id
                   ORDER BY plant_count DESC
                   LIMIT ?""",
                (plant_code, limit)
            )
        else:
            rows = await self.fetchall(
                """SELECT u.user_id, u.username, COUNT(f.id) as plant_count
                   FROM users u
                   JOIN farm_plots f ON u.user_id = f.user_id
                   WHERE f.plant_type IS NOT NULL
                   GROUP BY u.user_id
                   ORDER BY plant_count DESC
                   LIMIT ?""",
                (limit,)
            )
        
        return [
            {
                "user_id": r[0],
                "username": r[1],
                "plant_count": r[2]
            }
            for r in rows
        ]
    
    # === Методы для управления растениями ===
    
    async def update_plant_config(self, item_code: str, field: str, value) -> bool:
        """Обновляет конфигурацию растения"""
        import json
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        
        await self.execute(
            f"UPDATE shop_config SET {field} = ? WHERE item_code = ?",
            (value, item_code),
            commit=True
        )
        
        await self.log_admin_action(0, "update_plant", {"item_code": item_code, "field": field})
        return True
    
    async def toggle_plant_active(self, item_code: str) -> bool:
        """Переключает активность растения"""
        await self.execute(
            "UPDATE shop_config SET is_active = NOT is_active WHERE item_code = ?",
            (item_code,),
            commit=True
        )
        
        await self.log_admin_action(0, "toggle_plant", {"item_code": item_code})
        return True
    
    async def delete_plant_config(self, item_code: str, soft_delete: bool = True) -> bool:
        """Удаляет конфигурацию растения"""
        if soft_delete:
            await self.execute(
                "UPDATE shop_config SET is_active = 0 WHERE item_code = ?",
                (item_code,),
                commit=True
            )
        else:
            await self.execute(
                "DELETE FROM shop_config WHERE item_code = ?",
                (item_code,),
                commit=True
            )
        
        await self.log_admin_action(0, "delete_plant", {"item_code": item_code, "soft": soft_delete})
        return True
    
    async def get_inactive_plants(self) -> List[Dict]:
        """Возвращает неактивные растения (корзина)"""
        rows = await self.fetchall(
            "SELECT * FROM shop_config WHERE is_active = 0 AND item_type = 'plant'"
        )
        
        import json
        plants = []
        for r in rows:
            plants.append({
                "id": r[0],
                "item_code": r[1],
                "item_name": r[2],
                "item_type": r[3],
                "price": r[4],
                "sell_price": r[5],
                "grow_time": r[6],
                "emoji": r[7],
                "description": r[8],
                "is_active": bool(r[9]),
                "config_json": json.loads(r[10]) if r[10] else {}
            })
        return plants
    
    
    async def get_user_completed_achievements(self, user_id: int) -> List[Dict]:
        """Получает все выполненные достижения игрока для выбора в профиль"""
        rows = await self.fetchall(
            """SELECT a.achievement_id, a.code, a.name, a.icon, a.category_id,
                      ac.name as category_name, ac.icon as category_icon,
                      pa.completed_at
               FROM player_achievements pa
               JOIN achievements a ON pa.achievement_id = a.achievement_id
               JOIN achievement_categories ac ON a.category_id = ac.category_id
               WHERE pa.user_id = ? AND pa.completed = 1
               ORDER BY pa.completed_at DESC""",
            (user_id,)
        )
        
        return [{
            "id": r[0],
            "code": r[1],
            "name": r[2],
            "icon": r[3],
            "category_id": r[4],
            "category_name": r[5],
            "category_icon": r[6],
            "completed_at": r[7]
        } for r in rows]
    
    async def set_profile_achievements(self, user_id: int, achievement_ids: List[int]) -> bool:
        """Сохраняет выбранные достижения для отображения в профиле (максимум 4)"""
        import json
        
        # Ограничиваем до 4 ачивок
        achievement_ids = achievement_ids[:4]
        
        # Проверяем что все ачивки принадлежат пользователю и выполнены
        if achievement_ids:
            placeholders = ','.join('?' * len(achievement_ids))
            completed = await self.fetchall(
                f"""SELECT achievement_id FROM player_achievements 
                   WHERE user_id = ? AND completed = 1 AND achievement_id IN ({placeholders})""",
                (user_id, *achievement_ids)
            )
            valid_ids = [r[0] for r in completed]
        else:
            valid_ids = []
        
        # Сохраняем в settings
        settings_row = await self.fetchone(
            "SELECT settings FROM users WHERE user_id = ?",
            (user_id,)
        )
        
        settings = {}
        if settings_row and settings_row[0]:
            try:
                settings = json.loads(settings_row[0])
            except (json.JSONDecodeError, TypeError):
                settings = {}
        
        settings['profile_achievements'] = valid_ids
        
        await self.execute(
            "UPDATE users SET settings = ? WHERE user_id = ?",
            (json.dumps(settings), user_id),
            commit=True
        )
        
        return True
    
    async def get_profile_achievements(self, user_id: int) -> List[Dict]:
        """Получает выбранные для профиля достижения"""
        import json
        
        # Получаем настройки
        settings_row = await self.fetchone(
            "SELECT settings FROM users WHERE user_id = ?",
            (user_id,)
        )
        
        if not settings_row or not settings_row[0]:
            return []
        
        try:
            settings = json.loads(settings_row[0])
        except (json.JSONDecodeError, TypeError):
            return []
        
        achievement_ids = settings.get('profile_achievements', [])
        if not achievement_ids:
            return []
        
        # Получаем информацию об ачивках
        placeholders = ','.join('?' * len(achievement_ids))
        rows = await self.fetchall(
            f"""SELECT a.achievement_id, a.code, a.name, a.icon, a.category_id,
                       ac.name as category_name
                FROM achievements a
                JOIN achievement_categories ac ON a.category_id = ac.category_id
                WHERE a.achievement_id IN ({placeholders})""",
            tuple(achievement_ids)
        )
        
        # Сохраняем порядок
        ach_map = {r[0]: {
            "id": r[0],
            "code": r[1],
            "name": r[2],
            "icon": r[3],
            "category_id": r[4],
            "category_name": r[5]
        } for r in rows}
        
        return [ach_map[aid] for aid in achievement_ids if aid in ach_map]
    
    async def get_user_activity_history(self, user_id: int, limit: int = 20) -> List[Dict]:
        """Получает историю действий игрока"""
        # Объединяем данные из разных таблиц логов
        history = []
        
        # Экономические операции
        eco_rows = await self.fetchall(
            """SELECT 'economy' as source, operation_type as action, 
                      currency_type, amount, item_id, source as detail, created_at
               FROM economy_logs 
               WHERE user_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (user_id, limit)
        )
        
        for r in eco_rows:
            action_text = ""
            if r[1] == 'earn':
                action_text = f"💰 Получено: {r[3]:,} {r[2]}"
            elif r[1] == 'spend':
                action_text = f"💸 Потрачено: {r[3]:,} {r[2]}"
            elif r[1] == 'harvest':
                action_text = f"🌾 Собран урожай: +{r[3]:,} {r[2]}"
            elif r[1] == 'plant':
                action_text = f"🌱 Посажено: {r[4]}"
            
            if r[5]:  # detail
                action_text += f" ({r[5]})"
            
            history.append({
                "type": "economy",
                "action": action_text,
                "timestamp": r[6]
            })
        
        # Достижения
        ach_rows = await self.fetchall(
            """SELECT 'achievement' as source, al.action, a.name, a.icon, al.created_at
               FROM achievement_logs al
               JOIN achievements a ON al.achievement_id = a.achievement_id
               WHERE al.user_id = ?
               ORDER BY al.created_at DESC
               LIMIT ?""",
            (user_id, limit)
        )
        
        for r in ach_rows:
            if r[1] == 'completed':
                action_text = f"🏆 Достижение: {r[3]} {r[2]}"
            else:
                action_text = f"📊 Прогресс: {r[3]} {r[2]}"
            
            history.append({
                "type": "achievement",
                "action": action_text,
                "timestamp": r[4]
            })
        
        # Сортируем по времени
        history.sort(key=lambda x: x.get('timestamp', '') or '', reverse=True)
        
        return history[:limit]
    
    async def is_username_taken(self, username: str) -> bool:
        """Проверяет, занят ли ник"""
        if not username:
            return True
        
        # Убираем @ если есть
        username = username.lstrip('@').lower()
        
        row = await self.fetchone(
            "SELECT 1 FROM users WHERE LOWER(username) = ?",
            (username,)
        )
        
        return row is not None
    
    
    
    
    
    
    
    
    
    
    
    async def _generate_daily_quests(self, user_id: int) -> List[Dict]:
        """Генерирует случайные ежедневные квесты для пользователя"""
        from datetime import date
        import random
        
        today = date.today().isoformat()
        
        # Получаем все активные ежедневные квесты
        all_quests = await self.fetchall(
            """SELECT * FROM quests WHERE is_daily = 1 AND is_active = 1 ORDER BY RANDOM()"""
        )
        
        if not all_quests:
            # Если нет квестов в базе, создаём дефолтные
            await self._ensure_default_quests()
            all_quests = await self.fetchall(
                """SELECT * FROM quests WHERE is_daily = 1 AND is_active = 1 ORDER BY RANDOM()"""
            )
        
        # Выбираем 3 случайных квеста
        selected = all_quests[:3] if len(all_quests) >= 3 else all_quests
        
        quests = []
        for row in selected:
            quest_id = row[0]
            
            # Создаём запись прогресса
            await self.execute(
                """INSERT INTO user_quests (user_id, quest_id, assigned_date, progress, completed, claimed)
                   VALUES (?, ?, ?, 0, 0, 0)""",
                (user_id, quest_id, today),
                commit=True
            )
            
            quests.append({
                'quest_id': quest_id,
                'quest_type': row[1],
                'target_item': row[2],
                'target_count': row[4],
                'description': row[5],
                'reward_coins': row[6],
                'reward_gems': row[7],
                'reward_items': json.loads(row[8]) if row[8] else {},
                'progress': 0,
                'completed': False,
                'claimed': False
            })
        
        return quests
    
    async def _ensure_default_quests(self):
        """Создаёт дефолтные квесты если их нет"""
        default_quests = [
            ('harvest', None, 5, 'Соберите 5 урожаев', 100, 0, None, 1, 0),
            ('plant', None, 3, 'Посадите 3 семени', 50, 0, None, 1, 0),
            ('earn', None, 200, 'Заработайте 200 монет', 150, 0, None, 1, 0),
            ('harvest', None, 10, 'Соберите 10 урожаев', 200, 1, None, 1, 0),
            ('plant', None, 5, 'Посадите 5 семян', 100, 0, None, 1, 0),
            ('sell', None, 3, 'Продайте 3 предмета', 80, 0, None, 1, 0),
        ]
        
        for quest in default_quests:
            await self.execute(
                """INSERT OR IGNORE INTO quests 
                   (quest_type, target_item, target_count, description, reward_coins, reward_gems, reward_items_json, is_daily, is_weekly)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                quest,
                commit=True
            )
    
    
    async def _generate_weekly_quests(self, user_id: int, week_start: str) -> List[Dict]:
        """Генерирует еженедельные квесты для пользователя"""
        
        # Получаем все активные еженедельные квесты
        all_quests = await self.fetchall(
            """SELECT * FROM quests WHERE is_weekly = 1 AND is_active = 1 ORDER BY sort_order"""
        )
        
        if not all_quests:
            # Создаём дефолтные еженедельные квесты
            await self._ensure_default_weekly_quests()
            all_quests = await self.fetchall(
                """SELECT * FROM quests WHERE is_weekly = 1 AND is_active = 1 ORDER BY sort_order"""
            )
        
        quests = []
        for row in all_quests:
            quest_id = row[0]
            
            # Создаём запись прогресса
            await self.execute(
                """INSERT INTO user_quests (user_id, quest_id, assigned_date, progress, completed, claimed)
                   VALUES (?, ?, ?, 0, 0, 0)""",
                (user_id, quest_id, week_start),
                commit=True
            )
            
            quests.append({
                'quest_id': quest_id,
                'quest_type': row[1],
                'target_item': row[2],
                'target_count': row[4],
                'description': row[5],
                'reward_coins': row[6],
                'reward_gems': row[7],
                'reward_items': json.loads(row[8]) if row[8] else {},
                'progress': 0,
                'completed': False,
                'claimed': False
            })
        
        return quests
    
    async def _ensure_default_weekly_quests(self):
        """Создаёт дефолтные еженедельные квесты если их нет"""
        default_weekly = [
            ('harvest', None, 50, 'Соберите 50 урожаев за неделю', 500, 5, None, 0, 1),
            ('plant', None, 30, 'Посадите 30 семян за неделю', 300, 3, None, 0, 1),
            ('earn', None, 2000, 'Заработайте 2000 монет за неделю', 800, 8, None, 0, 1),
            ('harvest', None, 100, 'Соберите 100 урожаев за неделю', 1000, 10, '{"fertilizer": 5}', 0, 1),
        ]
        
        for quest in default_weekly:
            await self.execute(
                """INSERT OR IGNORE INTO quests 
                   (quest_type, target_item, target_count, description, reward_coins, reward_gems, reward_items_json, is_daily, is_weekly)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                quest,
                commit=True
            )
    
    
    
    
    
    
    async def add_xp(self, user_id: int, amount: int, source: str = None) -> Dict:
        """Добавляет опыт пользователю
        
        Уровень пересчитывается автоматически триггером БД.
        Формула уровня: level = SQRT(xp / 100) + 1
        
        Args:
            user_id: ID пользователя
            amount: Количество опыта
            source: Источник опыта (harvest, plant, quest, etc.)
        
        Returns:
            Dict с новым XP, уровнем и информацией о повышении
        """
        if amount <= 0:
            return {"success": False, "message": "Количество XP должно быть положительным"}
        
        # Получаем текущие данные
        user = await self.get_user(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        old_xp = user.get('xp', 0)
        old_level = user.get('level', 1)
        
        # Добавляем XP (уровень обновится автоматически через триггер)
        await self.execute(
            "UPDATE users SET xp = xp + ? WHERE user_id = ?",
            (amount, user_id), commit=True
        )
        
        # Получаем обновлённые данные
        updated_user = await self.get_user(user_id)
        new_xp = updated_user.get('xp', 0)
        new_level = updated_user.get('level', 1)
        
        # Проверяем повышение уровня
        level_up = new_level > old_level
        
        # Логируем
        if source:
            await self.log_event('progression', 'INFO', 'xp_gain', user_id,
                                details={"amount": amount, "source": source, 
                                        "old_xp": old_xp, "new_xp": new_xp})
        
        if level_up:
            await self.log_event('progression', 'INFO', 'level_up', user_id,
                                details={"old_level": old_level, "new_level": new_level})
        
        return {
            "success": True,
            "xp_gained": amount,
            "old_xp": old_xp,
            "new_xp": new_xp,
            "old_level": old_level,
            "new_level": new_level,
            "level_up": level_up,
            "levels_gained": new_level - old_level
        }
    
    async def get_xp_for_level(self, level: int) -> int:
        """Вычисляет количество XP, необходимое для достижения уровня
        
        Обратная формула от level = SQRT(xp / 100) + 1
        xp = (level - 1)^2 * 100
        
        Args:
            level: Целевой уровень
        
        Returns:
            Количество XP для достижения уровня
        """
        if level <= 1:
            return 0
        return int((level - 1) ** 2 * 100)
    
    async def get_xp_progress(self, user_id: int) -> Dict:
        """Получает прогресс XP пользователя
        
        Args:
            user_id: ID пользователя
        
        Returns:
            Dict с текущим XP, уровнем и прогрессом до следующего уровня
        """
        user = await self.get_user(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        current_xp = user.get('xp', 0)
        current_level = user.get('level', 1)
        
        # XP для текущего уровня
        xp_for_current = await self.get_xp_for_level(current_level)
        
        # XP для следующего уровня
        xp_for_next = await self.get_xp_for_level(current_level + 1)
        
        # Прогресс до следующего уровня
        xp_needed = xp_for_next - xp_for_current
        xp_progress = current_xp - xp_for_current
        progress_percent = min(100, (xp_progress / xp_needed * 100) if xp_needed > 0 else 100)
        
        return {
            "success": True,
            "current_xp": current_xp,
            "current_level": current_level,
            "xp_for_current_level": xp_for_current,
            "xp_for_next_level": xp_for_next,
            "xp_needed": xp_needed,
            "xp_progress": xp_progress,
            "progress_percent": progress_percent
        }
    
    async def check_prestige_ready(self, user_id: int) -> Dict:
        """Проверяет, готов ли игрок к повышению престижа
        
        Согласно ТЗ v4.0 п.9 - престиж повышается при достижении 50 уровня
        
        Args:
            user_id: ID пользователя
        
        Returns:
            Dict с информацией о готовности к престижу
        """
        user = await self.get_user(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        current_level = user.get('level', 1)
        current_prestige = user.get('prestige_level', 1)
        
        # Требуемый уровень для престижа
        REQUIRED_LEVEL = 50
        
        is_ready = current_level >= REQUIRED_LEVEL
        
        return {
            "success": True,
            "current_level": current_level,
            "current_prestige": current_prestige,
            "required_level": REQUIRED_LEVEL,
            "is_ready": is_ready,
            "levels_needed": max(0, REQUIRED_LEVEL - current_level)
        }
    
    async def do_prestige(self, user_id: int) -> Dict:
        """Выполняет повышение престижа
        
        Сбрасывает уровень и XP, увеличивает престиж на 1.
        Множитель дохода: 1 + prestige * 0.1
        
        Args:
            user_id: ID пользователя
        
        Returns:
            Dict с результатом операции
        """
        # Проверяем готовность
        ready = await self.check_prestige_ready(user_id)
        if not ready.get('success'):
            return ready
        
        if not ready.get('is_ready'):
            return {
                "success": False, 
                "message": f"Недостаточный уровень! Нужно: {ready['required_level']}, у вас: {ready['current_level']}"
            }
        
        user = await self.get_user(user_id)
        old_prestige = user.get('prestige_level', 1)
        new_prestige = old_prestige + 1
        new_multiplier = 1 + new_prestige * 0.1
        
        # Сбрасываем XP и уровень, повышаем престиж
        await self.execute(
            """UPDATE users 
               SET xp = 0, level = 1, 
                   prestige_level = ?, prestige_multiplier = ?
               WHERE user_id = ?""",
            (new_prestige, new_multiplier, user_id), commit=True
        )
        
        # Логируем
        await self.log_event('progression', 'INFO', 'prestige_up', user_id,
                            details={
                                "old_prestige": old_prestige,
                                "new_prestige": new_prestige,
                                "new_multiplier": new_multiplier
                            })
        
        return {
            "success": True,
            "old_prestige": old_prestige,
            "new_prestige": new_prestige,
            "new_multiplier": new_multiplier,
            "message": f"Поздравляем! Престиж повышен до {new_prestige}!"
        }
    
    async def get_prestige_rewards(self, prestige_level: int) -> Dict:
        """Возвращает награды за достижение уровня престижа
        
        Согласно ТЗ v4.0 п.9.2 - особые награды на 5/10/20/50/100 престиже
        
        Args:
            prestige_level: Уровень престижа
        
        Returns:
            Dict с наградами
        """
        # Базовые награды за каждый престиж
        base_reward = {
            "coins": 1000 * prestige_level,
            "gems": 10 * prestige_level
        }
        
        # Особые награды
        special_rewards = {
            5: {"gems": 50, "items": {"fert_gold": 1}, "title": "Опытный фермер"},
            10: {"gems": 100, "items": {"fert_gold": 3}, "title": "Мастер фермер"},
            20: {"gems": 200, "items": {"fert_gold": 5}, "title": "Легенда фермерства"},
            50: {"gems": 500, "items": {"fert_gold": 10}, "title": "Божественный фермер"},
            100: {"gems": 1000, "items": {"fert_gold": 20}, "title": "Фермер-бог"}
        }
        
        if prestige_level in special_rewards:
            return {**base_reward, **special_rewards[prestige_level]}
        
        return base_reward
    
    
    
    
    
    
    async def update_username(self, user_id: int, new_username: str) -> Dict:
        """Обновляет никнейм пользователя
        
        Args:
            user_id: ID пользователя
            new_username: Новый никнейм (без @)
        
        Returns:
            Результат операции
        """
        import re
        
        # Валидация ника
        new_username = new_username.strip().lstrip('@')
        
        if len(new_username) < 3:
            return {"success": False, "message": "Ник слишком короткий (минимум 3 символа)"}
        
        if len(new_username) > 20:
            return {"success": False, "message": "Ник слишком длинный (максимум 20 символов)"}
        
        if not re.match(r'^[a-zA-Z0-9_]+$', new_username):
            return {"success": False, "message": "Ник может содержать только латиницу, цифры и _"}
        
        # Проверяем занятость
        existing = await self.fetchone(
            "SELECT user_id FROM users WHERE LOWER(username) = LOWER(?) AND user_id != ?",
            (new_username, user_id)
        )
        
        if existing:
            return {"success": False, "message": "Этот ник уже занят"}
        
        # Обновляем
        await self.execute(
            "UPDATE users SET username = ? WHERE user_id = ?",
            (new_username, user_id), commit=True
        )
        
        # Логируем
        await self.log_event('user', 'INFO', 'change_username', user_id,
                            details={"new_username": new_username})
        
        return {"success": True, "username": new_username}
    
    
    
    
    async def get_leaderboard(self, category: str = 'balance', limit: int = 10, 
                               user_id: int = None) -> Dict:
        """Получает таблицу лидеров по категории (ТЗ v4.0 п.14)
        
        Категории:
        - balance: По балансу 💰
        - harvest: По собранному урожаю 🚜
        - prestige: По уровню престижа ⬆️
        - activity: По времени в игре 👤
        - streak: По серии бонусов 🔥
        - achievements: По достижениям 🏆
        
        Args:
            category: Категория сортировки
            limit: Количество записей
            user_id: ID пользователя для определения его места
        
        Returns:
            Dict с топ-игроками и местом текущего пользователя
        """
        
        # Выбираем запрос в зависимости от категории
        if category == 'balance':
            query = """SELECT user_id, username, first_name, balance as score, 
                              prestige_level, city_level
                       FROM users WHERE is_banned = 0 ORDER BY balance DESC LIMIT ?"""
            score_field = 'balance'
            
        elif category == 'harvest':
            query = """SELECT user_id, username, first_name, COALESCE(total_harvested, 0) as score,
                              prestige_level, city_level
                       FROM users WHERE is_banned = 0 ORDER BY total_harvested DESC LIMIT ?"""
            score_field = 'total_harvested'
            
        elif category == 'prestige':
            query = """SELECT user_id, username, first_name, 
                              prestige_level * 100 + prestige_multiplier * 10 as score,
                              prestige_level, city_level
                       FROM users WHERE is_banned = 0 
                       ORDER BY prestige_level DESC, prestige_multiplier DESC LIMIT ?"""
            score_field = 'prestige'
            
        elif category == 'activity':
            query = """SELECT user_id, username, first_name, 
                              COALESCE(total_play_time_minutes, 0) as score,
                              prestige_level, city_level
                       FROM users WHERE is_banned = 0 
                       ORDER BY total_play_time_minutes DESC LIMIT ?"""
            score_field = 'activity'
            
        elif category == 'streak':
            query = """SELECT u.user_id, u.username, u.first_name, 
                              COALESCE(dbh.streak_at_claim, 0) as score,
                              u.prestige_level, u.city_level
                       FROM users u
                       LEFT JOIN (
                           SELECT user_id, MAX(streak_at_claim) as streak_at_claim
                           FROM daily_bonus_history
                           WHERE claimed_at >= date('now', '-1 day')
                           GROUP BY user_id
                       ) dbh ON u.user_id = dbh.user_id
                       WHERE u.is_banned = 0
                       ORDER BY score DESC LIMIT ?"""
            score_field = 'streak'
            
        elif category == 'achievements':
            query = """SELECT u.user_id, u.username, u.first_name, 
                              COALESCE(pa.achievement_count, 0) as score,
                              u.prestige_level, u.city_level
                       FROM users u
                       LEFT JOIN (
                           SELECT user_id, COUNT(*) as achievement_count
                           FROM player_achievements
                           WHERE completed = 1
                           GROUP BY user_id
                       ) pa ON u.user_id = pa.user_id
                       WHERE u.is_banned = 0
                       ORDER BY score DESC LIMIT ?"""
            score_field = 'achievements'
        else:
            # По умолчанию - баланс
            query = """SELECT user_id, username, first_name, balance as score,
                              prestige_level, city_level
                       FROM users WHERE is_banned = 0 ORDER BY balance DESC LIMIT ?"""
            score_field = 'balance'
        
        # Получаем топ игроков
        rows = await self.fetchall(query, (limit,))
        
        players = []
        for i, row in enumerate(rows, start=1):
            score_value = row[3] or 0
            
            # Форматируем значение для отображения
            if category == 'activity':
                # Конвертируем минуты в часы/дни
                if score_value >= 1440:  # 24 часа
                    display_value = f"{int(score_value // 1440)} дн {int((score_value % 1440) // 60)} ч"
                else:
                    display_value = f"{int(score_value // 60)} ч {int(score_value % 60)} мин"
            elif category == 'streak':
                display_value = f"{int(score_value)} дней"
            elif category == 'prestige':
                display_value = f"Престиж {row[4] or 0}"
            else:
                display_value = f"{int(score_value):,}"
            
            players.append({
                "rank": i,
                "user_id": row[0],
                "username": row[1] or f"Игрок{row[0]}",
                "first_name": row[2] or "Фермер",
                "score": score_value,
                "display_value": display_value,
                "prestige_level": row[4] or 0,
                "city_level": row[5] or 1,
                "is_current_user": row[0] == user_id
            })
        
        # Определяем место текущего пользователя
        user_rank = None
        user_stats = None
        
        if user_id:
            user_rank, user_stats = await self._get_user_leaderboard_rank(user_id, category, score_field)
        
        return {
            "category": category,
            "players": players,
            "user_rank": user_rank,
            "user_stats": user_stats
        }
    
    async def _get_user_leaderboard_rank(self, user_id: int, category: str, score_field: str) -> tuple:
        """Определяет ранг пользователя в рейтинге
        
        Args:
            user_id: ID пользователя
            category: Категория рейтинга
            score_field: Поле для сортировки
            
        Returns:
            Кортеж (ранг, статистика пользователя)
        """
        # Получаем данные пользователя
        user_row = await self.fetchone(
            """SELECT user_id, username, first_name, balance, 
                      COALESCE(total_harvested, 0), prestige_level, 
                      COALESCE(total_play_time_minutes, 0), city_level
               FROM users WHERE user_id = ? AND is_banned = 0""",
            (user_id,)
        )
        
        if not user_row:
            return None, None
        
        # Определяем значение для сравнения
        if category == 'balance':
            user_score = user_row[3] or 0
            rank_query = """SELECT COUNT(*) + 1 FROM users 
                           WHERE balance > ? AND is_banned = 0"""
            rank_params = (user_score,)
            display_value = f"{int(user_score):,}🪙"
            
        elif category == 'harvest':
            user_score = user_row[4] or 0
            rank_query = """SELECT COUNT(*) + 1 FROM users 
                           WHERE COALESCE(total_harvested, 0) > ? AND is_banned = 0"""
            rank_params = (user_score,)
            display_value = f"{int(user_score)} урожаев"
            
        elif category == 'prestige':
            prestige_level = user_row[5] or 0
            rank_query = """SELECT COUNT(*) + 1 FROM users 
                           WHERE (prestige_level > ?) AND is_banned = 0"""
            rank_params = (prestige_level,)
            display_value = f"Престиж {prestige_level}"
            user_score = prestige_level
            
        elif category == 'activity':
            user_score = user_row[6] or 0
            rank_query = """SELECT COUNT(*) + 1 FROM users 
                           WHERE COALESCE(total_play_time_minutes, 0) > ? AND is_banned = 0"""
            rank_params = (user_score,)
            if user_score >= 1440:
                display_value = f"{int(user_score // 1440)} дн {int((user_score % 1440) // 60)} ч"
            else:
                display_value = f"{int(user_score // 60)} ч {int(user_score % 60)} мин"
            
        elif category == 'streak':
            streak_row = await self.fetchone(
                """SELECT COALESCE(MAX(streak_at_claim), 0) 
                   FROM daily_bonus_history 
                   WHERE user_id = ? AND claimed_at >= date('now', '-1 day')""",
                (user_id,)
            )
            user_score = streak_row[0] if streak_row else 0
            rank_query = """SELECT COUNT(*) + 1 FROM (
                SELECT user_id, COALESCE(MAX(streak_at_claim), 0) as max_streak
                FROM daily_bonus_history
                WHERE claimed_at >= date('now', '-1 day')
                GROUP BY user_id
                HAVING max_streak > ?
            )"""
            rank_params = (user_score,)
            display_value = f"{int(user_score)} дней"
            
        elif category == 'achievements':
            ach_row = await self.fetchone(
                """SELECT COUNT(*) FROM player_achievements 
                   WHERE user_id = ? AND completed = 1""",
                (user_id,)
            )
            user_score = ach_row[0] if ach_row else 0
            rank_query = """SELECT COUNT(*) + 1 FROM (
                SELECT user_id, COUNT(*) as ach_count
                FROM player_achievements
                WHERE completed = 1
                GROUP BY user_id
                HAVING ach_count > ?
            )"""
            rank_params = (user_score,)
            display_value = f"{int(user_score)} достижений"
        else:
            return None, None
    
        # Получаем ранг
        rank_row = await self.fetchone(rank_query, rank_params)
        user_rank = rank_row[0] if rank_row else None
        
        user_stats = {
            "user_id": user_row[0],
            "username": user_row[1] or f"Игрок{user_row[0]}",
            "first_name": user_row[2] or "Фермер",
            "score": user_score,
            "display_value": display_value,
            "prestige_level": user_row[5] or 0,
            "city_level": user_row[7] or 1
        }
        
        return user_rank, user_stats
    
    # ==================== СИСТЕМА УДОБРЕНИЙ (ТЗ v4.0 п.10) ====================
    
    async def get_plot_fertilizer_status(self, user_id: int, plot_number: int) -> Optional[Dict]:
        """Получает статус удобрений на грядке
        
        Args:
            user_id: ID пользователя
            plot_number: Номер грядки
            
        Returns:
            Dict с информацией о удобрении или None
        """
        row = await self.fetchone(
            """SELECT p.plot_number, p.status, p.crop_type, p.fertilized, p.fertilizer_type,
                      p.fertilizer_bonus, p.growth_time_seconds, p.planted_time,
                      sc.item_name, sc.item_icon
               FROM plots p
               LEFT JOIN shop_config sc ON p.fertilizer_type = sc.item_code
               WHERE p.user_id = ? AND p.plot_number = ?""",
            (user_id, plot_number)
        )
        
        if not row:
            return None
        
        return {
            "plot_number": row[0],
            "status": row[1],
            "crop_type": row[2],
            "fertilized": bool(row[3]),
            "fertilizer_type": row[4],
            "fertilizer_bonus": row[5] or 0.0,
            "growth_time_seconds": row[6] or 0,
            "planted_time": row[7],
            "fertilizer_name": row[8],
            "fertilizer_icon": row[9]
        }
    
    async def get_available_fertilizers(self, user_id: int) -> List[Dict]:
        """Получает список доступных удобрений из инвентаря
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Список удобрений с количеством и эффектами
        """
        inventory = await self.get_inventory_full(user_id)
        fertilizers = inventory.get('fertilizers', {})
        
        if not fertilizers:
            return []
        
        available = []
        for code, data in fertilizers.items():
            if data.get('quantity', 0) <= 0:
                continue
            
            available.append({
                "code": code,
                "name": data.get('name', code),
                "icon": data.get('icon', '🧪'),
                "quantity": data.get('quantity', 0),
                "effect_type": data.get('effect_type', 'speed'),
                "effect_value": data.get('effect_value', 0.0),
                "buy_price": data.get('buy_price', 0),
                "description": self._get_fertilizer_description(data.get('effect_type', 'speed'), 
                                                                  data.get('effect_value', 0.0))
            })
        
        return available
    
    def _get_fertilizer_description(self, effect_type: str, effect_value: float) -> str:
        """Возвращает описание эффекта удобрения
        
        Args:
            effect_type: Тип эффекта (speed, instant, bonus)
            effect_value: Значение эффекта
            
        Returns:
            Строка описания
        """
        if effect_type == 'speed':
            return f"Ускоряет рост на {int(effect_value * 100)}%"
        elif effect_type == 'instant':
            return f"Мгновенный рост, +{int(effect_value * 100)}% к доходу"
        elif effect_type == 'bonus':
            return f"+{int(effect_value * 100)}% к доходу"
        else:
            return "Неизвестный эффект"
    
    async def calculate_fertilized_time(self, current_time: int, effect_type: str, 
                                         effect_value: float) -> Dict:
        """Рассчитывает новое время роста после применения удобрения
        
        Args:
            current_time: Текущее оставшееся время в секундах
            effect_type: Тип эффекта
            effect_value: Значение эффекта
            
        Returns:
            Dict с новым временем и сокращением
        """
        if effect_type == 'instant':
            # Мгновенное созревание
            return {
                "new_time": 0,
                "time_reduced": current_time,
                "income_bonus": effect_value,
                "is_instant": True
            }
        elif effect_type == 'speed':
            # Ускорение роста
            time_reduced = int(current_time * effect_value)
            new_time = current_time - time_reduced
            return {
                "new_time": max(0, new_time),
                "time_reduced": time_reduced,
                "income_bonus": 0.0,
                "is_instant": False
            }
        else:
            # Без изменения времени
            return {
                "new_time": current_time,
                "time_reduced": 0,
                "income_bonus": effect_value,
                "is_instant": False
            }
    
    async def apply_fertilizer(self, user_id: int, plot_number: int, 
                                fertilizer_code: str) -> Dict:
        """Применяет удобрение к грядке
        
        Args:
            user_id: ID пользователя
            plot_number: Номер грядки
            fertilizer_code: Код удобрения
            
        Returns:
            Dict с результатом операции
        """
        # Проверяем наличие удобрения в инвентаре
        inventory_item = await self.get_inventory_item(user_id, fertilizer_code)
        if not inventory_item or inventory_item['quantity'] <= 0:
            return {"success": False, "message": "Удобрение не найдено в инвентаре"}
        
        # Проверяем что грядка существует и растёт что-то
        plot = await self.fetchone(
            """SELECT status, crop_type, growth_time_seconds, planted_time, 
                      fertilized, fertilizer_type, fertilizer_bonus
               FROM plots WHERE user_id = ? AND plot_number = ?""",
            (user_id, plot_number)
        )
        
        if not plot:
            return {"success": False, "message": "Грядка не найдена"}
        
        status = plot[0]
        if status != 'growing':
            return {"success": False, "message": "На грядке ничего не растёт"}
        
        if plot[4]:  # fertilized
            return {"success": False, "message": "Удобрение уже применено"}
        
        crop_type = plot[1]
        growth_time = plot[2] or 0
        planted_time = plot[3]
        
        # Получаем информацию об удобрении
        fertilizer = await self.get_shop_item(fertilizer_code)
        if not fertilizer or fertilizer.get('category') != 'fertilizer':
            return {"success": False, "message": "Неверный тип удобрения"}
        
        effect_type = fertilizer.get('effect_type', 'speed')
        effect_value = fertilizer.get('effect_value', 0.0)
        
        # Рассчитываем оставшееся время
        from datetime import datetime
        now = datetime.now()
        planted = datetime.fromisoformat(planted_time) if planted_time else now
        elapsed = (now - planted).total_seconds()
        remaining_time = max(0, growth_time - int(elapsed))
        
        # Рассчитываем новое время
        time_result = await self.calculate_fertilized_time(remaining_time, effect_type, effect_value)
        
        # Обновляем грядку
        new_planted_time = planted_time
        new_growth_time = growth_time
        
        if time_result['is_instant']:
            # Мгновенное созревание - меняем статус на ready
            await self.execute(
                """UPDATE plots 
                   SET fertilized = 1, 
                       fertilizer_type = ?,
                       fertilizer_bonus = ?,
                       status = 'ready'
                   WHERE user_id = ? AND plot_number = ?""",
                (fertilizer_code, time_result['income_bonus'], user_id, plot_number),
                commit=True
            )
            new_planted_time = None
            new_growth_time = 0
        else:
            # Ускорение роста - пересчитываем planted_time
            new_remaining = time_result['new_time']
            new_planted_time = now - timedelta(seconds=(growth_time - new_remaining))
            
            await self.execute(
                """UPDATE plots 
                   SET fertilized = 1, 
                       fertilizer_type = ?,
                       fertilizer_bonus = ?,
                       planted_time = ?,
                       growth_time_seconds = ?
                   WHERE user_id = ? AND plot_number = ?""",
                (fertilizer_code, time_result['income_bonus'], 
                 new_planted_time.isoformat(), growth_time, 
                 user_id, plot_number),
                commit=True
            )
        
        # Удаляем удобрение из инвентаря
        await self.remove_inventory(user_id, fertilizer_code, 1)
        
        # Логируем использование удобрения
        await self.execute(
            """INSERT INTO fertilizer_logs 
               (user_id, plot_number, fertilizer_type, crop_type, 
                original_time, time_reduced, new_time, income_bonus)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, plot_number, fertilizer_code, crop_type,
             growth_time, time_result['time_reduced'], 
             time_result['new_time'], time_result['income_bonus']),
            commit=True
        )
        
        # Логируем экономику
        await self.log_economy(
            user_id, 'spend', 'fertilizer', 1, None,
            'fertilizer_apply', fertilizer_code,
            f"Применение удобрения {fertilizer.get('name')} к грядке #{plot_number}"
        )
        
        return {
            "success": True,
            "fertilizer_name": fertilizer.get('name'),
            "fertilizer_icon": fertilizer.get('icon'),
            "plot_number": plot_number,
            "crop_type": crop_type,
            "is_instant": time_result['is_instant'],
            "original_time": remaining_time,
            "time_reduced": time_result['time_reduced'],
            "new_time": time_result['new_time'],
            "income_bonus": time_result['income_bonus'],
            "message": "Удобрение применено!" + 
                      (" Урожай созрел мгновенно!" if time_result['is_instant'] else "")
        }
    
    async def get_fertilizer_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Получает историю использования удобрений
        
        Args:
            user_id: ID пользователя
            limit: Количество записей
            
        Returns:
            Список записей использования
        """
        rows = await self.fetchall(
            """SELECT fl.*, sc.item_name, sc.item_icon
               FROM fertilizer_logs fl
               JOIN shop_config sc ON fl.fertilizer_type = sc.item_code
               WHERE fl.user_id = ?
               ORDER BY fl.applied_at DESC
               LIMIT ?""",
            (user_id, limit)
        )
        
        return [{
            "log_id": row[0],
            "plot_number": row[2],
            "fertilizer_type": row[3],
            "fertilizer_name": row[10],
            "fertilizer_icon": row[11],
            "crop_type": row[4],
            "original_time": row[5],
            "time_reduced": row[6],
            "new_time": row[7],
            "income_bonus": row[8],
            "applied_at": row[9]
        } for row in rows]
    
    async def check_auto_fertilizer_setting(self, user_id: int) -> bool:
        """Проверяет включена ли опция авто-удобрения
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если авто-удобрение включено
        """
        user = await self.get_user(user_id)
        if not user or not user.get('settings'):
            return False
        
        return user['settings'].get('auto_fertilize', False)
    
    async def toggle_auto_fertilizer(self, user_id: int, enabled: bool) -> bool:
        """Включает/выключает авто-удобрение
        
        Args:
            user_id: ID пользователя
            enabled: Включить или выключить
            
        Returns:
            True если успешно
        """
        user = await self.get_user(user_id)
        settings = user.get('settings', {}) if user else {}
        settings['auto_fertilize'] = enabled
        
        return await self.update_user_settings(user_id, settings)
    
    # ==================== СИСТЕМА ФЕРМЕРОВ (ТЗ v4.0 п.11) ====================
    
    async def get_farmer_types(self) -> List[Dict]:
        """Получает список доступных типов фермеров
        
        Returns:
            Список типов фермеров
        """
        rows = await self.fetchall(
            """SELECT type_code, name, icon, description, duration_days,
                      price_coins, price_gems, bonus_percent, uses_fertilizer,
                      salary_per_hour, work_interval_seconds
               FROM farmer_types
               WHERE is_active = 1
               ORDER BY sort_order"""
        )
        
        return [{
            "type_code": row[0],
            "name": row[1],
            "icon": row[2],
            "description": row[3],
            "duration_days": row[4],
            "price_coins": row[5],
            "price_gems": row[6],
            "bonus_percent": row[7],
            "uses_fertilizer": bool(row[8]),
            "salary_per_hour": row[9],
            "work_interval_seconds": row[10]
        } for row in rows]
    
    async def get_user_farmer(self, user_id: int) -> Optional[Dict]:
        """Получает информацию о фермере пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Информация о фермере или None
        """
        row = await self.fetchone(
            """SELECT f.farmer_id, f.farmer_type, f.status, f.bonus_percent,
                      f.uses_fertilizer, f.hired_at, f.expires_at, f.last_work,
                      f.total_planted, f.total_harvested, f.total_earned,
                      f.total_salary_paid, ft.name, ft.icon, ft.description,
                      ft.salary_per_hour, ft.work_interval_seconds
               FROM farmers f
               JOIN farmer_types ft ON f.farmer_type = ft.type_code
               WHERE f.user_id = ? AND f.status != 'expired'""",
            (user_id,)
        )
        
        if not row:
            return None
        
        # Проверяем не истёк ли срок
        expires_at = row[6]
        if expires_at:
            from datetime import datetime
            try:
                expires = datetime.fromisoformat(expires_at)
                if datetime.now() > expires:
                    # Помечаем как истёкшего
                    await self.execute(
                        "UPDATE farmers SET status = 'expired' WHERE farmer_id = ?",
                        (row[0],), commit=True
                    )
                    return None
            except:
                pass
        
        # Получаем настройки фермера
        config = await self.get_farmer_config(row[0])
        
        return {
            "farmer_id": row[0],
            "farmer_type": row[1],
            "status": row[2],
            "bonus_percent": row[3],
            "uses_fertilizer": bool(row[4]),
            "hired_at": row[5],
            "expires_at": row[6],
            "last_work": row[7],
            "total_planted": row[8],
            "total_harvested": row[9],
            "total_earned": row[10],
            "total_salary_paid": row[11],
            "type_name": row[12],
            "type_icon": row[13],
            "type_description": row[14],
            "salary_per_hour": row[15],
            "work_interval_seconds": row[16],
            "config": config
        }
    
    async def get_farmer_config(self, farmer_id: int) -> Dict:
        """Получает настройки фермера
        
        Args:
            farmer_id: ID фермера
            
        Returns:
            Настройки фермера
        """
        row = await self.fetchone(
            """SELECT preferred_crop, harvest_mode, use_fertilizer,
                      auto_harvest, auto_plant
               FROM farmer_config WHERE farmer_id = ?""",
            (farmer_id,)
        )
        
        if row:
            return {
                "preferred_crop": row[0],
                "harvest_mode": row[1],
                "use_fertilizer": bool(row[2]),
                "auto_harvest": bool(row[3]),
                "auto_plant": bool(row[4])
            }
        
        # Настройки по умолчанию
        return {
            "preferred_crop": None,
            "harvest_mode": "sell",
            "use_fertilizer": False,
            "auto_harvest": True,
            "auto_plant": True
        }
    
    async def hire_farmer(self, user_id: int, farmer_type: str) -> Dict:
        """Нанимает фермера
        
        Args:
            user_id: ID пользователя
            farmer_type: Тип фермера
            
        Returns:
            Результат операции
        """
        # Проверяем есть ли уже активный фермер
        existing = await self.get_user_farmer(user_id)
        if existing:
            return {"success": False, "message": "У вас уже есть активный фермер!"}
        
        # Получаем информацию о типе фермера
        farmer_type_info = await self.fetchone(
            """SELECT name, icon, duration_days, price_coins, price_gems,
                      bonus_percent, uses_fertilizer, salary_per_hour
               FROM farmer_types WHERE type_code = ? AND is_active = 1""",
            (farmer_type,)
        )
        
        if not farmer_type_info:
            return {"success": False, "message": "Тип фермера не найден!"}
        
        name, icon, duration_days, price_coins, price_gems, bonus, uses_fert, salary = farmer_type_info
        
        # Проверяем баланс
        user = await self.get_user(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден!"}
        
        if user.get('balance', 0) < price_coins:
            return {"success": False, "message": f"Недостаточно монет! Нужно {price_coins:,}🪙"}
        
        if user.get('gems', 0) < price_gems:
            return {"success": False, "message": f"Недостаточно кристаллов! Нужно {price_gems}💎"}
        
        # Рассчитываем дату истечения
        from datetime import datetime, timedelta
        expires_at = None
        if duration_days:
            expires_at = (datetime.now() + timedelta(days=duration_days)).isoformat()
        
        async with self.lock:
            db = await self.connect()
            await db.execute("BEGIN")
            try:
                # Списываем деньги
                if price_coins > 0:
                    await db.execute(
                        "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                        (price_coins, user_id)
                    )
                if price_gems > 0:
                    await db.execute(
                        "UPDATE users SET gems = gems - ? WHERE user_id = ?",
                        (price_gems, user_id)
                    )
                
                # Создаём фермера
                cursor = await db.execute(
                    """INSERT INTO farmers 
                       (user_id, farmer_type, bonus_percent, uses_fertilizer, expires_at, salary_per_hour)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (user_id, farmer_type, bonus, uses_fert, expires_at, salary)
                )
                farmer_id = cursor.lastrowid
                
                # Создаём настройки по умолчанию
                await db.execute(
                    """INSERT INTO farmer_config 
                       (farmer_id, preferred_crop, harvest_mode, use_fertilizer, auto_harvest, auto_plant)
                       VALUES (?, NULL, 'sell', ?, 1, 1)""",
                    (farmer_id, 1 if uses_fert else 0)
                )
                
                # Логируем найм
                await db.execute(
                    """INSERT INTO farmer_logs (farmer_id, action, amount)
                       VALUES (?, 'hire', 1)""",
                    (farmer_id,)
                )
                
                await db.commit()
                
                return {
                    "success": True,
                    "farmer_id": farmer_id,
                    "name": name,
                    "icon": icon,
                    "duration_days": duration_days,
                    "expires_at": expires_at,
                    "message": f"Фермер {icon} {name} нанят!"
                }
            except Exception as e:
                await db.rollback()
                raise
    
    async def update_farmer_config(self, farmer_id: int, **kwargs) -> bool:
        """Обновляет настройки фермера
        
        Args:
            farmer_id: ID фермера
            **kwargs: Поля для обновления
            
        Returns:
            True если успешно
        """
        allowed_fields = ['preferred_crop', 'harvest_mode', 'use_fertilizer', 
                         'auto_harvest', 'auto_plant']
        
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return False
        
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [farmer_id]
        
        await self.execute(
            f"UPDATE farmer_config SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE farmer_id = ?",
            tuple(values), commit=True
        )
        return True
    
    async def fire_farmer(self, farmer_id: int) -> bool:
        """Увольняет фермера
        
        Args:
            farmer_id: ID фермера
            
        Returns:
            True если успешно
        """
        await self.execute(
            "UPDATE farmers SET status = 'expired' WHERE farmer_id = ?",
            (farmer_id,), commit=True
        )
        return True
    
    async def pause_farmer(self, farmer_id: int) -> bool:
        """Приостанавливает работу фермера
        
        Args:
            farmer_id: ID фермера
            
        Returns:
            True если успешно
        """
        await self.execute(
            "UPDATE farmers SET status = 'paused' WHERE farmer_id = ?",
            (farmer_id,), commit=True
        )
        return True
    
    async def resume_farmer(self, farmer_id: int) -> bool:
        """Возобновляет работу фермера
        
        Args:
            farmer_id: ID фермера
            
        Returns:
            True если успешно
        """
        await self.execute(
            "UPDATE farmers SET status = 'active' WHERE farmer_id = ?",
            (farmer_id,), commit=True
        )
        return True
    
    async def get_all_active_farmers(self) -> List[Dict]:
        """Получает всех активных фермеров (для фоновой задачи)
        
        Returns:
            Список активных фермеров
        """
        rows = await self.fetchall(
            """SELECT f.farmer_id, f.user_id, f.farmer_type, f.bonus_percent,
                      f.uses_fertilizer, f.last_work, f.total_planted, f.total_harvested,
                      f.total_earned, f.total_salary_paid, ft.work_interval_seconds,
                      ft.salary_per_hour
               FROM farmers f
               JOIN farmer_types ft ON f.farmer_type = ft.type_code
               WHERE f.status = 'active'"""
        )
        
        return [{
            "farmer_id": row[0],
            "user_id": row[1],
            "farmer_type": row[2],
            "bonus_percent": row[3],
            "uses_fertilizer": bool(row[4]),
            "last_work": row[5],
            "total_planted": row[6],
            "total_harvested": row[7],
            "total_earned": row[8],
            "total_salary_paid": row[9],
            "work_interval_seconds": row[10],
            "salary_per_hour": row[11]
        } for row in rows]
    
    async def farmer_work(self, user_id: int) -> Dict:
        """Выполняет работу фермера для пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Результат работы фермера
        """
        farmer = await self.get_user_farmer(user_id)
        if not farmer or farmer['status'] != 'active':
            return {"success": False, "skipped": True, "message": "Нет активного фермера"}
        
        # Проверяем интервал работы
        from datetime import datetime, timedelta
        last_work = farmer.get('last_work')
        interval = farmer.get('work_interval_seconds', 300)
        
        if last_work:
            try:
                last_work_time = datetime.fromisoformat(last_work)
                if (datetime.now() - last_work_time).total_seconds() < interval:
                    return {"success": False, "skipped": True, "message": "Рано для работы"}
            except:
                pass
        
        config = farmer.get('config', {})
        
        # Получаем улучшения фермера
        speed_level = await self.get_upgrade_level(user_id, 'farmer_speed')
        income_level = await self.get_upgrade_level(user_id, 'farmer_income')
        capacity_level = await self.get_upgrade_level(user_id, 'farmer_capacity')
        
        # Модификаторы от улучшений
        speed_multiplier = 1.0 + (speed_level * 0.25)
        income_multiplier = 1.0 + (income_level * 0.10) + (farmer.get('bonus_percent', 0) / 100)
        capacity_multiplier = 1.0 + (capacity_level * 0.50)
        
        # Получаем грядки пользователя
        plots = await self.get_plots(user_id)
        
        planted = 0
        harvested = 0
        earned = 0
        
        # Собираем готовый урожай
        if config.get('auto_harvest', True):
            ready_plots = [p for p in plots if p.get('status') == 'ready']
            max_harvest = int(len(ready_plots) * capacity_multiplier)
            
            for plot in ready_plots[:max_harvest]:
                result = await self.harvest_plots(user_id)
                if result.get('success') and result.get('total', 0) > 0:
                    harvested += 1
                    earned += int(result['total'] * income_multiplier)
        
        # Сажаем новые культуры
        if config.get('auto_plant', True):
            empty_plots = [p for p in plots if p.get('status') == 'empty']
            max_plant = int(len(empty_plots) * capacity_multiplier)
            
            # Определяем что сажать
            preferred_crop = config.get('preferred_crop')
            
            for plot in empty_plots[:max_plant]:
                # Выбираем семена
                if preferred_crop:
                    crop_code = preferred_crop
                else:
                    # Берём случайное доступное семя
                    seeds = await self.get_shop_items("seed")
                    if seeds:
                        crop_code = seeds[0]['item_code']
                    else:
                        continue
                
                # Получаем информацию о семенах
                crop_data = await self.get_shop_item(crop_code)
                if not crop_data:
                    continue
                
                # Проверяем баланс
                user = await self.get_user(user_id)
                if not user or user.get('balance', 0) < crop_data.get('buy_price', 0):
                    continue
                
                # Сажаем
                try:
                    await self.update_balance(user_id, -crop_data['buy_price'])
                    await self.plant_crop(user_id, plot['number'], crop_code, 
                                         crop_data.get('growth_time', 120))
                    planted += 1
                    
                    # Применяем удобрение если настроено
                    if config.get('use_fertilizer', False) and farmer.get('uses_fertilizer'):
                        fertilizers = await self.get_available_fertilizers(user_id)
                        if fertilizers:
                            await self.apply_fertilizer(user_id, plot['number'], 
                                                       fertilizers[0]['code'])
                except:
                    continue
        
        # Рассчитываем зарплату
        salary = farmer.get('salary_per_hour', 0)
        
        # Обновляем статистику фермера
        async with self.lock:
            db = await self.connect()
            await db.execute("BEGIN")
            try:
                await db.execute(
                    """UPDATE farmers 
                       SET last_work = CURRENT_TIMESTAMP,
                           total_planted = total_planted + ?,
                           total_harvested = total_harvested + ?,
                           total_earned = total_earned + ?,
                           total_salary_paid = total_salary_paid + ?
                       WHERE farmer_id = ?""",
                    (planted, harvested, earned, salary, farmer['farmer_id'])
                )
                
                # Логируем работу
                if planted > 0:
                    await db.execute(
                        """INSERT INTO farmer_logs (farmer_id, action, amount)
                           VALUES (?, 'plant', ?)""",
                        (farmer['farmer_id'], planted)
                    )
                if harvested > 0:
                    await db.execute(
                        """INSERT INTO farmer_logs (farmer_id, action, amount, earned)
                           VALUES (?, 'harvest', ?, ?)""",
                        (farmer['farmer_id'], harvested, earned)
                    )
                
                await db.commit()
            except Exception as e:
                await db.rollback()
                raise
        
        return {
            "success": True,
            "planted": planted,
            "harvested": harvested,
            "earned": earned,
            "salary": salary
        }
    
    async def get_farmer_stats(self, farmer_id: int) -> Dict:
        """Получает статистику фермера
        
        Args:
            farmer_id: ID фермера
            
        Returns:
            Статистика работы
        """
        row = await self.fetchone(
            """SELECT total_planted, total_harvested, total_earned, total_salary_paid
               FROM farmers WHERE farmer_id = ?""",
            (farmer_id,)
        )
        
        if not row:
            return {}
        
        # Получаем логи за последний час
        logs = await self.fetchall(
            """SELECT action, amount, earned, created_at
               FROM farmer_logs
               WHERE farmer_id = ? AND created_at > datetime('now', '-1 hour')
               ORDER BY created_at DESC""",
            (farmer_id,)
        )
        
        return {
            "total_planted": row[0],
            "total_harvested": row[1],
            "total_earned": row[2],
            "total_salary_paid": row[3],
            "net_profit": row[2] - row[3],
            "recent_logs": [{
                "action": log[0],
                "amount": log[1],
                "earned": log[2],
                "time": log[3]
            } for log in logs]
        }
    
    # ==================== ЕЖЕДНЕВНЫЙ БОНУС (ТЗ v4.0 п.13) ====================
    
    async def get_daily_bonus_config(self) -> List[Dict]:
        """Получает настройки рулетки ежедневного бонуса
        
        Returns:
            Список настроек наград
        """
        rows = await self.fetchall(
            """SELECT reward_type, name, icon, min_amount, max_amount, 
                      base_chance, item_code
               FROM daily_bonus_config
               WHERE is_active = 1
               ORDER BY sort_order"""
        )
        
        return [{
            "type": row[0],
            "name": row[1],
            "icon": row[2],
            "min": row[3],
            "max": row[4],
            "chance": row[5],
            "item_code": row[6]
        } for row in rows]
    
    async def calculate_bonus_rewards(self, streak: int = 0) -> List[Dict]:
        """Рассчитывает награды для рулетки бонуса с учётом стрика
        
        Args:
            streak: Текущая серия дней
            
        Returns:
            Список наград с рассчитанными шансами и количеством
        """
        config = await self.get_daily_bonus_config()
        
        # Множители от стрика (по ТЗ)
        if streak >= 8:
            streak_multiplier = 2.0  # +100%
            jackpot_multiplier = 2.0
        elif streak >= 4:
            streak_multiplier = 1.5  # +50%
            jackpot_multiplier = 1.0
        else:
            streak_multiplier = 1.0
            jackpot_multiplier = 1.0
        
        rewards = []
        for cfg in config:
            reward_type = cfg['type']
            
            # Рассчитываем шанс
            chance = cfg['chance']
            if reward_type == 'jackpot':
                chance *= jackpot_multiplier
            
            # Рассчитываем количество
            min_amount = int(cfg['min'] * streak_multiplier)
            max_amount = int(cfg['max'] * streak_multiplier)
            
            rewards.append({
                "type": reward_type,
                "name": cfg['name'],
                "icon": cfg['icon'],
                "min": min_amount,
                "max": max_amount,
                "chance": min(1.0, chance),
                "item_code": cfg['item_code']
            })
        
        return rewards
    
    async def roll_daily_bonus(self, user_id: int) -> Dict:
        """Проводит рулетку ежедневного бонуса
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Результат рулетки с выигранными наградами
        """
        # Получаем текущий стрик
        streak_data = await self.get_daily_bonus_streak(user_id)
        streak = streak_data.get('streak', 0) + 1  # +1 за сегодня
        
        # Получаем настройки с учётом стрика
        rewards_config = await self.calculate_bonus_rewards(streak)
        
        import random
        
        # Проводим рулетку (3 броска)
        won_rewards = []
        
        for _ in range(3):
            roll = random.random()
            cumulative = 0.0
            
            for reward in rewards_config:
                cumulative += reward['chance']
                if roll <= cumulative:
                    # Определяем количество
                    amount = random.randint(reward['min'], reward['max'])
                    
                    won_rewards.append({
                        "type": reward['type'],
                        "name": reward['name'],
                        "icon": reward['icon'],
                        "amount": amount,
                        "item_code": reward.get('item_code')
                    })
                    break
            else:
                # Если ничего не выпало, даём минимум монет
                won_rewards.append({
                    "type": "coins",
                    "name": "Монеты",
                    "icon": "💰",
                    "amount": 50
                })
        
        # Объединяем одинаковые награды
        combined = {}
        for r in won_rewards:
            key = r['type']
            if key in combined:
                combined[key]['amount'] += r['amount']
            else:
                combined[key] = r.copy()
        
        return {
            "streak": streak,
            "rewards": list(combined.values())
        }
    
    async def get_daily_bonus_streak(self, user_id: int) -> Dict:
        """Получает информацию о серии ежедневных бонусов
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Информация о серии
        """
        # Получаем последнюю запись
        row = await self.fetchone(
            """SELECT streak, claimed_at, 
                       CASE 
                           WHEN date(claimed_at) = date('now') THEN 'today'
                           WHEN date(claimed_at) = date('now', '-1 day') THEN 'yesterday'
                           ELSE 'older'
                       END as last_claim_status
               FROM daily_bonus_history
               WHERE user_id = ?
               ORDER BY claimed_at DESC
               LIMIT 1""",
            (user_id,)
        )
        
        if not row:
            return {"streak": 0, "last_claim": None, "can_claim": True}
        
        streak, last_claim, status = row
        
        # Проверяем можно ли забрать
        can_claim = status != 'today'
        
        # Если пропустили день - сбрасываем стрик
        if status == 'older':
            streak = 0
        
        return {
            "streak": streak,
            "last_claim": last_claim,
            "can_claim": can_claim,
            "status": status
        }
    
    
    async def _add_inventory_internal(self, db, user_id: int, item_code: str, amount: int):
        """Внутренний метод для добавления предмета в инвентарь (внутри транзакции)
        """
        # Проверяем существование записи
        existing = await db.execute(
            "SELECT quantity FROM inventory WHERE user_id = ? AND item_code = ?",
            (user_id, item_code)
        )
        row = await existing.fetchone()
        
        if row:
            await db.execute(
                "UPDATE inventory SET quantity = quantity + ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND item_code = ?",
                (amount, user_id, item_code)
            )
        else:
            await db.execute(
                "INSERT INTO inventory (user_id, item_code, quantity) VALUES (?, ?, ?)",
                (user_id, item_code, amount)
            )
    
    # ==================== УЛУЧШЕНИЯ (ТЗ v4.0 п.12) ====================
    
    async def get_upgrades(self, category: str = None, required_prestige: int = None) -> List[Dict]:
        """Получает список доступных улучшений
        
        Args:
            category: Категория улучшений
            required_prestige: Требуемый престиж
            
        Returns:
            Список улучшений
        """
        query = """SELECT upgrade_code, name, icon, description, category,
                          max_level, base_price, price_multiplier, effect_type,
                          effect_value, effect_unit, required_prestige
                   FROM upgrades WHERE is_active = 1"""
        params = []
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        if required_prestige is not None:
            query += " AND required_prestige <= ?"
            params.append(required_prestige)
        
        query += " ORDER BY category, sort_order"
        
        rows = await self.fetchall(query, tuple(params) if params else None)
        
        return [{
            "upgrade_code": row[0],
            "name": row[1],
            "icon": row[2],
            "description": row[3],
            "category": row[4],
            "max_level": row[5],
            "base_price": row[6],
            "price_multiplier": row[7],
            "effect_type": row[8],
            "effect_value": row[9],
            "effect_unit": row[10],
            "required_prestige": row[11]
        } for row in rows]
    
    async def get_upgrade_level(self, user_id: int, upgrade_code: str) -> int:
        """Получает текущий уровень улучшения пользователя
        
        Args:
            user_id: ID пользователя
            upgrade_code: Код улучшения
            
        Returns:
            Текущий уровень (0 если не куплено)
        """
        row = await self.fetchone(
            "SELECT current_level FROM user_upgrades WHERE user_id = ? AND upgrade_code = ?",
            (user_id, upgrade_code)
        )
        return row[0] if row else 0
    
    async def buy_upgrade(self, user_id: int, upgrade_code: str) -> Dict:
        """Покупает улучшение
        
        Args:
            user_id: ID пользователя
            upgrade_code: Код улучшения
            
        Returns:
            Результат операции
        """
        # Получаем информацию об улучшении
        upgrade = await self.fetchone(
            """SELECT name, icon, max_level, base_price, price_multiplier,
                      effect_type, effect_value, effect_unit, required_prestige
               FROM upgrades WHERE upgrade_code = ? AND is_active = 1""",
            (upgrade_code,)
        )
        
        if not upgrade:
            return {"success": False, "message": "Улучшение не найдено!"}
        
        name, icon, max_level, base_price, price_mult, effect_type, effect_val, effect_unit, req_prestige = upgrade
        
        # Проверяем престиж
        user = await self.get_user(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден!"}
        
        if user.get('prestige_level', 1) < req_prestige:
            return {"success": False, "message": f"Требуется престиж {req_prestige}!"}
        
        # Получаем текущий уровень
        current_level = await self.get_upgrade_level(user_id, upgrade_code)
        
        if current_level >= max_level:
            return {"success": False, "message": "Улучшение уже на максимальном уровне!"}
        
        # Рассчитываем цену
        new_level = current_level + 1
        price = int(base_price * (price_mult ** current_level))
        
        # Проверяем баланс
        if user.get('balance', 0) < price:
            return {"success": False, "message": f"Недостаточно монет! Нужно {price:,}🪙"}
        
        # Покупаем улучшение
        async with self.lock:
            db = await self.connect()
            await db.execute("BEGIN")
            try:
                # Списываем деньги
                await db.execute(
                    "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                    (price, user_id)
                )
                
                # Обновляем или создаём запись об улучшении
                if current_level == 0:
                    await db.execute(
                        """INSERT INTO user_upgrades 
                           (user_id, upgrade_code, current_level, total_spent)
                           VALUES (?, ?, 1, ?)""",
                        (user_id, upgrade_code, price)
                    )
                else:
                    await db.execute(
                        """UPDATE user_upgrades 
                           SET current_level = current_level + 1,
                               total_spent = total_spent + ?,
                               updated_at = CURRENT_TIMESTAMP
                           WHERE user_id = ? AND upgrade_code = ?""",
                        (price, user_id, upgrade_code)
                    )
                
                await db.commit()
                
                return {
                    "success": True,
                    "name": name,
                    "icon": icon,
                    "new_level": new_level,
                    "max_level": max_level,
                    "price": price,
                    "effect_type": effect_type,
                    "effect_value": effect_val * new_level,
                    "effect_unit": effect_unit,
                    "message": f"Улучшение '{name}' повышено до уровня {new_level}!"
                }
            except Exception as e:
                await db.rollback()
                raise
    
    # ==================== ПРОМОКОДЫ (ТЗ v4.0 п.14) ====================
    
    async def get_active_promocodes(self, user_id: int = None) -> List[Dict]:
        """Получает список активных промокодов
        
        Args:
            user_id: ID пользователя (для проверки уже использованных)
            
        Returns:
            Список доступных промокодов
        """
        from datetime import datetime
        now = datetime.now().isoformat()
        
        # Получаем все активные промокоды
        rows = await self.fetchall(
            """SELECT id, code, type, reward_coins, reward_gems, reward_items,
                      valid_until, max_activations, times_used, is_active
               FROM promocodes
               WHERE is_active = 1 
                 AND (valid_until IS NULL OR valid_until > ?)
                 AND (max_activations = 0 OR times_used < max_activations)
               ORDER BY type, created_at DESC""",
            (now,)
        )
        
        promos = []
        for row in rows:
            promo_id = row[0]
            code = row[1]
            promo_type = row[2]
            
            # Проверяем использовал ли пользователь этот промокод
            already_used = False
            if user_id:
                used = await self.fetchone(
                    "SELECT 1 FROM promo_activations WHERE promo_id = ? AND user_id = ?",
                    (promo_id, user_id)
                )
                already_used = used is not None
            
            # Рассчитываем оставшиеся активации
            max_act = row[7] or 0
            used = row[8] or 0
            remaining = None if max_act == 0 else max_act - used
            
            # Рассчитываем оставшиеся дни
            days_left = None
            if row[6]:  # valid_until
                try:
                    expires = datetime.fromisoformat(row[6])
                    days_left = (expires - datetime.now()).days + 1
                except:
                    pass
            
            promos.append({
                "id": promo_id,
                "code": code,
                "type": promo_type,
                "reward_coins": row[3] or 0,
                "reward_gems": row[4] or 0,
                "reward_items": row[5],
                "valid_until": row[6],
                "days_left": days_left,
                "max_activations": max_act,
                "times_used": used,
                "remaining_activations": remaining,
                "already_used": already_used
            })
        
        return promos
    
    async def activate_promocode(self, user_id: int, code: str) -> Dict:
        """Активирует промокод
        
        Args:
            user_id: ID пользователя
            code: Код промокода
            
        Returns:
            Результат активации с наградами
        """
        code = code.upper().strip()
        
        # Ищем промокод
        promo = await self.fetchone(
            """SELECT id, code, type, reward_coins, reward_gems, reward_items,
                      valid_until, max_activations, times_used, is_active
               FROM promocodes WHERE code = ?""",
            (code,)
        )
        
        if not promo:
            return {
                "success": False,
                "error": "not_found",
                "message": "Промокод не найден!"
            }
        
        promo_id = promo[0]
        promo_type = promo[2]
        is_active = promo[9]
        
        # Проверяем активность
        if not is_active:
            return {
                "success": False,
                "error": "inactive",
                "message": "Промокод временно недоступен!"
            }
        
        # Проверяем срок действия
        from datetime import datetime
        valid_until = promo[6]
        if valid_until:
            try:
                expires = datetime.fromisoformat(valid_until)
                if datetime.now() > expires:
                    return {
                        "success": False,
                        "error": "expired",
                        "message": f"Срок действия промокода истёк!"
                    }
            except:
                pass
        
        # Проверяем лимит активаций
        max_act = promo[7] or 0
        times_used = promo[8] or 0
        if max_act > 0 and times_used >= max_act:
            return {
                "success": False,
                "error": "limit_reached",
                "message": "Лимит активаций исчерпан!"
            }
        
        # Проверяем использовал ли пользователь уже
        already_used = await self.fetchone(
            "SELECT 1 FROM promo_activations WHERE promo_id = ? AND user_id = ?",
            (promo_id, user_id)
        )
        
        if already_used:
            return {
                "success": False,
                "error": "already_used",
                "message": "Ты уже использовал этот промокод!"
            }
        
        # Проверяем тип промокода (одноразовые только для новых)
        if promo_type == 'starter':
            user = await self.get_user(user_id)
            if user and user.get('total_harvested', 0) > 100:
                return {
                    "success": False,
                    "error": "not_for_you",
                    "message": "Этот промокод только для новых игроков!"
                }
        
        # Активируем промокод
        reward_coins = promo[3] or 0
        reward_gems = promo[4] or 0
        reward_items = promo[5]
        
        async with self.lock:
            db = await self.connect()
            await db.execute("BEGIN")
            try:
                # Записываем активацию
                await db.execute(
                    """INSERT INTO promo_activations (promo_id, user_id)
                       VALUES (?, ?)""",
                    (promo_id, user_id)
                )
                
                # Обновляем счётчик использований (триггер сделает это, но на всякий случай)
                await db.execute(
                    "UPDATE promocodes SET times_used = times_used + 1 WHERE id = ?",
                    (promo_id,)
                )
                
                # Выдаём награды
                if reward_coins > 0:
                    await db.execute(
                        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                        (reward_coins, user_id)
                    )
                
                if reward_gems > 0:
                    await db.execute(
                        "UPDATE users SET gems = gems + ? WHERE user_id = ?",
                        (reward_gems, user_id)
                    )
                
                # Выдаём предметы если есть
                items_given = []
                if reward_items:
                    try:
                        import json
                        items = json.loads(reward_items)
                        for item in items:
                            item_code = item.get('code')
                            amount = item.get('amount', 1)
                            if item_code:
                                await self.add_inventory(user_id, item_code, amount)
                                items_given.append({
                                    'code': item_code,
                                    'amount': amount
                                })
                    except:
                        pass
                
                # Логируем
                await db.execute(
                    """INSERT INTO promo_logs (promo_code, user_id, action, details)
                       VALUES (?, ?, 'activated', ?)""",
                    (code, user_id, f"Coins: {reward_coins}, Gems: {reward_gems}")
                )
                
                await db.commit()
                
                return {
                    "success": True,
                    "code": code,
                    "message": "Промокод активирован!",
                    "rewards": {
                        "coins": reward_coins,
                        "gems": reward_gems,
                        "items": items_given
                    }
                }
            except Exception as e:
                await db.rollback()
                raise
    
    
    
    
    async def get_referral_link(self, user_id: int) -> str:
        """Получает реферальную ссылку пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Реферальная ссылка
        """
        # Получаем имя бота из переменных или используем дефолтное
        bot_username = os.getenv("BOT_USERNAME", "LazyFarmerBot")
        return f"https://t.me/{bot_username}?start=ref_{user_id}"
    
    async def get_referral_stats(self, user_id: int) -> Dict:
        """Получает статистику рефералов пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Статистика рефералов
        """
        # Общее количество рефералов
        total = await self.fetchone(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?",
            (user_id,)
        )
        
        # Количество достигших престижа 5
        prestige5 = await self.fetchone(
            """SELECT COUNT(*) FROM referrals r
               JOIN users u ON r.referred_id = u.user_id
               WHERE r.referrer_id = ? AND u.prestige_level >= 5""",
            (user_id,)
        )
        
        # Общий заработок
        earnings = await self.fetchone(
            """SELECT COALESCE(SUM(reward_coins), 0), COALESCE(SUM(reward_gems), 0)
               FROM referral_rewards WHERE referrer_id = ?""",
            (user_id,)
        )
        
        # Топ рефералов
        top_referrers = await self.fetchall(
            """SELECT r.referrer_id, u.username, COUNT(*) as count
               FROM referrals r
               JOIN users u ON r.referrer_id = u.user_id
               GROUP BY r.referrer_id
               ORDER BY count DESC
               LIMIT 10"""
        )
        
        # Место в топе
        my_place = None
        for i, row in enumerate(top_referrers, 1):
            if row[0] == user_id:
                my_place = i
                break
        
        # Список рефералов
        referrals = await self.fetchall(
            """SELECT r.referred_id, u.username, u.prestige_level, r.joined_at,
                      COALESCE(rr.total_coins, 0) as earned_coins,
                      COALESCE(rr.total_gems, 0) as earned_gems
               FROM referrals r
               JOIN users u ON r.referred_id = u.user_id
               LEFT JOIN (
                   SELECT referred_id, 
                          SUM(reward_coins) as total_coins,
                          SUM(reward_gems) as total_gems
                   FROM referral_rewards 
                   GROUP BY referred_id
               ) rr ON r.referred_id = rr.referred_id
               WHERE r.referrer_id = ?
               ORDER BY r.joined_at DESC""",
            (user_id,)
        )
        
        return {
            "total_referrals": total[0] if total else 0,
            "prestige5_count": prestige5[0] if prestige5 else 0,
            "total_earned_coins": earnings[0] if earnings else 0,
            "total_earned_gems": earnings[1] if earnings else 0,
            "my_place": my_place,
            "top_referrers": [{
                "user_id": row[0],
                "username": row[1],
                "count": row[2]
            } for row in top_referrers],
            "referrals": [{
                "user_id": row[0],
                "username": row[1],
                "prestige_level": row[2],
                "joined_at": row[3],
                "earned_coins": row[4],
                "earned_gems": row[5]
            } for row in referrals]
        }
    
    async def register_referral(self, referred_id: int, referrer_id: int) -> Dict:
        """Регистрирует нового реферала
        
        Args:
            referred_id: ID приглашённого
            referrer_id: ID пригласившего
            
        Returns:
            Результат регистрации
        """
        # Проверяем что не сам себя
        if referred_id == referrer_id:
            return {"success": False, "message": "Нельзя быть своим рефералом!"}
        
        # Проверяем что пригласивший существует
        referrer = await self.get_user(referrer_id)
        if not referrer:
            return {"success": False, "message": "Пригласивший не найден!"}
        
        # Проверяем что ещё не зарегистрирован
        existing = await self.fetchone(
            "SELECT 1 FROM referrals WHERE referred_id = ?",
            (referred_id,)
        )
        
        if existing:
            return {"success": False, "message": "Реферал уже зарегистрирован!"}
        
        # Регистрируем
        await self.execute(
            """INSERT INTO referrals (referrer_id, referred_id)
               VALUES (?, ?)""",
            (referrer_id, referred_id),
            commit=True
        )
        
        # Выдаём награду за регистрацию
        reward = await self._give_referral_reward(referrer_id, referred_id, 'registration')
        
        return {
            "success": True,
            "referrer_username": referrer.get('username', '???'),
            "reward": reward
        }
    
    async def _give_referral_reward(self, referrer_id: int, referred_id: int, 
                                     reward_type: str) -> Dict:
        """Выдаёт награду за реферала
        
        Args:
            referrer_id: ID пригласившего
            referred_id: ID приглашённого
            reward_type: Тип награды (registration, prestige1, prestige5, prestige10)
            
        Returns:
            Информация о награде
        """
        # Настройки наград
        rewards = {
            'registration': {'coins': 100, 'gems': 0},
            'prestige1': {'coins': 50, 'gems': 0},
            'prestige5': {'coins': 200, 'gems': 5},
            'prestige10': {'coins': 500, 'gems': 15}
        }
        
        reward = rewards.get(reward_type, {'coins': 0, 'gems': 0})
        coins = reward['coins']
        gems = reward['gems']
        
        async with self.lock:
            db = await self.connect()
            await db.execute("BEGIN")
            try:
                # Выдаём монеты
                if coins > 0:
                    await db.execute(
                        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                        (coins, referrer_id)
                    )
                
                # Выдаём кристаллы
                if gems > 0:
                    await db.execute(
                        "UPDATE users SET gems = gems + ? WHERE user_id = ?",
                        (gems, referrer_id)
                    )
                
                # Записываем награду
                await db.execute(
                    """INSERT INTO referral_rewards 
                       (referrer_id, referred_id, reward_type, reward_coins, reward_gems)
                       VALUES (?, ?, ?, ?, ?)""",
                    (referrer_id, referred_id, reward_type, coins, gems)
                )
                
                await db.commit()
                
                return {
                    "coins": coins,
                    "gems": gems,
                    "type": reward_type
                }
            except Exception as e:
                await db.rollback()
                raise
    
    # ==================== СЕЗОННЫЕ ИВЕНТЫ (ТЗ v4.0 п.16) ====================
    
    async def get_active_events(self) -> List[Dict]:
        """Получает список активных сезонных ивентов
        
        Returns:
            Список активных ивентов
        """
        from datetime import datetime
        now = datetime.now().isoformat()
        
        rows = await self.fetchall(
            """SELECT event_id, name, description, season, start_date, end_date, 
                      multiplier, is_active
               FROM seasonal_events
               WHERE is_active = 1 
                 AND start_date <= ?
                 AND end_date >= ?
               ORDER BY start_date""",
            (now, now)
        )
        
        return [{
            "event_id": row[0],
            "name": row[1],
            "description": row[2],
            "season": row[3],
            "start_date": row[4],
            "end_date": row[5],
            "multiplier": row[6],
            "is_active": bool(row[7])
        } for row in rows]
    
    async def get_event_by_id(self, event_id: int) -> Optional[Dict]:
        """Получает информацию об ивенте по ID"""
        row = await self.fetchone(
            """SELECT event_id, name, description, season, start_date, end_date,
                      multiplier, is_active
               FROM seasonal_events WHERE event_id = ?""",
            (event_id,)
        )
        
        if not row:
            return None
        
        return {
            "event_id": row[0],
            "name": row[1],
            "description": row[2],
            "season": row[3],
            "start_date": row[4],
            "end_date": row[5],
            "multiplier": row[6],
            "is_active": bool(row[7])
        }
    
    async def get_event_progress(self, user_id: int, event_id: int) -> Dict:
        """Получает прогресс пользователя в ивенте
        
        Args:
            user_id: ID пользователя
            event_id: ID ивента
            
        Returns:
            Прогресс и место в топе
        """
        # Получаем счёт пользователя
        row = await self.fetchone(
            "SELECT score FROM event_leaderboard WHERE event_id = ? AND user_id = ?",
            (event_id, user_id)
        )
        
        user_score = row[0] if row else 0
        
        # Получаем место в топе
        rank_row = await self.fetchone(
            """SELECT COUNT(*) + 1 FROM event_leaderboard 
               WHERE event_id = ? AND score > ?""",
            (event_id, user_score)
        )
        
        rank = rank_row[0] if rank_row else 1
        
        # Получаем топ-10
        top = await self.fetchall(
            """SELECT el.user_id, u.username, el.score
               FROM event_leaderboard el
               JOIN users u ON el.user_id = u.user_id
               WHERE el.event_id = ?
               ORDER BY el.score DESC
               LIMIT 10""",
            (event_id,)
        )
        
        return {
            "score": user_score,
            "rank": rank,
            "top_10": [{
                "user_id": row[0],
                "username": row[1],
                "score": row[2]
            } for row in top]
        }
    
    
    async def add_event_crop(self, user_id: int, event_crop_code: str, quantity: int = 1):
        """Добавляет ивентовый урожай пользователю
        
        Args:
            user_id: ID пользователя
            event_crop_code: Код ивентовой культуры (например, 'pumpkin', 'christmas_tree')
            quantity: Количество
        """
        # Используем отдельную таблицу или поле в инвентаре для ивентовых предметов
        # Здесь добавляем как обычный предмет с префиксом event_
        await self.add_inventory(user_id, f"event_{event_crop_code}", quantity)
    
    async def get_event_inventory(self, user_id: int, event_type: str = None) -> Dict:
        """Получает ивентовые предметы пользователя
        
        Args:
            user_id: ID пользователя
            event_type: Тип ивента (halloween, newyear) или None для всех
            
        Returns:
            Словарь с ивентовыми предметами
        """
        inventory = await self.get_inventory(user_id)
        
        event_items = {}
        for item_code, quantity in inventory.items():
            if item_code.startswith("event_"):
                # Убираем префикс event_
                clean_code = item_code.replace("event_", "")
                
                # Фильтруем по типу если указан
                if event_type:
                    if event_type == "halloween" and "pumpkin" in clean_code:
                        event_items[clean_code] = quantity
                    elif event_type == "newyear" and ("tree" in clean_code or "gift" in clean_code):
                        event_items[clean_code] = quantity
                else:
                    event_items[clean_code] = quantity
        
        return event_items

    # ==================== ПЕРЕВОДЫ МЕЖДУ ИГРОКАМИ (ТЗ v4.0 п.18) ====================
    
    async def get_transfer_limit(self, user_id: int) -> Dict:
        """Получает лимит перевода для пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Dict с информацией о лимите
        """
        # Получаем или создаём настройки лимита
        limit_row = await self.fetchone(
            "SELECT * FROM transfer_limits WHERE user_id = ?",
            (user_id,)
        )
        
        if not limit_row:
            # Создаём запись с дефолтными значениями
            await self.execute(
                """INSERT INTO transfer_limits (user_id, daily_limit, base_percentage, prestige_bonus)
                   VALUES (?, 0, 0.20, 0.0)""",
                (user_id,), commit=True
            )
            base_pct = 0.20
            prestige_bonus = 0.0
            upgrade_bonus = 0.0
            used_today = 0
            last_reset = datetime.now().isoformat()
        else:
            base_pct = limit_row[3] if len(limit_row) > 3 else 0.20
            prestige_bonus = limit_row[4] if len(limit_row) > 4 else 0.0
            upgrade_bonus = limit_row[5] if len(limit_row) > 5 else 0.0
            used_today = limit_row[6] if len(limit_row) > 6 else 0
            last_reset = limit_row[7] if len(limit_row) > 7 else datetime.now().isoformat()
        
        # Проверяем нужно ли сбросить счётчик (новый день)
        try:
            last_reset_date = datetime.fromisoformat(last_reset).date()
            if last_reset_date < datetime.now().date():
                used_today = 0
                await self.execute(
                    "UPDATE transfer_limits SET used_today = 0, last_reset = ? WHERE user_id = ?",
                    (datetime.now().isoformat(), user_id), commit=True
                )
        except:
            pass
        
        # Получаем пользователя для расчёта
        user = await self.get_user(user_id)
        if not user:
            return {"limit": 0, "used": 0, "available": 0}
        
        # Рассчитываем лимит
        prestige_level = user.get('prestige_level', 1)
        city_level = user.get('city_level', 1)
        
        # Требуемые монеты для следующего уровня (примерная формула)
        required_for_next = city_level * 1000
        
        # Базовый лимит = 20% от требуемых
        base_limit = int(required_for_next * base_pct)
        
        # Бонус за престиж (+10% за каждый престиж)
        prestige_multiplier = 1.0 + (prestige_level * 0.10)
        
        # Итоговый лимит
        total_limit = int(base_limit * prestige_multiplier)
        
        available = max(0, total_limit - used_today)
        
        return {
            "limit": total_limit,
            "base_limit": base_limit,
            "prestige_bonus": int(base_limit * (prestige_multiplier - 1.0)),
            "used": used_today,
            "available": available,
            "prestige_level": prestige_level,
            "city_level": city_level
        }
    
    async def can_transfer(self, user_id: int, amount: int) -> Dict:
        """Проверяет может ли пользователь сделать перевод
        
        Args:
            user_id: ID отправителя
            amount: Сумма перевода
            
        Returns:
            Dict с результатом проверки
        """
        # Проверяем престиж (нужен минимум 2)
        user = await self.get_user(user_id)
        if not user:
            return {"can_transfer": False, "reason": "Пользователь не найден"}
        
        if user.get('prestige_level', 1) < 2:
            return {
                "can_transfer": False, 
                "reason": "Переводы доступны с 2 престижа!",
                "required_prestige": 2,
                "current_prestige": user.get('prestige_level', 1)
            }
        
        # Проверяем лимит
        limit_info = await self.get_transfer_limit(user_id)
        if amount > limit_info['available']:
            return {
                "can_transfer": False,
                "reason": f"Превышен дневной лимит! Доступно: {limit_info['available']:,}🪙",
                "available": limit_info['available'],
                "requested": amount
            }
        
        # Проверяем баланс (с учётом комиссии 5%)
        fee = int(amount * 0.05)
        total_needed = amount + fee
        
        if user.get('balance', 0) < total_needed:
            return {
                "can_transfer": False,
                "reason": f"Недостаточно монет! Нужно: {total_needed:,}🪙 (включая комиссию {fee:,}🪙)",
                "balance": user.get('balance', 0),
                "needed": total_needed
            }
        
        return {
            "can_transfer": True,
            "fee": fee,
            "total": total_needed,
            "available_after": user.get('balance', 0) - total_needed
        }
    
    async def make_transfer(self, sender_id: int, receiver_id: int, amount: int, description: str = None) -> Dict:
        """Выполняет перевод между игроками
        
        Args:
            sender_id: ID отправителя
            receiver_id: ID получателя
            amount: Сумма перевода
            description: Описание/причина
            
        Returns:
            Результат операции
        """
        # Проверяем что не сам себе
        if sender_id == receiver_id:
            return {"success": False, "message": "Нельзя переводить самому себе!"}
        
        # Проверяем получателя
        receiver = await self.get_user(receiver_id)
        if not receiver:
            return {"success": False, "message": "Получатель не найден!"}
        
        # Проверяем возможность перевода
        check = await self.can_transfer(sender_id, amount)
        if not check.get('can_transfer', False):
            return {"success": False, "message": check.get('reason', 'Невозможно выполнить перевод')}
        
        fee = check.get('fee', int(amount * 0.05))
        total = check.get('total', amount + fee)
        
        async with self.lock:
            db = await self.connect()
            await db.execute("BEGIN")
            try:
                # Списываем у отправителя
                await db.execute(
                    "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                    (total, sender_id)
                )
                
                # Начисляем получателю
                await db.execute(
                    "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                    (amount, receiver_id)
                )
                
                # Записываем перевод
                cursor = await db.execute(
                    """INSERT INTO transfers (sender_id, receiver_id, amount, fee, total_amount, description)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (sender_id, receiver_id, amount, fee, total, description)
                )
                transfer_id = cursor.lastrowid
                
                # Обновляем использованный лимит
                await db.execute(
                    "UPDATE transfer_limits SET used_today = used_today + ? WHERE user_id = ?",
                    (amount, sender_id)
                )
                
                await db.commit()
                
                # Получаем обновлённые балансы
                sender = await self.get_user(sender_id)
                receiver_new = await self.get_user(receiver_id)
                
                return {
                    "success": True,
                    "transfer_id": transfer_id,
                    "amount": amount,
                    "fee": fee,
                    "total": total,
                    "receiver_username": receiver.get('username', '???'),
                    "sender_balance": sender.get('balance', 0),
                    "receiver_balance": receiver_new.get('balance', 0),
                    "message": f"✅ Перевод выполнен! {amount:,}🪙 отправлено @{receiver.get('username', '???')}"
                }
            except Exception as e:
                await db.rollback()
                raise
    
    async def get_transfer_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Получает историю переводов пользователя
        
        Args:
            user_id: ID пользователя
            limit: Количество записей
            
        Returns:
            Список переводов
        """
        rows = await self.fetchall(
            """SELECT t.*, 
                      s.username as sender_username,
                      r.username as receiver_username
               FROM transfers t
               JOIN users s ON t.sender_id = s.user_id
               JOIN users r ON t.receiver_id = r.user_id
               WHERE t.sender_id = ? OR t.receiver_id = ?
               ORDER BY t.created_at DESC
               LIMIT ?""",
            (user_id, user_id, limit)
        )
        
        return [{
            "transfer_id": row[0],
            "sender_id": row[1],
            "receiver_id": row[2],
            "amount": row[3],
            "fee": row[4],
            "total_amount": row[5],
            "status": row[6],
            "description": row[7],
            "created_at": row[8],
            "sender_username": row[9],
            "receiver_username": row[10],
            "is_outgoing": row[1] == user_id
        } for row in rows]
    
    # ==================== АДМИН МЕТОДЫ (ТЗ v4.0 п.21) ====================
    
    async def get_admin_stats(self) -> Dict:
        """Получает статистику для админ-панели
        
        Returns:
            Словарь со статистикой
        """
        # Общее количество пользователей
        total = await self.fetchone("SELECT COUNT(*) FROM users")
        
        # Активные сегодня
        from datetime import datetime, timedelta
        today = datetime.now().date().isoformat()
        active_today = await self.fetchone(
            "SELECT COUNT(*) FROM users WHERE DATE(last_activity) = ?",
            (today,)
        )
        
        # Активные за неделю
        week_ago = (datetime.now() - timedelta(days=7)).date().isoformat()
        active_week = await self.fetchone(
            "SELECT COUNT(*) FROM users WHERE DATE(last_activity) >= ?",
            (week_ago,)
        )
        
        # Забаненные
        banned = await self.fetchone(
            "SELECT COUNT(*) FROM users WHERE is_banned = 1"
        )
        
        # Новички (< 7 дней)
        new_users = await self.fetchone(
            "SELECT COUNT(*) FROM users WHERE joined_date >= ?",
            (week_ago,)
        )
        
        # Экономика
        total_coins = await self.fetchone("SELECT COALESCE(SUM(balance), 0) FROM users")
        total_gems = await self.fetchone("SELECT COALESCE(SUM(gems), 0) FROM users")
        avg_balance = await self.fetchone("SELECT COALESCE(AVG(balance), 0) FROM users")
        
        # Активность сегодня
        transactions_today = await self.fetchone(
            """SELECT COUNT(*) FROM economy_logs 
               WHERE DATE(created_at) = ? AND action_type = 'transfer'""",
            (today,)
        )
        
        plants_today = await self.fetchone(
            """SELECT COUNT(*) FROM economy_logs 
               WHERE DATE(created_at) = ? AND action_type = 'plant'""",
            (today,)
        )
        
        harvests_today = await self.fetchone(
            """SELECT COUNT(*) FROM economy_logs 
               WHERE DATE(created_at) = ? AND action_type = 'harvest'""",
            (today,)
        )
        
        quests_completed = await self.fetchone(
            """SELECT COUNT(*) FROM user_quests 
               WHERE completed = 1 AND DATE(completed_at) = ?""",
            (today,)
        )
        
        achievements_earned = await self.fetchone(
            """SELECT COUNT(*) FROM user_achievements 
               WHERE completed = 1 AND DATE(completed_at) = ?""",
            (today,)
        )
        
        return {
            "total_users": total[0] if total else 0,
            "active_today": active_today[0] if active_today else 0,
            "active_week": active_week[0] if active_week else 0,
            "banned": banned[0] if banned else 0,
            "new_users": new_users[0] if new_users else 0,
            "total_coins": total_coins[0] if total_coins else 0,
            "total_gems": total_gems[0] if total_gems else 0,
            "avg_balance": avg_balance[0] if avg_balance else 0,
            "transactions_today": transactions_today[0] if transactions_today else 0,
            "plants_today": plants_today[0] if plants_today else 0,
            "harvests_today": harvests_today[0] if harvests_today else 0,
            "quests_completed": quests_completed[0] if quests_completed else 0,
            "achievements_earned": achievements_earned[0] if achievements_earned else 0
        }
    
    async def admin_give_coins(self, admin_id: int, user_id: int, amount: int, reason: str = None) -> bool:
        """Выдача монет админом
        
        Args:
            admin_id: ID админа
            user_id: ID получателя
            amount: Сумма
            reason: Причина
            
        Returns:
            True если успешно
        """
        async with self.lock:
            db = await self.connect()
            await db.execute("BEGIN")
            try:
                # Выдаём монеты
                await db.execute(
                    "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                    (amount, user_id)
                )
                
                # Логируем
                await db.execute(
                    """INSERT INTO admin_logs (admin_id, action, target_user_id, details)
                       VALUES (?, 'give_coins', ?, ?)""",
                    (admin_id, user_id, f"Amount: {amount}, Reason: {reason}")
                )
                
                await db.commit()
                return True
            except Exception as e:
                await db.rollback()
                logging.error(f"Admin give coins error: {e}")
                return False
    
    async def admin_ban_user(self, admin_id: int, user_id: int, duration_hours: int = None, reason: str = None) -> bool:
        """Бан пользователя админом
        
        Args:
            admin_id: ID админа
            user_id: ID пользователя
            duration_hours: Длительность в часах (None = навсегда)
            reason: Причина
            
        Returns:
            True если успешно
        """
        from datetime import datetime, timedelta
        
        ban_until = None
        if duration_hours:
            ban_until = (datetime.now() + timedelta(hours=duration_hours)).isoformat()
        
        async with self.lock:
            db = await self.connect()
            await db.execute("BEGIN")
            try:
                await db.execute(
                    """UPDATE users SET is_banned = 1, ban_reason = ?, ban_until = ?
                       WHERE user_id = ?""",
                    (reason, ban_until, user_id)
                )
                
                await db.execute(
                    """INSERT INTO admin_logs (admin_id, action, target_user_id, details)
                       VALUES (?, 'ban_user', ?, ?)""",
                    (admin_id, user_id, f"Duration: {duration_hours}h, Reason: {reason}")
                )
                
                await db.commit()
                return True
            except Exception as e:
                await db.rollback()
                logging.error(f"Admin ban error: {e}")
                return False
    
    async def admin_unban_user(self, admin_id: int, user_id: int) -> bool:
        """Разбан пользователя
        
        Args:
            admin_id: ID админа
            user_id: ID пользователя
            
        Returns:
            True если успешно
        """
        async with self.lock:
            db = await self.connect()
            await db.execute("BEGIN")
            try:
                await db.execute(
                    """UPDATE users SET is_banned = 0, ban_reason = NULL, ban_until = NULL
                       WHERE user_id = ?""",
                    (user_id,)
                )
                
                await db.execute(
                    """INSERT INTO admin_logs (admin_id, action, target_user_id, details)
                       VALUES (?, 'unban_user', ?, 'User unbanned')""",
                    (admin_id, user_id)
                )
                
                await db.commit()
                return True
            except Exception as e:
                await db.rollback()
                logging.error(f"Admin unban error: {e}")
                return False
    

    async def admin_update_plant(self, admin_id: int, plant_code: str, **kwargs) -> bool:
        """Обновляет параметры растения
        
        Args:
            admin_id: ID админа
            plant_code: Код растения
            **kwargs: Поля для обновления
            
        Returns:
            True если успешно
        """
        allowed_fields = ['item_name', 'item_icon', 'buy_price', 'sell_price', 
                         'growth_time', 'yield_amount', 'required_level', 'is_active']
        
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return False
        
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [plant_code]
        
        async with self.lock:
            db = await self.connect()
            await db.execute("BEGIN")
            try:
                await db.execute(
                    f"UPDATE shop_config SET {set_clause} WHERE item_code = ?",
                    tuple(values)
                )
                
                # Логируем
                await db.execute(
                    """INSERT INTO admin_logs (admin_id, action, target_entity, old_value, new_value)
                       VALUES (?, 'update_plant', ?, ?, ?)""",
                    (admin_id, plant_code, str(kwargs), str(updates))
                )
                
                await db.commit()
                return True
            except Exception as e:
                await db.rollback()
                logging.error(f"Admin update plant error: {e}")
                return False
    
    async def admin_add_plant(self, admin_id: int, plant_code: str, name: str, 
                              icon: str, buy_price: int, sell_price: int, 
                              growth_time: int) -> bool:
        """Добавляет новое растение
        
        Args:
            admin_id: ID админа
            plant_code: Уникальный код
            name: Название
            icon: Иконка
            buy_price: Цена покупки
            sell_price: Цена продажи
            growth_time: Время роста
            
        Returns:
            True если успешно
        """
        try:
            await self.execute(
                """INSERT INTO shop_config 
                   (item_code, item_name, item_icon, category, buy_price, sell_price, growth_time, yield_amount)
                   VALUES (?, ?, ?, 'seed', ?, ?, ?, 1)""",
                (plant_code, name, icon, buy_price, sell_price, growth_time),
                commit=True
            )
            
            # Логируем
            await self.execute(
                """INSERT INTO admin_logs (admin_id, action, target_entity, new_value)
                   VALUES (?, 'add_plant', ?, ?)""",
                (admin_id, plant_code, f"Name: {name}, Price: {buy_price}"),
                commit=True
            )
            
            return True
        except Exception as e:
            logging.error(f"Admin add plant error: {e}")
            return False
    
    async def admin_toggle_plant(self, admin_id: int, plant_code: str) -> bool:
        """Включает/выключает растение
        
        Args:
            admin_id: ID админа
            plant_code: Код растения
            
        Returns:
            True если успешно
        """
        async with self.lock:
            db = await self.connect()
            await db.execute("BEGIN")
            try:
                # Получаем текущий статус
                row = await db.execute(
                    "SELECT is_active FROM shop_config WHERE item_code = ?",
                    (plant_code,)
                )
                current = await row.fetchone()
                new_status = 0 if current and current[0] else 1
                
                await db.execute(
                    "UPDATE shop_config SET is_active = ? WHERE item_code = ?",
                    (new_status, plant_code)
                )
                
                # Логируем
                await db.execute(
                    """INSERT INTO admin_logs (admin_id, action, target_entity, new_value)
                       VALUES (?, 'toggle_plant', ?, ?)""",
                    (admin_id, plant_code, f"Active: {new_status}")
                )
                
                await db.commit()
                return True
            except Exception as e:
                await db.rollback()
                logging.error(f"Admin toggle plant error: {e}")
                return False
    
    async def admin_broadcast_message(self, admin_id: int, message_text: str, 
                                      target_type: str = 'all') -> Dict:
        """Отправляет массовую рассылку
        
        Args:
            admin_id: ID админа
            message_text: Текст сообщения
            target_type: Целевая аудитория (all, active_today, new)
            
        Returns:
            Статистика рассылки
        """
        from datetime import datetime, timedelta
        
        # Формируем запрос в зависимости от цели
        if target_type == 'active_today':
            today = datetime.now().date().isoformat()
            query = "SELECT user_id FROM users WHERE DATE(last_activity) = ? AND is_banned = 0"
            params = (today,)
        elif target_type == 'new':
            week_ago = (datetime.now() - timedelta(days=7)).date().isoformat()
            query = "SELECT user_id FROM users WHERE joined_date >= ? AND is_banned = 0"
            params = (week_ago,)
        else:  # all
            query = "SELECT user_id FROM users WHERE is_banned = 0"
            params = ()
        
        rows = await self.fetchall(query, params)
        user_ids = [row[0] for row in rows]
        
        # Логируем рассылку
        await self.execute(
            """INSERT INTO admin_logs (admin_id, action, details)
               VALUES (?, 'broadcast', ?)""",
            (admin_id, f"Target: {target_type}, Users: {len(user_ids)}"),
            commit=True
        )
        
        return {
            "total_users": len(user_ids),
            "user_ids": user_ids,
            "target_type": target_type
        }

    # ==================== УВЕДОМЛЕНИЯ (ТЗ v4.0 п.20) ====================
    
    async def get_notification_settings(self, user_id: int) -> Dict:
        """Получает настройки уведомлений пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Настройки уведомлений
        """
        user = await self.get_user(user_id)
        if not user:
            return self._default_notification_settings()
        
        settings = user.get('settings', {})
        notifications = settings.get('notifications', {})
        
        # Если настроек нет, возвращаем дефолтные
        if not notifications:
            return self._default_notification_settings()
        
        return {
            "harvest_ready": notifications.get('harvest_ready', True),
            "daily_bonus": notifications.get('daily_bonus', True),
            "new_quests": notifications.get('new_quests', True),
            "farmer_report": notifications.get('farmer_report', True),
            "marketing": notifications.get('marketing', False),
            "friend_achievements": notifications.get('friend_achievements', False)
        }
    
    def _default_notification_settings(self) -> Dict:
        """Возвращает настройки по умолчанию"""
        return {
            "harvest_ready": True,
            "daily_bonus": True,
            "new_quests": True,
            "farmer_report": True,
            "marketing": False,
            "friend_achievements": False
        }
    
    async def update_notification_settings(self, user_id: int, **kwargs) -> bool:
        """Обновляет настройки уведомлений
        
        Args:
            user_id: ID пользователя
            **kwargs: Настройки для обновления
            
        Returns:
            True если успешно
        """
        user = await self.get_user(user_id)
        if not user:
            return False
        
        settings = user.get('settings', {})
        notifications = settings.get('notifications', {})
        
        # Обновляем только разрешённые поля
        allowed_fields = ['harvest_ready', 'daily_bonus', 'new_quests', 
                         'farmer_report', 'marketing', 'friend_achievements']
        
        for field in allowed_fields:
            if field in kwargs:
                notifications[field] = bool(kwargs[field])
        
        settings['notifications'] = notifications
        
        return await self.update_user_settings(user_id, settings)
    
    async def should_send_notification(self, user_id: int, notification_type: str) -> bool:
        """Проверяет нужно ли отправлять уведомление
        
        Args:
            user_id: ID пользователя
            notification_type: Тип уведомления
            
        Returns:
            True если нужно отправить
        """
        settings = await self.get_notification_settings(user_id)
        return settings.get(notification_type, True)
    
    async def get_notification_text(self, notification_type: str, **context) -> Optional[str]:
        """Формирует текст уведомления
        
        Args:
            notification_type: Тип уведомления
            **context: Контекст для формирования текста
            
        Returns:
            Текст уведомления или None
        """
        if notification_type == 'harvest_ready':
            ready_count = context.get('ready_count', 0)
            estimated_income = context.get('estimated_income', 0)
            plot_numbers = context.get('plot_numbers', [])
            
            if ready_count == 1:
                return (
                    f"🔔 <b>Урожай созрел!</b>\n\n"
                    f"🌽 Твой урожай на грядке #{plot_numbers[0]} созрел!\n"
                    f"Собери его, чтобы освободить место.\n\n"
                    f"💰 Примерный доход: {estimated_income:,}🪙"
                )
            else:
                plots_str = ', '.join([f"#{n}" for n in plot_numbers[:3]])
                if len(plot_numbers) > 3:
                    plots_str += f" и еще {len(plot_numbers) - 3}"
                
                return (
                    f"🔔 <b>Урожай созрел!</b>\n\n"
                    f"🌽 Готово грядок: {ready_count}\n"
                    f"Грядки: {plots_str}\n\n"
                    f"💰 Примерный доход: {estimated_income:,}🪙"
                )
        
        elif notification_type == 'daily_bonus':
            streak = context.get('streak', 1)
            return (
                f"🔔 <b>Ежедневный бонус ждет!</b>\n\n"
                f"🎁 Ты давно не заходил(а) на ферму!\n"
                f"Ежедневный бонус ждет тебя.\n\n"
                f"Твоя серия: {streak} дней\n"
                f"Завтра будет супер-бонус!"
            )
        
        elif notification_type == 'new_quests':
            quest_count = context.get('quest_count', 5)
            total_reward = context.get('total_reward', 0)
            return (
                f"🔔 <b>Новые квесты доступны!</b>\n\n"
                f"📜 {quest_count} заданий ждут тебя.\n\n"
                f"💰 Суммарная награда: {total_reward:,}🪙 + предметы"
            )
        
        elif notification_type == 'farmer_report':
            planted = context.get('planted', 0)
            harvested = context.get('harvested', 0)
            earned = context.get('earned', 0)
            salary = context.get('salary', 0)
            net = earned - salary
            
            return (
                f"🔔 <b>Отчет от фермера</b>\n\n"
                f"👤 Твой фермер отработал смену:\n"
                f"• Посажено: {planted}\n"
                f"• Собрано: {harvested}\n"
                f"• Заработано: {earned:,}🪙\n"
                f"• Зарплата: -{salary:,}🪙\n"
                f"• Чистый доход: {'+' if net >= 0 else ''}{net:,}🪙"
            )
        
        return None
    
    async def check_and_notify_harvest_ready(self, user_id: int, bot):
        """Проверяет созревший урожай и отправляет уведомление
        
        Args:
            user_id: ID пользователя
            bot: Экземпляр бота
        """
        # Проверяем включены ли уведомления
        if not await self.should_send_notification(user_id, 'harvest_ready'):
            return
        
        # Получаем готовые грядки
        plots = await self.get_plots(user_id)
        ready_plots = [p for p in plots if p.get('status') == 'ready']
        
        if not ready_plots:
            return
        
        # Рассчитываем примерный доход
        estimated_income = 0
        for plot in ready_plots:
            crop_data = await self.get_shop_item(plot.get('crop_type', ''))
            if crop_data:
                user = await self.get_user(user_id)
                multiplier = user.get('prestige_multiplier', 1.0) if user else 1.0
                estimated_income += int(crop_data.get('sell_price', 0) * multiplier)
        
        # Формируем текст
        notification_text = await self.get_notification_text(
            'harvest_ready',
            ready_count=len(ready_plots),
            estimated_income=estimated_income,
            plot_numbers=[p['number'] for p in ready_plots]
        )
        
        if notification_text:
            try:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🌾 На ферму", callback_data="back_farm")]
                ])
                await bot.send_message(user_id, notification_text, reply_markup=keyboard, parse_mode="HTML")
            except Exception as e:
                logging.error(f"Failed to send harvest notification to {user_id}: {e}")
    
    async def check_and_notify_daily_bonus(self, user_id: int, bot):
        """Проверяет доступность ежедневного бонуса
        
        Args:
            user_id: ID пользователя
            bot: Экземпляр бота
        """
        if not await self.should_send_notification(user_id, 'daily_bonus'):
            return
        
        # Проверяем доступен ли бонус
        bonus = await self.get_daily_bonus(user_id)
        if not bonus or not bonus.get('available', False):
            return
        
        # Проверяем неактивность (12+ часов)
        user = await self.get_user(user_id)
        if not user or not user.get('last_activity'):
            return
        
        try:
            last_activity = datetime.fromisoformat(user['last_activity'])
            hours_inactive = (datetime.now() - last_activity).total_seconds() / 3600
            
            if hours_inactive < 12:
                return
        except:
            return
        
        # Отправляем уведомление
        notification_text = await self.get_notification_text(
            'daily_bonus',
            streak=bonus.get('streak', 1)
        )
        
        if notification_text:
            try:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🎁 Забрать бонус", callback_data="daily_bonus")]
                ])
                await bot.send_message(user_id, notification_text, reply_markup=keyboard, parse_mode="HTML")
            except Exception as e:
                logging.error(f"Failed to send daily bonus notification to {user_id}: {e}")

    # ==================== УВЕДОМЛЕНИЯ В ЧАТ (ТЗ v4.0 п.19.2) ====================
    
    async def should_notify_chat(self, achievement_code: str) -> bool:
        """Проверяет нужно ли отправлять уведомление в чат
        
        Args:
            achievement_code: Код ачивки
            
        Returns:
            True если нужно уведомлять
        """
        # Уведомляем только о крупных достижениях
        notify_achievements = {
            'prestige_50', 'prestige_100', 'prestige_200',
            'billionaire', 'harvest_1m', 'first_farmer',
            'dynasty_master', 'event_winner', 'referral_50'
        }
        return achievement_code in notify_achievements
    
    async def get_chat_notification_text(self, user_id: int, achievement_code: str) -> Optional[str]:
        """Формирует текст уведомления для чата
        
        Args:
            user_id: ID пользователя
            achievement_code: Код ачивки
            
        Returns:
            Текст уведомления или None
        """
        user = await self.get_user(user_id)
        if not user:
            return None
        
        # Получаем информацию об ачивке
        achievement = await self.fetchone(
            "SELECT name, icon FROM achievements WHERE achievement_code = ?",
            (achievement_code,)
        )
        
        if not achievement:
            return None
        
        name = achievement[0]
        icon = achievement[1] if achievement[1] else '🏆'
        username = user.get('username', '???')
        
        # Формируем текст
        templates = {
            'prestige_50': f"🏆 Игрок @{username} только что достиг престижа 50!\nПоздравляем легенду! 👏",
            'prestige_100': f"👑 Игрок @{username} достиг невероятного престижа 100!\nБог среди фермеров! 🔥",
            'prestige_200': f"🌟 Игрок @{username} достиг БОЖЕСТВЕННОГО престижа 200!\nЭто исторический момент! 🎉",
            'billionaire': f"💰 @{username} стал МИЛЛИАРДЕРОМ!\nБаланс превысил 1,000,000,000🪙! 🤑",
            'harvest_1m': f"🌾 @{username} собрал 1,000,000 растений!\nНастоящий Бог Урожая! 🚜",
            'first_farmer': f"👤 @{username} нанял своего первого фермера!\nАвтоматизация в действии! ⚡",
            'dynasty_master': f"👥 @{username} построил фермерскую династию!\n50 друзей присоединилось! 🌟",
            'event_winner': f"🎉 @{username} вошел в топ-10 ивента!\nНастоящий чемпион! 🏆",
            'referral_50': f"🔗 @{username} пригласил 50 друзей!\nЛидер мнений и социальный фермер! 👥"
        }
        
        return templates.get(achievement_code, f"🏆 @{username} получил достижение {icon} {name}! Поздравляем!")
    
    async def check_referral_rewards(self, user_id: int) -> List[Dict]:
        """Проверяет и выдаёт награды за достижения рефералов
        
        Args:
            user_id: ID пользователя (для которого проверяем достижения)
            
        Returns:
            Список выданных наград
        """
        # Находим пригласившего
        ref_info = await self.fetchone(
            """SELECT referrer_id FROM referrals WHERE referred_id = ?""",
            (user_id,)
        )
        
        if not ref_info:
            return []
        
        referrer_id = ref_info[0]
        
        # Получаем текущий престиж
        user = await self.get_user(user_id)
        if not user:
            return []
        
        prestige = user.get('prestige_level', 1)
        
        # Проверяем какие награды уже получены
        received = await self.fetchall(
            """SELECT reward_type FROM referral_rewards 
               WHERE referrer_id = ? AND referred_id = ?""",
            (referrer_id, user_id)
        )
        
        received_types = {r[0] for r in received}
        
        # Определяем какие награды нужно выдать
        new_rewards = []
        
        if prestige >= 1 and 'prestige1' not in received_types:
            reward = await self._give_referral_reward(referrer_id, user_id, 'prestige1')
            new_rewards.append(reward)
        
        if prestige >= 5 and 'prestige5' not in received_types:
            reward = await self._give_referral_reward(referrer_id, user_id, 'prestige5')
            new_rewards.append(reward)
        
        if prestige >= 10 and 'prestige10' not in received_types:
            reward = await self._give_referral_reward(referrer_id, user_id, 'prestige10')
            new_rewards.append(reward)
        
        return new_rewards
