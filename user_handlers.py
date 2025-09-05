import telebot
from telebot import types
import json
import time

def load_data():
    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            if 'sh_services' not in data:
                data['sh_services'] = {}
            if 'countries' not in data:
                data['countries'] = {}
            return data
    except (FileNotFoundEror, json.JSONDecodeError):
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


def setup_user_handlers(bot, DEVELOPER_ID, data_file, users_data, ESM7AT, EESSMT, viotp_client, smsman_api, tiger_sms_client):
    
    @bot.message_handler(func=lambda message: True, pass_bot=True)
    def handle_user_messages(message, bot):
        chat_id = message.chat.id
        user_id = message.from_user.id
        first_name = message.from_user.first_name
        username = message.from_user.username
        
        register_user(user_id, first_name, username)

        if message.text in ['/start', 'start/', 'بدء/']:
            # --- تم إضافة هذا الشرط للتمييز بين المستخدم والمشرف ---
            if user_id == DEVELOPER_ID:
                markup = types.InlineKeyboardMarkup()
                markup.row(types.InlineKeyboardButton('إحصائيات البوت 📊', callback_data='bot_stats'), types.InlineKeyboardButton('إدارة المستخدمين 👥', callback_data='manage_users'))
                markup.row(types.InlineKeyboardButton('إضافة رصيد 💰', callback_data='add_balance'), types.InlineKeyboardButton('خصم رصيد 💸', callback_data='deduct_balance'))
                markup.row(types.InlineKeyboardButton('إضافة دولة 🌐', callback_data='add_country'), types.InlineKeyboardButton('حذف دولة ❌', callback_data='delete_country'))
                markup.row(types.InlineKeyboardButton('عرض الطلبات النشطة 📞', callback_data='view_active_requests'), types.InlineKeyboardButton('إلغاء جميع الطلبات 🚫', callback_data='cancel_all_requests'))
                markup.row(types.InlineKeyboardButton('إرسال رسالة جماعية 📣', callback_data='broadcast_message'), types.InlineKeyboardButton('الكشف عن أرصدة المواقع 💳', callback_data='show_api_balance_menu'))
                markup.row(types.InlineKeyboardButton('إدارة الرشق 🚀', callback_data='sh_admin_menu'))
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
            bot.send_message(chat_id, f"💰 رصيدك الحالي هو: *{balance}* روبل.", parse_mode='Markdown')

    @bot.callback_query_handler(func=lambda call: True, pass_bot=True)
    def handle_user_callbacks(call, bot):
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
            bot.send_message(chat_id, "💰 *يمكنك ربح روبل مجاني عن طريق إكمال بعض المهام. تابع الإعلانات لمعرفة التفاصيل.*", parse_mode='Markdown')
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
            countries_by_service = data_file.get('countries', {})
            
            viotp_countries = countries_by_service.get('viotp', {})
            smsman_countries = countries_by_service.get('smsman', {})
            tigersms_countries = countries_by_service.get('tigersms', {})
            
            if viotp_countries:
                markup.row(types.InlineKeyboardButton('سيرفر 1', callback_data='service_viotp'))
            if smsman_countries:
                markup.row(types.InlineKeyboardButton('سيرفر 2', callback_data='service_smsman'))
            if tigersms_countries:
                markup.row(types.InlineKeyboardButton('سيرفر 3', callback_data='service_tigersms'))

            if not viotp_countries and not smsman_countries and not tigersms_countries:
                bot.send_message(chat_id, "❌ لا توجد أي أرقام متاحة حاليًا. يرجى العودة لاحقًا.")
                return

            markup.row(types.InlineKeyboardButton('- رجوع.', callback_data='back'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="📞 *اختر الخدمة التي تريد الشراء منها:*", parse_mode='Markdown', reply_markup=markup)

        elif data.startswith('service_'):
            service = data.split('_')[1]
            markup = types.InlineKeyboardMarkup()
            service_apps = data_file.get('countries', {}).get(service, {})
            
            if service_apps.get('2'):
                markup.row(types.InlineKeyboardButton('⁞ واتسأب 💬', callback_data=f'show_countries_{service}_2'))
            if service_apps.get('3'):
                markup.row(types.InlineKeyboardButton('⁞ تيليجرام 📢', callback_data=f'show_countries_{service}_3'))
            if service_apps.get('4'):
                markup.row(types.InlineKeyboardButton('⁞ فيسبوك 🏆', callback_data=f'show_countries_{service}_4'))
            if service_apps.get('5'):
                markup.row(types.InlineKeyboardButton('⁞ إنستقرام 🎥', callback_data=f'show_countries_{service}_5'))
            if service_apps.get('6'):
                markup.row(types.InlineKeyboardButton('⁞ تويتر 🚀', callback_data=f'show_countries_{service}_6'))
            if service_apps.get('7'):
                markup.row(types.InlineKeyboardButton('⁞ تيكتوك 🎬', callback_data=f"show_countries_{service}_7"))
            if service_apps.get('8'):
                markup.row(types.InlineKeyboardButton('⁞ قوقل 🌐', callback_data=f'show_countries_{service}_8'))
            if service_apps.get('9'):
                markup.row(types.InlineKeyboardButton('⁞ إيمو 🐦', callback_data=f'show_countries_{service}_9'))
            if service_apps.get('11'):
                markup.row(types.InlineKeyboardButton('⁞ سناب 🐬', callback_data=f'show_countries_{service}_11'))
            if service_apps.get('12'):
                markup.row(types.InlineKeyboardButton('⁞ OK 🌟', callback_data=f'show_countries_{service}_12'))
            if service_apps.get('16'):
                markup.row(types.InlineKeyboardButton('⁞ Viber 📲', callback_data=f'show_countries_{service}_16'))
            if service_apps.get('13'):
                markup.row(types.InlineKeyboardButton('⁞ حراج 🛍', callback_data=f'show_countries_{service}_13'))
            if service_apps.get('14'):
                markup.row(types.InlineKeyboardButton('⁞ السيرفر العام ☑️', callback_data=f'show_countries_{service}_14'))
            
            if service == 'tigersms':
                if service_apps.get('wa'): markup.row(types.InlineKeyboardButton('⁞ واتسأب 💬', callback_data=f'show_countries_{service}_wa'))
                if service_apps.get('tg'): markup.row(types.InlineKeyboardButton('⁞ تيليجرام 📢', callback_data=f'show_countries_{service}_tg'))
                if service_apps.get('fb'): markup.row(types.InlineKeyboardButton('⁞ فيسبوك 🏆', callback_data=f'show_countries_{service}_fb'))
                if service_apps.get('ig'): markup.row(types.InlineKeyboardButton('⁞ إنستقرام 🎥', callback_data=f'show_countries_{service}_ig'))
                if service_apps.get('tw'): markup.row(types.InlineKeyboardButton('⁞ تويتر 🚀', callback_data=f'show_countries_{service}_tw'))
                if service_apps.get('tt'): markup.row(types.InlineKeyboardButton('⁞ تيكتوك 🎬', callback_data=f"show_countries_{service}_tt"))
                if service_apps.get('go'): markup.row(types.InlineKeyboardButton('⁞ قوقل 🌐', callback_data=f'show_countries_{service}_go'))
                if service_apps.get('sn'): markup.row(types.InlineKeyboardButton('⁞ سناب 🐬', callback_data=f'show_countries_{service}_sn'))
                if service_apps.get('ds'): markup.row(types.InlineKeyboardButton('⁞ ديسكورد 🎮', callback_data=f'show_countries_{service}_ds'))
                if service_apps.get('td'): markup.row(types.InlineKeyboardButton('⁞ تيندر ❤️', callback_data=f'show_countries_{service}_td'))
                if service_apps.get('ub'): markup.row(types.InlineKeyboardButton('⁞ أوبر 🚕', callback_data=f'show_countries_{service}_ub'))
                if service_apps.get('ok'): markup.row(types.InlineKeyboardButton('⁞ أوكي 🌟', callback_data=f'show_countries_{service}_ok'))
                if service_apps.get('li'): markup.row(types.InlineKeyboardButton('⁞ لاين 📲', callback_data=f'show_countries_{service}_li'))
                if service_apps.get('am'): markup.row(types.InlineKeyboardButton('⁞ أمازون 🛒', callback_data=f'show_countries_{service}_am'))
            
            markup.row(types.InlineKeyboardButton('- رجوع.', callback_data='Buynum'))
            server_name = 'سيرفر 1' if service == 'viotp' else ('سيرفر 2' if service == 'smsman' else 'سيرفر 3')
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"☑️ *اختر التطبيق* الذي تريد *شراء رقم وهمي* له من خدمة **{server_name}**.", parse_mode='Markdown', reply_markup=markup)

        elif data == 'Record':
            balance = users_data.get(str(user_id), {}).get('balance', 0)
            bot.send_message(chat_id, f"💰 رصيدك الحالي هو: *{balance}* روبل.", parse_mode='Markdown')
        
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

        elif data.startswith('show_countries_'):
            parts = data.split('_')
            service, app_id = parts[2], parts[3]
            page = int(parts[5]) if len(parts) > 5 else 1
            
            local_countries = data_file.get('countries', {}).get(service, {}).get(app_id, {})
            
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
            country_info = data_file.get('countries', {}).get(service, {}).get(app_id, {}).get(country_code, {})
            price = country_info.get('price', 0)
            
            users_data = load_users()
            user_balance = users_data.get(str(user_id), {}).get('balance', 0)
            
            if user_balance < price:
                bot.send_message(chat_id, f"❌ *عذرًا، رصيدك غير كافٍ لإتمام هذه العملية.*\n\n*الرصيد المطلوب:* {price} روبل.\n*رصيدك الحالي:* {user_balance} روبل.\n\n*يمكنك شحن رصيدك عبر زر شحن الرصيد.*", parse_mode='Markdown')
                return

            if service == 'viotp':
                result = viotp_client.buy_number(app_id)
            elif service == 'smsman':
                result = smsman_api.request_smsman_number(app_id, country_code)
            elif service == 'tigersms':
                result = tiger_sms_client.get_number(app_id, country_code)

            if result and result.get('success'):
                request_id = result.get('id')
                phone_number = result.get('number', result.get('Phone', 'غير متوفر'))
                
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
            data_file = load_data()

            if service == 'viotp':
                result = viotp_client.get_otp(request_id)
            elif service == 'smsman':
                result = smsman_api.get_smsman_code(request_id)
            elif service == 'tigersms':
                result = tiger_sms_client.get_code(request_id)

            if result and result.get('success') and result.get('code'):
                otp_code = result.get('code')
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
            
            result = None
            if service == 'viotp':
                result = viotp_client.cancel_request(request_id)
            elif service == 'smsman':
                result = smsman_api.cancel_smsman_request(request_id)
            elif service == 'tigersms':
                result = tiger_sms_client.cancel_request(request_id)
            
            if result and result.get('success'):
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
