# ================= CASINO SETTINGS =================
# Change these, save, then restart the bot.

# ---------- server ----------
GUILD_ID = None           # your server's ID (right-click server icon > Copy Server ID). Makes commands show up instantly
CASINO_CHANNELS = []      # channel IDs where games work, e.g. [123456789012345678]. Empty = everywhere
                          # (admins can also use /casino channel add in Discord)

# ---------- money ----------
STARTING_BALANCE = 1000   # coins a new player starts with
DAILY_AMOUNT = 200        # /daily
DAILY_STREAK_BONUS = 50   # extra per day of streak (up to 7 days in a row)
WEEKLY_AMOUNT = 1000      # /weekly
MIN_BET = 10
MAX_BET = None            # None = no limit
GAME_TIMEOUT = 60         # seconds before an untouched game ends by itself

# ---------- role shop (roles are created automatically) ----------
SHOP = [
    {"name": "🍀 Lucky Rookie",  "price": 1500,   "color": 0x2ECC71},
    {"name": "🎲 High Roller",   "price": 5000,   "color": 0x3498DB},
    {"name": "💎 Diamond Hands", "price": 15000,  "color": 0x9B59B6},
    {"name": "👑 Casino King",   "price": 50000,  "color": 0xF1C40F},
    {"name": "🪓 Guillotine Survivor", "price": 25000, "color": 0x992D22},
]

# ---------- guillotine ----------
GUILLOTINE_PUNISHMENT = "ban"   # "ban" (the original), "kick" or "timeout"
GUILLOTINE_TIMEOUT_MINUTES = 10 # only for "timeout"
GUILLOTINE_REWARD = 500         # coins for surviving
GUILLOTINE_SIDE_BET = 100       # what the crowd bets on "lives" / "dies" (pays double)

# ---------- other games ----------
SCRATCH_PRICE = 100       # one scratch card
ROB = True                # /rob on or off
ROB_CHANCE = 0.40         # chance a robbery works
ROB_COOLDOWN_MINUTES = 60
DARE_REWARD = 50          # coins for doing a dare

# ---------- role roller ----------
REROLL_SKIP_PRICE = 500   # coins to /reroll right away when you're on cooldown (0 = can't skip)
