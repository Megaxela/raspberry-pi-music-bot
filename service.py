import asyncio
import typing as tp
import logging

from tg_bot.bot import TelegramBot
from multimedia.player import Player, PlayerState
from multimedia.media import Media
from multimedia.playlist import Playlist
from database import Database

logger = logging.getLogger(__name__)


def propg(obj, prop):
    def getter():
        return getattr(obj, prop)

    return getter


def props(obj, prop):
    def setter(v):
        setattr(obj, prop, v)

    return setter


class Service:
    def __init__(self, telegram_bot_token: str, database_path: str):
        self._database = Database(database_path)
        self._bot = TelegramBot(
            telegram_bot_token,
            self._database,
        )
        self._playlist = Playlist()
        self._player = Player()

        # Setting up bot
        self._bot.add_to_playlist_cb = self._on_add_content
        self._bot.list_playlist_cb = propg(self._playlist, "items")
        self._bot.current_media_cb = propg(self._player, "current_media")
        self._bot.current_player_state_cb = propg(self._player, "state")
        self._bot.pause_cb = self._player.pause
        self._bot.resume_cb = self._player.resume
        self._bot.skip_cb = self.play_next
        self._bot.get_seek_cb = propg(self._player, "cursor")
        self._bot.set_seek_cb = props(self._player, "cursor")
        self._bot.get_volume_cb = propg(self._player, "volume")
        self._bot.set_volume_cb = props(self._player, "volume")
        self._bot.get_cursor_cb = propg(self._player, "cursor")
        self._bot.set_cursor_cb = props(self._player, "cursor")
        self._bot.get_length_cb = propg(self._player, "length")

    async def run(self):
        # Initializing database
        await self._database.initialize()

        # Running bot coro
        await self._bot.run()

        # Enable autoplay
        # todo: move to detached coroutine
        await self.autoplay()

    async def _on_add_content(self, mri: str):
        content = await self._playlist.add_content(mri)

        if self._player.state == PlayerState.Stopped:
            await self.play_next()

        return content

    async def play_next(self) -> bool:
        if not self._playlist.items:
            result = self._player.state in (PlayerState.Playing, PlayerState.Paused)
            await self._player.stop()
            return result

        last_media = self._playlist.last
        self._playlist.pop_last()

        logger.info(
            "Playing '%s' next. There is %d medias left in playlist",
            await last_media.media_title,
            len(self._playlist.items),
        )

        await self._bot.notify_currently_playing(last_media)

        if self._player.state in (PlayerState.Playing, PlayerState.Paused):
            await self._player.stop()

        await self._player.play(last_media)
        return True

    async def autoplay(self):
        while True:
            await self._player.wait_until_end_reached()
            logger.info("Track end has been reached. Autoplaying next.")

            if not self._playlist.items:
                logger.info("Nothing to play next.")
                continue

            await self.play_next()
