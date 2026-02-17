import aiosqlite
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import json
import logging

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
        row = await self.fetchone(
            "SELECT * FROM users WHERE user_id = ? AND is_banned = 0", (user_id,)
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
    
    async def update_balance(self, user_id: int, amount: int, transaction=True):
        async with self.lock:
            db = await self.connect()
            await db.execute("BEGIN")
            try:
                user = await self.get_user(user_id)
                if not user:
                    await db.rollback()
                    return None
                new_balance = user["balance"] + amount
                await db.execute("UPDATE users SET balance = ?, last_activity = CURRENT_TIMESTAMP WHERE user_id = ?", (new_balance, user_id))
                await db.commit()
                return new_balance
            except:
                await db.rollback()
                raise
    
    async def update_prestige(self, user_id: int, level: int, multiplier: float):
        await self.execute(
            "UPDATE users SET prestige_level = ?, prestige_multiplier = ?, city_level = ? WHERE user_id = ?",
            (level, multiplier, level, user_id), commit=True
        )
    
    # Грядки
    async def get_plots(self, user_id: int) -> List[Dict]:
        # Сначала обновим созревшие грядки
        await self._update_ready_plots(user_id)
        
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
    
    async def harvest_plots(self, user_id: int) -> int:
        async with self.lock:
            db = await self.connect()
            await db.execute("BEGIN")
            try:
                # Получить готовые грядки и цены
                async with db.execute(
                    """SELECT p.plot_number, p.crop_type, s.sell_price 
                       FROM plots p JOIN shop_config s ON p.crop_type = s.item_code 
                       WHERE p.user_id = ? AND p.status = 'ready'""", (user_id,)
                ) as cursor:
                    rows = await cursor.fetchall()
                
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
    
    async def claim_quest_reward(self, user_id: int, quest_id: int) -> Dict:
        """Выдает награду за выполненный квест"""
        today = datetime.now().date()
        
        row = await self.fetchone(
            """SELECT q.reward_coins, q.reward_items_json, uq.completed, uq.claimed
               FROM user_quests uq
               JOIN quests q ON uq.quest_id = q.quest_id
               WHERE uq.user_id = ? AND uq.quest_id = ? AND uq.assigned_date = ?""",
            (user_id, quest_id, today)
        )
        
        if not row:
            return {"success": False, "message": "Квест не найден"}
        
        coins, items_json, completed, claimed = row
        
        if not completed:
            return {"success": False, "message": "Квест еще не выполнен"}
        
        if claimed:
            return {"success": False, "message": "Награда уже получена"}
        
        # Выдаем награду
        if coins > 0:
            await self.update_balance(user_id, coins)
        
        items = json.loads(items_json) if items_json else {}
        for item, qty in items.items():
            await self.add_inventory(user_id, item, qty)
        
        # Помечаем как полученную
        await self.execute(
            """UPDATE user_quests SET claimed = 1 
               WHERE user_id = ? AND quest_id = ? AND assigned_date = ?""",
            (user_id, quest_id, today), commit=True
        )
        
        return {"success": True, "coins": coins, "items": items}
    
    # ==================== СИСТЕМА ДОСТИЖЕНИЙ (АЧИВОК) ====================
    
    async def get_achievement_categories(self) -> List[Dict]:
        """Получает все категории достижений"""
        rows = await self.fetchall(
            "SELECT category_id, name, icon, description, sort_order FROM achievement_categories ORDER BY sort_order"
        )
        return [{"id": r[0], "name": r[1], "icon": r[2], "description": r[3], "sort_order": r[4]} for r in rows]
        
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
    async def get_admin_role(self, user_id: int) -> Optional[str]:
        """Получает роль администратора"""
        row = await self.fetchone(
            "SELECT role FROM admin_roles WHERE user_id = ?",
            (user_id,)
        )
        return row[0] if row else None
    
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
    
    async def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Ищет пользователя по username"""
        row = await self.fetchone(
            "SELECT * FROM users WHERE username = ? OR LOWER(username) = LOWER(?)",
            (username, username)
        )
        if row:
            return {
                "user_id": row[0], "username": row[1], "first_name": row[2],
                "balance": row[3], "prestige_level": row[4], "prestige_multiplier": row[5],
                "city_level": row[6], "total_harvested": row[7],
                "is_banned": row[10], "ban_reason": row[11]
            }
        return None
    
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
    
    async def log_admin_action(self, admin_id: int, action_type: str, 
                               target_user_id: int = None, target_entity_id: str = None,
                               old_value: dict = None, new_value: dict = None, 
                               reason: str = None, details: dict = None):
        """Логирует действие администратора"""
        import json
        
        # Получаем роль админа
        role = await self.get_admin_role(admin_id)
        
        await self.execute(
            """INSERT INTO admin_logs 
               (admin_id, admin_role, action_type, target_user_id, target_entity_id, 
                old_value, new_value, reason, details)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (admin_id, role, action_type, target_user_id, target_entity_id,
             json.dumps(old_value) if old_value else None,
             json.dumps(new_value) if new_value else None,
             reason, json.dumps(details) if details else None),
            commit=True
        )
        
        # Также пишем в общий лог
        await self.log_event('admin', 'INFO', action_type, admin_id, target_user_id, 'user', 
                            {'reason': reason, **(details or {})})
    
    async def log_economy(self, user_id: int, operation_type: str, amount: int,
                         currency_type: str = 'coins', item_id: str = None,
                         balance_after: int = None, source: str = None, 
                         source_id: str = None, details: dict = None):
        """Логирует экономическую операцию"""
        import json
        
        await self.execute(
            """INSERT INTO economy_logs 
               (user_id, operation_type, currency_type, amount, item_id, 
                balance_after, source, source_id, details)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, operation_type, currency_type, amount, item_id,
             balance_after, source, source_id, json.dumps(details) if details else None),
            commit=True
        )
        
        # Пишем в общий лог
        await self.log_event('economy', 'INFO', operation_type, user_id, None, None, {
            'amount': amount, 'currency': currency_type, 'source': source, 'balance_after': balance_after
        })
    
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

    
# Инициализация базы данных (для запуска отдельно)
async def init_db():
    db = Database()
    await db.init_from_sql("init_db.sql")

    
