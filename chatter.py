#!/usr/bin/env python

from telegram.constants import ChatType, MessageEntityType
import os
import logging
import settings
import openai
import textract
import sqlite3
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

con = sqlite3.connect(os.path.join(script_dir,"chat.db"))

# messages = []

def update_db():
    cursor = con.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS chat (id INTEGER PRIMARY KEY, timestamp, role TEXT, user TEXT, chat TEXT, message TEXT)")
    con.commit()
    cursor.close()

def get_response(content,update):
    try:
        cursor = con.cursor()
        cursor.execute("INSERT INTO chat (timestamp, role, user, chat, message) VALUES (datetime('now'), 'user', ?, ?, ?)", (update.message.from_user.id, update.message.chat.id, content))
        con.commit()
        messages = cursor.execute("SELECT message,role FROM chat WHERE chat = ? ORDER BY timestamp", (update.message.chat.id,)).fetchall()
        history = [{'role':'assistant','content':m[0]} if m[1]=='assistant' else {'role':'user','content':m[0]} for m in messages]
        print('history:',history)
        response = openai.ChatCompletion.create(
            model='gpt-3.5-turbo',
            messages=history
        )
        print(response)
        cursor.execute("INSERT INTO chat (timestamp, role, user, chat, message) VALUES (datetime('now'), 'assistant', ?, ?, ?)", (update.message.from_user.id, update.message.chat.id, response.choices[0].message.content))
        print("after saving this response:",response.choices[0].message)
        con.commit()
        cursor.close()
        return response.choices[0].message.content
    except Exception as e:
        print("Error: ", e)
        raise e

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

async def imagine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print('ctxt:',dir(context))
    print('update:',update)
    try:
        response = openai.Image.create(
            prompt=update.message.text,
        n=1,
        size="1024x1024"
        )
        image_url = response['data'][0]['url']
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_url)
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, " + str(e))

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
        response = get_response(usermsg,update)
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
        response = get_response(transcript.text,update)
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
            response = get_response(update.message.text,update)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=response)
        except Exception as e:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, " + str(e))
    else:
        pass

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        cursor = con.cursor()
        cursor.execute("delete from chat where chat=?", (update.message.chat.id,))
        con.commit()
        cursor.close()
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Reset done")
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, " + str(e))

if __name__ == '__main__':
    update_db()
    application = ApplicationBuilder().token(settings.bot_key).build()
    start_handler = CommandHandler('start', start)
    reset_handler = CommandHandler('reset', reset)
    imagine_handler = CommandHandler('imagine', imagine)
    echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), catch_all)
    voice_handler = MessageHandler(filters.VOICE, voice_processing)
    doc_handler = MessageHandler(filters.Document.ALL, document_processing)
    application.add_handler(imagine_handler)
    application.add_handler(reset_handler)
    application.add_handler(start_handler)
    application.add_handler(echo_handler)
    application.add_handler(voice_handler)
    application.add_handler(doc_handler)
    application.run_polling()
