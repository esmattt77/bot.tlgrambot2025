from telebot import types
import telebot.apihelper
import json
import time

# --- Helper Functions ---
def load_data():
    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Ensure all keys exist, including 'ready_numbers'
            if 'sh_services' not in data:
                data['sh_services'] = {}
            if 'countries' not in data:
                data['countries'] = {}
            if 'states' not in data:
                data['states'] = {}
            if 'active_requests' not in data:
                data['active_requests'] = {}
            if 'ready_numbers' not in data:
                data['ready_numbers'] = []
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        # Create a new data structure with all necessary keys if the file doesn't exist or is corrupted
        return {'users': {}, 'states': {}, 'countries': {}, 'active_requests': {}, 'sh_services': {}, 'ready_numbers': []}

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

def setup_admin_handlers(bot, DEVELOPER_ID, viotp_client, smsman_api, tiger_sms_client):

    def show_admin_menu(chat_id, message_id=None):
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton('إحصائيات البوت 📊', callback_data='bot_stats'), types.InlineKeyboardButton('إدارة المستخدمين 👥', callback_data='manage_users'))
        markup.row(types.InlineKeyboardButton('إضافة رصيد 💰', callback_data='add_balance'), types.InlineKeyboardButton('خصم رصيد 💸', callback_data='deduct_balance'))
        markup.row(types.InlineKeyboardButton('إدارة الأرقام الجاهزة 🔢', callback_data='ready_numbers_menu'))
        markup.row(types.InlineKeyboardButton('إضافة دولة 🌐', callback_data='add_country'), types.InlineKeyboardButton('حذف دولة ❌', callback_data='delete_country'))
        markup.row(types.InlineKeyboardButton('عرض الطلبات النشطة 📞', callback_data='view_active_requests'), types.InlineKeyboardButton('إلغاء جميع الطلبات 🚫', callback_data='cancel_all_requests'))
        markup.row(types.InlineKeyboardButton('إرسال رسالة جماعية 📣', callback_data='broadcast_message'), types.InlineKeyboardButton('الكشف عن أرصدة المواقع 💳', callback_data='show_api_balance_menu'))
        markup.row(types.InlineKeyboardButton('إدارة الرشق 🚀', callback_data='sh_admin_menu'))
        
        text_message = "أهلاً بك في لوحة تحكم المشرف!"
        if message_id:
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text_message, reply_markup=markup)
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in str(e):
                    bot.send_message(chat_id, text_message, reply_markup=markup)
        else:
            bot.send_message(chat_id, text_message, reply_markup=markup)

    @bot.message_handler(func=lambda message: message.from_user.id == DEVELOPER_ID)
    def handle_admin_messages(message):
        chat_id = message.chat.id
        user_id = message.from_user.id
        
        data_file = load_data()
        state = data_file.get('states', {}).get(str(user_id))
    
        if message.text in ['/start', '/admin']:
            show_admin_menu(chat_id)
            return
        
        # --- Existing state handlers ---
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
                    bot.send_message(target_id, f"🎉 تم إضافة {amount} روبل إلى رصيدك من قبل المشرف!")
                except telebot.apihelper.ApiException as e:
                    bot.send_message(chat_id, f"✅ تم إضافة الرصيد بنجاح، لكن لا يمكن إرسال رسالة للمستخدم: {e}")

                del data_file['states'][str(user_id)]
                save_data(data_file)
                bot.send_message(chat_id, f"✅ تم إضافة {amount} روبل إلى المستخدم ذو الآيدي: {target_id}")
            except ValueError:
                bot.send_message(chat_id, "❌ المبلغ الذي أدخلته غير صحيح. يرجى إدخال رقم.")
        
        elif state and state.get('step') == 'waiting_for_deduct_coin_id':
            target_id = message.text
            data_file['states'][str(user_id)]['target_id'] = target_id
            data_file['states'][str(user_id)]['step'] = 'waiting_for_deduct_coin_amount'
            save_data(data_file)
            bot.send_message(chat_id, "تم حفظ الآيدي. الآن أرسل **المبلغ** الذي تريد خصم رصيد منه.")
        
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
                bot.send_message(chat_id, f"✅ تم خصم {amount} روبل من المستخدم ذو الآيدي: {target_id}")
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

                data_file = load_data()
                if service not in data_file['countries']:
                    data_file['countries'][service] = {}
                if app_id not in data_file['countries'][service]:
                    data_file['countries'][service][app_id] = {}
                
                data_file['countries'][service][app_id][country_code] = {'name': country_name, 'price': custom_price}
                
                del data_file['states'][str(user_id)]
                save_data(data_file)
                bot.send_message(chat_id, f"✅ تم إضافة الدولة **{country_name}** بالرمز **{country_code}** والسعر **{custom_price}** روبل بنجاح لخدمة **{service}**!", parse_mode='Markdown')
            except ValueError:
                bot.send_message(chat_id, "❌ السعر الذي أدخلته غير صحيح. يرجى إدخال رقم.")
        
        elif state and state.get('step') == 'waiting_for_check_user_id':
            target_id = message.text
            users_data = load_users()
            user_info = users_data.get(str(target_id))
            if user_info:
                balance = user_info.get('balance', 0)
                bot.send_message(chat_id, f"👤 **معلومات المستخدم:**\n\n**الآيدي:** `{target_id}`\n**الرصيد:** `{balance}` روبل", parse_mode='Markdown')
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
                    f"**الرصيد:** `{user_info.get('balance', 0)}` روبل\n"
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

        elif state and state.get('step') == 'waiting_for_sh_service_name':
            service_name = message.text
            data_file['states'][str(user_id)]['service_name'] = service_name
            data_file['states'][str(user_id)]['step'] = 'waiting_for_sh_service_price'
            save_data(data_file)
            bot.send_message(chat_id, "أرسل **سعر الخدمة** بالروبل.")

        elif state and state.get('step') == 'waiting_for_sh_service_price':
            try:
                service_price = int(message.text)
                service_name = state.get('service_name')
                data_file = load_data()
                data_file['sh_services'][service_name] = service_price
                save_data(data_file)
                bot.send_message(chat_id, f"✅ تم إضافة خدمة الرشق `{service_name}` بسعر `{service_price}` روبل بنجاح!")
                del data_file['states'][str(user_id)]
                save_data(data_file)
            except ValueError:
                bot.send_message(chat_id, "❌ السعر غير صحيح. يرجى إدخال رقم.")
        
        # --- Ready Numbers state handlers ---
        elif state and state.get('step') == 'waiting_for_ready_number_details':
            try:
                lines = message.text.split('\n')
                details = {}
                for line in lines:
                    if ':' in line:
                        key, value = line.split(':', 1)
                        details[key.strip()] = value.strip()
                
                number = details.get('الرقم')
                app = details.get('التطبيق')
                price_str = details.get('السعر')
                
                if not all([number, app, price_str]):
                    raise ValueError("Missing details")
                
                price = int(price_str)
                
                data_file = load_data()
                data_file['ready_numbers'].append({
                    'number': number,
                    'app': app,
                    'price': price,
                    'status': 'available'
                })
                save_data(data_file)
                
                bot.send_message(chat_id, "✅ تم إضافة الرقم الجاهز بنجاح.")
                del data_file['states'][str(user_id)]
                save_data(data_file)
            except (ValueError, IndexError):
                bot.send_message(chat_id, "❌ تنسيق غير صحيح. يرجى استخدام النموذج المحدد: `الرقم: ...\nالتطبيق: ...\nالسعر: ...`")

    @bot.callback_query_handler(func=lambda call: call.from_user.id == DEVELOPER_ID)
    def handle_admin_callbacks(call):
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        message_id = call.message.message_id
        data = call.data
        
        data_file = load_data()
        users_data = load_users()
        
        if data == 'admin_main_menu':
            show_admin_menu(chat_id, message_id)
            return
        
        elif data == 'manage_users':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('عرض رصيد مستخدم 💰', callback_data='check_user_balance'))
            markup.row(types.InlineKeyboardButton('عرض معلومات مستخدم 👤', callback_data='get_user_info'))
            markup.row(types.InlineKeyboardButton('إرسال رسالة لمستخدم ✉️', callback_data='send_message_to_user'))
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='admin_main_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="👥 اختر إجراء لإدارة المستخدمين:", reply_markup=markup)
            return
        
        # --- Ready Numbers Callbacks ---
        elif data == 'ready_numbers_menu':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('➕ إضافة رقم جاهز', callback_data='add_ready_number'))
            markup.row(types.InlineKeyboardButton('➖ حذف رقم جاهز', callback_data='delete_ready_number'))
            markup.row(types.InlineKeyboardButton('🔙 رجوع', callback_data='admin_main_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="🔢 *إدارة الأرقام الجاهزة:*", parse_mode='Markdown', reply_markup=markup)
        
        elif data == 'add_ready_number':
            data_file['states'][str(user_id)] = {'step': 'waiting_for_ready_number_details'}
            save_data(data_file)
            bot.send_message(chat_id, "يرجى إرسال تفاصيل الرقم الجاهز بالتنسيق التالي:\n\n`الرقم: ...\nالتطبيق: ...\nالسعر: ...`")

        elif data == 'delete_ready_number':
            data_file = load_data()
            ready_numbers = data_file.get('ready_numbers', [])
            if not ready_numbers:
                bot.send_message(chat_id, "❌ لا توجد أرقام جاهزة لحذفها.")
                return
            
            markup = types.InlineKeyboardMarkup()
            for i, num_data in enumerate(ready_numbers):
                markup.row(types.InlineKeyboardButton(f"❌ حذف {num_data.get('number', 'غير متوفر')}", callback_data=f'confirm_delete_ready_{i}'))
            markup.row(types.InlineKeyboardButton('🔙 رجوع', callback_data='ready_numbers_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="اختر الرقم الذي تريد حذفه:", reply_markup=markup)

        elif data.startswith('confirm_delete_ready_'):
            index_to_delete = int(data.split('_')[-1])
            data_file = load_data()
            ready_numbers = data_file.get('ready_numbers', [])
            
            if 0 <= index_to_delete < len(ready_numbers):
                deleted_number = ready_numbers.pop(index_to_delete)
                save_data(data_file)
                bot.send_message(chat_id, f"✅ تم حذف الرقم `{deleted_number.get('number', 'غير متوفر')}` بنجاح.")
                try:
                    # Refresh the menu
                    call.data = 'delete_ready_number'
                    handle_admin_callbacks(call)
                except Exception:
                    pass
            else:
                bot.send_message(chat_id, "❌ الرقم المحدد غير موجود.")
        
        # --- Existing callbacks ---
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
            markup.row(types.InlineKeyboardButton('Tiger SMS', callback_data='add_country_service_tigersms'))
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='admin_main_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text='🌐 اختر الخدمة لإضافة دولة:', reply_markup=markup)
        elif data == 'delete_country':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('ViOTP', callback_data='delete_country_service_viotp'))
            markup.row(types.InlineKeyboardButton('SMS.man', callback_data='delete_country_service_smsman'))
            markup.row(types.InlineKeyboardButton('Tiger SMS', callback_data='delete_country_service_tigersms'))
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='admin_main_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text='🌐 اختر الخدمة لحذف دولة:', reply_markup=markup)
        elif data == 'bot_stats':
            total_users = len(load_users())
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
            markup.row(types.InlineKeyboardButton('كشف رصيد Tiger SMS', callback_data='get_tigersms_balance'))
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='show_api_balance_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="💰 اختر الموقع الذي تريد كشف رصيده:", reply_markup=markup)
        
        elif data == 'get_viotp_balance':
            try:
                viotp_balance_data = viotp_client.get_balance()
                if viotp_balance_data and viotp_balance_data.get('success'):
                    viotp_balance = viotp_balance_data['data']['balance']
                    message = f"💰 رصيد ViOTP الحالي: *{viotp_balance}* روبل."
                else:
                    message = "❌ فشل الاتصال. يرجى التأكد من مفتاح API أو إعدادات الشبكة."
            except Exception as e:
                message = f"❌ حدث خطأ: {e}"
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='show_api_balance_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message, parse_mode='Markdown', reply_markup=markup)
        
        elif data == 'get_smsman_balance':
            try:
                smsman_balance = smsman_api['get_smsman_balance']()
                message = f"💰 رصيد SMS.man الحالي:\n• SMS.man: *{smsman_balance}* روبل." if smsman_balance is not False else "❌ فشل الاتصال. يرجى التأكد من مفتاح API أو إعدادات الشبكة."
            except Exception as e:
                message = f"❌ حدث خطأ: {e}"
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='show_api_balance_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message, parse_mode='Markdown', reply_markup=markup)
            
        elif data == 'get_tigersms_balance':
            try:
                tiger_sms_balance = tiger_sms_client.get_balance()
                if tiger_sms_balance and tiger_sms_balance.get('success'):
                    message = f"💰 رصيد Tiger SMS الحالي: *{tiger_sms_balance.get('balance')}* روبل."
                else:
                    message = f"❌ فشل الاتصال. {tiger_sms_balance.get('error', 'خطأ غير معروف')}" if tiger_sms_balance else "❌ فشل الاتصال. يرجى التحقق من المفتاح."
            except Exception as e:
                message = f"❌ حدث خطأ: {e}"
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='show_api_balance_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message, parse_mode='Markdown', reply_markup=markup)
        
        elif data.startswith('add_country_service_'):
            service = data.split('_')[3]
            markup = types.InlineKeyboardMarkup()
            if service == 'viotp':
                app_map = {'2': 'واتساب 💬', '3': 'تليجرام 📢', '4': 'فيسبوك 🏆', '5': 'إنستقرام 🎥', '6': 'تويتر 🚀', '7': 'تيكتوك 🎬', '8': 'قوقل 🌐', '9': 'إيمو 🐦', '11': 'سناب 🐬', '12': 'OK 🌟', '16': 'Viber 📲', '13': 'حراج 🛍', '14': 'السيرفر العام ☑️'}
            elif service == 'smsman':
                app_map = {'2': 'واتساب 💬', '3': 'تليجرام 📢', '4': 'فيسبوك 🏆', '5': 'إنستقرام 🎥', '6': 'تويتر 🚀', '7': 'تيكتوك 🎬', '8': 'قوقل 🌐', '9': 'إيمو 🐦', '11': 'سناب 🐬', '12': 'OK 🌟', '16': 'Viber 📲', '13': 'حراج 🛍', '14': 'السيرفر العام ☑️'}
            elif service == 'tigersms':
                app_map = {'wa': 'واتسأب 💬', 'tg': 'تيليجرام 📢', 'fb': 'فيسبوك 🏆', 'ig': 'إنستقرام 🎥', 'tw': 'تويتر 🚀', 'tt': 'تيكتوك 🎬', 'go': 'قوقل 🌐', 'sn': 'سناب 🐬', 'ds': 'ديسكورد 🎮', 'td': 'تيندر ❤️', 'ub': 'أوبر 🚕', 'ok': 'أوكي 🌟', 'li': 'لاين 📲', 'am': 'أمازون 🛒'}
            
            for app_id, app_name in app_map.items():
                markup.row(types.InlineKeyboardButton(f'{app_name}', callback_data=f"add_country_app_{service}_{app_id}"))
            
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='add_country'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text='📱 اختر التطبيق:', reply_markup=markup)
        
        elif data.startswith('add_country_app_'):
            parts = data.split('_')
            service = parts[3]
            app_id = parts[4]
            page = int(parts[6]) if len(parts) > 6 else 1

            try:
                api_countries = {}
                if service == 'viotp':
                    api_services_data = viotp_client.get_services()
                    if api_services_data and api_services_data.get('success') and 'data' in api_services_data:
                        for item in api_services_data['data']:
                            if str(item.get('service_id')) == str(app_id):
                                for country in item.get('countries', []):
                                    api_countries[str(country['country_code'])] = {'name': country['country_name'], 'price': country['price']}
                                break
                elif service == 'smsman':
                    api_countries_list = smsman_api['get_smsman_countries'](app_id)
                    if api_countries_list:
                        for item in api_countries_list:
                            api_countries[item['id']] = {'name': item['name'], 'price': item['price']}
                elif service == 'tigersms':
                    api_countries_list = tiger_sms_client.get_countries(app_id)
                    if api_countries_list and api_countries_list.get('success'):
                        for item in api_countries_list.get('countries', []):
                            api_countries[item['country_code']] = {'name': item['country_name'], 'price': item['price']}

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
                price_text = f" - السعر: {info.get('price', 'غير متاح')} روبل" if 'price' in info else ''
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
            service = parts[2]
            app_id = parts[3]
            country_code = parts[4]
            
            try:
                api_countries = {}
                if service == 'viotp':
                    api_services_data = viotp_client.get_services()
                    if api_services_data and api_services_data.get('success') and 'data' in api_services_data:
                        for item in api_services_data['data']:
                            if str(item.get('service_id')) == str(app_id):
                                for country in item.get('countries', []):
                                    api_countries[str(country['country_code'])] = {'name': country['country_name'], 'price': country['price']}
                                break
                elif service == 'smsman':
                    api_countries_list = smsman_api['get_smsman_countries'](app_id)
                    if api_countries_list:
                        for item in api_countries_list:
                            api_countries[item['id']] = {'name': item['name'], 'price': item['price']}
                elif service == 'tigersms':
                    api_countries_list = tiger_sms_client.get_countries(app_id)
                    if api_countries_list and api_countries_list.get('success'):
                        for item in api_countries_list.get('countries', []):
                            api_countries[item['country_code']] = {'name': item['country_name'], 'price': item['price']}
            except Exception as e:
                bot.send_message(chat_id, f'❌ حدث خطأ أثناء الاتصال بالـ API: {e}')
                return
                
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
            bot.send_message(chat_id, f"تم اختيار **{country_name}** بسعر أساسي **{api_price}** روبل.\n\nالآن أرسل **السعر الذي تريد بيعه للمستخدمين**.", parse_mode='Markdown')
        
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

        elif data == 'sh_admin_menu':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('➕ إضافة خدمة رشق', callback_data='add_sh_service'))
            markup.row(types.InlineKeyboardButton('➖ حذف خدمة رشق', callback_data='delete_sh_service'))
            markup.row(types.InlineKeyboardButton('عرض الخدمات 📄', callback_data='view_sh_services'))
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='admin_main_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="🚀 اختر الإجراء لإدارة خدمات الرشق:", reply_markup=markup)

        elif data == 'add_sh_service':
            data_file['states'][str(user_id)] = {'step': 'waiting_for_sh_service_name'}
            save_data(data_file)
            bot.send_message(chat_id, "أرسل **اسم خدمة الرشق** (مثلاً: متابعين انستقرام).")

        elif data == 'delete_sh_service':
            markup = types.InlineKeyboardMarkup()
            sh_services = data_file.get('sh_services', {})
            if not sh_services:
                bot.send_message(chat_id, "❌ لا توجد خدمات رشق لحذفها.")
                return
            for name, price in sh_services.items():
                markup.add(types.InlineKeyboardButton(f"❌ {name} ({price} روبل)", callback_data=f'confirm_delete_sh_{name}'))
            markup.add(types.InlineKeyboardButton('رجوع', callback_data='sh_admin_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="اختر الخدمة التي تريد حذفها:", reply_markup=markup)
        
        elif data.startswith('confirm_delete_sh_'):
            service_name_to_delete = data.split('_', 2)[-1]
            data_file = load_data()
            if service_name_to_delete in data_file.get('sh_services', {}):
                del data_file['sh_services'][service_name_to_delete]
                save_data(data_file)
                bot.send_message(chat_id, f"✅ تم حذف خدمة `{service_name_to_delete}` بنجاح.")
            else:
                bot.send_message(chat_id, "❌ الخدمة غير موجودة.")
            handle_admin_callbacks(call)
        
        elif data == 'view_sh_services':
            sh_services = data_file.get('sh_services', {})
            if not sh_services:
                message = "❌ لا توجد خدمات رشق متاحة حاليًا."
            else:
                message = "📄 **خدمات الرشق المتاحة:**\n\n"
                for name, price in sh_services.items():
                    message += f"• **{name}**: `{price}` روبل\n"
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='sh_admin_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message, parse_mode='Markdown', reply_markup=markup)
        
        elif data.startswith('delete_country_service_'):
            service = data.split('_')[3]
            markup = types.InlineKeyboardMarkup()
            if service == 'viotp':
                app_map = {'2': 'واتساب 💬', '3': 'تليجرام 📢', '4': 'فيسبوك 🏆', '5': 'إنستقرام 🎥', '6': 'تويتر 🚀', '7': 'تيكتوك 🎬', '8': 'قوقل 🌐', '9': 'إيمو 🐦', '11': 'سناب 🐬', '12': 'OK 🌟', '16': 'Viber 📲', '13': 'حراج 🛍', '14': 'السيرفر العام ☑️'}
            elif service == 'smsman':
                app_map = {'2': 'واتساب 💬', '3': 'تليجرام 📢', '4': 'فيسبوك 🏆', '5': 'إنستقرام 🎥', '6': 'تويتر 🚀', '7': 'تيكتوك 🎬', '8': 'قوقل 🌐', '9': 'إيمو 🐦', '11': 'سناب 🐬', '12': 'OK 🌟', '16': 'Viber 📲', '13': 'حراج 🛍', '14': 'السيرفر العام ☑️'}
            elif service == 'tigersms':
                app_map = {'wa': 'واتسأب 💬', 'tg': 'تيليجرام 📢', 'fb': 'فيسبوك 🏆', 'ig': 'إنستقرام 🎥', 'tw': 'تويتر 🚀', 'tt': 'تيكتوك 🎬', 'go': 'قوقل 🌐', 'sn': 'سناب 🐬', 'ds': 'ديسكورد 🎮', 'td': 'تيندر ❤️', 'ub': 'أوبر 🚕', 'ok': 'أوكي 🌟', 'li': 'لاين 📲', 'am': 'أمازون 🛒'}
            
            for app_id, app_name in app_map.items():
                markup.row(types.InlineKeyboardButton(f'{app_name}', callback_data=f'delete_country_app_{service}_{app_id}'))
            
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='delete_country'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text='📱 اختر التطبيق لحذف دولة منه:', reply_markup=markup)

        elif data.startswith('delete_country_app_'):
            parts = data.split('_')
            service, app_id = parts[3], parts[4]
            page = int(parts[6]) if len(parts) > 6 else 1

            local_countries = load_data().get('countries', {}).get(service, {}).get(app_id, {})
            if not local_countries:
                bot.send_message(chat_id, '❌ لا توجد دول مضافة لحذفها لهذا التطبيق.')
                return

            items_per_page = 10
            countries_chunked = list(local_countries.items())
            total_pages = (len(countries_chunked) + items_per_page - 1) // items_per_page
            start_index = (page - 1) * items_per_page
            end_index = start_index + items_per_page
            current_countries = countries_chunked[start_index:end_index]
            
            markup = types.InlineKeyboardMarkup()
            for code, info in current_countries:
                markup.row(types.InlineKeyboardButton(f"❌ {info.get('name', 'غير معروف')}", callback_data=f"confirm_delete_country_{service}_{app_id}_{code}"))
            
            nav_buttons = []
            if page > 1:
                nav_buttons.append(types.InlineKeyboardButton('◀️ السابق', callback_data=f'delete_country_app_{service}_{app_id}_page_{page - 1}'))
            if page < total_pages:
                nav_buttons.append(types.InlineKeyboardButton('التالي ▶️', callback_data=f'delete_country_app_{service}_{app_id}_page_{page + 1}'))
            if nav_buttons:
                markup.row(*nav_buttons)
            
            markup.row(types.InlineKeyboardButton('رجوع', callback_data=f'delete_country_service_{service}'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"اختر الدولة التي تريد حذفها: (صفحة {page}/{total_pages})", reply_markup=markup)

        elif data.startswith('confirm_delete_country_'):
            parts = data.split('_')
            service, app_id, country_code = parts[3], parts[4], parts[5]
            
            data_file = load_data()
            if service in data_file.get('countries', {}) and app_id in data_file['countries'][service] and country_code in data_file['countries'][service][app_id]:
                country_name = data_file['countries'][service][app_id][country_code]['name']
                del data_file['countries'][service][app_id][country_code]
                if not data_file['countries'][service][app_id]:
                    del data_file['countries'][service][app_id]
                if not data_file['countries'][service]:
                    del data_file['countries'][service]
                save_data(data_file)
                bot.send_message(chat_id, f"✅ تم حذف الدولة **{country_name}** بنجاح.")
            else:
                bot.send_message(chat_id, "❌ لم يتم العثور على هذه الدولة في قائمة الدول المضافة.")
            
            handle_admin_callbacks(call)

    # Note: This function is defined only once to avoid conflicts
    def show_admin_menu(chat_id, message_id=None):
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton('إحصائيات البوت 📊', callback_data='bot_stats'), types.InlineKeyboardButton('إدارة المستخدمين 👥', callback_data='manage_users'))
        markup.row(types.InlineKeyboardButton('إضافة رصيد 💰', callback_data='add_balance'), types.InlineKeyboardButton('خصم رصيد 💸', callback_data='deduct_balance'))
        markup.row(types.InlineKeyboardButton('إدارة الأرقام الجاهزة 🔢', callback_data='ready_numbers_menu'))
        markup.row(types.InlineKeyboardButton('إضافة دولة 🌐', callback_data='add_country'), types.InlineKeyboardButton('حذف دولة ❌', callback_data='delete_country'))
        markup.row(types.InlineKeyboardButton('عرض الطلبات النشطة 📞', callback_data='view_active_requests'), types.InlineKeyboardButton('إلغاء جميع الطلبات 🚫', callback_data='cancel_all_requests'))
        markup.row(types.InlineKeyboardButton('إرسال رسالة جماعية 📣', callback_data='broadcast_message'), types.InlineKeyboardButton('الكشف عن أرصدة المواقع 💳', callback_data='show_api_balance_menu'))
        markup.row(types.InlineKeyboardButton('إدارة الرشق 🚀', callback_data='sh_admin_menu'))
        
        text_message = "أهلاً بك في لوحة تحكم المشرف!"
        if message_id:
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text_message, reply_markup=markup)
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in str(e):
                    bot.send_message(chat_id, text_message, reply_markup=markup)
        else:
            bot.send_message(chat_id, text_message, reply_markup=markup)
