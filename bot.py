import os
import random
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

from database import Database
from game import ITEMS, MISSIONS, ENEMIES, item_embed, profile_embed, inventory_embed, roll_item, create_battle_embed

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
SPAWN_CHANNEL_ID = int(os.getenv("SPAWN_CHANNEL_ID", "0") or 0)
SPAWN_INTERVAL_MINUTES = max(1, int(os.getenv("SPAWN_INTERVAL_MINUTES", "15") or 15))
SPAWN_CHANCE = float(os.getenv("SPAWN_CHANCE", "0.45") or 0.45)

intents = discord.Intents.default()
intents.message_content = True  # Enable Message Content Intent in the Discord Developer Portal.
bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents, help_command=None)
db = Database("rpg.sqlite3")
active_battles = {}
active_drops = {}

def is_admin(ctx):
    return ctx.guild is not None and ctx.author.guild_permissions.manage_guild

class ClaimDropView(discord.ui.View):
    def __init__(self, drop_id: str, item_id: str):
        super().__init__(timeout=900)
        self.drop_id = drop_id
        self.item_id = item_id

    @discord.ui.button(label="Claim item", style=discord.ButtonStyle.success, custom_id="rpg:claim")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        drop = active_drops.get(self.drop_id)
        if not drop or drop["claimed"]:
            await interaction.response.send_message("This drop has already been claimed or expired.", ephemeral=True)
            return
        await db.ensure_player(interaction.user.id, str(interaction.user))
        ok = await db.add_item(interaction.user.id, self.item_id, source="world_drop")
        if not ok:
            await interaction.response.send_message("Couldn't save the item. Please try again.", ephemeral=True)
            return
        drop["claimed"] = True
        button.disabled = True
        await interaction.response.edit_message(
            content=f"🏴‍☠️ {interaction.user.mention} claimed **{ITEMS[self.item_id]['name']}**!",
            view=self,
        )
        await interaction.followup.send("Item saved to your inventory. Mention the bot with `inventory` to view it.", ephemeral=True)

class BattleView(discord.ui.View):
    def __init__(self, user_id: int, battle_id: str):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.battle_id = battle_id

    async def do_turn(self, interaction: discord.Interaction, action: str):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is someone else's battle.", ephemeral=True)
            return
        battle = active_battles.get(self.battle_id)
        if not battle or battle["finished"]:
            await interaction.response.send_message("This battle has ended.", ephemeral=True)
            return
        player = await db.get_player(self.user_id)
        stats = await db.get_effective_stats(self.user_id)
        enemy = battle["enemy"]
        log = []
        if action == "skill":
            if player["stamina"] < 10:
                await interaction.response.send_message("Not enough stamina (10 required).", ephemeral=True)
                return
            await db.change_stamina(self.user_id, -10)
            damage = max(1, int(stats["technique"] * 1.6 + stats["strength"] * 0.45 - enemy["defense"] * 0.4))
            log.append(f"✨ Skill deals **{damage}** damage.")
        else:
            damage = max(1, int(stats["strength"] - enemy["defense"] * 0.35))
            log.append(f"⚔️ Attack deals **{damage}** damage.")
        enemy["hp"] = max(0, enemy["hp"] - damage)
        if enemy["hp"] <= 0:
            battle["finished"] = True
            await db.reward(self.user_id, enemy["xp"], enemy["berries"])
            log.append(f"🏆 Victory! +{enemy['xp']} XP and ฿{enemy['berries']}.")
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(embed=create_battle_embed(battle, log), view=self)
            return
        enemy_damage = max(1, int(enemy["strength"] - stats["defense"] * 0.4))
        await db.change_hp(self.user_id, -enemy_damage)
        player = await db.get_player(self.user_id)
        log.append(f"💥 {enemy['name']} hits you for **{enemy_damage}** damage.")
        if player["hp"] <= 0:
            battle["finished"] = True
            await db.set_hp(self.user_id, max(1, player["max_hp"] // 2))
            log.append("You were defeated. You recover at half HP; no items were lost.")
            for child in self.children:
                child.disabled = True
        else:
            await db.regen_stamina(self.user_id, 3)
        await interaction.response.edit_message(embed=create_battle_embed(battle, log), view=self)

    @discord.ui.button(label="Attack", style=discord.ButtonStyle.primary, emoji="⚔️")
    async def attack(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.do_turn(interaction, "attack")

    @discord.ui.button(label="Skill", style=discord.ButtonStyle.danger, emoji="✨")
    async def skill(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.do_turn(interaction, "skill")

    @discord.ui.button(label="Retreat", style=discord.ButtonStyle.secondary, emoji="🏃")
    async def retreat(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is someone else's battle.", ephemeral=True)
            return
        battle = active_battles.get(self.battle_id)
        if battle:
            battle["finished"] = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="You retreated. No reward was awarded.", view=self)

@bot.event
async def on_ready():
    await db.initialize()
    if not world_spawns.is_running():
        world_spawns.change_interval(minutes=SPAWN_INTERVAL_MINUTES)
        world_spawns.start()
    print(f"Logged in as {bot.user}. Mention commands are enabled.")

@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(title="🏴‍☠️ Grand Line RPG Commands", color=discord.Color.gold())
    embed.description = (
        f"**Create/profile**\n`@{bot.user.name} start YourName`\n`@{bot.user.name} profile`\n\n"
        f"**Adventure**\n`@{bot.user.name} explore`\n`@{bot.user.name} fight`\n"
        f"`@{bot.user.name} missions`\n`@{bot.user.name} accept MS-001`\n"
        f"`@{bot.user.name} complete MS-001`\n\n"
        f"**Items**\n`@{bot.user.name} inventory`\n`@{bot.user.name} equip WPN-001`\n\n"
        f"**Admin**\n`@{bot.user.name} spawn_test`"
    )
    embed.set_footer(text="Mention me first, then type a command.")
    await ctx.send(embed=embed)

@bot.command(name="start")
async def start(ctx, *, name: str = ""):
    name = name.strip()
    if not name:
        await ctx.send(f"{ctx.author.mention} Give your pirate a name: `@{bot.user.name} start Luffy`")
        return
    if len(name) > 32:
        await ctx.send("Keep your character name to 32 characters or fewer.")
        return
    created = await db.create_player(ctx.author.id, name)
    if not created:
        await ctx.send(f"{ctx.author.mention} You already have a character. Try `@{bot.user.name} profile`.")
        return
    await ctx.send(f"🏴‍☠️ **{discord.utils.escape_markdown(name)}** has joined the seas! Use `@{bot.user.name} explore` to begin.")

@bot.command(name="profile", aliases=["stats", "me"])
async def profile(ctx):
    await db.ensure_player(ctx.author.id, str(ctx.author))
    player = await db.get_player(ctx.author.id)
    stats = await db.get_effective_stats(ctx.author.id)
    await ctx.send(embed=profile_embed(player, stats))

@bot.command(name="inventory", aliases=["inv", "items", "bag"])
async def inventory(ctx):
    await db.ensure_player(ctx.author.id, str(ctx.author))
    rows = await db.get_inventory(ctx.author.id)
    await ctx.send(embed=inventory_embed(rows))

@bot.command(name="equip")
async def equip(ctx, item_id: str = ""):
    if not item_id:
        await ctx.send(f"Provide an item ID, e.g. `@{bot.user.name} equip WPN-001`.")
        return
    await db.ensure_player(ctx.author.id, str(ctx.author))
    if item_id not in ITEMS:
        await ctx.send("Unknown item ID. Check your inventory.")
        return
    ok = await db.equip_item(ctx.author.id, item_id.upper())
    if not ok:
        await ctx.send("You don't own that item.")
        return
    await ctx.send(f"Equipped **{ITEMS[item_id.upper()]['name']}**.")

@bot.command(name="explore", aliases=["scout", "search"])
async def explore(ctx):
    await db.ensure_player(ctx.author.id, str(ctx.author))
    if not await db.cooldown_ready(ctx.author.id, "explore", 60):
        await ctx.send(f"{ctx.author.mention} You're catching your breath. Try again in a minute.")
        return
    await db.set_cooldown(ctx.author.id, "explore")
    event = random.choices(["item", "battle", "story"], weights=[45, 40, 15], k=1)[0]
    if event == "item":
        item = roll_item(location="starter")
        await db.add_item(ctx.author.id, item["id"], source="exploration")
        await ctx.send(content=f"{ctx.author.mention} You discovered an item! It has been added to your inventory.", embed=item_embed(item, title="🔎 Discovery!"))
    elif event == "battle":
        enemy = dict(random.choice(ENEMIES["starter"]))
        battle_id = f"{ctx.author.id}:{ctx.message.id}"
        active_battles[battle_id] = {"enemy": enemy, "user_id": ctx.author.id, "finished": False, "turn": 1}
        await ctx.send(embed=create_battle_embed(active_battles[battle_id], ["A hostile opponent blocks your path!"]), view=BattleView(ctx.author.id, battle_id))
    else:
        await ctx.send("📜 You find a weathered note: *'The sea rewards those who keep moving. Ask at the nearest port about a job.'* Check the mission board.")

@bot.command(name="missions", aliases=["quests", "mission"])
async def missions(ctx):
    await db.ensure_player(ctx.author.id, str(ctx.author))
    lines = []
    for mid, mission in MISSIONS.items():
        completed = await db.mission_completed(ctx.author.id, mid)
        active = await db.has_active_mission(ctx.author.id, mid)
        status = "✅ Completed" if completed else ("🟡 Active" if active else f"Reward: {mission['xp']} XP · ฿{mission['berries']}")
        lines.append(f"**{mission['name']}** (`{mid}`)\n{mission['description']}\n{status}")
    embed = discord.Embed(title="📜 Mission Board", description="\n\n".join(lines), color=discord.Color.gold())
    embed.set_footer(text=f"Use @{bot.user.name} accept MS-001 to accept a mission.")
    await ctx.send(embed=embed)

@bot.command(name="accept")
async def mission_accept(ctx, mission_id: str = ""):
    await db.ensure_player(ctx.author.id, str(ctx.author))
    mission_id = mission_id.upper()
    if mission_id not in MISSIONS:
        await ctx.send("Unknown mission ID. Check `@botname missions`.")
        return
    if await db.mission_completed(ctx.author.id, mission_id):
        await ctx.send("You've already completed this mission.")
        return
    await db.accept_mission(ctx.author.id, mission_id)
    await ctx.send(f"📜 Accepted **{MISSIONS[mission_id]['name']}**. {MISSIONS[mission_id]['objective']}")

@bot.command(name="complete")
async def mission_complete(ctx, mission_id: str = ""):
    await db.ensure_player(ctx.author.id, str(ctx.author))
    mission_id = mission_id.upper()
    if mission_id not in MISSIONS:
        await ctx.send("Unknown mission ID.")
        return
    if not await db.has_active_mission(ctx.author.id, mission_id):
        await ctx.send("Accept this mission first.")
        return
    mission = MISSIONS[mission_id]
    await db.complete_mission(ctx.author.id, mission_id)
    await db.reward(ctx.author.id, mission["xp"], mission["berries"])
    await ctx.send(f"✅ **{mission['name']}** completed! +{mission['xp']} XP and ฿{mission['berries']}.")

@bot.command(name="fight", aliases=["battle"])
async def fight(ctx):
    await db.ensure_player(ctx.author.id, str(ctx.author))
    battle_id = f"{ctx.author.id}:{ctx.message.id}"
    enemy = dict(random.choice(ENEMIES["starter"]))
    active_battles[battle_id] = {"enemy": enemy, "user_id": ctx.author.id, "finished": False, "turn": 1}
    await ctx.send(embed=create_battle_embed(active_battles[battle_id], ["A challenger approaches!"]), view=BattleView(ctx.author.id, battle_id))

@bot.command(name="spawn_test")
async def spawn_test(ctx):
    if not is_admin(ctx):
        await ctx.send("Only server moderators with Manage Server permission can use this command.")
        return
    item = roll_item(location="starter")
    drop_id = str(ctx.message.id)
    active_drops[drop_id] = {"claimed": False, "item_id": item["id"]}
    await ctx.send(content="🎁 **A wild item has appeared! First claim wins.**", embed=item_embed(item, title="🎁 World Drop"), view=ClaimDropView(drop_id, item["id"]))

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f"I don't know that command yet. Try mentioning me with `help`.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"You're missing an argument. Try `@{bot.user.name} help`.")
    else:
        raise error

@tasks.loop(minutes=15)
async def world_spawns():
    if not SPAWN_CHANNEL_ID or random.random() > SPAWN_CHANCE:
        return
    channel = bot.get_channel(SPAWN_CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(SPAWN_CHANNEL_ID)
        except Exception:
            return
    item = roll_item(location="starter")
    drop_id = f"auto:{datetime.now(timezone.utc).timestamp()}"
    active_drops[drop_id] = {"claimed": False, "item_id": item["id"]}
    await channel.send(content="🌊 **A discovery has appeared! First claim wins.**", embed=item_embed(item, title="🌊 World Item Spawn"), view=ClaimDropView(drop_id, item["id"]))

@world_spawns.before_loop
async def before_world_spawns():
    await bot.wait_until_ready()

if not TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN. Copy .env.example to .env and add your bot token.")
bot.run(TOKEN)
