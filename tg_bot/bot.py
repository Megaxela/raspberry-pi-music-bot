import typing as tp
import logging
import sys
import traceback
import json

from multimedia.media import Media
from multimedia.player import PlayerState
from database import Database

from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from telegram import (
    CallbackQuery,
    ForceReply,
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram._utils.defaultvalue import DEFAULT_NONE
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    CallbackQueryHandler,
)

MESSAGE_REPLY_TEMPLATE = "⚙️ {}: {}"
MESSAGE_SMALL_INTERNAL_ERROR = "😔 Что-то случилось и я теперь не могу работать."
MESSAGE_BIG_INTERNAL_ERROR = "😡🔧 Кое что случилось. Ошибку смотри ниже:\n```\n{}\n```"
MESSAGE_MEDIA_ADDED = "🎶 Добавили {} шт.:\n{}"
MESSAGE_MEDIA_READDED = "🎶 Передобавили {} шт.:\n{}"
MESSAGE_MEDIA_ADDING = "🤔 Добавляю:\n{}"
MESSAGE_MEDIA_READDING = "🤔 Передобавляю:\n{}"
MESSAGE_MEDIA_READDING_FAIL = "😔 Похоже, что это сообщение не может быть передобавлено."
MESSAGE_LIST_PLAYLIST = """🎶 {}

Треков в плейлисте {} шт.:
{}"""
MESSAGE_UNABLE_TO_PLAY_EMPTY = (
    "⚠️ Невозможно поставить на паузу или продолжить. Плеер ничего не играет."
)
MESSAGE_SKIPPING = "🤔 Пытаемся пропустить..."
MESSAGE_SKIP_SUCCESS = "💩 Трек был пропущен."
MESSAGE_SKIP_FAIL = "🤔 Нечего пропускать."

MESSAGE_PAUSE_SUCCESS = "⏸️ Музыка успешно поставлена на паузу"
MESSAGE_RESUME_SUCCESS = "▶️ Музыка успешно продолжена"
MESSAGE_PLAYER_PLAYING = "Сейчас играет:\n`{}`\n`{}/{}`"
MESSAGE_PLAYER_PAUSED = "Сейчас пауза:\n`{}`\n`{}/{}`"
MESSAGE_PLAYER_STOPPED = "Сейчас ничего не играет."
MESSAGE_PLAYER_SEEK_STATUS = "Текущая позиция: `{}/{}`"

MESSAGE_VOLUME_STATUS = "Текущая громкость: `{}/100`"

MESSAGE_NOTIFY_AUTOPLAY = "🔔 Сейчас будет играть: `{}`"

KEYBOARD_BUTTON_REPEAT = "Повторить"
KEYBOARD_BUTTON_VOLUME_ADD = "+10"
KEYBOARD_BUTTON_VOLUME_SUB = "-10"

AddToPlaylistCallback = tp.Callable[[str], tp.Awaitable[tp.List[Media]]]
ListPlaylistCallback = tp.Callable[[], tp.List[Media]]
CurrentMediaCallback = tp.Callable[[], tp.Optional[Media]]
CurrentPlayerStateCallback = tp.Callable[[], PlayerState]
PauseCallback = tp.Callable[[], None]
ResumeCallback = tp.Callable[[], None]
SkipCallback = tp.Callable[[], tp.Awaitable[None]]
GetVolumeCallback = tp.Callable[[], int]
SetVolumeCallback = tp.Callable[[int], None]
GetCursorCallback = tp.Callable[[], int]
SetCursorCallback = tp.Callable[[int], None]
GetLengthCallback = tp.Callable[[int], None]
GetSeekCallback = tp.Callable[[], int]
SetSeekCallback = tp.Callable[[int], None]

logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self, token: str, database: Database):
        self._debug_mode = True

        self._database: Database = database

        self._application = Application.builder().token(token).build()
        self._application.add_handler(CallbackQueryHandler(self._callback_handler))
        self._application.add_handler(CommandHandler("p", self.on_play_command))
        self._application.add_handler(CommandHandler("info", self.on_info_command))
        self._application.add_handler(CommandHandler("playlist", self.on_info_command))
        self._application.add_handler(CommandHandler("skip", self.on_skip_command))
        self._application.add_handler(CommandHandler("volume", self.on_volume_command))
        self._application.add_handler(CommandHandler("v", self.on_volume_command))
        self._application.add_handler(CommandHandler("seek", self.on_seek_command))
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
        self._get_volume_cb: tp.Optional[GetVolumeCallback] = None
        self._set_volume_cb: tp.Optional[SetVolumeCallback] = None
        self._get_cursor_cb: tp.Optional[GetCursorCallback] = None
        self._set_cursor_cb: tp.Optional[SetCursorCallback] = None
        self._get_length_cb: tp.Optional[GetLengthCallback] = None
        self._get_seek_cb: tp.Optional[GetSeekCallback] = None
        self._set_seek_cb: tp.Optional[SetSeekCallback] = None

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

    async def notify_currently_playing(self, media: Media):
        await self._notify(MESSAGE_NOTIFY_AUTOPLAY.format(await media.media_title))

    async def on_hi(
        self,
        update: Update,
        context: CallbackContext.DEFAULT_TYPE,
    ):
        try:
            # Do not use self._reply here, cause it may delete initial message.
            await update.message.reply_text("\\o")
        except Exception:
            logger.error("Unable to perform skip command.", exc_info=True)
            await self._exception_notify(update)

    async def on_seek_command(
        self,
        update: Update,
        context: CallbackContext.DEFAULT_TYPE,
    ):
        try:
            if self._get_cursor_cb is None:
                await self._error_notify(update, f"{self._get_cursor_cb}")
                return
            if self._get_length_cb is None:
                await self._error_notify(update, f"{self._get_length_cb}")
                return
            if self._set_cursor_cb is None:
                await self._error_notify(update, f"{self._set_cursor_cb}")
                return

            if context.args:
                seek_change = context.args[0]
                if not seek_change:
                    await self._error_notify(update, f"{seek_change=}")
                    return

                # If seek is relatively changed
                try:
                    if seek_change[0] in {"-", "+"}:
                        seek_change_int = self._time_to_seconds(seek_change[1:])
                        new_seek = self._get_seek_cb()
                        if seek_change[0] == "-":
                            new_seek -= seek_change_int
                        else:
                            new_seek += seek_change_int
                    else:
                        new_seek = self._time_to_seconds(seek_change)

                    new_seek = sorted((0, new_seek, self._get_length_cb()))[1]
                    self._set_cursor_cb(new_seek)

                except ValueError:
                    await self._error_notify(update, f"{seek_change=}")
                    return

            seek = self._get_cursor_cb()
            length = self.get_length_cb()
            await self._reply(
                update,
                MESSAGE_PLAYER_SEEK_STATUS.format(
                    self._seconds_to_time(seek),
                    self._seconds_to_time(length),
                ),
            )

        except Exception:
            logger.error("Unable to perform seek command.", exc_info=True)
            await self._exception_notify(update)

    async def on_volume_command(
        self,
        update: Update,
        context: CallbackContext.DEFAULT_TYPE,
    ):
        try:
            if self._get_volume_cb is None:
                await self._error_notify(update, f"{self._get_volume_cb=}")
            if self._set_volume_cb is None:
                await self._error_notify(update, f"{self._set_volume_cb=}")

            # Change current volume
            if context.args:
                volume_change = context.args[0]
                if not volume_change:
                    await self._error_notify(update, f"{volume_change=}")
                    return

                # If volume is relatively changed
                try:
                    if volume_change[0] in {"-", "+"}:
                        volume_change_int = int(volume_change[1:])
                        new_vol = self._get_volume_cb()
                        if volume_change[0] == "-":
                            new_vol -= volume_change_int
                        else:
                            new_vol += volume_change_int
                    else:
                        new_vol = int(volume_change)

                    new_vol = sorted((0, new_vol, 100))[1]
                    self._set_volume_cb(new_vol)

                except ValueError:
                    await self._error_notify(update, f"{volume_change=}")
                    return

            # Print current volume
            volume = self._get_volume_cb()
            await self._reply(
                update,
                MESSAGE_VOLUME_STATUS.format(volume),
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                KEYBOARD_BUTTON_VOLUME_SUB,
                                callback_data=json.dumps(
                                    {"type": "volume", "value": -10}
                                ),
                            ),
                            InlineKeyboardButton(
                                KEYBOARD_BUTTON_VOLUME_ADD,
                                callback_data=json.dumps(
                                    {"type": "volume", "value": 10}
                                ),
                            ),
                        ],
                    ]
                ),
            )
        except Exception:
            logger.error("Unable to perform volume command.", exc_info=True)
            await self._exception_notify(update)

    async def on_skip_command(
        self, update: Update, context: CallbackContext.DEFAULT_TYPE
    ):
        try:
            if self._skip_cb is None:
                await self._error_notify(update, f"{self._skip_cb=}")

            message = await self._reply(update, MESSAGE_SKIPPING)
            if await self._skip_cb():
                await message.edit_text(
                    MESSAGE_SKIP_SUCCESS,
                    parse_mode=ParseMode.MARKDOWN,
                )
            else:
                await message.edit_text(
                    MESSAGE_SKIP_FAIL,
                    parse_mode=ParseMode.MARKDOWN,
                )

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

            await self._reply(
                update,
                MESSAGE_LIST_PLAYLIST.format(
                    await self._player_status_fmt(),
                    len(medias),
                    "\n".join([f" - `{await media.media_title}`" for media in medias]),
                ),
            )
        except Exception:
            logger.error("Unable to perform info/playlist command.", exc_info=True)
            await self._exception_notify(update)

    async def _player_status_fmt(self):
        state = self._current_player_state_cb()
        if state == PlayerState.Playing:
            return MESSAGE_PLAYER_PLAYING.format(
                await self._current_media_cb().media_title,
                self._seconds_to_time(self._get_cursor_cb()),
                self._seconds_to_time(self._get_length_cb()),
            )
        elif state == PlayerState.Paused:
            return MESSAGE_PLAYER_PAUSED.format(
                await self._current_media_cb().media_title,
                self._seconds_to_time(self._get_cursor_cb()),
                self._seconds_to_time(self._get_length_cb()),
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

            # If no url specified - trying to control player
            if not context.args:
                state = self._current_player_state_cb()
                if state == PlayerState.Paused:
                    await self._resume_cb()
                    await self._reply(update, MESSAGE_RESUME_SUCCESS)
                elif state == PlayerState.Playing:
                    await self._pause_cb()
                    await self._reply(update, MESSAGE_PAUSE_SUCCESS)
                elif state == PlayerState.Stopped:
                    await self._reply(update, MESSAGE_UNABLE_TO_PLAY_EMPTY)
                return

            await self._add_medias(update, context.args)

        except Exception:
            logger.error("Unable to perform play command.", exc_info=True)
            await self._exception_notify(update)

    async def _add_medias(self, update: Update, uris: tp.List[str]):
        # Notifying people, that we are trying our best
        status_message = await self._reply(
            update,
            MESSAGE_MEDIA_ADDING.format("\n".join(f"- `{url}`" for url in uris)),
        )

        # Saving request to database.
        play_message_id = await self._database.add_play_message(uris)

        # Trying to fetch medias from playlist
        medias: tp.List[tp.Tuple[str, Media]] = []
        for url in uris:
            new_medias = await self._add_to_playlist_cb(url)
            medias += [(url, media) for media in new_medias]

        # Notifying people, that we was successfull about it.
        await status_message.edit_text(
            MESSAGE_REPLY_TEMPLATE.format(
                escape_markdown(update.message.from_user.name),
                MESSAGE_MEDIA_ADDED.format(
                    len(medias),
                    "\n".join(
                        [
                            f"- [{await media.media_title}]({url})"
                            for url, media in medias
                        ]
                    ),
                ),
            ),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            KEYBOARD_BUTTON_REPEAT,
                            callback_data=json.dumps(
                                {
                                    "type": "replay",
                                    "play_message_id": play_message_id,
                                }
                            ),
                        )
                    ],
                ]
            ),
        )

    async def _exception_notify(self, update: Update):
        if self._debug_mode:
            await self._application.bot.send_message(
                chat_id=update.effective_chat.id,
                text=MESSAGE_BIG_INTERNAL_ERROR.format(traceback.format_exc()),
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
            await self._reply(update, MESSAGE_SMALL_INTERNAL_ERROR)

    async def _notify(self, text):
        for chat_id in self._application.chat_data:
            try:
                await self._application.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN,
                )
            except Exception:
                logger.error("Unable to notify %s chat", str(chat_id))

    async def _reply(self, update: Update, txt: str, reply_markup=None):
        chat_id = update.effective_chat.id
        from_user = update.message.from_user
        await update.message.delete()
        return await self._application.bot.send_message(
            chat_id=chat_id,
            text=MESSAGE_REPLY_TEMPLATE.format(escape_markdown(from_user.name), txt),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup,
        )

    async def _reply_cb(self, query: CallbackQuery, txt: str):
        return await query.message.reply_text(
            text=txt,
            parse_mode=ParseMode.MARKDOWN,
        )

    async def _callback_handler(
        self,
        update: Update,
        context: CallbackContext.DEFAULT_TYPE,
    ):
        processors = {
            "replay": self._callback_replay,
            "volume": self._callback_volume,
        }

        try:
            query = update.callback_query

            await query.answer()

            data = json.loads(query.data)

            await processors[data["type"]](update, query, data)
        except Exception:
            logger.error("Unable to perform callback.", exc_info=True)
            await self._exception_notify(update)

    async def _callback_volume(
        self,
        update: Update,
        query: CallbackQuery,
        data: tp.Any,
    ):
        value = data["value"]

        old_volume = self._get_volume_cb()
        new_volume = sorted((0, old_volume + value, 100))[1]
        self._set_volume_cb(new_volume)

        # We do not want to receive exception,
        # that message was not changed.
        if old_volume == new_volume:
            return

        current_volume = self._get_volume_cb()

        await query.message.edit_text(
            text=MESSAGE_REPLY_TEMPLATE.format(
                escape_markdown(query.from_user.name),
                MESSAGE_VOLUME_STATUS.format(current_volume),
            ),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            KEYBOARD_BUTTON_VOLUME_SUB,
                            callback_data=json.dumps({"type": "volume", "value": -10}),
                        ),
                        InlineKeyboardButton(
                            KEYBOARD_BUTTON_VOLUME_ADD,
                            callback_data=json.dumps({"type": "volume", "value": 10}),
                        ),
                    ],
                ]
            ),
        )

    async def _callback_replay(
        self,
        update: Update,
        query: CallbackQuery,
        data: tp.Any,
    ):
        message_id = data["play_message_id"]
        uris = await self._database.fetch_uris_from_play_message(message_id)

        if not uris:
            await self._reply_cb(query, MESSAGE_MEDIA_READDING_FAIL)
            return

        # Notifying people, that we are trying our best
        status_message = await self._reply_cb(
            query,
            MESSAGE_MEDIA_READDING.format("\n".join(f"- `{url}`" for url in uris)),
        )

        # Trying to fetch medias from playlist
        medias: tp.List[tp.Tuple[str, Media]] = []
        for url in uris:
            new_medias = await self._add_to_playlist_cb(url)
            medias += [(url, media) for media in new_medias]

        # Notifying people, that we was successfull about it.
        await status_message.edit_text(
            MESSAGE_REPLY_TEMPLATE.format(
                escape_markdown(query.from_user.name),
                MESSAGE_MEDIA_READDED.format(
                    len(medias),
                    "\n".join(
                        [
                            f"- [{await media.media_title}]({url})"
                            for url, media in medias
                        ]
                    ),
                ),
            ),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            KEYBOARD_BUTTON_REPEAT,
                            callback_data=json.dumps(
                                {
                                    "type": "replay",
                                    "play_message_id": message_id,
                                }
                            ),
                        )
                    ],
                ]
            ),
        )

    @staticmethod
    def _time_to_seconds(time: str) -> int:
        try:
            multipliers = [1, 60, 60 * 60, 60 * 60 * 24]
            components = reversed(time.split(":"))

            summ = 0
            multiplier_index = 0

            for component in components:
                component_int = int(component)
                summ += multipliers[multiplier_index] * component_int
                multiplier_index += 1
            return summ
        except (ValueError, IndexError):
            raise ValueError(f'"{time}" is not a time')

    @staticmethod
    def _seconds_to_time(seconds: int) -> str:
        hours_total = seconds // 60 // 60
        minutes_total = seconds // 60
        seconds_total = seconds

        hours = hours_total
        minutes = minutes_total - hours * 60
        seconds = seconds_total - minutes_total * 60

        if hours == 0:
            return f"{minutes:02}:{seconds:02}"
        return f"{hours}:{minutes:02}:{seconds:02}"

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

    @property
    def get_volume_cb(self) -> tp.Optional[GetVolumeCallback]:
        return self._get_volume_cb

    @get_volume_cb.setter
    def get_volume_cb(self, v: GetVolumeCallback):
        self._get_volume_cb = v

    @property
    def set_volume_cb(self) -> tp.Optional[SetVolumeCallback]:
        return self._set_volume_cb

    @set_volume_cb.setter
    def set_volume_cb(self, v: SetVolumeCallback):
        self._set_volume_cb = v

    @property
    def set_cursor_cb(self) -> tp.Optional[SetCursorCallback]:
        return self._set_cursor_cb

    @set_cursor_cb.setter
    def set_cursor_cb(self, v):
        self._set_cursor_cb = v

    @property
    def get_cursor_cb(self) -> tp.Optional[GetCursorCallback]:
        return self._get_cursor_cb

    @get_cursor_cb.setter
    def get_cursor_cb(self, v):
        self._get_cursor_cb = v

    @property
    def get_length_cb(self) -> tp.Optional[GetLengthCallback]:
        return self._get_length_cb

    @get_length_cb.setter
    def get_length_cb(self, v):
        self._get_length_cb = v

    @property
    def get_seek_cb(self) -> tp.Optional[GetSeekCallback]:
        return self._get_seek_cb

    @get_seek_cb.setter
    def get_seek_cb(self, v: GetSeekCallback):
        self._get_seek_cb = v

    @property
    def set_seek_cb(self) -> tp.Optional[SetSeekCallback]:
        return self._set_seek_cb

    @set_seek_cb.setter
    def set_seek_cb(self, v: SetSeekCallback):
        self._set_seek_cb = v
