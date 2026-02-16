import aiosqlite
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import json
import logging


class Database:
    def __init__(self, db_path: str = "farm.db"):
        self.db_path = db_path
        self.lock = asyncio.Lock()
    
    async def get_db(self):
        return await aiosqlite.connect(self.db_path)
    
    async def execute(self, query: str, params=(), commit=False):
        async with self.lock:
            async with await self.get_db() as db:
                await db.execute(query, params)
                if commit:
                    await db.commit()
    
    async def fetchall(self, query: str, params=()):
        async with self.lock:
            async with await self.get_db() as db:
                async with db.execute(query, params) as cursor:
                    return await cursor.fetchall()
    
    async def fetchone(self, query: str, params=()):
        async with self.lock:
            async with await self.get_db() as db:
                async with db.execute(query, params) as cursor:
                    return await cursor.fetchone()
    
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
        row = await self.fetchone(
            "SELECT * FROM users WHERE user_id = ? AND is_banned = 0", (user_id,)
        )
        if row:
            return {
                "user_id": row[0], "username": row[1], "first_name": row[2],
                "balance": row[3], "prestige_level": row[4], "prestige_multiplier": row[5],
                "city_level": row[6], "total_harvested": row[7]
            }
        return None
    
    async def update_balance(self, user_id: int, amount: int, transaction=True):
        if transaction:
            async with await self.get_db() as db:
                await db.execute("BEGIN")
                try:
                    user = await self.get_user(user_id)
                    new_balance = user["balance"] + amount
                    await db.execute("UPDATE users SET balance = ?, last_activity = CURRENT_TIMESTAMP WHERE user_id = ?", (new_balance, user_id))
                    await db.commit()
                    return new_balance
                except:
                    await db.rollback()
                    raise
        else:
            await self.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id), commit=True)
    
    async def update_prestige(self, user_id: int, level: int, multiplier: float):
        await self.execute(
            "UPDATE users SET prestige_level = ?, prestige_multiplier = ?, city_level = ? WHERE user_id = ?",
            (level, multiplier, level, user_id), commit=True
        )
    
    # Грядки
    async def get_plots(self, user_id: int) -> List[Dict]:
        rows = await self.fetchall(
            """SELECT plot_number, status, crop_type, planted_time, growth_time_seconds 
               FROM plots WHERE user_id = ? ORDER BY plot_number""", (user_id,)
        )
        plots = []
        now = datetime.now()
        for row in rows:
            plot = {"number": row[0], "status": row[1]}
            if row[1] == "growing":
                planted = datetime.fromisoformat(row[3])
                remaining = max(0, (planted + timedelta(seconds=row[4]) - now).total_seconds())
                plot.update({
                    "crop_type": row[2],
                    "remaining_time": int(remaining),
                    "ready": remaining == 0
                })
            plots.append(plot)
        return plots
    
    async def plant_crop(self, user_id: int, plot_number: int, crop_type: str, growth_time: int):
        await self.execute(
            """UPDATE plots SET status = 'growing', crop_type = ?, 
               planted_time = CURRENT_TIMESTAMP, growth_time_seconds = ? 
               WHERE user_id = ? AND plot_number = ? AND status = 'empty'""",
            (crop_type, growth_time, user_id, plot_number), commit=True
        )
    
    async def harvest_plots(self, user_id: int) -> int:
        async with await self.get_db() as db:
            await db.execute("BEGIN")
            try:
                # Получить готовые грядки и цены
                rows = await db.execute_fetchall(
                    """SELECT p.plot_number, p.crop_type, s.sell_price 
                       FROM plots p JOIN shop_config s ON p.crop_type = s.item_code 
                       WHERE p.user_id = ? AND p.status = 'ready'""", (user_id,)
                )
                
                total = 0
                user = await self.get_user(user_id)
                multiplier = user["prestige_multiplier"]
                
                for row in rows:
                    total += row[2] * multiplier
                
                # Обновить баланс и сбросить грядки
                await db.execute(
                    "UPDATE users SET balance = balance + ?, total_harvested = total_harvested + ?, last_activity = CURRENT_TIMESTAMP WHERE user_id = ?",
                    (total, len(rows), user_id)
                )
                await db.execute(
                    "UPDATE plots SET status = 'empty', crop_type = NULL, planted_time = NULL, growth_time_seconds = NULL WHERE user_id = ? AND status = 'ready'",
                    (user_id,)
                )
                await db.commit()
                return total
            except:
                await db.rollback()
                raise
    
    # Инвентарь
    async def get_inventory(self, user_id: int) -> Dict[str, int]:
        rows = await self.fetchall("SELECT item_code, quantity FROM inventory WHERE user_id = ?", (user_id,))
        return {row[0]: row[1] for row in rows}
    
    async def add_inventory(self, user_id: int, item_code: str, quantity: int):
        await self.execute(
            """INSERT INTO inventory (user_id, item_code, quantity) 
               VALUES (?, ?, ?) 
               ON CONFLICT(user_id, item_code) DO UPDATE SET quantity = quantity + ?""",
            (user_id, item_code, quantity, quantity), commit=True
        )
    
    async def remove_inventory(self, user_id: int, item_code: str, quantity: int):
        await self.execute(
            "UPDATE inventory SET quantity = quantity - ? WHERE user_id = ? AND item_code = ? AND quantity >= ?",
            (quantity, user_id, item_code, quantity), commit=True
        )
    
    # Магазин
    async def get_shop_items(self, category: str = None) -> List[Dict]:
        if category:
            rows = await self.fetchall("SELECT * FROM shop_config WHERE category = ? ORDER BY sort_order", (category,))
        else:
            rows = await self.fetchall("SELECT * FROM shop_config ORDER BY category, sort_order")
        
        return [{"item_code": r[0], "name": r[1], "icon": r[2], "buy_price": r[3], 
                "sell_price": r[4], "growth_time": r[5], "category": r[6]} for r in rows]
    
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
    
    async def claim_daily_bonus(self, user_id: int):
        bonus = await self.get_daily_bonus(user_id)
        if not bonus["available"]:
            return False
        
        # Выдать награду
        await self.update_balance(user_id, bonus["coins"])
        for item, qty in bonus["items"].items():
            await self.add_inventory(user_id, item, qty)
        
        # Обновить прогресс
        today = datetime.now().date()
        await self.execute(
            """INSERT INTO user_daily (user_id, current_streak, last_claim_date) 
               VALUES (?, ?, ?) 
               ON CONFLICT(user_id) DO UPDATE SET 
               current_streak = ?, last_claim_date = ?""",
            (user_id, bonus["streak"], today, bonus["streak"], today), commit=True
        )
        return True
    
    # Промокоды
    async def activate_promo(self, user_id: int, code: str) -> Dict:
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
        
        rewards = json.loads(promo[2])
        
        # Выдать награды
        await self.update_balance(user_id, rewards.get("coins", 0))
        for item, qty in rewards.get("items", {}).items():
            await self.add_inventory(user_id, item, qty)
        
        # Обновить счетчик
        await self.execute(
            "UPDATE promocodes SET times_used = times_used + 1 WHERE id = ?", (promo[0],), commit=True
        )
        await self.execute(
            "INSERT INTO promo_activations (promo_id, user_id) VALUES (?, ?)", (promo[0], user_id), commit=True
        )
        
        return {"success": True, "rewards": rewards}
    
    async def get_promo_codes(self) -> List[Dict]:
        rows = await self.fetchall("SELECT * FROM promocodes WHERE is_active = 1 AND valid_until > CURRENT_TIMESTAMP")
        return [{"id": r[0], "code": r[1], "description": r[3], "coins": r[4], "items": json.loads(r[5])} for r in rows]
    
    async def get_promo_activations(self, user_id: int) -> List[Dict]:
        rows = await self.fetchall("SELECT * FROM promo_activations WHERE user_id = ?", (user_id,))
        return [{"promo_id": r[0], "promo_code": r[1]} for r in rows]
    

    async def init_from_sql(self, sql_file: str):
        """Выполняет SQL скрипт инициализации"""
        import os
        if not os.path.exists(sql_file):
            logging.warning(f"SQL file {sql_file} not found, skipping DB initialization")
            return
            
        async with self.lock:
            async with await self.get_db() as db:
                with open(sql_file, 'r', encoding='utf-8') as f:
                    sql = f.read()
                await db.executescript(sql)
                await db.commit()
                logging.info(f"Database initialized from {sql_file}")

# Инициализация базы данных (для запуска отдельно)
async def init_db():
    db = Database()
    await db.init_from_sql("init_db.sql")

