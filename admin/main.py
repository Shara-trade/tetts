import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from dotenv import load_dotenv
import os

from handlers import router as player_router
from admin_panel_full import router as admin_router
from achievements_admin import router as achievements_admin_router
from database import get_database

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
    """Фоновая задача для отправки уведомлений"""
    db = await get_database()
    
    while True:
        try:
            # Проверяем готовые грядки и создаем уведомления
            rows = await db.fetchall(
                """SELECT DISTINCT p.user_id FROM plots p
                   WHERE p.status = 'ready' 
                   AND p.user_id NOT IN (
                       SELECT user_id FROM notifications 
                       WHERE type = 'harvest_ready' AND sent = 0
                   )"""
            )
            
            for row in rows:
                user_id = row[0]
                await db.add_notification(
                    user_id, 
                    'harvest_ready', 
                    '🌾 Твой урожай созрел! Заходи на ферму и собирай!'
                )
            
            # Проверяем ежедневные бонусы (12+ часов)
            rows = await db.fetchall(
                """SELECT ud.user_id FROM user_daily ud
                   JOIN users u ON ud.user_id = u.user_id
                   WHERE ud.last_claim_date < date('now', '-12 hours')
                   AND u.last_activity < datetime('now', '-12 hours')"""
            )
            
            for row in rows:
                user_id = row[0]
                await db.add_notification(
                    user_id,
                    'daily_bonus',
                    '🎁 Не забудь забрать ежедневный бонус! Ты давно не заходил(а)!'
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
    db = await get_database()
    await db.init_from_sql("data/init_db.sql")
    
    # Установка команд
    await set_commands(bot)
    
    # Запускаем фоновую задачу уведомлений
    asyncio.create_task(notification_worker(bot))
    
    try:
        await dp.start_polling(bot)
    finally:
        # Закрываем соединение с БД при завершении
        await db.close()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
