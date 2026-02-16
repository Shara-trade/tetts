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
                "balance": row[3], "prestige_level": row[4], "prestige_multiplier": row[5],
                "city_level": row[6], "total_harvested": row[7]
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
    
    # ДОСТИЖЕНИЯ
    async def get_achievements(self, user_id: int) -> List[Dict]:
        """Получает все достижения с прогрессом пользователя"""
        rows = await self.fetchall(
            """SELECT a.achievement_id, a.code, a.name, a.description, a.icon,
                      a.requirement_type, a.requirement_count, 
                      a.reward_coins, a.reward_multiplier,
                      CASE WHEN ua.user_id IS NOT NULL THEN 1 ELSE 0 END as unlocked
               FROM achievements a
               LEFT JOIN user_achievements ua ON a.achievement_id = ua.achievement_id 
                   AND ua.user_id = ?
               ORDER BY a.requirement_count""",
            (user_id,)
        )
        
        achievements = []
        for row in rows:
            achievements.append({
                "id": row[0],
                "code": row[1],
                "name": row[2],
                "description": row[3],
                "icon": row[4],
                "requirement_type": row[5],
                "requirement_count": row[6],
                "reward_coins": row[7],
                "reward_multiplier": row[8],
                "unlocked": bool(row[9])
            })
        
        return achievements
    
    async def check_achievements(self, user_id: int) -> List[Dict]:
        """Проверяет и выдает новые достижения"""
        user = await self.get_user(user_id)
        if not user:
            return []
        
        new_achievements = []
        
        # Получаем все достижения
        all_achievements = await self.fetchall(
            "SELECT * FROM achievements"
        )
        
        for ach in all_achievements:
            ach_id, code, name, desc, icon, req_type, req_count, reward_coins, reward_mult = ach[:9]
            
            # Проверяем уже получено ли
            exists = await self.fetchone(
                "SELECT 1 FROM user_achievements WHERE user_id = ? AND achievement_id = ?",
                (user_id, ach_id)
            )
            if exists:
                continue
            
            # Проверяем условие
            unlocked = False
            if req_type == 'harvest' and user['total_harvested'] >= req_count:
                unlocked = True
            elif req_type == 'earn' and user['total_earned'] >= req_count:
                unlocked = True
            elif req_type == 'plant' and user['total_planted'] >= req_count:
                unlocked = True
            elif req_type == 'prestige' and user['prestige_level'] >= req_count:
                unlocked = True
            
            if unlocked:
                # Выдаем достижение
                await self.execute(
                    "INSERT INTO user_achievements (user_id, achievement_id) VALUES (?, ?)",
                    (user_id, ach_id), commit=True
                )
                
                # Выдаем награду
                if reward_coins > 0:
                    await self.update_balance(user_id, reward_coins)
                
                if reward_mult > 0:
                    new_mult = user['prestige_multiplier'] + reward_mult
                    await self.execute(
                        "UPDATE users SET prestige_multiplier = ? WHERE user_id = ?",
                        (new_mult, user_id), commit=True
                    )
                
                new_achievements.append({
                    "name": name,
                    "icon": icon,
                    "reward_coins": reward_coins,
                    "reward_multiplier": reward_mult
                })
        
        return new_achievements
    
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
    
    async def init_from_sql(self, sql_file: str):
        """Выполняет SQL скрипт инициализации"""
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

    