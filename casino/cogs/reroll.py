"""🎲 Role Roller: /reroll gives you a personal role with a random funny name and color (your original bot).
New: if you're on cooldown, you can pay coins to reroll right away."""
import random
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

from .. import config
from ..bank import bank
from ..ui import coins, oops

DEFAULT_COOLDOWN = 24 * 60 * 60
SKIP_PRICE = getattr(config, "REROLL_SKIP_PRICE", 500)  # coins to skip the cooldown (0 = off)

NAME_POOLS = {
    "Noble": [
        "Duke Reginald", "Lord Percival", "Baroness Wilhelmina", "Count Bartholomew",
        "Sir Cedric the Bold", "Lady Genevieve", "Marquess of Mudshire", "Viscount Fancypants",
        "Duchess Evangeline", "Prince Lucian", "Princess Seraphina", "Lord Montgomery III",
        "Countess Ophelia", "Baron von Snobbington", "Grand Duke Augustus", "Lord Ashford",
        "Dame Beatrice", "Margrave Otto", "His Excellency Humphrey", "Sir Reginald Pumpernickel",
        "The Lord Protector", "Archduchess Isolde", "Earl of Crumpetshire", "Lady Rosalind",
        "Baron Silverspoon",
    ],
    "Peasant": [
        "Turnip Farmer", "Mud Collector", "Village Idiot", "Bob the Blacksmith", "Humble Shepherd",
        "Dung Shoveler", "Peasant #47", "Barley Thresher", "Goose Herder", "Rat Catcher",
        "Lowly Serf", "Town Crier", "Chimney Sweep", "Potato Peasant", "Mead Brewer",
        "Plague Survivor", "Ye Olde Beggar", "Swineherd Greg", "Muck Raker", "Cabbage Merchant",
        "Apprentice Cobbler", "Stable Boy", "Firewood Gatherer", "Taxed Into Oblivion",
        "Owner of One Chicken",
    ],
    "Walter Black": [
        "Walter Black", "Walter Grey", "Gerald Purple", "Harold Beige", "Norman Teal",
        "Clarence Crimson", "Herbert Green", "Stanley Magenta", "Bernard Orange", "Leonard Brown",
        "Eugene Indigo", "Mildred Silver", "Gertrude Pink", "Doris Maroon", "Edna Turquoise",
        "Walter Yellow", "Frank Lavender", "Martha Olive", "Arthur Scarlet", "Howard Navy",
        "Dolores Cyan", "Vernon Gold", "Agnes Violet", "Ernest Charcoal", "Walter Plaid",
    ],
    "Mythological": [
        "Zeus", "Hades", "Poseidon", "Athena", "Loki", "Thor", "Odin", "Anubis", "Ra",
        "Medusa", "Hercules", "Achilles", "Fenrir", "Quetzalcoatl", "Amaterasu", "Susanoo",
        "Persephone", "Cerberus", "Minotaur", "Kitsune", "Baba Yaga", "Gilgamesh", "Freya",
        "Osiris", "The Morrigan",
    ],
    "Game Character": [
        "Mario", "Link", "Kratos", "Master Chief", "Geralt of Rivia", "Lara Croft", "Sonic",
        "Pikachu", "Steve", "Creeper", "Solid Snake", "Doomguy", "Cloud Strife", "Samus Aran",
        "Arthur Morgan", "Ezio Auditore", "GLaDOS", "Pac-Man", "Kirby", "Donkey Kong",
        "Gordon Freeman", "Sans", "Dante", "Joel Miller", "Aloy",
    ],
    "Goblin": [
        "Goblin Boss", "Hobgoblin Captain", "Bugbear Brute", "Goblin Shaman", "Worg Rider",
        "Kobold Trapmaker", "Snaggletooth", "Grubnik", "Skrix the Sneaky", "Nilbog", "Mudgrub",
        "Gnarlwart", "Stinkfoot", "Rotgut", "Zixxle", "Gribble", "Snot Goblin", "Splug",
        "Yeemik", "King Grol", "Klarg", "Toadbelly", "Wartnose the Wise", "Shiny Collector",
        "Goblin With a Spoon",
    ],
    "Movie & TV": [
        "Walter White", "Jesse Pinkman", "Saul Goodman", "Tony Soprano", "Michael Scott",
        "Dwight Schrute", "Sherlock Holmes", "Darth Vader", "Yoda", "Gandalf", "Frodo Baggins",
        "Gollum", "Jack Sparrow", "Shrek", "Homer Simpson", "Rick Sanchez", "SpongeBob",
        "Tyrion Lannister", "Jon Snow", "Eleven", "Thomas Shelby", "John Wick", "Forrest Gump",
        "Joey Tribbiani", "Barney Stinson",
    ],
}

QUIPS = {
    "Noble": ["👑 Bow, peasants. **{name}** has entered the court.",
              "🍷 The royal scrolls declare you **{name}**. Pinky up.",
              "🏰 You inherited a castle, three goats, and the title **{name}**."],
    "Peasant": ["🥔 Congratulations, you are now **{name}**. Your hut has no roof.",
                "🌾 The dice have spoken. You are **{name}**, and you smell like cabbage.",
                "💀 Tax collectors are on their way, **{name}**."],
    "Walter Black": ["☕ Please welcome **{name}**, who has strong opinions about the weather.",
                     "📰 **{name}** has arrived and wants to talk about lawn care.",
                     "🧓 **{name}** remembers when all this was fields."],
    "Mythological": ["⚡ The heavens tremble. You are now **{name}**.",
                     "🏛️ Ancient scrolls foretold your coming, **{name}**.",
                     "🔥 Mortals, kneel before **{name}**."],
    "Game Character": ["🎮 Player 1 has joined as **{name}**.",
                       "💾 Loading save file... you are **{name}**.",
                       "🕹️ A wild **{name}** appeared!"],
    "Goblin": ["👺 You crawled out of a cave as **{name}**. Shiny things beware.",
               "🗡️ **{name}** has stolen your boots and your dignity.",
               "🪨 You are **{name}** now. Hehehe."],
    "Movie & TV": ["🎬 And starring as **{name}**... you!",
                   "🍿 Plot twist: you are **{name}**.",
                   "📺 Previously on this server... **{name}** was born."],
}


# ---------- storage (inside casino.json, same layout as the old roles.json) ----------
def data():
    return bank.data.setdefault("reroll", {})


def save():
    bank.dirty = True


def get_entry(gid, uid):
    return data().setdefault(str(gid), {}).setdefault(str(uid), {})


def get_cooldown(gid):
    return data().get("cooldowns", {}).get(str(gid), DEFAULT_COOLDOWN)


# ---------- ratings ----------
def get_votes(gid, name):
    return data().setdefault("ratings", {}).setdefault(str(gid), {}).setdefault(name, {})


def get_score(gid, name):
    return sum(data().get("ratings", {}).get(str(gid), {}).get(name, {}).values())


def get_weight(gid, name):
    # each like = ~25% more likely, each dislike = ~20% less likely, capped both ways
    return min(10.0, max(0.05, 1.25 ** get_score(gid, name)))


def pick_name(gid, current=None):
    category = random.choice(list(NAME_POOLS))
    pool = [n for n in NAME_POOLS[category] if n != current] or NAME_POOLS[category]
    name = random.choices(pool, weights=[get_weight(gid, n) for n in pool])[0]
    return name, category


class RateView(discord.ui.View):
    def __init__(self, gid, name):
        super().__init__(timeout=6 * 3600)
        self.gid, self.name = gid, name

    async def vote(self, interaction, value):
        votes = get_votes(self.gid, self.name)
        uid = str(interaction.user.id)
        if votes.get(uid) == value:
            votes.pop(uid)
            msg = "Vote removed for"
        else:
            votes[uid] = value
            msg = "👍 You liked" if value > 0 else "👎 You disliked"
        save()
        await interaction.response.send_message(
            f"{msg} **{self.name}**. Score: {get_score(self.gid, self.name):+d} "
            f"({get_weight(self.gid, self.name):.2f}x chance)", ephemeral=True)

    @discord.ui.button(emoji="👍", style=discord.ButtonStyle.success)
    async def like(self, interaction, button):
        await self.vote(interaction, 1)

    @discord.ui.button(emoji="👎", style=discord.ButtonStyle.danger)
    async def dislike(self, interaction, button):
        await self.vote(interaction, -1)


class SkipView(discord.ui.View):
    """On cooldown? Pay coins to reroll now."""

    def __init__(self, cog, user):
        super().__init__(timeout=60)
        self.cog, self.user = cog, user
        self.pay.label = f"Reroll now for {SKIP_PRICE:,} coins"

    @discord.ui.button(emoji="🪙", style=discord.ButtonStyle.blurple)
    async def pay(self, interaction, button):
        if interaction.user.id != self.user.id:
            return await oops(interaction, "🙅 Not your button!")
        if not bank.take(self.user.id, SKIP_PRICE):
            return await oops(interaction, f"💸 You need {coins(SKIP_PRICE)}. Try `/daily`.")
        self.stop()
        await interaction.response.edit_message(content=f"🪙 Paid {coins(SKIP_PRICE)}, rerolling...", view=None)
        if not await self.cog.do_reroll(interaction):
            bank.add(self.user.id, SKIP_PRICE)  # it failed: refund


class Reroll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.cleanup.start()

    async def cog_unload(self):
        self.cleanup.cancel()

    async def delete_role(self, guild, uid):
        entry = data().get(str(guild.id), {}).get(str(uid))
        if not entry or "role_id" not in entry:
            return
        role = guild.get_role(entry.pop("role_id"))
        if role:
            try:
                await role.delete(reason="Personal role cleanup")
            except discord.HTTPException:
                pass
        save()

    @tasks.loop(hours=1)
    async def cleanup(self):
        if not self.bot.intents.members:
            return  # (can't see who has which role without the Server Members intent)
        for guild in self.bot.guilds:
            for uid, entry in list(data().get(str(guild.id), {}).items()):
                if not isinstance(entry, dict) or "role_id" not in entry:
                    continue
                role = guild.get_role(entry["role_id"])
                if role is None or not role.members:
                    await self.delete_role(guild, uid)

    @cleanup.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await self.delete_role(member.guild, member.id)

    async def do_reroll(self, interaction):
        """Gives/changes the role and announces it (the interaction must already be answered). True if it worked."""
        guild, user = interaction.guild, interaction.user
        entry = get_entry(guild.id, user.id)
        role = guild.get_role(entry.get("role_id", 0))
        name, cat = pick_name(guild.id, current=role.name if role else None)
        color = discord.Color(random.randint(1, 0xFFFFFF))  # 0 = no color, so start at 1
        try:
            if role:
                await role.edit(name=name, color=color)
            else:
                role = await guild.create_role(name=name, color=color, reason="Reroll")
                entry["role_id"] = role.id
                save()
                pos = guild.me.top_role.position - 1
                if pos > 0:
                    await role.edit(position=pos)
            if role not in user.roles:
                await user.add_roles(role)
        except discord.Forbidden:
            await interaction.followup.send("❌ I need **Manage Roles**, and my role must be above the reroll roles.")
            return False
        except discord.HTTPException:
            await interaction.followup.send("❌ Discord error, try again in a moment.")
            return False
        entry.update(role_id=role.id, last=time.time())
        save()
        quip = random.choice(QUIPS[cat]).format(name=name)
        await interaction.followup.send(f"{user.mention} {quip}\n-# Rate this name:", view=RateView(guild.id, name),
                                        allowed_mentions=discord.AllowedMentions.none())
        return True

    @app_commands.command(name="reroll", description="🎲 Get a random role name and color")
    @app_commands.guild_only()
    async def reroll(self, interaction: discord.Interaction):
        entry = get_entry(interaction.guild_id, interaction.user.id)
        left = get_cooldown(interaction.guild_id) - (time.time() - entry.get("last", 0))
        if left > 0:
            h, m = int(left // 3600), int(left % 3600 // 60)
            if SKIP_PRICE:
                return await interaction.response.send_message(f"⏳ You can reroll in {h}h {m}m... or skip the wait:",
                                                               view=SkipView(self, interaction.user), ephemeral=True)
            return await oops(interaction, f"⏳ You can reroll in {h}h {m}m.")
        await interaction.response.defer()
        await self.do_reroll(interaction)

    @app_commands.command(name="ratings", description="📊 See the most liked and disliked role names")
    @app_commands.guild_only()
    async def ratings(self, interaction: discord.Interaction):
        guild_ratings = data().get("ratings", {}).get(str(interaction.guild_id), {})
        scores = {n: sum(v.values()) for n, v in guild_ratings.items() if v}
        if not scores:
            return await oops(interaction, "No names have been rated yet.")
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        liked = [f"`{s:+d}` {n}" for n, s in ranked if s > 0][:10]
        disliked = [f"`{s:+d}` {n}" for n, s in reversed(ranked) if s < 0][:10]
        embed = discord.Embed(title="📊 Name Ratings", color=discord.Color.blurple())
        embed.add_field(name="👍 Most liked", value="\n".join(liked) or "None yet")
        embed.add_field(name="👎 Most disliked", value="\n".join(disliked) or "None yet")
        await interaction.response.send_message(embed=embed)

    cooldown = app_commands.Group(name="cooldown", description="Manage the reroll cooldown",
                                  default_permissions=discord.Permissions(manage_guild=True), guild_only=True)

    @cooldown.command(name="set", description="Set how long users wait between rerolls")
    async def cd_set(self, interaction: discord.Interaction, hours: app_commands.Range[int, 0, 720] = 0,
                     minutes: app_commands.Range[int, 0, 59] = 0):
        data().setdefault("cooldowns", {})[str(interaction.guild_id)] = hours * 3600 + minutes * 60
        save()
        await interaction.response.send_message(f"✅ Cooldown set to {hours}h {minutes}m.", ephemeral=True)

    @cooldown.command(name="default", description="Restore the default cooldown (24h)")
    async def cd_default(self, interaction: discord.Interaction):
        data().get("cooldowns", {}).pop(str(interaction.guild_id), None)
        save()
        await interaction.response.send_message("✅ Cooldown back to default (24h).", ephemeral=True)

    @cooldown.command(name="reset", description="Let a user (or everyone) reroll right now")
    async def cd_reset(self, interaction: discord.Interaction, user: discord.Member = None):
        users = data().get(str(interaction.guild_id), {})
        if user:
            users.get(str(user.id), {}).pop("last", None)
            msg = f"✅ {user.mention} can reroll now."
        else:
            for entry in users.values():
                if isinstance(entry, dict):
                    entry.pop("last", None)
            msg = "✅ Everyone can reroll now."
        save()
        await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Reroll(bot))
