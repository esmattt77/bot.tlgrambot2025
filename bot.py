import time
import telebot
from telebot import types
import json
import requests
import os
from viotp_api import VIOTPAPI
from smsman_api import get_smsman_balance, get_smsman_countries, request_smsman_number, get_smsman_code, cancel_smsman_request
from tiger_sms_api import TigerSMSAPI
from flask import Flask, request

# Import the new handlers
from user_handlers import setup_user_handlers
from admin_handlers import setup_admin_handlers

# Read bot token from environment variables
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
smsman_api = __import__('smsman_api')

# Create a Flask app instance
app = Flask(__name__)

# --- Helper Functions ---
def load_data():
    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            if 'sh_services' not in data:
                data['sh_services'] = {}
            if 'countries' not in data:
                data['countries'] = {}
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {'users': {}, 'states': {}, 'countries': {}, 'active_requests': {}, 'sh_services': {}}

def save_data(data):
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_users():
    try:
        with open('users.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_users(users):
    with open('users.json', 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=4, ensure_ascii=False)

def register_user(user_id, first_name, username):
    users_data = load_users()
    if str(user_id) not in users_data:
        users_data[str(user_id)] = {
            'id': user_id,
            'first_name': first_name,
            'username': username,
            'balance': 0,
            'join_date': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
        }
        save_users(users_data)

# --- Registering handlers from separate files ---
data_file = load_data()
users_data = load_users()

setup_user_handlers(bot, DEVELOPER_ID, data_file, users_data, ESM7AT, EESSMT, viotp_client, smsman_api, tiger_sms_client)
setup_admin_handlers(bot, DEVELOPER_ID, data_file, users_data, viotp_client, smsman_api, tiger_sms_client)

# --- Webhook Route ---
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
