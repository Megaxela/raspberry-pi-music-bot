import typing as tp
import re
import os
from urllib.parse import urlparse

from .basic_parser import BasicParser

BASE_URL_RE = re.compile(r"music\.yandex\.(ru|com)")
PLAYLIST_RE = re.compile(r"/users/.*/playlists/[0-9]+")
TRACK_RE = re.compile(r"/album/[0-9]+/track/[0-9]+")
ALBUM_RE = re.compile(r"/album/[0-9]+")

TOKEN_RE = re.compile(r"\?access_token=.+")


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
                not TOKEN_RE.search(url),
            )
        )

    async def parse_media(self, url: str) -> tp.List[str]:
        url = urlparse(url)._replace(query="").geturl()
        return [f"{url}?access_token={self._token}"]


if __name__ == "__main__":
    import asyncio

    u = "https://music.yandex.com/album/21370360/track/101378847"
    parser = YandexMusicParser()

    is_suitable = asyncio.new_event_loop().run_until_complete(parser.is_suitable(u))

    print(
        (
            BASE_URL_RE.search(u),
            any(
                (
                    PLAYLIST_RE.search(u),
                    TRACK_RE.search(u),
                    ALBUM_RE.search(u),
                )
            ),
            not TOKEN_RE.search(u),
        )
    )
    if is_suitable:
        print(asyncio.new_event_loop().run_until_complete(parser.parse_media(u)))
