from math import ceil
from typing import List, Dict

from telegram import MAX_MESSAGE_LENGTH, InlineKeyboardButton, Bot, ParseMode
from telegram.error import TelegramError

from haruka import LOAD, NO_LOAD
from haruka.modules.translations.strings import tld
from telegram.ext import CommandHandler, Filters, MessageHandler, CallbackQueryHandler


class EqInlineKeyboardButton(InlineKeyboardButton):
    def __eq__(self, other):
        return self.text == other.text

    def __lt__(self, other):
        return self.text < other.text

    def __gt__(self, other):
        return self.text > other.text


def split_message(msg: str) -> List[str]:
    if len(msg) < MAX_MESSAGE_LENGTH:
        return [msg]

    else:
        lines = msg.splitlines(True)
        small_msg = ""
        result = []
        for line in lines:
            if len(small_msg) + len(line) < MAX_MESSAGE_LENGTH:
                small_msg += line
            else:
                result.append(small_msg)
                small_msg = line
        else:
            # Else statement at the end of the for loop, so append the leftover string.
            result.append(small_msg)

        return result


def paginate_modules(chat_id,
                     page_n: int,
                     module_dict: Dict,
                     prefix,
                     chat=None) -> List:
    if not chat:
        modules = sorted([
            EqInlineKeyboardButton(tld(chat_id, "modname_" + x),
                                   callback_data="{}_module({})".format(
                                       prefix, x)) for x in module_dict.keys()
        ])
    else:
        modules = sorted([
            EqInlineKeyboardButton(tld(chat_id, "modname_" + x),
                                   callback_data="{}_module({},{})".format(
                                       prefix, chat, x))
            for x in module_dict.keys()
        ])

    pairs = list(zip(modules[::2], modules[1::2]))

    if len(modules) % 2 == 1:
        pairs.append((modules[-1], ))

    max_num_pages = ceil(len(pairs) / 7)
    modulo_page = page_n % max_num_pages

    # can only have a certain amount of buttons side by side
    if len(pairs) > 7:
        pairs = pairs[modulo_page * 7:7 * (modulo_page + 1)] + [
            (EqInlineKeyboardButton(
                "<<", callback_data="{}_prev({})".format(prefix, modulo_page)),
             EqInlineKeyboardButton(tld(chat_id, 'btn_go_back'), callback_data="bot_start"),
             EqInlineKeyboardButton(">>",
                                    callback_data="{}_next({})".format(
                                        prefix, modulo_page)))
        ]
    else:
        pairs += [[
            EqInlineKeyboardButton(tld(chat_id, 'btn_go_back'), callback_data="bot_start")
        ]]

    return pairs


def send_to_list(bot: Bot,
                 send_to: list,
                 message: str,
                 markdown=False,
                 html=False) -> None:
    if html and markdown:
        raise Exception("Can only send with either markdown or HTML!")
    for user_id in set(send_to):
        try:
            if markdown:
                bot.send_message(user_id,
                                 message,
                                 parse_mode=ParseMode.MARKDOWN)
            elif html:
                bot.send_message(user_id, message, parse_mode=ParseMode.HTML)
            else:
                bot.send_message(user_id, message)
        except TelegramError:
            pass  # ignore users who fail


def build_keyboard(buttons):
    keyb = []
    for btn in buttons:
        if btn.same_line and keyb:
            keyb[-1].append(InlineKeyboardButton(btn.name, url=btn.url))
        else:
            keyb.append([InlineKeyboardButton(btn.name, url=btn.url)])

    return keyb


def revert_buttons(buttons):
    res = ""
    for btn in buttons:
        if btn.same_line:
            res += "\n[{}](buttonurl://{}:same)".format(btn.name, btn.url)
        else:
            res += "\n[{}](buttonurl://{})".format(btn.name, btn.url)

    return res


def is_module_loaded(name):
    return (not LOAD or name in LOAD) and name not in NO_LOAD


def user_bot_owner(func):
    @wraps(func)
    def is_user_bot_owner(bot: Bot, update: Update, *args, **kwargs):
        user = update.effective_user
        if user and user.id == OWNER_ID:
            return func(bot, update, *args, **kwargs)
        else:
            pass

    return is_user_bot_owner
