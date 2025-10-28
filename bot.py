import os
import telebot
from flask import Flask, request
from telebot import types
import logging # 💡 إضافة مكتبة التسجيل
import time # 💡 إضافة مكتبة time للاستخدام المستقبلي إذا لزم

# 💡 تهيئة نظام التسجيل: يضمن ظهور السجلات والأخطاء في Log الاستضافة
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s' 
)

# Import API clients
# 💡 [التعديل 1: استبدال VIOTPAPI بـ SMMKingsAPI]
from smmkings_api import SMMKingsAPI 
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
    logging.error("Error: TELEGRAM_BOT_TOKEN and WEBHOOK_URL environment variables must be set.")
    exit()

# 💡 التعديل 1: تعطيل الـ threading في telebot في بيئة الـ Webhook
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, threaded=False)
DEVELOPER_ID = int(os.environ.get('DEVELOPER_ID'))
EESSMT = os.environ.get('EESSMT')
ESM7AT = os.environ.get('ESM7AT')

# 💡 [التعديل 2: استبدال VIOTP_API_KEY بـ SMMKINGS_API_KEY]
SMMKINGS_API_KEY = os.environ.get('SMMKINGS_API_KEY') 
SMSMAN_API_KEY = os.environ.get('SMSMAN_API_KEY')
TIGER_SMS_API_KEY = os.environ.get('TIGER_SMS_API_KEY')

# Create API client objects
# 💡 [التعديل 3: تكوين عميل SMMKings واستبدال viotp_client]
smmkings_client = SMMKingsAPI(SMMKINGS_API_KEY)
tiger_sms_client = TigerSMSAPI(TIGER_SMS_API_KEY)

# 🟢 التعديل: تم إضافة set_smsman_status إلى القاموس
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

# 💡 [التعديل 4: تمرير smmkings_client بدلاً من viotp_client إلى Handlers]
setup_user_handlers(bot, DEVELOPER_ID, ESM7AT, EESSMT, smmkings_client, smsman_api, tiger_sms_client)
setup_admin_handlers(bot, DEVELOPER_ID, smmkings_client, smsman_api, tiger_sms_client)

@app.route(f'/{TELEGRAM_BOT_TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        
        try:
            update = telebot.types.Update.de_json(json_string)
            # 💡 التعديل 2: إضافة معالجة الأخطاء حول عملية معالجة التحديثات
            bot.process_new_updates([update])
        except Exception as e:
            # تسجيل الخطأ لظهوره في سجلات الاستضافة
            logging.error(f"❌ FATAL HANDLER EXCEPTION: {type(e).__name__} - {e}")
            # يمكنك إرسال تنبيه للمطور هنا باستخدام bot.send_message
        
        # يجب أن يستجيب الـ Webhook دائمًا بـ 200 OK لتليجرام، بغض النظر عن الأخطاء الداخلية.
        return '!', 200
    else:
        return 'Hello, World!', 200

if __name__ == '__main__':
    # يُفضل حذف الـ webhook القديم قبل تعيين الجديد
    try:
        bot.delete_webhook() 
    except Exception as e:
        logging.warning(f"Failed to delete old webhook: {e}")

    # تعيين الـ Webhook الجديد
    bot.set_webhook(url=WEBHOOK_URL + TELEGRAM_BOT_TOKEN, allowed_updates=['message', 'callback_query'])
    
    # تشغيل تطبيق Flask
    logging.info(f"Flask app starting on port {PORT}...")
    app.run(host='0.0.0.0', port=PORT)
