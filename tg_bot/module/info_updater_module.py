import asyncio
import datetime
import typing as tp
import logging
import json
import pprint

from tg_bot.module.context import ModuleContext
from tg_bot.module.basic_utility_module import BasicUtilityModule
from tg_bot.module.keyboard_callback_module import KeyboardCallbackModule
from tg_bot.module.player_module import PlayerModule
from tg_bot.utils import shorten_to_message, choose_multiplication
from multimedia.player import PlayerState

from telegram import (
    User,
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    CallbackQuery,
)
from telegram.ext import CommandHandler, CallbackContext
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from telegram.error import BadRequest

logger = logging.getLogger(__name__)


MESSAGE_TOO_MANY_TRACKS = "И еще {} {}, которые не влезли"
MESSAGE_TOO_MANY_TRACKS_SINGLE = "трек"
MESSAGE_TOO_MANY_TRACKS_DUAL = "трека"
MESSAGE_TOO_MANY_TRACKS_MULTIPLE = "треков"

MESSAGE_LIST_PLAYLIST = """🎶 {}
{}

Треков в плейлисте {} шт\\.:
{}"""


KEYBOARD_BUTTON_EMPTY = "❌"
KEYBOARD_BUTTON_VOLUME_ADD = "🔈 +10"
KEYBOARD_BUTTON_VOLUME_SUB = "🔊 -10"
KEYBOARD_BUTTON_PAUSE = "⏸️"
KEYBOARD_BUTTON_RESUME = "▶️"
KEYBOARD_BUTTON_SKIP = "⏭️"
KEYBOARD_BUTTON_SKIPALL = "⏏️"
KEYBOARD_BUTTON_SHUFFLE = "🔀"
KEYBOARD_BUTTON_FF = "⏩"
KEYBOARD_BUTTON_FR = "⏪"

CB_PAUSE_NAME = "pause"
CB_RESUME_NAME = "resume"
CB_SKIP_NAME = "skip"
CB_SKIPALL_NAME = "skipall"
CB_SHUFFLE_NAME = "shuffle"
CB_SEEK_NAME = "seek"
CB_VOLUME_NAME = "volume"


class InfoUpdaterModule(BasicUtilityModule):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._info_messages: tp.Dict[tp.Union[int, str], tp.Tuple[Message, User]] = {}
        self._last_update = datetime.datetime.now()

        self._update_interval = datetime.timedelta(seconds=5)
        self._auto_update_task: asyncio.Task = None
        self._kb_module: KeyboardCallbackModule = None
        self._player_module: PlayerModule = None

    def _initialize(self):
        self.application.add_handler(CommandHandler("info", self.__on_info_command))

        self._kb_module = self.find_module(KeyboardCallbackModule)
        self._player_module = self.find_module(PlayerModule)

        self._kb_module.register_processor(CB_SKIP_NAME, self.__callback_skip)
        self._kb_module.register_processor(CB_SKIPALL_NAME, self.__callback_skipall)
        self._kb_module.register_processor(CB_SHUFFLE_NAME, self.__callback_shuffle)
        self._kb_module.register_processor(CB_SEEK_NAME, self.__callback_seek)
        self._kb_module.register_processor(CB_VOLUME_NAME, self.__callback_volume)
        self._kb_module.register_processor(CB_PAUSE_NAME, self.__callback_pause)
        self._kb_module.register_processor(CB_RESUME_NAME, self.__callback_resume)

        self._auto_update_task = asyncio.create_task(self._auto_update_job())

    async def __on_info_command(
        self,
        update: Update,
        context: CallbackContext.DEFAULT_TYPE,
    ):
        try:
            prev_message = self._info_messages.get(update.effective_chat.id)
            if prev_message is not None:
                try:
                    await prev_message.delete()
                except Exception:
                    logger.warning("Unable to delete message", exc_info=True)

            self._info_messages[update.effective_chat.id] = (
                await self._reply(
                    update,
                    await self.build_info_message(),
                    reply_markup=self.generate_info_buttons(),
                ),
                update.message.from_user,
            )
        except Exception:
            logger.error("Unable to perform info/playlist command.", exc_info=True)
            await self._exception_notify(update)

    async def build_info_message(self):
        max_medias_per_info = 16

        medias = self.callbacks.list_playlist()

        titles = "\n".join(
            [
                f"\\- `{escape_markdown(shorten_to_message(str(await media.media_title)), 2)}`"
                for media in medias[:max_medias_per_info]
            ]
        )

        if len(medias) > max_medias_per_info:
            titles += "\n"
            tracks_left = len(medias) - max_medias_per_info
            titles += MESSAGE_TOO_MANY_TRACKS.format(
                tracks_left,
                choose_multiplication(
                    tracks_left,  #
                    word_for_single=MESSAGE_TOO_MANY_TRACKS_SINGLE,  #
                    word_for_dual=MESSAGE_TOO_MANY_TRACKS_DUAL,  #
                    word_for_multiple=MESSAGE_TOO_MANY_TRACKS_MULTIPLE,  #
                ),
            )

        return MESSAGE_LIST_PLAYLIST.format(
            await self._player_module.status_fmt(),
            self._player_module.volume_fmt(),
            len(medias),
            titles,
        )

    async def update_info_messages(self):
        text = await self.build_info_message()

        self._last_update = datetime.datetime.now()
        await asyncio.gather(
            *[
                self._update_info_message(
                    chat_id=chat_id,
                    message=message_user_tuple[0],
                    user_from=message_user_tuple[1],
                    text=text,
                )
                for chat_id, message_user_tuple in self._info_messages.items()
            ]
        )

    def generate_info_buttons(self):
        state = self.callbacks.current_player_state()
        current_media = self.callbacks.current_media()
        medias = self.callbacks.list_playlist()

        none_button = InlineKeyboardButton(
            KEYBOARD_BUTTON_EMPTY,
            callback_data=self._kb_module.build_data(),
        )

        resume_pause_button = None
        if state == PlayerState.Playing:
            resume_pause_button = InlineKeyboardButton(
                KEYBOARD_BUTTON_PAUSE,
                callback_data=self._kb_module.build_data("pause"),
            )
        elif state == PlayerState.Paused:
            resume_pause_button = InlineKeyboardButton(
                KEYBOARD_BUTTON_RESUME,
                callback_data=self._kb_module.build_data("resume"),
            )
        elif state == PlayerState.Stopped:
            resume_pause_button = none_button

        skip_button = none_button
        skipall_button = none_button
        shuffle_button = none_button

        if current_media or medias:
            skip_button = InlineKeyboardButton(
                KEYBOARD_BUTTON_SKIP,
                callback_data=self._kb_module.build_data(CB_SKIP_NAME),
            )

        if medias:
            skipall_button = InlineKeyboardButton(
                KEYBOARD_BUTTON_SKIPALL,
                callback_data=self._kb_module.build_data(CB_SKIPALL_NAME),
            )

            shuffle_button = InlineKeyboardButton(
                KEYBOARD_BUTTON_SHUFFLE,
                callback_data=self._kb_module.build_data(CB_SHUFFLE_NAME),
            )

        fr_button = InlineKeyboardButton(
            KEYBOARD_BUTTON_FR,
            callback_data=self._kb_module.build_data(CB_SEEK_NAME, {"seconds": -10}),
        )

        ff_button = InlineKeyboardButton(
            KEYBOARD_BUTTON_FF,
            callback_data=self._kb_module.build_data(CB_SEEK_NAME, {"seconds": +10}),
        )

        volume_up_button = InlineKeyboardButton(
            KEYBOARD_BUTTON_VOLUME_ADD,
            callback_data=self._kb_module.build_data(CB_VOLUME_NAME, {"value": 10}),
        )

        volume_down_button = InlineKeyboardButton(
            KEYBOARD_BUTTON_VOLUME_SUB,
            callback_data=self._kb_module.build_data(CB_VOLUME_NAME, {"value": -10}),
        )

        return InlineKeyboardMarkup(
            [
                [
                    resume_pause_button,
                    skipall_button,
                    shuffle_button,
                    skip_button,
                    fr_button,
                    ff_button,
                ],
                [
                    volume_down_button,
                    volume_up_button,
                ],
            ]
        )

    async def _update_info_message(
        self,
        chat_id: tp.Union[str, int],
        message: Message,
        user_from: User,
        text: str,
    ):
        real_text = self._build_reply_text(user_from.name, text)

        buttons = self.generate_info_buttons()

        if all(
            (
                message.reply_markup == buttons,
                message.text_markdown_v2.strip() == real_text.strip(),
            )
        ):
            return

        try:
            self._info_messages[chat_id] = (
                await self.application.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message.message_id,
                    text=real_text,
                    reply_markup=buttons,
                    parse_mode=ParseMode.MARKDOWN_V2,
                ),
                user_from,
            )
        except BadRequest as e:
            logger.warning("Trying to set the same text probably: %s", str(e))

            logger.debug("Setting Text:\n%s", str(real_text.strip()))
            logger.debug("Set Text:\n%s", str(message.text_markdown_v2.strip()))

            logger.debug("Setting Markup:\n%s", str(pprint.pformat(buttons)))
            logger.debug("Set Markup:\n%s", str(pprint.pformat(message.reply_markup)))
        except Exception:
            logger.error("Exception acquired:", exc_info=True)

    async def _auto_update_job(self):
        while True:
            try:
                execution_amount = datetime.datetime.now() - self._last_update
                sleep_amount = 0
                if execution_amount < self._update_interval:
                    sleep_amount = (
                        self._update_interval - execution_amount
                    ).seconds + 1

                logger.info(
                    "Waiting until next info update for %d seconds", sleep_amount
                )
                await asyncio.sleep(sleep_amount)

                if datetime.datetime.now() < (
                    self._last_update + self._update_interval
                ):
                    logger.info("Trying to autoupdate too early, waiting again.")
                    continue

                await self.update_info_messages()
            except Exception:
                logger.error(
                    "Uncatched auto-update exception (see below). Waiting %d seconds before retrying",
                    self._update_interval.seconds,
                    exc_info=True,
                )
                await asyncio.sleep(self._update_interval.seconds)

    async def __callback_skip(
        self,
        update: Update,
        query: CallbackQuery,
        data: tp.Any,
    ):
        await self.callbacks.skip()
        await self.update_info_messages()

    async def __callback_skipall(
        self,
        update: Update,
        query: CallbackQuery,
        data: tp.Any,
    ):
        await self.callbacks.skipall()
        await self.update_info_messages()

    async def __callback_shuffle(
        self,
        update: Update,
        query: CallbackQuery,
        data: tp.Any,
    ):
        await self.callbacks.shuffle()
        await self.update_info_messages()

    async def __callback_seek(
        self,
        update: Update,
        query: CallbackQuery,
        data: tp.Any,
    ):
        value = data["seconds"]

        current_cursor = self.callbacks.get_cursor()
        current_cursor += value
        current_cursor = sorted((0, current_cursor, self.callbacks.get_length()))[1]
        self.callbacks.set_cursor(current_cursor)

        await self.update_info_messages()

    async def __callback_volume(
        self,
        update: Update,
        query: CallbackQuery,
        data: tp.Any,
    ):
        value = data["value"]

        old_volume = self.callbacks.get_volume()

        new_volume = sorted((0, old_volume + value, 100))[1]

        self.callbacks.set_volume(new_volume)
        await self.update_info_messages()

    async def __callback_pause(
        self,
        update: Update,
        query: CallbackQuery,
        data: tp.Any,
    ):
        await self.callbacks.pause()
        await self.update_info_messages()

    async def __callback_resume(
        self,
        update: Update,
        query: CallbackQuery,
        data: tp.Any,
    ):
        await self.callbacks.resume()
        await self.update_info_messages()
