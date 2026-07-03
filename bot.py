import discord
from discord.ext import commands
from discord import app_commands
import os
import re

TOKEN = os.getenv("BOT_TOKEN")

intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix=".",
    intents=intents
)

blocked_words = [
    "free nitro",
    "grabify",
    "skid",
    "dox",
    "token logger",
    "ip grabber"
]

# ================= EVENTS =================

@bot.event
async def on_ready():

    print(f"Logged in as {bot.user}")

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(e)


@bot.event
async def on_member_join(member):

    channel = member.guild.system_channel

    if channel:

        embed = discord.Embed(
            title="👋 Welcome",
            description=f"Welcome {member.mention} to **{member.guild.name}**",
            color=0x00ff00
        )

        embed.add_field(
            name="Member Count",
            value=member.guild.member_count
        )

        await channel.send(embed=embed)


@bot.event
async def on_message(message):

    if message.author.bot:
        return

    lower = message.content.lower()

    # Anti-links

    if "http://" in lower or "https://" in lower:

        await message.delete()

        await message.channel.send(
            f"{message.author.mention} links are not allowed",
            delete_after=5
        )

        return

    # Anti-discord invites

    if "discord.gg/" in lower:

        await message.delete()

        return

    # Blocked words

    for word in blocked_words:

        if word in lower:

            await message.delete()

            await message.channel.send(
                f"{message.author.mention} blocked word detected",
                delete_after=5
            )

            return

    # Anti mass mention

    if len(message.mentions) >= 5:

        await message.delete()

        await message.channel.send(
            f"{message.author.mention} mention spam detected",
            delete_after=5
        )

        return

    await bot.process_commands(message)


# ================= SECURITY COMMANDS =================

@bot.tree.command(
    name="lockdown",
    description="Lock all channels"
)
async def lockdown(interaction: discord.Interaction):

    for channel in interaction.guild.text_channels:

        await channel.set_permissions(
            interaction.guild.default_role,
            send_messages=False
        )

    await interaction.response.send_message(
        "🔒 Server locked"
    )


@bot.tree.command(
    name="unlock",
    description="Unlock all channels"
)
async def unlock(interaction: discord.Interaction):

    for channel in interaction.guild.text_channels:

        await channel.set_permissions(
            interaction.guild.default_role,
            send_messages=True
        )

    await interaction.response.send_message(
        "🔓 Server unlocked"
    )


# ================= MODERATION =================

@bot.tree.command(
    name="purge",
    description="Delete messages"
)
@app_commands.describe(amount="Amount")

async def purge(
interaction: discord.Interaction,
amount: int
):

    await interaction.channel.purge(
        limit=amount
    )

    await interaction.response.send_message(
        f"Deleted {amount}",
        ephemeral=True
    )


@bot.tree.command(
    name="kick",
    description="Kick member"
)

async def kick(
interaction: discord.Interaction,
member: discord.Member
):

    await member.kick()

    await interaction.response.send_message(
        f"Kicked {member}"
    )


@bot.tree.command(
    name="ban",
    description="Ban member"
)

async def ban(
interaction: discord.Interaction,
member: discord.Member
):

    await member.ban()

    await interaction.response.send_message(
        f"Banned {member}"
    )


# ================= UTILITY =================

@bot.tree.command(
    name="ping",
    description="Bot ping"
)

async def ping(interaction: discord.Interaction):

    await interaction.response.send_message(
        f"🏓 {round(bot.latency*1000)}ms"
    )


@bot.tree.command(
    name="userinfo",
    description="User info"
)

async def userinfo(
interaction: discord.Interaction,
member: discord.Member=None
):

    member = member or interaction.user

    embed = discord.Embed(
        title=str(member),
        color=0x00ff00
    )

    embed.add_field(
        name="ID",
        value=member.id
    )

    embed.add_field(
        name="Joined",
        value=member.joined_at
    )

    await interaction.response.send_message(
        embed=embed
    )


# ================= TICKETS =================

class TicketButton(discord.ui.View):

    @discord.ui.button(
        label="Create Ticket",
        style=discord.ButtonStyle.green
    )

    async def create_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        overwrites = {

            interaction.guild.default_role:
            discord.PermissionOverwrite(
                view_channel=False
            ),

            interaction.user:
            discord.PermissionOverwrite(
                view_channel=True
            )
        }

        channel = await interaction.guild.create_text_channel(
            f"ticket-{interaction.user.name}",
            overwrites=overwrites
        )

        await interaction.response.send_message(
            f"Created {channel.mention}",
            ephemeral=True
        )


@bot.tree.command(
    name="tickets",
    description="Ticket panel"
)

async def tickets(
interaction: discord.Interaction
):

    embed = discord.Embed(
        title="🎟 Support Tickets",
        description="Press button below"
    )

    await interaction.response.send_message(
        embed=embed,
        view=TicketButton()
    )

@bot.tree.command(
    name="setup",
    description="Build a complete server layout"
)
async def setup(interaction: discord.Interaction):

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ You need Administrator permission",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        "⚙️ Building server...",
        ephemeral=True
    )

    guild = interaction.guild

    # ===== ROLES =====

    roles = [
        ("Owner", discord.Permissions(administrator=True)),
        ("Admin", discord.Permissions(administrator=True)),
        ("Moderator", discord.Permissions(
            manage_messages=True,
            kick_members=True,
            ban_members=True
        )),
        ("Helper", discord.Permissions(
            manage_messages=True
        )),
        ("Verified", discord.Permissions()),
        ("Muted", discord.Permissions(
            send_messages=False
        )),
        ("Giveaway Ping", discord.Permissions()),
        ("Event Ping", discord.Permissions()),
        ("Member", discord.Permissions())
    ]

    existing_roles = [r.name for r in guild.roles]

    for role_name, perms in roles:

        if role_name not in existing_roles:

            await guild.create_role(
                name=role_name,
                permissions=perms
            )

    # ===== CATEGORIES =====

    categories = {}

    category_names = [
        "📢 Information",
        "💬 Community",
        "🎮 Gaming",
        "🛡 Moderation",
        "🎫 Support",
        "🎉 Events",
        "🔊 Voice"
    ]

    for name in category_names:

        category = discord.utils.get(
            guild.categories,
            name=name
        )

        if not category:

            category = await guild.create_category(name)

        categories[name] = category

    # ===== INFORMATION =====

    await guild.create_text_channel(
        "rules",
        category=categories["📢 Information"]
    )

    await guild.create_text_channel(
        "announcements",
        category=categories["📢 Information"]
    )

    await guild.create_text_channel(
        "welcome",
        category=categories["📢 Information"]
    )

    await guild.create_text_channel(
        "server-news",
        category=categories["📢 Information"]
    )

    # ===== COMMUNITY =====

    await guild.create_text_channel(
        "general",
        category=categories["💬 Community"]
    )

    await guild.create_text_channel(
        "media",
        category=categories["💬 Community"]
    )

    await guild.create_text_channel(
        "bot-commands",
        category=categories["💬 Community"]
    )

    await guild.create_text_channel(
        "suggestions",
        category=categories["💬 Community"]
    )

    # ===== GAMING =====

    await guild.create_text_channel(
        "gaming-chat",
        category=categories["🎮 Gaming"]
    )

    await guild.create_text_channel(
        "clips",
        category=categories["🎮 Gaming"]
    )

    # ===== MODERATION =====

    await guild.create_text_channel(
        "mod-logs",
        category=categories["🛡 Moderation"]
    )

    await guild.create_text_channel(
        "security-alerts",
        category=categories["🛡 Moderation"]
    )

    await guild.create_text_channel(
        "staff-chat",
        category=categories["🛡 Moderation"]
    )

    # ===== SUPPORT =====

    ticket_channel = await guild.create_text_channel(
        "tickets",
        category=categories["🎫 Support"]
    )

    await guild.create_text_channel(
        "reports",
        category=categories["🎫 Support"]
    )

    # ===== EVENTS =====

    await guild.create_text_channel(
        "giveaways",
        category=categories["🎉 Events"]
    )

    await guild.create_text_channel(
        "events",
        category=categories["🎉 Events"]
    )

    # ===== VOICE =====

    await guild.create_voice_channel(
        "General VC",
        category=categories["🔊 Voice"]
    )

    await guild.create_voice_channel(
        "Gaming VC",
        category=categories["🔊 Voice"]
    )

    await guild.create_voice_channel(
        "Music VC",
        category=categories["🔊 Voice"]
    )

    await guild.create_voice_channel(
        "Private VC",
        category=categories["🔊 Voice"]
    )

    # ===== TICKET PANEL =====

    embed = discord.Embed(
        title="🎟 Support Tickets",
        description="Use /tickets to create a support ticket",
        color=0x00ff00
    )

    await ticket_channel.send(
        embed=embed
    )

    await interaction.followup.send(
        "✅ Server setup complete"
    )
bot.run(TOKEN)
