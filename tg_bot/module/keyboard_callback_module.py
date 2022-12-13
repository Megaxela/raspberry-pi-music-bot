import logging
import json
import asyncio

from tg_bot.module.basic_utility_module import BasicUtilityModule

from telegram import Update
from telegram.ext import CallbackQueryHandler, CallbackContext


logger = logging.getLogger(__name__)


class KeyboardCallbackModule(BasicUtilityModule):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._processors = {}

    def register_processor(self, name: str, callback):
        self._processors[name] = callback

    def build_data(self, name: str = "none", extra_data=None):
        result = {"type": name}

        if extra_data is not None:
            result.update(extra_data)

        return json.dumps(result)

    def _initialize(self):
        self.application.add_handler(CallbackQueryHandler(self.__handler))

    async def __handler(
        self,
        update: Update,
        context: CallbackContext.DEFAULT_TYPE,
    ):
        try:
            query = update.callback_query
            await query.answer()

            data = json.loads(query.data)

            processor_name = data["type"]
            processor = self._processors.get(processor_name)
            if processor is None:
                raise ValueError(
                    f"No processor for keyboard callback '{processor_name}'"
                )

            asyncio.create_task(processor(update, query, data))
        except Exception:
            logger.error("Unable to perform callback", exc_info=True)
            await self._exception_notify(update)
