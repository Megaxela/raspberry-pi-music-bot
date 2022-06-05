import asyncio
import logging
import sys
import os

import vlc

from multimedia.media import Media
from multimedia.player import Player
from multimedia.playlist import Playlist

from service import Service

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def main():
    try:
        service = Service(
            telegram_bot_token=os.getenv("TG_BOT_TOKEN"),
            database_path="db.sqlite3",
        )

        await service.run()

        while True:
            await asyncio.sleep(1000)

        return
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    vlc._default_instance = vlc.Instance(
        [
            "--no-video",
            "--audio-resampler=speex_resampler",
            "--advanced",
            "--speex-resampler-quality",
            "0",
            "-v",
        ]
    )

    asyncio.run(main())
