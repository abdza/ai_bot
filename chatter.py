#!/usr/bin/env python

from telegram.constants import ChatType, MessageEntityType
import os
import logging
import settings
import openai
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

openai.api_key = settings.openai_key

script_path = os.path.abspath(__file__)

# Get the directory containing the current script
script_dir = os.path.dirname(script_path)

messages = []

def get_response(content):
    try:
        messages.append({'role':'user','content':content})
        response = openai.ChatCompletion.create(
            model='gpt-3.5-turbo',
            messages=messages
        )
        messages.append(response.choices[0].message)
        return response.choices[0].message.content
    except Exception as e:
        raise e

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

async def catch_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print('ctxt:',dir(context))
    print('update:',update)
    mentiontest = [etype.type==MessageEntityType.MENTION for etype in update.message.entities]
    print("Mtest:",mentiontest)
    if update.message.chat.type == ChatType.PRIVATE or any(mentiontest):
        try:
            response = get_response(update.message.text)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=response)
        except Exception as e:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, " + str(e))
    else:
        pass

if __name__ == '__main__':
    application = ApplicationBuilder().token(settings.bot_key).build()
    start_handler = CommandHandler('start', start)
    echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), catch_all)
    application.add_handler(start_handler)
    application.add_handler(echo_handler)
    application.run_polling()
