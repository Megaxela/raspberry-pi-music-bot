import logging

from tg_bot.callbacks import Callbacks
from tg_bot.module.context import ModuleContext
from tg_bot.module.container import ModuleContainer
from tg_bot.module.hi_module import HiModule
from tg_bot.module.info_updater_module import InfoUpdaterModule
from tg_bot.module.keyboard_callback_module import KeyboardCallbackModule
from tg_bot.module.whereami_module import WhereAmIModule
from tg_bot.module.player_module import PlayerModule
from multimedia.media import Media
from database import Database
from telegram.constants import ParseMode

from telegram._utils.defaultvalue import DEFAULT_NONE
from telegram.ext import Application


MESSAGE_NOTIFY_AUTOPLAY = "🔔 Сейчас будет играть: `{}`"


logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self, token: str, database: Database):
        self._debug_mode = True

        self._database: Database = database

        self._cb: Callbacks = Callbacks()

        self._application = Application.builder().token(token).build()

        self._modules = ModuleContainer()

        module_ctx = ModuleContext(
            container=self._modules,
            bot=self._application,
            callbacks=self._cb,
            database=self._database,
        )

        self._modules.add_module(HiModule(module_ctx))
        self._modules.add_module(InfoUpdaterModule(module_ctx))
        self._modules.add_module(KeyboardCallbackModule(module_ctx))
        self._modules.add_module(WhereAmIModule(module_ctx))
        self._modules.add_module(PlayerModule(module_ctx))

    @property
    def callbacks(self) -> Callbacks:
        return self._cb

    async def run(self):
        # Initialize modules
        self._modules.initialize()

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

    async def _notify(self, text):
        for chat_id in self._application.chat_data:
            try:
                await self._application.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
            except Exception:
                logger.error("Unable to notify %s chat", str(chat_id))
