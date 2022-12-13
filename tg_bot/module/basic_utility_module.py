import traceback

from tg_bot.module.basic_module import BasicModule

from telegram import Update, CallbackQuery
from telegram.helpers import escape_markdown
from telegram.constants import ParseMode


MESSAGE_SMALL_INTERNAL_ERROR = "😔 Что-то случилось и я теперь не могу работать\\."
MESSAGE_BIG_INTERNAL_ERROR = "😡🔧 Кое что случилось\\. Ошибку смотри ниже:\n```\n{}\n```"
MESSAGE_REPLY_TEMPLATE = "⚙️ {}: {}"


class BasicUtilityModule(BasicModule):
    async def _exception_notify(self, update: Update):
        if self.is_debug:
            await self.application.bot.send_message(
                chat_id=update.effective_chat.id,
                text=MESSAGE_BIG_INTERNAL_ERROR.format(
                    escape_markdown(traceback.format_exc(), 2)
                ),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        else:
            await update.message.reply_text(MESSAGE_SMALL_INTERNAL_ERROR)

    def _build_reply_text(self, author: str, text: str):
        return MESSAGE_REPLY_TEMPLATE.format(
            escape_markdown(author, 2),
            text,
        )

    async def _reply(self, update: Update, txt: str, reply_markup=None):
        chat_id = update.effective_chat.id
        from_user = update.message.from_user
        await update.message.delete()
        return await self.application.bot.send_message(
            chat_id=chat_id,
            text=self._build_reply_text(from_user.name, txt),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=reply_markup,
        )

    async def _reply_cb(self, query: CallbackQuery, txt: str):
        return await query.message.reply_text(
            text=txt,
            parse_mode=ParseMode.MARKDOWN_V2,
        )

    async def _error_notify(self, update: Update, message: str):
        if self._debug_mode:
            await update.message.reply_text(
                MESSAGE_BIG_INTERNAL_ERROR.format(message),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        else:
            await self._reply(update, MESSAGE_SMALL_INTERNAL_ERROR)
