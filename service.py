import asyncio
import typing as tp
import logging

from tg_bot.bot import TelegramBot
from multimedia.player import Player, PlayerState
from multimedia.media import Media
from multimedia.playlist import Playlist
from database import Database
from media_parser.youtube_playlist_parser import YoutubePlaylistParser
from media_parser.yandex_music_parser import YandexMusicParser

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

        # Preparing extention parsers
        self._media_parsers = [
            YoutubePlaylistParser(),
            YandexMusicParser(),
        ]

        # Setting up bot
        self._bot.callbacks.add_to_playlist = self._on_add_content
        self._bot.callbacks.list_playlist = propg(self._playlist, "items")
        self._bot.callbacks.current_media = propg(self._player, "current_media")
        self._bot.callbacks.current_player_state = propg(self._player, "state")
        self._bot.callbacks.pause = self._player.pause
        self._bot.callbacks.resume = self._player.resume
        self._bot.callbacks.skip = self.play_next
        self._bot.callbacks.skipall = self.clear_playlist
        self._bot.callbacks.shuffle = self.shuffle
        self._bot.callbacks.get_seek = propg(self._player, "cursor")
        self._bot.callbacks.set_seek = props(self._player, "cursor")
        self._bot.callbacks.get_volume = propg(self._player, "volume")
        self._bot.callbacks.set_volume = props(self._player, "volume")
        self._bot.callbacks.get_cursor = propg(self._player, "cursor")
        self._bot.callbacks.set_cursor = props(self._player, "cursor")
        self._bot.callbacks.get_length = propg(self._player, "length")

    async def run(self):
        # Initializing database
        await self._database.initialize()

        # Running bot coro
        await self._bot.run()

        # Enable autoplay
        # todo: move to detached coroutine
        await self.autoplay()

    async def _on_add_content(self, mri: str):
        # Trying to preparse media
        for parser in self._media_parsers:
            # Does parser is suitable for provided url
            if not await parser.is_suitable(mri):
                continue

            # Trying to parse media with parser
            try:
                parsed_media = await parser.parse_media(mri)
            except Exception:
                logger.warning(
                    "Preparsing '%s' with '%s' failed",
                    mri,
                    str(parser),
                    exc_info=True,
                )
                continue

            if not isinstance(parsed_media, list):
                logger.warning(
                    "Parser '%s' returned '%s' instead of 'list'",
                    str(parser),
                    type(parsed_media),
                )
                break

            result = []
            logger.info(
                "Adding %d medias parsed with '%s': %s",
                len(parsed_media),
                str(parser),
                ", ".join(parsed_media),
            )
            for media in parsed_media:
                result += await self._on_add_content(media)
            return result

        content = await self._playlist.add_content(mri)

        if self._player.state == PlayerState.Stopped:
            await self.play_next()

        return content

    async def shuffle(self):
        self._playlist.shuffle()

    async def clear_playlist(self) -> bool:
        self._playlist.clear()
        return True

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
