import aiosqlite
from game import ITEMS, calculate_power_level, BASE_STATS

class Database:
    def __init__(self, path):
        self.path = path

    async def initialize(self):
        async with aiosqlite.connect(self.path) as db:
            await db.executescript("""
            CREATE TABLE IF NOT EXISTS players (
                user_id INTEGER PRIMARY KEY, name TEXT NOT NULL, level INTEGER NOT NULL DEFAULT 1,
                xp INTEGER NOT NULL DEFAULT 0, berries INTEGER NOT NULL DEFAULT 250,
                hp INTEGER NOT NULL DEFAULT 100, max_hp INTEGER NOT NULL DEFAULT 100,
                stamina INTEGER NOT NULL DEFAULT 50, max_stamina INTEGER NOT NULL DEFAULT 50,
                strength INTEGER NOT NULL DEFAULT 10, defense INTEGER NOT NULL DEFAULT 8,
                speed INTEGER NOT NULL DEFAULT 10, vitality INTEGER NOT NULL DEFAULT 10,
                technique INTEGER NOT NULL DEFAULT 8, haki INTEGER NOT NULL DEFAULT 0,
                rank TEXT NOT NULL DEFAULT 'E', island TEXT NOT NULL DEFAULT 'Dawn Island'
            );
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
                item_id TEXT NOT NULL, source TEXT NOT NULL, equipped INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS cooldowns (
                user_id INTEGER NOT NULL, action TEXT NOT NULL, used_at REAL NOT NULL,
                PRIMARY KEY(user_id, action)
            );
            CREATE TABLE IF NOT EXISTS missions (
                user_id INTEGER NOT NULL, mission_id TEXT NOT NULL, status TEXT NOT NULL,
                PRIMARY KEY(user_id, mission_id)
            );
            """)
            await db.commit()

    async def create_player(self, user_id, name):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT 1 FROM players WHERE user_id=?", (user_id,))
            if await cur.fetchone():
                return False
            await db.execute("INSERT INTO players(user_id,name) VALUES(?,?)", (user_id, name))
            await db.commit()
            return True

    async def ensure_player(self, user_id, name):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT OR IGNORE INTO players(user_id,name) VALUES(?,?)", (user_id, name))
            await db.commit()

    async def get_player(self, user_id):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM players WHERE user_id=?", (user_id,))
            return dict(await cur.fetchone())

    async def get_inventory(self, user_id):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT item_id, source, equipped, COUNT(*) AS quantity FROM inventory WHERE user_id=? GROUP BY item_id, source, equipped ORDER BY id DESC", (user_id,))
            rows = [dict(r) for r in await cur.fetchall()]
            for row in rows:
                row["item"] = ITEMS.get(row["item_id"])
            return rows

    async def add_item(self, user_id, item_id, source="unknown"):
        if item_id not in ITEMS:
            return False
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT INTO inventory(user_id,item_id,source) VALUES(?,?,?)", (user_id, item_id, source))
            await db.commit()
        return True

    async def equip_item(self, user_id, item_id):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT id FROM inventory WHERE user_id=? AND item_id=? ORDER BY id LIMIT 1", (user_id, item_id))
            row = await cur.fetchone()
            if not row:
                return False
            item = ITEMS[item_id]
            await db.execute("UPDATE inventory SET equipped=0 WHERE user_id=? AND item_id IN (SELECT item_id FROM inventory WHERE user_id=?)", (user_id, user_id))
            await db.execute("UPDATE inventory SET equipped=1 WHERE id=?", (row[0],))
            await db.commit()
            return True

    async def get_effective_stats(self, user_id):
        player = await self.get_player(user_id)
        stats = {k: player[k] for k in BASE_STATS}
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT item_id FROM inventory WHERE user_id=? AND equipped=1", (user_id,))
            rows = await cur.fetchall()
        for (item_id,) in rows:
            item = ITEMS.get(item_id, {})
            for stat, value in item.get("stats", {}).items():
                if stat in stats:
                    stats[stat] += value
        return stats

    async def change_hp(self, user_id, delta):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE players SET hp=MIN(max_hp,MAX(0,hp+?)) WHERE user_id=?", (delta, user_id))
            await db.commit()

    async def set_hp(self, user_id, hp):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE players SET hp=MIN(max_hp,MAX(1,?)) WHERE user_id=?", (hp, user_id))
            await db.commit()

    async def change_stamina(self, user_id, delta):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE players SET stamina=MIN(max_stamina,MAX(0,stamina+?)) WHERE user_id=?", (delta, user_id))
            await db.commit()

    async def regen_stamina(self, user_id, amount):
        await self.change_stamina(user_id, amount)

    async def reward(self, user_id, xp, berries):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE players SET xp=xp+?, berries=berries+? WHERE user_id=?", (xp, berries, user_id))
            cur = await db.execute("SELECT level,xp FROM players WHERE user_id=?", (user_id,))
            level, total_xp = await cur.fetchone()
            new_level = max(1, total_xp // 100 + 1)
            if new_level > level:
                gains = new_level - level
                await db.execute("UPDATE players SET level=?, max_hp=max_hp+?, hp=MIN(max_hp+?,hp+?), strength=strength+?, defense=defense+?, vitality=vitality+?, technique=technique+?, max_stamina=max_stamina+?, stamina=MIN(max_stamina+?,stamina+?) WHERE user_id=?",
                                 (new_level, gains*8, gains*8, gains*8, gains*2, gains, gains, gains, gains*3, gains*3, gains*3, user_id))
            await db.commit()

    async def cooldown_ready(self, user_id, action, seconds):
        import time
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT used_at FROM cooldowns WHERE user_id=? AND action=?", (user_id, action))
            row = await cur.fetchone()
            return not row or time.time() - row[0] >= seconds

    async def set_cooldown(self, user_id, action):
        import time
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT OR REPLACE INTO cooldowns(user_id,action,used_at) VALUES(?,?,?)", (user_id, action, time.time()))
            await db.commit()

    async def mission_completed(self, user_id, mission_id):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT status FROM missions WHERE user_id=? AND mission_id=?", (user_id, mission_id))
            row = await cur.fetchone()
            return bool(row and row[0] == "completed")

    async def has_active_mission(self, user_id, mission_id):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT status FROM missions WHERE user_id=? AND mission_id=?", (user_id, mission_id))
            row = await cur.fetchone()
            return bool(row and row[0] == "active")

    async def accept_mission(self, user_id, mission_id):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT OR IGNORE INTO missions(user_id,mission_id,status) VALUES(?,?,'active')", (user_id, mission_id))
            await db.commit()

    async def complete_mission(self, user_id, mission_id):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE missions SET status='completed' WHERE user_id=? AND mission_id=?", (user_id, mission_id))
            await db.commit()
