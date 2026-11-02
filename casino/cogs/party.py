"""🎉 Party games: Truth or Dare and Would You Rather.
The questions live in the prompts folder (one per line), so you can edit or add your own anytime."""
import os
import random

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..bank import bank
from ..ui import BLUE, GREEN, PURPLE, RED, coins, games_only, oops

TRUTHS = """What's the most embarrassing thing you've done in front of a crush?
What's a secret you've never told anyone in this server?
What's the last thing you searched on your phone?
Who in this server would you trust with your life? Who would you NOT?
What's the worst gift you've ever received?
What's the most childish thing you still do?
Have you ever blamed someone else for something you did?
What's your most useless talent?
What's the weirdest dream you remember?
What's a food you pretend to like but actually hate?
What's the longest you've gone without showering?
What's the dumbest way you've ever hurt yourself?
Which game have you rage-quit the most?
What's your most embarrassing username ever?
What's the most money you've wasted on something stupid?
Who was your first celebrity crush?
What's something you're secretly proud of?
What's the biggest lie you've told to get out of plans?
If you could swap lives with someone in this server for a day, who would it be?
What's the cringiest thing you've posted online?
What's the worst grade you ever got, and for what?
What's a habit you have that you hope nobody notices?
Have you ever laughed at the wrong moment? What happened?
What's your guilty-pleasure song?
What's the worst thing you've ever cooked?
What's the last lie you told?
What's the most trouble you got into as a kid?
What's the most embarrassing thing your parents caught you doing?
Who in this server do you think is the funniest?
What's a conspiracy theory you secretly kind of believe?
What's the longest you've stayed awake gaming?
What would your autobiography be called?
What's something you've never admitted about yourself?
What's your worst fashion phase?
Who do you text the most?""".splitlines()

DARES = """Change your nickname to something the group picks for 1 hour.
Talk in an accent for the next 3 messages (or in voice for 2 minutes).
Send the 5th photo in your gallery (if it's safe!).
Type your next message with your elbows.
Let someone in the chat write your status for an hour.
Sing the chorus of any song in voice chat.
Speak only in questions for the next 5 minutes.
Do your best evil villain laugh in voice.
Send a voice message of you pretending to be a news reporter.
Use only emojis for your next 5 messages.
Compliment every person in the voice channel.
Tell a joke. If nobody laughs, do another dare.
Do 10 push-ups (or 10 squats) right now.
Change your profile picture to whatever the group picks for 1 hour.
Describe your day as if you're a nature documentary narrator.
Talk like a pirate for the next 3 minutes.
Send the last meme you saved.
Read the last message you sent to your mom out loud (if it's safe!).
Say the alphabet backwards as fast as you can.
Let someone pick a word you must use in every message for 10 minutes.
Do a dramatic reading of the last 3 messages in this channel.
Pretend to be a game show host and introduce everyone in voice.
Type with your eyes closed for your next message.
Make up a rap about the person above you.
Narrate everything you do for the next 2 minutes.
Do your best impression of a cat for 30 seconds.
Speak in slow motion for the next minute.
Send a selfie with the weirdest face you can make.
Write a short poem about the last game you played.
Act like a robot for the next 3 minutes.
Say something nice about the person who last roasted you.
Explain how to make a sandwich like it's the most serious thing in the world.
Rate everyone's username out of 10.
Put on a hat (or anything as a hat) and keep it on for the next 15 minutes.
Speak in third person for the next 5 minutes.""".splitlines()

WYR = """Be able to fly | Be invisible
Always be 10 minutes late | Always be 20 minutes early
Have unlimited free food | Have unlimited free games
Fight 1 horse-sized duck | Fight 100 duck-sized horses
Never play games again | Never watch movies again
Live without music | Live without the internet for a year
Be famous but broke | Be rich but unknown
Talk to animals | Speak every human language
Only eat pizza forever | Never eat pizza again
Have a rewind button | Have a pause button for your life
Lose all your money | Lose all your photos
Be the funniest person in the room | Be the smartest person in the room
Always have to sing instead of speak | Always have to dance while walking
Have a personal chef | Have a personal driver
Know when you'll die | Know how you'll die
Be stuck in a game forever | Be stuck in a movie forever
Have no lag ever | Have free Wi-Fi everywhere
Only whisper | Only shout
Live in the past | Live in the future
Have a pet dragon | Have a pet dinosaur
Have 3 arms | Have 3 legs
Be a wizard | Be a superhero
Give up your phone for a month | Give up sleeping in a bed for a month
Win the lottery | Live twice as long
Be able to teleport | Be able to read minds
Have hands for feet | Have feet for hands
Always win at games | Always win arguments
Eat a spoonful of mayo | Eat a spoonful of mustard
Be stuck on an island alone | Be stuck on an island with someone you hate
Never feel cold again | Never feel tired again""".splitlines()

DEFAULTS = {"truths.txt": TRUTHS, "dares.txt": DARES, "would_you_rather.txt": WYR}


def make_prompt_files():
    os.makedirs(config.PROMPTS_FOLDER, exist_ok=True)
    for name, lines in DEFAULTS.items():
        path = os.path.join(config.PROMPTS_FOLDER, name)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")


def prompts(name):
    try:
        with open(os.path.join(config.PROMPTS_FOLDER, name), encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        return lines or DEFAULTS[name]
    except FileNotFoundError:
        return DEFAULTS[name]


_last = {}


def pick(name):
    """A random line, avoiding the last few."""
    lines = prompts(name)
    recent = _last.setdefault(name, [])
    choices = [l for l in lines if l not in recent] or lines
    line = random.choice(choices)
    recent.append(line)
    del recent[:-min(10, len(lines) // 2)]
    return line


# ---------- truth or dare ----------
class TruthOrDare(discord.ui.View):
    def __init__(self, asked_by=None, kind=None):
        super().__init__(timeout=900)
        self.asked_by, self.kind, self.rewarded = asked_by, kind, False
        if kind != "dare":
            self.remove_item(self.did_it)

    async def _next(self, interaction, kind):
        if kind == "random":
            kind = random.choice(["truth", "dare"])
        text = pick("truths.txt" if kind == "truth" else "dares.txt")
        embed = discord.Embed(title=f"{'🤔 Truth' if kind == 'truth' else '😈 Dare'} for {interaction.user.display_name}",
                              description=f"### {text}", color=BLUE if kind == "truth" else RED)
        if kind == "dare" and config.DARE_REWARD:
            embed.set_footer(text=f"Do it, then press 'I did it' for {config.DARE_REWARD} coins")
        await interaction.response.send_message(embed=embed, view=TruthOrDare(interaction.user, kind))

    @discord.ui.button(label="Truth", emoji="🤔", style=discord.ButtonStyle.blurple)
    async def truth(self, interaction, button):
        await self._next(interaction, "truth")

    @discord.ui.button(label="Dare", emoji="😈", style=discord.ButtonStyle.red)
    async def dare(self, interaction, button):
        await self._next(interaction, "dare")

    @discord.ui.button(label="Random", emoji="🎲", style=discord.ButtonStyle.secondary)
    async def random_one(self, interaction, button):
        await self._next(interaction, "random")

    @discord.ui.button(label="I did it", emoji="✅", style=discord.ButtonStyle.green)
    async def did_it(self, interaction, button):
        if not self.asked_by or interaction.user.id != self.asked_by.id:
            return await oops(interaction, "🙅 Only the person who got the dare can claim it.")
        if self.rewarded:
            return await oops(interaction, "You already claimed this one!")
        self.rewarded = True
        button.disabled = True
        bank.add(interaction.user.id, config.DARE_REWARD)
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"🏅 {interaction.user.mention} did the dare! +{coins(config.DARE_REWARD)}")


# ---------- would you rather ----------
class WouldYouRather(discord.ui.View):
    def __init__(self, a, b):
        super().__init__(timeout=900)
        self.a, self.b = a, b
        self.votes = {}  # user id -> "a"/"b"
        self.option_a.label = a[:80]
        self.option_b.label = b[:80]

    def embed(self):
        na = sum(v == "a" for v in self.votes.values())
        nb = len(self.votes) - na

        def bar(n):
            share = n / len(self.votes) if self.votes else 0
            return f"{'🟦' * round(share * 10)}{'⬜' * (10 - round(share * 10))} {round(share * 100)}% ({n})"
        return discord.Embed(title="🤷 Would you rather...", color=PURPLE,
                             description=f"🅰️ **{self.a}**\n{bar(na)}\n\n🅱️ **{self.b}**\n{bar(nb)}")

    async def _vote(self, interaction, side):
        self.votes[interaction.user.id] = side
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(emoji="🅰️", style=discord.ButtonStyle.blurple, row=0)
    async def option_a(self, interaction, button):
        await self._vote(interaction, "a")

    @discord.ui.button(emoji="🅱️", style=discord.ButtonStyle.red, row=1)
    async def option_b(self, interaction, button):
        await self._vote(interaction, "b")

    @discord.ui.button(label="Next question", emoji="➡️", style=discord.ButtonStyle.secondary, row=2)
    async def next_one(self, interaction, button):
        view = new_wyr()
        await interaction.response.send_message(embed=view.embed(), view=view)


def new_wyr():
    line = pick("would_you_rather.txt")
    a, _, b = line.partition("|")
    return WouldYouRather(a.strip(), (b or "neither").strip())


class Party(commands.Cog):
    def __init__(self):
        make_prompt_files()

    @app_commands.command(name="truthordare", description="🎉 Truth or dare? Press a button")
    @games_only()
    async def truthordare(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🎉 Truth or Dare", color=GREEN,
                              description="Press a button to get a **truth** or a **dare**.\nAnyone can play!")
        await interaction.response.send_message(embed=embed, view=TruthOrDare())

    @app_commands.command(name="wouldyourather", description="🤷 Would you rather... everyone votes")
    @games_only()
    async def wouldyourather(self, interaction: discord.Interaction):
        view = new_wyr()
        await interaction.response.send_message(embed=view.embed(), view=view)


async def setup(bot):
    await bot.add_cog(Party())
