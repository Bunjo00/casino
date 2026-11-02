"""Shared bits: coin formatting, bets, the casino-channel check, 'play again' buttons."""
import time

import discord
from discord import app_commands

from . import config
from .bank import bank

GREEN = discord.Color.green()
RED = discord.Color.red()
GOLD = discord.Color.gold()
GREY = discord.Color.light_grey()
BLUE = discord.Color.blurple()
PURPLE = discord.Color.purple()
FELT = discord.Color.dark_green()


def coins(n):
    return f"🪙 {int(n):,}"


class CasinoError(app_commands.CheckFailure):
    """A friendly message for the player (shown only to them)."""


def games_only():
    """Games only work in the casino channel(s), if any are set."""
    async def check(interaction):
        if interaction.guild is None:
            raise CasinoError("🎰 Play in a server, not in DMs!")
        allowed = bank.channels(interaction.guild.id)
        channel = interaction.channel
        if allowed and interaction.channel_id not in allowed and getattr(channel, "parent_id", None) not in allowed:
            raise CasinoError("🎰 The casino is over in " + ", ".join(f"<#{c}>" for c in sorted(allowed)))
        return True
    return app_commands.check(check)


# ---------- one game at a time per person ----------
_busy = {}


def busy(uid):
    return time.time() - _busy.get(uid, 0) < 600  # (forgotten after 10 minutes, just in case)


def set_busy(uid):
    _busy[uid] = time.time()


def free(uid):
    _busy.pop(uid, None)


# ---------- bets ----------
def parse_bet(text, balance):
    t = str(text or "").lower().replace(",", "").replace("🪙", "").strip()
    if t in ("all", "max", "allin", "all in", "everything"):
        return balance
    if t == "half":
        return balance // 2
    mult = 1
    if t.endswith("k"):
        mult, t = 1000, t[:-1]
    elif t.endswith("m"):
        mult, t = 1_000_000, t[:-1]
    try:
        return int(float(t) * mult)
    except ValueError:
        return None


async def oops(interaction, text):
    """A message only that person sees."""
    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=True)
    else:
        await interaction.response.send_message(text, ephemeral=True)


async def take_bet(interaction, text, game=True, minimum=None):
    """Checks the bet and takes it. Tells them what's wrong and returns None if it's no good."""
    uid = interaction.user.id
    if game and busy(uid):
        await oops(interaction, "⏳ Finish your other game first!")
        return None
    balance = bank.balance(uid)
    bet = parse_bet(text, balance)
    minimum = config.MIN_BET if minimum is None else minimum
    if bet is None:
        await oops(interaction, f"🤨 `{text}` isn't a bet. Try `100`, `5k`, `half` or `all`.")
    elif bet < minimum:
        await oops(interaction, f"🪙 The minimum bet is {coins(minimum)}." + (" You're broke, try `/daily`!" if balance < minimum else ""))
    elif config.MAX_BET and bet > config.MAX_BET:
        await oops(interaction, f"🛑 The maximum bet is {coins(config.MAX_BET)}.")
    elif not bank.take(uid, bet):
        await oops(interaction, f"💸 You only have {coins(balance)}. Bet less or grab your `/daily`.")
    else:
        if game:
            set_busy(uid)
        return bet
    return None


async def send(interaction, edit=False, **kwargs):
    """Sends a new message, or replaces the clicked one (edit=True). Returns the message."""
    if edit:
        await interaction.response.edit_message(**kwargs)
        return interaction.message
    await interaction.response.send_message(**kwargs)
    return await interaction.original_response()


def balance_footer(embed, uid, extra=""):
    embed.set_footer(text=f"{extra}Balance: {bank.balance(uid):,} coins")
    return embed


class AgainView(discord.ui.View):
    """A 'play again' button under a finished game. start(interaction, bet_text, edit=True) -> bool"""

    def __init__(self, player, bet, start, label="Play again"):
        super().__init__(timeout=120)
        self.player, self.start, self.message = player, start, None
        button = discord.ui.Button(label=f"{label} · {bet:,}", emoji="🔁", style=discord.ButtonStyle.secondary)
        button.callback = self._again
        self.bet = bet
        self.add_item(button)

    async def interaction_check(self, interaction):
        if interaction.user.id != self.player.id:
            await oops(interaction, "🙅 Not your game! Start your own.")
            return False
        return True

    async def _again(self, interaction):
        if await self.start(interaction, str(self.bet), edit=True):
            self.stop()

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.HTTPException:
                pass


class PlayerView(discord.ui.View):
    """Buttons only the player can press."""

    def __init__(self, player, timeout=None):
        super().__init__(timeout=timeout or config.GAME_TIMEOUT)
        self.player = player
        self.message = None

    async def interaction_check(self, interaction):
        if interaction.user.id != self.player.id:
            await oops(interaction, "🙅 This isn't your game! Start your own.")
            return False
        return True

    def disable_all(self):
        for item in self.children:
            item.disabled = True
