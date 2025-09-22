# user_handlers.py

from telebot import types
import json
import time
from telebot.apihelper import ApiTelegramException

# --- Shared Functions ---
def load_data():
    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            if 'sh_services' not in data:
                data['sh_services'] = {}
            if 'countries' not in data:
                data['countries'] = {}
            if 'states' not in data:
                data['states'] = {}
            if 'active_requests' in data:
                # Filter out expired requests
                current_time = time.time()
                data['active_requests'] = {
                    req_id: req_info
                    for req_id, req_info in data['active_requests'].items()
                    if req_info.get('expiry_time', current_time + 300) > current_time
                }
            else:
                data['active_requests'] = {}
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
            'join_date': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
            'has_received_bonus': False,
            'has_referrer': False
        }
        save_users(users_data)

def get_main_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton('☎️︙شراء ارقـام وهمية', callback_data='Buynum'))
    markup.row(types.InlineKeyboardButton('💰︙شحن رصيدك', callback_data='Payment'), types.InlineKeyboardButton('👤︙قسم الرشق', callback_data='sh'))
    markup.row(types.InlineKeyboardButton('🅿️︙كشف الحساب', callback_data='Record'), types.InlineKeyboardButton('🛍︙قسم العروض', callback_data='Wo'))
    markup.row(types.InlineKeyboardButton('☑️︙قسم العشوائي', callback_data='worldwide'), types.InlineKeyboardButton('👑︙قسم الملكي', callback_data='saavmotamy'))
    markup.row(types.InlineKeyboardButton('💰︙ربح روبل مجاني 🤑', callback_data='assignment'))
    markup.row(types.InlineKeyboardButton('💳︙متجر الكروت', callback_data='readycard-10'), types.InlineKeyboardButton('🔰︙الارقام الجاهزة', callback_data='ready'))
    markup.row(types.InlineKeyboardButton('👨‍💻︙قسم الوكلاء', callback_data='gents'), types.InlineKeyboardButton('⚙️︙إعدادات البوت', callback_data='MyAccount'))
    markup.row(types.InlineKeyboardButton('📮︙تواصل الدعم أونلاين', callback_data='super'))
    return markup


def setup_user_handlers(bot, DEVELOPER_ID, ESM7AT, EESSMT, viotp_client, smsman_api, tiger_sms_client):

    @bot.message_handler(func=lambda message: message.from_user.id != DEVELOPER_ID)
    def handle_user_messages(message):
        chat_id = message.chat.id
        user_id = message.from_user.id
        first_name = message.from_user.first_name
        username = message.from_user.username

        users_data = load_users()
        register_user(user_id, first_name, username)
        user_info = users_data.get(str(user_id))

        if message.text.startswith('/start'):
            # The rest of the /start handler logic from your original code
            bot.send_message(chat_id, f"☑️ *⁞ قناة البوت الرسمية: @{EESSMT}\n🎬︙قم بالتحكم بالبوت الأن عبر الضعط على الأزرار.*", parse_mode='Markdown', reply_markup=get_main_keyboard())
        
        elif message.text in ['/balance', 'رصيدي']:
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
        
        # All your existing callback handlers here...
        if data == 'assignment':
            # The assignment logic from your original code
            pass # Remove this line after pasting your code
        elif data == 'check_subscription':
            # The subscription check logic
            pass # Remove this line after pasting your code
        # ... and so on ...
        
        elif data == 'Buynum':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('سيرفر 1 (ViOTP)', callback_data='show_countries_viotp'))
            markup.row(types.InlineKeyboardButton('سيرفر 2 (SMS.man)', callback_data='service_smsman'))
            markup.row(types.InlineKeyboardButton('سيرفر 3 (Tiger SMS)', callback_data='service_tigersms'))
            markup.row(types.InlineKeyboardButton('- رجوع.', callback_data='back'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="📞 *اختر الخدمة التي تريد الشراء منها:*", parse_mode='Markdown', reply_markup=markup)

        # --- SMS-Man Logic ---
        elif data == 'service_smsman':
            try:
                # Correct way to call the get_countries method from the SmsManApi class
                api_response = smsman_api.get_countries()
                if not api_response.get('success'):
                    bot.send_message(chat_id, f"❌ حدث خطأ من الـ API: {api_response.get('message', 'لا توجد بيانات')}")
                    return

                countries_data = api_response.get('data', [])
                if not countries_data:
                    bot.send_message(chat_id, '❌ لا توجد دول متاحة من واجهة API لهذه الخدمة حاليًا.')
                    return

                markup = types.InlineKeyboardMarkup()
                for country_info in countries_data:
                    markup.add(types.InlineKeyboardButton(f"🌐 {country_info['name']} ({country_info['count']})", callback_data=f'show_apps_smsman_{country_info["id"]}'))
                markup.add(types.InlineKeyboardButton('رجوع', callback_data='Buynum'))
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="اختر الدولة التي تريدها:", reply_markup=markup)

            except Exception as e:
                bot.send_message(chat_id, f"❌ حدث خطأ أثناء الاتصال بالـ API: {e}")

        elif data.startswith('show_apps_smsman_'):
            country_id = data.split('_')[-1]
            try:
                api_response = smsman_api.get_applications(country_id)
                if not api_response.get('success'):
                    bot.send_message(chat_id, f"❌ حدث خطأ من الـ API: {api_response.get('message', 'لا توجد بيانات')}")
                    return

                apps_data = api_response.get('data', [])
                if not apps_data:
                    bot.send_message(chat_id, '❌ لا توجد تطبيقات متاحة لهذه الدولة حاليًا.')
                    return

                markup = types.InlineKeyboardMarkup()
                for app_info in apps_data:
                    markup.add(types.InlineKeyboardButton(f"📱 {app_info['name']} ({app_info['price']} روبل)", callback_data=f'buy_smsman_{app_info["id"]}_{country_id}_{app_info["price"]}'))
                markup.add(types.InlineKeyboardButton('رجوع', callback_data=f'service_smsman'))
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="اختر التطبيق الذي تريده:", reply_markup=markup)

            except Exception as e:
                bot.send_message(chat_id, f"❌ حدث خطأ أثناء الاتصال بالـ API: {e}")
        
        # --- Other services (ViOTP, TigerSMS) ---
        elif data.startswith('show_countries_viotp'):
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('فيتنام (Vietnam)', callback_data=f'show_services_viotp_vn'))
            markup.row(types.InlineKeyboardButton('لاوس (Laos)', callback_data=f'show_services_viotp_la'))
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='Buynum'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="اختر الدولة التي تريدها:", reply_markup=markup)

        elif data.startswith('show_services_viotp_'):
            country_code = data.split('_')[-1]
            try:
                api_response = viotp_client.get_services_by_country(country_code)
                if not api_response.get('success'):
                    bot.send_message(chat_id, f"❌ حدث خطأ من الـ API: {api_response.get('message', 'لا توجد بيانات')}")
                    return

                services_data = api_response.get('data', [])
                if not services_data:
                    bot.send_message(chat_id, '❌ لا توجد خدمات متاحة في هذه الدولة حاليًا.')
                    return

                markup = types.InlineKeyboardMarkup()
                for service_info in services_data:
                    markup.row(types.InlineKeyboardButton(f"⁞ {service_info['name']} ({service_info['price']} روبل)", callback_data=f'buy_viotp_{service_info["id"]}_{service_info["price"]}_{country_code}'))

                markup.row(types.InlineKeyboardButton('رجوع', callback_data='show_countries_viotp'))
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"اختر التطبيق من {country_code.upper()}:", reply_markup=markup)
            except Exception as e:
                bot.send_message(chat_id, f"❌ حدث خطأ أثناء الاتصال بالـ API: {e}")
        
        # --- Buy Number Logic (Unified) ---
        elif data.startswith('buy_'):
            parts = data.split('_')
            service = parts[1]

            if service == 'viotp':
                app_id = parts[2]
                final_price = float(parts[3])
                country_code = parts[4]
            elif service == 'smsman':
                app_id = parts[2]
                country_id = parts[3]
                final_price = float(parts[4])
                country_code = country_id
            else:
                return

            user_balance = users_data.get(str(user_id), {}).get('balance', 0)

            if user_balance < final_price:
                bot.send_message(chat_id, f"❌ *عذرًا، رصيدك غير كافٍ لإتمام هذه العملية.*\n\n*الرصيد المطلوب:* {final_price} روبل.\n*رصيدك الحالي:* {user_balance} روبل.\n\n*يمكنك شحن رصيدك عبر زر شحن الرصيد.*", parse_mode='Markdown')
                return

            try:
                result = None
                if service == 'viotp':
                    result = viotp_client.buy_number(app_id)
                elif service == 'smsman':
                    result = smsman_api.request_smsman_number(app_id, country_code)
                elif service == 'tigersms':
                    result = tiger_sms_client.get_number(app_id, country_code)

                if result and result.get('success'):
                    request_id = None
                    phone_number = None
                    final_price_actual = None

                    if service == 'viotp':
                        request_id = result.get('data', {}).get('request_id')
                        phone_number = result.get('data', {}).get('phone_number')
                        final_price_actual = result.get('data', {}).get('balance')
                    elif service == 'smsman':
                        request_id = result.get('request_id')
                        phone_number = result.get('number')
                        final_price_actual = result.get('price')
                    elif service == 'tigersms':
                        request_id = result.get('id')
                        phone_number = result.get('number')
                        final_price_actual = result.get('price')

                    if not request_id or not phone_number or final_price_actual is None:
                        bot.send_message(chat_id, "❌ فشل الحصول على معلومات الرقم من الخدمة. يرجى المحاولة مرة أخرى.")
                        return

                    users_data[str(user_id)]['balance'] -= final_price_actual
                    save_users(users_data)

                    active_requests = data_file.get('active_requests', {})
                    active_requests[request_id] = {
                        'user_id': user_id,
                        'phone_number': phone_number,
                        'status': 'pending',
                        'service': service,
                        'price': final_price_actual,
                        'expiry_time': time.time() + 600 # 10 minutes expiry time
                    }
                    data_file['active_requests'] = active_requests
                    save_data(data_file)

                    markup = types.InlineKeyboardMarkup()
                    markup.row(types.InlineKeyboardButton('✅ الحصول على الكود', callback_data=f'get_otp_{service}_{request_id}'))
                    markup.row(types.InlineKeyboardButton('❌ إلغاء الطلب', callback_data=f'cancel_{service}_{request_id}'))
                    bot.send_message(chat_id, f"✅ تم طلب الرقم بنجاح: *{phone_number}*\n\nاضغط على الزر للحصول على الكود أو إلغاء الطلب.", parse_mode='Markdown', reply_markup=markup)
                else:
                    bot.send_message(chat_id, f"❌ فشل طلب الرقم. قد يكون غير متوفر أو أن رصيدك في الخدمة غير كافٍ. رسالة الخطأ: {result.get('message', 'لا يوجد')}")
            except Exception as e:
                bot.send_message(chat_id, f"❌ حدث خطأ أثناء الشراء: {e}")

        # --- Get OTP Logic (Unified) ---
        elif data.startswith('get_otp_'):
            parts = data.split('_')
            service, request_id = parts[2], parts[3]

            active_requests = data_file.get('active_requests', {})
            request_info = active_requests.get(request_id)

            if not request_info or request_info['user_id'] != user_id:
                bot.send_message(chat_id, '❌ هذا الطلب غير موجود أو انتهت صلاحيته.')
                return

            try:
                if service == 'viotp':
                    result = viotp_client.get_otp(request_id)
                elif service == 'smsman':
                    result = smsman_api.get_smsman_code(request_id)
                elif service == 'tigersms':
                    result = tiger_sms_client.get_code(request_id)

                if result and result.get('success') and result.get('data', {}).get('code'):
                    code = result.get('data', {}).get('code')
                    bot.send_message(chat_id, f"✅ تم استلام الكود بنجاح!\n\n*الكود:* `{code}`", parse_mode='Markdown')
                    del data_file['active_requests'][request_id]
                    save_data(data_file)
                else:
                    bot.send_message(chat_id, f'⏳ لم يتم استلام الكود بعد. يرجى المحاولة مرة أخرى لاحقاً.')
            except Exception as e:
                bot.send_message(chat_id, f"❌ حدث خطأ أثناء جلب الكود: {e}")

        # --- Cancel Logic (Unified) ---
        elif data.startswith('cancel_'):
            parts = data.split('_')
            service, request_id = parts[1], parts[2]

            active_requests = data_file.get('active_requests', {})
            request_info = active_requests.get(request_id)

            if not request_info or request_info['user_id'] != user_id:
                bot.send_message(chat_id, '❌ هذا الطلب غير موجود أو لا يمكنك إلغاؤه.')
                return

            try:
                if service == 'viotp':
                    viotp_client.cancel_request(request_id)
                elif service == 'smsman':
                    smsman_api.cancel_smsman_number(request_id)
                elif service == 'tigersms':
                    tiger_sms_client.cancel_number(request_id)

                price = request_info['price']
                users_data[str(user_id)]['balance'] += price
                save_users(users_data)

                del data_file['active_requests'][request_id]
                save_data(data_file)

                bot.send_message(chat_id, f"✅ تم إلغاء الطلب بنجاح. تم استرجاع `{price}` روبل إلى رصيدك.", parse_mode='Markdown')
            except Exception as e:
                bot.send_message(chat_id, f"❌ حدث خطأ أثناء إلغاء الطلب: {e}")
