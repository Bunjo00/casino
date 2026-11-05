"""💰 Wallet, daily/weekly, giving, leaderboards, profile, the role shop, the games menu and admin tools."""
import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..bank import bank
from ..ui import GOLD, GREEN, PURPLE, coins, oops

GAMES = """**🎰 Casino**
`/blackjack` 🃏 beat the dealer · `/slots` 🎰 spin the machine · `/spin` 🎡 roulette wheel
`/coinflip` 🪙 heads or tails · `/duel` ⚔️ 1v1 a friend · `/highlow` 🃏 higher or lower streak
`/crash` 📈 cash out before it explodes · `/mines` 💣 gems or bombs · `/scratch` 🎟️ scratch cards
**🪓 Guillotine**
`/roulette` 50/50 trial, survive for coins · `/execute` (mods) · `/pardon` (mods) · `/graveyard`
**🎲 Role Roller**
`/reroll` random role name + color · `/ratings` best & worst names · `/cooldown` (admins)
**🧊 Icebreakers**
`/question` random question, would you rather or this or that · `/icebreaker setup` (admins)
**🎉 Party**
`/truthordare` · `/wouldyourather` · `/rob` 🦹 steal coins (might backfire)
**💰 Money**
`/balance` · `/daily` · `/weekly` · `/give` · `/leaderboard` · `/profile` · `/shop` · `/buy`
-# Bets: type a number, `5k`, `half` or `all`"""


def shop_role(guild, item):
    return discord.utils.get(guild.roles, name=item["name"])


class Economy(commands.Cog):
    @app_commands.command(name="games", description="🎮 Everything you can play")
    async def games(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🎮 The Casino", description=GAMES, color=PURPLE)
        embed.set_footer(text=f"Your balance: {bank.balance(interaction.user.id):,} coins")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="balance", description="💰 Check your coins")
    @app_commands.describe(user="Check someone else's wallet")
    async def balance(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        rank = bank.rank(user.id)
        embed = discord.Embed(title=f"💰 {user.display_name}'s wallet", description=f"## {coins(bank.balance(user.id))}", color=GOLD)
        if rank:
            embed.set_footer(text=f"#{rank} richest")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="daily", description="🎁 Free coins every day (bigger with a streak)")
    async def daily(self, interaction: discord.Interaction):
        left, amount, streak = bank.claim(interaction.user.id, "daily")
        if left:
            h, m = divmod(left // 60, 60)
            return await oops(interaction, f"⏰ Come back in **{h}h {m}m**. Your streak: 🔥 {streak}")
        bonus = f"\n🔥 **{streak}-day streak!**" + (" (max bonus)" if streak >= 7 else " Come back tomorrow for more.") if streak > 1 else \
            "\n🔥 Claim every day to build a streak bonus!"
        await interaction.response.send_message(
            f"🎁 You claimed {coins(amount)}! Balance: {coins(bank.balance(interaction.user.id))}{bonus}")

    @app_commands.command(name="weekly", description="📦 A big pile of free coins every week")
    async def weekly(self, interaction: discord.Interaction):
        left, amount, _ = bank.claim(interaction.user.id, "weekly")
        if left:
            d, rest = divmod(left, 86400)
            return await oops(interaction, f"⏰ Next weekly in **{d}d {rest // 3600}h**.")
        await interaction.response.send_message(f"📦 Weekly crate opened: {coins(amount)}! Balance: {coins(bank.balance(interaction.user.id))}")

    @app_commands.command(name="give", description="🤝 Give coins to someone")
    async def give(self, interaction: discord.Interaction, user: discord.Member, amount: app_commands.Range[int, 1]):
        if user.bot or user.id == interaction.user.id:
            return await oops(interaction, "🤨 You can't give coins to that user.")
        if not bank.take(interaction.user.id, amount):
            return await oops(interaction, "💸 You don't have that many coins.")
        bank.add(user.id, amount)
        await interaction.response.send_message(f"🤝 {interaction.user.mention} gave {coins(amount)} to {user.mention}!")

    @app_commands.command(name="leaderboard", description="🏆 The top players")
    @app_commands.describe(by="What to rank by")
    @app_commands.choices(by=[app_commands.Choice(name="💰 Richest", value="balance"),
                              app_commands.Choice(name="🏅 Most wins", value="wins"),
                              app_commands.Choice(name="💥 Biggest single win", value="biggest"),
                              app_commands.Choice(name="📈 Total won", value="won")])
    async def leaderboard(self, interaction: discord.Interaction, by: app_commands.Choice[str] = None):
        key = by.value if by else "balance"
        rows = [r for r in bank.top(key) if r[1].get(key, 0) > 0]
        if not rows:
            return await interaction.response.send_message("Nobody's on the board yet! `/games` to start.")
        medals = ["🥇", "🥈", "🥉"]
        show = (lambda v: coins(v)) if key != "wins" else (lambda v: f"{v:,} wins")
        lines = [f"{medals[i] if i < 3 else f'`#{i + 1}`'} <@{uid}>: {show(u[key])}" for i, (uid, u) in enumerate(rows)]
        title = {"balance": "💰 Richest players", "wins": "🏅 Most wins", "biggest": "💥 Biggest wins", "won": "📈 Total won"}[key]
        await interaction.response.send_message(embed=discord.Embed(title=title, description="\n".join(lines), color=GOLD),
                                                allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name="profile", description="🪪 Your casino stats")
    @app_commands.describe(user="See someone else's profile")
    async def profile(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        u = bank.user(user.id)
        grave = bank.data["graveyard"].get(str(interaction.guild_id), {}).get(str(user.id), {})
        winrate = f"{u['wins'] / u['games'] * 100:.0f}%" if u["games"] else "-"
        net = u["won"] - u["lost"]
        roles = [item["name"] for item in config.SHOP if any(r.name == item["name"] for r in getattr(user, "roles", []))]
        embed = discord.Embed(title=f"🪪 {user.display_name}", color=user.color if user.color.value else PURPLE)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="💰 Balance", value=f"{coins(u['balance'])}\n#{bank.rank(user.id) or '?'} richest")
        embed.add_field(name="🎮 Games", value=f"{u['games']:,} played\n{u['wins']:,} won ({winrate})")
        embed.add_field(name="📈 Profit", value=f"{'+' if net >= 0 else ''}{net:,}\nbest win {u['biggest']:,}")
        embed.add_field(name="🔥 Daily streak", value=str(u["streak"]))
        embed.add_field(name="🪓 Guillotine", value=f"☠️ {grave.get('deaths', 0)} · 🍀 {grave.get('survivals', 0)}")
        embed.add_field(name="🎖️ Roles", value="\n".join(roles) or "none yet, `/shop`", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="shop", description="🛒 Special roles you can buy")
    async def shop(self, interaction: discord.Interaction):
        owned = {r.name for r in getattr(interaction.user, "roles", [])}
        embed = discord.Embed(title="🛒 Role Shop", color=PURPLE,
                              description=f"Your balance: {coins(bank.balance(interaction.user.id))}\nBuy with `/buy`")
        for item in config.SHOP:
            embed.add_field(name=item["name"], value="✅ Owned" if item["name"] in owned else coins(item["price"]), inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="buy", description="🛍️ Buy a special role")
    @app_commands.describe(role="The role you want")
    @app_commands.choices(role=[app_commands.Choice(name=f"{item['name']} · {item['price']:,} coins", value=i)
                                for i, item in enumerate(config.SHOP[:25])])
    async def buy(self, interaction: discord.Interaction, role: app_commands.Choice[int]):
        if interaction.guild is None:
            return await oops(interaction, "Use this in a server!")
        item, member, guild = config.SHOP[role.value], interaction.user, interaction.guild
        existing = shop_role(guild, item)
        if existing and existing in member.roles:
            return await oops(interaction, "😎 You already own that role!")
        if bank.balance(member.id) < item["price"]:
            need = item["price"] - bank.balance(member.id)
            return await oops(interaction, f"💸 You need {coins(need)} more for **{item['name']}**. Hit the tables!")
        if existing and existing >= guild.me.top_role:
            return await oops(interaction, "⚠️ That role is above mine. An admin needs to drag my role **above** the shop roles.")
        try:
            if existing is None:
                existing = await guild.create_role(name=item["name"], colour=discord.Colour(item["color"]), hoist=True,
                                                   reason="Casino shop role")
            await member.add_roles(existing, reason="Bought in the casino shop")
        except discord.Forbidden:
            return await oops(interaction, "⚠️ I can't give roles. An admin needs to give me **Manage Roles** and drag my role "
                                           "**above** the shop roles.")
        bank.take(member.id, item["price"])
        await interaction.response.send_message(f"🎉 {member.mention} bought **{item['name']}**! Left: {coins(bank.balance(member.id))}")

    # ---------- admin ----------
    casino = app_commands.Group(name="casino", description="⚙️ Casino settings (admins)",
                                default_permissions=discord.Permissions(manage_guild=True), guild_only=True)

    @casino.command(name="channel", description="Choose where games can be played")
    @app_commands.describe(action="add = games work here too · remove · list · everywhere")
    @app_commands.choices(action=[app_commands.Choice(name=n, value=n) for n in ("add", "remove", "list", "everywhere")])
    async def channel(self, interaction: discord.Interaction, action: app_commands.Choice[str],
                      channel: discord.TextChannel = None):
        gid, act = interaction.guild_id, action.value
        target = channel or interaction.channel
        if act == "add":
            bank.set_channel(gid, target.id, True)
        elif act == "remove":
            bank.set_channel(gid, target.id, False)
        elif act == "everywhere":
            bank.data["channels"][str(gid)] = []
            bank.dirty = True
        now = bank.channels(gid)
        where = ", ".join(f"<#{c}>" for c in sorted(now)) if now else "**every channel**"
        await interaction.response.send_message(f"🎰 Games now work in: {where}", ephemeral=True)

    @casino.command(name="coins", description="Give or take someone's coins (use a minus number to take)")
    async def admin_coins(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        bank.add(user.id, max(amount, -bank.balance(user.id)))
        await interaction.response.send_message(
            f"🏦 {'Added' if amount >= 0 else 'Took'} {coins(abs(amount))} {'to' if amount >= 0 else 'from'} {user.mention}. "
            f"New balance: {coins(bank.balance(user.id))}", allowed_mentions=discord.AllowedMentions.none())


async def setup(bot):
    await bot.add_cog(Economy())
