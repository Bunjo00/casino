"""🎰 Arcade games: slots, roulette wheel, coinflip, duels, higher or lower, crash, mines, scratch cards, rob."""
import asyncio
import math
import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..bank import bank
from ..ui import (BLUE, GOLD, GREEN, GREY, PURPLE, RED, AgainView, PlayerView, balance_footer, busy, coins, free,
                  games_only, oops, send, set_busy, take_bet)

BET = "Coins to bet: 100, 5k, half or all"


def finish(uid, bet, pay):
    bank.add(uid, pay)
    bank.result(uid, bet, pay)
    free(uid)


async def show_result(interaction, edit, embed, player, bet, start_fn):
    again = AgainView(player, bet, start_fn)
    again.message = await send(interaction, edit, embed=embed, view=again)


# =====================================================================
# 🎰 SLOTS
# =====================================================================
REELS = [("🍒", 30), ("🍋", 24), ("🍇", 18), ("🔔", 12), ("⭐", 8), ("💎", 4), ("7️⃣", 2)]
THREE = {"🍒": 5, "🍋": 8, "🍇": 12, "🔔": 20, "⭐": 40, "💎": 100, "7️⃣": 300}
SYMBOLS, WEIGHTS = zip(*REELS)


def slot_payout(reel, bet):
    a, b, c = reel
    if a == b == c:
        return bet * THREE[a], f"🎉 **TRIPLE {a}!** ×{THREE[a]}"
    if a == b or b == c or a == c:
        pair = b if b in (a, c) else a
        mult = 3 if pair in ("💎", "7️⃣") else 1.1
        return int(bet * mult), f"✨ Pair of {pair} ×{mult}"
    return 0, "💨 Nothing"


async def slots_start(interaction, bet_text, edit=False):
    bet = await take_bet(interaction, bet_text)
    if bet is None:
        return False
    uid = interaction.user.id
    reel = random.choices(SYMBOLS, WEIGHTS, k=3)
    pay, line = slot_payout(reel, bet)
    finish(uid, bet, pay)

    def board(shown, spinning):
        return " │ ".join(s if i < shown else random.choice(SYMBOLS) for i, s in enumerate(reel)) + ("  🔄" if spinning else "")

    embed = discord.Embed(title="🎰 Slots", description=f"# {board(0, True)}", color=PURPLE)
    message = await send(interaction, edit, embed=embed, view=None)
    for shown in (1, 2):
        await asyncio.sleep(0.8)
        embed.description = f"# {board(shown, True)}"
        await message.edit(embed=embed)
    await asyncio.sleep(0.8)
    win = pay > bet
    embed.description = f"# {board(3, False)}\n{line}\n" + (f"**You win {coins(pay - bet)}!**" if win else
                                                             f"You get {coins(pay)} back." if pay else f"You lose {coins(bet)}.")
    embed.color = GOLD if pay >= bet * 20 else GREEN if win else GREY if pay else RED
    balance_footer(embed, uid)
    again = AgainView(interaction.user, bet, slots_start, "Spin again")
    again.message = message
    await message.edit(embed=embed, view=again)
    return True


# =====================================================================
# 🎡 ROULETTE WHEEL
# =====================================================================
RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}


def color_of(n):
    return "🟢" if n == 0 else "🔴" if n in RED_NUMBERS else "⚫"


def wheel_wins(choice, number, n):
    return {"red": n in RED_NUMBERS, "black": n != 0 and n not in RED_NUMBERS, "odd": n % 2 == 1,
            "even": n != 0 and n % 2 == 0, "low": 1 <= n <= 18, "high": n >= 19, "green": n == 0,
            "number": n == number}[choice]


def wheel_start_for(choice, number):
    async def start(interaction, bet_text, edit=False):
        bet = await take_bet(interaction, bet_text)
        if bet is None:
            return False
        uid = interaction.user.id
        n = random.randint(0, 36)
        win = wheel_wins(choice, number, n)
        mult = 36 if choice in ("number", "green") else 2
        pay = bet * mult if win else 0
        finish(uid, bet, pay)
        bet_name = f"number {number}" if choice == "number" else choice
        embed = discord.Embed(title="🎡 Roulette", description="# 🎡 spinning...", color=BLUE)
        message = await send(interaction, edit, embed=embed, view=None)
        for _ in range(3):
            await asyncio.sleep(0.7)
            fake = random.randint(0, 36)
            embed.description = f"# {color_of(fake)} {fake}  🔄"
            await message.edit(embed=embed)
        await asyncio.sleep(0.9)
        embed.description = (f"# {color_of(n)} {n}\nYou bet on **{bet_name}**.\n"
                             + (f"**You win {coins(pay - bet)}!** (×{mult})" if win else f"You lose {coins(bet)}."))
        embed.color = GOLD if win and mult > 2 else GREEN if win else RED
        balance_footer(embed, uid)
        again = AgainView(interaction.user, bet, start, "Spin again")
        again.message = message
        await message.edit(embed=embed, view=again)
        return True
    return start


# =====================================================================
# 🪙 COINFLIP + ⚔️ DUEL
# =====================================================================
def coinflip_start_for(side):
    async def start(interaction, bet_text, edit=False):
        bet = await take_bet(interaction, bet_text)
        if bet is None:
            return False
        uid = interaction.user.id
        landed = random.choice(["heads", "tails"])
        win = landed == side
        pay = int(bet * 1.95) if win else 0
        finish(uid, bet, pay)
        embed = discord.Embed(title="🪙 Coinflip", description="# 🪙 flipping...", color=BLUE)
        message = await send(interaction, edit, embed=embed, view=None)
        await asyncio.sleep(1.5)
        embed.description = (f"# {'👑 Heads' if landed == 'heads' else '🦅 Tails'}\nYou picked **{side}**. "
                             + (f"**You win {coins(pay - bet)}!**" if win else f"You lose {coins(bet)}."))
        embed.color = GREEN if win else RED
        balance_footer(embed, uid)
        again = AgainView(interaction.user, bet, start, "Flip again")
        again.message = message
        await message.edit(embed=embed, view=again)
        return True
    return start


class Duel(discord.ui.View):
    def __init__(self, challenger, opponent, bet):
        super().__init__(timeout=60)
        self.challenger, self.opponent, self.bet = challenger, opponent, bet
        self.done = False
        self.message = None

    async def interaction_check(self, interaction):
        if interaction.user.id != self.opponent.id:
            await oops(interaction, "🙅 This duel isn't for you!")
            return False
        return True

    async def _cancel(self, text):
        self.done = True
        self.stop()
        bank.add(self.challenger.id, self.bet)  # refund
        free(self.challenger.id)
        return text

    @discord.ui.button(label="Accept", emoji="⚔️", style=discord.ButtonStyle.green)
    async def accept(self, interaction, button):
        if self.done:
            return
        if busy(self.opponent.id):
            return await oops(interaction, "⏳ Finish your other game first!")
        if not bank.take(self.opponent.id, self.bet):
            return await oops(interaction, f"💸 You need {coins(self.bet)} to accept.")
        self.done = True
        self.stop()
        winner, loser = random.sample([self.challenger, self.opponent], 2)
        pot = self.bet * 2
        bank.add(winner.id, pot)
        bank.result(winner.id, self.bet, pot)
        bank.result(loser.id, self.bet, 0)
        free(self.challenger.id)
        embed = discord.Embed(title="⚔️ Duel", description=f"# 🪙 ...\n{self.challenger.mention} vs {self.opponent.mention}", color=BLUE)
        await interaction.response.edit_message(embed=embed, view=None)
        await asyncio.sleep(1.5)
        embed.description = (f"# 🏆 {winner.display_name} wins!\n{winner.mention} takes the pot of {coins(pot)}. "
                             f"{loser.mention} goes home broke-er.")
        embed.color = GOLD
        await interaction.message.edit(embed=embed)

    @discord.ui.button(label="Run away", emoji="🏃", style=discord.ButtonStyle.secondary)
    async def decline(self, interaction, button):
        if self.done:
            return
        text = await self._cancel(f"🐔 {self.opponent.mention} ran away from the duel. {self.challenger.mention} got their coins back.")
        await interaction.response.edit_message(content=text, embed=None, view=None)

    async def on_timeout(self):
        if self.done:
            return
        text = await self._cancel(f"⌛ {self.opponent.mention} didn't answer the duel. Coins refunded.")
        if self.message:
            try:
                await self.message.edit(content=text, embed=None, view=None)
            except discord.HTTPException:
                pass


# =====================================================================
# 🃏 HIGHER OR LOWER
# =====================================================================
CARD_NAMES = {1: "A", 11: "J", 12: "Q", 13: "K"}


def card(n):
    return f"`{CARD_NAMES.get(n, n)}{random.choice(['♠️', '♥️', '♦️', '♣️'])}`"


class HighLow(PlayerView):
    def __init__(self, player, bet):
        super().__init__(player)
        self.bet, self.mult, self.streak = bet, 1.0, 0
        self.current = random.randint(1, 13)
        self.history = [card(self.current)]
        self.done = False
        self.note = "Will the next card be higher or lower? (Same card = free redo)"
        self.update_buttons()

    def update_buttons(self):
        self.higher.disabled = self.current == 13
        self.lower.disabled = self.current == 1
        self.cashout.disabled = self.streak == 0
        self.higher.label = f"Higher ×{self.step('higher'):.2f}" if self.current < 13 else "Higher"
        self.lower.label = f"Lower ×{self.step('lower'):.2f}" if self.current > 1 else "Lower"
        self.cashout.label = f"Cash out {int(self.bet * self.mult):,}"

    def step(self, way):
        chance = (13 - self.current) / 12 if way == "higher" else (self.current - 1) / 12
        return 0.97 / chance if chance else 0

    def embed(self, color=BLUE):
        e = discord.Embed(title="🃏 Higher or Lower", color=color,
                          description=f"# {self.history[-1]}\n{self.note}\n\n"
                                      f"Cards: {' → '.join(self.history[-8:])}\n"
                                      f"Bet {coins(self.bet)} · Streak **{self.streak}** · ×{self.mult:.2f} = **{coins(self.bet * self.mult)}**")
        return balance_footer(e, self.player.id)

    async def guess(self, interaction, way):
        nxt = random.randint(1, 13)
        self.history.append(card(nxt))
        if nxt == self.current:
            self.note = "🤝 Same card! Guess again."
        elif (nxt > self.current) == (way == "higher"):
            self.mult *= self.step(way)
            self.streak += 1
            self.note = f"✅ Correct! Keep going or cash out."
        else:
            return await self.end(interaction, lost=True)
        self.current = nxt
        self.update_buttons()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    async def end(self, interaction=None, lost=False):
        self.done = True
        self.stop()
        pay = 0 if lost else int(self.bet * self.mult)
        finish(self.player.id, self.bet, pay)
        self.note = (f"💥 Wrong! You lose {coins(self.bet)}." if lost else
                     f"💰 Cashed out **{coins(pay)}** (+{coins(pay - self.bet)})!" if pay > self.bet else "Bet returned.")
        embed = self.embed(RED if lost else GREEN)
        again = AgainView(self.player, self.bet, highlow_start)
        if interaction:
            await interaction.response.edit_message(embed=embed, view=again)
            again.message = interaction.message
        elif self.message:
            await self.message.edit(embed=embed, view=again)
            again.message = self.message

    @discord.ui.button(label="Higher", emoji="⬆️", style=discord.ButtonStyle.green)
    async def higher(self, interaction, button):
        await self.guess(interaction, "higher")

    @discord.ui.button(label="Lower", emoji="⬇️", style=discord.ButtonStyle.red)
    async def lower(self, interaction, button):
        await self.guess(interaction, "lower")

    @discord.ui.button(label="Cash out", emoji="💰", style=discord.ButtonStyle.blurple)
    async def cashout(self, interaction, button):
        await self.end(interaction)

    async def on_timeout(self):
        if not self.done:
            await self.end()  # auto cash out


async def highlow_start(interaction, bet_text, edit=False):
    bet = await take_bet(interaction, bet_text)
    if bet is None:
        return False
    game = HighLow(interaction.user, bet)
    game.message = await send(interaction, edit, embed=game.embed(), view=game)
    return True


# =====================================================================
# 📈 CRASH
# =====================================================================
class Crash(PlayerView):
    def __init__(self, player, bet):
        super().__init__(player, timeout=180)
        self.bet, self.mult = bet, 1.0
        self.crash_at = min(100.0, max(1.0, math.floor(97 / (1 - random.random())) / 100))
        self.done = False
        self.lock = asyncio.Lock()

    def embed(self, text, color=BLUE):
        rocket = "🚀" if not self.done else "💥" if color == RED else "🪂"
        e = discord.Embed(title="📈 Crash", color=color,
                          description=f"# {rocket} ×{self.mult:.2f}\n{text}\nBet {coins(self.bet)} → **{coins(self.bet * self.mult)}**")
        return balance_footer(e, self.player.id)

    async def fly(self):
        await asyncio.sleep(1.2)
        while not self.done:
            nxt = round(self.mult * 1.12, 2)
            async with self.lock:
                if self.done:
                    return
                if nxt >= self.crash_at:
                    self.mult = self.crash_at
                    self.done = True
                    self.stop()
                    finish(self.player.id, self.bet, 0)
                    again = AgainView(self.player, self.bet, crash_start)
                    again.message = self.message
                    await self.message.edit(embed=self.embed(f"💥 **CRASHED at ×{self.crash_at:.2f}!** You lose {coins(self.bet)}.", RED),
                                            view=again)
                    return
                self.mult = nxt
                self.cashout.label = f"Cash out {int(self.bet * self.mult):,}"
                try:
                    await self.message.edit(embed=self.embed("Cash out before it crashes!"), view=self)
                except discord.HTTPException:
                    pass
            await asyncio.sleep(1.3)

    @discord.ui.button(label="Cash out", emoji="💰", style=discord.ButtonStyle.green)
    async def cashout(self, interaction, button):
        if self.done:
            return await interaction.response.defer()
        self.done = True  # (set first, so the rocket can't crash after you clicked)
        self.stop()
        pay = int(self.bet * self.mult)
        finish(self.player.id, self.bet, pay)
        again = AgainView(self.player, self.bet, crash_start)
        async with self.lock:
            await interaction.response.edit_message(
                embed=self.embed(f"🪂 Cashed out at ×{self.mult:.2f}: **+{coins(pay - self.bet)}**! "
                                 f"(it would've crashed at ×{self.crash_at:.2f})", GREEN), view=again)
        again.message = interaction.message


async def crash_start(interaction, bet_text, edit=False):
    bet = await take_bet(interaction, bet_text)
    if bet is None:
        return False
    game = Crash(interaction.user, bet)
    game.cashout.label = f"Cash out {bet:,}"
    game.message = await send(interaction, edit, embed=game.embed("Taking off..."), view=game)
    asyncio.create_task(game.fly())
    return True


# =====================================================================
# 💣 MINES
# =====================================================================
TILES = 20


class Tile(discord.ui.Button):
    def __init__(self, i):
        super().__init__(label="​", style=discord.ButtonStyle.secondary, row=i // 5)
        self.i = i

    async def callback(self, interaction):
        await self.view.pick(interaction, self)


class Mines(PlayerView):
    def __init__(self, player, bet, mines):
        super().__init__(player, timeout=120)
        self.bet, self.mines = bet, mines
        self.bombs = set(random.sample(range(TILES), mines))
        self.found = 0
        self.done = False
        self.tiles = [Tile(i) for i in range(TILES)]
        for t in self.tiles:
            self.add_item(t)
        self.cash = discord.ui.Button(label="Cash out", emoji="💰", style=discord.ButtonStyle.blurple, row=4, disabled=True)
        self.cash.callback = self.cashout
        self.add_item(self.cash)

    def mult(self, found=None):
        found = self.found if found is None else found
        m = 0.97
        for i in range(found):
            m *= (TILES - i) / (TILES - self.mines - i)
        return m if found else 1.0

    def embed(self, text, color=BLUE):
        e = discord.Embed(title="💣 Mines", color=color,
                          description=f"{text}\n\n💣 {self.mines} mines · 💎 {self.found} found · ×{self.mult():.2f} = "
                                      f"**{coins(self.bet * self.mult())}**\nNext gem: ×{self.mult(self.found + 1):.2f}")
        return balance_footer(e, self.player.id)

    def reveal(self):
        for t in self.tiles:
            t.disabled = True
            if t.i in self.bombs:
                t.emoji, t.label, t.style = "💣", None, discord.ButtonStyle.red
        self.cash.disabled = True

    async def pick(self, interaction, tile):
        if self.done:
            return await interaction.response.defer()
        if tile.i in self.bombs:
            self.done = True
            self.stop()
            finish(self.player.id, self.bet, 0)
            self.reveal()
            tile.emoji = "💥"
            await interaction.response.edit_message(embed=self.embed(f"💥 **BOOM!** You lose {coins(self.bet)}.", RED), view=self)
            await self._again(interaction.message)
            return
        self.found += 1
        tile.emoji, tile.label, tile.style, tile.disabled = "💎", None, discord.ButtonStyle.green, True
        self.cash.disabled = False
        self.cash.label = f"Cash out {int(self.bet * self.mult()):,}"
        if self.found == TILES - self.mines:
            return await self.cashout(interaction)
        await interaction.response.edit_message(embed=self.embed("💎 Safe! Keep digging or cash out."), view=self)

    async def cashout(self, interaction=None):
        if self.done:
            return await interaction.response.defer() if interaction else None
        self.done = True
        self.stop()
        pay = int(self.bet * self.mult())
        finish(self.player.id, self.bet, pay)
        self.reveal()
        embed = self.embed(f"💰 Cashed out **+{coins(pay - self.bet)}**!" if pay > self.bet else "Bet returned.", GREEN)
        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
            await self._again(interaction.message)
        elif self.message:
            await self.message.edit(embed=embed, view=self)
            await self._again(self.message)

    async def _again(self, message):
        again = AgainView(self.player, self.bet, mines_start_for(self.mines))
        again.message = await message.channel.send(f"-# {self.player.mention}'s mines game is over", view=again,
                                                    allowed_mentions=discord.AllowedMentions.none())

    async def on_timeout(self):
        if not self.done:
            await self.cashout()


def mines_start_for(mines):
    async def start(interaction, bet_text, edit=False):
        bet = await take_bet(interaction, bet_text)
        if bet is None:
            return False
        game = Mines(interaction.user, bet, mines)
        game.message = await send(interaction, edit, content=None, embed=game.embed("Find the 💎, avoid the 💣. Cash out anytime!"), view=game)
        return True
    return start


# =====================================================================
# 🎟️ SCRATCH CARD
# =====================================================================
PRIZES = [("👑", 25, 0.006), ("💎", 10, 0.015), ("💵", 5, 0.04), ("🍀", 2, 0.09), ("🍒", 1, 0.16)]
FILLER = ["👑", "💎", "💵", "🍀", "🍒", "🍋"]


def scratch_card():
    """Returns (9 symbols, winning symbol or None, multiplier)."""
    roll, prize = random.random(), None
    for symbol, mult, chance in PRIZES:
        if roll < chance:
            prize = (symbol, mult)
            break
        roll -= chance
    cells = [prize[0]] * 3 if prize else []
    counts = {s: cells.count(s) for s in FILLER}
    while len(cells) < 9:
        s = random.choice([f for f in FILLER if counts[f] < 2 and (not prize or f != prize[0])])
        counts[s] += 1
        cells.append(s)
    random.shuffle(cells)
    return cells, prize[0] if prize else None, prize[1] if prize else 0


async def scratch_start(interaction, bet_text=None, edit=False):
    price = config.SCRATCH_PRICE
    bet = await take_bet(interaction, str(price), minimum=price)
    if bet is None:
        return False
    uid = interaction.user.id
    cells, symbol, mult = scratch_card()
    pay = price * mult
    finish(uid, price, pay)
    grid = "\n".join(" ".join(f"||{c}||" for c in cells[r * 3:r * 3 + 3]) for r in range(3))
    result = (f"||**3× {symbol}: you win {coins(pay)}!**||" if mult > 1 else
              f"||{symbol} 3× {symbol}: your {coins(price)} back||" if mult == 1 else "||no match, better luck next time 💨||")
    embed = discord.Embed(title="🎟️ Scratch card", color=GOLD,
                          description=f"Click the squares to scratch! Find **3 of the same** to win.\n\n# {grid}\n\n{result}")
    embed.add_field(name="Prizes", value="👑 ×25 · 💎 ×10 · 💵 ×5 · 🍀 ×2 · 🍒 money back")
    balance_footer(embed, uid, f"Card: {price} coins · ")
    again = AgainView(interaction.user, price, scratch_start, "Another card")
    again.message = await send(interaction, edit, embed=embed, view=again)
    return True


# =====================================================================
# THE COMMANDS
# =====================================================================
class Arcade(commands.Cog):
    @app_commands.command(name="slots", description="🎰 Spin the slot machine")
    @app_commands.describe(bet=BET)
    @games_only()
    async def slots(self, interaction: discord.Interaction, bet: str):
        await slots_start(interaction, bet)

    @app_commands.command(name="spin", description="🎡 Roulette wheel: bet on red, black, odd, even, green or a number")
    @app_commands.describe(bet=BET, on="What you bet on", number="The number (0-36) if you picked 'number'")
    @app_commands.choices(on=[app_commands.Choice(name=n, value=v) for n, v in [
        ("🔴 Red (×2)", "red"), ("⚫ Black (×2)", "black"), ("Odd (×2)", "odd"), ("Even (×2)", "even"),
        ("1-18 (×2)", "low"), ("19-36 (×2)", "high"), ("🟢 Green 0 (×36)", "green"), ("🎯 A number (×36)", "number")]])
    @games_only()
    async def spin(self, interaction: discord.Interaction, bet: str, on: app_commands.Choice[str],
                   number: app_commands.Range[int, 0, 36] = None):
        if on.value == "number" and number is None:
            return await oops(interaction, "🎯 Pick which number with the `number` option (0-36).")
        await wheel_start_for(on.value, number)(interaction, bet)

    @app_commands.command(name="coinflip", description="🪙 Heads or tails, pays ×1.95")
    @app_commands.describe(bet=BET, side="Heads or tails")
    @app_commands.choices(side=[app_commands.Choice(name="👑 Heads", value="heads"), app_commands.Choice(name="🦅 Tails", value="tails")])
    @games_only()
    async def coinflip(self, interaction: discord.Interaction, bet: str, side: app_commands.Choice[str]):
        await coinflip_start_for(side.value)(interaction, bet)

    @app_commands.command(name="duel", description="⚔️ Challenge someone: you both bet, the winner takes it all")
    @app_commands.describe(opponent="Who you're fighting", bet=BET)
    @games_only()
    async def duel(self, interaction: discord.Interaction, opponent: discord.Member, bet: str):
        if opponent.bot or opponent.id == interaction.user.id:
            return await oops(interaction, "🤨 Pick a real opponent.")
        amount = await take_bet(interaction, bet)
        if amount is None:
            return
        view = Duel(interaction.user, opponent, amount)
        embed = discord.Embed(title="⚔️ Duel!", color=BLUE,
                              description=f"{interaction.user.mention} challenges {opponent.mention} to a coinflip duel for "
                                          f"**{coins(amount)}** each!\nWinner takes {coins(amount * 2)}. You have 60 seconds.")
        await interaction.response.send_message(content=opponent.mention, embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="highlow", description="🃏 Higher or lower: build a streak, cash out before you're wrong")
    @app_commands.describe(bet=BET)
    @games_only()
    async def highlow(self, interaction: discord.Interaction, bet: str):
        await highlow_start(interaction, bet)

    @app_commands.command(name="crash", description="📈 The multiplier rises... cash out before it crashes")
    @app_commands.describe(bet=BET)
    @games_only()
    async def crash(self, interaction: discord.Interaction, bet: str):
        await crash_start(interaction, bet)

    @app_commands.command(name="mines", description="💣 Find gems, avoid mines, cash out anytime")
    @app_commands.describe(bet=BET, mines="How many mines (more = riskier = bigger wins)")
    @games_only()
    async def mines(self, interaction: discord.Interaction, bet: str, mines: app_commands.Range[int, 1, 15] = 3):
        await mines_start_for(mines)(interaction, bet)

    @app_commands.command(name="scratch", description="🎟️ Buy a scratch card and scratch it")
    @games_only()
    async def scratch(self, interaction: discord.Interaction):
        await scratch_start(interaction)

    @app_commands.command(name="rob", description="🦹 Try to steal coins from someone (it might backfire)")
    @app_commands.describe(victim="Who you're robbing")
    @games_only()
    async def rob(self, interaction: discord.Interaction, victim: discord.Member):
        if not config.ROB:
            return await oops(interaction, "🚓 Robbing is turned off on this server.")
        thief = interaction.user
        if victim.bot or victim.id == thief.id:
            return await oops(interaction, "🤨 Pick a real victim.")
        me = bank.user(thief.id)
        wait = int(me["last_rob"] + config.ROB_COOLDOWN_MINUTES * 60 - time.time())
        if wait > 0:
            return await oops(interaction, f"🚓 Lay low for **{wait // 60 + 1} more minutes**, the cops are watching.")
        if bank.balance(victim.id) < 200:
            return await oops(interaction, f"🥺 {victim.display_name} is too broke to rob.")
        if bank.balance(thief.id) < 100:
            return await oops(interaction, "💸 You need at least 🪙 100 to afford the getaway car.")
        me["last_rob"] = time.time()
        if random.random() < config.ROB_CHANCE:
            loot = min(5000, int(bank.balance(victim.id) * random.uniform(0.05, 0.15)))
            bank.take(victim.id, loot)
            bank.add(thief.id, loot)
            text = random.choice([f"🦹 {thief.mention} pickpocketed {victim.mention} and got away with **{coins(loot)}**!",
                                  f"💰 {thief.mention} robbed {victim.mention} for **{coins(loot)}**. Smooth.",
                                  f"🏃 {thief.mention} snatched **{coins(loot)}** from {victim.mention} and vanished!"])
        else:
            fine = max(50, int(bank.balance(thief.id) * 0.10))
            bank.take(thief.id, fine)
            bank.add(victim.id, fine)
            text = random.choice([f"🚓 {thief.mention} tripped over their own feet and paid {victim.mention} **{coins(fine)}** in damages.",
                                  f"👮 {thief.mention} got caught robbing {victim.mention}! Fined **{coins(fine)}** (paid to the victim).",
                                  f"🐕 {victim.mention}'s dog chased {thief.mention} away. {thief.mention} dropped **{coins(fine)}**."])
        await interaction.response.send_message(text)


async def setup(bot):
    await bot.add_cog(Arcade())
