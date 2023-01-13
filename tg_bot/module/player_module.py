import logging
import asyncio
import typing as tp

from tg_bot.module.keyboard_callback_module import KeyboardCallbackModule
from tg_bot.module.basic_utility_module import BasicUtilityModule
from tg_bot.utils import time_to_seconds, seconds_to_time, shorten_to_message
from multimedia.player import PlayerState
from multimedia.media import Media

from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from telegram.ext import CommandHandler, CallbackContext
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

logger = logging.getLogger(__name__)

KEYBOARD_BUTTON_REPEAT = "Повторить"

MESSAGE_VOLUME_STATUS = "Текущая громкость: `{}/100`"


MESSAGE_PLAYER_PLAYING = "Сейчас играет:\n`{}`\n`{}/{}`"
MESSAGE_PLAYER_PAUSED = "Сейчас пауза:\n`{}`\n`{}/{}`"
MESSAGE_PLAYER_STOPPED = "Сейчас ничего не играет\\."

MESSAGE_MEDIA_ADDED = "🎶 Добавили {} шт\\.:\n{}"
MESSAGE_MEDIA_READDED = "🎶 Передобавили {} шт\\.:\n{}"
MESSAGE_MEDIA_ADDING = "🤔 Добавляю:\n{}"
MESSAGE_MEDIA_READDING = "🤔 Передобавляю:\n{}"
MESSAGE_MEDIA_READDING_FAIL = (
    "😔 Похоже, что это сообщение не может быть передобавлено\\."
)


MESSAGE_SKIPPING = "🤔 Пытаемся пропустить..."
MESSAGE_SKIP_SUCCESS = "💩 Трек был пропущен."
MESSAGE_SKIP_FAIL = "🤔 Нечего пропускать."

MESSAGE_PLAYER_SEEK_STATUS = "Текущая позиция: `{}/{}`"

MESSAGE_PAUSE_SUCCESS = "⏸️ Музыка успешно поставлена на паузу"
MESSAGE_RESUME_SUCCESS = "▶️ Музыка успешно продолжена"
MESSAGE_UNABLE_TO_PLAY_EMPTY = (
    "⚠️ Невозможно поставить на паузу или продолжить\\. Плеер ничего не играет\\."
)

CB_REPLAY_NAME = "replay"


class PlayerModule(BasicUtilityModule):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._kb_module: KeyboardCallbackModule = None

    def _initialize(self):
        self._kb_module = self.find_module(KeyboardCallbackModule)

        self.application.add_handler(CommandHandler("p", self.__on_play_command))
        self.application.add_handler(CommandHandler("skip", self.__on_skip_command))
        self.application.add_handler(CommandHandler("seek", self.__on_seek_command))
        self.application.add_handler(CommandHandler("volume", self.__on_volume_command))

        self._kb_module.register_processor(CB_REPLAY_NAME, self.__on_replay_callback)

    async def __on_play_command(
        self,
        update: Update,
        context: CallbackContext.DEFAULT_TYPE,
    ):
        try:
            # If no url specified - trying to control player
            if not context.args:
                state = self.callbacks.current_player_state()
                if state == PlayerState.Paused:
                    await self.callbacks.resume()
                    await self._reply(update, MESSAGE_RESUME_SUCCESS)
                elif state == PlayerState.Playing:
                    await self.callbacks.pause()
                    await self._reply(update, MESSAGE_PAUSE_SUCCESS)
                elif state == PlayerState.Stopped:
                    await self._reply(update, MESSAGE_UNABLE_TO_PLAY_EMPTY)
                return

            asyncio.create_task(self.add_medias(update, context.args))

        except Exception:
            logger.error("Unable to perform play command.", exc_info=True)
            await self._exception_notify(update)

    async def __on_seek_command(
        self,
        update: Update,
        context: CallbackContext.DEFAULT_TYPE,
    ):
        try:
            if context.args:
                seek_change = context.args[0]
                if not seek_change:
                    await self._error_notify(update, f"{seek_change=}")
                    return

                # If seek is relatively changed
                try:
                    if seek_change[0] in {"-", "+"}:
                        seek_change_int = time_to_seconds(seek_change[1:])
                        new_seek = self.callbacks.get_seek()
                        if seek_change[0] == "-":
                            new_seek -= seek_change_int
                        else:
                            new_seek += seek_change_int
                    else:
                        new_seek = time_to_seconds(seek_change)

                    new_seek = sorted((0, new_seek, self.callbacks.get_length()))[1]
                    self._set_cursor_cb(new_seek)

                except ValueError:
                    await self._error_notify(update, f"{seek_change=}")
                    return

            seek = self.callbacks.get_cursor()
            length = self.callbacks.get_length()
            await self._reply(
                update,
                MESSAGE_PLAYER_SEEK_STATUS.format(
                    seconds_to_time(seek),
                    seconds_to_time(length),
                ),
            )

        except Exception:
            logger.error("Unable to perform seek command.", exc_info=True)
            await self._exception_notify(update)

    async def __on_skip_command(
        self, update: Update, context: CallbackContext.DEFAULT_TYPE
    ):
        try:
            message = await self._reply(update, escape_markdown(MESSAGE_SKIPPING, 2))
            if await self.callbacks.skip():
                await message.edit_text(
                    escape_markdown(MESSAGE_SKIP_SUCCESS, 2),
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
            else:
                await message.edit_text(
                    escape_markdown(MESSAGE_SKIP_FAIL, 2),
                    parse_mode=ParseMode.MARKDOWN_V2,
                )

        except Exception:
            logger.error("Unable to perform skip command.", exc_info=True)
            await self._exception_notify(update)

    async def __on_replay_callback(
        self,
        update: Update,
        query: CallbackQuery,
        data: tp.Any,
    ):
        message_id = data["play_message_id"]
        uris = await self.database.fetch_uris_from_play_message(message_id)

        if not uris:
            await self._reply_cb(query, MESSAGE_MEDIA_READDING_FAIL)
            return

        # Notifying people, that we are trying our best
        status_message = await self._reply_cb(
            query,
            MESSAGE_MEDIA_READDING.format(
                "\n".join(f"\\- `{escape_markdown(url, 2)}`" for url in uris)
            ),
        )

        # Trying to fetch medias from playlist
        medias: tp.List[tp.Tuple[str, Media]] = []
        url_to_medias = {}
        for url in uris:
            new_medias = await self._add_to_playlist_cb(url)
            medias += [(url, media) for media in new_medias]
            await status_message.edit_text(
                self._build_reply_text(
                    query.from_user.name,
                    MESSAGE_MEDIA_READDED.format(
                        len(medias),
                        "\n".join(
                            [
                                f"\\- [{escape_markdown(shorten_to_message(await media.media_title), 2)}]({escape_markdown(url, 2)})"
                                for url in uris
                                if url in url_to_medias
                                for media in url_to_medias[url]
                            ]
                            + [
                                f"\\- `{escape_markdown(url, 2)}`"
                                for url in uris
                                if url not in url_to_medias
                            ]
                        ),
                    ),
                ),
                parse_mode=ParseMode.MARKDOWN_V2,
            )

        # Notifying people, that we was successfull about it.
        await status_message.edit_text(
            self._build_reply_text(
                query.from_user.name,
                MESSAGE_MEDIA_READDED.format(
                    len(medias),
                    "\n".join(
                        [
                            f"\\- [{escape_markdown(shorten_to_message(await media.media_title), 2)}]({escape_markdown(url)})"
                            for url, media in medias
                        ]
                    ),
                ),
            ),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            KEYBOARD_BUTTON_REPEAT,
                            callback_data=self._kb_module.build_data(
                                CB_REPLAY_NAME, {"play_message_id": message_id}
                            ),
                        )
                    ],
                ]
            ),
        )

    async def __on_volume_command(
        self,
        update: Update,
        context: CallbackContext.DEFAULT_TYPE,
    ):
        try:
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
                        new_vol = self.callbacks.get_volume()
                        if volume_change[0] == "-":
                            new_vol -= volume_change_int
                        else:
                            new_vol += volume_change_int
                    else:
                        new_vol = int(volume_change)

                    new_vol = sorted((0, new_vol, 100))[1]
                    self.callbacks.set_volume(new_vol)

                except ValueError:
                    await self._error_notify(update, f"{volume_change=}")
                    return

            # Print current volume
            await self._reply(update, self.volume_fmt())

        except Exception:
            logger.error("Unable to perform volume command.", exc_info=True)
            await self._exception_notify(update)

    def volume_fmt(self):
        return MESSAGE_VOLUME_STATUS.format(self.callbacks.get_volume())

    async def status_fmt(self):
        state = self.callbacks.current_player_state()
        if state == PlayerState.Playing:
            return MESSAGE_PLAYER_PLAYING.format(
                await self.callbacks.current_media().media_title,
                seconds_to_time(self.callbacks.get_cursor()),
                seconds_to_time(self.callbacks.get_length()),
            )
        elif state == PlayerState.Paused:
            return MESSAGE_PLAYER_PAUSED.format(
                await self.callbacks.current_media().media_title,
                seconds_to_time(self.callbacks.get_cursor()),
                seconds_to_time(self.callbacks.get_length()),
            )
        elif state == PlayerState.Stopped:
            return MESSAGE_PLAYER_STOPPED

    async def add_medias(self, update: Update, uris: tp.List[str]):
        # Notifying people, that we are trying our best
        status_message = await self._reply(
            update,
            MESSAGE_MEDIA_ADDING.format(
                "\n".join(f"\\- `{escape_markdown(url, 2)}`" for url in uris)
            ),
        )

        # Saving request to database.
        play_message_id = await self.database.add_play_message(uris)

        # Trying to fetch medias from playlist
        medias: tp.List[tp.Tuple[str, Media]] = []
        url_to_medias = {}
        for url in uris:
            new_medias = await self.callbacks.add_to_playlist(url)

            url_to_medias[url] = new_medias
            medias += [(url, media) for media in new_medias]

            # Notifying people, about process
            await status_message.edit_text(
                self._build_reply_text(
                    update.message.from_user.name,
                    MESSAGE_MEDIA_ADDED.format(
                        len(medias),
                        "\n".join(
                            [
                                f"\\- [{escape_markdown(shorten_to_message(await media.media_title), 2)}]({escape_markdown(url, 2)})"
                                for url in uris
                                if url in url_to_medias
                                for media in url_to_medias[url]
                            ]
                            + [
                                f"\\- `{escape_markdown(url, 2)}`"
                                for url in uris
                                if url not in url_to_medias
                            ]
                        ),
                    ),
                ),
                parse_mode=ParseMode.MARKDOWN_V2,
            )

        # Notifying people, that we was successfull about it.
        await status_message.edit_text(
            self._build_reply_text(
                update.message.from_user.name,
                MESSAGE_MEDIA_ADDED.format(
                    len(medias),
                    "\n".join(
                        [
                            f"\\- [{escape_markdown(shorten_to_message(await media.media_title), 2)}]({escape_markdown(url, 2)})"
                            for url, media in medias
                        ]
                    ),
                ),
            ),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            KEYBOARD_BUTTON_REPEAT,
                            callback_data=self._kb_module.build_data(
                                CB_REPLAY_NAME, {"play_message_id": play_message_id}
                            ),
                        )
                    ],
                ]
            ),
        )
