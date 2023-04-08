#!/usr/bin/env python

from telegram.constants import ChatType, MessageEntityType
import os
import logging
import settings
import openai
import textract
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from pydub import AudioSegment

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

async def document_processing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print('ctxt:',dir(context))
    print('update:',update)
    try:
        file_info = await context.bot.get_file(update.message.document.file_id)
        downloaded_file = await file_info.download_as_bytearray() 
        filename = update.message.document.file_name
        doc_dir = os.path.join(script_dir,'documents')
        with open(os.path.join(doc_dir,filename), 'wb') as new_file:
            new_file.write(downloaded_file)
        filetext = textract.process(os.path.join(doc_dir,filename))
        usermsg = str(update.message.caption) + "\nFile content: " + str(filetext).replace('\n\n','\n')
        response = get_response(usermsg)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response)
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, " + str(e))

async def voice_processing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print('ctxt:',dir(context))
    print('update:',update)
    try:
        file_info = await context.bot.get_file(update.message.voice.file_id)
        downloaded_file = await file_info.download_as_bytearray()
        filename = 'voice_' + str(update.message.from_user.id)
        with open(os.path.join(script_dir,'voices',filename + '.ogg'), 'wb') as new_file:
            new_file.write(downloaded_file)
        ogg_audio = AudioSegment.from_file(os.path.join(script_dir,'voices',filename + '.ogg'), format="ogg")
        ogg_audio.export(os.path.join(script_dir,'voices',filename + '.mp3'), format="mp3")
        transcript = openai.Audio.transcribe("whisper-1", open(os.path.join(script_dir,'voices',filename + '.mp3'),'rb'))
        response = get_response(transcript.text)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response)
    except Exception as e:
        print("error:",e)
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, " + str(e))

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
    voice_handler = MessageHandler(filters.VOICE, voice_processing)
    doc_handler = MessageHandler(filters.Document.ALL, document_processing)
    application.add_handler(start_handler)
    application.add_handler(echo_handler)
    application.add_handler(voice_handler)
    application.add_handler(doc_handler)
    application.run_polling()
