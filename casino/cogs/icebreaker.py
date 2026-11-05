"""🧊 Icebreakers & Question of the Hour

- Welcomes new members with a fun question they can answer (+ welcome coins).
- Every hour (ICE_EVERY_MINUTES) posts a question, Would You Rather, or This or That in your channel.
- Nobody answers? It roasts the silence (crickets.txt). Ignored 3 times? It naps until someone talks.

EVERYTHING you might want to change is in:
  settings.py              -> the ICE_ settings (how often, quiet hours, rewards, roasts on/off, the mix)
  prompts/ folder          -> the text files below (one line each, lines starting with # are ignored)
      questions.txt          random questions for the hourly post
      icebreakers.txt        questions for new members
      this_or_that.txt       "Pizza | Burger"
      would_you_rather.txt   "A | B"  (shared with /wouldyourather)
      welcomes.txt           welcome lines, {user} = the new person
      crickets.txt           when nobody answers: {member} = someone from chat, {answer} = the bot's own answer
      naps.txt               when it gives up and pauses
      my_answers.txt         the bot's own silly answers to open questions
Adding a whole new KIND of post: write a function like post_question() below and add it to KINDS.
"""
import os
import random
import time
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from .. import config
from ..bank import bank
from ..ui import coins, oops

S = lambda name, default: getattr(config, name, default)  # noqa: E731  (reads a setting, with a default)

# ---------------------------------------------------------------- default texts (copied into prompts/ once)
DEFAULT_FILES = {
    "questions.txt": """# Random questions for the hourly post. One per line.
What's the worst food combo you secretly love?
What's a hill you will die on?
What game would you delete from existence?
What's your most controversial opinion about pizza?
If you could master one skill instantly, what would it be?
What's the most useless thing you own but refuse to throw away?
What's a smell that instantly takes you back to childhood?
What's the best thing you've ever eaten at 3am?
If your life was a video game, what would the loading screen tip be?
What's something everyone loves that you think is overrated?
What's the weirdest thing you've ever Googled?
If animals could talk, which one would be the rudest?
What's your go-to karaoke song?
What would your villain name be?
What's the best purchase you've made under 50 dirhams?
Which fictional world would you live in?
What's your toxic gaming trait?
What's the funniest thing that happened to you this week?
If you had to eat one meal forever, what is it?
What's an app you'd delete from everyone's phone?""",
    "icebreakers.txt": """# Questions for new members. One per line.
What game could you play forever?
What's your comfort food?
Night owl or early bird?
What's the last show you binged?
What's your main in your favourite game?
If you could teleport anywhere right now, where?
Cats, dogs, or chaos?
What's a fun fact about you?
How did you find this server?
What's your favourite emoji and why?""",
    "this_or_that.txt": """# This or That. Format:  Option A | Option B
🍕 Pizza | 🍔 Burger
☀️ Summer | ❄️ Winter
🎮 PC | 🕹️ Console
🌅 Sunrise | 🌇 Sunset
☕ Coffee | 🧋 Bubble tea
🐱 Cats | 🐶 Dogs
🎬 Movies | 📺 Series
🏖️ Beach | 🏔️ Mountains
🍫 Sweet | 🧂 Salty
🎧 Headphones | 🔊 Speakers
📱 Call | 💬 Text
🌙 Night | 🌞 Day
🍟 Fries | 🧅 Onion rings
🧙 Wizard | 🦸 Superhero""",
    "welcomes.txt": """# Welcome lines. {user} = the new member.
👋 Everyone act normal, {user} just joined!
🎉 A wild {user} appeared!
🚪 {user} walked in. Somebody hide the snacks.
🌟 Welcome {user}! We were just talking about you (we weren't).
🎰 {user} has entered the casino. The house says hi.""",
    "crickets.txt": """# When nobody answers. {member} = someone who chatted recently (only if roasts are on), {answer} = the bot's own answer.
🦗 *crickets*... fine, I'll answer it myself: {answer}.
Wow. 0 answers. I'm telling my mom.
I asked a question and the server said "seen". 💀
🦗 The silence is so loud I can hear {member} breathing.
{member} I KNOW you're online. Answer the question.
This chat has the energy of a Monday morning.
📉 Engagement levels: critical. Even {member} is ignoring me.
I'll just answer it myself then. {answer}. Riveting stuff, thanks guys.
Hello? Is this thing on? 🎤 *taps mic*
{member} is typing... no they're not. Nobody is. 😔""",
    "naps.txt": """# When it gets ignored too many times and pauses (until someone talks again).
😴 Fine. I'm taking a nap. Wake me up when you're interesting.
🛌 3 questions, 0 answers. I'm going to bed. Say anything to wake me up.
💤 Clearly you're all busy. I'll be in my room.""",
    "my_answers.txt": """# The bot's own answers when nobody else answers.
obviously pizza
whatever {member} would say, but better
I plead the fifth
probably something illegal in 3 countries
the answer is always more coins
I'd tell you but then I'd have to ban you
42
crying in the club""",
}


def _folder():
    return config.PROMPTS_FOLDER


def make_files():
    os.makedirs(_folder(), exist_ok=True)
    for name, text in DEFAULT_FILES.items():
        path = os.path.join(_folder(), name)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(text.strip() + "\n")


def lines(name):
    """The usable lines of a prompts file (re-read every time, so edits work without a restart)."""
    try:
        with open(os.path.join(_folder(), name), encoding="utf-8") as f:
            got = [l.strip() for l in f if l.strip() and not l.lstrip().startswith("#")]
    except FileNotFoundError:
        got = []
    if not got and name in DEFAULT_FILES:
        got = [l for l in DEFAULT_FILES[name].splitlines() if l.strip() and not l.startswith("#")]
    return got


_recent_picks = {}


def pick(name):
    """A random line, avoiding the last few picked."""
    options = lines(name) or ["What's on your mind?"]
    recent = _recent_picks.setdefault(name, [])
    fresh = [l for l in options if l not in recent] or options
    line = random.choice(fresh)
    recent.append(line)
    del recent[:-max(1, len(options) // 2)]
    return line


def two_options(name):
    a, _, b = pick(name).partition("|")
    return a.strip(), (b.strip() or "neither")


# ---------------------------------------------------------------- saved state (inside casino.json)
def state():
    return bank.data.setdefault("icebreaker", {"guilds": {}, "open": {}, "votes": {}, "welcomed": {}})


def guild_cfg(gid):
    return state()["guilds"].setdefault(str(gid), {"on": False, "channel": None, "welcome": None, "last": 0,
                                                    "ignored": 0, "paused": False})


def save():
    bank.dirty = True


def local_hour():
    return (datetime.now(timezone.utc) + timedelta(hours=S("ICE_UTC_OFFSET", 4))).hour


def quiet_now(cfg):
    quiet = cfg.get("quiet", S("ICE_QUIET_HOURS", (2, 10)))
    if not quiet:
        return False
    start, end = quiet
    h = local_hour()
    return start <= h < end if start < end else (h >= start or h < end)


# ---------------------------------------------------------------- the buttons (they keep working after a restart)
def bar(n, total):
    share = n / total if total else 0
    return f"{'🟦' * round(share * 10)}{'⬜' * (10 - round(share * 10))} {round(share * 100)}% ({n})"


class AnswerBox(discord.ui.Modal):
    def __init__(self, question, message):
        super().__init__(title="Your answer ✍️")
        self.message = message
        self.answer = discord.ui.TextInput(label=question[:45], style=discord.TextStyle.paragraph, max_length=300,
                                           placeholder="Type something fun...")
        self.add_item(self.answer)

    async def on_submit(self, interaction):
        o = state()["open"].get(str(self.message.id), {})
        user = interaction.user
        reward = 0
        if not o.get("first"):
            o["first"] = user.id
            reward += S("ICE_FIRST_REWARD", 25)
        if o.get("for") == user.id and not state()["welcomed"].get(str(user.id)):
            state()["welcomed"][str(user.id)] = True
            reward += S("ICE_WELCOME_REWARD", 100)
        o["answers"] = o.get("answers", 0) + 1
        guild_cfg(interaction.guild_id).update(ignored=0)
        if reward:
            bank.add(user.id, reward)
        save()
        embed = discord.Embed(description=f"💬 {self.answer.value}", color=user.color if user.color.value else 0x5865F2)
        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
        if reward:
            embed.set_footer(text=f"+{reward} coins" + (" · first answer!" if o.get("first") == user.id else ""))
        await interaction.response.defer()  # (closes the box quietly; the answer is posted as a reply below)
        await self.message.channel.send(embed=embed, reference=self.message.to_reference(fail_if_not_exists=False),
                                        mention_author=False)


class IceButtons(discord.ui.View):
    """One view for every icebreaker message. Messages only show the buttons they need."""

    def __init__(self, kind="all"):
        super().__init__(timeout=None)
        if kind == "answer":
            self.remove_item(self.a)
            self.remove_item(self.b)
        elif kind == "vote":
            self.remove_item(self.answer)

    @discord.ui.button(label="Answer", emoji="✍️", style=discord.ButtonStyle.green, custom_id="ice:answer")
    async def answer(self, interaction, button):
        question = (interaction.message.embeds[0].description or "Your answer").split("\n")[0].strip("*# ")
        await interaction.response.send_modal(AnswerBox(question, interaction.message))

    async def vote(self, interaction, side):
        mid = str(interaction.message.id)
        votes = state()["votes"].setdefault(mid, {})
        o = state()["open"].get(mid, {})
        first_vote = str(interaction.user.id) not in votes
        votes[str(interaction.user.id)] = side
        reward = 0
        if first_vote:
            o["answers"] = o.get("answers", 0) + 1
            if o and not o.get("first"):
                o["first"] = interaction.user.id
                reward = S("ICE_FIRST_REWARD", 25)
                bank.add(interaction.user.id, reward)
        guild_cfg(interaction.guild_id).update(ignored=0)
        save()
        embed = interaction.message.embeds[0]
        na = sum(v == "a" for v in votes.values())
        nb = len(votes) - na
        embed.set_field_at(0, name=embed.fields[0].name, value=bar(na, len(votes)), inline=False)
        embed.set_field_at(1, name=embed.fields[1].name, value=bar(nb, len(votes)), inline=False)
        await interaction.response.edit_message(embed=embed)
        if reward:
            await interaction.followup.send(f"⚡ First vote! +{coins(reward)}", ephemeral=True)

    @discord.ui.button(emoji="🅰️", style=discord.ButtonStyle.blurple, custom_id="ice:a")
    async def a(self, interaction, button):
        await self.vote(interaction, "a")

    @discord.ui.button(emoji="🅱️", style=discord.ButtonStyle.red, custom_id="ice:b")
    async def b(self, interaction, button):
        await self.vote(interaction, "b")


# ---------------------------------------------------------------- the kinds of posts (add your own here!)
def post_question():
    q = pick("questions.txt")
    return discord.Embed(title="❓ Question of the hour", description=f"### {q}", color=0x5865F2), "answer", q


def post_wyr():
    a, b = two_options("would_you_rather.txt")
    e = discord.Embed(title="🤷 Would you rather...", color=0x9B59B6, description="Vote with the buttons!")
    e.add_field(name=f"🅰️ {a}", value=bar(0, 0), inline=False)
    e.add_field(name=f"🅱️ {b}", value=bar(0, 0), inline=False)
    return e, "vote", f"{a} or {b}"


def post_this_or_that():
    a, b = two_options("this_or_that.txt")
    e = discord.Embed(title="⚡ This or That?", color=0xE67E22, description=f"### {a}  vs  {b}")
    e.add_field(name=f"🅰️ {a}", value=bar(0, 0), inline=False)
    e.add_field(name=f"🅱️ {b}", value=bar(0, 0), inline=False)
    return e, "vote", f"{a} or {b}"


KINDS = {"question": post_question, "wyr": post_wyr, "this_or_that": post_this_or_that}


def random_kind():
    mix = S("ICE_MIX", {"question": 3, "wyr": 2, "this_or_that": 2})
    names = [k for k in mix if k in KINDS and mix[k] > 0] or list(KINDS)
    return random.choices(names, [mix.get(k, 1) for k in names])[0]


# ---------------------------------------------------------------- the cog
class Icebreaker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.chatters = {}  # guild id -> recent people who talked (for roasts)
        make_files()

    async def cog_load(self):
        self.bot.add_view(IceButtons())  # buttons keep working after restarts
        self.ticker.start()

    async def cog_unload(self):
        self.ticker.cancel()

    async def post(self, channel, kind=None, extra=None):
        kind = kind or random_kind()
        embed, buttons, text = KINDS[kind]()
        if extra:
            embed.set_footer(text=extra)
        message = await channel.send(embed=embed, view=IceButtons(buttons))
        state()["open"][str(message.id)] = {"guild": channel.guild.id, "channel": channel.id, "time": time.time(),
                                            "answers": 0, "kind": kind, "question": text}
        save()
        return message

    def roast_line(self, gid, question):
        names = self.chatters.get(gid, [])
        roast = S("ICE_ROAST", True) and names
        options = [l for l in lines("crickets.txt") if roast or "{member}" not in l] or ["🦗 *crickets*"]
        member = random.choice(names) if names else "someone"
        answer = random.choice(question.split(" or ")) if " or " in question else pick("my_answers.txt")
        return random.choice(options).replace("{member}", member).replace("{answer}", answer.replace("{member}", member))

    @tasks.loop(minutes=1)
    async def ticker(self):
        now = time.time()
        st = state()
        # 1. roast questions nobody answered
        for mid, o in list(st["open"].items()):
            if now - o["time"] > 86400:
                st["open"].pop(mid, None)
                st["votes"].pop(mid, None)
                continue
            if o.get("answers") or o.get("roasted") or o.get("kind") == "welcome":
                continue
            if now - o["time"] < S("ICE_NO_ANSWER_MINUTES", 30) * 60:
                continue
            o["roasted"] = True
            channel = self.bot.get_channel(o["channel"])
            if not channel:
                continue
            cfg = guild_cfg(o["guild"])
            try:
                await channel.send(self.roast_line(o["guild"], o.get("question", "")),
                                   reference=discord.MessageReference(message_id=int(mid), channel_id=channel.id,
                                                                      fail_if_not_exists=False))
                if o.get("scheduled"):
                    cfg["ignored"] = cfg.get("ignored", 0) + 1
                    if cfg["ignored"] >= S("ICE_MAX_IGNORED", 3):
                        cfg["paused"] = True
                        await channel.send(pick("naps.txt"))
            except discord.HTTPException:
                pass
            save()
        # 2. time for a new question?
        for gid, cfg in st["guilds"].items():
            if not cfg.get("on") or cfg.get("paused") or quiet_now(cfg):
                continue
            if now - cfg.get("last", 0) < cfg.get("every", S("ICE_EVERY_MINUTES", 60)) * 60:
                continue
            channel = self.bot.get_channel(cfg.get("channel") or 0)
            if not channel:
                continue
            cfg["last"] = now
            try:
                message = await self.post(channel)
                st["open"][str(message.id)]["scheduled"] = True
            except discord.HTTPException as e:
                print(f"⚠️ icebreaker couldn't post: {e}")
            save()

    @ticker.before_loop
    async def before(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        names = self.chatters.setdefault(message.guild.id, [])
        if message.author.display_name in names:
            names.remove(message.author.display_name)
        names.append(message.author.display_name)
        del names[:-20]
        cfg = state()["guilds"].get(str(message.guild.id))
        if cfg and cfg.get("paused") and message.channel.id == cfg.get("channel"):
            cfg.update(paused=False, ignored=0)  # someone's alive: next question in ~2 minutes
            cfg["last"] = time.time() - cfg.get("every", S("ICE_EVERY_MINUTES", 60)) * 60 + 120
            save()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        cfg = state()["guilds"].get(str(member.guild.id))
        if not cfg or not cfg.get("on") or member.bot:
            return
        channel = self.bot.get_channel(cfg.get("welcome") or cfg.get("channel") or 0)
        if not channel:
            return
        q = pick("icebreakers.txt")
        embed = discord.Embed(title=pick("welcomes.txt").replace("{user}", member.display_name),
                              description=f"### {q}", color=0x2ECC71)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Answer it for +{S('ICE_WELCOME_REWARD', 100)} welcome coins!")
        try:
            message = await channel.send(content=member.mention, embed=embed, view=IceButtons("answer"))
        except discord.HTTPException:
            return
        state()["open"][str(message.id)] = {"guild": member.guild.id, "channel": channel.id, "time": time.time(),
                                            "answers": 0, "kind": "welcome", "question": q, "for": member.id}
        save()

    # ---------- commands ----------
    @app_commands.command(name="question", description="❓ Post a random question, would you rather, or this or that")
    @app_commands.describe(kind="Pick one, or leave empty for random")
    @app_commands.choices(kind=[app_commands.Choice(name="❓ Question", value="question"),
                                app_commands.Choice(name="🤷 Would you rather", value="wyr"),
                                app_commands.Choice(name="⚡ This or that", value="this_or_that")])
    @app_commands.checks.cooldown(1, 60, key=lambda i: i.channel_id)
    async def question(self, interaction: discord.Interaction, kind: app_commands.Choice[str] = None):
        await interaction.response.send_message("🎲 here you go!", ephemeral=True)
        await self.post(interaction.channel, kind.value if kind else None, extra=f"asked by {interaction.user.display_name}")

    ice = app_commands.Group(name="icebreaker", description="⚙️ Welcome questions & question of the hour (admins)",
                             default_permissions=discord.Permissions(manage_guild=True), guild_only=True)

    @ice.command(name="setup", description="Turn it on in a channel (and optionally a separate welcome channel)")
    async def setup(self, interaction: discord.Interaction, channel: discord.TextChannel = None,
                    welcome_channel: discord.TextChannel = None):
        cfg = guild_cfg(interaction.guild_id)
        cfg.update(on=True, channel=(channel or interaction.channel).id, paused=False, ignored=0,
                   welcome=welcome_channel.id if welcome_channel else None)
        save()
        every = cfg.get("every", S("ICE_EVERY_MINUTES", 60))
        await interaction.response.send_message(
            f"🧊 Icebreakers ON in <#{cfg['channel']}>, a question every **{every} min**. "
            f"New members get welcomed in <#{cfg['welcome'] or cfg['channel']}>.\n"
            f"-# Try `/icebreaker now` to test. Edit the questions in the prompts folder.", ephemeral=True)

    @ice.command(name="every", description="How many minutes between questions")
    async def every(self, interaction: discord.Interaction, minutes: app_commands.Range[int, 5, 1440]):
        guild_cfg(interaction.guild_id)["every"] = minutes
        save()
        await interaction.response.send_message(f"⏰ A question every **{minutes} minutes**.", ephemeral=True)

    @ice.command(name="quiet", description="Hours with no questions, e.g. from 2 to 10 (your time). Same number twice = off")
    async def quiet(self, interaction: discord.Interaction, start: app_commands.Range[int, 0, 23], end: app_commands.Range[int, 0, 23]):
        guild_cfg(interaction.guild_id)["quiet"] = None if start == end else [start, end]
        save()
        await interaction.response.send_message("🌙 Quiet hours off." if start == end else
                                                f"🌙 No questions from **{start}:00 to {end}:00**.", ephemeral=True)

    @ice.command(name="now", description="Post a question right now (for testing)")
    async def now(self, interaction: discord.Interaction):
        cfg = guild_cfg(interaction.guild_id)
        channel = self.bot.get_channel(cfg.get("channel") or 0) or interaction.channel
        await interaction.response.send_message(f"🎲 posting in {channel.mention}", ephemeral=True)
        message = await self.post(channel)
        state()["open"][str(message.id)]["scheduled"] = True
        cfg["last"] = time.time()
        save()

    @ice.command(name="welcome_test", description="See what a new member's welcome looks like")
    async def welcome_test(self, interaction: discord.Interaction):
        await interaction.response.send_message("👋 sending a test welcome", ephemeral=True)
        cfg = guild_cfg(interaction.guild_id)
        on = cfg.get("on")
        cfg["on"] = True
        await self.on_member_join(interaction.user)
        cfg["on"] = on

    @ice.command(name="off", description="Stop the hourly questions and welcomes")
    async def off(self, interaction: discord.Interaction):
        guild_cfg(interaction.guild_id)["on"] = False
        save()
        await interaction.response.send_message("🧊 Icebreakers off.", ephemeral=True)

    @ice.command(name="status", description="See the current icebreaker settings")
    async def status(self, interaction: discord.Interaction):
        cfg = guild_cfg(interaction.guild_id)
        quiet = cfg.get("quiet", S("ICE_QUIET_HOURS", (2, 10)))
        left = cfg.get("every", S("ICE_EVERY_MINUTES", 60)) * 60 - (time.time() - cfg.get("last", 0))
        await interaction.response.send_message(
            f"🧊 **{'ON' if cfg.get('on') else 'OFF'}**" + (" (napping 😴 until someone talks)" if cfg.get("paused") else "")
            + f"\nChannel: <#{cfg.get('channel') or 0}> · Welcomes: <#{cfg.get('welcome') or cfg.get('channel') or 0}>"
            + f"\nEvery {cfg.get('every', S('ICE_EVERY_MINUTES', 60))} min · next in ~{max(0, int(left // 60))} min"
            + f"\nQuiet hours: {f'{quiet[0]}:00-{quiet[1]}:00' if quiet else 'off'}"
            + f"\nIgnored in a row: {cfg.get('ignored', 0)}/{S('ICE_MAX_IGNORED', 3)} · roasts {'on' if S('ICE_ROAST', True) else 'off'}",
            ephemeral=True)


async def setup(bot):
    await bot.add_cog(Icebreaker(bot))
