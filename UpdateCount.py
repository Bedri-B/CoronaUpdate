from datetime import datetime
import threading
import time
from bs4 import BeautifulSoup
import requests
import sqlite3
import logging
from telegram import Update, ForceReply
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

con = sqlite3.connect('Corona.db')
cur = con.cursor()
data = {}
delay = 3600


def setup():
    cur.execute("create table Corona (Country, tcase, tdeath, trecovery)")


def load():
    cur.execute("select * from Corona")
    for item in cur.fetchall():
        data[item[0]] = [item[1], item[2], item[3], item[4]]
    print("Data Loaded!")


def updateCount(cursor, connection):
    ss = requests.get("https://www.worldometers.info/coronavirus/?zarsrc=130#countries")
    updatetime = datetime.now()
    dd = BeautifulSoup(ss.text, 'html.parser')
    for item in dd.findAll('tr'):
        n = item.findAll('td')
        m = []
        if n.__len__() > 7:
            Country = str(n[1].get_text()).strip()
            tcase = str(n[2].get_text()).strip()
            tdeath = str(n[4].get_text()).strip()
            trecovery = str(n[6].get_text()).strip()
            if Country.__len__() != 0 and Country != "Total:":
                data[Country] = [tcase, tdeath, trecovery, str(updatetime).split(".")[0]]

    try:
        cursor.execute("select * from Corona")
        cursor.fetchall()
    except Exception as e:
        print(e)
        setup()

    for key in data.keys():
        cursor.execute("update Corona set tcase=?, tdeath=?, trecovery=?, updatetime=?  where Country=?",
                       (data[key][0], data[key][1], data[key][2], data[key][3], key))

        # cur.execute("insert into Corona values (?, ?, ?, ?, ?)", (key, data[key][0], data[key][1], data[key][2],
        # updatetime))
    connection.commit()

def Update():
    connection = sqlite3.connect('Corona.db')
    cursor = connection.cursor()
    while True:
        updateCount(cursor, connection)
        time.sleep(delay)


def Query(query):
    try:
        found = False
        query = query.title()
        if query.lower().strip() == 'usa':
            query = 'USA'
        if query.lower().strip() == 'united states':
            query = 'USA'
        if query.lower().strip() == 'britain':
            query = 'USA'
        if query.lower().strip() == 'england':
            query = 'UK'
        if query.lower().strip() == 'uk':
            query = 'UK'
        if query.lower().strip() == 'democratic republic of congo':
            query = 'DRC'
        if query.lower().strip() == 'congo':
            query = 'DRC'

        for key in data.keys():
            if str(key).lower() == query.lower():
                item = data[key]
                found = True
                return query + "\nTotal Case: " + item[0] + "\nTotal Death: " + item[1] + "\nTotal Recovery: " + item[
                    2] + "\nUpdate Date: " + str(item[3])
        if not found:
            return "Item not found in database!"
    except Exception as v:
        print(v.with_traceback())
        return "There was an error!"


# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)


# Define a few command handlers. These usually take the two arguments update and
# context.
def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    update.message.reply_markdown_v2(
        fr'Hi {user.mention_markdown_v2()}\!',
        reply_markup=ForceReply(selective=True),
    )


def help_command(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Corona Update Bot')


def Handle(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(Query(update.message.text))


def main() -> None:
    load()
    t1 = threading.Thread(target=Update)
    t1.start()

    updater = Updater("Token")
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, Handle))
    updater.start_polling()

    updater.idle()


if __name__ == '__main__':
    main()
