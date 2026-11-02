"""Reads settings.py and fills in anything missing."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    import settings as _s
except ImportError:
    _s = None
    print("⚠️ settings.py not found, using defaults")


def _get(name, default):
    return getattr(_s, name, default)


GUILD_ID = _get("GUILD_ID", None)
CASINO_CHANNELS = [int(c) for c in _get("CASINO_CHANNELS", [])]

STARTING_BALANCE = _get("STARTING_BALANCE", 1000)
DAILY_AMOUNT = _get("DAILY_AMOUNT", 200)
DAILY_STREAK_BONUS = _get("DAILY_STREAK_BONUS", 50)
WEEKLY_AMOUNT = _get("WEEKLY_AMOUNT", 1000)
MIN_BET = _get("MIN_BET", 10)
MAX_BET = _get("MAX_BET", None)
GAME_TIMEOUT = _get("GAME_TIMEOUT", 60)

SHOP = _get("SHOP", [
    {"name": "🍀 Lucky Rookie", "price": 1500, "color": 0x2ECC71},
    {"name": "🎲 High Roller", "price": 5000, "color": 0x3498DB},
    {"name": "💎 Diamond Hands", "price": 15000, "color": 0x9B59B6},
    {"name": "👑 Casino King", "price": 50000, "color": 0xF1C40F},
])

GUILLOTINE_PUNISHMENT = str(_get("GUILLOTINE_PUNISHMENT", "ban")).lower()
GUILLOTINE_TIMEOUT_MINUTES = _get("GUILLOTINE_TIMEOUT_MINUTES", 10)
GUILLOTINE_REWARD = _get("GUILLOTINE_REWARD", 500)
GUILLOTINE_SIDE_BET = _get("GUILLOTINE_SIDE_BET", 100)

SCRATCH_PRICE = _get("SCRATCH_PRICE", 100)
ROB = _get("ROB", True)
ROB_CHANCE = _get("ROB_CHANCE", 0.40)
ROB_COOLDOWN_MINUTES = _get("ROB_COOLDOWN_MINUTES", 60)
DARE_REWARD = _get("DARE_REWARD", 50)
REROLL_SKIP_PRICE = _get("REROLL_SKIP_PRICE", 500)

DATA_FILE = os.path.join(ROOT, "casino.json")
OLD_FILES = [os.path.join(ROOT, "data.json"), os.path.join(ROOT, "graveyard.json"), os.path.join(ROOT, "roles.json")]
PROMPTS_FOLDER = os.path.join(ROOT, "prompts")
