import typing as tp

import aiosqlite

QUERY_CREATE_GROUPS_TABLE = """
CREATE TABLE IF NOT EXISTS "groups" (
    "id" INTEGER NOT NULL UNIQUE,
    "group_id" TEXT,
    PRIMARY KEY("id" AUTOINCREMENT)
);
"""

QUERY_CREATE_PLAYLIST_TABLE = """
CREATE TABLE IF NOT EXISTS "active_playlist" (
    "id" INTEGER UNIQUE,
    "mri" TEXT NOT NULL,
    PRIMARY KEY("id" AUTOINCREMENT)
);
"""


class Database:
    def __init__(self, path: str):
        self._db: tp.Optional[aiosqlite.Connection] = None
        self._path: str = path

    @staticmethod
    async def create(self, path) -> "Database":
        db = Database(path)
        await db.initialize()

    async def initialize(self):
        self._db = await aiosqlite.connect(self._path)

        await self._db.execute(QUERY_CREATE_GROUPS_TABLE)
        await self._db.execute(QUERY_CREATE_PLAYLIST_TABLE)
