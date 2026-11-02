"""🃏 Blackjack against the bot (your original game, plus a 'play again' button)."""
import random

import discord
from discord import app_commands
from discord.ext import commands

from ..bank import bank
from ..ui import (FELT, GOLD, GREEN, GREY, RED, AgainView, PlayerView, coins, free, games_only, send,
                  take_bet)

SUITS = ["♠️", "♥️", "♦️", "♣️"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]


def new_deck():
    deck = [(r, s) for s in SUITS for r in RANKS]
    random.shuffle(deck)
    return deck


def value(hand):
    total = sum(11 if r == "A" else 10 if r in "JQK" else int(r) for r, _ in hand)
    aces = sum(r == "A" for r, _ in hand)
    while total > 21 and aces:
        total, aces = total - 10, aces - 1
    return total


def show(hand, hide=False):
    if hide:
        return f"`{hand[0][0]}{hand[0][1]}` `🂠`"
    return " ".join(f"`{r}{s}`" for r, s in hand)


def blackjack(hand):
    return len(hand) == 2 and value(hand) == 21


class Table(PlayerView):
    def __init__(self, player, bet):
        super().__init__(player)
        self.bet = bet
        self.deck = new_deck()
        self.hand = [self.deck.pop(), self.deck.pop()]
        self.dealer = [self.deck.pop(), self.deck.pop()]
        self.finished = False
        if bank.balance(player.id) < bet:
            self.double.disabled = True

    def embed(self, reveal=False, result=None, color=FELT):
        e = discord.Embed(title="🃏 Blackjack", color=color)
        e.add_field(name=f"🤖 Dealer ({value(self.dealer) if reveal else '?'})", value=show(self.dealer, not reveal), inline=False)
        e.add_field(name=f"🧑 {self.player.display_name} ({value(self.hand)})", value=show(self.hand), inline=False)
        e.add_field(name="Bet", value=coins(self.bet))
        if result:
            e.add_field(name="Result", value=result, inline=False)
            e.set_footer(text=f"Balance: {bank.balance(self.player.id):,} coins")
        else:
            e.set_footer(text="Hit = draw · Stand = hold · Double = double the bet and draw one card")
        return e

    def finish(self, natural=False):
        """Ends the hand, pays out. Returns (embed, play-again view)."""
        self.finished = True
        self.stop()
        free(self.player.id)
        me = value(self.hand)
        if me <= 21 and not natural:
            while value(self.dealer) < 17:
                self.dealer.append(self.deck.pop())
        dealer, bet = value(self.dealer), self.bet
        if natural and blackjack(self.hand) and blackjack(self.dealer):
            pay, text, color = bet, "🤝 Both have Blackjack, push! Bet returned.", GREY
        elif natural and blackjack(self.hand):
            pay = int(bet * 2.5)
            text, color = f"🎉 **BLACKJACK!** You win {coins(pay - bet)}!", GOLD
        elif natural:
            pay, text, color = 0, f"💀 Dealer has Blackjack. You lose {coins(bet)}.", RED
        elif me > 21:
            pay, text, color = 0, f"💥 Bust! You lose {coins(bet)}.", RED
        elif dealer > 21:
            pay, text, color = bet * 2, f"🔥 Dealer busts! You win {coins(bet)}!", GREEN
        elif me > dealer:
            pay, text, color = bet * 2, f"✅ You win {coins(bet)}!", GREEN
        elif me == dealer:
            pay, text, color = bet, "🤝 Push, bet returned.", GREY
        else:
            pay, text, color = 0, f"❌ Dealer wins. You lose {coins(bet)}.", RED
        bank.add(self.player.id, pay)
        bank.result(self.player.id, bet, pay)
        return self.embed(True, text, color), AgainView(self.player, self.start_bet, start)

    async def _end(self, interaction):
        embed, again = self.finish()
        await interaction.response.edit_message(embed=embed, view=again)
        again.message = interaction.message

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green, emoji="🃏")
    async def hit(self, interaction, button):
        self.hand.append(self.deck.pop())
        self.double.disabled = True
        if value(self.hand) >= 21:
            await self._end(interaction)
        else:
            await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.red, emoji="✋")
    async def stand(self, interaction, button):
        await self._end(interaction)

    @discord.ui.button(label="Double", style=discord.ButtonStyle.blurple, emoji="💰")
    async def double(self, interaction, button):
        if not bank.take(self.player.id, self.bet):
            await interaction.response.send_message("💸 Not enough coins to double!", ephemeral=True)
            return
        self.bet *= 2
        self.hand.append(self.deck.pop())
        await self._end(interaction)

    async def on_timeout(self):
        if self.finished:
            return
        embed, again = self.finish()  # took too long: auto-stand
        if self.message:
            try:
                await self.message.edit(embed=embed, view=again)
                again.message = self.message
            except discord.HTTPException:
                pass


async def start(interaction, bet_text, edit=False):
    bet = await take_bet(interaction, bet_text)
    if bet is None:
        return False
    table = Table(interaction.user, bet)
    table.start_bet = bet
    if blackjack(table.hand) or blackjack(table.dealer):
        embed, again = table.finish(natural=True)
        again.message = await send(interaction, edit, embed=embed, view=again)
    else:
        table.message = await send(interaction, edit, embed=table.embed(), view=table)
    return True


class Blackjack(commands.Cog):
    @app_commands.command(name="blackjack", description="🃏 Play blackjack against the dealer")
    @app_commands.describe(bet="Coins to bet: 100, 5k, half or all")
    @games_only()
    async def blackjack_cmd(self, interaction: discord.Interaction, bet: str):
        await start(interaction, bet)


async def setup(bot):
    await bot.add_cog(Blackjack())
