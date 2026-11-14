"""🏦 Loans: borrow from the bank (/loan) or from friends (/lend).
Miss the deadline and you get a funny debt role until you pay it back (or someone forgives you).

Settings: the LOAN_ lines in settings.py (interest, days, limits, the debt role names).
"""
import math
import random
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

from .. import config
from ..bank import bank
from ..ui import GOLD, GREEN, RED, coins, oops

S = lambda name, default: getattr(config, name, default)  # noqa: E731
DAY = 86400


def loans():
    return bank.data.setdefault("loans", {"bank": {}, "friends": [], "next": 1})


def save():
    bank.dirty = True


def debt_role_names():
    return S("DEBT_ROLES", ["🦈 Loan Shark Bait", "💸 Broke & Owing", "🤡 Financially Challenged",
                            "🧾 Professional Debtor", "🪦 Credit Score: 0", "🐀 Owes The House"])


def limit_for(uid):
    u = bank.user(uid)
    return min(S("LOAN_MAX", 10000), S("LOAN_MAX_BASE", 1000) + u["games"] * S("LOAN_PER_GAME", 20))


def due_text(due):
    left = int(due - time.time())
    if left <= 0:
        return "**OVERDUE** 🦈"
    d, rest = divmod(left, DAY)
    return f"due in {d}d {rest // 3600}h" if d else f"due in {rest // 3600}h {rest % 3600 // 60}m"


def still_overdue(uid):
    """Does this person still owe anything that's past its deadline?"""
    now = time.time()
    b = loans()["bank"].get(str(uid))
    if b and b["due"] < now:
        return True
    return any(l["borrower"] == uid and l["due"] < now for l in loans()["friends"])


class LendOffer(discord.ui.View):
    def __init__(self, lender, borrower, amount, interest, days):
        super().__init__(timeout=300)
        self.lender, self.borrower = lender, borrower
        self.amount, self.interest, self.days = amount, interest, days
        self.message = None

    async def interaction_check(self, interaction):
        if interaction.user.id != self.borrower.id:
            await oops(interaction, "🙅 This offer isn't for you.")
            return False
        return True

    @discord.ui.button(label="Accept", emoji="🤝", style=discord.ButtonStyle.green)
    async def accept(self, interaction, button):
        if not bank.take(self.lender.id, self.amount):
            self.stop()
            return await interaction.response.edit_message(
                content=f"💸 {self.lender.mention} doesn't have {coins(self.amount)} anymore. Deal's off.", embed=None, view=None)
        self.stop()
        bank.add(self.borrower.id, self.amount)
        owed = math.ceil(self.amount * (1 + self.interest / 100))
        data = loans()
        data["friends"].append({"id": data["next"], "lender": self.lender.id, "borrower": self.borrower.id,
                                "guild": interaction.guild_id, "amount": self.amount, "owed": owed,
                                "due": time.time() + self.days * DAY, "overdue": False})
        data["next"] += 1
        save()
        await interaction.response.edit_message(
            content=f"🤝 Deal! {self.lender.mention} lent {self.borrower.mention} **{coins(self.amount)}**. "
                    f"Pay back **{coins(owed)}** within **{self.days} days** with `/repay`.", embed=None, view=None)

    @discord.ui.button(label="No thanks", emoji="✋", style=discord.ButtonStyle.secondary)
    async def decline(self, interaction, button):
        self.stop()
        await interaction.response.edit_message(content=f"✋ {self.borrower.mention} turned down the loan.", embed=None, view=None)

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(content="⌛ Loan offer expired.", embed=None, view=None)
            except discord.HTTPException:
                pass


class Loans(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.checker.start()

    async def cog_unload(self):
        self.checker.cancel()

    # ---------- the debt role ----------
    async def member(self, guild, uid):
        m = guild.get_member(uid)
        if m is None:
            try:
                m = await guild.fetch_member(uid)
            except discord.HTTPException:
                return None
        return m

    async def give_debt_role(self, guild_id, uid):
        guild = self.bot.get_guild(guild_id or 0)
        if not guild:
            return None
        member = await self.member(guild, uid)
        if not member:
            return None
        if any(r.name in debt_role_names() for r in member.roles):
            return next(r.name for r in member.roles if r.name in debt_role_names())
        name = random.choice(debt_role_names())
        role = discord.utils.get(guild.roles, name=name)
        try:
            if role is None:
                role = await guild.create_role(name=name, colour=discord.Colour(S("DEBT_ROLE_COLOR", 0x7F8C8D)),
                                               hoist=True, reason="Unpaid loan")
            await member.add_roles(role, reason="Unpaid loan")
            return name
        except discord.HTTPException:
            return None

    async def clear_debt_role(self, uid):
        """Takes the debt role away (in every server) once nothing is overdue anymore."""
        if still_overdue(uid):
            return
        for guild in self.bot.guilds:
            member = guild.get_member(uid)
            if member is None:
                continue
            shame = [r for r in member.roles if r.name in debt_role_names()]
            if not shame:
                continue
            try:
                await member.remove_roles(*shame, reason="Debt paid / forgiven")
                for role in shame:  # tidy up empty debt roles
                    if self.bot.intents.members and not role.members:
                        await role.delete(reason="Nobody's in debt with this name anymore")
            except discord.HTTPException:
                pass

    async def announce(self, guild_id, text):
        guild = self.bot.get_guild(guild_id or 0)
        if not guild:
            return
        for cid in sorted(bank.channels(guild.id)) or []:
            channel = guild.get_channel(cid)
            if channel:
                try:
                    await channel.send(text)
                    return
                except discord.HTTPException:
                    pass

    @tasks.loop(minutes=2)
    async def checker(self):
        now = time.time()
        data = loans()
        for uid, l in list(data["bank"].items()):
            if not l["overdue"] and l["due"] < now:
                l["overdue"] = True
                save()
                role = await self.give_debt_role(l.get("guild"), int(uid))
                await self.announce(l.get("guild"), f"🦈 <@{uid}> didn't pay back the bank ({coins(l['owed'])}). "
                                                    + (f"Enjoy your new role: **{role}** 😂" if role else "Shame! 🔔"))
        for l in data["friends"]:
            if not l["overdue"] and l["due"] < now:
                l["overdue"] = True
                save()
                role = await self.give_debt_role(l.get("guild"), l["borrower"])
                await self.announce(l.get("guild"), f"🦈 <@{l['borrower']}> owes <@{l['lender']}> {coins(l['owed'])} and "
                                                    f"missed the deadline. " + (f"New role: **{role}** 😂" if role else ""))

    @checker.before_loop
    async def before(self):
        await self.bot.wait_until_ready()

    # ---------- bank loans ----------
    loan = app_commands.Group(name="loan", description="🏦 Borrow coins from the bank", guild_only=True)

    @loan.command(name="take", description="Borrow coins from the bank (pay back with interest)")
    async def take(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1]):
        uid = str(interaction.user.id)
        if uid in loans()["bank"]:
            return await oops(interaction, "🏦 You already have a bank loan. Pay it off first with `/loan pay`.")
        most = limit_for(interaction.user.id)
        if amount > most:
            return await oops(interaction, f"🏦 The bank will only lend you up to {coins(most)}. Play more to raise your limit!")
        interest = S("LOAN_INTEREST", 10)
        days = S("LOAN_DAYS", 3)
        owed = math.ceil(amount * (1 + interest / 100))
        loans()["bank"][uid] = {"amount": amount, "owed": owed, "due": time.time() + days * DAY,
                                "guild": interaction.guild_id, "overdue": False}
        bank.add(interaction.user.id, amount)
        save()
        embed = discord.Embed(title="🏦 Loan approved", color=GOLD,
                              description=f"You got **{coins(amount)}**.\nPay back **{coins(owed)}** ({interest}% interest) "
                                          f"within **{days} days** with `/loan pay`.\n-# Miss it and you get a special role 🦈")
        await interaction.response.send_message(embed=embed)

    @loan.command(name="pay", description="Pay back the bank (leave empty to pay as much as you can)")
    async def pay(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1] = None):
        uid = str(interaction.user.id)
        l = loans()["bank"].get(uid)
        if not l:
            return await oops(interaction, "🏦 You don't owe the bank anything. 😇")
        paying = min(l["owed"], amount or l["owed"], bank.balance(interaction.user.id))
        if paying <= 0:
            return await oops(interaction, "💸 You're broke. Try `/daily` first.")
        bank.take(interaction.user.id, paying)
        l["owed"] -= paying
        if l["owed"] <= 0:
            loans()["bank"].pop(uid)
            save()
            await interaction.response.send_message(f"🎉 {interaction.user.mention} paid off their bank loan! Debt-free. 🕊️")
            await self.clear_debt_role(interaction.user.id)
        else:
            save()
            await interaction.response.send_message(f"🏦 Paid {coins(paying)}. Still owe {coins(l['owed'])} ({due_text(l['due'])}).")

    @loan.command(name="status", description="What you owe and who owes you")
    async def status(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        data, lines = loans(), []
        b = data["bank"].get(str(user.id))
        if b:
            lines.append(f"🏦 **Bank:** owes {coins(b['owed'])} · {due_text(b['due'])}")
        for l in data["friends"]:
            if l["borrower"] == user.id:
                lines.append(f"📤 Owes <@{l['lender']}> {coins(l['owed'])} · {due_text(l['due'])}")
        for l in data["friends"]:
            if l["lender"] == user.id:
                lines.append(f"📥 <@{l['borrower']}> owes them {coins(l['owed'])} · {due_text(l['due'])}")
        if user.id == interaction.user.id and not b:
            lines.append(f"-# You can borrow up to {coins(limit_for(user.id))} from the bank with `/loan take`")
        embed = discord.Embed(title=f"🧾 {user.display_name}'s debts", color=RED if still_overdue(user.id) else GREEN,
                              description="\n".join(lines) or "Debt-free! 🕊️")
        await interaction.response.send_message(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    # ---------- friend loans ----------
    @app_commands.command(name="lend", description="🤝 Offer to lend coins to someone (they pay you back with interest)")
    @app_commands.describe(user="Who you're lending to", amount="How much", interest="Extra % they pay back",
                           days="Days they have to pay you back")
    @app_commands.guild_only()
    async def lend(self, interaction: discord.Interaction, user: discord.Member, amount: app_commands.Range[int, 1],
                   interest: app_commands.Range[int, 0, 100] = 10, days: app_commands.Range[int, 1, 30] = 3):
        if user.bot or user.id == interaction.user.id:
            return await oops(interaction, "🤨 Pick a real person.")
        interest = min(interest, S("LEND_MAX_INTEREST", 50))
        if bank.balance(interaction.user.id) < amount:
            return await oops(interaction, f"💸 You only have {coins(bank.balance(interaction.user.id))}.")
        owed = math.ceil(amount * (1 + interest / 100))
        view = LendOffer(interaction.user, user, amount, interest, days)
        embed = discord.Embed(title="🤝 Loan offer", color=GOLD,
                              description=f"{interaction.user.mention} offers {user.mention} **{coins(amount)}**.\n"
                                          f"Pay back **{coins(owed)}** ({interest}% interest) within **{days} days**.\n"
                                          f"-# Miss the deadline = debt role 🦈")
        await interaction.response.send_message(content=user.mention, embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="repay", description="💸 Pay back someone who lent you coins")
    @app_commands.describe(user="Who you owe", amount="How much (empty = as much as you can)")
    @app_commands.guild_only()
    async def repay(self, interaction: discord.Interaction, user: discord.Member, amount: app_commands.Range[int, 1] = None):
        mine = sorted([l for l in loans()["friends"] if l["borrower"] == interaction.user.id and l["lender"] == user.id],
                      key=lambda l: l["due"])
        if not mine:
            return await oops(interaction, f"🤷 You don't owe {user.display_name} anything.")
        left = min(amount or sum(l["owed"] for l in mine), bank.balance(interaction.user.id))
        if left <= 0:
            return await oops(interaction, "💸 You're broke. Try `/daily` first.")
        paid = 0
        for l in mine:
            part = min(left, l["owed"])
            l["owed"] -= part
            left -= part
            paid += part
            if l["owed"] <= 0:
                loans()["friends"].remove(l)
            if left <= 0:
                break
        bank.take(interaction.user.id, paid)
        bank.add(user.id, paid)
        save()
        still = sum(l["owed"] for l in loans()["friends"] if l["borrower"] == interaction.user.id and l["lender"] == user.id)
        await interaction.response.send_message(
            f"💸 {interaction.user.mention} paid {user.mention} **{coins(paid)}**. "
            + (f"Still owes {coins(still)}." if still else "All paid off! 🎉"))
        await self.clear_debt_role(interaction.user.id)

    @app_commands.command(name="forgive", description="🕊️ Cancel what someone owes you (admins: cancel ALL their debts)")
    @app_commands.guild_only()
    async def forgive(self, interaction: discord.Interaction, user: discord.Member):
        admin = interaction.user.guild_permissions.manage_guild
        data = loans()
        before = len(data["friends"]) + (str(user.id) in data["bank"])
        data["friends"] = [l for l in data["friends"]
                           if not (l["borrower"] == user.id and (admin or l["lender"] == interaction.user.id))]
        if admin:
            data["bank"].pop(str(user.id), None)
        if len(data["friends"]) + (str(user.id) in data["bank"]) == before:
            return await oops(interaction, f"🤷 {user.display_name} doesn't owe {'anything' if admin else 'you anything'}.")
        save()
        await interaction.response.send_message(
            f"🕊️ {interaction.user.mention} forgave {user.mention}'s {'debts' if admin else 'debt to them'}. How generous!")
        await self.clear_debt_role(user.id)


async def setup(bot):
    await bot.add_cog(Loans(bot))
