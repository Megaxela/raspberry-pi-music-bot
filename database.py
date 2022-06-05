import typing as tp
import asyncio

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

QUERY_CREATE_PLAY_MESSAGES_TABLE = """
CREATE TABLE IF NOT EXISTS "play_messages" (
    "id" INTEGER NOT NULL UNIQUE,
    PRIMARY KEY("id" AUTOINCREMENT)
);
"""

QUERY_CREATE_PLAY_MESSAGES_URIS_TABLE = """
CREATE TABLE IF NOT EXISTS "play_messages_uris" (
    "id" INTEGER NOT NULL UNIQUE,
    "play_message_id" INTEGER NOT NULL,
    "uri" TEXT NOT NULL,
    FOREIGN KEY("play_message_id") REFERENCES "play_messages"("id"),
    PRIMARY KEY("id" AUTOINCREMENT)
);
"""

QUERY_INSERT_PLAY_MESSAGE = """
INSERT INTO play_messages DEFAULT VALUES;
"""

QUERY_INSERT_PLAY_MESSAGE_URI = """
INSERT INTO play_messages_uris(play_message_id, uri) VALUES (?, ?);
"""

QUERY_SELECT_URIS_FROM_PLAY_MESSAGE = """
SELECT uri FROM play_messages_uris WHERE play_message_id = ?;
"""


class Database:
    def __init__(self, path: str):
        self._db: tp.Optional[aiosqlite.Connection] = None
        self._path: str = path

    @staticmethod
    async def create(self, path) -> "Database":
        db = Database(path)
        await db.initialize()

    async def add_play_message(self, uris: tp.List[str]) -> int:
        message_id = (await self._db.execute_insert(QUERY_INSERT_PLAY_MESSAGE))[0]
        await asyncio.gather(
            *[
                self._db.execute(QUERY_INSERT_PLAY_MESSAGE_URI, (message_id, uri))
                for uri in uris
            ]
        )
        await self._db.commit()
        return message_id

    async def fetch_uris_from_play_message(self, message_id) -> tp.List[str]:
        return [
            row[0]
            for row in await self._db.execute_fetchall(
                QUERY_SELECT_URIS_FROM_PLAY_MESSAGE, (message_id,)
            )
        ]

    async def initialize(self):
        self._db = await aiosqlite.connect(self._path)

        await self._db.execute(QUERY_CREATE_GROUPS_TABLE)
        await self._db.execute(QUERY_CREATE_PLAYLIST_TABLE)
        await self._db.execute(QUERY_CREATE_PLAY_MESSAGES_TABLE)
        await self._db.execute(QUERY_CREATE_PLAY_MESSAGES_URIS_TABLE)
        await self._db.commit()
