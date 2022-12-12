import asyncio
import logging
import sys
import os
import ctypes

import vlc

from multimedia.media import Media
from multimedia.player import Player
from multimedia.playlist import Playlist

from service import Service

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)-8s] [%(funcName)-30s] [%(filename)+20s:%(lineno)-4d] %(message)s",
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


libc = ctypes.CDLL(ctypes.util.find_library("c"))


@vlc.CallbackDecorators.LogCb
def vlc_log_handler(instance, log_level, ctx, fmt, va_list):
    levels = [
        logging.INFO,
        logging.ERROR,
        logging.WARN,
        logging.DEBUG,
        logging.CRITICAL,
    ]

    # Fetching context info
    module, log_source_file, log_source_line = vlc.libvlc_log_get_context(ctx)

    log_source_file = log_source_file.decode("utf-8")
    module = module.decode("utf-8")

    message_buffer = ctypes.create_string_buffer(16384)
    libc.vsprintf(message_buffer, fmt, ctypes.cast(va_list, ctypes.c_void_p))

    message = message_buffer.value.decode("utf-8")

    logger.handle(
        logger.makeRecord(
            name=logger.name,
            level=levels[log_level],
            fn=log_source_file,
            lno=log_source_line,
            msg=message,
            args=[],
            exc_info=None,
            func=f"vlc {module}",
        )
    )


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

    vlc._default_instance.log_set(vlc_log_handler, None)

    asyncio.run(main())
