import typing as tp
import logging
import asyncio
import random

from multimedia.media import Media


logger = logging.getLogger(__name__)


class Playlist:
    def __init__(self):
        self._queue: tp.List[Media] = []

    async def add_content(self, mri: str) -> tp.List[Media]:
        logger.info("Adding content with mri: '%s'", mri)
        media = Media(mri)

        flatten_medias = await self._unwrap_media(media)

        self._queue += flatten_medias

        return flatten_medias

    def clear(self):
        self._queue.clear()

    def shuffle(self):
        random.shuffle(self._queue)

    @property
    def items(self):
        return self._queue

    @property
    def last(self):
        return self._queue[0]

    def pop_last(self):
        self._queue = self._queue[1:]

    async def _unwrap_media(self, media: Media, level=0) -> tp.List[Media]:
        submedia = await media.subitems
        if not submedia:
            return [media]

        return submedia

        # note: disabling recursive parsing to support huge playlists.
        # Concat all lists with media
        # return sum(
        #     [(await self._unwrap_media(m, level + 1)) for m in submedia],
        #     list(),
        # )
