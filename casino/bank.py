"""Everyone's coins and stats, kept in memory and saved to casino.json a few seconds after any change.

Old files from the separate bots (data.json from blackjack, graveyard.json from the guillotine)
are imported automatically the first time.
"""
import asyncio
import json
import os
import time

from . import config

DAY = 24 * 3600
NEW_USER = {"balance": None, "last_daily": 0, "streak": 0, "last_weekly": 0, "last_rob": 0,
            "games": 0, "wins": 0, "won": 0, "lost": 0, "biggest": 0}


class Bank:
    def __init__(self, path):
        self.path = path
        self.dirty = False
        self.data = {"users": {}, "graveyard": {}, "channels": {}}
        try:
            with open(path, encoding="utf-8") as f:
                self.data.update(json.load(f))
        except FileNotFoundError:
            self._import_old()
        except json.JSONDecodeError:
            backup = path + f".broken-{int(time.time())}"
            os.replace(path, backup)
            print(f"⚠️ casino.json was damaged, saved it as {backup} and started fresh")

    def _import_old(self):
        blackjack, graveyard, roles = config.OLD_FILES
        try:
            with open(blackjack, encoding="utf-8") as f:
                old = json.load(f)
            for uid, info in old.items():
                if uid.isdigit() and isinstance(info, dict):
                    self.user(uid).update(balance=info.get("balance", config.STARTING_BALANCE),
                                          last_daily=info.get("last_daily", 0))
            print(f"💰 imported {len(old)} wallets from data.json")
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        try:
            with open(graveyard, encoding="utf-8") as f:
                self.data["graveyard"] = json.load(f)
            print("⚰️ imported the graveyard from graveyard.json")
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        try:
            with open(roles, encoding="utf-8") as f:
                self.data["reroll"] = json.load(f)
            print("🎲 imported reroll roles from roles.json")
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        self.dirty = True

    # ---------- saving ----------
    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=1)
        os.replace(tmp, self.path)
        self.dirty = False

    async def autosave(self):
        while True:
            await asyncio.sleep(5)
            if self.dirty:
                try:
                    self.save()
                except Exception as e:
                    print(f"⚠️ couldn't save: {e}")

    # ---------- people ----------
    def user(self, uid):
        u = self.data["users"].setdefault(str(uid), {})
        for key, value in NEW_USER.items():
            u.setdefault(key, value)
        if u["balance"] is None:
            u["balance"] = config.STARTING_BALANCE
            self.dirty = True
        return u

    def balance(self, uid):
        return self.user(uid)["balance"]

    def add(self, uid, amount):
        self.user(uid)["balance"] += int(amount)
        self.dirty = True

    def take(self, uid, amount):
        """Takes coins. False if they don't have enough."""
        u = self.user(uid)
        if amount < 0 or u["balance"] < amount:
            return False
        u["balance"] -= int(amount)
        self.dirty = True
        return True

    def result(self, uid, bet, payout):
        """Records a finished game (the payout itself must already be added)."""
        u = self.user(uid)
        u["games"] += 1
        if payout > bet:
            u["wins"] += 1
            u["won"] += payout - bet
            u["biggest"] = max(u["biggest"], payout - bet)
        elif payout < bet:
            u["lost"] += bet - payout
        self.dirty = True

    def claim(self, uid, kind):
        """daily/weekly. Returns (seconds left, coins given, streak)."""
        u = self.user(uid)
        now = time.time()
        if kind == "weekly":
            left = int(u["last_weekly"] + 7 * DAY - now)
            if left > 0:
                return left, 0, 0
            u["last_weekly"] = now
            amount, streak = config.WEEKLY_AMOUNT, 0
        else:
            left = int(u["last_daily"] + DAY - now)
            if left > 0:
                return left, 0, u["streak"]
            streak = u["streak"] + 1 if now - u["last_daily"] < 2 * DAY else 1
            u["streak"], u["last_daily"] = streak, now
            amount = config.DAILY_AMOUNT + config.DAILY_STREAK_BONUS * (min(streak, 7) - 1)
        u["balance"] += amount
        self.dirty = True
        return 0, amount, streak

    def top(self, key="balance", n=10):
        rows = [(uid, self.user(uid)) for uid in list(self.data["users"])]
        return sorted(rows, key=lambda r: r[1].get(key, 0), reverse=True)[:n]

    def rank(self, uid):
        order = [r[0] for r in self.top("balance", len(self.data["users"]))]
        return order.index(str(uid)) + 1 if str(uid) in order else None

    # ---------- guillotine ----------
    def grave(self, guild_id, user, died):
        g = self.data["graveyard"].setdefault(str(guild_id), {})
        u = g.setdefault(str(user.id), {"name": user.name, "deaths": 0, "survivals": 0})
        u["name"] = user.name
        u["deaths" if died else "survivals"] += 1
        self.dirty = True
        return u

    # ---------- casino channels ----------
    def channels(self, guild_id):
        return set(config.CASINO_CHANNELS) | set(self.data["channels"].get(str(guild_id), []))

    def set_channel(self, guild_id, channel_id, on):
        ids = set(self.data["channels"].get(str(guild_id), []))
        (ids.add if on else ids.discard)(channel_id)
        self.data["channels"][str(guild_id)] = sorted(ids)
        self.dirty = True


bank = Bank(config.DATA_FILE)
