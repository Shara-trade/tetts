"""
Конфигурация Lazy Farmer Bot
Настройки игры, баланс, уровни
"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class GameConfig:
    """Основные настройки игры"""
    
    # Начальные ресурсы
    start_balance: int = 100
    start_gems: int = 0
    start_plots: int = 3
    
    # Грядки
    max_plots_base: int = 6
    max_plots_per_prestige: int = 1
    plot_price_base: int = 500
    plot_price_multiplier: float = 1.5
    
    # Престиж
    prestige_cost_base: int = 100_000
    prestige_cost_multiplier: float = 2.0
    prestige_multiplier_per_level: float = 0.1
    
    # Фермеры
    prestige_for_farmers: int = 10
    farmer_work_interval_min: int = 120  # секунд
    
    # Улучшения
    prestige_for_upgrades: int = 5
    
    # Интервалы уведомлений
    notification_check_interval: int = 300  # 5 минут
    farmer_check_interval: int = 120  # 2 минуты
    
    # Переводы
    transfer_fee_percent: int = 5
    transfer_min_amount: int = 10
    transfer_daily_limit_base: int = 10_000
    
    # Ежедневный бонус
    daily_bonus_base: int = 50
    daily_bonus_streak_multiplier: float = 1.5
    daily_bonus_max_streak: int = 30
    daily_bonus_gems_chance: float = 0.1  # 10% шанс получить кристаллы


@dataclass
class AdminConfig:
    """Настройки админ-панели"""
    
    # Лимиты
    max_broadcast_length: int = 4000
    max_promo_code_length: int = 20
    max_achievement_name_length: int = 50
    max_achievement_desc_length: int = 200
    
    # Пагинация
    players_per_page: int = 10
    achievements_per_page: int = 5
    items_per_page: int = 8
    
    # Логи
    max_log_entries: int = 100
    log_retention_days: int = 30


@dataclass  
class BalanceConfig:
    """Настройки баланса экономики"""
    
    # Множители дохода
    harvest_base_multiplier: float = 1.0
    fertilizer_speed_bonus: float = 0.5  # 50% ускорение
    fertilizer_income_bonus: float = 0.25  # 25% бонус к доходу
    
    # Цены на семена (базовые)
    seed_prices: Dict[str, int] = None
    
    # Время роста (в секундах)
    growth_times: Dict[str, int] = None
    
    def __post_init__(self):
        if self.seed_prices is None:
            self.seed_prices = {
                'wheat': 50,
                'carrot': 100,
                'potato': 200,
                'corn': 400,
                'tomato': 800,
                'strawberry': 1500,
                'sunflower': 3000,
                'rose': 5000,
            }
        
        if self.growth_times is None:
            self.growth_times = {
                'wheat': 60,      # 1 минута
                'carrot': 120,    # 2 минуты
                'potato': 180,    # 3 минуты
                'corn': 300,      # 5 минут
                'tomato': 480,    # 8 минут
                'strawberry': 720, # 12 минут
                'sunflower': 1200, # 20 минут
                'rose': 1800,     # 30 минут
            }


# Глобальные экземпляры конфигурации
GAME_CONFIG = GameConfig()
ADMIN_CONFIG = AdminConfig()
BALANCE_CONFIG = BalanceConfig()


# Функции для получения значений
def get_plot_price(current_plots: int, prestige_level: int = 1) -> int:
    """Рассчитать цену следующей грядки"""
    base = GAME_CONFIG.plot_price_base
    multiplier = GAME_CONFIG.plot_price_multiplier
    
    # Скидка от престижа
    prestige_discount = min(0.5, prestige_level * 0.02)  # до 50% скидки
    
    price = int(base * (multiplier ** current_plots) * (1 - prestige_discount))
    return max(100, price)  # Минимум 100 монет


def get_max_plots(prestige_level: int = 1) -> int:
    """Рассчитать максимальное количество грядок"""
    base = GAME_CONFIG.max_plots_base
    bonus = GAME_CONFIG.max_plots_per_prestige * (prestige_level - 1)
    return base + bonus


def get_prestige_cost(current_level: int) -> int:
    """Рассчитать стоимость следующего уровня престижа"""
    base = GAME_CONFIG.prestige_cost_base
    multiplier = GAME_CONFIG.prestige_cost_multiplier
    return int(base * (multiplier ** (current_level - 1)))


def get_prestige_multiplier(level: int) -> float:
    """Рассчитать множитель престижа"""
    return 1.0 + (level - 1) * GAME_CONFIG.prestige_multiplier_per_level


def get_transfer_limit(prestige_level: int) -> int:
    """Рассчитать дневной лимит переводов"""
    base = GAME_CONFIG.transfer_daily_limit_base
    bonus = prestige_level * 1000
    return base + bonus
