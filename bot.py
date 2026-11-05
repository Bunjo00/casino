"""🎰 The Casino: blackjack, the guillotine, slots, crash, mines, party games and a role shop, all in one bot.
Start it with:  python bot.py
"""
import asyncio
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from casino import config
from casino.bank import bank
from casino.ui import CasinoError

COGS = ["economy", "blackjack", "guillotine", "arcade", "party", "reroll", "icebreaker"]


class Casino(commands.Bot):
    async def setup_hook(self):
        for cog in COGS:
            await self.load_extension(f"casino.cogs.{cog}")
        self.tree.on_error = on_app_error
        if config.GUILD_ID:  # instant commands on your server
            guild = discord.Object(id=int(config.GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            self.tree.clear_commands(guild=None)
            await self.tree.sync()  # (removes old global copies so nothing shows twice)
        else:
            synced = await self.tree.sync()
        print(f"✅ {len(synced)} slash commands ready" + ("" if config.GUILD_ID else " (can take a few minutes to appear)"))
        self.saver = asyncio.create_task(bank.autosave())

    async def close(self):
        bank.save()
        print("💾 saved")
        await super().close()


async def on_app_error(interaction, error):
    if isinstance(error, CasinoError):
        msg = str(error)
    elif isinstance(error, app_commands.CommandOnCooldown):
        msg = f"⏳ Slow down! Try again in {error.retry_after:.0f}s."
    elif isinstance(error, app_commands.MissingPermissions):
        msg = "🚫 Only the royal executioners (mods) can do that."
    elif isinstance(error, app_commands.CheckFailure):
        msg = "🚫 You can't use that here."
    else:
        original = getattr(error, "original", error)
        print(f"⚠️ /{interaction.command.name if interaction.command else '?'}: {original!r}")
        msg = f"⚠️ Something broke: `{original}`"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except discord.HTTPException:
        pass


def main():
    load_dotenv(os.path.join(HERE, ".env"))
    token = (os.getenv("DISCORD_TOKEN") or os.getenv("Discord_Token") or os.getenv("TOKEN") or "").strip().strip('"')
    if not token:
        raise SystemExit("❌ No token found. Add a variable DISCORD_TOKEN with your bot token "
                         "(Railway: Variables tab · your PC: the .env file next to bot.py).")
    intents = discord.Intents.default()
    intents.members = True  # /reroll cleans up roles of people who left (needs "Server Members Intent")
    try:
        make_bot(intents).run(token)
    except discord.PrivilegedIntentsRequired:
        print("⚠️ 'Server Members Intent' is off in the Developer Portal (Bot tab). "
              "Starting anyway; /reroll just won't clean up old roles by itself.")
        intents.members = False
        make_bot(intents).run(token)


def make_bot(intents):
    bot = Casino(command_prefix=commands.when_mentioned, intents=intents, help_command=None)

    @bot.event
    async def on_ready():
        print(f"🎰 Logged in as {bot.user}, the casino is open!")
    return bot


if __name__ == "__main__":
    main()
