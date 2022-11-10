import typing as tp

from .basic_parser import BasicParser
from clients.youtube import YoutubePlaylistClient


class YoutubePlaylistParser(BasicParser):
    def __init__(self):
        self._client = YoutubePlaylistClient()

    async def is_suitable(self, url: str) -> bool:
        return await self._client.is_playlist(url)

    async def parse_media(self, url: str) -> tp.List[str]:
        return await self._client.parse_media(url)
