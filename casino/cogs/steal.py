"""🦹 /steal: try to steal a role from someone. Only harmless roles (no admin/mod powers) can be stolen.

Settings: the STEAL_ lines in settings.py (chance, cost, cooldowns, roles that can never be stolen).
"""
import asyncio
import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..bank import bank
from ..ui import GOLD, RED, coins, oops
from .reroll import ALL_NAMES

S = lambda name, default: getattr(config, name, default)  # noqa: E731

# a role with ANY of these can't be stolen
POWERS = ("administrator", "manage_guild", "manage_roles", "manage_channels", "manage_messages", "manage_webhooks",
          "manage_expressions", "manage_events", "manage_threads", "manage_nicknames", "kick_members", "ban_members",
          "moderate_members", "mention_everyone", "view_audit_log", "move_members", "mute_members", "deafen_members")


def stealable(role, guild):
    if role.is_default() or role.managed or role.is_premium_subscriber() or role >= guild.me.top_role:
        return False
    if role.name in ALL_NAMES:  # personal /reroll roles
        return False
    if role.name in S("DEBT_ROLES", []) or role.name in S("STEAL_NEVER", []):
        return False
    perms = role.permissions
    return not any(getattr(perms, p, False) for p in POWERS)


def steal_data():
    return bank.data.setdefault("steal", {"last": {}, "robbed": {}})


class Steal(commands.Cog):
    async def role_choices(self, interaction: discord.Interaction, current: str):
        victim = getattr(interaction.namespace, "victim", None)
        member = interaction.guild.get_member(victim.id) if victim else None
        roles = [r for r in (member.roles if member else []) if stealable(r, interaction.guild)]
        return [app_commands.Choice(name=r.name[:100], value=str(r.id))
                for r in roles if current.lower() in r.name.lower()][:25]

    @app_commands.command(name="steal", description="🦹 Try to steal a role from someone (only roles with no powers)")
    @app_commands.describe(victim="Who you're robbing", role="Which role (empty = grab a random one)")
    @app_commands.autocomplete(role=role_choices)
    @app_commands.guild_only()
    async def steal(self, interaction: discord.Interaction, victim: discord.Member, role: str = None):
        thief, guild = interaction.user, interaction.guild
        if victim.bot or victim.id == thief.id:
            return await oops(interaction, "🤨 Pick a real victim.")
        data, now = steal_data(), time.time()
        wait = int(data["last"].get(str(thief.id), 0) + S("STEAL_COOLDOWN_MINUTES", 180) * 60 - now)
        if wait > 0:
            h, m = divmod(-(-wait // 60), 60)
            return await oops(interaction, f"🚓 Lay low for **{f'{h}h ' if h else ''}{m}m**, the guards know your face.")
        safe = int(data["robbed"].get(str(victim.id), 0) + S("STEAL_PROTECT_MINUTES", 60) * 60 - now)
        if safe > 0:
            return await oops(interaction, f"🛡️ {victim.display_name} was just robbed. They're under protection for {safe // 60 + 1} more minutes.")

        options = [r for r in victim.roles if stealable(r, guild) and r not in thief.roles]
        if role:
            target = guild.get_role(int(role)) if role.isdigit() else discord.utils.get(victim.roles, name=role)
            if not target or target not in victim.roles:
                return await oops(interaction, f"🤷 {victim.display_name} doesn't have that role.")
            if not stealable(target, guild):
                return await oops(interaction, f"🔒 **{target.name}** is too powerful to steal.")
            if target in thief.roles:
                return await oops(interaction, "😐 You already have that role.")
        elif options:
            target = random.choice(options)
        else:
            return await oops(interaction, f"🤷 {victim.display_name} has nothing worth stealing.")

        cost = S("STEAL_COST", 300)
        if not bank.take(thief.id, cost):
            return await oops(interaction, f"💸 A heist costs {coins(cost)} (lockpicks aren't free).")
        data["last"][str(thief.id)] = now
        bank.dirty = True

        await interaction.response.send_message(f"🦹 {thief.mention} is sneaking up on {victim.mention}... 👀",
                                                allowed_mentions=discord.AllowedMentions.none())
        await asyncio.sleep(2.5)  # suspense
        if random.random() < S("STEAL_CHANCE", 0.35):
            try:
                await victim.remove_roles(target, reason=f"Stolen by {thief}")
                await thief.add_roles(target, reason=f"Stole it from {victim}")
            except discord.HTTPException:
                bank.add(thief.id, cost)
                return await interaction.edit_original_response(
                    content="😬 The vault was locked. (I need **Manage Roles** and my role above that one.) Fee refunded.")
            data["robbed"][str(victim.id)] = now
            line = random.choice([f"💰 **HEIST SUCCESSFUL!** {thief.mention} stole **{target.name}** from {victim.mention}!",
                                  f"🦹 {thief.mention} snatched **{target.name}** right off {victim.mention}'s back. Smooth.",
                                  f"🕶️ {victim.mention} blinked and **{target.name}** was gone. {thief.mention} wears it now."])
            embed = discord.Embed(description=line + f"\n-# {victim.display_name} can try to `/steal` it back later 👀", color=GOLD)
        else:
            fine = S("STEAL_FINE", 200)
            paid = min(fine, bank.balance(thief.id))
            bank.take(thief.id, paid)
            bank.add(victim.id, paid)
            line = random.choice([f"🚨 {thief.mention} tripped the alarm trying to steal **{target.name}** from {victim.mention}!",
                                  f"👮 {thief.mention} got caught red-handed reaching for {victim.mention}'s **{target.name}**!",
                                  f"🐕 {victim.mention}'s guard dog bit {thief.mention}. **{target.name}** stays put."])
            embed = discord.Embed(description=line + (f"\n💸 Fined {coins(paid)}, paid to {victim.mention}." if paid else ""), color=RED)
        bank.dirty = True
        await interaction.edit_original_response(content=None, embed=embed, allowed_mentions=discord.AllowedMentions.none())


async def setup(bot):
    await bot.add_cog(Steal())
