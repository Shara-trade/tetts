"""
Общие утилиты для Lazy Farmer Bot
Вспомогательные функции, используемые в разных модулях
"""

import logging
from typing import Optional, Dict, Any, List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from admin.constants import ROLES, TEXT_IN_DEVELOPMENT


logger = logging.getLogger(__name__)


# ==================== АДМИН-ФУНКЦИИ ====================

async def check_admin_access(user_id: int) -> Optional[str]:
    """
    Проверяет права администратора
    
    Args:
        user_id: ID пользователя
        
    Returns:
        Роль ('creator', 'admin', 'moderator') или None
    """
    try:
        from admin.database import get_database
        db = await get_database()
        role = await db.get_admin_role(user_id)
        return role
    except Exception as e:
        logger.error(f"Error checking admin access for {user_id}: {e}")
        return None


def get_role_emoji(role: str) -> str:
    """Получить эмодзи для роли"""
    return ROLES.get(role, {}).get('emoji', '❓')


def get_role_name(role: str) -> str:
    """Получить название роли"""
    return ROLES.get(role, {}).get('name', 'Неизвестно')


def get_role_level(role: str) -> int:
    """Получить уровень доступа роли (для сравнения)"""
    return ROLES.get(role, {}).get('level', 0)


async def require_admin(user_id: int, min_role: str = 'moderator') -> bool:
    """
    Проверяет что пользователь админ с нужным уровнем
    
    Args:
        user_id: ID пользователя
        min_role: Минимальная требуемая роль
        
    Returns:
        True если есть доступ, False если нет
    """
    role = await check_admin_access(user_id)
    if not role:
        return False
    
    user_level = get_role_level(role)
    required_level = get_role_level(min_role)
    
    return user_level >= required_level


# ==================== ЛОГИРОВАНИЕ ====================

async def log_admin_action(
    admin_id: int,
    action: str,
    target_id: int = None,
    target_entity: str = None,
    details: Dict[str, Any] = None
) -> bool:
    """
    Логирует действие администратора
    
    Args:
        admin_id: ID админа
        action: Тип действия
        target_id: ID целевого пользователя (если есть)
        target_entity: ID/код сущности (если есть)
        details: Дополнительные детали
        
    Returns:
        True если успешно, False если ошибка
    """
    try:
        from admin.database import get_database
        import json
        
        db = await get_database()
        
        # Ограничиваем размер details
        details_str = None
        if details:
            try:
                details_str = json.dumps(details, ensure_ascii=False)[:1000]
            except:
                details_str = str(details)[:1000]
        
        await db.log_admin_action(
            admin_id,
            action,
            target_user_id=target_id,
            target_entity_id=target_entity,
            details=details_str
        )
        return True
    except Exception as e:
        logger.error(f"Error logging admin action: {e}")
        return False


# ==================== КЛАВИАТУРЫ ====================

def get_back_button(callback_data: str, text: str = "🔙 Назад") -> InlineKeyboardMarkup:
    """Создаёт простую клавиатуру с кнопкой назад"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=callback_data)]
    ])


def get_nav_buttons(
    back_callback: str = "admin_back_main",
    show_home: bool = True
) -> List[InlineKeyboardButton]:
    """Стандартные кнопки навигации"""
    buttons = [InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback)]
    if show_home:
        buttons.append(InlineKeyboardButton(text="🏠 Главное меню", callback_data="admin_back_main"))
    return buttons


def get_development_keyboard(back_callback: str = "back_main") -> InlineKeyboardMarkup:
    """Клавиатура для функций в разработке"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback)]
    ])


# ==================== ФОРМАТИРОВАНИЕ ====================

def format_number(num: int) -> str:
    """Форматирует число с разделителями (1,000,000)"""
    return f"{num:,}".replace(",", " ")


def format_time(seconds: int) -> str:
    """Форматирует время в читаемый вид"""
    if seconds < 60:
        return f"{seconds}с"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}м {secs}с" if secs > 0 else f"{minutes}м"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}ч {minutes}м" if minutes > 0 else f"{hours}ч"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f"{days}д {hours}ч" if hours > 0 else f"{days}д"


def format_datetime(dt_str: str) -> str:
    """Форматирует дату-время из строки БД"""
    if not dt_str:
        return "Неизвестно"
    
    try:
        # Обрабатываем разные форматы
        if 'T' in dt_str:
            dt_str = dt_str.replace('T', ' ')
        if '.' in dt_str:
            dt_str = dt_str.split('.')[0]
        if 'Z' in dt_str:
            dt_str = dt_str.replace('Z', '')
        
        # Оставляем только дату и часы:минуты
        parts = dt_str.split(' ')
        if len(parts) == 2:
            date_part = parts[0]
            time_part = parts[1][:5] if len(parts[1]) >= 5 else parts[1]
            return f"{date_part} {time_part}"
        
        return dt_str[:16]
    except:
        return dt_str


# ==================== ВАЛИДАЦИЯ ====================

def validate_username(username: str) -> bool:
    """Проверяет валидность username"""
    if not username:
        return False
    username = username.lower().replace('@', '')
    return 3 <= len(username) <= 32 and username.replace('_', '').isalnum()


def validate_promo_code(code: str) -> bool:
    """Проверяет валидность промокода"""
    if not code:
        return False
    code = code.upper()
    return 3 <= len(code) <= 20 and code.replace('_', '').isalnum()


def validate_achievement_id(ach_id: str) -> bool:
    """Проверяет валидность ID достижения"""
    if not ach_id:
        return False
    ach_id = ach_id.lower()
    return 3 <= len(ach_id) <= 50 and ach_id.replace('_', '').isalnum()


# ==================== БЕЗОПАСНОСТЬ ====================

def sanitize_input(text: str, max_length: int = 500) -> str:
    """Очищает пользовательский ввод"""
    if not text:
        return ""
    
    # Удаляем потенциально опасные символы
    text = text.replace('<', '&lt;').replace('>', '&gt;')
    
    # Ограничиваем длину
    return text[:max_length].strip()


def escape_html(text: str) -> str:
    """Экранирует HTML-теги"""
    if not text:
        return ""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


# ==================== ДЕКОРАТОРЫ ====================

def admin_required(min_role: str = 'moderator'):
    """
    Декоратор для проверки прав админа
    
    Usage:
        @admin_required('admin')
        async def handler(callback: CallbackQuery):
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Находим user_id в аргументах
            user_id = None
            for arg in args:
                if hasattr(arg, 'from_user'):
                    user_id = arg.from_user.id
                    break
            
            if not user_id:
                return
            
            if not await require_admin(user_id, min_role):
                # Находим объект для ответа
                for arg in args:
                    if hasattr(arg, 'answer'):
                        await arg.answer("⛔ Нет доступа!", show_alert=True)
                        return
                return
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator
