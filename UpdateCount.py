import base64
import io
import os
import random
import string
import time
import sqlite3
import logging

import requests
import threading

from uuid import uuid4
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, \
    InputTextMessageContent, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, InlineQueryHandler, \
    CallbackQueryHandler
from telegram.utils.helpers import escape_markdown
from PIL import Image, ImageFont, ImageDraw, ImageFilter, ImageOps

''' 
# load environmental variables (.env file)
# load bot-token
'''
load_dotenv()
bot_token = os.environ.get("bot-token")

data = {}
update_delay = 3600 * 24

image_cache = {}


# fetch cache image if it exists in cache
def get_cached_image(_query):
    try:
        return image_cache[parse_string(_query)]['file_id']
    except:
        return None


# cache image if it doesn't exist in cache
def cache_image(_query, _img):
    try:
        item = image_cache[parse_string(_query)]
    except:
        item = None
    if item is None:
        c = (_img['photo']).__len__()
        image_cache[_query] = {'file_id': _img['photo'][c-1]['file_id']}


# Setup database table
def setup_database(setup_cursor, setup_connection):
    try:
        setup_cursor.execute(
            "create table corona (country, total_case, total_death, total_recovery, total_test, critical_case,"
            " active_case, population, update_time, country_name)")
        setup_connection.commit()
    except Exception as e:
        print(e.with_traceback())
        exit(-2)


# load database (local: SQLite)
def load_data():
    logger.info("Initializing database connection")
    load_connection = sqlite3.connect('Corona.db')
    logger.info("Database connection initialized")
    load_cursor = load_connection.cursor()
    logger.info("Database cursor initialized")
    try:
        logger.info("Loading data")
        load_cursor.execute("select * from corona")
        count = 0
        for item in load_cursor.fetchall():
            data[item[0]] = {
                'country': item[0],
                'total_case': item[1],
                'total_death': item[2],
                'total_recovery': item[3],
                'total_test': item[4],
                'critical_case': item[5],
                'active_case': item[6],
                'population': item[7],
                'update_time': item[8],
                'country_name': item[9],
            }
            count += 1

        logger.info(str(count) + " item loaded")
    except:
        logger.error("Error loading data(Database empty)")


def parse_item_string(item_content, index):
    item_data = str(item_content[index].get_text()).strip()
    return "-" if item_data.__len__() == 0 else item_data


def parse_string(_item_):
    return str(_item_).lower().strip().replace(' ', '_')


def update_count(u_cursor, u_connection):
    try:
        site_data = requests.get("https://www.worldometers.info/coronavirus/?zarsrc=130#countries")
        update_time = str(datetime.now()).split(".")[0]
        soup = BeautifulSoup(site_data.text, 'html.parser')
        for data_item in soup.findAll('tr'):
            _item_content = data_item.findAll('td')
            if _item_content.__len__() > 7:
                country = parse_string(parse_item_string(_item_content, 1))
                total_case = parse_item_string(_item_content, 2)
                total_death = parse_item_string(_item_content, 4)
                total_recovery = parse_item_string(_item_content, 6)
                active_case = parse_item_string(_item_content, 8)
                critical_case = parse_item_string(_item_content, 9)
                total_test = parse_item_string(_item_content, 12)
                population = parse_item_string(_item_content, 14)

                if country.__len__() != 0 and country != "Total:" and country != "-":
                    data[country] = {
                        'country': country,
                        'total_case': total_case,
                        'total_death': total_death,
                        'total_recovery': total_recovery,
                        'total_test': total_test,
                        'critical_case': critical_case,
                        'active_case': active_case,
                        'population': population,
                        'update_time': update_time,
                        'country_name': parse_item_string(_item_content, 1),
                    }

        db_empty = False
        try:
            u_cursor.execute("select * from corona")
            u_cursor.fetchall()
            logger.info("Update Thread: Database not empty")
        except Exception as e:
            logger.error("Update Thread: " + str(e))
            logger.info("Update Thread: Database doesn't exist")
            logger.info("Update Thread: Setting up database")
            setup_database(u_cursor, u_connection)
            logger.info("Update Thread: Database setup")
            db_empty = True

        if db_empty:
            logger.info("Update Thread: Inserting data to database")
        else:
            logger.info("Update Thread: Updating database content")

        for key in data.keys():
            if db_empty:
                u_cursor.execute(
                    "insert into corona (country, total_case, total_death, total_recovery, total_test,"
                    "critical_case, active_case, population, update_time, country_name) values (?,?,?,?,?,?,?,?,?,?)",
                    (data[key]['country'], data[key]['total_case'], data[key]['total_death'], data[key]['total_recovery'],
                     data[key]['total_test'], data[key]['critical_case'], data[key]['active_case'], data[key]['population'],
                     data[key]['update_time'], data[key]['country_name']))
            else:
                u_cursor.execute(
                    "update corona set total_case=?, total_death=?, total_recovery=?, total_test=?, critical_case=?, "
                    "active_case=?, population=?, update_time=? where country=?",
                    (data[key]['total_case'], data[key]['total_death'], data[key]['total_recovery'], data[key]['total_test']
                     , data[key]['critical_case'], data[key]['active_case'], data[key]['population'],
                     data[key]['update_time'], key))
        u_connection.commit()
        image_cache.clear()
    except:
        logger.error("Network Error, Couldn't fetch data")


def count_update():
    logger.info("Update Thread: Initializing database connection")
    update_connection = sqlite3.connect('Corona.db')
    logger.info("Update Thread: Database connection initialized")
    update_cursor = update_connection.cursor()
    logger.info("Update Thread: Database cursor initialized")
    while True:
        logger.info("Update Thread: update initialized")
        update_count(update_cursor, update_connection)
        logger.info("Update Thread: update completed")
        logger.info("Update Thread: thread sleeping")
        time.sleep(update_delay)
        logger.info("Update Thread: thread wakeup")


def formatted_query_result(query, item):
    return """
{0}
Total Case:         {1}
Total Death:        {2}
Total Recovery:     {3}
Total Test:         {4}
Critical case:      {5}
Active case:        {6}
Population:         {7}
Update Date:        {8}
            """.format(query, item['total_case'], item['total_death'], item['total_recovery'],
                       item['total_test'], item['critical_case'], item['active_case'], item['population'],
                       item['update_time'], )


def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


country_connection = None


def fetch_image_1(query, item):
    background_image = "http://image.bedrubahru.com/images/corona_ (7).jpg"
    try:
        country_cursor = country_connection.cursor()
        country_cursor.execute("SELECT link FROM country WHERE name = '" + item['country'] + "'")
        flag = country_cursor.fetchall()[0][0]
    except:
        flag = "https://upload.wikimedia.org/wikipedia/commons/e/ef/International_Flag_of_Planet_Earth.svg"

    bot_name = "@CoronaCounter_bot"

    parsed_html = """
        <!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>Title</title>
    <style>
      body {
        width: 450px;
        height: 550px;
        margin: 0;
      }
      .bg-image {
            position: fixed;
            width: 450px;
            z-index: 1;
            top: 0;
            left: 0;
      }
      .jumbotron {
        color: white;
        position: fixed;
        top: 5px;
        left: 5px;
        z-index: 10;
      }
      .overlay {
        position: relative;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: black;
        opacity: 0.5;
        z-index: 2;
      }
      .content {
        position: relative;
        top: 40px;
        z-index: 25;
        width: 445px;
      }
      .flag {
        display: block;
        margin: auto;
        box-shadow: 0 0 2px 2px #fff;
        width: 140px;
        height: 80px;
      }
      .text_con{
          margin-top: 30px;
      }
      .table_x thead, tbody{
          margin: auto;
          display: block;
      }
      .small{
          font-size: 12px;
      }
      .heads{
        padding: 7px 40px;
         font-size: 17px;
      }
      .values{
        padding: 10px 60px;
        font-size: 16px;
      }
      .c_name{
          padding-left: 10px;
      }
    </style>
  </head>"""

    parsed_html += f"""
  <body>
    <img src="{background_image}" class="bg-image" />
    <div class="jumbotron text-center splash">
      <div class="content">
        <img
          class="flag"
          src="{flag}"
          alt="image_"
        />

        <div class="text_con">
            <h2 class="c_name">{query}</h2>
            <table class="table_x">
                <thead>
                    <tr>
                        <td></td>
                        <td></td>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td class="heads">Total test </td>
                        <td class="values">{item['total_test']}</td>
                    </tr>
                    <tr>
                        <td class="heads">Total case </td>
                        <td class="values">{item['total_case']}</td>
                    </tr>
                    <tr>
                        <td class="heads">Total death </td>
                        <td class="values">{item['total_death']}</td>
                    </tr>
                    <tr>
                        <td class="heads">Total recovery </td>
                        <td class="values">{item['total_recovery']}</td>
                    </tr>
                    <tr>
                        <td class="heads">Active case </td>
                        <td class="values">{item['active_case']}</td>
                    </tr>
                    <tr>
                        <td class="heads">Critical case </td>
                        <td class="values">{item['critical_case']}</td>
                    </tr>
                    <tr>
                        <td class="heads">Population </td>
                        <td class="values">{item['population']}</td>
                    </tr>
                </tbody>
            </table>    
            <br>   
            <span class="small">{parse_date(item['update_time'])}</span><br>
            <span class="small">{bot_name}</span>
        </div>
      </div>
    </div>
  </body>
</html>
    """

    response = requests.post('http://image.bedribahru.com/convert', {'html': parsed_html})
    return response.content


def fetch_image(query, item):
    __image = get_cached_image(query)
    if __image is not None:
        print("Image form cache")
        return {"status": 200, 'source': 'cache', "data": __image}
    try:
        country_cursor = country_connection.cursor()
        country_cursor.execute("SELECT flag_path FROM country WHERE name = '" + item['country'] + "'")
        flag = country_cursor.fetchall()[0][0]
    except:
        flag = "/countries/International_flag.png"
    try:
        size = 2000, 1400
        my_image = Image.open("image/background.jpg")
        my_image.thumbnail(size, Image.ANTIALIAS)
        title_font = ImageFont.truetype('fonts/Singika.ttf', 55)
        sub_font = ImageFont.truetype('fonts/Singika.ttf', 45)
        sud_font = ImageFont.truetype('fonts/Singika.ttf', 35)

        country_name = query
        tc_p = "Total case"
        tc_v = item['total_case']
        tt_p = "Total test"
        tt_v = item['total_test']
        td_p = "Total death"
        td_v = item['total_death']
        tr_p = "Total recovery"
        tr_v = item['total_recovery']
        ac_p = "Active Case"
        ac_v = item['active_case']
        po_p = "Population"
        po_v = item['population']
        cc_p = "Critical Case"
        cc_v = item['critical_case']
        ut_v = parse_date(item['update_time'])
        bn_v = "@CoronaCounter_Bot"

        item_hh = 480
        level_mult = 100

        item_ws = 150
        item_we = 550

        image_editable = ImageDraw.Draw(my_image)
        image_editable.text((30, 310), country_name, (237, 230, 211), font=title_font)

        image_editable.text((item_ws, item_hh + (0 * level_mult)), tt_p, (237, 230, 211), font=sub_font)
        image_editable.text((item_we, item_hh + (0 * level_mult)), tt_v, (237, 230, 211), font=sub_font)

        image_editable.text((item_ws, item_hh + (1 * level_mult)), tc_p, (237, 230, 211), font=sub_font)
        image_editable.text((item_we, item_hh + (1 * level_mult)), tc_v, (237, 230, 211), font=sub_font)

        image_editable.text((item_ws, item_hh + (2 * level_mult)), td_p, (237, 230, 211), font=sub_font)
        image_editable.text((item_we, item_hh + (2 * level_mult)), td_v, (237, 230, 211), font=sub_font)

        image_editable.text((item_ws, item_hh + (3 * level_mult)), tr_p, (237, 230, 211), font=sub_font)
        image_editable.text((item_we, item_hh + (3 * level_mult)), tr_v, (237, 230, 211), font=sub_font)

        image_editable.text((item_ws, item_hh + (4 * level_mult)), ac_p, (237, 230, 211), font=sub_font)
        image_editable.text((item_we, item_hh + (4 * level_mult)), ac_v, (237, 230, 211), font=sub_font)

        image_editable.text((item_ws, item_hh + (5 * level_mult)), cc_p, (237, 230, 211), font=sub_font)
        image_editable.text((item_we, item_hh + (5 * level_mult)), cc_v, (237, 230, 211), font=sub_font)

        image_editable.text((item_ws, item_hh + (6 * level_mult)), po_p, (237, 230, 211), font=sub_font)
        image_editable.text((item_we, item_hh + (6 * level_mult)), po_v, (237, 230, 211), font=sub_font)

        image_editable.text((30, item_hh + (8.2 * level_mult)), ut_v, (237, 230, 211), font=sud_font)
        image_editable.text((30, item_hh + (8.7 * level_mult)), bn_v, (237, 230, 211), font=sud_font)

        flag = Image.open(flag[1:])
        # flag = ImageOps.expand(flag, border=1, fill='rgb(0,0,0)')
        flag.thumbnail((300, 250), Image.ANTIALIAS)
        mask_im = Image.new("L", flag.size, 0)
        draw = ImageDraw.Draw(mask_im)
        draw.rectangle((0, 0, 300, 250), fill=255)
        mask_im_blur = mask_im.filter(ImageFilter.GaussianBlur(10))
        my_image.paste(flag, (315, 50), mask_im_blur)
        random_name = 'out/' + id_generator(10) + '_' + str(int(time.time())) + '.png'
        my_image.save(random_name)
        return {"status": 200, 'source': 'img_create', "data": random_name}
    except Exception as ex:
        print(ex)
        logger.exception(ex)
        return {'status': 500, 'data': "None"}


def parse_date(s):
    f = "%Y-%m-%d %H:%M:%S"
    date_ = datetime.strptime(s, f)
    return date_.strftime('%Y, %b %d')


def data_query(query):
    try:
        main_query = query
        found = False
        query = query.title()
        if query.lower().strip() == 'usa':
            query = 'USA'
        if query.lower().strip() == 'united states':
            query = 'USA'
        if query.lower().strip() == 'britain':
            query = 'UK'
        if query.lower().strip() == 'england':
            query = 'UK'
        if query.lower().strip() == 'uk':
            query = 'UK'
        if query.lower().strip() == 'democratic republic of congo':
            query = 'DRC'
        if query.lower().strip() == 'congo':
            query = 'DRC'

        sub_query = parse_string(query)

        for key in data.keys():
            if key == sub_query.lower():
                item = data[key]
                found = True
                r = None
                try:
                    resp = fetch_image(main_query, item)
                    logger.info(resp)
                    if resp['status'] == '500':
                        r = {"type": 'text', 'data': formatted_query_result(main_query, item)}
                    else:
                        logger.info("===================================================")
                        r = {"type": 'image', 'source': resp['source'], 'data': resp['data'],
                             'text': formatted_query_result(main_query, item)}
                except Exception as s:
                    r = {"type": 'text', 'data': formatted_query_result(main_query, item)}
                return r
        if not found:
            r = {"type": 'text', 'data': "\"" + main_query + "\" not found in list of countries!"}
            return r
    except Exception as v:
        print(v.with_traceback())
        r = {"type": 'text', 'data': "There was an error!"}
        return r


# Enable logging
# logging.basicConfig(filename='Log_po.txt',
#                     filemode='a',
#                     format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
#                     datefmt='%H:%M:%S',
#                     level=logging.DEBUG)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

logger = logging.getLogger(__name__)


# Define a few command handlers. These usually take the two arguments update and
# context.
def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    username = "User" if user.username is None else user.username
    update.message.reply_text("Hi " + username + ", I am Corona case counter bot. Send me the name of the country you "
                                                 "want and I will give you the country's information related to "
                                                 "Corona. \nExample:- Ethiopia")


def countries_list(update: Update, context: CallbackContext) -> None:
    global country_connection
    if country_connection is None:
        country_connection = sqlite3.connect('Corona.db')

    c_cursor = country_connection.cursor()
    res = c_cursor.execute("SELECT country, country_name FROM corona ORDER BY country_name")
    f = []
    o = []
    s = []
    for item in res.fetchall():
        ll = str(item[1])[0]
        if ll is None:
            continue
        if not s.__contains__(ll):
            s.append(ll)
            o.append(InlineKeyboardButton(ll, callback_data=ll))
            if o.__len__() == 5:
                f.append(o)
                o = []

    # f.append([InlineKeyboardButton("Prev", callback_data='prev')])
    # f.append([InlineKeyboardButton("Next", callback_data='next')])

    keyboard = f

    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Please choose country:', reply_markup=reply_markup)


def button(update: Update, context: CallbackContext) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    query.answer()
    if query.data != "next" or query.data != "prev":
        if query.data.__len__() == 1:
            global country_connection
            if country_connection is None:
                country_connection = sqlite3.connect('Corona.db')

            c_cursor = country_connection.cursor()
            mm = query.data + '%'
            sql_q = "SELECT country, country_name FROM corona WHERE country_name LIKE ? ORDER BY country_name"
            res = c_cursor.execute(sql_q, (mm,))
            f = []
            o = []
            for item in res.fetchall():
                ll = str(item[1])
                o.append(InlineKeyboardButton(ll, callback_data=ll))
                if o.__len__() == 2:
                    f.append(o)
                    o = []

            # f.append([InlineKeyboardButton("Prev", callback_data='prev')])
            # f.append([InlineKeyboardButton("Next", callback_data='next')])

            keyboard = f

            reply_markup = InlineKeyboardMarkup(keyboard)
            query.edit_message_text(text='Please choose country:', reply_markup=reply_markup)
        else:
            result = data_query(query.data)
            if result['type'] == 'image':
                try:
                    query.edit_message_text("Country: " + query.data)
                    if result['source'] == 'cache':
                        query.message.reply_photo(result['data'])
                    else:
                        item = query.message.reply_photo(open(result['data'], 'rb'))
                        cache_image(parse_string(query.data), item)
                        print("Image cached")
                except:
                    query.edit_message_text(result['text'])
            elif result['type'] == 'text':
                query.edit_message_text(result['data'])
    else:
        query.edit_message_text(text=f"Selected option: {query.data}")


def help_command(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Corona count update bot')


def Handle(update: Update, context: CallbackContext) -> None:
    global country_connection
    if country_connection is None:
        country_connection = sqlite3.connect('Corona.db')
    result = data_query(update.message.text)
    if result['type'] == 'image':
        try:
            if result['source'] == 'cache':
                update.message.reply_photo(result['data'])
            else:
                item = update.message.reply_photo(open(result['data'], 'rb'))
                cache_image(parse_string(update.message.text), item)
                print("Image cached!")

        except Exception as d:
            print(d)
            update.message.reply_text(result['text'])
    elif result['type'] == 'text':
        update.message.reply_text(result['data'])


def world_update(update: Update, context: CallbackContext) -> None:
    global country_connection
    if country_connection is None:
        country_connection = sqlite3.connect('Corona.db')
    result = data_query("World")
    if result['type'] == 'image':
        try:
            if result['source'] == 'cache':
                img = update.message.reply_photo(result['data'])
                cache_image("World", img)
            else:
                update.message.reply_photo(open(result['data'], 'rb'))
        except:
            update.message.reply_text(result['text'])
    elif result['type'] == 'text':
        update.message.reply_text(result['data'])


def inlinequery(update: Update, context: CallbackContext) -> None:
    """Handle the inline query."""
    query = update.inline_query.query

    if query == "":
        return

    results = [
        InlineQueryResultArticle(
            id=str(uuid4()),
            title="Caps",
            input_message_content=InputTextMessageContent(query.upper()),
        ),
        InlineQueryResultArticle(
            id=str(uuid4()),
            title="Bold",
            input_message_content=InputTextMessageContent(
                f"*{escape_markdown(query)}*", parse_mode=ParseMode.MARKDOWN
            ),
        ),
        InlineQueryResultArticle(
            id=str(uuid4()),
            title="Italic",
            input_message_content=InputTextMessageContent(
                f"_{escape_markdown(query)}_", parse_mode=ParseMode.MARKDOWN
            ),
        ),
    ]

    update.inline_query.answer(results)


def main() -> None:
    load_data()
    update_thread = threading.Thread(target=count_update)
    logger.info("Database update thread initialized")
    logger.info("Database update thread started")
    update_thread.start()

    updater = Updater(bot_token)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("update", world_update))
    dispatcher.add_handler(CommandHandler("list", countries_list))
    updater.dispatcher.add_handler(CallbackQueryHandler(button))
    dispatcher.add_handler(CommandHandler("help", help_command))

    dispatcher.add_handler(InlineQueryHandler(inlinequery))

    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, Handle))
    updater.start_polling()

    updater.idle()


if __name__ == '__main__':
    main()
