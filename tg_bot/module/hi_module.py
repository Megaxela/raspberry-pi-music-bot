import logging

from tg_bot.module.basic_utility_module import BasicUtilityModule

from telegram.ext import MessageHandler, filters, CallbackContext
from telegram import (
    Update,
)

logger = logging.getLogger(__name__)


class HiModule(BasicUtilityModule):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _initialize(self):
        self.application.add_handler(
            MessageHandler(
                filters.Regex(r"^((\\o|o\/|\\o\/) *)+$"),
                self.__on_hi,
            )
        )
        self.application.add_handler(
            MessageHandler(
                filters.Regex(r"^(☀️|🌤|🌥|⛅️|🌦|🌞|🌅)$"),
                self.__on_emoji_hi,
            )
        )

    async def __on_hi(
        self,
        update: Update,
        context: CallbackContext.DEFAULT_TYPE,
    ):
        try:
            # Do not use self._reply here, cause it may delete initial message.
            await update.message.reply_text(update.message.text)
        except Exception:
            logger.error("Unable to say hi.", exc_info=True)
            await self._exception_notify(update)

    async def __on_emoji_hi(
        self,
        update: Update,
        context: CallbackContext.DEFAULT_TYPE,
    ):
        try:
            # Do not use self._reply here, cause it may delete initial message.
            await update.message.reply_text("🤚")
        except Exception:
            logger.error("Unable to say hi.", exc_info=True)
            await self._exception_notify(update)
