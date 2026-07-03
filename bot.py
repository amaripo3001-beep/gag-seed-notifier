"""Grow a Garden 2 - Discord Seed Notifier BotA Discord bot that monitors the shop and sends notifications via DMs or channel pings"""

import discordfrom discord import app_commandsfrom discord.ui import View, Button, Selectimport aiohttpimport asyncioimport jsonimport osfrom datetime import datetime, timedeltafrom typing import Dict, Set, Optional

============ CONFIGURATION ============

BOT_TOKEN = os.getenv("MTUyMjE1MDE0NTUyNzkxMDQ0MA.G6aOqH.POU8SE2fnjvhwgPz2hMxIS1Jqa4tuv1WrnxMhk")  # Get from Discord Developer PortalAPI_URL = "https://gagapi.onrender.com"CHECK_INTERVAL = 30  # seconds between stock checks

Seed database organized by category

SEED_CATEGORIES = {"Common": {"color": 0x888888,"seeds": ["Carrot Seed", "Wheat Seed", "Potato Seed", "Lettuce Seed", "Turnip Seed"]},"Uncommon": {"color": 0x00ff00,"seeds": ["Tomato Seed", "Corn Seed", "Strawberry Seed", "Blueberry Seed"]},"Rare": {"color": 0x0088ff,"seeds": ["Pumpkin Seed", "Watermelon Seed", "Pineapple Seed", "Peach Seed"]},"Epic": {"color": 0xaa00ff,"seeds": ["Dragon Fruit Seed", "Golden Apple Seed", "Coconut Seed", "Mango Seed"]},"Legendary": {"color": 0xffaa00,"seeds": ["Rainbow Seed", "Crystal Seed", "Celestial Seed", "Void Seed"]},"Event": {"color": 0xff0088,"seeds": ["Christmas Tree Seed", "Halloween Pumpkin Seed", "Valentine Rose Seed", "Easter Egg Seed"]}}

Flatten seed list for easy lookup

ALL_SEEDS = []for category, data in SEED_CATEGORIES.items():ALL_SEEDS.extend(data["seeds"])

============ DATA STORAGE ============

class UserData:def init(self):self.watchlists: Dict[int, Set[str]] = {}  # user_id -> set of seedsself.notification_channels: Dict[int, int] = {}  # user_id -> channel_id (optional)self.dm_preferred: Dict[int, bool] = {}  # user_id -> prefer DM over channelself.last_notified: Dict[str, datetime] = {}  # seed -> last notification time

def load(self):
    if os.path.exists("user_data.json"):
        with open("user_data.json", "r") as f:
            data = json.load(f)
            self.watchlists = {int(k): set(v) for k, v in data.get("watchlists", {}).items()}
            self.notification_channels = {int(k): int(v) for k, v in data.get("channels", {}).items()}
            self.dm_preferred = {int(k): v for k, v in data.get("dm_preferred", {}).items()}

def save(self):
    with open("user_data.json", "w") as f:
        json.dump({
            "watchlists": {k: list(v) for k, v in self.watchlists.items()},
            "channels": self.notification_channels,
            "dm_preferred": self.dm_preferred
        }, f, indent=2)

user_data = UserData()

============ BOT SETUP ============

intents = discord.Intents.default()intents.message_content = Trueintents.dm_messages = True

class GAGBot(discord.Client):def init(self):super().init(intents=intents)self.tree = app_commands.CommandTree(self)self.session: Optional[aiohttp.ClientSession] = Noneself.current_stock = {}self.monitoring = False

async def setup_hook(self):
    self.session = aiohttp.ClientSession()
    user_data.load()
    self.monitoring_task = self.loop.create_task(self.monitor_stock())
    
async def close(self):
    if self.session:
        await self.session.close()
    await super().close()

bot = GAGBot()

============ UI COMPONENTS ============

class SeedSelectView(View):"""Interactive menu for selecting seeds to watch"""

def __init__(self, user_id: int, category: str):
    super().__init__(timeout=300)
    self.user_id = user_id
    self.category = category
    
    # Create select menu for seeds in this category
    seeds = SEED_CATEGORIES[category]["seeds"]
    current_watchlist = user_data.watchlists.get(user_id, set())
    
    # Split into chunks of 25 (Discord limit)
    options = []
    for seed in seeds:
        options.append(discord.SelectOption(
            label=seed,
            value=seed,
            default=seed in current_watchlist,
            emoji="✅" if seed in current_watchlist else "⬜"
        ))
    
    select = Select(
        placeholder=f"Select {category} seeds to watch...",
        options=options[:25],  # Discord limit
        min_values=0,
        max_values=len(options),
        custom_id=f"seed_select_{category}"
    )
    select.callback = self.on_select
    self.add_item(select)
    
    # Add navigation buttons
    nav_row = View()
    categories = list(SEED_CATEGORIES.keys())
    current_idx = categories.index(category)
    
    if current_idx > 0:
        prev_btn = Button(
            label=f"← {categories[current_idx-1]}",
            style=discord.ButtonStyle.secondary,
            custom_id="prev_cat"
        )
        prev_btn.callback = self.prev_category
        self.add_item(prev_btn)
        
    if current_idx < len(categories) - 1:
        next_btn = Button(
            label=f"{categories[current_idx+1]} →",
            style=discord.ButtonStyle.secondary,
            custom_id="next_cat"
        )
        next_btn.callback = self.next_category
        self.add_item(next_btn)
        
    # Done button
    done_btn = Button(
        label="✓ Done",
        style=discord.ButtonStyle.success,
        custom_id="done"
    )
    done_btn.callback = self.done
    self.add_item(done_btn)
    
    # Clear category button
    clear_btn = Button(
        label="Clear All",
        style=discord.ButtonStyle.danger,
        custom_id="clear"
    )
    clear_btn.callback = self.clear_category
    self.add_item(clear_btn)
    
async def on_select(self, interaction: discord.Interaction):
    selected = interaction.data.get("values", [])
    user_id = interaction.user.id
    
    if user_id not in user_data.watchlists:
        user_data.watchlists[user_id] = set()
        
    # Remove old seeds from this category
    for seed in SEED_CATEGORIES[self.category]["seeds"]:
        user_data.watchlists[user_id].discard(seed)
        
    # Add newly selected
    user_data.watchlists[user_id].update(selected)
    user_data.save()
    
    await interaction.response.send_message(
        f"Updated! Watching **{len(user_data.watchlists[user_id])}** total seeds.",
        ephemeral=True
    )
    
async def prev_category(self, interaction: discord.Interaction):
    categories = list(SEED_CATEGORIES.keys())
    current_idx = categories.index(self.category)
    new_view = SeedSelectView(self.user_id, categories[current_idx - 1])
    await interaction.response.edit_message(
        embed=create_category_embed(categories[current_idx - 1], self.user_id),
        view=new_view
    )
    
async def next_category(self, interaction: discord.Interaction):
    categories = list(SEED_CATEGORIES.keys())
    current_idx = categories.index(self.category)
    new_view = SeedSelectView(self.user_id, categories[current_idx + 1])
    await interaction.response.edit_message(
        embed=create_category_embed(categories[current_idx + 1], self.user_id),
        view=new_view
    )
    
async def done(self, interaction: discord.Interaction):
    count = len(user_data.watchlists.get(self.user_id, []))
    await interaction.response.edit_message(
        content=f"✅ Setup complete! You'll be notified when any of your **{count}** selected seeds appear in the shop.",
        embed=None,
        view=None
    )
    
async def clear_category(self, interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id in user_data.watchlists:
        for seed in SEED_CATEGORIES[self.category]["seeds"]:
            user_data.watchlists[user_id].discard(seed)
        user_data.save()
    await interaction.response.send_message(
        f"Cleared all {self.category} seeds from your watchlist.",
        ephemeral=True
    )

class MainMenuView(View):"""Main menu for the bot"""

def __init__(self, user_id: int):
    super().__init__(timeout=300)
    self.user_id = user_id
    
@discord.ui.button(label="🌱 Select Seeds", style=discord.ButtonStyle.primary, row=0)
async def select_seeds(self, interaction: discord.Interaction, button: Button):
    view = SeedSelectView(self.user_id, "Common")
    await interaction.response.edit_message(
        embed=create_category_embed("Common", self.user_id),
        view=view
    )
    
@discord.ui.button(label="📋 View Watchlist", style=discord.ButtonStyle.secondary, row=0)
async def view_watchlist(self, interaction: discord.Interaction, button: Button):
    seeds = user_data.watchlists.get(self.user_id, set())
    if not seeds:
        await interaction.response.send_message(
            "Your watchlist is empty! Click 'Select Seeds' to add some.",
            ephemeral=True
        )
        return
        
    # Group by category
    lines = []
    for category, data in SEED_CATEGORIES.items():
        cat_seeds = [s for s in seeds if s in data["seeds"]]
        if cat_seeds:
            lines.append(f"**{category}:** {', '.join(cat_seeds)}")
            
    embed = discord.Embed(
        title="📋 Your Seed Watchlist",
        description="\n".join(lines) if lines else "Empty",
        color=0x00ff88
    )
    embed.set_footer(text=f"Total: {len(seeds)} seeds")
    await interaction.response.send_message(embed=embed, ephemeral=True)
    
@discord.ui.button(label="🔔 Test Notification", style=discord.ButtonStyle.secondary, row=0)
async def test_notification(self, interaction: discord.Interaction, button: Button):
    await send_notification(self.user_id, "Test Seed", {"price": 100, "stock": 5}, test=True)
    await interaction.response.send_message(
        "📨 Test notification sent! Check your DMs.",
        ephemeral=True
    )
    
@discord.ui.button(label="⚙️ Settings", style=discord.ButtonStyle.secondary, row=1)
async def settings(self, interaction: discord.Interaction, button: Button):
    view = SettingsView(self.user_id)
    await interaction.response.edit_message(embed=create_settings_embed(self.user_id), view=view)
    
@discord.ui.button(label="🗑️ Clear All", style=discord.ButtonStyle.danger, row=1)
async def clear_all(self, interaction: discord.Interaction, button: Button):
    if self.user_id in user_data.watchlists:
        del user_data.watchlists[self.user_id]
        user_data.save()
    await interaction.response.send_message(
        "🗑️ Watchlist cleared!",
        ephemeral=True
    )

class SettingsView(View):"""Settings menu"""

def __init__(self, user_id: int):
    super().__init__(timeout=300)
    self.user_id = user_id
    
@discord.ui.button(label="← Back", style=discord.ButtonStyle.secondary)
async def back(self, interaction: discord.Interaction, button: Button):
    await interaction.response.edit_message(
        embed=create_main_embed(),
        view=MainMenuView(self.user_id)
    )

============ EMBED HELPERS ============

def create_main_embed():embed = discord.Embed(title="🌱 Grow a Garden 2 - Seed Notifier",description="Get notified instantly when your favorite seeds appear in the shop!",color=0x00ff88)embed.add_field(name="How to use:",value="1. Click Select Seeds to choose which seeds to watch\n""2. The bot checks the shop every 30 seconds\n""3. You'll get a DM when a watched seed appears!",inline=False)embed.add_field(name="Commands:",value="/seeds - Open this menu\n""/stock - View current shop stock\n""/notifyhere - Set this channel for notifications (optional)",inline=False)return embed

def create_category_embed(category: str, user_id: int):data = SEED_CATEGORIES[category]current = user_data.watchlists.get(user_id, set())cat_seeds = [s for s in current if s in data["seeds"]]

embed = discord.Embed(
    title=f"{category} Seeds",
    description=f"Select which {category} seeds you want to be notified for.\n\n"
               f"Currently watching: **{len(cat_seeds)}/{len(data['seeds'])}**",
    color=data["color"]
)
return embed

def create_settings_embed(user_id: int):dm_pref = user_data.dm_preferred.get(user_id, True)channel = user_data.notification_channels.get(user_id)

embed = discord.Embed(
    title="⚙️ Settings",
    description="Configure your notification preferences",
    color=0x888888
)
embed.add_field(
    name="Notification Method",
    value="DM" if dm_pref else f"Channel #{channel}" if channel else "DM (default)",
    inline=True
)
return embed

============ NOTIFICATION SYSTEM ============

async def send_notification(user_id: int, seed_name: str, seed_data: dict, test: bool = False):"""Send notification to user"""user = await bot.fetch_user(user_id)if not user:return

embed = discord.Embed(
    title="🌱 Seed Alert!" if not test else "🧪 Test Notification",
    description=f"**{seed_name}** is now in the shop!" if not test else f"This is a test for **{seed_name}**",
    color=0xffaa00 if not test else 0x888888,
    timestamp=datetime.now()
)

if not test:
    embed.add_field(name="Price", value=f"{seed_data.get('price', '?')} coins", inline=True)
    embed.add_field(name="Stock", value=f"{seed_data.get('stock', '?')} available", inline=True)
    
embed.set_footer(text="Grow a Garden 2 Notifier")

try:
    await user.send(embed=embed)
except discord.Forbidden:
    # Can't DM user, try channel if set
    channel_id = user_data.notification_channels.get(user_id)
    if channel_id:
        channel = bot.get_channel(channel_id)
        if channel:
            await channel.send(f"<@{user_id}>", embed=embed)

async def check_stock():"""Fetch current stock from API"""try:async with bot.session.get(f"{API_URL}/stock", timeout=10) as resp:if resp.status == 200:return await resp.json()except Exception as e:print(f"Error fetching stock: {e}")return None

async def monitor_stock():"""Background task to monitor stock"""await bot.wait_until_ready()

while not bot.is_closed():
    stock = await check_stock()
    if stock:
        bot.current_stock = stock
        
        # Check each user's watchlist
        for user_id, watchlist in user_data.watchlists.items():
            for seed in watchlist:
                # Check if seed is in stock
                in_stock = False
                seed_info = {}
                
                # Parse stock data (adjust based on actual API response)
                if isinstance(stock, dict):
                    for category, items in stock.items():
                        if isinstance(items, list):
                            for item in items:
                                if item.get('name') == seed:
                                    in_stock = True
                                    seed_info = item
                                    break
                
                if in_stock:
                    # Check cooldown (don't spam)
                    key = f"{user_id}:{seed}"
                    last = user_data.last_notified.get(key)
                    if not last or datetime.now() - last > timedelta(minutes=5):
                        await send_notification(user_id, seed, seed_info)
                        user_data.last_notified[key] = datetime.now()
                        
    await asyncio.sleep(CHECK_INTERVAL)

============ COMMANDS ============

@bot.tree.command(name="seeds", description="Open the seed notifier menu")async def seeds_command(interaction: discord.Interaction):await interaction.response.send_message(embed=create_main_embed(),view=MainMenuView(interaction.user.id),ephemeral=True)

@bot.tree.command(name="stock", description="View current shop stock")async def stock_command(interaction: discord.Interaction):stock = await check_stock()if not stock:await interaction.response.send_message("❌ Couldn't fetch stock data. Try again later.",ephemeral=True)return

embed = discord.Embed(
    title="🌱 Current Shop Stock",
    description="Here's what's in the shop right now:",
    color=0x00ff88,
    timestamp=datetime.now()
)

if isinstance(stock, dict):
    for category, items in stock.items():
        if isinstance(items, list) and items:
            values = []
            for item in items[:5]:  # Limit to 5 per category
                name = item.get('name', 'Unknown')
                price = item.get('price', '?')
                values.append(f"• {name} ({price}🪙)")
            embed.add_field(
                name=f"{category} ({len(items)} items)",
                value="\n".join(values) if values else "Empty",
                inline=True
            )

await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="notifyhere", description="Set this channel for notifications (instead of DMs)")@app_commands.describe(channel="The channel for notifications (leave empty for this channel)")async def notifyhere_command(interaction: discord.Interaction, channel: discord.TextChannel = None):target = channel or interaction.channeluser_data.notification_channels[interaction.user.id] = target.iduser_data.dm_preferred[interaction.user.id] = Falseuser_data.save()

await interaction.response.send_message(
    f"✅ Notifications will be sent to {target.mention}",
    ephemeral=True
)

@bot.tree.command(name="dm", description="Switch back to DM notifications")async def dm_command(interaction: discord.Interaction):user_data.dm_preferred[interaction.user.id] = Trueuser_data.save()await interaction.response.send_message("✅ Notifications will be sent via DM",ephemeral=True)

============ EVENTS ============

@bot.eventasync def on_ready():print(f"🌱 Bot logged in as {bot.user}")await bot.tree.sync()print("✅ Commands synced")

============ RUN ============

if name == "main":bot.run(BOT_TOKEN)
