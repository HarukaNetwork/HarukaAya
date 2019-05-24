from typing import Optional, List

from telegram import ParseMode
from telegram import Message, Chat, Update, Bot, User
from telegram.error import BadRequest
from telegram.ext import CommandHandler, Filters
from telegram.ext.dispatcher import run_async
from telegram.utils.helpers import mention_html

import haruka.modules.sql.connection_sql as sql
from haruka import dispatcher, LOGGER, SUDO_USERS
from haruka.modules.helper_funcs.chat_status import bot_admin, user_admin, is_user_admin, can_restrict
from haruka.modules.helper_funcs.extraction import extract_user, extract_user_and_text
from haruka.modules.helper_funcs.string_handling import extract_time

from haruka.modules.translations.strings import tld

from haruka.modules.keyboard import keyboard


@user_admin
@run_async
def allow_connections(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    if chat.type != chat.PRIVATE:
        if len(args) >= 1:
            var = args[0]
            print(var)
            if var == "no":
                sql.set_allow_connect_to_chat(chat.id, False)
                update.effective_message.reply_text(tld(chat.id, "Disabled connections to this chat for users"))
            elif var == "yes":
                sql.set_allow_connect_to_chat(chat.id, True)
                update.effective_message.reply_text(tld(chat.id, "Enabled connections to this chat for users"))
            else:
                update.effective_message.reply_text(tld(chat.id, "Please enter on/yes/off/no in group!"))
        else:
            update.effective_message.reply_text(tld(chat.id, "Please enter on/yes/off/no in group!"))
    else:
        update.effective_message.reply_text(tld(chat.id, "Please enter on/yes/off/no in group!"))


@run_async
def connect_chat(bot, update, args):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    if update.effective_chat.type == 'private':
        if len(args) >= 1:
            try:
                connect_chat = int(args[0])
            except ValueError:
                update.effective_message.reply_text(tld(chat.id, "Invalid Chat ID provided!"))
                return
            if (bot.get_chat_member(connect_chat, update.effective_message.from_user.id).status in ('administrator', 'creator') or 
                                     (sql.allow_connect_to_chat(connect_chat) == True) and 
                                     bot.get_chat_member(connect_chat, update.effective_message.from_user.id).status in ('member')) or (
                                     user.id in SUDO_USERS):

                connection_status = sql.connect(update.effective_message.from_user.id, connect_chat)
                if connection_status:
                    chat_name = dispatcher.bot.getChat(connected(bot, update, chat, user.id, need_admin=False)).title
                    update.effective_message.reply_text(tld(chat.id, "Successfully connected to *{}*").format(chat_name), parse_mode=ParseMode.MARKDOWN)

                    #Add chat to connection history
                    history = sql.get_history(user.id)
                    if history:
                        #Vars
                        if history.chat_id1:
                            history1 = int(history.chat_id1)
                        if history.chat_id2:
                            history2 = int(history.chat_id2)
                        if history.chat_id3:
                            history3 = int(history.chat_id3)
                        if history.updated:
                            number = history.updated

                        if number == 1 and connect_chat != history2 and connect_chat != history3:
                            history1 = connect_chat
                            number = 2
                        elif number == 2 and connect_chat != history1 and connect_chat != history3:
                            history2 = connect_chat
                            number = 3
                        elif number >= 3 and connect_chat != history2 and connect_chat != history1:
                            history3 = connect_chat
                            number = 1
                        else:
                            print("Error")
                    
                        print(history.updated)
                        print(number)

                        sql.add_history(user.id, history1, history2, history3, number)
                        print(history.user_id, history.chat_id1, history.chat_id2, history.chat_id3, history.updated)
                    else:
                        sql.add_history(user.id, connect_chat, "0", "0", 2)
                    #Rebuild user's keyboard
                    keyboard(bot, update)
                    
                else:
                    update.effective_message.reply_text(tld(chat.id, "Connection failed!"))
            else:
                update.effective_message.reply_text(tld(chat.id, "Connections to this chat not allowed!"))
        else:
            update.effective_message.reply_text(tld(chat.id, "Input chat ID to connect!"))
            history = sql.get_history(user.id)
            print(history.user_id, history.chat_id1, history.chat_id2, history.chat_id3, history.updated)

    elif update.effective_chat.type == 'supergroup':
        connect_chat = chat.id
        if (bot.get_chat_member(connect_chat, update.effective_message.from_user.id).status in ('administrator', 'creator') or (sql.allow_connect_to_chat(connect_chat) == True) and bot.get_chat_member(connect_chat, update.effective_message.from_user.id).status in'member') or (user.id in SUDO_USERS):

            connection_status = sql.connect(update.effective_message.from_user.id, connect_chat)
            if connection_status:
                update.effective_message.reply_text(tld(chat.id, "Succesfully connected to *{}*").format(chat.id),
                                                    parse_mode=ParseMode.MARKDOWN)
            else:
                update.effective_message.reply_text(tld(chat.id, "Failed to connect to *{}*").format(chat.id),
                                                    parse_mode=ParseMode.MARKDOWN)
        else:
            update.effective_message.reply_text(tld(chat.id, "You are not admin!"))

    else:
        update.effective_message.reply_text(tld(chat.id, "Usage is limited to PMs only!"))


def disconnect_chat(bot, update):
    if update.effective_chat.type == 'private':
        disconnection_status = sql.disconnect(update.effective_message.from_user.id)
        if disconnection_status:
            sql.disconnected_chat = update.effective_message.reply_text("Disconnected from chat!")
            #Rebuild user's keyboard
            keyboard(bot, update)
        else:
           update.effective_message.reply_text("Disconnection unsuccessfull!")
    elif update.effective_chat.type == 'supergroup':
        disconnection_status = sql.disconnect(update.effective_message.from_user.id)
        if disconnection_status:
            sql.disconnected_chat = update.effective_message.reply_text("Disconnected from chat!")
            # Rebuild user's keyboard
            keyboard(bot, update)
        else:
            update.effective_message.reply_text("Disconnection unsuccessfull!")
    else:
        update.effective_message.reply_text("Usage is restricted to PMs only")


def connected(bot, update, chat, user_id, need_admin=True):
    if chat.type == chat.PRIVATE and sql.get_connected_chat(user_id):
        conn_id = sql.get_connected_chat(user_id).chat_id
        if (bot.get_chat_member(conn_id, user_id).status in ('administrator', 'creator') or 
                                     (sql.allow_connect_to_chat(connect_chat) == True) and 
                                     bot.get_chat_member(user_id, update.effective_message.from_user.id).status in ('member')) or (
                                     user_id in SUDO_USERS):
            if need_admin:
                if bot.get_chat_member(conn_id, update.effective_message.from_user.id).status in ('administrator', 'creator') or user_id in SUDO_USERS:
                    return conn_id
                else:
                    update.effective_message.reply_text("You need to be a admin in a connected group!")
                    exit(1)
            else:
                return conn_id
        else:
            update.effective_message.reply_text("Group changed rights connection or you are not admin anymore.\nI'll disconnect you.")
            disconnect_chat(bot, update)
            exit(1)
    else:
        return False


__help__ = """
Sometimes, you just want to add some notes and filters to a group chat, but you don't want everyone to see; This is where connections come in...

This allows you to connect to a chat's database, and add things to it without the chat knowing about it! For obvious reasons, you need to be an admin to add things; but any member can view your data. (banned/kicked users can't!)

Actions are available with connected groups:
 • View and edit notes
 • View and edit filters
 • View and edit blacklists
 • Promote/demote users
 • See adminlist, see invitelink
 • Disable/enable commands in chat
 • Mute/unmute users in chat
 • Restrict/unrestrict users in chat
 • More in future!

 - /connection <chatid>: Connect to remote chat
 - /disconnect: Disconnect from chat
 - /allowconnect on/yes/off/no: Allow connect users to group

 You can retrieve the chat id by using the /id command in your chat. Don't be surprised if the id is negative; all super groups have negative ids.
"""

__mod_name__ = "Connections"

CONNECT_CHAT_HANDLER = CommandHandler("connect", connect_chat, allow_edited=True, pass_args=True)
DISCONNECT_CHAT_HANDLER = CommandHandler("disconnect", disconnect_chat, allow_edited=True)
ALLOW_CONNECTIONS_HANDLER = CommandHandler("allowconnect", allow_connections, allow_edited=True, pass_args=True)

dispatcher.add_handler(CONNECT_CHAT_HANDLER)
dispatcher.add_handler(DISCONNECT_CHAT_HANDLER)
dispatcher.add_handler(ALLOW_CONNECTIONS_HANDLER)
