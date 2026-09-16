import os
import json
import random
import asyncio
from datetime import datetime, timezone, timedelta

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN", "")
PREFIX = os.getenv("PREFIX", "!")
SUPPORT_ROLE_ID = int(os.getenv("SUPPORT_ROLE_ID", "0"))
TICKET_CATEGORY_ID = int(os.getenv("TICKET_CATEGORY_ID", "0"))
WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID", "0"))
STAFF_APPLICATION_CHANNEL_ID = int(os.getenv("STAFF_APPLICATION_CHANNEL_ID", "0"))
STAFF_REVIEW_CHANNEL_ID = int(os.getenv("STAFF_REVIEW_CHANNEL_ID", "0"))
APPLICATION_ROLE_ID = int(os.getenv("APPLICATION_ROLE_ID", "0"))

DATA_FILE = "bot_data.json"


def load_data():
    if not os.path.exists(DATA_FILE):
        return {"giveaways": {}, "applications": {}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"giveaways": {}, "applications": {}}


data = load_data()


def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)


def support_role(guild: discord.Guild):
    return guild.get_role(SUPPORT_ROLE_ID) if SUPPORT_ROLE_ID else None


def ticket_category(guild: discord.Guild):
    return guild.get_channel(TICKET_CATEGORY_ID) if TICKET_CATEGORY_ID else None


class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Create Ticket",
        style=discord.ButtonStyle.primary,
        emoji="🎫",
        custom_id="tickets:create"
    )
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message("This can only be used in a server.", ephemeral=True)

        existing = discord.utils.get(guild.text_channels, name=f"ticket-{interaction.user.id}")
        if existing:
            return await interaction.response.send_message(
                f"You already have a ticket: {existing.mention}", ephemeral=True
            )

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_channels=True
            ),
        }

        role = support_role(guild)
        if role:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            )

        category = ticket_category(guild)
        channel = await guild.create_text_channel(
            f"ticket-{interaction.user.id}",
            category=category if isinstance(category, discord.CategoryChannel) else None,
            overwrites=overwrites,
            reason=f"Ticket created by {interaction.user}"
        )

        embed = discord.Embed(
            title="🎫 Support Ticket",
            description=(
                f"Welcome {interaction.user.mention}!\n\n"
                "Please explain your issue and a staff member will help you.\n"
                "Use the button below when the issue is resolved."
            ),
            color=discord.Color.blurple()
        )
        await channel.send(
            content=interaction.user.mention,
            embed=embed,
            view=CloseTicketView()
        )
        await interaction.response.send_message(
            f"Ticket created: {channel.mention}", ephemeral=True
        )


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="tickets:close"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.channel or not interaction.channel.name.startswith("ticket-"):
            return await interaction.response.send_message(
                "This button can only be used inside a ticket.", ephemeral=True
            )

        role = support_role(interaction.guild) if interaction.guild else None
        is_staff = role and role in getattr(interaction.user, "roles", [])
        if not is_staff and not interaction.channel.name.endswith(str(interaction.user.id)):
            return await interaction.response.send_message(
                "Only the ticket creator or support staff can close this ticket.", ephemeral=True
            )

        await interaction.response.send_message("🔒 Closing ticket in 5 seconds...")
        await asyncio.sleep(5)
        await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")


class GiveawayView(discord.ui.View):
    def __init__(self, giveaway_id: str):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id

    @discord.ui.button(
        label="Enter Giveaway",
        style=discord.ButtonStyle.success,
        emoji="🎉",
        custom_id="giveaway:enter"
    )
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaway = data["giveaways"].get(self.giveaway_id)
        if not giveaway or giveaway["ended"]:
            return await interaction.response.send_message("This giveaway has ended.", ephemeral=True)

        entrants = giveaway.setdefault("entrants", [])
        uid = interaction.user.id

        if uid in entrants:
            entrants.remove(uid)
            message = "You have left the giveaway."
        else:
            entrants.append(uid)
            message = "You entered the giveaway! 🎉"

        save_data()
        await interaction.response.send_message(message, ephemeral=True)


class StaffApplicationModal(discord.ui.Modal, title="Staff Application"):
    age = discord.ui.TextInput(
        label="Age",
        placeholder="How old are you?",
        max_length=3
    )
    experience = discord.ui.TextInput(
        label="Experience",
        placeholder="Tell us about your previous staff experience.",
        style=discord.TextStyle.paragraph,
        max_length=1000
    )
    why = discord.ui.TextInput(
        label="Why should we choose you?",
        placeholder="Explain why you would be a good staff member.",
        style=discord.TextStyle.paragraph,
        max_length=1500
    )
    availability = discord.ui.TextInput(
        label="Availability",
        placeholder="When are you usually available?",
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        app_id = str(random.randint(100000, 999999))
        while app_id in data["applications"]:
            app_id = str(random.randint(100000, 999999))

        data["applications"][app_id] = {
            "user_id": interaction.user.id,
            "age": self.age.value,
            "experience": self.experience.value,
            "why": self.why.value,
            "availability": self.availability.value,
            "status": "Pending",
        }
        save_data()

        embed = discord.Embed(
            title=f"📝 Staff Application #{app_id}",
            color=discord.Color.orange(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Applicant", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
        embed.add_field(name="Age", value=self.age.value, inline=True)
        embed.add_field(name="Availability", value=self.availability.value, inline=True)
        embed.add_field(name="Experience", value=self.experience.value, inline=False)
        embed.add_field(name="Why should we choose you?", value=self.why.value, inline=False)

        channel = interaction.guild.get_channel(STAFF_REVIEW_CHANNEL_ID) if interaction.guild else None
        if channel:
            await channel.send(embed=embed, view=ApplicationReviewView(app_id))

        await interaction.response.send_message(
            "Your staff application has been submitted. Good luck! 🍀", ephemeral=True
        )


class StaffApplicationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Apply for Staff",
        style=discord.ButtonStyle.primary,
        emoji="📋",
        custom_id="applications:open"
    )
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(StaffApplicationModal())


class ApplicationReviewView(discord.ui.View):
    def __init__(self, app_id: str):
        super().__init__(timeout=None)
        self.app_id = app_id

    async def review(self, interaction: discord.Interaction, status: str):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message(
                "You need Manage Server permission to review applications.", ephemeral=True
            )

        app = data["applications"].get(self.app_id)
        if not app:
            return await interaction.response.send_message("Application not found.", ephemeral=True)

        app["status"] = status
        save_data()

        user = interaction.guild.get_member(app["user_id"]) if interaction.guild else None
        if user:
            try:
                await user.send(
                    f"Your staff application for **{interaction.guild.name}** has been **{status}**."
                )
            except discord.Forbidden:
                pass

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content=f"Application **{status}** by {interaction.user.mention}.",
            view=self
        )

    @discord.ui.button(
        label="Accept",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="applications:accept"
    )
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.review(interaction, "Accepted")

    @discord.ui.button(
        label="Deny",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        custom_id="applications:deny"
    )
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.review(interaction, "Denied")


@bot.event
async def on_ready():
    bot.add_view(TicketControlView())
    bot.add_view(CloseTicketView())
    bot.add_view(StaffApplicationView())

    for gid in data["giveaways"]:
        if not data["giveaways"][gid]["ended"]:
            bot.add_view(GiveawayView(gid))

    await bot.tree.sync()
    giveaway_loop.start()
    print(f"Logged in as {bot.user} ({bot.user.id})")


@bot.event
async def on_member_join(member: discord.Member):
    if not WELCOME_CHANNEL_ID:
        return

    channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
    if not channel:
        return

    embed = discord.Embed(
        title="👋 Welcome!",
        description=f"Welcome {member.mention} to **{member.guild.name}**!",
        color=discord.Color.green()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"Member #{member.guild.member_count}")
    await channel.send(embed=embed)


@bot.tree.command(name="ticketpanel", description="Send the ticket panel.")
@app_commands.checks.has_permissions(manage_guild=True)
async def ticketpanel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎫 Support Tickets",
        description=(
            "Need help? Click **Create Ticket** below.\n\n"
            "Please do not open tickets for spam or jokes."
        ),
        color=discord.Color.blurple()
    )
    await interaction.channel.send(embed=embed, view=TicketControlView())
    await interaction.response.send_message("Ticket panel sent.", ephemeral=True)


@bot.tree.command(name="staffpanel", description="Send the staff application panel.")
@app_commands.checks.has_permissions(manage_guild=True)
async def staffpanel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📋 Staff Applications",
        description="Interested in joining the staff team? Click the button below to apply.",
        color=discord.Color.blurple()
    )
    await interaction.channel.send(embed=embed, view=StaffApplicationView())
    await interaction.response.send_message("Staff application panel sent.", ephemeral=True)


@bot.tree.command(name="giveaway", description="Create a giveaway.")
@app_commands.describe(
    duration="Duration in minutes",
    winners="Number of winners",
    prize="Giveaway prize"
)
@app_commands.checks.has_permissions(manage_guild=True)
async def giveaway(
    interaction: discord.Interaction,
    duration: app_commands.Range[int, 1, 10080],
    winners: app_commands.Range[int, 1, 20],
    prize: str
):
    ends_at = datetime.now(timezone.utc) + timedelta(minutes=duration)
    giveaway_id = str(random.randint(100000, 999999))

    while giveaway_id in data["giveaways"]:
        giveaway_id = str(random.randint(100000, 999999))

    embed = discord.Embed(
        title="🎉 GIVEAWAY",
        description=(
            f"**Prize:** {prize}\n"
            f"**Winners:** {winners}\n"
            f"**Ends:** <t:{int(ends_at.timestamp())}:R>\n\n"
            "Click **Enter Giveaway** to participate!"
        ),
        color=discord.Color.gold(),
        timestamp=ends_at
    )
    embed.set_footer(text=f"Giveaway ID: {giveaway_id}")

    await interaction.response.defer()
    message = await interaction.channel.send(
        embed=embed,
        view=GiveawayView(giveaway_id)
    )

    data["giveaways"][giveaway_id] = {
        "guild_id": interaction.guild.id,
        "channel_id": interaction.channel.id,
        "message_id": message.id,
        "prize": prize,
        "winners": winners,
        "ends_at": ends_at.isoformat(),
        "entrants": [],
        "ended": False,
    }
    save_data()

    await interaction.followup.send("Giveaway created!", ephemeral=True)


@tasks.loop(seconds=15)
async def giveaway_loop():
    now = datetime.now(timezone.utc)

    for giveaway_id, giveaway in list(data["giveaways"].items()):
        if giveaway["ended"]:
            continue

        ends_at = datetime.fromisoformat(giveaway["ends_at"])
        if now < ends_at:
            continue

        giveaway["ended"] = True
        save_data()

        guild = bot.get_guild(giveaway["guild_id"])
        channel = guild.get_channel(giveaway["channel_id"]) if guild else None
        if not channel:
            continue

        try:
            message = await channel.fetch_message(giveaway["message_id"])
        except discord.HTTPException:
            continue

        entrants = giveaway.get("entrants", [])
        winners_count = min(giveaway["winners"], len(entrants))

        if winners_count:
            winner_ids = random.sample(entrants, winners_count)
            mentions = ", ".join(f"<@{uid}>" for uid in winner_ids)
            result = f"🎉 Congratulations {mentions}! You won **{giveaway['prize']}**!"
        else:
            result = "There were not enough valid entries to choose a winner."

        embed = message.embeds[0] if message.embeds else discord.Embed()
        embed.title = "🎉 GIVEAWAY ENDED"
        embed.description = (
            f"**Prize:** {giveaway['prize']}\n"
            f"**Entries:** {len(entrants)}\n\n{result}"
        )
        await message.edit(embed=embed, view=None)


@giveaway_loop.before_loop
async def before_giveaway_loop():
    await bot.wait_until_ready()


@bot.tree.command(name="reroll", description="Reroll a completed giveaway.")
@app_commands.describe(giveaway_id="The giveaway ID shown in its footer.")
@app_commands.checks.has_permissions(manage_guild=True)
async def reroll(interaction: discord.Interaction, giveaway_id: str):
    giveaway = data["giveaways"].get(giveaway_id)
    if not giveaway or not giveaway["ended"]:
        return await interaction.response.send_message(
            "That giveaway does not exist or has not ended.", ephemeral=True
        )

    entrants = giveaway.get("entrants", [])
    if not entrants:
        return await interaction.response.send_message(
            "There are no entrants to reroll.", ephemeral=True
        )

    winner = random.choice(entrants)
    await interaction.response.send_message(
        f"🎉 New winner for **{giveaway['prize']}**: <@{winner}>!"
    )


@bot.tree.command(name="ping", description="Check the bot latency.")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing. Put your bot token in the .env file.")

bot.run(TOKEN)
