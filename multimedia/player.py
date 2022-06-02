import asyncio
import typing as tp
import logging
import enum
from functools import reduce

import vlc
from async_property import async_property

from multimedia.utils import (
    vlc_flags_or,
    wrap_vlc_event,
)
from .media import Media

logger = logging.getLogger(__name__)

# Buffering      -> Playing
# Ended          -> Stopped
# Error          -> Stopped
# NothingSpecial -> Stopped
# Opening        -> Playing
# Paused         -> Paused
# Stopped        -> Stopped
class PlayerState(enum.Enum):
    Playing = enum.auto()
    Stopped = enum.auto()
    Paused = enum.auto()


class Player:
    def __init__(self):
        self._player: vlc.MediaPlayer = vlc.MediaPlayer()
        self._current_media: tp.Optional[Media] = None
        self._volume = 100

        # Setting up player object
        self._player.audio_set_volume(self._volume)
        loop = asyncio.get_event_loop()

        ev: vlc.EventManager = self._player.event_manager()
        ev.event_attach(
            vlc.EventType.MediaPlayerEndReached,
            lambda ev: loop.call_soon_threadsafe(self.on_media_player_end_reached),
        )

    async def wait_until_end_reached(self):
        ev: vlc.EventManager = self._player.event_manager()
        await wrap_vlc_event(ev, vlc.EventType.MediaPlayerEndReached)

    async def pause(self):
        if self.state != PlayerState.Playing:
            return

        ev: vlc.EventManager = self._player.event_manager()
        fut = wrap_vlc_event(ev, vlc.EventType.MediaPlayerPaused)

        self._player.set_pause(True)

        await fut

    async def resume(self):
        if self.state != PlayerState.Paused:
            return
        ev: vlc.EventManager = self._player.event_manager()
        fut = wrap_vlc_event(ev, vlc.EventType.MediaPlayerPlaying)

        self._player.set_pause(False)

        await fut

    async def play(self, media: Media):
        logger.info(f"Playing '{media.mrl}'")

        # Attempting to load metadata before play
        await media.load_metadata()

        # Set current media
        self._current_media = media

        # Set media to player
        self._player.set_media(self._current_media.vlc_media)

        # Playing...
        return self._player.play() == 0

    async def stop(self):
        self._current_media = None
        self._player.stop()

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, new_val):
        self._volume = new_val
        self._player.audio_set_volume(new_val)

    @property
    def cursor(self):
        return int(self._player.get_time() / 1000)

    @cursor.setter
    def cursor(self, new_val: int):
        self._player.set_time(int(new_val * 1000))

    @property
    def length(self):
        return int(self._player.get_length() / 1000)

    @property
    def current_media(self) -> tp.Optional[Media]:
        return self._current_media

    @property
    def state(self) -> PlayerState:
        status_mapping = {
            vlc.State.Opening: PlayerState.Playing,
            vlc.State.Buffering: PlayerState.Playing,
            vlc.State.Playing: PlayerState.Playing,
            vlc.State.Paused: PlayerState.Paused,
            vlc.State.Stopped: PlayerState.Stopped,
            vlc.State.Ended: PlayerState.Stopped,
            vlc.State.Error: PlayerState.Stopped,
            vlc.State.NothingSpecial: PlayerState.Stopped,
        }

        return status_mapping[self._player.get_state()]

    def on_media_player_end_reached(self, event: vlc.Event):
        self._current_media = None
