import dataclasses

from tg_bot.module.container import ModuleContainer
from tg_bot.callbacks import Callbacks
from database import Database

from telegram.ext import Application


@dataclasses.dataclass()
class ModuleContext:
    container: ModuleContainer
    bot: Application
    callbacks: Callbacks
    database: Database
