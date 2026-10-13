import random
import discord

BASE_STATS = ("strength", "defense", "speed", "vitality", "technique", "haki")

# Replace image_url values with your own hosted art URLs. Stats and ranks are fixed per item ID.
ITEMS = {
    "WPN-001": {
        "id": "WPN-001", "name": "Marine Standard Cutlass", "type": "weapon",
        "rank": "E", "rarity": "Common", "stats": {"strength": 8, "speed": 2},
        "description": "A dependable cutlass issued to low-ranking Marines.",
        "image_url": "https://placehold.co/600x800/png?text=Marine+Cutlass"
    },
    "ACC-004": {
        "id": "ACC-004", "name": "Tideglass Pendant", "type": "accessory",
        "rank": "B", "rarity": "Rare", "stats": {"defense": 12, "vitality": 10},
        "description": "An original charm said to hold the calm of the deep sea.",
        "image_url": "https://placehold.co/600x800/png?text=Tideglass+Pendant"
    },
    "MAT-002": {
        "id": "MAT-002", "name": "Sea Prism Fragment", "type": "material",
        "rank": "C", "rarity": "Uncommon", "stats": {},
        "description": "A rare mineral fragment. Crafting use can be added in a later version.",
        "image_url": "https://placehold.co/600x800/png?text=Sea+Prism+Fragment"
    },
    "CON-001": {
        "id": "CON-001", "name": "Travel Ration", "type": "consumable",
        "rank": "E", "rarity": "Common", "stats": {},
        "description": "Basic provisions for a long voyage.",
        "image_url": "https://placehold.co/600x800/png?text=Travel+Ration"
    },
}
LOOT_TABLES = {
    "starter": [
        ("WPN-001", 55), ("CON-001", 30), ("MAT-002", 12), ("ACC-004", 3)
    ]
}
MISSIONS = {
    "MS-001": {"name": "Trouble at the Port", "description": "Help the port workers deal with a local nuisance.", "objective": "Starter demo objective: report back to the quest board.", "xp": 45, "berries": 120},
    "MS-002": {"name": "Supply Run", "description": "Gather supplies for a small vessel.", "objective": "Starter demo objective: deliver the supplies to the contact.", "xp": 30, "berries": 90},
}
ENEMIES = {
    "starter": [
        {"id": "EN-001", "name": "Rowdy Dockhand", "hp": 48, "max_hp": 48, "strength": 7, "defense": 2, "xp": 25, "berries": 55},
        {"id": "EN-002", "name": "Rookie Marine", "hp": 58, "max_hp": 58, "strength": 8, "defense": 3, "xp": 35, "berries": 75},
        {"id": "EN-003", "name": "Wild Boar", "hp": 42, "max_hp": 42, "strength": 9, "defense": 1, "xp": 20, "berries": 35},
    ]
}

def roll_item(location="starter"):
    table = LOOT_TABLES.get(location, LOOT_TABLES["starter"])
    ids, weights = zip(*table)
    return ITEMS[random.choices(ids, weights=weights, k=1)[0]]

def calculate_power_level(stats, level=1):
    # Transparent baseline formula; tune balance in one place.
    return int(stats["strength"]*2 + stats["defense"]*1.5 + stats["speed"]*1.5 +
               stats["vitality"]*1.5 + stats["technique"]*2 + stats["haki"]*3 + level*10)

def effective_stats(player):
    return {k: player[k] for k in BASE_STATS}

def item_embed(item, title=None):
    stats = item.get("stats", {})
    stat_text = "\n".join(f"**{k.title()}:** +{v}" for k, v in stats.items()) or "No direct combat stat bonus."
    embed = discord.Embed(
        title=title or f"{item['name']} · {item['id']}",
        description=f"{item['description']}\n\n**Rank:** {item['rank']} · **Rarity:** {item['rarity']} · **Type:** {item['type'].title()}\n\n{stat_text}",
        color=discord.Color.gold()
    )
    embed.set_image(url=item["image_url"])
    embed.set_footer(text="Fixed catalog data · item stats do not reroll")
    return embed

def profile_embed(player, stats):
    pl = calculate_power_level(stats, player["level"])
    embed = discord.Embed(title=f"🏴‍☠️ {player['name']}", description=f"Level {player['level']} · Rank {player['rank']} · Power Level {pl}", color=discord.Color.blue())
    embed.add_field(name="Vitals", value=f"HP **{player['hp']}/{player['max_hp']}**\nStamina **{player['stamina']}/{player['max_stamina']}**", inline=True)
    embed.add_field(name="Economy", value=f"฿{player['berries']}\nXP {player['xp']}", inline=True)
    embed.add_field(name="Fundamental Stats", value="\n".join(f"**{k.title()}:** {v}" for k, v in stats.items()), inline=False)
    embed.add_field(name="Location", value=player["island"], inline=True)
    return embed

def inventory_embed(rows):
    embed = discord.Embed(title="🎒 Inventory", color=discord.Color.dark_teal())
    if not rows:
        embed.description = "Your inventory is empty. Try `/explore`."
        return embed
    for row in rows[:20]:
        item = row.get("item")
        if not item:
            continue
        equipped = " · **Equipped**" if row["equipped"] else ""
        embed.add_field(name=f"{item['name']} ×{row['quantity']}{equipped}", value=f"`{item['id']}` · Rank {item['rank']} · {item['rarity']}", inline=False)
    return embed

def create_battle_embed(battle, log):
    enemy = battle["enemy"]
    embed = discord.Embed(title=f"⚔️ Battle: {enemy['name']}", description="\n".join(log[-5:]), color=discord.Color.red())
    embed.add_field(name="Enemy HP", value=f"{enemy['hp']}/{enemy['max_hp']}", inline=True)
    embed.add_field(name="Turn", value=str(battle.get("turn", 1)), inline=True)
    embed.set_footer(text="Attack costs no stamina · Skill costs 10 stamina · Retreat ends battle")
    battle["turn"] = battle.get("turn", 1) + 1
    return embed
