import logging

from tg_bot.module.basic_utility_module import BasicUtilityModule

from telegram.ext import CommandHandler, filters, CallbackContext
from telegram import Update
import netifaces

logger = logging.getLogger(__name__)

MESSAGE_WHEREAMI = """🤔 Хде я? А вот хде я:
```
{}
```"""


class WhereAmIModule(BasicUtilityModule):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _initialize(self):
        self.application.add_handler(
            CommandHandler("whereami", self.__on_whereami_command)
        )

    async def __on_whereami_command(
        self,
        update: Update,
        context: CallbackContext.DEFAULT_TYPE,
    ):
        blacklist_ifaces = {"lo"}
        try:
            addresses = list(
                filter(
                    lambda x: x is not None
                    and len(x[1]) > 0
                    and x[0] not in blacklist_ifaces,
                    map(
                        lambda x: (
                            x,
                            list(
                                filter(
                                    lambda x: "addr" in x,
                                    netifaces.ifaddresses(x).get(netifaces.AF_INET, []),
                                )
                            ),
                        ),
                        netifaces.interfaces(),
                    ),
                )
            )

            max_iface_len = len(max(*addresses, key=lambda x: len(x[0]))[0])

            await self._reply(
                update,
                MESSAGE_WHEREAMI.format(
                    "\n\n".join(
                        (
                            f"{{:<{max_iface_len}}} - {{}}".format(
                                iface,
                                "\n".join(
                                    [
                                        f"{{:<{max_iface_len + 3}}}".format(a["addr"])
                                        for a in addr
                                    ]
                                ),
                            )
                            for iface, addr in addresses
                        )
                    )
                ),
            )
        except Exception:
            logger.error("Unable to see where am I.", exc_info=True)
            await self._exception_notify(update)
