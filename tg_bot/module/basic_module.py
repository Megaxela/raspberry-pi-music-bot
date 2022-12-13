import abc
import typing as tp

from tg_bot.module.context import ModuleContext
from tg_bot.callbacks import Callbacks
from database import Database

from telegram.ext import Application


class BasicModule(abc.ABC):
    def __init__(self, context: ModuleContext):
        self._ctx: ModuleContext = context

    @abc.abstractmethod
    def _initialize(self):
        pass

    def find_module(self, cls: type) -> tp.Optional[tp.Any]:
        return self._ctx.container.find_module(cls)

    @property
    def application(self) -> Application:
        return self._ctx.bot

    @property
    def callbacks(self) -> Callbacks:
        return self._ctx.callbacks

    @property
    def database(self) -> Database:
        return self._ctx.database

    @property
    def is_debug(self) -> bool:
        return True
