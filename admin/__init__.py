"""
Lazy Farmer Bot - Admin Package
Пакет администрирования и игровых модулей
"""

import sys
import os

# Добавляем путь к корневой директории для корректных импортов
_root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root_path not in sys.path:
    sys.path.insert(0, _root_path)

# Экспортируем основные модули
from admin.states import (
    PlayerStates,
    AdminStates,
    AchievementCreateStates,
    AchievementEditStates,
    AchievementGiveStates
)

__all__ = [
    'PlayerStates',
    'AdminStates', 
    'AchievementCreateStates',
    'AchievementEditStates',
    'AchievementGiveStates'
]
