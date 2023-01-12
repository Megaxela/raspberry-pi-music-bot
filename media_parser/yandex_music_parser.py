import typing as tp
import re
import os

from .basic_parser import BasicParser
from clients.youtube import YoutubePlaylistClient

BASE_URL_RE = re.compile(r"music\.yandex\.ru")
PLAYLIST_RE = re.compile(r"/users/.*/playlists/[0-9]+")
TRACK_RE = re.compile(r"/album/[0-9]+/track/[0-9]+")
ALBUM_RE = re.compile(r"/album/[0-9]+")


class YandexMusicParser(BasicParser):
    def __init__(self):
        self._token = os.getenv("YA_MUSIC_TOKEN")

    async def is_suitable(self, url: str) -> bool:
        return all(
            (
                BASE_URL_RE.search(url),
                any(
                    (
                        PLAYLIST_RE.search(url),
                        TRACK_RE.search(url),
                        ALBUM_RE.search(url),
                    )
                ),
            )
        )

    async def parse_media(self, url: str) -> tp.List[str]:
        return f"{url}?access_token={self._token}"
