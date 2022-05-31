import typing as tp
import logging
import sys
import traceback

from multimedia.media import Media
from multimedia.player import PlayerState

from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from telegram import ForceReply, Update
from telegram._utils.defaultvalue import DEFAULT_NONE
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
)

MESSAGE_SMALL_INTERNAL_ERROR = "😔 Что-то случилось и я теперь не могу работать."
MESSAGE_BIG_INTERNAL_ERROR = "😡🔧 Кое что случилось. Ошибку смотри ниже:\n```\n{}\n```"
MESSAGE_MEDIA_ADDED = "🎶🎶🎶 Добавили {} шт.:\n{}"
MESSAGE_LIST_PLAYLIST = """🎶🎶🎶 {}
Треков в плейлисте {} шт.:
{}"""
MESSAGE_UNABLE_TO_PLAY_EMPTY = (
    "⚠️ Невозможно поставить на паузу или продолжить. Плеер ничего не играет."
)
MESSAGE_SKIP_SUCCESS = "💩 Трек был пропущен."

MESSAGE_PAUSE_SUCCESS = "⏸️ Музыка успешно поставлена на паузу"
MESSAGE_RESUME_SUCCESS = "▶️ Мызыка успешно продолжена"
MESSAGE_PLAYER_PLAYING = "Сейчас играет: `{}`."
MESSAGE_PLAYER_PAUSED = "Сейчас пауза на `{}`."
MESSAGE_PLAYER_STOPPED = "Сейчас ничего не играет."

AddToPlaylistCallback = tp.Callable[[str], tp.List[Media]]
ListPlaylistCallback = tp.Callable[[], tp.List[Media]]
CurrentMediaCallback = tp.Callable[[], tp.Optional[Media]]
CurrentPlayerStateCallback = tp.Callable[[], PlayerState]
PauseCallback = tp.Callable[[], None]
ResumeCallback = tp.Callable[[], None]
SkipCallback = tp.Callable[[], None]

logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self, token: str):
        self._debug_mode = True

        self._application = Application.builder().token(token).build()
        self._application.add_handler(CommandHandler("p", self.on_play_command))
        self._application.add_handler(CommandHandler("info", self.on_info_command))
        self._application.add_handler(CommandHandler("playlist", self.on_info_command))
        self._application.add_handler(CommandHandler("skip", self.on_skip_command))
        self._application.add_handler(
            MessageHandler(filters.Regex(r"^\\o$"), self.on_hi)
        )

        self._add_to_playlist_cb: tp.Optional[AddToPlaylistCallback] = None
        self._list_playlist_cb: tp.Optional[ListPlaylistCallback] = None
        self._current_media_cb: tp.Optional[CurrentMediaCallback] = None
        self._current_player_state_cb: tp.Optional[CurrentPlayerStateCallback] = None
        self._pause_cb: tp.Optional[PauseCallback] = None
        self._resume_cb: tp.Optional[ResumeCallback] = None
        self._skip_cb: tp.Optional[SkipCallback] = None

    async def run(self):
        def error_callback(exc) -> None:
            self._application.create_task(
                self._application.process_error(error=exc, update=None)
            )

        # Running bot wtf?!
        await self._application.initialize()
        await self._application.updater.start_polling(
            poll_interval=0.0,
            timeout=10,
            bootstrap_retries=-1,
            read_timeout=2,
            write_timeout=DEFAULT_NONE,
            connect_timeout=DEFAULT_NONE,
            pool_timeout=DEFAULT_NONE,
            allowed_updates=None,
            drop_pending_updates=None,
            error_callback=error_callback,  # if there is an error in fetching updates
        )
        await self._application.start()

    async def on_hi(self, update: Update, context: CallbackContext.DEFAULT_TYPE):
        try:
            await update.message.reply_text("\\o")
        except Exception:
            logger.error("Unable to perform skip command.", exc_info=True)
            await self._exception_notify(update)

    async def on_skip_command(
        self, update: Update, context: CallbackContext.DEFAULT_TYPE
    ):
        try:
            if self._skip_cb is None:
                await self._error_notify(update, f"{self._skip_cb=}")

            await self._skip_cb()

            await update.message.reply_text(MESSAGE_SKIP_SUCCESS)
        except Exception:
            logger.error("Unable to perform skip command.", exc_info=True)
            await self._exception_notify(update)

    async def on_info_command(
        self, update: Update, context: CallbackContext.DEFAULT_TYPE
    ):
        try:
            if self._list_playlist_cb is None:
                await self._error_notify(update, f"{self._list_playlist_cb=}")
                return

            if self._current_media_cb is None:
                await self._error_notify(update, f"{self._current_media_cb=}")
                return

            if self._current_player_state_cb is None:
                await self._error_notify(update, f"{self.current_player_state_cb=}")
                return

            medias = self._list_playlist_cb()

            await update.message.reply_text(
                MESSAGE_LIST_PLAYLIST.format(
                    await self._player_status_fmt(),
                    len(medias),
                    "\n".join([f" - `{await media.media_title}`" for media in medias]),
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            logger.error("Unable to perform info/playlist command.", exc_info=True)
            await self._exception_notify(update)

    async def _player_status_fmt(self):
        state = self._current_player_state_cb()
        if state == PlayerState.Playing:
            return MESSAGE_PLAYER_PLAYING.format(
                await self._current_media_cb().media_title
            )
        elif state == PlayerState.Paused:
            return MESSAGE_PLAYER_PAUSED.format(
                await self._current_media_cb().media_title
            )
        elif state == PlayerState.Stopped:
            return MESSAGE_PLAYER_STOPPED

    async def on_play_command(
        self,
        update: Update,
        context: CallbackContext.DEFAULT_TYPE,
    ):
        try:
            if self._add_to_playlist_cb is None:
                await self._error_notify(update, f"{self._add_to_playlist_cb=}")
                return

            url = update.message.text[2:].strip()

            # If no url specified - trying to control player
            if not url:
                state = self._current_player_state_cb()
                if state == PlayerState.Paused:
                    await self._resume_cb()
                    update.message.reply_text(MESSAGE_RESUME_SUCCESS)
                elif state == PlayerState.Playing:
                    await self._pause_cb()
                    update.message.reply_text(MESSAGE_PAUSE_SUCCESS)
                elif state == PlayerState.Stopped:
                    update.message.reply_text(MESSAGE_UNABLE_TO_PLAY_EMPTY)
                return

            medias = await self._add_to_playlist_cb(url)

            await update.message.reply_text(
                MESSAGE_MEDIA_ADDED.format(
                    len(medias),
                    "\n".join([f"- `{await media.media_title}`" for media in medias]),
                ),
                parse_mode=ParseMode.MARKDOWN,
            )

        except Exception:
            logger.error("Unable to perform play command.", exc_info=True)
            await self._exception_notify(update)

    async def _exception_notify(self, update: Update):
        if self._debug_mode:
            await update.message.reply_text(
                MESSAGE_BIG_INTERNAL_ERROR.format(traceback.format_exc()),
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await update.message.reply_text(MESSAGE_SMALL_INTERNAL_ERROR)

    async def _error_notify(self, update: Update, message: str):
        if self._debug_mode:
            await update.message.reply_text(
                MESSAGE_BIG_INTERNAL_ERROR.format(message),
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await update.message.reply_text(MESSAGE_SMALL_INTERNAL_ERROR)

    @property
    def add_to_playlist_cb(self) -> tp.Optional[AddToPlaylistCallback]:
        return self._add_to_playlist_cb

    @add_to_playlist_cb.setter
    def add_to_playlist_cb(self, v: AddToPlaylistCallback):
        self._add_to_playlist_cb = v

    @property
    def list_playlist_cb(self) -> tp.Optional[ListPlaylistCallback]:
        return self._list_playlist_cb

    @list_playlist_cb.setter
    def list_playlist_cb(self, v: ListPlaylistCallback):
        self._list_playlist_cb = v

    @property
    def current_media_cb(self) -> tp.Optional[CurrentMediaCallback]:
        return self._current_media_cb

    @current_media_cb.setter
    def current_media_cb(self, v: CurrentMediaCallback):
        self._current_media_cb = v

    @property
    def current_player_state_cb(self) -> tp.Optional[CurrentPlayerStateCallback]:
        return self._current_player_state_cb

    @current_player_state_cb.setter
    def current_player_state_cb(self, v: CurrentPlayerStateCallback):
        self._current_player_state_cb = v

    @property
    def pause_cb(self) -> tp.Optional[PauseCallback]:
        return self._pause_cb

    @pause_cb.setter
    def pause_cb(self, v: PauseCallback):
        self._pause_cb = v

    @property
    def resume_cb(self) -> tp.Optional[ResumeCallback]:
        return self._resume_cb

    @resume_cb.setter
    def resume_cb(self, v: ResumeCallback):
        self._resume_cb = v

    @property
    def skip_cb(self) -> tp.Optional[SkipCallback]:
        return self._skip_cb

    @skip_cb.setter
    def skip_cb(self, v: SkipCallback):
        self._skip_cb = v
