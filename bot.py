import discord
from discord import app_commands
from discord.ui import View, Select
import aiohttp
import asyncio
import os
from datetime import datetime

BOT_TOKEN = os.getenv("MTUyMjE1MDE0NTUyNzkxMDQ0MA.GoUv60.Rl7kFqwevNYmrOC4r3suOCdghd_OjJAAKRk8GM")
API_URL = "https://gagapi.onrender.com"

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

watchlists = {}

SEEDS = [
    "Carrot Seed",
    "Wheat Seed",
    "Potato Seed",
    "Tomato Seed",
    "Corn Seed",
    "Pumpkin Seed",
    "Watermelon Seed",
    "Dragon Fruit Seed",
    "Rainbow Seed",
    "Crystal Seed"
]

class SeedSelect(Select):
    def __init__(self, user_id):
        self.user_id = user_id

        options = [
            discord.SelectOption(label=seed)
            for seed in SEEDS
        ]

        super().__init__(
            placeholder="Choose seeds...",
            min_values=0,
            max_values=len(options),
            options=options
        )

    async def callback(self, interaction: discord.Interaction):

        watchlists[self.user_id] = self.values

        await interaction.response.send_message(
            f"✅ Watching: {', '.join(self.values)}",
            ephemeral=True
        )

class SeedView(View):
    def __init__(self, user_id):
        super().__init__(timeout=300)
        self.add_item(SeedSelect(user_id))


async def check_stock():

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_URL}/stock"
            ) as response:

                if response.status == 200:
                    return await response.json()

    except Exception as e:
        print(e)

    return None


async def stock_loop():

    await client.wait_until_ready()

    while not client.is_closed():

        stock = await check_stock()

        if stock:

            for user_id, seeds in watchlists.items():

                for seed in seeds:

                    found = False

                    for category in stock.values():

                        if isinstance(category, list):

                            for item in category:

                                if item.get("name") == seed:

                                    found = True

                                    try:

                                        user = await client.fetch_user(user_id)

                                        embed = discord.Embed(
                                            title="🌱 Seed Alert",
                                            description=f"{seed} is in stock!",
                                            color=0x00ff00,
                                            timestamp=datetime.now()
                                        )

                                        embed.add_field(
                                            name="Price",
                                            value=str(item.get("price", "?"))
                                        )

                                        embed.add_field(
                                            name="Stock",
                                            value=str(item.get("stock", "?"))
                                        )

                                        await user.send(
                                            embed=embed
                                        )

                                    except:
                                        pass

                    await asyncio.sleep(.5)

        await asyncio.sleep(30)


@tree.command(
    name="seeds",
    description="Choose seeds to watch"
)
async def seeds(interaction: discord.Interaction):

    embed = discord.Embed(
        title="🌱 Seed Notifier",
        description="Pick seeds below",
        color=0x00ff00
    )

    await interaction.response.send_message(
        embed=embed,
        view=SeedView(interaction.user.id),
        ephemeral=True
    )


@tree.command(
    name="stock",
    description="View stock"
)
async def stock(interaction: discord.Interaction):

    data = await check_stock()

    if not data:

        await interaction.response.send_message(
            "Couldn't fetch stock.",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title="Current Stock",
        color=0x00ff00
    )

    for category, items in data.items():

        if isinstance(items, list):

            value = "\n".join(
                [
                    f"• {x.get('name','Unknown')}"
                    for x in items[:5]
                ]
            )

            embed.add_field(
                name=category,
                value=value if value else "None",
                inline=True
            )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


@client.event
async def on_ready():

    print(f"Logged in as {client.user}")

    await tree.sync()

    client.loop.create_task(
        stock_loop()
    )

    print("Commands synced")


client.run(BOT_TOKEN)
