import datetime
import importlib
import re
from typing import Optional, List

from telegram import Message, Chat, Update, Bot, User
from telegram import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from telegram.error import Unauthorized, BadRequest, TimedOut, NetworkError, ChatMigrated, TelegramError
from telegram.ext import CommandHandler, Filters, MessageHandler, CallbackQueryHandler
from telegram.ext.dispatcher import run_async, DispatcherHandlerStop, Dispatcher
from telegram.utils.helpers import escape_markdown

from tg_bot import dispatcher, updater, TOKEN, WEBHOOK, SUDO_USERS, OWNER_ID, DONATION_LINK, CERT_PATH, PORT, URL, LOGGER, \
    ALLOW_EXCL
# needed to dynamically load modules
# NOTE: Module order is not guaranteed, specify that in the config file!
from tg_bot.modules import ALL_MODULES
from tg_bot.modules.helper_funcs.chat_status import is_user_admin
from tg_bot.modules.helper_funcs.misc import paginate_modules
from tg_bot.modules.translations.strings import tld, tld_help
from tg_bot.modules.connection import connected

DONATE_STRING = """Heya, glad to hear you want to donate! I do not actually want for myself but it \
It took lots of work for [my creator](t.me/SonOfLars) to get me to where I am now, and every donation helps \
motivate him to make me even better. All the donation money will go to a better VPS to host me, and/or beer \
https://orangefox.tech/donate."""

IMPORTED = {}
MIGRATEABLE = []
HELPABLE = {}
STATS = []
USER_INFO = []
DATA_IMPORT = []
DATA_EXPORT = []

CHAT_SETTINGS = {}
USER_SETTINGS = {}

GDPR = []

for module_name in ALL_MODULES:
    imported_module = importlib.import_module("tg_bot.modules." + module_name)
    if not hasattr(imported_module, "__mod_name__"):
        imported_module.__mod_name__ = imported_module.__name__

    if not imported_module.__mod_name__.lower() in IMPORTED:
        IMPORTED[imported_module.__mod_name__.lower()] = imported_module
    else:
        raise Exception("Can't have two modules with the same name! Please change one")

    if hasattr(imported_module, "__help__") and imported_module.__help__:
        HELPABLE[imported_module.__mod_name__.lower()] = imported_module

    # Chats to migrate on chat_migrated events
    if hasattr(imported_module, "__migrate__"):
        MIGRATEABLE.append(imported_module)

    if hasattr(imported_module, "__stats__"):
        STATS.append(imported_module)

    if hasattr(imported_module, "__gdpr__"):
        GDPR.append(imported_module)

    if hasattr(imported_module, "__user_info__"):
        USER_INFO.append(imported_module)

    if hasattr(imported_module, "__import_data__"):
        DATA_IMPORT.append(imported_module)

    if hasattr(imported_module, "__export_data__"):
        DATA_EXPORT.append(imported_module)

    if hasattr(imported_module, "__chat_settings__"):
        CHAT_SETTINGS[imported_module.__mod_name__.lower()] = imported_module

    if hasattr(imported_module, "__user_settings__"):
        USER_SETTINGS[imported_module.__mod_name__.lower()] = imported_module


# do not async
def send_help(chat_id, text, keyboard=None):
    if not keyboard:
        keyboard = InlineKeyboardMarkup(paginate_modules(chat_id, 0, HELPABLE, "help"))
    dispatcher.bot.send_message(chat_id=chat_id,
                                text=text,
                                parse_mode=ParseMode.MARKDOWN,
                                reply_markup=keyboard)


@run_async
def test(bot: Bot, update: Update):
    # pprint(eval(str(update)))
    # update.effective_message.reply_text("Hola tester! _I_ *have* `markdown`", parse_mode=ParseMode.MARKDOWN)
    update.effective_message.reply_text("This person edited a message")
    print(update.effective_message)


@run_async
def start(bot: Bot, update: Update, args: List[str]):
    print("Start")
    chat = update.effective_chat  # type: Optional[Chat]
    query = update.callback_query
    if update.effective_chat.type == "private":
        if len(args) >= 1:
            if args[0].lower() == "help":
                send_help(update.effective_chat.id, tld(chat.id, "send-help").format(
                     dispatcher.bot.first_name, "" if not ALLOW_EXCL else tld(chat.id, "\nAll commands can either be used with `/` or `!`.\n")))

            elif args[0].lower().startswith("stngs_"):
                match = re.match("stngs_(.*)", args[0].lower())
                chat = dispatcher.bot.getChat(match.group(1))

                if is_user_admin(chat, update.effective_user.id):
                    send_settings(match.group(1), update.effective_user.id, user=False)
                else:
                    send_settings(match.group(1), update.effective_user.id, user=True)

            elif args[0][1:].isdigit() and "rules" in IMPORTED:
                IMPORTED["rules"].send_rules(update, args[0], from_pm=True)

        else:
            send_start(bot, update)
    else:
        update.effective_message.reply_text("Hey there! I'm alive :3")


def send_start(bot, update):
    #Try to remove old message
    try:
        query = update.callback_query
        query.message.delete()
    except:
        pass

    chat = update.effective_chat  # type: Optional[Chat]
    text = "Hey there! My name is Haruka Aya - I'm here to help you manage your groups! Click Help button to find out more about how to use me to my full potential."
    text += "\n \nJoin [Haruka Aya Group](https://t.me/HarukaAyaGroup) ( @HarukaAyaGroup ) if you need any support or help \n \nFollow [Haruka Aya](https://t.me/HarukaAya) ( @HarukaAya ) if you want to keep up with the news, updates and bot downtime! \n \nMy source can be founded [here](https://github.com/peaktogoo/HarukaAya) \n \nMade with love by @peaktogoo \n \nWant to add me to your group? [Click here!](t.me/HarukaAyaBot?startgroup=true)"

    keyboard = [[InlineKeyboardButton(text="🛠 Control panel", callback_data="cntrl_panel_M")]]
    keyboard += [[InlineKeyboardButton(text="🇺🇸 Language", callback_data="set_lang_"), 
        InlineKeyboardButton(text="❔ Help", callback_data="help_back")]]

    update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)



def control_panel(bot, update):
    print("Panel")
    chat = update.effective_chat
    user = update.effective_user

    #Support to run from command handler
    query = update.callback_query
    if query:
        query.message.delete()

        M_match = re.match(r"cntrl_panel_M", query.data)
        U_match = re.match(r"cntrl_panel_U", query.data)
        G_match = re.match(r"cntrl_panel_G", query.data)
        back_match = re.match(r"help_back", query.data)

        print(query.data)
    else:
        M_match = "Haruka Aya is best bot"

    if M_match:
        text = "*Control panel* 🛠 (beta)"

        keyboard = [[InlineKeyboardButton(text="👤 My settings", callback_data="cntrl_panel_U(1)")]]

        #Show connected chat and add chat settings button
        conn = connected(bot, update, chat, user.id, need_admin=False)

        if not conn == False:
            chatG = bot.getChat(conn)
            admin_list = chatG.get_administrators()

            #If user admin
            member = chatG.get_member(user.id)
            if member.status in ('administrator', 'creator'):
                text += "\nConnected chat - *{}* (you {})".format(chatG.title, member.status)
                keyboard += [[InlineKeyboardButton(text="👥 Group settings", callback_data="cntrl_panel_G_back")]]
            elif user.id in SUDO_USERS:
                text += "\nConnected chat - *{}* (you sudo)".format(chatG.title)
                keyboard += [[InlineKeyboardButton(text="👥 Group settings (SUDO)", callback_data="cntrl_panel_G_back")]]
            else:
                text += "\nConnected chat - *{}* (you don't admin!)".format(chatG.title)
        else:
            text += "\nNo chat connected!"

        keyboard += [[InlineKeyboardButton(text="⬅️ Back", callback_data="bot_start")]]

        update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

    elif U_match:

        mod_match = re.match(r"cntrl_panel_U_module\((.+?)\)", query.data)
        back_match = re.match(r"cntrl_panel_U\((.+?)\)", query.data)

        chatP = update.effective_chat  # type: Optional[Chat]
        if mod_match:
            module = mod_match.group(1)

            R = CHAT_SETTINGS[module].__user_settings__(bot, update, user)

            text = "You has the following settings for the *{}* module:\n\n".format(
                CHAT_SETTINGS[module].__mod_name__) + R[0]

            keyboard = R[1]
            keyboard += [[InlineKeyboardButton(text="⬅️ Back", callback_data="cntrl_panel_U(1)")]]
                
            query.message.reply_text(text=text, arse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

        elif back_match:
            text = "*User control panel* 🛠"
            
            query.message.reply_text(text=text, parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(paginate_modules(user.id, 0, USER_SETTINGS, "cntrl_panel_U")))

    elif G_match:
        mod_match = re.match(r"cntrl_panel_G_module\((.+?)\)", query.data)
        prev_match = re.match(r"cntrl_panel_G_prev\((.+?)\)", query.data)
        next_match = re.match(r"cntrl_panel_G_next\((.+?)\)", query.data)
        back_match = re.match(r"cntrl_panel_G_back", query.data)

        chatP = chat
        conn = connected(bot, update, chat, user.id)

        if not conn == False:
            chat = bot.getChat(conn)
        else:
            query.message.reply_text(text="Error with connection to chat")
            exit(1)

        if mod_match:
            module = mod_match.group(1)
            R = CHAT_SETTINGS[module].__chat_settings__(bot, update, chat, chatP, user)

            if type(R) is list:
                text = R[0]
                keyboard = R[1]
            else:
                text = R
                keyboard = []

            text = "*{}* has the following settings for the *{}* module:\n\n".format(
                escape_markdown(chat.title), CHAT_SETTINGS[module].__mod_name__) + text

            keyboard += [[InlineKeyboardButton(text="Back", callback_data="cntrl_panel_G_back")]]
                
            query.message.reply_text(text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

        elif prev_match:
            chat_id = prev_match.group(1)
            curr_page = int(prev_match.group(2))
            chat = bot.get_chat(chat_id)
            query.message.reply_text(tld(user.id, "send-group-settings").format(chat.title),
                                    reply_markup=InlineKeyboardMarkup(
                                        paginate_modules(curr_page - 1, CHAT_SETTINGS, "cntrl_panel_G",
                                                        chat=chat_id)))

        elif next_match:
            chat_id = next_match.group(1)
            next_page = int(next_match.group(2))
            chat = bot.get_chat(chat_id)
            query.message.reply_text(tld(user.id, "send-group-settings").format(chat.title),
                                    reply_markup=InlineKeyboardMarkup(
                                        paginate_modules(next_page + 1, CHAT_SETTINGS, "cntrl_panel_G",
                                                        chat=chat_id)))

        elif back_match:
            text = "Test"
            query.message.reply_text(text=text, parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(paginate_modules(user.id, 0, CHAT_SETTINGS, "cntrl_panel_G")))


# for test purposes
def error_callback(bot, update, error):
    try:
        raise error
    except Unauthorized:
        print("no nono1")
        print(error)
        # remove update.message.chat_id from conversation list
    except BadRequest:
        print("no nono2")
        print("BadRequest caught")
        print(error)

        # handle malformed requests - read more below!
    except TimedOut:
        print("no nono3")
        # handle slow connection problems
    except NetworkError:
        print("no nono4")
        # handle other connection problems
    except ChatMigrated as err:
        print("no nono5")
        print(err)
        # the chat_id of a group has changed, use e.new_chat_id instead
    except TelegramError:
        print(error)
        # handle all other telegram related errors


@run_async
def help_button(bot: Bot, update: Update):
    query = update.callback_query
    chat = update.effective_chat  # type: Optional[Chat]
    mod_match = re.match(r"help_module\((.+?)\)", query.data)
    prev_match = re.match(r"help_prev\((.+?)\)", query.data)
    next_match = re.match(r"help_next\((.+?)\)", query.data)
    back_match = re.match(r"help_back", query.data)
    try:
        if mod_match:
            module = mod_match.group(1)
            mod_name = tld(chat.id, HELPABLE[module].__mod_name__)
            help_txt = tld_help(chat.id, HELPABLE[module].__mod_name__)

            if help_txt == False:
                help_txt = HELPABLE[module].__help__

            text = tld(chat.id, "Here is the help for the *{}* module:\n{}").format(mod_name, help_txt)
            query.message.reply_text(text=text,
                                     parse_mode=ParseMode.MARKDOWN,
                                     reply_markup=InlineKeyboardMarkup(
                                         [[InlineKeyboardButton(text=tld(chat.id, "Back"), callback_data="help_back")]]))

        elif prev_match:
            curr_page = int(prev_match.group(1))
            query.message.reply_text(tld(chat.id, "send-help").format(dispatcher.bot.first_name, "" if not ALLOW_EXCL else tld(chat.id, "\nAll commands can either be used with `/` or `!`.\n")),
                                     parse_mode=ParseMode.MARKDOWN,
                                     reply_markup=InlineKeyboardMarkup(
                                         paginate_modules(chat.id, curr_page - 1, HELPABLE, "help")))

        elif next_match:
            next_page = int(next_match.group(1))
            query.message.reply_text(tld(chat.id, "send-help").format(dispatcher.bot.first_name, "" if not ALLOW_EXCL else tld(chat.id, "\nAll commands can either be used with `/` or `!`.\n")),
                                     parse_mode=ParseMode.MARKDOWN,
                                     reply_markup=InlineKeyboardMarkup(
                                         paginate_modules(chat.id, next_page + 1, HELPABLE, "help")))

        elif back_match:
            query.message.reply_text(text=tld(chat.id, "send-help").format(dispatcher.bot.first_name, "" if not ALLOW_EXCL else tld(chat.id, "\nAll commands can either be used with `/` or `!`.\n")),
                                     parse_mode=ParseMode.MARKDOWN,
                                     reply_markup=InlineKeyboardMarkup(
                                         paginate_modules(chat.id, 0, HELPABLE, "help")))

        # ensure no spinny white circle
        bot.answer_callback_query(query.id)
        query.message.delete()
    except BadRequest as excp:
        if excp.message == "Message is not modified":
            pass
        elif excp.message == "Query_id_invalid":
            pass
        elif excp.message == "Message can't be deleted":
            pass
        else:
            LOGGER.exception("Exception in help buttons. %s", str(query.data))


@run_async
def get_help(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    args = update.effective_message.text.split(None, 1)

    # ONLY send help in PM
    if chat.type != chat.PRIVATE:

        update.effective_message.reply_text("Contact me in PM to get the list of possible commands.",
                                            reply_markup=InlineKeyboardMarkup(
                                                [[InlineKeyboardButton(text="Help",
                                                                       url="t.me/{}?start=help".format(
                                                                           bot.username))]]))
        return

    elif len(args) >= 2 and any(args[1].lower() == x for x in HELPABLE):
        module = args[1].lower()
        mod_name = tld(chat.id, HELPABLE[module].__mod_name__)
        help_txt = tld_help(chat.id, HELPABLE[module].__mod_name__)

        if help_txt == False:
            help_txt = HELPABLE[module].__help__

        text = tld(chat.id, "Here is the help for the *{}* module:\n{}").format(mod_name, help_txt)
        send_help(chat.id, text, InlineKeyboardMarkup([[InlineKeyboardButton(text=tld(chat.id, "Back"), callback_data="help_back")]]))

    else:
        send_help(chat.id, tld(chat.id, "send-help").format(dispatcher.bot.first_name, "" if not ALLOW_EXCL else tld(chat.id, "\nAll commands can either be used with `/` or `!`.\n")))


def send_settings(chat_id, user_id, user=False):
    if user:
        if USER_SETTINGS:
            settings = "\n\n".join(
                "*{}*:\n{}".format(mod.__mod_name__, mod.__user_settings__(user_id)) for mod in USER_SETTINGS.values())
            dispatcher.bot.send_message(user_id, "These are your current settings:" + "\n\n" + settings,
                                        parse_mode=ParseMode.MARKDOWN)

        else:
            dispatcher.bot.send_message(user_id, "Seems like there aren't any user specific settings available :'(",
                                        parse_mode=ParseMode.MARKDOWN)

    else:
        if CHAT_SETTINGS:
            chat_name = dispatcher.bot.getChat(chat_id).title
            dispatcher.bot.send_message(user_id,
                                        text="Which module would you like to check {}'s settings for?".format(
                                            chat_name),
                                        reply_markup=InlineKeyboardMarkup(
                                            paginate_modules(user_id, 0, CHAT_SETTINGS, "stngs", chat=chat_id)))
        else:
            dispatcher.bot.send_message(user_id, "Seems like there aren't any chat settings available :'(\nSend this "
                                                 "in a group chat you're admin in to find its current settings!",
                                        parse_mode=ParseMode.MARKDOWN)


@run_async
def settings_button(bot: Bot, update: Update):
    query = update.callback_query
    user = update.effective_user
    chatP = update.effective_chat  # type: Optional[Chat]
    mod_match = re.match(r"stngs_module\((.+?),(.+?)\)", query.data)
    prev_match = re.match(r"stngs_prev\((.+?),(.+?)\)", query.data)
    next_match = re.match(r"stngs_next\((.+?),(.+?)\)", query.data)
    back_match = re.match(r"stngs_back\((.+?)\)", query.data)
    try:
        if mod_match:
            chat_id = mod_match.group(1)
            module = mod_match.group(2)
            chat = bot.get_chat(chat_id)
            text = "*{}* has the following settings for the *{}* module:\n\n".format(escape_markdown(chat.title),
                                                                                     CHAT_SETTINGS[
                                                                                         module].__mod_name__) + \
                   CHAT_SETTINGS[module].__chat_settings__(bot, update, chat, chatP, user)
            query.message.reply_text(text=text,
                                     parse_mode=ParseMode.MARKDOWN,
                                     reply_markup=InlineKeyboardMarkup(
                                         [[InlineKeyboardButton(text="Back",
                                                                callback_data="stngs_back({})".format(chat_id))]]))

        elif prev_match:
            chat_id = prev_match.group(1)
            curr_page = int(prev_match.group(2))
            chat = bot.get_chat(chat_id)
            query.message.reply_text(tld(user.id, "send-group-settings").format(chat.title),
                                     reply_markup=InlineKeyboardMarkup(
                                         paginate_modules(curr_page - 1, CHAT_SETTINGS, "stngs",
                                                          chat=chat_id)))

        elif next_match:
            chat_id = next_match.group(1)
            next_page = int(next_match.group(2))
            chat = bot.get_chat(chat_id)
            query.message.reply_text(tld(user.id, "send-group-settings").format(chat.title),
                                     reply_markup=InlineKeyboardMarkup(
                                         paginate_modules(next_page + 1, CHAT_SETTINGS, "stngs",
                                                          chat=chat_id)))

        elif back_match:
            chat_id = back_match.group(1)
            chat = bot.get_chat(chat_id)
            query.message.reply_text(text=tld(user.id, "send-group-settings").format(escape_markdown(chat.title)),
                                     parse_mode=ParseMode.MARKDOWN,
                                     reply_markup=InlineKeyboardMarkup(paginate_modules(user.id, 0, CHAT_SETTINGS, "stngs",
                                                                                        chat=chat_id)))

        # ensure no spinny white circle
        bot.answer_callback_query(query.id)
        query.message.delete()
    except BadRequest as excp:
        if excp.message == "Message is not modified":
            pass
        elif excp.message == "Query_id_invalid":
            pass
        elif excp.message == "Message can't be deleted":
            pass
        else:
            LOGGER.exception("Exception in settings buttons. %s", str(query.data))


@run_async
def get_settings(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    msg = update.effective_message  # type: Optional[Message]
    args = msg.text.split(None, 1)

    # ONLY send settings in PM
    if chat.type != chat.PRIVATE:
        if is_user_admin(chat, user.id):
            text = "Click here to get this chat's settings, as well as yours."
            msg.reply_text(text,
                           reply_markup=InlineKeyboardMarkup(
                               [[InlineKeyboardButton(text="Settings",
                                                      url="t.me/{}?start=stngs_{}".format(
                                                          bot.username, chat.id))]]))
        else:
            text = "Click here to check your settings."

    else:
        send_settings(chat.id, user.id, True)


@run_async
def donate(bot: Bot, update: Update):
    user = update.effective_message.from_user
    chat = update.effective_chat  # type: Optional[Chat]

    if chat.type == "private":
        update.effective_message.reply_text(DONATE_STRING, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

        if OWNER_ID != 254318997 and DONATION_LINK:
            update.effective_message.reply_text("You can also donate to the person currently running me "
                                                "[here]({})".format(DONATION_LINK),
                                                parse_mode=ParseMode.MARKDOWN)

    else:
        try:
            bot.send_message(user.id, DONATE_STRING, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

            update.effective_message.reply_text("I've PM'ed you about donating to my creator!")
        except Unauthorized:
            update.effective_message.reply_text("Contact me in PM first to get donation information.")


def migrate_chats(bot: Bot, update: Update):
    msg = update.effective_message  # type: Optional[Message]
    if msg.migrate_to_chat_id:
        old_chat = update.effective_chat.id
        new_chat = msg.migrate_to_chat_id
    elif msg.migrate_from_chat_id:
        old_chat = msg.migrate_from_chat_id
        new_chat = update.effective_chat.id
    else:
        return

    LOGGER.info("Migrating from %s, to %s", str(old_chat), str(new_chat))
    for mod in MIGRATEABLE:
        mod.__migrate__(old_chat, new_chat)

    LOGGER.info("Successfully migrated!")
    raise DispatcherHandlerStop


def main():
    test_handler = CommandHandler("test", test)
    start_handler = CommandHandler("start", start, pass_args=True)

    help_handler = CommandHandler("help", get_help)
    help_callback_handler = CallbackQueryHandler(help_button, pattern=r"help_")

    start_callback_handler = CallbackQueryHandler(send_start, pattern=r"bot_start")
    dispatcher.add_handler(start_callback_handler)

    cntrl_panel = CommandHandler("controlpanel", control_panel)
    cntrl_panel_callback_handler = CallbackQueryHandler(control_panel, pattern=r"cntrl_panel")
    dispatcher.add_handler(cntrl_panel_callback_handler)
    dispatcher.add_handler(cntrl_panel)

    

    settings_handler = CommandHandler("settings", get_settings)
    settings_callback_handler = CallbackQueryHandler(settings_button, pattern=r"stngs_")

    donate_handler = CommandHandler("donate", donate)
    migrate_handler = MessageHandler(Filters.status_update.migrate, migrate_chats)

    # dispatcher.add_handler(test_handler)
    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(help_handler)
    dispatcher.add_handler(settings_handler)
    dispatcher.add_handler(help_callback_handler)
    dispatcher.add_handler(settings_callback_handler)
    dispatcher.add_handler(migrate_handler)
    dispatcher.add_handler(donate_handler)

    # dispatcher.add_error_handler(error_callback)

    # add antiflood processor
    Dispatcher.process_update = process_update

    if WEBHOOK:
        LOGGER.info("Using webhooks.")
        updater.start_webhook(listen="127.0.0.1",
                              port=PORT,
                              url_path=TOKEN)

        if CERT_PATH:
            updater.bot.set_webhook(url=URL + TOKEN,
                                    certificate=open(CERT_PATH, 'rb'))
        else:
            updater.bot.set_webhook(url=URL + TOKEN)

    else:
        LOGGER.info("Using long polling.")
        updater.start_polling(timeout=15, read_latency=4)

    updater.idle()

CHATS_CNT = {}
CHATS_TIME = {}


def process_update(self, update):
    # An error happened while polling
    if isinstance(update, TelegramError):
        try:
            self.dispatch_error(None, update)
        except Exception:
            self.logger.exception('An uncaught error was raised while handling the error')
        return

    if update.effective_chat: #Checks if update contains chat object
        now = datetime.datetime.utcnow()
        cnt = CHATS_CNT.get(update.effective_chat.id, 0)

        t = CHATS_TIME.get(update.effective_chat.id, datetime.datetime(1970, 1, 1))
        if t and now > t + datetime.timedelta(0, 1):
            CHATS_TIME[update.effective_chat.id] = now
            cnt = 0
        else:
            cnt += 1

        if cnt > 10:
            return
        CHATS_CNT[update.effective_chat.id] = cnt

    for group in self.groups:
        try:
            for handler in (x for x in self.handlers[group] if x.check_update(update)):
                handler.handle_update(update, self)
                break

        # Stop processing with any other handler.
        except DispatcherHandlerStop:
            self.logger.debug('Stopping further handlers due to DispatcherHandlerStop')
            break

        # Dispatch any error.
        except TelegramError as te:
            self.logger.warning('A TelegramError was raised while processing the Update')

            try:
                self.dispatch_error(update, te)
            except DispatcherHandlerStop:
                self.logger.debug('Error handler stopped further handlers')
                break
            except Exception:
                self.logger.exception('An uncaught error was raised while handling the error')

        # Errors should not stop the thread.
        except Exception:
            self.logger.exception('An uncaught error was raised while processing the update')


if __name__ == '__main__':
    LOGGER.info("Successfully loaded modules: " + str(ALL_MODULES))
    LOGGER.info("Successfully loaded")
    main()
