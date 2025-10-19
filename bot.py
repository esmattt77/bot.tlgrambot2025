Import os
import telebot
from flask import Flask, request
from telebot import types

# Import API clients
from viotp_api import VIOTPAPI
# 🟢 التعديل: تم إضافة set_smsman_status هنا
from smsman_api import (
    get_smsman_balance, 
    get_smsman_countries, 
    request_smsman_number, 
    get_smsman_code, 
    cancel_smsman_request,
    set_smsman_status 
)
from tiger_sms_api import TigerSMSAPI

# Import handlers
from user_handlers import setup_user_handlers
from admin_handlers import setup_admin_handlers

# Read bot token and other environment variables
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
PORT = int(os.environ.get('PORT', 5000))

if not TELEGRAM_BOT_TOKEN or not WEBHOOK_URL:
    print("Error: TELEGRAM_BOT_TOKEN and WEBHOOK_URL environment variables must be set.")
    exit()

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
DEVELOPER_ID = int(os.environ.get('DEVELOPER_ID'))
EESSMT = os.environ.get('EESSMT')
ESM7AT = os.environ.get('ESM7AT')
VIOTP_API_KEY = os.environ.get('VIOTP_API_KEY')
SMSMAN_API_KEY = os.environ.get('SMSMAN_API_KEY')
TIGER_SMS_API_KEY = os.environ.get('TIGER_SMS_API_KEY')

# Create API client objects
viotp_client = VIOTPAPI(VIOTP_API_KEY)
tiger_sms_client = TigerSMSAPI(TIGER_SMS_API_KEY)

# 🟢 التعديل: تم إضافة set_smsman_status إلى القاموس
smsman_api = {
    'get_smsman_balance': get_smsman_balance, 
    'get_smsman_countries': get_smsman_countries,
    'request_smsman_number': request_smsman_number, 
    'get_smsman_code': get_smsman_code,
    'cancel_smsman_request': cancel_smsman_request,
    'set_smsman_status': set_smsman_status # 🟢 المفتاح الجديد هنا
}

# Create a Flask app instance
app = Flask(__name__)

# Setup all handlers by passing the necessary objects
setup_user_handlers(bot, DEVELOPER_ID, ESM7AT, EESSMT, viotp_client, smsman_api, tiger_sms_client)
setup_admin_handlers(bot, DEVELOPER_ID, viotp_client, smsman_api, tiger_sms_client)

@app.route(f'/{TELEGRAM_BOT_TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '!', 200
    else:
        return 'Hello, World!', 200

if __name__ == '__main__':
    bot.set_webhook(url=WEBHOOK_URL + TELEGRAM_BOT_TOKEN, allowed_updates=['message', 'callback_query'])
    app.run(host='0.0.0.0', port=PORT)
