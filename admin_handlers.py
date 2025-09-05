import telebot
from telebot import types
import json
import os
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

def setup_admin_handlers(bot, DEVELOPER_ID, data_file, users_data, viotp_client, smsman_api, tiger_sms_client):
    
    admin_states = {}

    def is_admin(user_id):
        return user_id == DEVELOPER_ID

    def show_admin_menu(chat_id):
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton('إحصائيات البوت 📊', callback_data='bot_stats'), types.InlineKeyboardButton('إدارة المستخدمين 👥', callback_data='manage_users'))
        markup.row(types.InlineKeyboardButton('إضافة رصيد 💰', callback_data='add_balance'), types.InlineKeyboardButton('خصم رصيد 💸', callback_data='deduct_balance'))
        markup.row(types.InlineKeyboardButton('إضافة دولة 🌐', callback_data='add_country'), types.InlineKeyboardButton('حذف دولة ❌', callback_data='delete_country'))
        markup.row(types.InlineKeyboardButton('عرض الطلبات النشطة 📞', callback_data='view_active_requests'), types.InlineKeyboardButton('إلغاء جميع الطلبات 🚫', callback_data='cancel_all_requests'))
        markup.row(types.InlineKeyboardButton('إرسال رسالة جماعية 📣', callback_data='broadcast_message'), types.InlineKeyboardButton('الكشف عن أرصدة المواقع 💳', callback_data='show_api_balance_menu'))
        markup.row(types.InlineKeyboardButton('إدارة الرشق 🚀', callback_data='sh_admin_menu'))
        bot.send_message(chat_id, "أهلاً بك في لوحة تحكم المشرف!", reply_markup=markup)

    @bot.message_handler(commands=['start', 'admin'], func=lambda message: is_admin(message.from_user.id), pass_bot=True)
    def handle_admin_start(message, bot):
        show_admin_menu(message.chat.id)

    @bot.callback_query_handler(func=lambda call: is_admin(call.from_user.id) and call.data in ['admin_menu', 'back_to_admin'], pass_bot=True)
    def handle_admin_back(call, bot):
        show_admin_menu(call.message.chat.id)

    @bot.callback_query_handler(func=lambda call: is_admin(call.from_user.id), pass_bot=True)
    def handle_admin_callbacks(call, bot):
        chat_id = call.message.chat.id
        data = call.data
        message_id = call.message.message_id
        
        if data == 'bot_stats':
            users_count = len(users_data)
            active_requests_count = len(data_file.get('active_requests', {}))
            bot.edit_message_text(f"📊 إحصائيات البوت:\n\nعدد المستخدمين: {users_count}\nعدد الطلبات النشطة: {active_requests_count}", chat_id, message_id)
        
        elif data == 'manage_users':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('إضافة رصيد', callback_data='add_balance'), types.InlineKeyboardButton('خصم رصيد', callback_data='deduct_balance'))
            markup.row(types.InlineKeyboardButton('بحث عن مستخدم', callback_data='search_user'))
            markup.row(types.InlineKeyboardButton('🔙 رجوع', callback_data='back_to_admin'))
            bot.edit_message_text("👥 قسم إدارة المستخدمين:", chat_id, message_id, reply_markup=markup)

        elif data == 'add_balance':
            admin_states[chat_id] = 'awaiting_add_balance'
            bot.send_message(chat_id, "أرسل لي معرف المستخدم (user ID) والمبلغ الذي تريد إضافته، مفصولين بمسافة.\nمثال: `123456789 50`")

        elif data == 'deduct_balance':
            admin_states[chat_id] = 'awaiting_deduct_balance'
            bot.send_message(chat_id, "أرسل لي معرف المستخدم (user ID) والمبلغ الذي تريد خصمه، مفصولين بمسافة.\nمثال: `123456789 20`")
        
        elif data == 'sh_admin_menu':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('إضافة خدمة رشق ➕', callback_data='add_sh_service'))
            markup.row(types.InlineKeyboardButton('حذف خدمة رشق ➖', callback_data='delete_sh_service'))
            markup.row(types.InlineKeyboardButton('🔙 رجوع', callback_data='back_to_admin'))
            bot.edit_message_text("🚀 قسم إدارة خدمات الرشق:", chat_id, message_id, reply_markup=markup)

        elif data == 'add_sh_service':
            admin_states[chat_id] = 'awaiting_sh_service_details'
            bot.send_message(chat_id, "أرسل لي اسم الخدمة والسعر، مفصولين بمسافة.\nمثال: `رشق انستقرام 1000 متابع 50`")
        
        elif data == 'delete_sh_service':
            sh_services = data_file.get('sh_services', {})
            if not sh_services:
                bot.send_message(chat_id, "❌ لا توجد خدمات رشق لحذفها.")
                return
            
            markup = types.InlineKeyboardMarkup()
            for name in sh_services.keys():
                markup.row(types.InlineKeyboardButton(name, callback_data=f'del_sh_{name}'))
            markup.row(types.InlineKeyboardButton('🔙 رجوع', callback_data='back_to_admin'))
            bot.edit_message_text("اختر الخدمة التي تريد حذفها:", chat_id, message_id, reply_markup=markup)

        elif data.startswith('del_sh_'):
            service_name = data.split('_', 2)[-1]
            if service_name in data_file.get('sh_services', {}):
                del data_file['sh_services'][service_name]
                save_data(data_file)
                bot.send_message(chat_id, f"✅ تم حذف خدمة `{service_name}` بنجاح.")
            else:
                bot.send_message(chat_id, "❌ الخدمة غير موجودة.")
        
        elif data == 'add_country':
            admin_states[chat_id] = 'awaiting_country_details'
            bot.send_message(chat_id, "أرسل لي اسم الخدمة، رمز الدولة، التطبيق، الاسم، والسعر، مفصولين بمسافة.\nمثال: `viotp sa 2 السعودية 5`")

        elif data == 'delete_country':
            admin_states[chat_id] = 'awaiting_country_to_delete'
            bot.send_message(chat_id, "أرسل لي اسم الخدمة، ورمز الدولة، ورمز التطبيق، مفصولين بمسافة.\nمثال: `viotp sa 2`")

        elif data == 'view_active_requests':
            active_requests = data_file.get('active_requests', {})
            if not active_requests:
                bot.send_message(chat_id, "📞 لا توجد طلبات نشطة حالياً.")
                return
            
            message_text = "📞 الطلبات النشطة:\n\n"
            for request_id, req_info in active_requests.items():
                user_id_req = req_info.get('user_id')
                phone_number = req_info.get('phone_number')
                service_name = req_info.get('service')
                message_text += f"**ID الطلب:** `{request_id}`\n"
                message_text += f"**رقم الهاتف:** `{phone_number}`\n"
                message_text += f"**الخدمة:** `{service_name}`\n"
                message_text += f"**معرف المستخدم:** `{user_id_req}`\n\n"
            
            bot.send_message(chat_id, message_text, parse_mode='Markdown')

        elif data == 'cancel_all_requests':
            active_requests = data_file.get('active_requests', {})
            if not active_requests:
                bot.send_message(chat_id, "🚫 لا توجد طلبات نشطة لإلغائها.")
                return

            for request_id, req_info in list(active_requests.items()):
                service = req_info['service']
                try:
                    if service == 'viotp':
                        viotp_client.cancel_request(request_id)
                    elif service == 'smsman':
                        smsman_api.cancel_smsman_request(request_id)
                    elif service == 'tigersms':
                        tiger_sms_client.cancel_request(request_id)
                except Exception as e:
                    print(f"Failed to cancel request {request_id}: {e}")
                
                user_id_from_request = req_info['user_id']
                price_to_restore = req_info['price']
                
                users_data = load_users()
                if str(user_id_from_request) in users_data:
                    users_data[str(user_id_from_request)]['balance'] += price_to_restore
                    save_users(users_data)

            data_file['active_requests'] = {}
            save_data(data_file)
            bot.send_message(chat_id, "✅ تم إلغاء جميع الطلبات النشطة واستعادة الرصيد للمستخدمين.")

        elif data == 'broadcast_message':
            admin_states[chat_id] = 'awaiting_broadcast_message'
            bot.send_message(chat_id, "📣 أرسل لي الرسالة التي تريد إرسالها لجميع المستخدمين:")

        elif data == 'show_api_balance_menu':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('رصيد VIOTP', callback_data='check_viotp_balance'))
            markup.row(types.InlineKeyboardButton('رصيد SMSMAN', callback_data='check_smsman_balance'))
            markup.row(types.InlineKeyboardButton('رصيد TigerSMS', callback_data='check_tigersms_balance'))
            markup.row(types.InlineKeyboardButton('🔙 رجوع', callback_data='back_to_admin'))
            bot.edit_message_text("💳 اختر الموقع الذي تريد الكشف عن رصيده:", chat_id, message_id, reply_markup=markup)

        elif data == 'check_viotp_balance':
            balance = viotp_client.get_balance()
            bot.send_message(chat_id, f"💰 رصيد VIOTP هو: `{balance}`")

        elif data == 'check_smsman_balance':
            balance = smsman_api.get_smsman_balance(smsman_api.API_KEY)
            bot.send_message(chat_id, f"💰 رصيد SMSMAN هو: `{balance}`")
        
        elif data == 'check_tigersms_balance':
            balance = tiger_sms_client.get_balance()
            bot.send_message(chat_id, f"💰 رصيد TigerSMS هو: `{balance}`")


    @bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.chat.id in admin_states, pass_bot=True)
    def handle_admin_text_input(message, bot):
        chat_id = message.chat.id
        state = admin_states.get(chat_id)
        
        if state == 'awaiting_add_balance':
            try:
                user_id, amount = message.text.split()
                user_id = int(user_id)
                amount = float(amount)
                users_data = load_users()
                if str(user_id) in users_data:
                    users_data[str(user_id)]['balance'] += amount
                    save_users(users_data)
                    bot.send_message(chat_id, f"✅ تم إضافة `{amount}` روبل إلى رصيد المستخدم `{user_id}`.")
                else:
                    bot.send_message(chat_id, "❌ المستخدم غير موجود.")
            except (ValueError, IndexError):
                bot.send_message(chat_id, "❌ صيغة خاطئة. يرجى إرسال معرف المستخدم والمبلغ بشكل صحيح.")
            finally:
                del admin_states[chat_id]

        elif state == 'awaiting_deduct_balance':
            try:
                user_id, amount = message.text.split()
                user_id = int(user_id)
                amount = float(amount)
                users_data = load_users()
                if str(user_id) in users_data:
                    users_data[str(user_id)]['balance'] -= amount
                    save_users(users_data)
                    bot.send_message(chat_id, f"✅ تم خصم `{amount}` روبل من رصيد المستخدم `{user_id}`.")
                else:
                    bot.send_message(chat_id, "❌ المستخدم غير موجود.")
            except (ValueError, IndexError):
                bot.send_message(chat_id, "❌ صيغة خاطئة. يرجى إرسال معرف المستخدم والمبلغ بشكل صحيح.")
            finally:
                del admin_states[chat_id]

        elif state == 'awaiting_sh_service_details':
            try:
                parts = message.text.split()
                service_price = float(parts[-1])
                service_name = " ".join(parts[:-1])
                data_file = load_data()
                data_file['sh_services'][service_name] = service_price
                save_data(data_file)
                bot.send_message(chat_id, f"✅ تم إضافة خدمة `{service_name}` بسعر `{service_price}` روبل.")
            except (ValueError, IndexError):
                bot.send_message(chat_id, "❌ صيغة خاطئة. يرجى إرسال اسم الخدمة والسعر بشكل صحيح.")
            finally:
                del admin_states[chat_id]
        
        elif state == 'awaiting_country_details':
            try:
                parts = message.text.split()
                service, country_code, app_id, country_name = parts[0], parts[1], parts[2], parts[3]
                price = float(parts[-1])
                
                data_file = load_data()
                if service not in data_file['countries']:
                    data_file['countries'][service] = {}
                if app_id not in data_file['countries'][service]:
                    data_file['countries'][service][app_id] = {}
                
                data_file['countries'][service][app_id][country_code] = {'name': country_name, 'price': price}
                save_data(data_file)
                bot.send_message(chat_id, f"✅ تم إضافة الدولة `{country_name}` بنجاح.")
            except (ValueError, IndexError):
                bot.send_message(chat_id, "❌ صيغة خاطئة. يرجى إرسال البيانات بشكل صحيح.\nمثال: `viotp sa 2 السعودية 5`")
            finally:
                del admin_states[chat_id]

        elif state == 'awaiting_country_to_delete':
            try:
                service, country_code, app_id = message.text.split()
                data_file = load_data()
                if service in data_file['countries'] and app_id in data_file['countries'][service] and country_code in data_file['countries'][service][app_id]:
                    del data_file['countries'][service][app_id][country_code]
                    save_data(data_file)
                    bot.send_message(chat_id, f"✅ تم حذف الدولة بنجاح.")
                else:
                    bot.send_message(chat_id, "❌ الدولة غير موجودة.")
            except (ValueError, IndexError):
                bot.send_message(chat_id, "❌ صيغة خاطئة. يرجى إرسال البيانات بشكل صحيح.\nمثال: `viotp sa 2`")
            finally:
                del admin_states[chat_id]
                
        elif state == 'awaiting_broadcast_message':
            users_data = load_users()
            for user_id_str in users_data:
                try:
                    bot.send_message(int(user_id_str), message.text)
                except Exception as e:
                    print(f"Failed to send broadcast to user {user_id_str}: {e}")
            
            bot.send_message(chat_id, "✅ تم إرسال الرسالة لجميع المستخدمين.")
            del admin_states[chat_id]
