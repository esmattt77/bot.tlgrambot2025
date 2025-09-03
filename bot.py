import time
import telebot
from telebot import types
import json
import requests
import os
from viotp_api import VIOTPAPI
from smsman_api import get_smsman_balance, get_smsman_countries, request_smsman_number, get_smsman_code, cancel_smsman_request

# قراءة توكن البوت من المتغيرات البيئية
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TELEGRAM_BOT_TOKEN:
    print("Error: TELEGRAM_BOT_TOKEN environment variable not set.")
    exit()

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
DEVELOPER_ID = int(os.environ.get('DEVELOPER_ID'))
EESSMT = os.environ.get('EESSMT')
VIOTP_API_KEY = os.environ.get('VIOTP_API_KEY')
SMSMAN_API_KEY = os.environ.get('SMSMAN_API_KEY')


# إنشاء كائنات (objects) للتعامل مع الـ APIs
viotp_client = VIOTPAPI(VIOTP_API_KEY)


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
@bot.message_handler(func=lambda message: True)
def handle_text_messages(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    username = message.from_user.username

    register_user(user_id, first_name, username)

    data_file = load_data()
    state = data_file.get('states', {}).get(str(user_id))
    
    if message.text in ['/start', 'start/', 'بدء/', '/admin']:
        if user_id == DEVELOPER_ID:
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('إحصائيات البوت 📊', callback_data='bot_stats'), types.InlineKeyboardButton('إدارة المستخدمين 👥', callback_data='manage_users'))
            markup.row(types.InlineKeyboardButton('إضافة رصيد 💰', callback_data='add_balance'), types.InlineKeyboardButton('خصم رصيد 💸', callback_data='deduct_balance'))
            markup.row(types.InlineKeyboardButton('إضافة دولة 🌐', callback_data='add_country'), types.InlineKeyboardButton('حذف دولة ❌', callback_data='delete_country'))
            markup.row(types.InlineKeyboardButton('عرض الطلبات النشطة 📞', callback_data='view_active_requests'), types.InlineKeyboardButton('إلغاء جميع الطلبات 🚫', callback_data='cancel_all_requests'))
            markup.row(types.InlineKeyboardButton('إرسال رسالة جماعية 📣', callback_data='broadcast_message'), types.InlineKeyboardButton('الكشف عن أرصدة المواقع 💳', callback_data='show_api_balance_menu'))
            bot.send_message(chat_id, "أهلاً بك في لوحة تحكم المشرف!", reply_markup=markup)
        else:
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
    
    # معالجة الأوامر النصية للمشرف
    if user_id == DEVELOPER_ID:
        if state and state.get('step') == 'waiting_for_add_coin_id':
            target_id = message.text
            data_file['states'][str(user_id)]['target_id'] = target_id
            data_file['states'][str(user_id)]['step'] = 'waiting_for_add_coin_amount'
            save_data(data_file)
            bot.send_message(chat_id, "تم حفظ الآيدي. الآن أرسل **المبلغ** الذي تريد إضافته للمستخدم.")
        
        elif state and state.get('step') == 'waiting_for_add_coin_amount':
            try:
                amount = int(message.text)
                target_id = state.get('target_id')
                users_data = load_users()
                if str(target_id) not in users_data:
                    users_data[str(target_id)] = {'balance': 0}
                users_data[str(target_id)]['balance'] += amount
                save_users(users_data)
                
                try:
                    bot.send_message(target_id, f"🎉 تم إضافة {amount} عملة إلى رصيدك من قبل المشرف!")
                except telebot.apihelper.ApiException as e:
                    bot.send_message(chat_id, f"✅ تم إضافة الرصيد بنجاح، لكن لا يمكن إرسال رسالة للمستخدم: {e}")

                del data_file['states'][str(user_id)]
                save_data(data_file)
                bot.send_message(chat_id, f"✅ تم إضافة {amount} عملة إلى المستخدم ذو الآيدي: {target_id}")
            except ValueError:
                bot.send_message(chat_id, "❌ المبلغ الذي أدخلته غير صحيح. يرجى إدخال رقم.")
        
        elif state and state.get('step') == 'waiting_for_deduct_coin_id':
            target_id = message.text
            data_file['states'][str(user_id)]['target_id'] = target_id
            data_file['states'][str(user_id)]['step'] = 'waiting_for_deduct_coin_amount'
            save_data(data_file)
            bot.send_message(chat_id, "تم حفظ الآيدي. الآن أرسل **المبلغ** الذي تريد خصمه من المستخدم.")
        
        elif state and state.get('step') == 'waiting_for_deduct_coin_amount':
            try:
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
            except ValueError:
                bot.send_message(chat_id, "❌ المبلغ الذي أدخلته غير صحيح. يرجى إدخال رقم.")

        elif state and state.get('step') == 'waiting_for_broadcast_message':
            users_data = load_users()
            for uid in users_data.keys():
                bot.send_message(uid, message.text)
            del data_file['states'][str(user_id)]
            save_data(data_file)
            bot.send_message(chat_id, "📣 اكتمل البث بنجاح!")
        
        elif state and state.get('step') == 'waiting_for_admin_price':
            try:
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
            except ValueError:
                bot.send_message(chat_id, "❌ السعر الذي أدخلته غير صحيح. يرجى إدخال رقم.")
        
        elif state and state.get('step') == 'waiting_for_check_user_id':
            target_id = message.text
            users_data = load_users()
            user_info = users_data.get(str(target_id))
            if user_info:
                balance = user_info.get('balance', 0)
                bot.send_message(chat_id, f"👤 **معلومات المستخدم:**\n\n**الآيدي:** `{target_id}`\n**الرصيد:** `{balance}` عملة", parse_mode='Markdown')
            else:
                bot.send_message(chat_id, "❌ لم يتم العثور على مستخدم بهذا الآيدي.")
            del data_file['states'][str(user_id)]
            save_data(data_file)
        
        elif state and state.get('step') == 'waiting_for_get_user_info_id':
            target_id = message.text
            users_data = load_users()
            user_info = users_data.get(str(target_id))
            if user_info:
                message_text = (
                    f"👤 **تفاصيل المستخدم:**\n"
                    f"**الآيدي:** `{user_info.get('id', 'غير متوفر')}`\n"
                    f"**الاسم:** `{user_info.get('first_name', 'غير متوفر')}`\n"
                    f"**اسم المستخدم:** `@{user_info.get('username', 'غير متوفر')}`\n"
                    f"**الرصيد:** `{user_info.get('balance', 0)}` عملة\n"
                    f"**تاريخ الانضمام:** `{user_info.get('join_date', 'غير متوفر')}`"
                )
                bot.send_message(chat_id, message_text, parse_mode='Markdown')
            else:
                bot.send_message(chat_id, "❌ لم يتم العثور على مستخدم بهذا الآيدي.")
            del data_file['states'][str(user_id)]
            save_data(data_file)

        elif state and state.get('step') == 'waiting_for_send_message_to_user_id':
            target_id = message.text
            data_file['states'][str(user_id)]['target_id'] = target_id
            data_file['states'][str(user_id)]['step'] = 'waiting_for_message_to_send'
            save_data(data_file)
            bot.send_message(chat_id, "تم حفظ الآيدي. الآن أرسل **الرسالة** التي تريد إرسالها للمستخدم.")

        elif state and state.get('step') == 'waiting_for_message_to_send':
            target_id = state.get('target_id')
            try:
                bot.send_message(target_id, message.text)
                bot.send_message(chat_id, f"✅ تم إرسال الرسالة للمستخدم ذو الآيدي: {target_id}")
            except telebot.apihelper.ApiException as e:
                bot.send_message(chat_id, f"❌ فشل إرسال الرسالة للمستخدم. قد يكون المستخدم قد حظر البوت: {e}")
            finally:
                del data_file['states'][str(user_id)]
                save_data(data_file)
                
# --- Callback Query Handler ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    message_id = call.message.message_id
    data = call.data
    
    data_file = load_data()
    users_data = load_users()
    
    # User actions
    if user_id != DEVELOPER_ID:
        if data == 'Payment':
            bot.send_message(chat_id, "💰 *لشحن رصيدك، يرجى التواصل مع المشرف عبر هذا الحساب: @[username].*", parse_mode='Markdown')
            return
        elif data == 'sh':
            bot.send_message(chat_id, "👤 *خدمة الرشق (زيادة المتابعين) قيد التطوير وستتوفر قريباً.*", parse_mode='Markdown')
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
            bot.send_message(chat_id, "💰 *يمكنك ربح عملات مجانية عن طريق إكمال بعض المهام. تابع الإعلانات لمعرفة التفاصيل.*", parse_mode='Markdown')
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
                f"**الرصيد:** `{user_info.get('balance', 0)}` عملة\n"
            )
            bot.send_message(chat_id, message_text, parse_mode='Markdown')
            return
        elif data == 'super':
            bot.send_message(chat_id, "📮 *للتواصل مع الدعم الفني، يرجى إرسال رسالتك إلى هذا الحساب: @[username].*")
            return

        elif data == 'Buynum':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('سيرفر 1', callback_data='service_viotp'))
            markup.row(types.InlineKeyboardButton('سيرفر 2', callback_data='service_smsman'))
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
            markup.row(types.InlineKeyboardButton('⁞ تيكتوك 🎬', callback_data=f"show_countries_{service}_7"))
            markup.row(types.InlineKeyboardButton('⁞ قوقل 🌐', callback_data=f'show_countries_{service}_8'))
            markup.row(types.InlineKeyboardButton('⁞ إيمو 🐦', callback_data=f'show_countries_{service}_9'))
            markup.row(types.InlineKeyboardButton('⁞ سناب 🐬', callback_data=f'show_countries_{service}_11'))
            markup.row(types.InlineKeyboardButton('⁞ حراج 🛍', callback_data=f'show_countries_{service}_13'))
            markup.row(types.InlineKeyboardButton('⁞ السيرفر العام ☑️', callback_data=f'show_countries_{service}_14'))
            markup.row(types.InlineKeyboardButton('- رجوع.', callback_data='Buynum'))
            server_name = 'سيرفر 1' if service == 'viotp' else 'سيرفر 2'
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"☑️ *اختر التطبيق* الذي تريد *شراء رقم وهمي* له من خدمة **{server_name}**.", parse_mode='Markdown', reply_markup=markup)
        
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
            
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='Buynum'))
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

            if service == 'viotp':
                result = viotp_client.buy_number(app_id, country_code)
            else:
                result = request_smsman_number(app_id, country_code)

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
            
            if service == 'viotp':
                result = viotp_client.get_otp(request_id)
            else:
                result = get_smsman_code(request_id)

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
            
            if service == 'viotp':
                result = viotp_client.cancel_request(request_id)
            else:
                result = cancel_smsman_request(request_id)
            
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

    # Admin actions
    elif user_id == DEVELOPER_ID:
        if data == 'admin_main_menu':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('إحصائيات البوت 📊', callback_data='bot_stats'), types.InlineKeyboardButton('إدارة المستخدمين 👥', callback_data='manage_users'))
            markup.row(types.InlineKeyboardButton('إضافة رصيد 💰', callback_data='add_balance'), types.InlineKeyboardButton('خصم رصيد 💸', callback_data='deduct_balance'))
            markup.row(types.InlineKeyboardButton('إضافة دولة 🌐', callback_data='add_country'), types.InlineKeyboardButton('حذف دولة ❌', callback_data='delete_country'))
            markup.row(types.InlineKeyboardButton('عرض الطلبات النشطة 📞', callback_data='view_active_requests'), types.InlineKeyboardButton('إلغاء جميع الطلبات 🚫', callback_data='cancel_all_requests'))
            markup.row(types.InlineKeyboardButton('إرسال رسالة جماعية 📣', callback_data='broadcast_message'), types.InlineKeyboardButton('الكشف عن أرصدة المواقع 💳', callback_data='show_api_balance_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="أهلاً بك في لوحة تحكم المشرف!", reply_markup=markup)
            return

        elif data == 'manage_users':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('عرض رصيد مستخدم 💰', callback_data='check_user_balance'))
            markup.row(types.InlineKeyboardButton('عرض معلومات مستخدم 👤', callback_data='get_user_info'))
            markup.row(types.InlineKeyboardButton('إرسال رسالة لمستخدم ✉️', callback_data='send_message_to_user'))
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='admin_main_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="👥 اختر إجراء لإدارة المستخدمين:", reply_markup=markup)
            return
        
        elif data == 'add_balance':
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
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='admin_main_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text='🌐 اختر الخدمة لإضافة دولة:', reply_markup=markup)
        elif data == 'bot_stats':
            total_users = len(users_data)
            message = f"📊 إحصائيات البوت:\nعدد المستخدمين: *{total_users}*\n"
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='admin_main_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message, parse_mode='Markdown', reply_markup=markup)
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
            viotp_balance_data = viotp_client.get_balance()
            if viotp_balance_data and viotp_balance_data.get('success'):
                viotp_balance = viotp_balance_data['data']['balance']
                message = f"💰 رصيد ViOTP الحالي: *{viotp_balance}* عملة."
            else:
                message = "❌ فشل الاتصال. يرجى التأكد من مفتاح API أو إعدادات الشبكة."
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='admin_main_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message, parse_mode='Markdown', reply_markup=markup)
        elif data == 'get_smsman_balance':
            smsman_balance = get_smsman_balance()
            message = f"💰 رصيد SMS.man الحالي:\n• SMS.man: *{smsman_balance}* عملة." if smsman_balance is not False else "❌ فشل الاتصال. يرجى التأكد من مفتاح API أو إعدادات الشبكة."
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='admin_main_menu'))
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

            try:
                if service == 'viotp':
                    all_services = viotp_client.get_services_and_countries()
                    api_countries = all_services.get(app_id, {}).get('countries', {})
                else:
                    api_countries = get_smsman_countries(app_id)
            except Exception as e:
                bot.send_message(chat_id, f'❌ حدث خطأ أثناء الاتصال بالـ API: {e}')
                return

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
                price_text = f" - السعر: {info.get('price', 'غير متاح')}" if 'price' in info else ''
                markup.row(types.InlineKeyboardButton(f"{info.get('name', 'غير معروف')}{price_text}", callback_data=f"select_country_{service}_{app_id}_{code}"))
            
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
            
            if service == 'viotp':
                all_services = viotp_client.get_services_and_countries()
                country_info = all_services.get(app_id, {}).get('countries', {}).get(country_code, {})
            else:
                api_countries = get_smsman_countries(app_id)
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
        
        # Admin User Management Buttons
        elif data == 'check_user_balance':
            data_file['states'][str(user_id)] = {'step': 'waiting_for_check_user_id'}
            save_data(data_file)
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="💰 أرسل **آيدي المستخدم** للتحقق من رصيده.")
        
        elif data == 'get_user_info':
            data_file['states'][str(user_id)] = {'step': 'waiting_for_get_user_info_id'}
            save_data(data_file)
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="👤 أرسل **آيدي المستخدم** للحصول على معلوماته.")
        
        elif data == 'send_message_to_user':
            data_file['states'][str(user_id)] = {'step': 'waiting_for_send_message_to_user_id'}
            save_data(data_file)
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="✉️ أرسل **آيدي المستخدم** الذي تريد إرسال رسالة إليه.")


    # User actions (end)
    else:
        if data == 'Buynum':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('سيرفر 1', callback_data='service_viotp'))
            markup.row(types.InlineKeyboardButton('سيرفر 2', callback_data='service_smsman'))
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
            markup.row(types.InlineKeyboardButton('⁞ تيكتوك 🎬', callback_data=f"show_countries_{service}_7"))
            markup.row(types.InlineKeyboardButton('⁞ قوقل 🌐', callback_data=f'show_countries_{service}_8'))
            markup.row(types.InlineKeyboardButton('⁞ إيمو 🐦', callback_data=f'show_countries_{service}_9'))
            markup.row(types.InlineKeyboardButton('⁞ سناب 🐬', callback_data=f'show_countries_{service}_11'))
            markup.row(types.InlineKeyboardButton('⁞ حراج 🛍', callback_data=f'show_countries_{service}_13'))
            markup.row(types.InlineKeyboardButton('⁞ السيرفر العام ☑️', callback_data=f'show_countries_{service}_14'))
            markup.row(types.InlineKeyboardButton('- رجوع.', callback_data='Buynum'))
            server_name = 'سيرفر 1' if service == 'viotp' else 'سيرفر 2'
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"☑️ *اختر التطبيق* الذي تريد *شراء رقم وهمي* له من خدمة **{server_name}**.", parse_mode='Markdown', reply_markup=markup)
        
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
            
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='Buynum'))
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

            if service == 'viotp':
                result = viotp_client.buy_number(app_id, country_code)
            else:
                result = request_smsman_number(app_id, country_code)

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
            
            if service == 'viotp':
                result = viotp_client.get_otp(request_id)
            else:
                result = get_smsman_code(request_id)

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
            
            if service == 'viotp':
                result = viotp_client.cancel_request(request_id)
            else:
                result = cancel_smsman_request(request_id)
            
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
