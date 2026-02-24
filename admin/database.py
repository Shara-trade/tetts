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
        """
        Инициализирует базу данных:
        1. Проверяет существование файла БД
        2. Если БД не существует - создаёт все таблицы из SQL файла
        
        Args:
            sql_file_path: Путь к SQL файлу со схемой БД
            
        Returns:
            True если инициализация прошла успешно
        """
        import os
        
        # Проверяем существование файла БД
        db_exists = os.path.exists(self.db_path)
        
        # Устанавливаем соединение
        db = await self.connect()
        
        if not db_exists:
            logging.info(f"База данных {self.db_path} не найдена. Создаём новую...")
            
            # Проверяем существование SQL файла
            if not os.path.exists(sql_file_path):
                logging.error(f"SQL файл {sql_file_path} не найден!")
                return False
    
            try:
                # Читаем SQL файл
                with open(sql_file_path, 'r', encoding='utf-8') as f:
                    sql_script = f.read()
                
                # Выполняем SQL скрипт
                await db.executescript(sql_script)
                await db.commit()
                
                logging.info(f"✅ База данных успешно создана из {sql_file_path}")
                return True
            except Exception as e:
                logging.error(f"❌ Ошибка при создании БД: {e}")
                return False
        else:
            logging.info(f"✅ База данных {self.db_path} уже существует")
            return True
    
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
            # Проверяем наличие поля settings (индекс 18 после всех основных полей)
            settings = {}
            if len(row) > 18 and row[18]:
                try:
                    settings = json.loads(row[18])
                except (json.JSONDecodeError, TypeError):
                    settings = {}
        
            return {
                "user_id": row[0], "username": row[1], "first_name": row[2],
                "balance": row[3], "gems": row[4],
                "prestige_level": row[5], "prestige_multiplier": row[6],
                "city_level": row[7], "total_harvested": row[8],
                "total_planted": row[9], "total_earned": row[10], "total_spent": row[11],
                "joined_date": row[12] if len(row) > 12 else None,
                "last_activity": row[13] if len(row) > 13 else None,
                "daily_streak": row[17] if len(row) > 17 else 0,
                "settings": settings,
                "selected_achievements": []
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
        
        items = []
        for r in rows:
            items.append({
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
                "is_active": r[11] if len(r) > 11 else True,
                "sort_order": r[12] if len(r) > 12 else 0
            })
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
        ach = await self.get_
