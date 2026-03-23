# bot.py (معدل وجاهز للعمل على Render)

import os
import telebot
from flask import Flask, request
from telebot import types
import logging 
import time 

# تهيئة نظام التسجيل: يضمن ظهور السجلات والأخطاء في Log الاستضافة
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s' 
)

# Import API clients
from smmkings_api import SMMKingsAPI 
from smsman_api import (
    get_smsman_balance, 
    get_smsman_countries, 
    request_smsman_number, 
    get_smsman_code, 
    cancel_smsman_request,
    set_smsman_status 
)
from hero_sms_api import HeroSMSAPI

# Import handlers
from user_handlers import setup_user_handlers
from admin_handlers import setup_admin_handlers

# 🚀 [التعديل الحاسم لتوافق Render] 
# المنفذ الافتراضي لـ Render هو 10000. نعتمد عليه إذا لم يتم تعيين المتغير.
PORT = int(os.environ.get('PORT', 10000)) 

# Read bot token and other environment variables
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')

if not TELEGRAM_BOT_TOKEN or not WEBHOOK_URL:
    logging.error("Error: TELEGRAM_BOT_TOKEN and WEBHOOK_URL environment variables must be set.")
    # 📌 توقف التشغيل إذا كانت المتغيرات الأساسية مفقودة
    exit() 

# 💡 تعطيل الـ threading في telebot في بيئة الـ Webhook
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, threaded=False)
DEVELOPER_ID = int(os.environ.get('DEVELOPER_ID', 0)) # إضافة قيمة افتراضية آمنة
EESSMT = os.environ.get('EESSMT')
ESM7AT = os.environ.get('ESM7AT')

# Get API Keys
SMMKINGS_API_KEY = os.environ.get('SMMKINGS_API_KEY') 
SMSMAN_API_KEY = os.environ.get('SMSMAN_API_KEY')
HERO_SMS_API_KEY = os.environ.get('HERO_SMS_API_KEY')

# Create API client objects
smmkings_client = SMMKingsAPI(SMMKINGS_API_KEY)
hero_sms_client = HeroSMSAPI(HERO_SMS_API_KEY)

# قاموس API لـ SMSMan
smsman_api = {
    'get_smsman_balance': get_smsman_balance, 
    'get_smsman_countries': get_smsman_countries,
    'request_smsman_number': request_smsman_number, 
    'get_smsman_code': get_smsman_code,
    'cancel_smsman_request': cancel_smsman_request,
    'set_smsman_status': set_smsman_status 
}

# Create a Flask app instance
app = Flask(__name__)

# 🟢 إعداد الـ Handlers وتمرير العملاء
setup_user_handlers(bot, DEVELOPER_ID, ESM7AT, EESSMT, smmkings_client, smsman_api, hero_sms_client)
setup_admin_handlers(bot, DEVELOPER_ID, smmkings_client, smsman_api, hero_sms_client)

@app.route(f'/{TELEGRAM_BOT_TOKEN}', methods=['POST'])
def webhook():
    """معالج Webhook الأساسي الذي يستقبل التحديثات من تيليجرام."""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        
        try:
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
        except Exception as e:
            # تسجيل الخطأ لظهوره في سجلات الاستضافة
            logging.error(f"❌ FATAL HANDLER EXCEPTION: {type(e).__name__} - {e}")
        
        # يجب أن يستجيب الـ Webhook دائمًا بـ 200 OK
        return '!', 200
    else:
        return 'Hello, World!', 200

if __name__ == '__main__':
    logging.info("Attempting to set Webhook...")
    try:
        # حذف الـ webhook القديم قبل تعيين الجديد
        bot.delete_webhook() 
    except Exception as e:
        logging.warning(f"Failed to delete old webhook: {e}")

    # تعيين الـ Webhook الجديد
    webhook_url_full = WEBHOOK_URL + TELEGRAM_BOT_TOKEN
    bot.set_webhook(url=webhook_url_full, allowed_updates=['message', 'callback_query'])
    logging.info(f"Webhook set to: {webhook_url_full}")
    
    # تشغيل تطبيق Flask
    logging.info(f"Flask app starting on host 0.0.0.0, port {PORT}...")
    # 📌 التعديل الحاسم: التأكد من الاستماع للمنفذ الذي تتوقعه Render
    app.run(host='0.0.0.0', port=PORT)
