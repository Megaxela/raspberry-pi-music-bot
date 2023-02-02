import asyncio
import typing as tp
import logging
import enum

import vlc
from async_property import async_property

from multimedia.utils import (
    vlc_flags_or,
    wrap_vlc_event,
)


class MediaType(enum.Enum):
    Unknown = 0
    File = 1
    Directory = 2
    Disc = 3
    Stream = 4
    Playlist = 5


class Media:
    def __init__(self, mrl: str, from_vlc_media: tp.Optional[vlc.Media] = None):
        if from_vlc_media is None:
            self._base_url = mrl
            self._media = vlc.Media(mrl)
        else:
            self._base_url = from_vlc_media.get_mrl()
            self._media = from_vlc_media
        self._metadata_loading_future: asyncio.Future = None

    @property
    def vlc_media(self) -> vlc.Media:
        return self._media

    @property
    def mrl(self) -> str:
        return self._base_url

    @async_property
    async def media_title(self) -> tp.Optional[str]:
        title = self._media.get_meta(vlc.Meta.Title)
        if title is None:
            await self.load_metadata()
            title = self._media.get_meta(vlc.Meta.Title)
        return title

    @async_property
    async def subitems(self) -> vlc.MediaList:
        await self.load_metadata()

        return [
            Media(None, from_vlc_media=vlc_med) for vlc_med in self._media.subitems()
        ]

    async def load_metadata(self):
        if self._metadata_loading_future is None:
            # Await parsing finished event
            ev = self._media.event_manager()
            self._metadata_loading_future = wrap_vlc_event(
                ev, vlc.EventType.MediaParsedChanged
            )

            self._media.parse_with_options(
                vlc_flags_or(
                    vlc.MediaParseFlag.local,
                    vlc.MediaParseFlag.fetch_local,
                    vlc.MediaParseFlag.network,
                    vlc.MediaParseFlag.fetch_network,
                ),
                timeout=-1,
            )

        await self._metadata_loading_future
