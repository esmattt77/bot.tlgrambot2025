from telebot import types
import telebot.apihelper
import json
import time
import logging
from collections import defaultdict

# تهيئة التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# *** مهم: يجب تحديد آيدي قناة الإشعارات هنا إذا كنت تريد نشر الإضافة تلقائيًا ***
# SIM_CHANNEL_ID = -100xxxxxxxxxx # آيدي القناة الرقمي
SIM_CHANNEL_ID = -1001158537466 # اتركه None إذا لم يكن لديك قناة للإشعارات

# 💡 التعديل: قاموس ترجمة أسماء الخدمات والفئات من الإنجليزية إلى العربية
SERVICE_TRANSLATIONS = {
    "Instagram": "إنستقرام",
    "Facebook": "فيسبوك",
    "YouTube": "يوتيوب",
    "TikTok": "تيك توك",
    "Twitter": "تويتر",
    "Telegram": "تليجرام",
    "Spotify": "سبوتيفاي",
    "Website Traffic": "زيارات مواقع",
    "Views": "مشاهدات",
    "Followers": "متابعين",
    "Likes": "إعجابات",
    "Comments": "تعليقات",
    "Shares": "مشاركات",
    "Members": "أعضاء",
    "Reactions": "تفاعلات",
    # يمكنك إضافة المزيد من الكلمات الشائعة هنا
}

def translate_service_name(name):
    """دالة لترجمة الكلمات الرئيسية في اسم الخدمة إلى العربية."""
    for en, ar in SERVICE_TRANSLATIONS.items():
        name = name.replace(en, ar)
    return name

# 💡 --- MongoDB IMPORTS ---
from db_manager import (
    get_user_balance, 
    update_user_balance, 
    get_bot_data, 
    save_bot_data, 
    get_all_users_keys,
    get_user_doc 
)

# ⭐️ التغيير الأول: استبدال viotp_client بـ smmkings_client
def setup_admin_handlers(bot, DEVELOPER_ID, smmkings_client, smsman_api, tiger_sms_client):

    # دالة مساعدة لتحديث الأرقام الجاهزة في المخزون الداخلي (تعتمد على save_bot_data)
    def update_ready_numbers_stock(stock_data=None, delete_key=None):
        data_file = get_bot_data()
        # نستخدم ready_numbers_stock كاسم للحقل في db_manager.py
        stock = data_file.get('ready_numbers_stock', {}) 
        
        if stock_data:
            # إضافة أو تحديث رقم
            stock.update(stock_data)
        elif delete_key:
            # حذف رقم
            stock.pop(delete_key, None)
            
        # ✅ تحديث حقل المخزون فقط
        save_bot_data({'ready_numbers_stock': stock})
        return stock

    @bot.message_handler(func=lambda message: message.from_user.id == DEVELOPER_ID)
    def handle_admin_messages(message):
        chat_id = message.chat.id
        user_id = message.from_user.id
        
        # 💡 التحميل من MongoDB
        data_file = get_bot_data() 
        state = data_file.get('states', {}).get(str(user_id))
    
        if message.text in ['/start', '/admin']:
            show_admin_menu(chat_id)
            return
        
        if state and state.get('step') == 'waiting_for_add_coin_id':
            target_id = message.text
            data_file.setdefault('states', {})[str(user_id)] = {'step': 'waiting_for_add_coin_amount', 'target_id': target_id}
            save_bot_data({'states': data_file.get('states', {})})
            bot.send_message(chat_id, "تم حفظ الآيدي. الآن أرسل **المبلغ** الذي تريد إضافته للمستخدم.")
        
        elif state and state.get('step') == 'waiting_for_add_coin_amount':
            try:
                amount = int(message.text)
                if amount <= 0:
                    raise ValueError
                target_id = state.get('target_id')
                
                update_user_balance(target_id, amount, is_increment=True)
                
                try:
                    bot.send_message(target_id, f"🎉 تم إضافة {amount} روبل إلى رصيدك من قبل المشرف!")
                except telebot.apihelper.ApiException:
                    pass

                del data_file['states'][str(user_id)]
                save_bot_data({'states': data_file.get('states', {})})
                bot.send_message(chat_id, f"✅ تم إضافة {amount} روبل إلى المستخدم ذو الآيدي: {target_id}")
            except ValueError:
                bot.send_message(chat_id, "❌ المبلغ الذي أدخلته غير صحيح. يرجى إدخال رقم صحيح أكبر من صفر.")
        
        elif state and state.get('step') == 'waiting_for_deduct_coin_id':
            target_id = message.text
            data_file.setdefault('states', {})[str(user_id)] = {'step': 'waiting_for_deduct_coin_amount', 'target_id': target_id}
            save_bot_data({'states': data_file.get('states', {})})
            bot.send_message(chat_id, "تم حفظ الآيدي. الآن أرسل **المبلغ** الذي تريد خصمه من المستخدم.")
        
        elif state and state.get('step') == 'waiting_for_deduct_coin_amount':
            try:
                amount = int(message.text)
                if amount <= 0:
                    raise ValueError
                target_id = state.get('target_id')
                
                update_user_balance(target_id, -amount, is_increment=True)
                
                del data_file['states'][str(user_id)]
                save_bot_data({'states': data_file.get('states', {})})
                bot.send_message(chat_id, f"✅ تم خصم {amount} روبل من المستخدم ذو الآيدي: {target_id}")
            except ValueError:
                bot.send_message(chat_id, "❌ المبلغ الذي أدخلته غير صحيح. يرجى إدخال رقم صحيح أكبر من صفر.")

        elif state and state.get('step') == 'waiting_for_broadcast_message':
            user_ids_list = get_all_users_keys()
            for uid in user_ids_list:
                try:
                    bot.send_message(uid, message.text)
                except telebot.apihelper.ApiException:
                    continue 
            del data_file['states'][str(user_id)]
            save_bot_data({'states': data_file.get('states', {})})
            bot.send_message(chat_id, "📣 اكتمل البث بنجاح!")
        
        # ⚠️ ملاحظة: تم إبقاء هذا الجزء لخدمات الأرقام الافتراضية (SMS/Tiger)
        elif state and state.get('step') == 'waiting_for_admin_price':
            try:
                custom_price = int(message.text)
                if custom_price <= 0:
                    raise ValueError
                    
                country_name = state.get('country_name')
                country_code = state.get('country_code')
                service = state.get('service')
                app_id = state.get('app_id')

                data_file.setdefault('countries', {})
                data_file['countries'].setdefault(service, {})
                data_file['countries'][service].setdefault(app_id, {})
                
                data_file['countries'][service][app_id][country_code] = {'name': country_name, 'price': custom_price}
                
                del data_file['states'][str(user_id)]
                save_bot_data({'states': data_file.get('states', {}), 'countries': data_file.get('countries', {})}) 
                bot.send_message(chat_id, f"✅ تم إضافة الدولة **{country_name}** بالرمز **{country_code}** والسعر **{custom_price}** روبل بنجاح لخدمة **{service}**!", parse_mode='Markdown')
            except ValueError:
                bot.send_message(chat_id, "❌ السعر الذي أدخلته غير صحيح. يرجى إدخال رقم صحيح أكبر من صفر.")
        
        elif state and state.get('step') == 'waiting_for_check_user_id':
            target_id = message.text
            
            balance = get_user_balance(target_id)
            
            if balance is not None:
                bot.send_message(chat_id, f"👤 **معلومات المستخدم:**\n\n**الآيدي:** `{target_id}`\n**الرصيد:** `{balance}` روبل", parse_mode='Markdown')
            else:
                bot.send_message(chat_id, "❌ لم يتم العثور على مستخدم بهذا الآيدي.")
            
            del data_file['states'][str(user_id)]
            save_bot_data({'states': data_file.get('states', {})})

        elif state and state.get('step') == 'waiting_for_get_user_info_id':
            target_id = message.text
            
            user_info = get_user_doc(target_id)
            
            if user_info:
                message_text = (
                    f"👤 **تفاصيل المستخدم:**\n"
                    f"**الآيدي:** `{user_info.get('_id', 'غير متوفر')}`\n"
                    f"**الرصيد:** `{user_info.get('balance', 0)}` روبل\n"
                    f"**الاسم:** `{user_info.get('first_name', 'غير متوفر')}`\n"
                    f"**اسم المستخدم:** `@{user_info.get('username', 'غير متوفر')}`\n"
                    f"**تاريخ الانضمام:** `{user_info.get('join_date', 'غير متوفر')}`"
                )
                bot.send_message(chat_id, message_text, parse_mode='Markdown')
            else:
                bot.send_message(chat_id, "❌ لم يتم العثور على مستخدم بهذا الآيدي.")
                
            del data_file['states'][str(user_id)]
            save_bot_data({'states': data_file.get('states', {})})

        elif state and state.get('step') == 'waiting_for_send_message_to_user_id':
            target_id = message.text
            data_file.setdefault('states', {})[str(user_id)] = {'step': 'waiting_for_message_to_send', 'target_id': target_id}
            save_bot_data({'states': data_file.get('states', {})})
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
                save_bot_data({'states': data_file.get('states', {})})

        elif state and state.get('step') == 'waiting_for_sh_service_name':
            # هذا الجزء لم يعد مستخدماً في النظام الجديد المعتمد على جلب API
            bot.send_message(chat_id, "❌ تم إيقاف هذا الأسلوب. يرجى استخدام 'جلب/تحديث خدمات SMMKings'.")
        
        elif state and state.get('step') == 'waiting_for_sh_service_price':
            # هذا الجزء لم يعد مستخدماً في النظام الجديد المعتمد على جلب API
            bot.send_message(chat_id, "❌ تم إيقاف هذا الأسلوب. يرجى استخدام 'جلب/تحديث خدمات SMMKings'.")

        # 🆕 --- معالج استقبال السعر الجديد وتحديث قاعدة البيانات لخدمات SMM ---
        elif state and state.get('step') == 'waiting_for_new_smm_price':
            try:
                new_price = int(message.text)
                if new_price <= 0:
                    raise ValueError
                
                service_id = state.get('service_id')
                service_name = state.get('service_name')
                
                # 💡 استخدام الحقل الموحد: 'smmkings_services'
                smmkings_services = data_file.get('smmkings_services', {})
                if service_id in smmkings_services:
                    smmkings_services[service_id]['user_price'] = new_price
                    save_bot_data({'smmkings_services': smmkings_services})
                    
                    bot.send_message(chat_id, f"✅ تم تحديث سعر خدمة **{service_name}** إلى `{new_price}` روبل بنجاح!")
                else:
                    bot.send_message(chat_id, "❌ لم يتم العثور على الخدمة لتحديث سعرها.")
                
                del data_file['states'][str(user_id)]
                save_bot_data({'states': data_file.get('states', {})})

            except ValueError:
                bot.send_message(chat_id, "❌ السعر الجديد غير صحيح. يرجى إدخال رقم صحيح أكبر من صفر.")
        
        # 🆕 --- معالج إضافة رقم جاهز (الخطوة 2: استقبال جميع المعلومات) ---
        elif state and state.get('step') == 'waiting_for_ready_number_full_info':
            
            # نفترض أن كل حقل مفصول بسطر جديد، ونحاول استخراج القيم
            lines = message.text.strip().split('\n')
            
            # تنظيف السطور وإزالة الأرقام والرموز الزائدة
            extracted_data = []
            for line in lines:
                # نحذف الأجزاء الثابتة مثل "1⃣ الاسم :-" (نفترض وجود ":-")
                # إذا لم يكن هناك فاصل ":-" نأخذ السطر كما هو
                if ":-" in line:
                    clean_value = line.split(":-")[-1].strip()
                else:
                    clean_value = line.strip()

                extracted_data.append(clean_value)

            # يجب أن يكون لدينا 6 قيم على الأقل
            if len(extracted_data) < 6:
                bot.send_message(chat_id, "❌ لم تقم بإرسال جميع الحقول الستة بشكل صحيح. أعد المحاولة. (تأكد من فصل كل حقل بسطر جديد)", 
                                 reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('رجوع', callback_data='ready_numbers_menu')))
                return
            
            try:
                # تعيين المتغيرات بناءً على ترتيب الإدخال
                country, price_str, app_state, note, number, code = extracted_data[:6]
                
                price = int(price_str)
                if price <= 0:
                    raise ValueError("Price must be a positive integer.")
                
                # تنظيف الرقم والتأكد من الصيغة
                if not number.replace('+', '').isdigit() or len(number.replace('+', '')) < 8:
                    raise ValueError("Phone number format is incorrect.")
                
                # إزالة المسافات من الكود
                code = code.replace('-', '').strip()
                
                # 🔑 مفتاح التخزين في المخزون هو رقم الهاتف
                stock_key = number
                
                # تحديث المخزون في قاعدة البيانات
                update_ready_numbers_stock(stock_data={
                    stock_key: {
                        'country': country,
                        'price': price,
                        'state': app_state, # حالة الرقم (واتساب، تيليجرام...)
                        'note': note,
                        'number': number,
                        'code': code,
                        'added_by': str(user_id),
                        'added_date': time.time()
                    }
                })
                
                # حذف الحالة من المشرف
                del data_file['states'][str(user_id)]
                save_bot_data({'states': data_file.get('states', {})}) 
                
                # 🔔 إرسال إشعار للمشرف
                num_hidden = number[:len(number) - 4] + "••••"
                message_to_admin = (
                    f"✅ تم إضافة رقم جاهز بنجاح:\n\n"
                    f"☎️ ⪼ الدولة: {country}\n"
                    f"💸 ⪼ السعر: {price} روبل\n"
                    f"☎️ ⪼ الرقم: {num_hidden}\n"
                    f"✳️ ⪼ الحالة: *{app_state}*"
                )
                
                bot.send_message(chat_id, message_to_admin, 
                                          parse_mode='Markdown',
                                          reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('رجوع', callback_data='ready_numbers_menu')))
                
                # 📢 إرسال إشعار للقناة إذا تم تعيينها
                if SIM_CHANNEL_ID:
                    message_to_channel = (
                        f"*⌯ تم إضافة رقم جديد الى الأرقام الجاهزة! ☑️*\n\n"
                        f"☎️ ⪼ الدولة: {country}\n"
                        f"💸 ⪼ السعر: ₽ {price}.00\n"
                        f"☎️ ⪼ الرقم: {num_hidden}\n"
                        f"✳️ ⪼ الحالة: *{app_state}*"
                    )
                    bot.send_message(SIM_CHANNEL_ID, message_to_channel, parse_mode='Markdown')
                
            except ValueError as e:
                error_message = f"❌ خطأ في الإدخال. يرجى التأكد من أن السعر رقم صحيح والرقم بصيغة صحيحة. ({e})"
                bot.send_message(chat_id, error_message, 
                                 reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('رجوع', callback_data='ready_numbers_menu')))
            except Exception as e:
                bot.send_message(chat_id, f"❌ حدث خطأ غير متوقع أثناء الحفظ: {e}", 
                                 reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('رجوع', callback_data='ready_numbers_menu')))
        

    @bot.callback_query_handler(func=lambda call: call.from_user.id == DEVELOPER_ID)
    def handle_admin_callbacks(call):
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        message_id = call.message.message_id
        data = call.data
        
        data_file = get_bot_data() 
        state = data_file.get('states', {}).get(str(user_id))

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
        
        elif data == 'add_balance':
            data_file.setdefault('states', {})[str(user_id)] = {'step': 'waiting_for_add_coin_id'}
            save_bot_data({'states': data_file.get('states', {})})
            bot.send_message(chat_id, '➕ أرسل **آيدي المستخدم** الذي تريد إضافة رصيد له.')
        elif data == 'deduct_balance':
            data_file.setdefault('states', {})[str(user_id)] = {'step': 'waiting_for_deduct_coin_id'}
            save_bot_data({'states': data_file.get('states', {})})
            bot.send_message(chat_id, '➖ أرسل **آيدي المستخدم** الذي تريد خصم رصيد منه.')
        elif data == 'add_country':
            # 💡 التعديل هنا: حذف ViOTP من القائمة
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('SMS.man', callback_data='add_country_service_smsman'))
            markup.row(types.InlineKeyboardButton('Tiger SMS', callback_data='add_country_service_tigersms'))
            # 🆕 إضافة زر جلب خدمات SMMKings 
            markup.row(types.InlineKeyboardButton('جلب خدمات SMMKings 🚀', callback_data='fetch_smmkings_services'))
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='admin_main_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text='🌐 اختر الخدمة لإضافة دولة:', reply_markup=markup)
        elif data == 'delete_country':
            # 💡 التعديل هنا: حذف ViOTP من القائمة
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('SMS.man', callback_data='delete_country_service_smsman'))
            markup.row(types.InlineKeyboardButton('Tiger SMS', callback_data='delete_country_service_tigersms'))
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='admin_main_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text='🌐 اختر الخدمة لحذف دولة:', reply_markup=markup)
        elif data == 'bot_stats':
            total_users = len(get_all_users_keys())
            message = f"📊 إحصائيات البوت:\nعدد المستخدمين: *{total_users}*\n"
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='admin_main_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message, parse_mode='Markdown', reply_markup=markup)
        elif data == 'broadcast_message':
            data_file.setdefault('states', {})[str(user_id)] = {'step': 'waiting_for_broadcast_message'}
            save_bot_data({'states': data_file.get('states', {})})
            bot.send_message(chat_id, '📣 أرسل رسالتك للبث.')
        
        # 🆕 --- قائمة كشف الأرصدة (حذف ViOTP وإضافة SMMKings) ---
        elif data == 'show_api_balance_menu':
            markup = types.InlineKeyboardMarkup()
            # markup.row(types.InlineKeyboardButton('كشف رصيد ViOTP', callback_data='get_viotp_balance')) # محذوف
            markup.row(types.InlineKeyboardButton('كشف رصيد SMMKings 🚀', callback_data='get_smmkings_balance')) # جديد
            markup.row(types.InlineKeyboardButton('كشف رصيد SMS.man', callback_data='get_smsman_balance'))
            markup.row(types.InlineKeyboardButton('كشف رصيد Tiger SMS', callback_data='get_tigersms_balance'))
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='admin_main_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="💰 اختر الموقع الذي تريد كشف رصيده:", reply_markup=markup)
        
        # 🆕 --- معالج كشف رصيد SMMKings ---
        elif data == 'get_smmkings_balance':
            smmkings_balance_data = smmkings_client.get_balance()
            if smmkings_balance_data.get('success'):
                balance = smmkings_balance_data.get('balance')
                currency = smmkings_balance_data.get('currency', 'USD')
                message = f"💰 رصيد SMMKings الحالي: *{balance}* {currency}."
            else:
                error_msg = smmkings_balance_data.get('error', 'خطأ غير معروف')
                message = f"❌ فشل الاتصال بـ SMMKings. يرجى التأكد من مفتاح API: {error_msg}"
            
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='show_api_balance_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message, parse_mode='Markdown', reply_markup=markup)
            
        elif data == 'get_smsman_balance':
            # 💡 تم تغيير طريقة استدعاء الدالة لضمان التكامل
            smsman_balance = smsman_api['get_smsman_balance']()
            message = f"💰 رصيد SMS.man الحالي: *{smsman_balance}* روبل." if smsman_balance is not False else "❌ فشل الاتصال. يرجى التأكد من مفتاح API أو إعدادات الشبكة."
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='show_api_balance_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message, parse_mode='Markdown', reply_markup=markup)
            
        elif data == 'get_tigersms_balance':
            tiger_sms_balance = tiger_sms_client.get_balance()
            if tiger_sms_balance.get('success'):
                message = f"💰 رصيد Tiger SMS الحالي: *{tiger_sms_balance.get('balance')}* روبل."
            else:
                message = f"❌ فشل الاتصال. {tiger_sms_balance.get('error', 'خطأ غير معروف')}"
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='show_api_balance_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message, parse_mode='Markdown', reply_markup=markup)
        
        # 🆕 --- معالج جلب خدمات SMMKings API وتخزينها (معالجة لخطأ 414) ---
        elif data == 'fetch_smmkings_services':
            # 💡 يتم تعديل الرسالة فوراً قبل جلب البيانات لتجنب مشكلة الـ Timeout
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="🔄 جاري جلب خدمات SMMKings... (قد يستغرق وقتاً)")
            except telebot.apihelper.ApiTelegramException:
                pass # تجاهل إذا كانت الرسالة قد تم تعديلها بالفعل أو غير قابلة للتعديل

            services_data = smmkings_client.get_services(force_reload=True) # 💡 فرض تحديث البيانات
            
            if services_data and services_data.get('services'):
                # 💡 الاستجابة هي قاموس مفتاحه هو Service ID
                services_dict = services_data['services']
                smm_services_storage = {}
                count = 0
                
                # 💡 التخزين في 'smmkings_services' بدلاً من 'sh_services' لتجنب التداخل
                for service_id, service in services_dict.items():
                    
                    # 💡 التعديل: تطبيق دالة الترجمة هنا على اسم الخدمة والفئة
                    translated_category = translate_service_name(service['category'])
                    translated_name = translate_service_name(service['name'])
                    
                    # 💡 دمج الاسم المترجم والفئة المترجمة
                    final_service_name = f"[{translated_category}] {translated_name}"
                    
                    # نستخدم 'service' (المعرف الرقمي) كمفتاح التخزين الأساسي
                    service_id = str(service['service']) 
                    
                    # يتم تخزين سعر API الأساسي (rate) والحدود الدنيا والقصوى
                    smm_services_storage[service_id] = {
                        'name': final_service_name, # 💡 تخزين الاسم المعرب
                        'api_rate': float(service['rate']),
                        'min': int(service['min']),
                        'max': int(service['max']),
                        # 💡 تعيين سعر بيع مبدئي أو الحفاظ على السعر القديم إذا وجد
                        'user_price': data_file.get('smmkings_services', {}).get(service_id, {}).get('user_price', round(float(service['rate']) * 1.5)), 
                    }
                    count += 1
                
                # حفظ الخدمات في حقل جديد في قاعدة البيانات
                save_bot_data({'smmkings_services': smm_services_storage})
                
                message = f"✅ تم جلب وتخزين {count} خدمة من SMMKings بنجاح.\n\n"
                message += "⚠️ تم تعيين سعر بيع تقريبي مبدئي للخدمات الجديدة. يمكنك تعديله من قائمة إدارة الرشق."
            else:
                error_msg = services_data.get('error', 'خطأ غير معروف') if services_data else 'فشل في الاتصال أو لم يتم إرجاع بيانات.'
                message = f"❌ فشل جلب خدمات SMMKings: {error_msg}"
            
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('رجوع لقائمة الإدارة', callback_data='sh_admin_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message, parse_mode='Markdown', reply_markup=markup)

        elif data.startswith('add_country_service_'):
            service = data.split('_')[3]
            markup = types.InlineKeyboardMarkup()
            
            # --- أزرار التطبيقات (SMS.man) ---
            if service == 'smsman':
                # تم حذف ViOTP
                markup.row(types.InlineKeyboardButton('واتساب 💬', callback_data=f"add_country_app_{service}_2_page_1"))
                markup.row(types.InlineKeyboardButton('تليجرام 📢', callback_data=f"add_country_app_{service}_3_page_1"))
                markup.row(types.InlineKeyboardButton('فيسبوك 🏆', callback_data=f"add_country_app_{service}_4_page_1"))
                markup.row(types.InlineKeyboardButton('إنستقرام 🎥', callback_data=f"add_country_app_{service}_5_page_1"))
                markup.row(types.InlineKeyboardButton('تويتر 🚀', callback_data=f"add_country_app_{service}_6_page_1"))
                markup.row(types.InlineKeyboardButton('تيكتوك 🎬', callback_data=f"add_country_app_{service}_7_page_1"))
                markup.row(types.InlineKeyboardButton('قوقل 🌐', callback_data=f"add_country_app_{service}_8_page_1"))
                markup.row(types.InlineKeyboardButton('إيمو 🐦', callback_data=f"add_country_app_{service}_9_page_1"))
                markup.row(types.InlineKeyboardButton('سناب 🐬', callback_data=f"add_country_app_{service}_11_page_1"))
                markup.row(types.InlineKeyboardButton('OK 🌟', callback_data=f"add_country_app_{service}_12_page_1"))
                markup.row(types.InlineKeyboardButton('Viber 📲', callback_data=f"add_country_app_{service}_16_page_1"))
                markup.row(types.InlineKeyboardButton('حراج 🛍', callback_data=f"add_country_app_{service}_13_page_1"))
                markup.row(types.InlineKeyboardButton('السيرفر العام ☑️', callback_data=f"add_country_app_{service}_14_page_1"))
            # --- أزرار التطبيقات (Tiger SMS) ---
            elif service == 'tigersms':
                markup.row(types.InlineKeyboardButton('واتسأب 💬', callback_data=f"add_country_app_{service}_wa_page_1"))
                markup.row(types.InlineKeyboardButton('تيليجرام 📢', callback_data=f"add_country_app_{service}_tg_page_1"))
                markup.row(types.InlineKeyboardButton('فيسبوك 🏆', callback_data=f"add_country_app_{service}_fb_page_1"))
                markup.row(types.InlineKeyboardButton('إنستقرام 🎥', callback_data=f"add_country_app_{service}_ig_page_1"))
                markup.row(types.InlineKeyboardButton('تويتر 🚀', callback_data=f"add_country_app_{service}_tw_page_1"))
                markup.row(types.InlineKeyboardButton('تيكتوك 🎬', callback_data=f"add_country_app_{service}_tt_page_1"))
                markup.row(types.InlineKeyboardButton('قوقل 🌐', callback_data=f'add_country_app_{service}_go_page_1'))
                markup.row(types.InlineKeyboardButton('سناب 🐬', callback_data=f'add_country_app_{service}_sn_page_1'))
                markup.row(types.InlineKeyboardButton('ديسكورد 🎮', callback_data=f'add_country_app_{service}_ds_page_1'))
                markup.row(types.InlineKeyboardButton('تيندر ❤️', callback_data=f'add_country_app_{service}_td_page_1'))
                markup.row(types.InlineKeyboardButton('أوبر 🚕', callback_data=f'add_country_app_{service}_ub_page_1'))
                markup.row(types.InlineKeyboardButton('أوكي 🌟', callback_data=f'add_country_app_{service}_ok_page_1'))
                markup.row(types.InlineKeyboardButton('لاين 📲', callback_data=f'add_country_app_{service}_li_page_1'))
                markup.row(types.InlineKeyboardButton('أمازون 🛒', callback_data=f'add_country_app_{service}_am_page_1'))
            
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='add_country'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text='📱 اختر التطبيق:', reply_markup=markup)
        
        elif data.startswith('add_country_app_'):
            parts = data.split('_')
            service = parts[3]
            app_id = parts[4]
            page = int(parts[6])

            try:
                # 💡 جلب الدول من API (تم حذف ViOTP)
                if service == 'smsman':
                    api_countries = smsman_api['get_smsman_countries'](app_id)
                elif service == 'tigersms':
                    api_countries = tiger_sms_client.get_countries(app_id)
                else: # ViOTP محذوف، لكن للتأكد
                    api_countries = {}
            except Exception as e:
                # تم تغيير رسالة الخطأ
                bot.send_message(chat_id, f'❌ حدث خطأ أثناء الاتصال بواجهة API ({service}): {e}')
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
            
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='add_country'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"اختر الدولة التي تريد إضافتها: (صفحة {page}/{total_pages})", reply_markup=markup)

        elif data.startswith('select_country_'):
            parts = data.split('_')
            service = parts[2]
            app_id = parts[3]
            country_code = parts[4]

            # 💡 جلب معلومات الدولة مرة أخرى للحصول على الاسم والسعر الأساسي (تم حذف ViOTP)
            try:
                if service == 'smsman':
                    api_countries = smsman_api['get_smsman_countries'](app_id)
                elif service == 'tigersms':
                    api_countries = tiger_sms_client.get_countries(app_id)
                else:
                    api_countries = {}
            except Exception as e:
                bot.send_message(chat_id, f'❌ حدث خطأ أثناء الاتصال بالـ API: {e}')
                return
                
            country_info = api_countries.get(country_code, {})
            country_name = country_info.get('name')
            api_price = country_info.get('price', 0)
            
            data_file.setdefault('states', {})[str(user_id)] = {
                'step': 'waiting_for_admin_price',
                'service': service,
                'app_id': app_id,
                'country_code': country_code,
                'country_name': country_name
            }
            save_bot_data({'states': data_file.get('states', {})})
            bot.send_message(chat_id, f"تم اختيار **{country_name}** بسعر أساسي **{api_price}** روبل.\n\nالآن أرسل **السعر الذي تريد بيعه للمستخدمين**.", parse_mode='Markdown')
        
        elif data == 'check_user_balance':
            data_file.setdefault('states', {})[str(user_id)] = {'step': 'waiting_for_check_user_id'}
            save_bot_data({'states': data_file.get('states', {})})
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="💰 أرسل **آيدي المستخدم** للتحقق من رصيده.")
        
        elif data == 'get_user_info':
            data_file.setdefault('states', {})[str(user_id)] = {'step': 'waiting_for_get_user_info_id'}
            save_bot_data({'states': data_file.get('states', {})})
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="👤 أرسل **آيدي المستخدم** للحصول على معلوماته.")
        
        elif data == 'send_message_to_user':
            data_file.setdefault('states', {})[str(user_id)] = {'step': 'waiting_for_send_message_to_user_id'}
            save_bot_data({'states': data_file.get('states', {})})
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="✉️ أرسل **آيدي المستخدم** الذي تريد إرسال رسالة إليه.")

        # 🚀 --- قائمة إدارة خدمات الرشق (SMM) ---
        elif data == 'sh_admin_menu':
            markup = types.InlineKeyboardMarkup()
            # 💡 يتم الآن إدارة الخدمات بشكل أساسي من جلب API ثم تعديلها
            markup.row(types.InlineKeyboardButton('🔄 جلب/تحديث خدمات SMMKings', callback_data='fetch_smmkings_services'))
            markup.row(types.InlineKeyboardButton('✍️ تعديل سعر خدمة SMM', callback_data='edit_smm_service_price')) # وظيفة جديدة
            markup.row(types.InlineKeyboardButton('عرض الخدمات المخزنة 📄', callback_data='view_smmkings_services')) # تم تغيير الـ callback
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='admin_main_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="🚀 اختر الإجراء لإدارة خدمات الرشق:", reply_markup=markup)

        # 🆕 --- معالج عرض خدمات SMMKings (يعرض من قاعدة البيانات) ---
        elif data == 'view_smmkings_services':
            # 💡 استخدام الحقل الموحد: 'smmkings_services'
            smmkings_services = data_file.get('smmkings_services', {})
            
            if not smmkings_services:
                message = "❌ لا توجد خدمات SMMKings مخزنة حاليًا. يرجى جلبها أولاً."
            else:
                # 💡 تقليل حجم الرسالة لتجنب مشكلة الـ 414 في بعض الحالات
                services_list = []
                # 💡 الترتيب الأبجدي حسب اسم الخدمة لتسهيل القراءة
                sorted_services = sorted(smmkings_services.items(), key=lambda item: item[1].get('name', ''))
                
                for service_id, info in sorted_services:
                    services_list.append(
                        f"• **{info.get('name', 'غير معروف')}**\n"
                        f"  - `ID: {service_id}` / `السعر: {info.get('user_price', 'غير محدد')} روبل`\n"
                    )

                message = f"📄 **خدمات SMMKings المتاحة (المخزنة):** ({len(services_list)} خدمة)\n\n"
                # نستخدم فقط أول 25 خدمة في العرض للتلخيص
                message += "\n".join(services_list[:25])
                
                if len(services_list) > 25:
                    message += "\n..."
                message += "\n\nللحصول على التفاصيل الكاملة، استخدم 'تعديل سعر خدمة SMM'."
            
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='sh_admin_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message, parse_mode='Markdown', reply_markup=markup)

        # 🆕 --- بدء تعديل سعر خدمة SMM ---
        elif data == 'edit_smm_service_price':
            # 💡 استخدام الحقل الموحد: 'smmkings_services'
            smmkings_services = data_file.get('smmkings_services', {})
            if not smmkings_services:
                # تغيير edit_message_text إلى send_message لضمان ظهور الرسالة
                bot.send_message(chat_id, "❌ لا توجد خدمات SMMKings مخزنة لتعديلها. يرجى جلبها أولاً.")
                return

            markup = types.InlineKeyboardMarkup()
            # 💡 الترتيب الأبجدي حسب اسم الخدمة لتسهيل البحث
            sorted_services = sorted(smmkings_services.items(), key=lambda item: item[1].get('name', ''))
            
            # 💡 نستخدم جزء من الاسم والسعر الحالي في الزر
            for service_id, info in sorted_services:
                # تقليص طول اسم الخدمة للزر إذا كان طويلاً
                name_short = (info['name'][:30] + '...') if len(info['name']) > 33 else info['name']
                markup.add(types.InlineKeyboardButton(f"✍️ {name_short} ({info.get('user_price', 0)} روبل)", callback_data=f'select_smm_to_edit_{service_id}'))
            
            markup.add(types.InlineKeyboardButton('رجوع', callback_data='sh_admin_menu'))
            # 💡 تغيير الرسالة لتكون واضحة أكثر
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="اختر خدمة SMM التي تريد تعديل سعرها: (مرتبة أبجدياً)", reply_markup=markup)

        # 🆕 --- اختيار الخدمة وبدء طلب السعر الجديد ---
        elif data.startswith('select_smm_to_edit_'):
            service_id = data.split('_')[-1]
            # 💡 استخدام الحقل الموحد: 'smmkings_services'
            smmkings_services = data_file.get('smmkings_services', {})
            service_info = smmkings_services.get(service_id)
            
            if not service_info:
                bot.send_message(chat_id, "❌ لم يتم العثور على الخدمة المطلوبة.")
                return

            data_file.setdefault('states', {})[str(user_id)] = {
                'step': 'waiting_for_new_smm_price', 
                'service_id': service_id,
                'service_name': service_info['name']
            }
            save_bot_data({'states': data_file.get('states', {})})
            
            message_text = (
                f"تم اختيار خدمة: **{service_info['name']}**\n"
                f"السعر الحالي: `{service_info.get('user_price', 'غير محدد')}` روبل.\n"
                f"سعر API الأصلي: `{service_info.get('api_rate', 'غير محدد')}` USD.\n"
                "الآن، أرسل **السعر الجديد** الذي تريد بيع الخدمة به للمستخدمين (بالروبل)."
            )
            bot.send_message(chat_id, message_text, parse_mode='Markdown')
        
        # ⚠️ باقي معالجات الكولباك لـ delete_country و view_active_requests لا تحتاج لتعديل جوهري لأنها لم تكن سبب المشكلة 414
        
        elif data.startswith('delete_country_service_'):
            service = data.split('_')[3]
            markup = types.InlineKeyboardMarkup()
            
            # --- أزرار التطبيقات (SMS.man) ---
            if service == 'smsman':
                # تم حذف ViOTP
                markup.row(types.InlineKeyboardButton('واتساب 💬', callback_data=f"delete_country_app_{service}_2_page_1"))
                markup.row(types.InlineKeyboardButton('تليجرام 📢', callback_data=f"delete_country_app_{service}_3_page_1"))
                markup.row(types.InlineKeyboardButton('فيسبوك 🏆', callback_data=f"delete_country_app_{service}_4_page_1"))
                markup.row(types.InlineKeyboardButton('إنستقرام 🎥', callback_data=f"delete_country_app_{service}_5_page_1"))
                markup.row(types.InlineKeyboardButton('تويتر 🚀', callback_data=f"delete_country_app_{service}_6_page_1"))
                markup.row(types.InlineKeyboardButton('تيكتوك 🎬', callback_data=f"delete_country_app_{service}_7_page_1"))
                markup.row(types.InlineKeyboardButton('قوقل 🌐', callback_data=f"delete_country_app_{service}_8_page_1"))
                markup.row(types.InlineKeyboardButton('إيمو 🐦', callback_data=f"delete_country_app_{service}_9_page_1"))
                markup.row(types.InlineKeyboardButton('سناب 🐬', callback_data=f"delete_country_app_{service}_11_page_1"))
                markup.row(types.InlineKeyboardButton('OK 🌟', callback_data=f"delete_country_app_{service}_12_page_1"))
                markup.row(types.InlineKeyboardButton('Viber 📲', callback_data=f"delete_country_app_{service}_16_page_1"))
                markup.row(types.InlineKeyboardButton('حراج 🛍', callback_data=f"delete_country_app_{service}_13_page_1"))
                markup.row(types.InlineKeyboardButton('السيرفر العام ☑️', callback_data=f"delete_country_app_{service}_14_page_1"))
            # --- أزرار التطبيقات (Tiger SMS) ---
            elif service == 'tigersms':
                markup.row(types.InlineKeyboardButton('واتسأب 💬', callback_data=f"delete_country_app_{service}_wa_page_1"))
                markup.row(types.InlineKeyboardButton('تيليجرام 📢', callback_data=f"delete_country_app_{service}_tg_page_1"))
                markup.row(types.InlineKeyboardButton('فيسبوك 🏆', callback_data=f"delete_country_app_{service}_fb_page_1"))
                markup.row(types.InlineKeyboardButton('إنستقرام 🎥', callback_data=f"delete_country_app_{service}_ig_page_1"))
                markup.row(types.InlineKeyboardButton('تويتر 🚀', callback_data=f"delete_country_app_{service}_tw_page_1"))
                markup.row(types.InlineKeyboardButton('تيكتوك 🎬', callback_data=f"delete_country_app_{service}_tt_page_1"))
                markup.row(types.InlineKeyboardButton('قوقل 🌐', callback_data=f'delete_country_app_{service}_go_page_1'))
                markup.row(types.InlineKeyboardButton('سناب 🐬', callback_data=f'delete_country_app_{service}_sn_page_1'))
                markup.row(types.InlineKeyboardButton('ديسكورد 🎮', callback_data=f'delete_country_app_{service}_ds_page_1'))
                markup.row(types.InlineKeyboardButton('تيندر ❤️', callback_data=f'delete_country_app_{service}_td_page_1'))
                markup.row(types.InlineKeyboardButton('أوبر 🚕', callback_data=f'delete_country_app_{service}_ub_page_1'))
                markup.row(types.InlineKeyboardButton('أوكي 🌟', callback_data=f'delete_country_app_{service}_ok_page_1'))
                markup.row(types.InlineKeyboardButton('لاين 📲', callback_data=f'delete_country_app_{service}_li_page_1'))
                markup.row(types.InlineKeyboardButton('أمازون 🛒', callback_data=f'delete_country_app_{service}_am_page_1'))
            
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='delete_country'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text='📱 اختر التطبيق لحذف دولة منه:', reply_markup=markup)

        elif data.startswith('delete_country_app_'):
            parts = data.split('_')
            service, app_id = parts[3], parts[4]
            page = int(parts[6])

            local_countries = data_file.get('countries', {}).get(service, {}).get(app_id, {})
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
            
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='delete_country_service_{service}'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"اختر الدولة التي تريد حذفها: (صفحة {page}/{total_pages})", reply_markup=markup)

        elif data.startswith('confirm_delete_country_'):
            parts = data.split('_')
            service, app_id, country_code = parts[3], parts[4], parts[5]
            
            data_file = get_bot_data()
            if service in data_file.get('countries', {}) and app_id in data_file['countries'][service] and country_code in data_file['countries'][service][app_id]:
                country_name = data_file['countries'][service][app_id][country_code]['name']
                del data_file['countries'][service][app_id][country_code]
                if not data_file.get('countries', {}).get(service, {}).get(app_id):
                    del data_file['countries'][service][app_id]
                if not data_file.get('countries', {}).get(service):
                    del data_file['countries'][service]
                save_bot_data({'countries': data_file.get('countries', {})})
                bot.send_message(chat_id, f"✅ تم حذف الدولة **{country_name}** بنجاح.")
            else:
                bot.send_message(chat_id, "❌ لم يتم العثور على هذه الدولة في قائمة الدول المضافة.")
            
            # محاولة تحديث القائمة بعد الحذف
            handle_admin_callbacks(call)

        elif data == 'view_active_requests':
            active_requests = data_file.get('active_requests', {})
            if not active_requests:
                message = "📞 لا توجد طلبات نشطة حاليًا."
            else:
                message = "📞 **الطلبات النشطة:**\n\n"
                # 💡 الترتيب حسب وقت الإضافة (الطلب الأحدث أولاً)
                sorted_requests = sorted(active_requests.items(), key=lambda item: item[1].get('request_time', 0), reverse=True)
                
                for user_id, request_data in sorted_requests:
                    message += f"**آيدي المستخدم:** `{user_id}`\n"
                    
                    # 💡 إضافة حقل 'is_smm' أو فحص مزود الخدمة
                    api_service = request_data.get('api_service', 'غير معروف')
                    
                    if api_service == 'smmkings':
                         message += f"**الخدمة (رشق):** {request_data.get('service_name', 'غير معروف')}\n"
                         message += f"**الرابط:** `{request_data.get('link', 'غير متوفر')}`\n"
                         message += f"**الكمية:** `{request_data.get('quantity', 'غير متوفر')}`\n"
                    else:
                        message += f"**الطلب (أرقام):** {request_data.get('service', 'غير معروف')} - {request_data.get('app_name', 'غير معروف')}\n"
                        message += f"**رقم الهاتف:** `{request_data.get('phone_number', 'غير متوفر')}`\n"
                        message += f"**حالة الطلب:** `{request_data.get('status', 'غير معروف')}`\n"
                        
                    message += f"**آيدي الطلب:** `{request_data.get('order_id', 'غير متوفر')}`\n"
                    message += f"**الموقع:** `{api_service}`\n"
                    message += "-------------------\n"
            
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='admin_main_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message, parse_mode='Markdown', reply_markup=markup)

        elif data == 'cancel_all_requests':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('تأكيد إلغاء جميع الطلبات (من السجل فقط) ⚠️', callback_data='confirm_cancel_all_requests'))
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='admin_main_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="⚠️ هل أنت متأكد من رغبتك في حذف جميع الطلبات النشطة من سجل البوت؟\n(هذا لا يلغيها بالضرورة من مواقع API الخارجية)", reply_markup=markup)

        elif data == 'confirm_cancel_all_requests':
            data_file = get_bot_data()
            if 'active_requests' in data_file:
                # 💡 ملاحظة مهمة: يجب تحذير المستخدم هنا بأن هذا يحذف السجل لكل من الأرقام وخدمات SMM.
                data_file['active_requests'] = {}
                save_bot_data({'active_requests': data_file['active_requests']})
                bot.send_message(chat_id, "✅ تم مسح سجل الطلبات النشطة في البوت بنجاح (يشمل الأرقام وخدمات الرشق). تذكر أن تلغيها يدويًا من واجهات API الخارجية إذا لزم الأمر.")
            else:
                bot.send_message(chat_id, "❌ لا توجد طلبات نشطة في السجل لحذفها.")
            handle_admin_callbacks(call)
        
        # 🆕 --- قائمة إدارة الأرقام الجاهزة (يدوياً) ---
        elif data == 'ready_numbers_menu':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('➕ إضافة رقم جاهز', callback_data='add_ready_number_start'))
            markup.row(types.InlineKeyboardButton('➖ حذف رقم جاهز', callback_data='delete_ready_number_start'))
            markup.row(types.InlineKeyboardButton('📄 عرض الأرقام الجاهزة', callback_data='view_ready_numbers_stock'))
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='admin_main_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="🔢 إدارة مخزون الأرقام الجاهزة يدوياً:", reply_markup=markup)

        # 🆕 --- بدء عملية إضافة رقم جاهز (الخطوة 1: تحديد الحالة) - تم التصحيح هنا
        elif data == 'add_ready_number_start':
            data_file.setdefault('states', {}) # ✅ ضمان وجود مفتاح states
            # 💡 تغيير اسم الحالة ليعكس أننا ننتظر جميع البيانات
            data_file['states'][str(user_id)] = {'step': 'waiting_for_ready_number_full_info'}
            save_bot_data({'states': data_file.get('states', {})})
            
            message_prompt = (
                "🔰 - أرسل معلومات الرقم الجاهز بالصيغة التالية (في أسطر متتالية):\n\n"
                "1⃣ الاسم (الدولة/البلد) :-\n"
                "2⃣ السعر :-\n"
                "3⃣ الحالة (واتساب/تيليجرام) :-\n"
                "4⃣ ملاحظة :-\n"
                "5⃣ الرقم :-\n"
                "6⃣ الكود :-\n\n"
                "⚠️ - بعد إرسال الرقم سيتم إضافته مباشرة."
            )
            
            # محاولة تعديل الرسالة
            try:
                bot.edit_message_text(
                    chat_id=chat_id, 
                    message_id=message_id, 
                    text=message_prompt,
                    reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('رجوع', callback_data='ready_numbers_menu'))
                )
            except telebot.apihelper.ApiTelegramException:
                bot.send_message(chat_id, message_prompt, reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('رجوع', callback_data='ready_numbers_menu')))
        
        # 🆕 --- عرض الأرقام الجاهزة في المخزون ---
        elif data == 'view_ready_numbers_stock':
            ready_numbers_stock = data_file.get('ready_numbers_stock', {})
            
            if not ready_numbers_stock:
                message = "❌ لا توجد أرقام جاهزة في المخزون حاليًا."
            else:
                message = "📄 **الأرقام الجاهزة في المخزون:**\n\n"
                # 💡 الترتيب حسب وقت الإضافة (الأحدث أولاً)
                sorted_numbers = sorted(ready_numbers_stock.items(), key=lambda item: item[1].get('added_date', 0), reverse=True)
                
                for phone, info in sorted_numbers:
                    # إخفاء آخر 4 أرقام
                    num_hidden = info.get('number', 'غير متوفر')[:len(info.get('number', '')) - 4] + "••••"
                    message += f"• **الرقم:** `{num_hidden}`\n"
                    message += f"• **السعر:** `{info.get('price', 0)}` روبل\n"
                    message += f"• **الدولة:** `{info.get('country', 'غير متوفر')}`\n"
                    message += f"• **الحالة:** `{info.get('state', 'غير متوفر')}`\n"
                    message += f"• **الملاحظة:** `{info.get('note', 'لا يوجد')}`\n"
                    message += f"• **الكود (للمشرف):** `{info.get('code', 'غير متوفر')}`\n"
                    message += f"• **أضيف بواسطة:** `{info.get('added_by', 'مشرف')}`\n"
                    message += "-------------------\n"
            
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='ready_numbers_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message, parse_mode='Markdown', reply_markup=markup)

        # 🆕 --- بدء عملية حذف رقم جاهز ---
        elif data == 'delete_ready_number_start':
            ready_numbers_stock = data_file.get('ready_numbers_stock', {})
            if not ready_numbers_stock:
                # استخدام edit_message_text لعدم إرسال رسالة جديدة إذا لم يكن هناك شيء للحذف
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="❌ لا توجد أرقام في المخزون لحذفها.", reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('رجوع', callback_data='ready_numbers_menu')))
                return

            markup = types.InlineKeyboardMarkup()
            # 💡 الترتيب حسب وقت الإضافة (الأحدث أولاً)
            sorted_numbers = sorted(ready_numbers_stock.items(), key=lambda item: item[1].get('added_date', 0), reverse=True)
            
            for phone, info in sorted_numbers:
                # عرض جزء من الرقم والسعر فقط
                num_hidden = phone[:len(phone) - 4] + "••••"
                markup.add(types.InlineKeyboardButton(f"❌ {num_hidden} ({info.get('price', 0)} روبل)", callback_data=f'confirm_delete_ready_{phone}'))
            
            markup.add(types.InlineKeyboardButton('رجوع', callback_data='ready_numbers_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="اختر الرقم الذي تريد حذفه من المخزون:", reply_markup=markup)

        # 🆕 --- تأكيد وحذف الرقم الجاهز ---
        elif data.startswith('confirm_delete_ready_'):
            phone_to_delete = data.split('_', 2)[-1]
            update_ready_numbers_stock(delete_key=phone_to_delete)
            # إخفاء آخر 4 أرقام
            num_hidden = phone_to_delete[:len(phone_to_delete) - 4] + "••••"
            bot.send_message(chat_id, f"✅ تم حذف الرقم الجاهز **{num_hidden}** من المخزون بنجاح.")
            
            # إعادة عرض قائمة الحذف المحدثة
            ready_numbers_stock = get_bot_data().get('ready_numbers_stock', {})
            if not ready_numbers_stock:
                 bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="❌ لا توجد أرقام متبقية في المخزون لحذفها.", reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('رجوع', callback_data='ready_numbers_menu')))
            else:
                 # استدعاء دالة العرض لتحديث الرسالة
                 call.data = 'delete_ready_number_start'
                 handle_admin_callbacks(call)


    # ⭐️ التغيير الثاني: تعديل قائمة المشرف الرئيسية
    def show_admin_menu(chat_id, message_id=None):
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton('إحصائيات البوت 📊', callback_data='bot_stats'), types.InlineKeyboardButton('إدارة المستخدمين 👥', callback_data='manage_users'))
        markup.row(types.InlineKeyboardButton('إضافة رصيد 💰', callback_data='add_balance'), types.InlineKeyboardButton('خصم رصيد 💸', callback_data='deduct_balance'))
        # 💡 تم تغيير زر "إضافة دولة" ليتضمن جلب خدمات SMM
        markup.row(types.InlineKeyboardButton('إضافة/جلب خدمات 🌐', callback_data='add_country'), types.InlineKeyboardButton('حذف دولة ❌', callback_data='delete_country'))
        markup.row(types.InlineKeyboardButton('إدارة الرشق 🚀', callback_data='sh_admin_menu'), types.InlineKeyboardButton('إدارة الأرقام الجاهزة 🔢', callback_data='ready_numbers_menu'))
        markup.row(types.InlineKeyboardButton('عرض الطلبات النشطة 📞', callback_data='view_active_requests'), types.InlineKeyboardButton('إلغاء جميع الطلبات 🚫', callback_data='cancel_all_requests'))
        markup.row(types.InlineKeyboardButton('إرسال رسالة جماعية 📣', callback_data='broadcast_message'))
        markup.row(types.InlineKeyboardButton('الكشف عن أرصدة المواقع 💳', callback_data='show_api_balance_menu'))
        
        text_message = "أهلاً بك في لوحة تحكم المشرف!"
        if message_id:
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text_message, reply_markup=markup)
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in str(e):
                    bot.send_message(chat_id, text_message, reply_markup=markup)
        else:
            bot.send_message(chat_id, text_message, reply_markup=markup)
