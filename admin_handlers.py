from telebot import types
import json
import time
from datetime import datetime
import os
import requests

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
            if 'active_requests' not in data:
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

def setup_admin_handlers(bot, DEVELOPER_ID, viotp_client, smsman_api, tiger_sms_client):
    
    @bot.message_handler(commands=['admin', 'panel'])
    def handle_admin_panel_command(message):
        user_id = message.from_user.id
        if user_id == DEVELOPER_ID:
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('➕ إضافة دولة', callback_data='add_country'),
                       types.InlineKeyboardButton('❌ حذف دولة', callback_data='delete_country'))
            markup.row(types.InlineKeyboardButton('💰 إضافة رصيد لمستخدم', callback_data='add_balance'))
            markup.row(types.InlineKeyboardButton('➕ إضافة خدمة رشق', callback_data='add_sh_service'),
                       types.InlineKeyboardButton('❌ حذف خدمة رشق', callback_data='delete_sh_service'))
            markup.row(types.InlineKeyboardButton('📊 عرض احصائيات البوت', callback_data='view_stats'))
            markup.row(types.InlineKeyboardButton('تحديث بيانات API', callback_data='update_api'))
            # هذا هو الزر الجديد لاختبار الشراء
            markup.row(types.InlineKeyboardButton('⚙️ اختبار شراء رقم', callback_data='admin_test_buy'))
            bot.send_message(user_id, 'مرحباً بك يا مشرف، اختر أحد الأوامر:', reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.from_user.id == DEVELOPER_ID)
    def handle_admin_callbacks(call):
        chat_id = call.message.chat.id
        message_id = call.message.message_id
        data = call.data

        if data == 'admin_test_buy':
            bot.send_message(chat_id, "جارٍ محاولة شراء رقم تجريبي من SMS.man...")
            service = 'smsman'
            app_id = '2'  # WhatsApp
            country_code = '1'  # Russia
            
            # هذا هو الجزء الحاسم الذي سيخبرنا بالسبب
            result = smsman_api['request_smsman_number'](app_id, country_code)
            
            # هذا السطر سيُظهر لنا الرد الفعلي من API في سجلات Render
            print(f"ADMIN DEBUG - SMS.man API Response: {result}")
            
            if result and result.get('success'):
                phone_number = result.get('number', 'غير متوفر')
                bot.send_message(chat_id, f"✅ تم شراء رقم تجريبي بنجاح!\n\n**الرقم:** {phone_number}", parse_mode='Markdown')
            else:
                error_message = result.get('message', result.get('error', 'رسالة الخطأ غير متوفرة.'))
                bot.send_message(chat_id, f"❌ فشل شراء الرقم التجريبي.\n\n**رسالة الخطأ من السيرفر:** `{error_message}`\n\nيرجى مراجعة سجلات Render للحصول على تفاصيل.", parse_mode='Markdown')
            return

        elif data == 'add_country':
            bot.send_message(chat_id, 'أرسل لي بيانات الدولة الجديدة بالصيغة التالية:\n`service;app_id;country_code;price;name`\n\nمثال: `smsman;2;1;10;روسيا`')
            bot.register_next_step_handler(call.message, add_country_step)
        
        elif data == 'delete_country':
            bot.send_message(chat_id, 'أرسل لي بيانات الدولة التي تريد حذفها بالصيغة التالية:\n`service;app_id;country_code`\n\nمثال: `smsman;2;1`')
            bot.register_next_step_handler(call.message, delete_country_step)

        elif data == 'add_balance':
            bot.send_message(chat_id, 'أرسل لي معرف المستخدم (ID) والمبلغ الذي تريد إضافته بالصيغة التالية:\n`user_id;amount`\n\nمثال: `123456789;50`')
            bot.register_next_step_handler(call.message, add_balance_step)

        elif data == 'add_sh_service':
            bot.send_message(chat_id, 'أرسل لي اسم خدمة الرشق والسعر بالصيغة التالية:\n`name;price`\n\nمثال: `رشق انستقرام;5`')
            bot.register_next_step_handler(call.message, add_sh_service_step)

        elif data == 'delete_sh_service':
            bot.send_message(chat_id, 'أرسل لي اسم خدمة الرشق التي تريد حذفها:\n\nمثال: `رشق انستقرام`')
            bot.register_next_step_handler(call.message, delete_sh_service_step)

        elif data == 'view_stats':
            users_data = load_users()
            total_users = len(users_data)
            total_balance = sum(user.get('balance', 0) for user in users_data.values())
            
            # API balances
            viotp_balance = viotp_client.get_balance().get('balance', 'N/A')
            smsman_balance = smsman_api['get_balance_smsman']().get('balance', 'N/A')
            tigersms_balance = tiger_sms_client.get_balance().get('balance', 'N/A')
            
            stats_text = (
                f"📊 **إحصائيات البوت:**\n"
                f"• عدد المستخدمين: `{total_users}`\n"
                f"• إجمالي أرصدة المستخدمين: `{total_balance}` روبل\n\n"
                f"**أرصدة خدمات الـ API:**\n"
                f"• ViOTP: `{viotp_balance}` روبل\n"
                f"• SMS.man: `{smsman_balance}` روبل\n"
                f"• TigerSMS: `{tigersms_balance}` روبل"
            )
            bot.send_message(chat_id, stats_text, parse_mode='Markdown')

        elif data == 'update_api':
            bot.send_message(chat_id, "بدء تحديث بيانات الدول والأسعار. قد يستغرق الأمر بضع لحظات...")
            
            data_file = load_data()
            data_file['countries'] = {}
            
            # --- ViOTP Update ---
            viotp_services = requests.get(f'https://api.viotp.com/get/services?token={os.environ.get("VIOTP_KEY")}').json()
            if viotp_services.get('success'):
                for service in viotp_services['data']:
                    app_id = str(service['id'])
                    viotp_countries = requests.get(f'https://api.viotp.com/get/country?token={os.environ.get("VIOTP_KEY")}&serviceId={app_id}').json()
                    if viotp_countries.get('success'):
                        for country in viotp_countries['data']:
                            country_code = str(country['id'])
                            if 'viotp' not in data_file['countries']: data_file['countries']['viotp'] = {}
                            if app_id not in data_file['countries']['viotp']: data_file['countries']['viotp'][app_id] = {}
                            data_file['countries']['viotp'][app_id][country_code] = {
                                'name': country['name'],
                                'price': country['price']
                            }
            # --- SMS.man Update ---
            smsman_services_data = smsman_api['get_services_smsman']()
            if not smsman_services_data.get('error'):
                for service_name, info in smsman_services_data.items():
                    app_id = info['id']
                    if 'smsman' not in data_file['countries']: data_file['countries']['smsman'] = {}
                    if app_id not in data_file['countries']['smsman']: data_file['countries']['smsman'][app_id] = {}
                    
                    smsman_countries_data = smsman_api['get_countries_smsman']()
                    if not smsman_countries_data.get('error'):
                        for country_name, country_info in smsman_countries_data.items():
                            country_id = country_info['id']
                            try:
                                price_response = requests.get(f"https://api.sms-man.com/v1/getPrice?token={os.environ.get('SMSMAN_KEY')}&country_id={country_id}&service_id={app_id}")
                                price_response.raise_for_status()
                                price_data = price_response.json()
                                price = price_data.get('price', {}).get(str(country_id))
                                
                                if price:
                                    data_file['countries']['smsman'][app_id][str(country_id)] = {
                                        'name': country_name,
                                        'price': price
                                    }
                            except requests.exceptions.RequestException as e:
                                print(f"Error getting SMS.man price for {country_name}: {e}")

            # --- TigerSMS Update ---
            tiger_services_data = tiger_sms_client._request("getApps")
            if tiger_services_data.get('success'):
                for service in tiger_services_data.get('data', {}):
                    app_id = service['shortName']
                    tiger_countries_data = tiger_sms_client.get_countries()
                    if tiger_countries_data.get('success'):
                        for country in tiger_countries_data.get('data', []):
                            country_code = country['countryCode']
                            price_response = tiger_sms_client._request("getPrice", params={'appId': app_id, 'countryCode': country_code})
                            if price_response.get('success') and price_response.get('price'):
                                if 'tigersms' not in data_file['countries']: data_file['countries']['tigersms'] = {}
                                if app_id not in data_file['countries']['tigersms']: data_file['countries']['tigersms'][app_id] = {}
                                data_file['countries']['tigersms'][app_id][country_code] = {
                                    'name': country['countryName'],
                                    'price': price_response['price']
                                }
            
            save_data(data_file)
            bot.send_message(chat_id, "✅ تم تحديث بيانات الدول والأسعار بنجاح.")


    # Handler for next step operations
    def add_country_step(message):
        try:
            service, app_id, country_code, price, name = message.text.split(';')
            data_file = load_data()
            if service not in data_file['countries']: data_file['countries'][service] = {}
            if app_id not in data_file['countries'][service]: data_file['countries'][service][app_id] = {}
            data_file['countries'][service][app_id][country_code] = {'price': float(price), 'name': name}
            save_data(data_file)
            bot.send_message(message.chat.id, f"✅ تم إضافة الدولة `{name}` بنجاح.")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ حدث خطأ: {e}\nالرجاء التحقق من الصيغة الصحيحة.")

    def delete_country_step(message):
        try:
            service, app_id, country_code = message.text.split(';')
            data_file = load_data()
            if service in data_file['countries'] and app_id in data_file['countries'][service] and country_code in data_file['countries'][service][app_id]:
                del data_file['countries'][service][app_id][country_code]
                save_data(data_file)
                bot.send_message(message.chat.id, "✅ تم حذف الدولة بنجاح.")
            else:
                bot.send_message(message.chat.id, "❌ الدولة غير موجودة.")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ حدث خطأ: {e}\nالرجاء التحقق من الصيغة الصحيحة.")

    def add_balance_step(message):
        try:
            user_id, amount = message.text.split(';')
            users_data = load_users()
            if str(user_id) in users_data:
                users_data[str(user_id)]['balance'] += float(amount)
                save_users(users_data)
                bot.send_message(message.chat.id, f"✅ تم إضافة `{amount}` روبل إلى رصيد المستخدم `{user_id}`.")
            else:
                bot.send_message(message.chat.id, "❌ المستخدم غير موجود.")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ حدث خطأ: {e}\nالرجاء التحقق من الصيغة الصحيحة.")
    
    def add_sh_service_step(message):
        try:
            name, price = message.text.split(';')
            data_file = load_data()
            data_file['sh_services'][name.strip()] = float(price.strip())
            save_data(data_file)
            bot.send_message(message.chat.id, f"✅ تم إضافة خدمة الرشق '{name}' بسعر {price} روبل.")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ حدث خطأ: {e}\nالرجاء التحقق من الصيغة الصحيحة.")

    def delete_sh_service_step(message):
        try:
            name = message.text.strip()
            data_file = load_data()
            if name in data_file['sh_services']:
                del data_file['sh_services'][name]
                save_data(data_file)
                bot.send_message(message.chat.id, f"✅ تم حذف خدمة الرشق '{name}' بنجاح.")
            else:
                bot.send_message(message.chat.id, "❌ خدمة الرشق غير موجودة.")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ حدث خطأ: {e}")
