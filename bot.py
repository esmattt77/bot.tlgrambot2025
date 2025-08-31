# bot.py
import time
import telebot
from telebot import types
import json
import requests
import os

# قراءة توكن البوت من المتغيرات البيئية
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TELEGRAM_BOT_TOKEN:
    print("Error: TELEGRAM_BOT_TOKEN environment variable not set.")
    exit()

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# --- Helper Functions ---
def load_data():
    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {'users': {}, 'states': {}, 'countries': {}, 'active_requests': {}}

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

# --- Message Handlers ---
@bot.message_handler(commands=['start', 'admin', 'balance'])
def handle_commands(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    username = message.from_user.username

    register_user(user_id, first_name, username)

    data_file = load_data()
    state = data_file.get('states', {}).get(str(user_id))

    if user_id == DEVELOPER_ID:
        if message.text in ['/start', '/admin']:
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('إحصائيات البوت 📊', callback_data='bot_stats'), types.InlineKeyboardButton('إدارة المستخدمين 👥', callback_data='manage_users'))
            markup.row(types.InlineKeyboardButton('إضافة رصيد 💰', callback_data='add_balance'), types.InlineKeyboardButton('خصم رصيد 💸', callback_data='deduct_balance'))
            markup.row(types.InlineKeyboardButton('إضافة دولة 🌐', callback_data='add_country'), types.InlineKeyboardButton('حذف دولة ❌', callback_data='delete_country'))
            markup.row(types.InlineKeyboardButton('عرض الطلبات النشطة 📞', callback_data='view_active_requests'), types.InlineKeyboardButton('إلغاء جميع الطلبات 🚫', callback_data='cancel_all_requests'))
            markup.row(types.InlineKeyboardButton('إرسال رسالة جماعية 📣', callback_data='broadcast_message'), types.InlineKeyboardButton('الكشف عن أرصدة المواقع 💳', callback_data='show_api_balance_menu'))
            bot.send_message(chat_id, "أهلاً بك في لوحة تحكم المشرف!", reply_markup=markup)
        
        elif state and state.get('step') == 'waiting_for_add_coin_id':
            target_id = message.text
            data_file['states'][str(user_id)]['target_id'] = target_id
            data_file['states'][str(user_id)]['step'] = 'waiting_for_add_coin_amount'
            save_data(data_file)
            bot.send_message(chat_id, "تم حفظ الآيدي. الآن أرسل **المبلغ** الذي تريد إضافته للمستخدم.")
        
        elif state and state.get('step') == 'waiting_for_add_coin_amount':
            amount = int(message.text)
            target_id = state.get('target_id')
            users_data = load_users()
            if str(target_id) not in users_data:
                users_data[str(target_id)] = {'balance': 0}
            users_data[str(target_id)]['balance'] += amount
            save_users(users_data)
            del data_file['states'][str(user_id)]
            save_data(data_file)
            bot.send_message(chat_id, f"✅ تم إضافة {amount} عملة إلى المستخدم ذو الآيدي: {target_id}")

        elif state and state.get('step') == 'waiting_for_deduct_coin_id':
            target_id = message.text
            data_file['states'][str(user_id)]['target_id'] = target_id
            data_file['states'][str(user_id)]['step'] = 'waiting_for_deduct_coin_amount'
            save_data(data_file)
            bot.send_message(chat_id, "تم حفظ الآيدي. الآن أرسل **المبلغ** الذي تريد خصمه من المستخدم.")
        
        elif state and state.get('step') == 'waiting_for_deduct_coin_amount':
            amount = int(message.text)
            target_id = state.get('target_id')
            users_data = load_users()
            if str(target_id) not in users_data:
                users_data[str(target_id)] = {'balance': 0}
            users_data[str(target_id)]['balance'] -= amount
            save_users(users_data)
            del data_file['states'][str(user_id)]
            save_data(data_file)
            bot.send_message(chat_id, f"✅ تم خصم {amount} عملة من المستخدم ذو الآيدي: {target_id}")

        elif state and state.get('step') == 'waiting_for_broadcast_message':
            users_data = load_users()
            for uid in users_data.keys():
                bot.send_message(uid, message.text)
            del data_file['states'][str(user_id)]
            save_data(data_file)
            bot.send_message(chat_id, "📣 اكتمل البث بنجاح!")

        elif state and state.get('step') == 'waiting_for_admin_price':
            custom_price = int(message.text)
            country_name = state.get('country_name')
            country_code = state.get('country_code')
            service = state.get('service')
            app_id = state.get('app_id')

            if service not in data_file['countries']:
                data_file['countries'][service] = {}
            if str(app_id) not in data_file['countries'][service]:
                data_file['countries'][service][str(app_id)] = {}
            
            data_file['countries'][service][str(app_id)][country_code] = {'name': country_name, 'price': custom_price}
            
            del data_file['states'][str(user_id)]
            save_data(data_file)
            bot.send_message(chat_id, f"✅ تم إضافة الدولة **{country_name}** بالرمز **{country_code}** والسعر **{custom_price}** بنجاح لخدمة **{service}**!", parse_mode='Markdown')

    else:
        if message.text == '/start':
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
            bot.send_message(chat_id, f"💰 رصيدك الحالي هو: *{balance}* عملة.", parse_mode='Markdown')


# --- Callback Query Handler ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    message_id = call.message.message_id
    data = call.data
    
    data_file = load_data()
    users_data = load_users()

    # Admin actions
    if user_id == DEVELOPER_ID:
        if data == 'add_balance':
            data_file['states'][str(user_id)] = {'step': 'waiting_for_add_coin_id'}
            save_data(data_file)
            bot.send_message(chat_id, '➕ أرسل **آيدي المستخدم** الذي تريد إضافة رصيد له.')
        elif data == 'deduct_balance':
            data_file['states'][str(user_id)] = {'step': 'waiting_for_deduct_coin_id'}
            save_data(data_file)
            bot.send_message(chat_id, '➖ أرسل **آيدي المستخدم** الذي تريد خصم رصيد منه.')
        elif data == 'add_country':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('ViOTP', callback_data='add_country_service_viotp'))
            markup.row(types.InlineKeyboardButton('SMS.man', callback_data='add_country_service_smsman'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text='🌐 اختر الخدمة لإضافة دولة:', reply_markup=markup)
        elif data == 'bot_stats':
            total_users = len(users_data)
            message = f"📊 إحصائيات البوت:\nعدد المستخدمين: *{total_users}*\n"
            bot.send_message(chat_id, message, parse_mode='Markdown')
        elif data == 'broadcast_message':
            data_file['states'][str(user_id)] = {'step': 'waiting_for_broadcast_message'}
            save_data(data_file)
            bot.send_message(chat_id, '📣 أرسل رسالتك للبث.')
        elif data == 'show_api_balance_menu':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('كشف رصيد ViOTP', callback_data='get_viotp_balance'))
            markup.row(types.InlineKeyboardButton('كشف رصيد SMS.man', callback_data='get_smsman_balance'))
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='admin_main_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="💰 اختر الموقع الذي تريد كشف رصيده:", reply_markup=markup)
        elif data == 'get_viotp_balance':
            viotp_balance = get_viotp_balance()
            message = f"💰 رصيد ViOTP الحالي:\n• ViOTP: *{viotp_balance}* عملة." if viotp_balance is not False else "❌ فشل الاتصال."
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='show_api_balance_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message, parse_mode='Markdown', reply_markup=markup)
        elif data == 'get_smsman_balance':
            smsman_balance = get_smsman_balance()
            message = f"💰 رصيد SMS.man الحالي:\n• SMS.man: *{smsman_balance}* عملة." if smsman_balance is not False else "❌ فشل الاتصال."
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='show_api_balance_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message, parse_mode='Markdown', reply_markup=markup)
        
        elif data.startswith('add_country_service_'):
            service = data.split('_')[3]
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('واتساب 💬', callback_data=f"add_country_app_{service}_2"))
            markup.row(types.InlineKeyboardButton('تليجرام 📢', callback_data=f"add_country_app_{service}_3"))
            markup.row(types.InlineKeyboardButton('فيسبوك 🏆', callback_data=f"add_country_app_{service}_4"))
            markup.row(types.InlineKeyboardButton('إنستقرام 🎥', callback_data=f"add_country_app_{service}_5"))
            markup.row(types.InlineKeyboardButton('تويتر 🚀', callback_data=f"add_country_app_{service}_6"))
            markup.row(types.InlineKeyboardButton('تيكتوك 🎬', callback_data=f"add_country_app_{service}_7"))
            markup.row(types.InlineKeyboardButton('قوقل 🌐', callback_data=f"add_country_app_{service}_8"))
            markup.row(types.InlineKeyboardButton('إيمو 🐦', callback_data=f"add_country_app_{service}_9"))
            markup.row(types.InlineKeyboardButton('سناب 🐬', callback_data=f"add_country_app_{service}_11"))
            markup.row(types.InlineKeyboardButton('حراج 🛍', callback_data=f"add_country_app_{service}_13"))
            markup.row(types.InlineKeyboardButton('السيرفر العام ☑️', callback_data=f"add_country_app_{service}_14"))
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='add_country'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text='📱 اختر التطبيق:', reply_markup=markup)
        
        elif data.startswith('add_country_app_'):
            parts = data.split('_')
            service = parts[3]
            app_id = parts[4]
            page = int(parts[6]) if len(parts) > 6 else 1

            api_countries = get_viotp_countries(app_id) if service == 'viotp' else get_smsman_countries(app_id)

            if not api_countries:
                bot.send_message(chat_id, '❌ لا توجد دول متاحة من واجهة API لهذه الخدمة حاليًا.')
                return

            items_per_page = 10
            countries_chunked = list(api_countries.items())
            total_pages = (len(countries_chunked) + items_per_page - 1) // items_per_page
            start_index = (page - 1) * items_per_page
            end_index = start_index + items_per_page
            current_countries = countries_chunked[start_index:end_index]

            markup = types.InlineKeyboardMarkup()
            for code, info in current_countries:
                price_text = f" - السعر: {info['price']}" if 'price' in info else ''
                markup.row(types.InlineKeyboardButton(f"{info['name']}{price_text}", callback_data=f"select_country_{service}_{app_id}_{code}"))
            
            nav_buttons = []
            if page > 1:
                nav_buttons.append(types.InlineKeyboardButton('◀️ السابق', callback_data=f"add_country_app_{service}_{app_id}_page_{page - 1}"))
            if page < total_pages:
                nav_buttons.append(types.InlineKeyboardButton('التالي ▶️', callback_data=f"add_country_app_{service}_{app_id}_page_{page + 1}"))
            if nav_buttons:
                markup.row(*nav_buttons)
            
            markup.row(types.InlineKeyboardButton('رجوع', callback_data=f"add_country_service_{service}"))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"اختر الدولة التي تريد إضافتها: (صفحة {page}/{total_pages})", reply_markup=markup)

        elif data.startswith('select_country_'):
            parts = data.split('_')
            service, app_id, country_code = parts[2], parts[3], parts[4]
            api_countries = get_viotp_countries(app_id) if service == 'viotp' else get_smsman_countries(app_id)
            country_info = api_countries.get(country_code, {})
            country_name = country_info.get('name')
            api_price = country_info.get('price', 0)
            
            data_file['states'][str(user_id)] = {
                'step': 'waiting_for_admin_price',
                'service': service,
                'app_id': app_id,
                'country_code': country_code,
                'country_name': country_name
            }
            save_data(data_file)
            bot.send_message(chat_id, f"تم اختيار **{country_name}** بسعر أساسي **{api_price}** عملة.\n\nالآن أرسل **السعر الذي تريد بيعه للمستخدمين**.", parse_mode='Markdown')

    # User actions
    else:
        if data == 'Buynum':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('ViOTP', callback_data='service_viotp'))
            markup.row(types.InlineKeyboardButton('SMS.man', callback_data='service_smsman'))
            markup.row(types.InlineKeyboardButton('- رجوع.', callback_data='back'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="📞 *اختر الخدمة التي تريد الشراء منها:*", parse_mode='Markdown', reply_markup=markup)
        
        elif data == 'Record':
            balance = users_data.get(str(user_id), {}).get('balance', 0)
            bot.send_message(chat_id, f"💰 رصيدك الحالي هو: *{balance}* عملة.", parse_mode='Markdown')
        
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
            markup.row(types.InlineKeyboardButton('⁞ واتسأب 💬', callback_data=f'show_countries_{service}_2'))
            markup.row(types.InlineKeyboardButton('⁞ تيليجرام 📢', callback_data=f'show_countries_{service}_3'))
            markup.row(types.InlineKeyboardButton('⁞ فيسبوك 🏆', callback_data=f'show_countries_{service}_4'))
            markup.row(types.InlineKeyboardButton('⁞ إنستقرام 🎥', callback_data=f'show_countries_{service}_5'))
            markup.row(types.InlineKeyboardButton('⁞ تويتر 🚀', callback_data=f'show_countries_{service}_6'))
            markup.row(types.InlineKeyboardButton('⁞ تيكتوك 🎬', callback_data=f'show_countries_{service}_7'))
            markup.row(types.InlineKeyboardButton('⁞ قوقل 🌐', callback_data=f'show_countries_{service}_8'))
            markup.row(types.InlineKeyboardButton('⁞ إيمو 🐦', callback_data=f'show_countries_{service}_9'))
            markup.row(types.InlineKeyboardButton('⁞ سناب 🐬', callback_data=f'show_countries_{service}_11'))
            markup.row(types.InlineKeyboardButton('⁞ حراج 🛍', callback_data=f'show_countries_{service}_13'))
            markup.row(types.InlineKeyboardButton('⁞ السيرفر العام ☑️', callback_data=f'show_countries_{service}_14'))
            markup.row(types.InlineKeyboardButton('- رجوع.', callback_data='Buynum'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"☑️ *اختر التطبيق* الذي تريد *شراء رقم وهمي* له من خدمة **{service}**.", parse_mode='Markdown', reply_markup=markup)
        
        elif data.startswith('show_countries_'):
            parts = data.split('_')
            service, app_id = parts[2], parts[3]
            page = int(parts[5]) if len(parts) > 5 else 1
            
            countries = data_file.get('countries', {}).get(service, {}).get(app_id, {})
            
            if not countries:
                bot.send_message(chat_id, 'لا توجد دول متاحة لهذا التطبيق حاليًا.')
                return

            items_per_page = 10
            country_items = list(countries.items())
            total_pages = (len(country_items) + items_per_page - 1) // items_per_page
            start_index = (page - 1) * items_per_page
            end_index = start_index + items_per_page
            current_countries = country_items[start_index:end_index]
            
            markup = types.InlineKeyboardMarkup()
            for code, info in current_countries:
                markup.row(types.InlineKeyboardButton(f"{info['name']} ({info['price']} عملة)", callback_data=f'buy_{service}_{app_id}_{code}'))
            
            nav_buttons = []
            if page > 1:
                nav_buttons.append(types.InlineKeyboardButton('◀️ السابق', callback_data=f'show_countries_{service}_{app_id}_page_{page - 1}'))
            if page < total_pages:
                nav_buttons.append(types.InlineKeyboardButton('التالي ▶️', callback_data=f'show_countries_{service}_{app_id}_page_{page + 1}'))
            if nav_buttons:
                markup.row(*nav_buttons)
            
            markup.row(types.InlineKeyboardButton('رجوع', callback_data=f'service_{service}'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"اختر الدولة التي تريدها: (صفحة {page}/{total_pages})", reply_markup=markup)

        elif data.startswith('buy_'):
            parts = data.split('_')
            service, app_id, country_code = parts[1], parts[2], parts[3]
            
            country_info = data_file.get('countries', {}).get(service, {}).get(app_id, {}).get(country_code, {})
            price = country_info.get('price', 0)
            
            user_balance = users_data.get(str(user_id), {}).get('balance', 0)
            
            if user_balance < price:
                bot.send_message(chat_id, f"❌ *عذرًا، رصيدك غير كافٍ لإتمام هذه العملية.*\n\n*الرصيد المطلوب:* {price} عملة.\n*رصيدك الحالي:* {user_balance} عملة.\n\n*يمكنك شحن رصيدك عبر زر شحن الرصيد.*", parse_mode='Markdown')
                return

            result = request_viotp_number(app_id, country_code) if service == 'viotp' else request_smsman_number(app_id, country_code)

            if result and result.get('request_id'):
                request_id = result.get('request_id')
                phone_number = result.get('Phone', 'غير متوفر')
                
                users_data[str(user_id)]['balance'] -= price
                save_users(users_data)
                
                active_requests = data_file.get('active_requests', {})
                active_requests[request_id] = {
                    'user_id': user_id,
                    'phone_number': phone_number,
                    'status': 'pending',
                    'service': service,
                    'price': price
                }
                data_file['active_requests'] = active_requests
                save_data(data_file)
                
                markup = types.InlineKeyboardMarkup()
                markup.row(types.InlineKeyboardButton('✅ الحصول على الكود', callback_data=f'get_otp_{service}_{request_id}'))
                markup.row(types.InlineKeyboardButton('❌ إلغاء الطلب', callback_data=f'cancel_{service}_{request_id}'))
                bot.send_message(chat_id, f"✅ تم طلب الرقم بنجاح: *{phone_number}*\n\nاضغط على الزر للحصول على الكود أو إلغاء الطلب.", parse_mode='Markdown', reply_markup=markup)
            else:
                bot.send_message(chat_id, "❌ فشل طلب الرقم. قد يكون غير متوفر أو أن رصيدك في الخدمة غير كافٍ.")
                
        elif data.startswith('get_otp_'):
            parts = data.split('_')
            service, request_id = parts[2], parts[3]

            result = get_viotp_code(request_id) if service == 'viotp' else get_smsman_code(request_id)

            if result and result.get('Code'):
                otp_code = result.get('Code')
                active_requests = data_file.get('active_requests', {})
                if request_id in active_requests:
                    phone_number = active_requests[request_id]['phone_number']
                    del active_requests[request_id]
                    data_file['active_requests'] = active_requests
                    save_data(data_file)
                    bot.send_message(chat_id, f"✅ *رمزك هو: {otp_code}*\n\nالرقم: *{phone_number}*", parse_mode='Markdown')
                else:
                    bot.send_message(chat_id, "❌ حدث خطأ، لم يتم العثور على الطلب.")
            else:
                bot.send_message(chat_id, "❌ لا يوجد كود حتى الآن. حاول مجدداً.")
                
        elif data.startswith('cancel_'):
            parts = data.split('_')
            service, request_id = parts[1], parts[2]
            
            result = cancel_viotp_request(request_id) if service == 'viotp' else cancel_smsman_request(request_id)
            
            if result:
                active_requests = data_file.get('active_requests', {})
                if request_id in active_requests:
                    request_info = active_requests[request_id]
                    user_id_from_request = request_info['user_id']
                    price_to_restore = request_info['price']
                    
                    users_data = load_users()
                    if str(user_id_from_request) in users_data:
                        users_data[str(user_id_from_request)]['balance'] += price_to_restore
                        save_users(users_data)
                    
                    del active_requests[request_id]
                    data_file['active_requests'] = active_requests
                    save_data(data_file)
                bot.send_message(chat_id, "✅ تم إلغاء الطلب بنجاح. سيتم استرجاع رصيدك.")
            else:
                bot.send_message(chat_id, "❌ فشل إلغاء الطلب. يرجى المحاولة مرة أخرى أو التواصل مع الدعم.")
    
bot.polling()
