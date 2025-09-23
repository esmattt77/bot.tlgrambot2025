import telebot
from telebot import types
import json
import time
import logging
import requests
import os  # <<=== هذا السطر الجديد

# Set your API token and other information
API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
DEVELOPER_ID = os.environ.get('DEVELOPER_ID')
EESSMT = os.environ.get('EESSMT')
ESM7AT = os.environ.get('ESM7AT')

# Service API keys and URLs
VIOTP_API_KEY = os.environ.get('VIOTP_API_KEY')
SMSMAN_API_KEY = os.environ.get('SMSMAN_API_KEY')
TIGERSMS_API_KEY = os.environ.get('TIGER_SMS_API_KEY')

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- API Clients (for external services) ---
class ViOtpClient:
    def __init__(self, api_key):
        self.base_url = "https://api.viotps.com/api/"
        self.api_key = api_key

    def buy_number(self, app_id):
        url = f"{self.base_url}buy-number"
        params = {"api_key": self.api_key, "service_id": app_id}
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"ViOTP API error: {e}")
            return {"success": False}

    def get_otp(self, request_id):
        url = f"{self.base_url}get-otp"
        params = {"api_key": self.api_key, "request_id": request_id}
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"ViOTP API error: {e}")
            return {"success": False}
    
    def cancel_request(self, request_id):
        url = f"{self.base_url}cancel-request"
        params = {"api_key": self.api_key, "request_id": request_id}
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"ViOTP API error: {e}")
            return {"success": False}

class SMSManAPI:
    def __init__(self, api_key):
        self.base_url = "http://api.sms-man.com/stubs/handler_api.php"
        self.api_key = api_key

    def request_smsman_number(self, app_id, country_code):
        url = self.base_url
        params = {
            "api_key": self.api_key,
            "action": "getNumber",
            "service": app_id,
            "country": country_code
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            # Special handling for SMSMan response
            if "ACCESS_NUMBER" in response.text:
                parts = response.text.split(':')
                return {'request_id': parts[1], 'Phone': parts[2]}
            else:
                return {"success": False}
        except requests.exceptions.RequestException as e:
            logging.error(f"SMSMan API error: {e}")
            return {"success": False}

    def get_smsman_code(self, request_id):
        url = self.base_url
        params = {
            "api_key": self.api_key,
            "action": "getStatus",
            "id": request_id
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            if "STATUS_OK" in response.text:
                return {"success": True, "code": response.text.split(':')[1]}
            elif "STATUS_WAIT_CODE" in response.text:
                return {"success": False, "code": None}
            else:
                return {"success": False, "code": None}
        except requests.exceptions.RequestException as e:
            logging.error(f"SMSMan API error: {e}")
            return {"success": False, "code": None}

    def cancel_smsman_request(self, request_id):
        url = self.base_url
        params = {
            "api_key": self.api_key,
            "action": "setStatus",
            "id": request_id,
            "status": "8"  # Cancel status
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            if "STATUS_CANCEL" in response.text:
                return {"success": True}
            else:
                return {"success": False}
        except requests.exceptions.RequestException as e:
            logging.error(f"SMSMan API error: {e}")
            return {"success": False}

class TigerSmsClient:
    def __init__(self, api_key):
        self.base_url = "https://tigersms.top/api/"
        self.api_key = api_key

    def get_number(self, app_id, country_code):
        url = f"{self.base_url}getNumber"
        params = {
            "token": self.api_key,
            "service": app_id,
            "country": country_code
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"TigerSMS API error: {e}")
            return {"success": False}

    def get_code(self, request_id):
        url = f"{self.base_url}getCode"
        params = {
            "token": self.api_key,
            "request_id": request_id
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"TigerSMS API error: {e}")
            return {"success": False}

    def cancel_request(self, request_id):
        url = f"{self.base_url}cancelNumber"
        params = {
            "token": self.api_key,
            "request_id": request_id
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"TigerSMS API error: {e}")
            return {"success": False}

# --- Data Management Functions ---
def load_data():
    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Ensure all keys exist
            if 'sh_services' not in data:
                data['sh_services'] = {}
            if 'countries' not in data:
                data['countries'] = {}
            if 'states' not in data:
                data['states'] = {}
            if 'active_requests' not in data:
                data['active_requests'] = {}
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        # Create a new data structure if the file doesn't exist or is corrupted
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
    user_id_str = str(user_id)
    if user_id_str not in users_data:
        users_data[user_id_str] = {
            'id': user_id,
            'first_name': first_name,
            'username': username,
            'balance': 0,
            'join_date': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
            'purchases': []
        }
    else:
        # Update username and first name in case they change
        users_data[user_id_str]['first_name'] = first_name
        users_data[user_id_str]['username'] = username
    save_users(users_data)

# --- Bot Initialization ---
bot = telebot.TeleBot(API_TOKEN)
viotp_client = ViOtpClient(VIOTP_API_KEY)
smsman_api = SMSManAPI(SMSMAN_API_KEY)
tiger_sms_client = TigerSmsClient(TIGERSMS_API_KEY)

# --- Bot Handlers ---

@bot.message_handler(commands=['start', 'balance'])
@bot.message_handler(func=lambda message: message.text in ['/start', 'start/', 'بدء/', '/balance', 'رصيدي'])
def handle_user_commands(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    username = message.from_user.username
    
    register_user(user_id, first_name, username)

    if message.text in ['/start', 'start/', 'بدء/']:
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton('☎️︙شراء ارقـام وهمية', callback_data='Buynum'))
        markup.row(types.InlineKeyboardButton('💰︙شحن رصيدك', callback_data='Payment'), types.InlineKeyboardButton('👤︙قسم الرشق', callback_data='sh'))
        markup.row(types.InlineKeyboardButton('🅿️︙كشف الحساب', callback_data='Record'), types.InlineKeyboardButton('🛍︙قسم العروض', callback_data='Wo'))
        markup.row(types.InlineKeyboardButton('☑️︙قسم العشوائي', callback_data='worldwide'), types.InlineKeyboardButton('👑︙قسم الملكي', callback_data='saavmotamy'))
        markup.row(types.InlineKeyboardButton('💰︙ربح روبل مجاني 🤑', callback_data='assignment'))
        markup.row(types.InlineKeyboardButton('💳︙متجر الكروت', callback_data='readycard-10'), types.InlineKeyboardButton('🔰︙الارقام الجاهزة', callback_data='ready'))
        markup.row(types.InlineKeyboardButton('👨‍💻︙قسم الوكلاء', callback_data='gents'), types.InlineKeyboardButton('⚙️︙إعدادات البوت', callback_data='MyAccount'))
        markup.row(types.InlineKeyboardButton('📮︙تواصل الدعم أونلاين', callback_data='super'))
        bot.send_message(chat_id, f"☑️ *⁞ قناة البوت الرسمية: @{EESSMT}\n🎬︙قم بالتحكم بالبوت الأن عبر الضعط على الأزرار.*", parse_mode='Markdown', reply_markup=markup)

    elif message.text in ['/balance', 'رصيدي']:
        users_data = load_users()
        balance = users_data.get(str(user_id), {}).get('balance', 0)
        bot.send_message(chat_id, f"💰 رصيدك الحالي هو: *{balance}* روبل.", parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.from_user.id != DEVELOPER_ID)
def handle_user_callbacks(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    message_id = call.message.message_id
    data = call.data
    
    data_file = load_data()
    users_data = load_users()
    
    if data == 'Payment':
        bot.send_message(chat_id, f"💰 *لشحن رصيدك، يرجى التواصل مع المشرف عبر هذا الحساب: @{ESM7AT}.*", parse_mode='Markdown')
        return
    elif data == 'sh':
        markup = types.InlineKeyboardMarkup()
        sh_services = data_file.get('sh_services', {})
        if not sh_services:
            bot.send_message(chat_id, "❌ لا توجد خدمات رشق متاحة حاليًا.")
            return
        for name, price in sh_services.items():
            markup.add(types.InlineKeyboardButton(f"⭐ {name} ({price} روبل)", callback_data=f'buy_sh_{name}'))
        markup.add(types.InlineKeyboardButton('- رجوع.', callback_data='back'))
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="🚀 اختر خدمة الرشق:", reply_markup=markup)
        return

    elif data.startswith('buy_sh_'):
        service_name = data.split('_', 2)[-1]
        service_price = data_file.get('sh_services', {}).get(service_name)
        user_balance = users_data.get(str(user_id), {}).get('balance', 0)
        
        if user_balance < service_price:
            bot.send_message(chat_id, f"❌ *عذرًا، رصيدك غير كافٍ لإتمام هذه العملية.*\n\n*الرصيد المطلوب:* {service_price} روبل.\n*رصيدك الحالي:* {user_balance} روبل.\n\n*يمكنك شحن رصيدك عبر زر شحن الرصيد.*", parse_mode='Markdown')
            return

        users_data[str(user_id)]['balance'] -= service_price
        save_users(users_data)
        
        bot.send_message(chat_id, f"✅ تم شراء خدمة `{service_name}` بنجاح! سيتم معالجة طلبك قريباً.")
        return

    elif data == 'Wo':
        bot.send_message(chat_id, "🛍 *لا توجد عروض خاصة متاحة حالياً. تابعنا للحصول على التحديثات!*", parse_mode='Markdown')
        return
    elif data == 'worldwide':
        bot.send_message(chat_id, "☑️ *قسم الأرقام العشوائية قيد الإعداد. يرجى العودة لاحقاً.*", parse_mode='Markdown')
        return
    elif data == 'saavmotamy':
        bot.send_message(chat_id, "👑 *خدمة الأرقام الملكية قادمة قريباً، تابعنا لمعرفة المزيد.*", parse_mode='Markdown')
        return
    elif data == 'assignment':
        bot.send_message(chat_id, "💰 *يمكنك ربح روبل مجانية عن طريق إكمال بعض المهام. تابع الإعلانات لمعرفة التفاصيل.*", parse_mode='Markdown')
        return
    elif data == 'readycard-10':
        bot.send_message(chat_id, "💳 *متجر الكروت متوفر الآن! تواصل مع الدعم لشراء كرت.*", parse_mode='Markdown')
        return
    elif data == 'ready':
        bot.send_message(chat_id, "🔰 *لا توجد أرقام جاهزة متاحة حالياً.*", parse_mode='Markdown')
        return
    elif data == 'gents':
        bot.send_message(chat_id, "👨‍💻 *نظام الوكلاء قيد المراجعة. إذا كنت مهتماً، يمكنك التواصل مع المشرف.*", parse_mode='Markdown')
        return
    elif data == 'MyAccount':
        user_info = users_data.get(str(user_id), {})
        message_text = (
            f"⚙️ **إعدادات حسابك:**\n"
            f"**الآيدي:** `{user_info.get('id', 'غير متوفر')}`\n"
            f"**الاسم:** `{user_info.get('first_name', 'غير متوفر')}`\n"
            f"**اسم المستخدم:** `@{user_info.get('username', 'غير متوفر')}`\n"
            f"**الرصيد:** `{user_info.get('balance', 0)}` روبل\n"
        )
        bot.send_message(chat_id, message_text, parse_mode='Markdown')
        return
    elif data == 'super':
        bot.send_message(chat_id, f"📮 *للتواصل مع الدعم الفني، يرجى إرسال رسالتك إلى هذا الحساب: @{ESM7AT}.*")
        return

    elif data == 'Buynum':
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton('سيرفر 1', callback_data='service_viotp'))
        markup.row(types.InlineKeyboardButton('سيرفر 2', callback_data='service_smsman'))
        markup.row(types.InlineKeyboardButton('سيرفر 3', callback_data='service_tigersms'))
        markup.row(types.InlineKeyboardButton('- رجوع.', callback_data='back'))
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="📞 *اختر الخدمة التي تريد الشراء منها:*", parse_mode='Markdown', reply_markup=markup)
    
    elif data == 'Record':
        user_info = users_data.get(str(user_id), {})
        balance = user_info.get('balance', 0)
        purchases = user_info.get('purchases', [])
        
        message_text = f"💰 رصيدك الحالي هو: *{balance}* روبل.\n\n"
        if purchases:
            message_text += "📝 **سجل مشترياتك الأخيرة:**\n"
            for i, p in enumerate(purchases[-5:]):
                phone_number = p.get('phone_number', 'غير متوفر')
                price = p.get('price', 0)
                timestamp = p.get('timestamp', 'غير متوفر')
                message_text += f"*{i+1}. رقم {phone_number} بسعر {price} روبل في {timestamp}*\n"
        else:
            message_text += "❌ لا يوجد لديك مشتريات سابقة."
        
        bot.send_message(chat_id, message_text, parse_mode='Markdown')

    elif data == 'back':
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton('☎️︙شراء ارقـام وهمية', callback_data='Buynum'))
        markup.row(types.InlineKeyboardButton('💰︙شحن رصيدك', callback_data='Payment'), types.InlineKeyboardButton('👤︙قسم الرشق', callback_data='sh'))
        markup.row(types.InlineKeyboardButton('🅿️︙كشف الحساب', callback_data='Record'), types.InlineKeyboardButton('🛍︙قسم العروض', callback_data='Wo'))
        markup.row(types.InlineKeyboardButton('☑️︙قسم العشوائي', callback_data='worldwide'), types.InlineKeyboardButton('👑︙قسم الملكي', callback_data='saavmotamy'))
        markup.row(types.InlineKeyboardButton('💰︙ربح روبل مجاني 🤑', callback_data='assignment'))
        markup.row(types.InlineKeyboardButton('💳︙متجر الكروت', callback_data='readycard-10'), types.InlineKeyboardButton('🔰︙الارقام الجاهزة', callback_data='ready'))
        markup.row(types.InlineKeyboardButton('👨‍💻︙قسم الوكلاء', callback_data='gents'), types.InlineKeyboardButton('⚙️︙إعدادات البوت', callback_data='MyAccount'))
        markup.row(types.InlineKeyboardButton('📮︙تواصل الدعم أونلاين', callback_data='super'))
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"☑️ *⁞ قناة البوت الرسمية: @{EESSMT}\n🎬︙قم بالتحكم بالبوت الأن عبر الضعط على الأزرار.*", parse_mode='Markdown', reply_markup=markup)
    
    elif data.startswith('service_'):
        service = data.split('_')[1]
        markup = types.InlineKeyboardMarkup()
        if service == 'viotp':
            markup.row(types.InlineKeyboardButton('⁞ واتسأب 💬', callback_data=f'show_countries_{service}_2'))
            markup.row(types.InlineKeyboardButton('⁞ تيليجرام 📢', callback_data=f'show_countries_{service}_3'))
            markup.row(types.InlineKeyboardButton('⁞ فيسبوك 🏆', callback_data=f'show_countries_{service}_4'))
            markup.row(types.InlineKeyboardButton('⁞ إنستقرام 🎥', callback_data=f'show_countries_{service}_5'))
            markup.row(types.InlineKeyboardButton('⁞ تويتر 🚀', callback_data=f'show_countries_{service}_6'))
            markup.row(types.InlineKeyboardButton('⁞ تيكتوك 🎬', callback_data=f"show_countries_{service}_7"))
            markup.row(types.InlineKeyboardButton('⁞ قوقل 🌐', callback_data=f'show_countries_{service}_8'))
            markup.row(types.InlineKeyboardButton('⁞ إيمو 🐦', callback_data=f'show_countries_{service}_9'))
            markup.row(types.InlineKeyboardButton('⁞ سناب 🐬', callback_data=f'show_countries_{service}_11'))
            markup.row(types.InlineKeyboardButton('⁞ OK 🌟', callback_data=f'show_countries_{service}_12'))
            markup.row(types.InlineKeyboardButton('⁞ Viber 📲', callback_data=f'show_countries_{service}_16'))
            markup.row(types.InlineKeyboardButton('⁞ حراج 🛍', callback_data=f'show_countries_{service}_13'))
            markup.row(types.InlineKeyboardButton('⁞ السيرفر العام ☑️', callback_data=f'show_countries_{service}_14'))
        elif service == 'smsman':
            markup.row(types.InlineKeyboardButton('⁞ واتسأب 💬', callback_data=f'show_countries_{service}_2'))
            markup.row(types.InlineKeyboardButton('⁞ تيليجرام 📢', callback_data=f'show_countries_{service}_3'))
            markup.row(types.InlineKeyboardButton('⁞ فيسبوك 🏆', callback_data=f'show_countries_{service}_4'))
            markup.row(types.InlineKeyboardButton('⁞ إنستقرام 🎥', callback_data=f'show_countries_{service}_5'))
            markup.row(types.InlineKeyboardButton('⁞ تويتر 🚀', callback_data=f'show_countries_{service}_6'))
            markup.row(types.InlineKeyboardButton('⁞ تيكتوك 🎬', callback_data=f"show_countries_{service}_7"))
            markup.row(types.InlineKeyboardButton('⁞ قوقل 🌐', callback_data=f'show_countries_{service}_8'))
            markup.row(types.InlineKeyboardButton('⁞ إيمو 🐦', callback_data=f'show_countries_{service}_9'))
            markup.row(types.InlineKeyboardButton('⁞ سناب 🐬', callback_data=f'show_countries_{service}_11'))
            markup.row(types.InlineKeyboardButton('⁞ OK 🌟', callback_data=f'show_countries_{service}_12'))
            markup.row(types.InlineKeyboardButton('⁞ Viber 📲', callback_data=f'show_countries_{service}_16'))
            markup.row(types.InlineKeyboardButton('⁞ حراج 🛍', callback_data=f'show_countries_{service}_13'))
            markup.row(types.InlineKeyboardButton('⁞ السيرفر العام ☑️', callback_data=f'show_countries_{service}_14'))
        elif service == 'tigersms':
            markup.row(types.InlineKeyboardButton('⁞ واتسأب 💬', callback_data=f'show_countries_{service}_wa'))
            markup.row(types.InlineKeyboardButton('⁞ تيليجرام 📢', callback_data=f'show_countries_{service}_tg'))
            markup.row(types.InlineKeyboardButton('⁞ فيسبوك 🏆', callback_data=f'show_countries_{service}_fb'))
            markup.row(types.InlineKeyboardButton('⁞ إنستقرام 🎥', callback_data=f'show_countries_{service}_ig'))
            markup.row(types.InlineKeyboardButton('⁞ تويتر 🚀', callback_data=f'show_countries_{service}_tw'))
            markup.row(types.InlineKeyboardButton('⁞ تيكتوك 🎬', callback_data=f"show_countries_{service}_tt"))
            markup.row(types.InlineKeyboardButton('⁞ قوقل 🌐', callback_data=f'show_countries_{service}_go'))
            markup.row(types.InlineKeyboardButton('⁞ سناب 🐬', callback_data=f'show_countries_{service}_sn'))
            markup.row(types.InlineKeyboardButton('⁞ ديسكورد 🎮', callback_data=f'show_countries_{service}_ds'))
            markup.row(types.InlineKeyboardButton('⁞ تيندر ❤️', callback_data=f'show_countries_{service}_td'))
            markup.row(types.InlineKeyboardButton('⁞ أوبر 🚕', callback_data=f'show_countries_{service}_ub'))
            markup.row(types.InlineKeyboardButton('⁞ أوكي 🌟', callback_data=f'show_countries_{service}_ok'))
            markup.row(types.InlineKeyboardButton('⁞ لاين 📲', callback_data=f'show_countries_{service}_li'))
            markup.row(types.InlineKeyboardButton('⁞ أمازون 🛒', callback_data=f'show_countries_{service}_am'))
        
        markup.row(types.InlineKeyboardButton('- رجوع.', callback_data='Buynum'))
        server_name = 'سيرفر 1' if service == 'viotp' else ('سيرفر 2' if service == 'smsman' else 'سيرفر 3')
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"☑️ *اختر التطبيق* الذي تريد *شراء رقم وهمي* له من خدمة **{server_name}**.", parse_mode='Markdown', reply_markup=markup)

    elif data.startswith('show_countries_'):
        parts = data.split('_')
        service, app_id = parts[2], parts[3]
        page = int(parts[5]) if len(parts) > 5 else 1
        
        local_countries = load_data().get('countries', {}).get(service, {}).get(app_id, {})
        
        if not local_countries:
            bot.send_message(chat_id, '❌ لا توجد دول متاحة لهذا التطبيق حاليًا.')
            return

        items_per_page = 10
        country_items = list(local_countries.items())
        total_pages = (len(country_items) + items_per_page - 1) // items_per_page
        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page
        current_countries = country_items[start_index:end_index]
        
        markup = types.InlineKeyboardMarkup()
        for code, info in current_countries:
            display_price = info.get('price', 'غير متاح')
            markup.row(types.InlineKeyboardButton(f"{info['name']} ({display_price} روبل)", callback_data=f'buy_{service}_{app_id}_{code}'))
        
        nav_buttons = []
        if page > 1:
            nav_buttons.append(types.InlineKeyboardButton('◀️ السابق', callback_data=f'show_countries_{service}_{app_id}_page_{page - 1}'))
        if page < total_pages:
            nav_buttons.append(types.InlineKeyboardButton('التالي ▶️', callback_data=f'show_countries_{service}_{app_id}_page_{page + 1}'))
        if nav_buttons:
            markup.row(*nav_buttons)
        
        markup.row(types.InlineKeyboardButton('رجوع', callback_data='Buynum'))
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"اختر الدولة التي تريدها: (صفحة {page}/{total_pages})", reply_markup=markup)

    elif data.startswith('buy_'):
        parts = data.split('_')
        service, app_id, country_code = parts[1], parts[2], parts[3]
        
        data_file = load_data()
        users_data = load_users()
        country_info = data_file.get('countries', {}).get(service, {}).get(app_id, {}).get(country_code, {})
        price = country_info.get('price', 0)
        
        user_balance = users_data.get(str(user_id), {}).get('balance', 0)
        
        if user_balance < price:
            bot.send_message(chat_id, f"❌ *عذرًا، رصيدك غير كافٍ لإتمام هذه العملية.*\n\n*الرصيد المطلوب:* {price} روبل.\n*رصيدك الحالي:* {user_balance} روبل.\n\n*يمكنك شحن رصيدك عبر زر شحن الرصيد.*", parse_mode='Markdown')
            return

        result = None
        if service == 'viotp':
            result = viotp_client.buy_number(app_id)
        elif service == 'smsman':
            result = smsman_api.request_smsman_number(app_id, country_code)
            if result and 'request_id' in result:
                result['success'] = True
                result['id'] = result['request_id']
                result['number'] = result['Phone']
        elif service == 'tigersms':
            result = tiger_sms_client.get_number(app_id, country_code)

        logging.info(f"Response from {service}: {result}")

        if result and result.get('success'):
            request_id = result.get('id')
            phone_number = result.get('number', result.get('Phone', 'غير متوفر'))
            
            users_data[str(user_id)]['balance'] -= price
            remaining_balance = users_data[str(user_id)]['balance']
            
            users_data[str(user_id)]['purchases'].append({
                'request_id': request_id,
                'phone_number': phone_number,
                'service': service,
                'price': price,
                'status': 'pending',
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
            })
            
            save_users(users_data)
            
            active_requests = data_file.get('active_requests', {})
            active_requests[request_id] = {
                'user_id': user_id,
                'phone_number': phone_number,
                'status': 'pending',
                'service': service,
                'price': price,
                'message_id': message_id
            }
            data_file['active_requests'] = active_requests
            save_data(data_file)
            
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('✅ الحصول على الكود', callback_data=f'get_otp_{service}_{request_id}'))
            markup.row(types.InlineKeyboardButton('❌ إلغاء الطلب', callback_data=f'cancel_{service}_{request_id}'))

            service_name = 'سيرفر 1' if service == 'viotp' else ('سيرفر 2' if service == 'smsman' else 'سيرفر 3')
            
            app_map = {
                '2': 'واتساب', '3': 'تيليجرام', '4': 'فيسبوك', '5': 'إنستقرام',
                '6': 'تويتر', '7': 'تيكتوك', '8': 'قوقل', '9': 'إيمو',
                '11': 'سناب', '12': 'OK', '16': 'Viber', '13': 'حراج',
                '14': 'السيرفر العام', 'wa': 'واتساب', 'tg': 'تيليجرام',
                'fb': 'فيسبوك', 'ig': 'إنستقرام', 'tw': 'تويتر',
                'tt': 'تيكتوك', 'go': 'قوقل', 'sn': 'سناب', 'ds': 'ديسكورد',
                'td': 'تيندر', 'ub': 'أوبر', 'ok': 'أوكي', 'li': 'لاين',
                'am': 'أمازون'
            }
            app_name = app_map.get(app_id, 'غير معروف')
            country_name = country_info.get('name', 'غير معروف')
            
            message_text = (
                f"**☎️ - الرقم:** `{phone_number}`\n"
                f"**🧿 - التطبيق:** `{app_name}`\n"
                f"**📥 - الدولة:** `{country_name}`\n"
                f"**🔥 - الأيدي:** `{user_id}`\n"
                f"**💸 - السعر:** `Ꝑ{price}`\n"
                f"**🤖 - الرصيد المتبقي:** `{remaining_balance}`\n"
                f"**🔄 - معرف المشتري:** `@{users_data[str(user_id)].get('username', 'غير متوفر')}`\n"
                f"**🎦 - الموقع:** `soper.com`"
            )

            bot.send_message(chat_id, message_text, parse_mode='Markdown', reply_markup=markup)
        else:
            bot.send_message(chat_id, "❌ فشل طلب الرقم. قد يكون غير متوفر أو أن رصيدك في الخدمة غير كافٍ.")
            
    elif data.startswith('get_otp_'):
        parts = data.split('_')
        service, request_id = parts[2], parts[3]
        
        result = None
        if service == 'viotp':
            result = viotp_client.get_otp(request_id)
        elif service == 'smsman':
            result = smsman_api.get_smsman_code(request_id)
        elif service == 'tigersms':
            result = tiger_sms_client.get_code(request_id)

        if result and result.get('success') and result.get('code'):
            otp_code = result.get('code')
            data_file = load_data()
            users_data = load_users()
            active_requests = data_file.get('active_requests', {})
            
            if request_id in active_requests:
                phone_number = active_requests[request_id]['phone_number']
                del active_requests[request_id]
                data_file['active_requests'] = active_requests
                save_data(data_file)

                for purchase in users_data.get(str(user_id), {}).get('purchases', []):
                    if purchase.get('request_id') == request_id:
                        purchase['status'] = 'completed'
                        break
                save_users(users_data)

                bot.send_message(chat_id, f"✅ *رمزك هو: {otp_code}*\n\nالرقم: *{phone_number}*", parse_mode='Markdown')
            else:
                bot.send_message(chat_id, "❌ حدث خطأ، لم يتم العثور على الطلب.")
        else:
            bot.send_message(chat_id, "❌ لا يوجد كود حتى الآن. حاول مجدداً.", reply_markup=call.message.reply_markup)
            
    elif data.startswith('cancel_'):
        parts = data.split('_')
        service, request_id = parts[1], parts[2]
        
        result = None
        if service == 'viotp':
            result = viotp_client.cancel_request(request_id)
        elif service == 'smsman':
            result = smsman_api.cancel_smsman_request(request_id)
        elif service == 'tigersms':
            result = tiger_sms_client.cancel_request(request_id)
        
        if result and result.get('success'):
            data_file = load_data()
            users_data = load_users()
            active_requests = data_file.get('active_requests', {})
            
            if request_id in active_requests:
                request_info = active_requests[request_id]
                user_id_from_request = request_info['user_id']
                price_to_restore = request_info['price']
                
                user_id_str = str(user_id_from_request)
                if user_id_str in users_data:
                    users_data[user_id_str]['balance'] += price_to_restore
                    
                    users_data[user_id_str]['purchases'] = [
                        p for p in users_data[user_id_str]['purchases'] 
                        if p.get('request_id') != request_id
                    ]
                    
                    save_users(users_data)
                
                del active_requests[request_id]
                data_file['active_requests'] = active_requests
                save_data(data_file)
            bot.send_message(chat_id, "✅ تم إلغاء الطلب بنجاح. سيتم استرجاع رصيدك.")
        else:
            bot.send_message(chat_id, "❌ فشل إلغاء الطلب. يرجى المحاولة مرة أخرى أو التواصل مع الدعم.")

# --- Start the bot ---
if __name__ == '__main__':
    try:
        logging.info("Starting bot polling...")
        bot.polling(none_stop=True)
    except Exception as e:
        logging.error(f"Bot failed to start: {e}")
