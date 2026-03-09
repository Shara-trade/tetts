import asyncio
import logging
import os
import sys

# Добавляем путь к admin модулю для корректных импортов
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from dotenv import load_dotenv

# Импорты с полными путями
from admin.handlers import router as player_router
from admin.admin_panel_full import router as admin_router
from admin.achievements_admin import router as achievements_admin_router
from admin.database import get_database

load_dotenv()
    
logging.basicConfig(level=logging.INFO)

async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Начать игру / Главное меню"),
        BotCommand(command="help", description="Помощь по игре"),
        BotCommand(command="stats", description="Твоя статистика"),
        BotCommand(command="top", description="Топ-10 игроков"),
        BotCommand(command="promo", description="Активировать промокод"),
        BotCommand(command="admin", description="Админ-панель"),
    ]
    await bot.set_my_commands(commands)

async def notification_worker(bot: Bot):
    """Фоновая задача для отправки уведомлений с batch-оптимизацией"""
    db = await get_database()
    
    while True:
        try:
            # Batch-вставка уведомлений о готовых грядках
            await db.execute(
                """INSERT INTO notifications (user_id, type, message)
                   SELECT DISTINCT p.user_id, 'harvest_ready', 
                   '🌾 Твой урожай созрел! Заходи на ферму и собирай!'
                   FROM plots p
                   WHERE p.status = 'ready' 
                   AND p.user_id NOT IN (
                       SELECT user_id FROM notifications 
                       WHERE type = 'harvest_ready' AND sent = 0
                   )"""
            )
            
            # Batch-вставка уведомлений о бонусах
            await db.execute(
                """INSERT INTO notifications (user_id, type, message)
                   SELECT ud.user_id, 'daily_bonus', 
                   '🎁 Не забудь забрать ежедневный бонус! Ты давно не заходил(а)!'
                   FROM user_daily ud
                   JOIN users u ON ud.user_id = u.user_id
                   WHERE ud.last_claim_date < datetime('now', '-12 hours')
                   AND u.last_activity < datetime('now', '-12 hours')"""
            )
            
            # Отправляем неотправленные уведомления
            notifications = await db.get_pending_notifications()
            for notif in notifications:
                try:
                    await bot.send_message(
                        notif['user_id'],
                        f"🔔 <b>Уведомление</b>\n\n{notif['message']}",
                        parse_mode="HTML"
                    )
                    await db.mark_notification_sent(notif['id'])
                except Exception as e:
                    logging.error(f"Failed to send notification: {e}")
            
        except Exception as e:
            logging.error(f"Notification worker error: {e}")
        
        # Проверяем каждые 5 минут
        await asyncio.sleep(300)


async def farmer_worker(bot: Bot):
    """Фоновая задача для автоматической работы фермеров (ТЗ v4.0 п.11)"""
    db = await get_database()
    
    while True:
        try:
            # Получаем всех активных фермеров
            farmers = await db.get_all_active_farmers()
            
            for farmer in farmers:
                user_id = farmer.get('user_id')
                farmer_id = farmer.get('farmer_id')
                last_work = farmer.get('last_work')
                interval = farmer.get('work_interval_seconds', 300)
                
                # Проверяем интервал работы
                from datetime import datetime
                if last_work:
                    if isinstance(last_work, str):
                        last_work = datetime.fromisoformat(last_work.replace('Z', '+00:00'))
                    
                    time_since_last = (datetime.now() - last_work).total_seconds()
                    
                    if time_since_last < interval:
                        continue  # Рано для работы
                
                # Выполняем работу фермера
                result = await db.farmer_work(user_id)
                
                if result.get('success') and not result.get('skipped'):
                    planted = result.get('planted', 0)
                    harvested = result.get('harvested', 0)
                    earned = result.get('earned', 0)
                    salary = result.get('salary', 0)
                    
                    # Логируем работу
                    logging.info(
                        f"Farmer {farmer_id} for user {user_id}: "
                        f"planted={planted}, harvested={harvested}, "
                        f"earned={earned}, salary={salary}"
                    )
                    
                    # Если была значительная работа, отправляем уведомление
                    if harvested > 0 or planted > 0:
                        try:
                            # Получаем информацию о фермере для имени
                            farmer_info = await db.get_user_farmer(user_id)
                            if farmer_info:
                                icon = farmer_info.get('type_icon', '👤')
                                name = farmer_info.get('type_name', 'Фермер')
                                
                                text_lines = [
                                    f"{icon} <b>ОТЧЁТ ФЕРМЕРА</b>",
                                    "",
                                ]
                                
                                if harvested > 0:
                                    text_lines.append(f"🌾 Собрано: {harvested} урожаев")
                                if planted > 0:
                                    text_lines.append(f"🌱 Посажено: {planted} растений")
                                if earned > 0:
                                    text_lines.append(f"💰 Заработано: {earned:,}🪙")
                                if salary > 0:
                                    text_lines.append(f"💸 Зарплата: -{salary:,}🪙")
                                
                                net = earned - salary
                                if net > 0:
                                    text_lines.append(f"\n✅ Чистый доход: +{net:,}🪙")
                                
                                # Отправляем только если пользователь не в режиме "не беспокоить"
                                user = await db.get_user(user_id)
                                if user:
                                    settings = user.get('settings', {})
                                    if settings.get('farmer_notifications', True):
                                        await bot.send_message(
                                            user_id,
                                            "\n".join(text_lines),
                                            parse_mode="HTML"
                                        )
                        except Exception as e:
                            logging.error(f"Failed to send farmer report to {user_id}: {e}")
                
        except Exception as e:
            logging.error(f"Farmer worker error: {e}")
        
        # Проверяем каждые 2 минуты (минимальный интервал работы профи фермера)
        await asyncio.sleep(120)

async def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("Ошибка: BOT_TOKEN не найден!")
        print("Создайте файл .env и добавьте: BOT_TOKEN=your_token_here")
        return
    
    bot = Bot(token=token)
    dp = Dispatcher(storage=MemoryStorage())
    
    dp.include_router(player_router)
    dp.include_router(admin_router)
    dp.include_router(achievements_admin_router)
    
    # Инициализация БД (синглтон)
    print("🔧 Шаг 1: Подключаемся к БД...")
    db = await get_database()
    print("🔧 Шаг 2: Создаём таблицы...")
    await db.init_db("data/init_db.sql")
    print("✅ Шаг 3: БД готова!")
    
    # Установка команд
    await set_commands(bot)
    
    # Запускаем фоновую задачу уведомлений
    asyncio.create_task(notification_worker(bot))
    
    # Запускаем фоновую задачу фермеров
    asyncio.create_task(farmer_worker(bot))
    
    try:
        await dp.start_polling(bot)
    finally:
        # Закрываем соединение с БД при завершении
        await db.close()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
