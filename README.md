# One Piece Discord RPG — starter build

A modular starter project using Python, discord.py, SQLite, and a fixed item catalog.

## Included
- Mention-based commands: `@Bot start YourName`, `@Bot profile`, `@Bot inventory`, `@Bot equip WPN-001`
- `@Bot explore` random event loop
- `@Bot fight` turn-based combat with Attack, Skill, and Retreat buttons
- `@Bot missions`, `@Bot accept MS-001`, `@Bot complete MS-001` (mission completion is a demo hook)
- Item embeds with an item-specific image URL
- `@Bot spawn_test` for server admins
- Optional timed world drops in a configured channel
- SQLite persistence for characters, inventory, cooldowns, and mission state
- Data and formulas are separated into `game.py`

## Requirements
- Python 3.10+
- A Discord account and a Discord server where you have permission to add an application
- A Discord application/bot token

## Setup
1. Create an application in the Discord Developer Portal and add a bot user.
2. Invite the bot to your server with the `bot` scope and permissions to read/send messages, embed links, and use buttons. You do not need slash-command setup for this version.
3. Copy `.env.example` to `.env`.
4. Put the bot token in `DISCORD_TOKEN`. Never share the token or upload `.env`.
5. Install packages: `python -m pip install -r requirements.txt`
6. Run: `python bot.py`
7. In the Discord Developer Portal, open **Bot → Privileged Gateway Intents** and enable **Message Content Intent**. Then run `python bot.py`.
8. In Discord, mention the bot and type a command, e.g. `@YourBot start Luffy`, then `@YourBot profile`, `@YourBot explore`, or `@YourBot missions`.

## Image setup
Each catalog entry in `game.py` has an `image_url`. Replace the placeholder URLs with direct HTTPS image URLs for artwork you own, have permission to use, or generated for this project. Discord embeds need a reachable image URL. Keep a separate image for each item; do not use a generic image for every item.

## Set up timed drops
1. Enable Developer Mode in Discord and copy the ID of the channel where drops should appear.
2. Set `SPAWN_CHANNEL_ID` in `.env`.
3. Adjust `SPAWN_INTERVAL_MINUTES` and `SPAWN_CHANCE` in `.env`.
4. Restart the bot.

## Edit content
- Add items to `ITEMS` and their IDs/weights to `LOOT_TABLES` in `game.py`.
- Add missions to `MISSIONS`.
- Add enemies to `ENEMIES`.
- Keep item IDs unique and stable. Never generate stats at drop time.
- The power-level formula is in `calculate_power_level()`.

## Important limitations of this first version
- The demo mission-complete command is manually invoked; it is a placeholder for proper objective tracking. Commands are mention-based, not slash commands.
- World-drop claim state is in memory, so drops that were active at the exact moment of a restart expire. Player inventory and character data remain saved in SQLite.
- Timed spawns are per process, not a distributed scheduler. Run only one bot instance against the same database.
- Image URLs are placeholders until you replace them.
- Free hosting services can sleep, have usage caps, or change plans. For reliable always-on operation, verify the current plan terms and persistent disk/database availability before deploying.
- Canon characters and settings are fan content. For a public server, use art you own or have permission to use and check platform/service terms.

## Suggested next upgrades
1. Add proper story chapters and objective counters tied to battle victories.
2. Persist active drops and battle sessions in SQLite so restarts restore them.
3. Add Devil Fruits, fighting styles, Haki progression, equipment slots, and rank exams.
4. Add a data validator and admin commands for managing catalog content without editing Python.
5. Add island unlocks, crew systems, PvP, trade, crafting, and raids after the core loop is balanced.
