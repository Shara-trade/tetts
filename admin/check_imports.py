#!/usr/bin/env python3
"""Диагностика импортов для админ-панели"""

import sys
import os

print("Python version:", sys.version)
print("Current directory:", os.getcwd())
print("Script directory:", os.path.dirname(os.path.abspath(__file__)))
print("sys.path:", sys.path[:3])

# Добавляем родительскую директорию
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)
print("Added to path:", parent_dir)

# Пробуем импортировать
try:
    from admin_panel_full import router as admin_router
    print("OK: admin_panel_full imported successfully")
    print("Router handlers count:", len(admin_router.callback_query.handlers) + len(admin_router.message.handlers))
except Exception as e:
    print(f"ERROR importing admin_panel_full: {e}")
    import traceback
    traceback.print_exc()
