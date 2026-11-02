"""🪓 The 50/50 guillotine (your original), now with coins: survivors get a reward,
and the crowd can bet on whether the accused lives or dies."""
import asyncio
import random
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..bank import bank
from ..ui import coins, games_only, oops

DRAMA = [
    "🥁 *drumroll intensifies*",
    "🪙 The coin is flipped high into the air...",
    "😰 The crowd holds its breath...",
    "🌀 It spins... and spins...",
]
DOOM = [
    "🪓 **OFF WITH THEIR HEAD!** {name} has been executed. Their snacks will be redistributed.",
    "⚰️ {name} has been yeeted into the shadow realm. Press F.",
    "💀 The coin has spoken. {name} is no more. Someone tell their mom.",
    "🔥 {name} was found guilty of vibing incorrectly. Sentence: immediate exile.",
    "🦆 A goose has dragged {name} away. There is nothing we can do.",
]
SPARE = [
    "😇 **SPARED!** {name} lives to cause chaos another day.",
    "🍀 The coin shows mercy. {name} walks free... for now.",
    "🛡️ {name} dodged the guillotine like it was a dodgeball. Respect.",
    "🎉 {name} survives! The executioner goes home disappointed.",
    "🐸 A frog jumped on the lever. {name} is saved by pure frog energy.",
]


class CrowdBets(discord.ui.View):
    """Everyone except the accused can bet on the outcome while the coin spins."""

    def __init__(self, target):
        super().__init__(timeout=60)
        self.target = target
        self.bets = {}  # user id -> "live" / "die"
        self.open = True

    async def _bet(self, interaction, side):
        uid = interaction.user.id
        if uid == self.target.id:
            return await oops(interaction, "🙅 You can't bet on your own head!")
        if not self.open:
            return await oops(interaction, "⌛ Too late, the blade is falling!")
        if uid in self.bets:
            return await oops(interaction, "You already bet on this one.")
        if not bank.take(uid, config.GUILLOTINE_SIDE_BET):
            return await oops(interaction, f"💸 You need {coins(config.GUILLOTINE_SIDE_BET)} to bet.")
        self.bets[uid] = side
        await oops(interaction, f"✅ You bet {coins(config.GUILLOTINE_SIDE_BET)} that they **{'live' if side == 'live' else 'die'}**.")

    @discord.ui.button(label="Bet: lives", emoji="🍀", style=discord.ButtonStyle.green)
    async def live(self, interaction, button):
        await self._bet(interaction, "live")

    @discord.ui.button(label="Bet: dies", emoji="💀", style=discord.ButtonStyle.red)
    async def die(self, interaction, button):
        await self._bet(interaction, "die")

    def settle(self, doomed):
        self.open = False
        self.stop()
        for item in self.children:
            item.disabled = True
        if not self.bets:
            return ""
        winning = "die" if doomed else "live"
        winners = [uid for uid, side in self.bets.items() if side == winning]
        for uid in self.bets:
            pay = config.GUILLOTINE_SIDE_BET * 2 if uid in winners else 0
            bank.add(uid, pay)
            bank.result(uid, config.GUILLOTINE_SIDE_BET, pay)
        if not winners:
            return "\n🎲 Nobody in the crowd called it. The house keeps the bets."
        return (f"\n🎲 The crowd bet right: " + ", ".join(f"<@{u}>" for u in winners)
                + f" (+{coins(config.GUILLOTINE_SIDE_BET)} each)")


async def punish(guild, channel, target):
    """Carries out the sentence. Returns an error message, or None if it worked."""
    mode = config.GUILLOTINE_PUNISHMENT
    if mode == "timeout":
        try:
            await target.timeout(timedelta(minutes=config.GUILLOTINE_TIMEOUT_MINUTES), reason="Lost the 50/50 guillotine")
            return None
        except discord.HTTPException:
            return "😬 The blade got stuck. (I'm missing the Timeout Members permission.)"
    invite_url = None
    try:  # a one-use invite so they can come back
        invite = await channel.create_invite(max_uses=1, max_age=0, unique=True, reason="Return ticket from the afterlife")
        invite_url = invite.url
    except discord.HTTPException:
        pass
    how = "Beg a mod for a `/pardon`, then use" if mode == "ban" else "Use"
    try:
        await target.send(f"💀 You were executed in **{guild.name}** by the 50/50 guillotine.\n"
                          f"{how} this to come back: {invite_url or '(ask a mod for an invite)'}")
    except discord.HTTPException:
        pass  # DMs closed
    try:
        if mode == "kick":
            await guild.kick(target, reason="Lost the 50/50 guillotine")
        else:
            await guild.ban(target, reason="Lost the 50/50 guillotine", delete_message_seconds=0)
        return None
    except discord.HTTPException:
        return f"😬 The blade got stuck. (I'm missing the {'Kick' if mode == 'kick' else 'Ban'} Members permission.)"


async def trial(interaction, target):
    guild = interaction.guild
    if target.bot:
        return await oops(interaction, "🤖 Bots have diplomatic immunity.")
    if target.id == guild.owner_id:
        return await oops(interaction, "👑 The server owner cannot be executed. They own the guillotine.")
    if target.top_role >= guild.me.top_role:
        return await oops(interaction, f"🛡️ {target.display_name}'s role is too powerful for my axe. (Move my role higher.)")
    if trial.running.get(target.id):
        return await oops(interaction, "⚖️ They're already on trial!")
    trial.running[target.id] = True
    try:
        crowd = CrowdBets(target)
        text = f"⚖️ **THE COURT IS NOW IN SESSION**\n{target.mention} stands before the guillotine..."
        footer = f"\n-# 🎲 Bet {config.GUILLOTINE_SIDE_BET} on the outcome below, it pays double"
        await interaction.response.send_message(text + footer, view=crowd)
        for line in DRAMA:
            await asyncio.sleep(1.5)
            text += f"\n{line}"
            await interaction.edit_original_response(content=text + footer)
        await asyncio.sleep(2)

        doomed = random.random() < 0.5
        if doomed:
            problem = await punish(guild, interaction.channel, target)
            if problem:  # nothing happened: give the crowd their money back
                crowd.open = False
                crowd.stop()
                for uid in crowd.bets:
                    bank.add(uid, config.GUILLOTINE_SIDE_BET)
                return await interaction.edit_original_response(content=text + "\n\n" + problem + "\n-# bets refunded", view=None)
            stats = bank.grave(guild.id, target, died=True)
            verdict = random.choice(DOOM).format(name=f"**{target.display_name}**")
            verdict += f"\n☠️ Death count: **{stats['deaths']}**"
            if config.GUILLOTINE_PUNISHMENT == "timeout":
                verdict += f" · ⏳ timed out for {config.GUILLOTINE_TIMEOUT_MINUTES} minutes"
        else:
            stats = bank.grave(guild.id, target, died=False)
            bank.add(target.id, config.GUILLOTINE_REWARD)
            verdict = random.choice(SPARE).format(name=target.mention)
            verdict += f"\n🍀 Survivals: **{stats['survivals']}** · 💰 survivor's bonus: {coins(config.GUILLOTINE_REWARD)}"
        verdict += crowd.settle(doomed)
        await interaction.edit_original_response(content=text + "\n\n" + verdict, view=crowd)
    finally:
        trial.running.pop(target.id, None)


trial.running = {}


class Guillotine(commands.Cog):
    @app_commands.command(name="roulette", description="🪓 Put yourself on trial. 50/50. Survive for coins. Good luck.")
    @games_only()
    async def roulette(self, interaction: discord.Interaction):
        await trial(interaction, interaction.user)

    @app_commands.command(name="execute", description="🪓 Drag someone to the guillotine (50/50)")
    @app_commands.describe(target="The accused")
    @app_commands.checks.has_permissions(ban_members=True)
    @games_only()
    async def execute(self, interaction: discord.Interaction, target: discord.Member):
        await trial(interaction, target)

    @app_commands.command(name="pardon", description="✨ Bring someone back from the dead (unban)")
    @app_commands.describe(user="The fallen (paste their user ID if needed)")
    @app_commands.checks.has_permissions(ban_members=True)
    async def pardon(self, interaction: discord.Interaction, user: discord.User):
        try:
            await interaction.guild.unban(user, reason=f"Pardoned by {interaction.user}")
            await interaction.response.send_message(
                f"✨ **RESURRECTION!** {user.name} has been pardoned by the crown. They may return to the land of the living.")
        except discord.NotFound:
            await oops(interaction, f"🤔 {user.name} isn't dead. Yet.")

    @app_commands.command(name="graveyard", description="⚰️ See who has died the most")
    async def graveyard(self, interaction: discord.Interaction):
        data = bank.data["graveyard"].get(str(interaction.guild_id), {})
        if not data:
            return await interaction.response.send_message("🌱 The graveyard is empty. Suspiciously peaceful.")
        ranked = sorted(data.values(), key=lambda u: (u["deaths"], -u["survivals"]), reverse=True)[:10]
        medals = ["🥇", "🥈", "🥉"]
        lines = [f"{medals[i] if i < 3 else '🪦'} **{u['name']}**: ☠️ {u['deaths']} deaths | 🍀 {u['survivals']} survived"
                 for i, u in enumerate(ranked)]
        embed = discord.Embed(title="⚰️ THE GRAVEYARD ⚰️", description="\n".join(lines), color=0x2B2D31)
        embed.set_footer(text="Rest in pieces.")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Guillotine())
