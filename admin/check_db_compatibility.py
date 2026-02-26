#!/usr/bin/env python3
"""
Скрипт проверки совместимости базы данных Lazy Farmer v4.0
Запустить для проверки всех таблиц и связей
"""

import asyncio
import aiosqlite
from typing import List, Tuple

DB_PATH = "bot.db"

# Ожидаемые таблицы
REQUIRED_TABLES = {
    'users',
    'plots',
    'shop_items',
    'shop_categories',
    'inventory',
    'daily_bonus',
    'user_daily',
    'player_achievements',
    'achievements',
    'achievement_categories',
    'active_promocodes',
    'promocode_claims',
    'referrals',
    'market_listings',
    'market_transactions',
    'upgrades',
    'seasonal_events',
    'event_participation',
    'farmers',
    'active_quests',
    'user_stats',
    'clans',
    'clan_members',
    'notifications',
    'economy_logs',
    'progression_logs',
    'security_logs',
    'promo_logs',
    'seasonal_events',
    'event_participation',
    'quest_templates',
    'daily_bonus_history',
    'user_referrals',
    'referral_reward_settings',
    'farmer_logs',
}

# Ожидаемые индексы для оптимизации
REQUIRED_INDEXES = {
    'idx_plots_user_status',
    'idx_plots_user_ready',
    'idx_player_achievements_progress',
    'idx_users_username_lower',
    'idx_farmer_logs_detailed',
}


async def check_tables(db: aiosqlite.Connection) -> Tuple[List[str], List[str]]:
    """Проверяет наличие всех требуемых таблиц"""
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    existing_tables = {row[0] for row in await cursor.fetchall()}
    
    missing = list(REQUIRED_TABLES - existing_tables)
    extra = list(existing_tables - REQUIRED_TABLES - {'sqlite_sequence'})
    
    return missing, extra


async def check_indexes(db: aiosqlite.Connection) -> Tuple[List[str], List[str]]:
    """Проверяет наличие важных индексов"""
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    )
    existing_indexes = {row[0] for row in await cursor.fetchall()}
    
    missing = list(REQUIRED_INDEXES - existing_indexes)
    extra = []  # Дополнительные индексы - нормально
    
    return missing, extra


async def check_foreign_keys(db: aiosqlite.Connection) -> List[str]:
    """Проверяет целостность внешних ключей"""
    issues = []
    
    # Проверяем orphaned записи
    checks = [
        ("plots", "user_id", "users", "user_id"),
        ("inventory", "user_id", "users", "user_id"),
        ("farmers", "user_id", "users", "user_id"),
        ("active_quests", "user_id", "users", "user_id"),
    ]
    
    for table, fk_column, parent_table, parent_column in checks:
        cursor = await db.execute(f"""
            SELECT COUNT(*) FROM {table} t
            LEFT JOIN {parent_table} p ON t.{fk_column} = p.{parent_column}
            WHERE p.{parent_column} IS NULL
        """)
        count = (await cursor.fetchone())[0]
        if count > 0:
            issues.append(f"Таблица {table}: {count} orphaned записей в {fk_column}")
    
    return issues


async def main():
    print("=" * 60)
    print("ПРОВЕРКА СОВМЕСТИМОСТИ БАЗЫ ДАННЫХ Lazy Farmer v4.0")
    print("=" * 60)
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Проверка таблиц
            print("\n📋 ПРОВЕРКА ТАБЛИЦ:")
            missing_tables, extra_tables = await check_tables(db)
            
            if missing_tables:
                print(f"  ❌ Отсутствуют таблицы: {', '.join(missing_tables)}")
            else:
                print("  ✅ Все требуемые таблицы на месте")
            
            if extra_tables:
                print(f"  ℹ️  Дополнительные таблицы: {', '.join(extra_tables)}")
            
            # Проверка индексов
            print("\n🔍 ПРОВЕРКА ИНДЕКСОВ:")
            missing_indexes, _ = await check_indexes(db)
            
            if missing_indexes:
                print(f"  ⚠️  Рекомендуемые индексы отсутствуют:")
                for idx in missing_indexes:
                    print(f"     - {idx}")
            else:
                print("  ✅ Все рекомендуемые индексы на месте")
            
            # Проверка целостности
            print("\n🔗 ПРОВЕРКА ЦЕЛОСТНОСТИ:")
            issues = await check_foreign_keys(db)
            
            if issues:
                print("  ⚠️  Найдены проблемы:")
                for issue in issues:
                    print(f"     - {issue}")
            else:
                print("  ✅ Целостность данных в порядке")
            
            # Итог
            print("\n" + "=" * 60)
            if missing_tables or missing_indexes or issues:
                print("❌ НАЙДЕНЫ ПРОБЛЕМЫ. Запустите инициализацию БД.")
            else:
                print("✅ БАЗА ДАННЫХ ПОЛНОСТЬЮ СОВМЕСТИМА")
            print("=" * 60)
            
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        print("Возможно, база данных еще не создана. Запустите init_db.sql")


if __name__ == "__main__":
    asyncio.run(main())
