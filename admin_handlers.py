from telebot import types
import telebot.apihelper
import json
import time
import logging
from collections import defaultdict
import re

# تهيئة التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# *** مهم: يجب تحديد آيدي قناة الإشعارات هنا إذا كنت تريد نشر الإضافة تلقائيًا ***
SIM_CHANNEL_ID = -1001158537466 # آيدي القناة الرقمي
# SIM_CHANNEL_ID = None # اتركه None إذا لم يكن لديك قناة للإشعارات

# 💡 قاموس ترجمة أسماء الخدمات والفئات من الإنجليزية إلى العربية (مُحسّن)
# ************** القائمة الموسعة للترجمة **************
SERVICE_TRANSLATIONS = {
    # المنصات الكبيرة
    "Instagram": "إنستقرام",
    "Facebook": "فيسبوك",
    "YouTube": "يوتيوب",
    "TikTok": "تيك توك",
    "Twitter": "تويتر",
    "Telegram": "تليجرام",
    "Snapchat": "سناب شات",
    "Spotify": "سبوتيفاي",
    "Twitch": "تويتش",
    "Pinterest": "بينتيريست",
    "Discord": "ديسكورد",
    "LinkedIn": "لينكدإن",
    "SoundCloud": "ساوند كلاود",
    
    # أنواع الخدمات الشائعة
    "Views": "مشاهدات",
    "Followers": "متابعين",
    "Likes": "إعجابات",
    "Comments": "تعليقات",
    "Shares": "مشاركات",
    "Members": "أعضاء",
    "Reactions": "تفاعلات",
    "Subscribers": "مشتركين",
    "Traffic": "زيارات",
    "Saves": "حفظ",
    "Mentions": "منشن",
    "Ratings": "تقييمات",
    
    # الصفات والضمانات
    "Arab": "عرب",
    "Real": "حقيقي",
    "Non Drop": "غير تساقط", # مهم: الحفاظ على المسافة
    "Drop": "تساقط",
    "Premium": "مميز",
    "Guaranteed": "مضمون",
    "High Quality": "جودة عالية",
    "HQ": "جودة عالية",
    "Speed": "سرعة",
    "Fast": "سريع",
    "Slow": "بطيء",
    "Mix": "مختلط",
    "Targeted": "مستهدف",
    "Lifetime": "مدى الحياة",
    "Start": "بدء",
    "Instant": "فوري",
    "Cheapest": "الأرخص",
    
    # كلمات عامة
    "Website": "موقع ويب",
    "Post": "منشور",
    "Story": "ستوري",
    "Reel": "ريلز",
    "Video": "فيديو",
    "Live Stream": "بث مباشر",
    "Group": "مجموعة",
    "Channel": "قناة",
}
# ****************************************************

def translate_service_name(name):
    """دالة لترجمة الكلمات الرئيسية في اسم الخدمة إلى العربية."""
    # يتم استبدال الكلمات الرئيسية في الاسم بترتيب تنازلي للطول لضمان دقة الترجمة
    sorted_keys = sorted(SERVICE_TRANSLATIONS.keys(), key=len, reverse=True)
    
    name_title = name 
    
    for en in sorted_keys:
        ar = SERVICE_TRANSLATIONS[en]
        
        # استخدام التعبير العادي للبحث عن الكلمة الإنجليزية ككلمة كاملة
        pattern = re.compile(r'\b' + re.escape(en) + r'\b', re.IGNORECASE) 
        name_title = pattern.sub(ar, name_title)
        
    return name_title.replace("[]", "") 


# 💡 --- MongoDB IMPORTS ---
# افترض أن هذا الملف تم إنشاؤه في مكان آخر
# يجب أن يتضمن هذا الملف الدوال التالية:
# get_user_balance, update_user_balance, get_bot_data, save_bot_data, get_all_users_keys, get_user_doc
try:
    from db_manager import (
        get_user_balance, 
        update_user_balance, 
        get_bot_data, 
        save_bot_data, 
        get_all_users_keys,
        get_user_doc 
    )
except ImportError:
    logging.error("❌ ملف db_manager.py غير موجود. لن تعمل وظائف قاعدة البيانات.")
    # تعريف دوال وهمية لمنع تعطل الكود في حالة عدم وجود الملف
    def get_user_balance(*args): return 0
    def update_user_balance(*args): pass
    def get_bot_data(): return {}
    def save_bot_data(*args): pass
    def get_all_users_keys(): return []
    def get_user_doc(*args): return None

# ⭐️ إعداد المعالجات
def setup_admin_handlers(bot, DEVELOPER_ID, smmkings_client, smsman_api, hero_sms_client):

    # دالة مساعدة لتحديث الأرقام الجاهزة في المخزون الداخلي
    def update_ready_numbers_stock(stock_data=None, delete_key=None):
        data_file = get_bot_data()
        stock = data_file.get('ready_numbers_stock', {}) 
        
        if stock_data:
            stock.update(stock_data)
        elif delete_key:
            stock.pop(delete_key, None)
            
        # يتم حفظ البيانات الجديدة ضمن المفتاح فقط
        # يجب تمرير القاموس بالكامل إلى save_bot_data
        save_bot_data({'ready_numbers_stock': stock})
        
        # 🚨 سطر إضافي لضمان تحديث الكاش بعد الحفظ 
        return get_bot_data().get('ready_numbers_stock', {})


    
    # -----------------------------------------------------------------------------------
    # دالة مساعدة لإنشاء أزرار التطبيقات (لتجنب التكرار)
    # -----------------------------------------------------------------------------------
    
    def get_app_buttons(service, action_type):
        """
        تقوم بإنشاء قائمة أزرار التطبيقات لـ SMS.man و Hero SMS.
        action_type يمكن أن تكون 'add' أو 'delete'.
        """
        
        # صيغة الـ callback_data: {action_type}_country_app_{service}_{app_id}_page_1
        
        smsman_apps = [
            ('واتساب 💬', '2'), ('تليجرام 📢', '3'), ('فيسبوك 🏆', '4'),
            ('إنستقرام 🎥', '5'), ('تويتر 🚀', '6'), ('تيكتوك 🎬', '7'),
            ('قوقل 🌐', '8'), ('إيمو 🐦', '9'), ('سناب 🐬', '11'),
            ('OK 🌟', '12'), ('Viber 📲', '16'), ('حراج 🛍', '13'),
            ('السيرفر العام ☑️', '14')
        ]
        
        herosms_apps = [
            ('واتسأب 💬', 'wa'), ('تيليجرام 📢', 'tg'), ('فيسبوك 🏆', 'fb'),
            ('إنستقرام 🎥', 'ig'), ('تويتر 🚀', 'tw'), ('تيكتوك 🎬', 'tt'),
            ('قوقل 🌐', 'go'), ('سناب 🐬', 'sn'), ('ديسكورد 🎮', 'ds'),
            ('تيندر ❤️', 'td'), ('أوبر 🚕', 'ub'), ('أوكي 🌟', 'ok'),
            ('لاين 📲', 'li'), ('أمازون 🛒', 'am')
        ]
        
        apps_list = smsman_apps if service == 'smsman' else herosms_apps
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        for name, app_id in apps_list:
            markup.add(types.InlineKeyboardButton(name, callback_data=f"{action_type}_country_app_{service}_{app_id}_page_1"))

        return markup


    # -----------------------------------------------------------------------------------
    # معالج الرسائل النصية
    # -----------------------------------------------------------------------------------

    @bot.message_handler(func=lambda message: message.from_user.id == DEVELOPER_ID)
    def handle_admin_messages(message):
        chat_id = message.chat.id
        user_id = message.from_user.id
        
        # 💡 عند كل رسالة جديدة، نتأكد من جلب أحدث ملف بيانات
        data_file = get_bot_data() 
        state = data_file.get('states', {}).get(str(user_id))
    
        if message.text in ['/start', '/admin']:
            show_admin_menu(chat_id)
            return
        
        # --- معالجات إدارة الرصيد ---
        if state and state.get('step') == 'waiting_for_add_coin_id':
            target_id = message.text
            data_file.setdefault('states', {})[str(user_id)] = {'step': 'waiting_for_add_coin_amount', 'target_id': target_id}
            save_bot_data({'states': data_file.get('states', {})})
            bot.send_message(chat_id, "تم حفظ الآيدي. الآن أرسل **المبلغ** الذي تريد إضافته للمستخدم.")
        
        elif state and state.get('step') == 'waiting_for_add_coin_amount':
            try:
                amount = int(message.text)
                if amount <= 0: raise ValueError
                target_id = state.get('target_id')
                
                update_user_balance(target_id, amount, is_increment=True)
                
                try: bot.send_message(target_id, f"🎉 تم إضافة {amount} روبل إلى رصيدك من قبل المشرف!")
                except telebot.apihelper.ApiException: pass

                del data_file['states'][str(user_id)]
                save_bot_data({'states': data_file.get('states', {})})
                bot.send_message(chat_id, f"✅ تم إضافة {amount} روبل إلى المستخدم ذو الآيدي: {target_id}")
                
                # 💡 إعادة جلب البيانات لضمان تحديث ملف States في الذاكرة
                data_file = get_bot_data() 

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
                if amount <= 0: raise ValueError
                target_id = state.get('target_id')
                
                update_user_balance(target_id, -amount, is_increment=True)
                
                del data_file['states'][str(user_id)]
                save_bot_data({'states': data_file.get('states', {})})
                bot.send_message(chat_id, f"✅ تم خصم {amount} روبل من المستخدم ذو الآيدي: {target_id}")
                
                # 💡 إعادة جلب البيانات لضمان تحديث ملف States في الذاكرة
                data_file = get_bot_data() 

            except ValueError:
                bot.send_message(chat_id, "❌ المبلغ الذي أدخلته غير صحيح. يرجى إدخال رقم صحيح أكبر من صفر.")

        # --- معالج إضافة سعر الدولة لخدمات الأرقام ---
        elif state and state.get('step') == 'waiting_for_admin_price':
            try:
                custom_price = int(message.text)
                if custom_price <= 0: raise ValueError
                    
                country_name = state.get('country_name')
                country_code = state.get('country_code')
                service = state.get('service')
                app_id = state.get('app_id')

                data_file.setdefault('countries', {}).setdefault(service, {}).setdefault(app_id, {})
                data_file['countries'][service][app_id][country_code] = {'name': country_name, 'price': custom_price}
                
                del data_file['states'][str(user_id)]
                save_bot_data({'states': data_file.get('states', {}), 'countries': data_file.get('countries', {})}) 
                bot.send_message(chat_id, f"✅ تم إضافة الدولة **{country_name}** بالرمز **{country_code}** والسعر **{custom_price}** روبل بنجاح لخدمة **{service}**!", parse_mode='Markdown')
                
                # 💡 إعادة جلب البيانات لضمان تحديث ملف Countries في الذاكرة
                data_file = get_bot_data() 

            except ValueError:
                bot.send_message(chat_id, "❌ السعر الذي أدخلته غير صحيح. يرجى إدخال رقم صحيح أكبر من صفر.")
        
        # --- معالج معلومات المستخدمين ---
        elif state and state.get('step') == 'waiting_for_check_user_id':
            target_id = message.text
            balance = get_user_balance(target_id)
            
            if balance is not None:
                bot.send_message(chat_id, f"👤 **معلومات المستخدم:**\n\n**الآيدي:** `{target_id}`\n**الرصيد:** `{balance}` روبل", parse_mode='Markdown')
            else:
                bot.send_message(chat_id, "❌ لم يتم العثور على مستخدم بهذا الآيدي.")
            
            del data_file['states'][str(user_id)]
            save_bot_data({'states': data_file.get('states', {})})
            
            # 💡 إعادة جلب البيانات لضمان تحديث ملف States في الذاكرة
            data_file = get_bot_data() 


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
            
            # 💡 إعادة جلب البيانات لضمان تحديث ملف States في الذاكرة
            data_file = get_bot_data() 

        
        # --- معالج إرسال رسالة فردية ---
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
                
                # 💡 إعادة جلب البيانات لضمان تحديث ملف States في الذاكرة
                data_file = get_bot_data() 
        
        # --- معالج رسالة جماعية ---
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
            
            # 💡 إعادة جلب البيانات لضمان تحديث ملف States في الذاكرة
            data_file = get_bot_data() 


        # --- معالج تحديث سعر خدمة SMM ---
        elif state and state.get('step') == 'waiting_for_new_smm_price':
            try:
                new_price = int(message.text)
                if new_price <= 0: raise ValueError
                
                service_id = state.get('service_id')
                service_name = state.get('service_name')
                
                smmkings_services = data_file.get('smmkings_services', {})
                if service_id in smmkings_services:
                    smmkings_services[service_id]['user_price'] = new_price
                    save_bot_data({'smmkings_services': smmkings_services})
                    
                    # 🚨 السطر الذي يحل المشكلة! إعادة جلب البيانات لتحديث الذاكرة المؤقتة للبوت.
                    data_file = get_bot_data() 

                    bot.send_message(chat_id, f"✅ تم تحديث سعر خدمة **{service_name}** إلى `{new_price}` روبل بنجاح!")
                else:
                    bot.send_message(chat_id, "❌ لم يتم العثور على الخدمة لتحديث سعرها.")
                
                del data_file['states'][str(user_id)]
                save_bot_data({'states': data_file.get('states', {})})
                
                # 💡 إعادة جلب البيانات لضمان تحديث ملف States في الذاكرة
                data_file = get_bot_data() 

            except ValueError:
                bot.send_message(chat_id, "❌ السعر الجديد غير صحيح. يرجى إدخال رقم صحيح أكبر من صفر.")
        
        # --- معالج إضافة رقم جاهز (يدوياً) ---
        elif state and state.get('step') == 'waiting_for_ready_number_full_info':
            
            lines = message.text.strip().split('\n')
            extracted_data = []
            for line in lines:
                if ":-" in line:
                    clean_value = line.split(":-")[-1].strip()
                elif "=" in line:
                    clean_value = line.split("=")[-1].strip()
                else:
                    clean_value = line.strip()

                extracted_data.append(clean_value)

            if len(extracted_data) < 6:
                bot.send_message(chat_id, "❌ لم تقم بإرسال جميع الحقول الستة بشكل صحيح. أعد المحاولة. (تأكد من فصل كل حقل بسطر جديد)", 
                                 reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('رجوع', callback_data='ready_numbers_menu')))
                return
            
            try:
                country, price_str, app_state, note, number, code = extracted_data[:6]
                
                price = int(price_str)
                if price <= 0: raise ValueError("السعر يجب أن يكون رقماً صحيحاً وموجباً.")
                
                clean_number = number.replace('+', '').strip()
                if not clean_number.isdigit() or len(clean_number) < 8:
                    raise ValueError("صيغة رقم الهاتف غير صحيحة.")
                
                code = code.replace('-', '').strip()
                stock_key = number
                
                # استخدام الدالة المساعدة للتحديث
                update_ready_numbers_stock(stock_data={
                    stock_key: {
                        'country': country,
                        'price': price,
                        'state': app_state,
                        'note': note,
                        'number': number,
                        'code': code,
                        'added_by': str(user_id),
                        'added_date': time.time()
                    }
                })
                
                del data_file['states'][str(user_id)]
                save_bot_data({'states': data_file.get('states', {})}) 
                
                # 💡 إعادة جلب البيانات لضمان تحديث ملف States في الذاكرة
                data_file = get_bot_data()
                
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
                
                if SIM_CHANNEL_ID:
                    message_to_channel = (
                        f"*⌯ تم إضافة رقم جديد الى الأرقام الجاهزة! ☑️*\n\n"
                        f"☎️ ⪼ الدولة: {country}\n"
                        f"💸 ⪼ السعر: ₽ {price}.00\n"
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
        

    # -----------------------------------------------------------------------------------
    # معالج الكولباك
    # -----------------------------------------------------------------------------------

    @bot.callback_query_handler(func=lambda call: call.from_user.id == DEVELOPER_ID)
    def handle_admin_callbacks(call):
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        message_id = call.message.message_id
        data = call.data
        
        # 💡 عند كل كولباك، نتأكد من جلب أحدث ملف بيانات
        data_file = get_bot_data() 
        state = data_file.get('states', {}).get(str(user_id))

        if data == 'admin_main_menu':
            show_admin_menu(chat_id, message_id)
            return
        
        # --- إدارة المستخدمين ---
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
            # 💡 إعادة جلب البيانات لضمان تحديث ملف States في الذاكرة
            data_file = get_bot_data() 

        elif data == 'deduct_balance':
            data_file.setdefault('states', {})[str(user_id)] = {'step': 'waiting_for_deduct_coin_id'}
            save_bot_data({'states': data_file.get('states', {})})
            bot.send_message(chat_id, '➖ أرسل **آيدي المستخدم** الذي تريد خصم رصيد منه.')
            # 💡 إعادة جلب البيانات لضمان تحديث ملف States في الذاكرة
            data_file = get_bot_data() 

        elif data == 'check_user_balance':
            data_file.setdefault('states', {})[str(user_id)] = {'step': 'waiting_for_check_user_id'}
            save_bot_data({'states': data_file.get('states', {})})
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="💰 أرسل **آيدي المستخدم** للتحقق من رصيده.")
            # 💡 إعادة جلب البيانات لضمان تحديث ملف States في الذاكرة
            data_file = get_bot_data() 

        elif data == 'get_user_info':
            data_file.setdefault('states', {})[str(user_id)] = {'step': 'waiting_for_get_user_info_id'}
            save_bot_data({'states': data_file.get('states', {})})
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="👤 أرسل **آيدي المستخدم** للحصول على معلوماته.")
            # 💡 إعادة جلب البيانات لضمان تحديث ملف States في الذاكرة
            data_file = get_bot_data() 

        elif data == 'send_message_to_user':
            data_file.setdefault('states', {})[str(user_id)] = {'step': 'waiting_for_send_message_to_user_id'}
            save_bot_data({'states': data_file.get('states', {})})
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="✉️ أرسل **آيدي المستخدم** الذي تريد إرسال رسالة إليه.")
            # 💡 إعادة جلب البيانات لضمان تحديث ملف States في الذاكرة
            data_file = get_bot_data() 

        
        # --- الإحصائيات والبث ---
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
            # 💡 إعادة جلب البيانات لضمان تحديث ملف States في الذاكرة
            data_file = get_bot_data() 

        # --- إدارة أرصدة المواقع ---
        elif data == 'show_api_balance_menu':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('كشف رصيد SMMKings 🚀', callback_data='get_smmkings_balance'))
            markup.row(types.InlineKeyboardButton('كشف رصيد SMS.man', callback_data='get_smsman_balance'))
            markup.row(types.InlineKeyboardButton('كشف رصيد Hero SMS', callback_data='get_herosms_balance'))
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='admin_main_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="💰 اختر الموقع الذي تريد كشف رصيده:", reply_markup=markup)
        
        elif data == 'get_smmkings_balance':
            smmkings_balance_data = smmkings_client.get_balance()
            if smmkings_balance_data.get('success'):
                balance = smmkings_balance_data.get('balance')
                currency = smmkings_balance_data.get('currency', 'USD')
                message = f"💰 رصيد SMMKings الحالي: *{round(float(balance), 2)}* {currency}."
            else:
                error_msg = smmkings_balance_data.get('error', 'خطأ غير معروف')
                message = f"❌ فشل الاتصال بـ SMMKings. يرجى التأكد من مفتاح API: {error_msg}"
            
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='show_api_balance_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message, parse_mode='Markdown', reply_markup=markup)
            
        elif data == 'get_smsman_balance':
            smsman_balance = smsman_api['get_smsman_balance']()
            message = f"💰 رصيد SMS.man الحالي: *{smsman_balance}* روبل." if smsman_balance is not False else "❌ فشل الاتصال. يرجى التأكد من مفتاح API أو إعدادات الشبكة."
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='show_api_balance_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message, parse_mode='Markdown', reply_markup=markup)
            
        elif data == 'get_herosms_balance':
            hero_sms_balance = hero_sms_client.get_balance()
            if hero_sms_balance.get('success'):
                message = f"💰 رصيد Hero SMS الحالي: *{hero_sms_balance.get('balance')}* روبل."
            else:
                message = f"❌ فشل الاتصال. {hero_sms_balance.get('error', 'خطأ غير معروف')}"
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='show_api_balance_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message, parse_mode='Markdown', reply_markup=markup)

        # -------------------------------------------------------------------------------
        # --- إدارة خدمات الرشق (SMM) ---
        # -------------------------------------------------------------------------------
        elif data == 'sh_admin_menu':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('🔄 جلب/تحديث خدمات SMMKings', callback_data='fetch_smmkings_services'))
            markup.row(types.InlineKeyboardButton('✍️ تعديل سعر خدمة SMM', callback_data='edit_smm_service_price_page_1')) # تم التعديل لإضافة رقم الصفحة
            markup.row(types.InlineKeyboardButton('عرض الخدمات المخزنة 📄', callback_data='view_smmkings_services'))
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='admin_main_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="🚀 اختر الإجراء لإدارة خدمات الرشق:", reply_markup=markup)

        elif data == 'fetch_smmkings_services':
            try: bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="🔄 جاري جلب خدمات SMMKings... (قد يستغرق وقتاً)", reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('رجوع', callback_data='sh_admin_menu')))
            except telebot.apihelper.ApiTelegramException: pass # في حال كانت الرسالة محذوفة أو لم يتم تعديلها

            services_data = smmkings_client.get_services(force_reload=True)
            
            if services_data and services_data.get('services'):
                services_dict = services_data['services']
                smm_services_storage = {}
                count = 0
                
                # 💡 يجب إعادة جلب بيانات البوت هنا لضمان الحصول على أحدث نسخة 
                data_file = get_bot_data() 

                for service_id, service in services_dict.items():
                    
                    # 1. الآيدي الأصلي
                    original_category = service['category']
                    
                    # 2. تنظيف الآيدي الأصلي وتقصيره (مهم جداً!)
                    # * يتم إزالة المسافات والرموز وجعله قصيراً قدر الإمكان
                    category_id_short = original_category.replace(" ", "_").replace("/", "-").replace("[", "").replace("]", "").replace("(", "").replace(")", "").replace(".", "").replace(",", "").lower()
                    
                    # 3. قص الآيدي إذا تجاوز طول معين
                    # 📌 ضمان ألا يتجاوز طول الآيدي القصير 25 حرفاً لترك مساحة كافية للبادئة 'smmc_' وللأرقام
                    if len(category_id_short) > 25:
                        category_id_short = category_id_short[:25] # قص الآيدي
                    
                    # 4. الترجمة
                    translated_category = translate_service_name(original_category)
                    translated_name = translate_service_name(service['name'])
                    
                    # دمج الفئة والاسم المترجمين
                    final_service_name = f"[{translated_category}] {translated_name}"
                    service_id = str(service['service']) 
                    
                    smm_services_storage[service_id] = {
                        'name': final_service_name,
                        'api_rate': float(service['rate']),
                        'min': int(service['min']),
                        'max': int(service['max']),
                        # الاسم المترجم للعرض
                        'category_name': translated_category, 
                        # الآيدي القصير جداً والآمن لاستخدامه في الـ Callback
                        'category_id_short': category_id_short, 
                        # الحفاظ على السعر الحالي إذا كان موجودًا، وإلا تعيين سعر افتراضي
                        'user_price': data_file.get('smmkings_services', {}).get(service_id, {}).get('user_price', round(float(service['rate']) * 1.5)), 
                    }
                    count += 1
                
                save_bot_data({'smmkings_services': smm_services_storage})
                
                # 💡 إعادة جلب البيانات لضمان تحديث ملف SMM Services في الذاكرة
                data_file = get_bot_data() 

                message = f"✅ تم جلب وتخزين {count} خدمة من SMMKings بنجاح.\n\n⚠️ تذكر أن ترجمة الأسماء تعتمد على قاموس البوت. يجب **إعادة جلب الخدمات** بعد أي تعديل في قاموس الترجمة."
            else:
                error_msg = services_data.get('error', 'خطأ غير معروف') if services_data else 'فشل في الاتصال أو لم يتم إرجاع بيانات.'
                message = f"❌ فشل جلب خدمات SMMKings: {error_msg}"
            
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('رجوع لقائمة الإدارة', callback_data='sh_admin_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message, parse_mode='Markdown', reply_markup=markup)

        # 💡 تم حل مشكلة 414 هنا عن طريق إضافة نظام تقسيم الصفحات (Pagination)
        elif data.startswith('edit_smm_service_price_page_'):
            page = int(data.split('_')[-1])
            items_per_page = 10 
            
            smmkings_services = data_file.get('smmkings_services', {})
            if not smmkings_services:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="❌ لا توجد خدمات SMMKings مخزنة لتعديلها. يرجى جلبها أولاً.", reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton('رجوع', callback_data='sh_admin_menu')))
                return

            # فرز الخدمات أبجدياً (للتنظيم)
            sorted_services = sorted(smmkings_services.items(), key=lambda item: item[1].get('name', ''))
            
            total_services = len(sorted_services)
            total_pages = (total_services + items_per_page - 1) // items_per_page
            
            # التأكد من أن رقم الصفحة صالح
            if page < 1: page = 1
            if page > total_pages: page = total_pages 

            start_index = (page - 1) * items_per_page
            end_index = start_index + items_per_page
            
            current_page_services = sorted_services[start_index:end_index]

            markup = types.InlineKeyboardMarkup(row_width=1)
            
            for service_id, info in current_page_services:
                # استخدام الاسم المترجم المخزن بالفعل
                name_short = (info['name'][:50] + '...') if len(info['name']) > 53 else info['name']
                markup.add(types.InlineKeyboardButton(f"✍️ {name_short} ({info.get('user_price', 0)} روبل)", callback_data=f'select_smm_to_edit_{service_id}'))
            
            # أزرار التنقل بين الصفحات
            nav_buttons = []
            if page > 1:
                nav_buttons.append(types.InlineKeyboardButton('◀️ السابق', callback_data=f'edit_smm_service_price_page_{page - 1}'))
            
            # زر عرض رقم الصفحة (غير قابل للضغط)
            nav_buttons.append(types.InlineKeyboardButton(f'صفحة {page}/{total_pages}', callback_data='ignore'))

            if page < total_pages:
                nav_buttons.append(types.InlineKeyboardButton('التالي ▶️', callback_data=f'edit_smm_service_price_page_{page + 1}'))
            
            if nav_buttons: markup.row(*nav_buttons)
            
            markup.add(types.InlineKeyboardButton('رجوع', callback_data='sh_admin_menu'))
            
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, 
                                  text=f"اختر خدمة SMM التي تريد تعديل سعرها: (الصفحة {page}/{total_pages})", 
                                  reply_markup=markup)


        elif data == 'view_smmkings_services':
            smmkings_services = data_file.get('smmkings_services', {})
            
            if not smmkings_services:
                message = "❌ لا توجد خدمات SMMKings مخزنة حاليًا. يرجى جلبها أولاً."
            else:
                services_list = []
                sorted_services = sorted(smmkings_services.items(), key=lambda item: item[1].get('name', ''))
                
                for service_id, info in sorted_services:
                    services_list.append(
                        f"• **{info.get('name', 'غير معروف')}**\n"
                        f"  - `ID: {service_id}` / `السعر: {info.get('user_price', 'غير محدد')} روبل`\n"
                    )

                message = f"📄 **خدمات SMMKings المتاحة (المخزنة):** ({len(services_list)} خدمة)\n\n"
                message += "".join(services_list[:25])
                
                if len(services_list) > 25: message += "\n..."
                message += "\n\nللحصول على التفاصيل الكاملة، استخدم 'تعديل سعر خدمة SMM'."
            
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='sh_admin_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message, parse_mode='Markdown', reply_markup=markup)

        elif data.startswith('select_smm_to_edit_'):
            service_id = data.split('_')[-1]
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
            
            # 💡 إعادة جلب البيانات لضمان تحديث ملف States في الذاكرة
            data_file = get_bot_data() 

            message_text = (
                f"تم اختيار خدمة: **{service_info['name']}**\n"
                f"السعر الحالي: `{service_info.get('user_price', 'غير محدد')}` روبل.\n"
                f"سعر API الأصلي: `{service_info.get('api_rate', 'غير محدد')}` USD.\n"
                "الآن، أرسل **السعر الجديد** الذي تريد بيع الخدمة به للمستخدمين (بالروبل)."
            )
            bot.send_message(chat_id, message_text, parse_mode='Markdown')

        # -------------------------------------------------------------------------------
        # --- إدارة إضافة الدول (خدمات الأرقام) ---
        # -------------------------------------------------------------------------------
        elif data == 'add_country':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('SMS.man', callback_data='add_country_service_smsman'))
            markup.row(types.InlineKeyboardButton('Hero SMS', callback_data='add_country_service_herosms'))
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='admin_main_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text='🌐 اختر الخدمة لإضافة دولة:', reply_markup=markup)

        elif data.startswith('add_country_service_'):
            service = data.split('_')[3]
            
            # 💡 استخدام الدالة المساعدة لإنشاء الأزرار الصحيحة
            markup = get_app_buttons(service, 'add')
            
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='add_country'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text='📱 اختر التطبيق:', reply_markup=markup)
        
        elif data.startswith('add_country_app_'):
            # معالج لعرض الدول مع تقسيم الصفحات (PAGINATION)
            parts = data.split('_')
            service = parts[3]
            app_id = parts[4]
            page = int(parts[6])

            try:
                if service == 'smsman':
                    api_countries = smsman_api['get_smsman_countries'](app_id)
                elif service == 'herosms':
                    api_countries = hero_sms_client.get_countries(app_id)
                else: api_countries = {}
            except Exception as e:
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
            if page > 1: nav_buttons.append(types.InlineKeyboardButton('◀️ السابق', callback_data=f"add_country_app_{service}_{app_id}_page_{page - 1}"))
            if page < total_pages: nav_buttons.append(types.InlineKeyboardButton('التالي ▶️', callback_data=f"add_country_app_{service}_{app_id}_page_{page + 1}"))
            if nav_buttons: markup.row(*nav_buttons)
            
            markup.row(types.InlineKeyboardButton('رجوع', callback_data=f'add_country_service_{service}')) # الرجوع لاختيار التطبيق
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"اختر الدولة التي تريد إضافتها: (صفحة {page}/{total_pages})", reply_markup=markup)

        elif data.startswith('select_country_'):
            parts = data.split('_')
            service, app_id, country_code = parts[2], parts[3], parts[4]

            try:
                if service == 'smsman': api_countries = smsman_api['get_smsman_countries'](app_id)
                elif service == 'herosms': api_countries = hero_sms_client.get_countries(app_id)
                else: api_countries = {}
            except Exception as e:
                bot.send_message(chat_id, f'❌ حدث خطأ أثناء الاتصال بالـ API: {e}')
                return
                
            country_info = api_countries.get(country_code, {})
            country_name = country_info.get('name', country_code)
            api_price = country_info.get('price', 0)
            
            data_file.setdefault('states', {})[str(user_id)] = {
                'step': 'waiting_for_admin_price',
                'service': service, 'app_id': app_id,
                'country_code': country_code, 'country_name': country_name
            }
            save_bot_data({'states': data_file.get('states', {})})
            
            # 💡 إعادة جلب البيانات لضمان تحديث ملف States في الذاكرة
            data_file = get_bot_data() 

            bot.send_message(chat_id, f"تم اختيار **{country_name}** بسعر أساسي **{api_price}** روبل.\n\nالآن أرسل **السعر الذي تريد بيعه للمستخدمين**.", parse_mode='Markdown')
        
        # -------------------------------------------------------------------------------
        # --- إدارة حذف الدول (خدمات الأرقام) ---
        # -------------------------------------------------------------------------------
        elif data == 'delete_country':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('SMS.man', callback_data='delete_country_service_smsman'))
            markup.row(types.InlineKeyboardButton('Hero SMS', callback_data='delete_country_service_herosms'))
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='admin_main_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text='🌐 اختر الخدمة لحذف دولة:', reply_markup=markup)

        elif data.startswith('delete_country_service_'):
            service = data.split('_')[3]
            
            # 💡 استخدام الدالة المساعدة لإنشاء الأزرار الصحيحة
            markup = get_app_buttons(service, 'delete')
            
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='delete_country'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text='📱 اختر التطبيق لحذف دولة منه:', reply_markup=markup)

        elif data.startswith('delete_country_app_'):
            # معالج لعرض الدول المضافة محلياً مع تقسيم الصفحات
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
            if page > 1: nav_buttons.append(types.InlineKeyboardButton('◀️ السابق', callback_data=f'delete_country_app_{service}_{app_id}_page_{page - 1}'))
            if page < total_pages: nav_buttons.append(types.InlineKeyboardButton('التالي ▶️', callback_data=f'delete_country_app_{service}_{app_id}_page_{page + 1}'))
            if nav_buttons: markup.row(*nav_buttons)
            
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='delete_country'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"اختر الدولة التي تريد حذفها: (صفحة {page}/{total_pages})", reply_markup=markup)

        elif data.startswith('confirm_delete_country_'):
            parts = data.split('_')
            service, app_id, country_code = parts[3], parts[4], parts[5]
            
            # 💡 يجب أن نستخدم get_bot_data() هنا لضمان الحصول على أحدث نسخة قبل الحذف
            data_file = get_bot_data()
            
            # منطق الحذف
            if service in data_file.get('countries', {}) and app_id in data_file['countries'][service] and country_code in data_file['countries'][service][app_id]:
                country_name = data_file['countries'][service][app_id][country_code]['name']
                del data_file['countries'][service][app_id][country_code]
                if not data_file.get('countries', {}).get(service, {}).get(app_id): del data_file['countries'][service][app_id]
                if not data_file.get('countries', {}).get(service): del data_file['countries'][service]
                save_bot_data({'countries': data_file.get('countries', {})})
                bot.send_message(chat_id, f"✅ تم حذف الدولة **{country_name}** بنجاح.")

                # 💡 إعادة جلب البيانات لضمان تحديث ملف Countries في الذاكرة
                data_file = get_bot_data() 
            else:
                bot.send_message(chat_id, "❌ لم يتم العثور على هذه الدولة في قائمة الدول المضافة.")
            
            # محاولة تحديث القائمة بعد الحذف
            try:
                # محاكاة الضغط على زر الرجوع لتحديث القائمة
                call.data = f'delete_country_app_{service}_{app_id}_page_1'
                handle_admin_callbacks(call)
            except:
                call.data = 'delete_country'
                handle_admin_callbacks(call)


        # --- إدارة الطلبات النشطة ---
        elif data == 'view_active_requests':
            active_requests = data_file.get('active_requests', {})
            if not active_requests:
                message = "📞 لا توجد طلبات نشطة حاليًا."
            else:
                message = "📞 **الطلبات النشطة:**\n\n"
                sorted_requests = sorted(active_requests.items(), key=lambda item: item[1].get('request_time', 0), reverse=True)
                
                # عرض آخر 10 طلبات فقط لتجنب طول الرسالة
                for user_id, request_data in sorted_requests[:10]:
                    message += f"**آيدي المستخدم:** `{user_id}`\n"
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
                
                if len(sorted_requests) > 10: message += f"\n... والمزيد من الطلبات ({len(sorted_requests)} في المجموع)."
            
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
                data_file['active_requests'] = {}
                save_bot_data({'active_requests': data_file['active_requests']})
                
                # 💡 إعادة جلب البيانات لضمان تحديث ملف Active Requests في الذاكرة
                data_file = get_bot_data() 

                bot.send_message(chat_id, "✅ تم مسح سجل الطلبات النشطة في البوت بنجاح (يشمل الأرقام وخدمات الرشق).")
            else:
                bot.send_message(chat_id, "❌ لا توجد طلبات نشطة في السجل لحذفها.")
            handle_admin_callbacks(call)
        
        # --- إدارة الأرقام الجاهزة ---
        elif data == 'ready_numbers_menu':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('➕ إضافة رقم جاهز', callback_data='add_ready_number_start'))
            markup.row(types.InlineKeyboardButton('➖ حذف رقم جاهز', callback_data='delete_ready_number_start'))
            markup.row(types.InlineKeyboardButton('📄 عرض الأرقام الجاهزة', callback_data='view_ready_numbers_stock'))
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='admin_main_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="🔢 إدارة مخزون الأرقام الجاهزة يدوياً:", reply_markup=markup)

        elif data == 'add_ready_number_start':
            data_file.setdefault('states', {}) 
            data_file['states'][str(user_id)] = {'step': 'waiting_for_ready_number_full_info'}
            save_bot_data({'states': data_file.get('states', {})})
            
            # 💡 إعادة جلب البيانات لضمان تحديث ملف States في الذاكرة
            data_file = get_bot_data() 

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
            
            try: bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message_prompt, reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('رجوع', callback_data='ready_numbers_menu')))
            except telebot.apihelper.ApiTelegramException: bot.send_message(chat_id, message_prompt, reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('رجوع', callback_data='ready_numbers_menu')))
        
        elif data == 'view_ready_numbers_stock':
            ready_numbers_stock = data_file.get('ready_numbers_stock', {})
            
            if not ready_numbers_stock: message = "❌ لا توجد أرقام جاهزة في المخزون حاليًا."
            else:
                message = "📄 **الأرقام الجاهزة في المخزون:**\n\n"
                sorted_numbers = sorted(ready_numbers_stock.items(), key=lambda item: item[1].get('added_date', 0), reverse=True)
                
                for phone, info in sorted_numbers[:10]:
                    num_hidden = info.get('number', 'غير متوفر')[:len(info.get('number', '')) - 4] + "••••"
                    message += f"• **الرقم:** `{num_hidden}`\n"
                    message += f"• **السعر:** `{info.get('price', 0)}` روبل\n"
                    message += f"• **الدولة:** `{info.get('country', 'غير متوفر')}`\n"
                    message += f"• **الحالة:** `{info.get('state', 'غير متوفر')}`\n"
                    message += f"• **الكود (للمشرف):** `{info.get('code', 'غير متوفر')}`\n"
                    message += "-------------------\n"
                
                if len(sorted_numbers) > 10: message += f"... والمزيد من الأرقام ({len(sorted_numbers)} في المجموع)."
            
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='ready_numbers_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message, parse_mode='Markdown', reply_markup=markup)

        elif data == 'delete_ready_number_start':
            ready_numbers_stock = data_file.get('ready_numbers_stock', {})
            if not ready_numbers_stock:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="❌ لا توجد أرقام في المخزون لحذفها.", reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('رجوع', callback_data='ready_numbers_menu')))
                return

            markup = types.InlineKeyboardMarkup(row_width=2)
            sorted_numbers = sorted(ready_numbers_stock.items(), key=lambda item: item[1].get('added_date', 0), reverse=True)
            
            for phone, info in sorted_numbers:
                num_hidden = phone[:len(phone) - 4] + "••••"
                markup.add(types.InlineKeyboardButton(f"❌ {num_hidden} ({info.get('price', 0)} روبل)", callback_data=f'confirm_delete_ready_{phone}'))
            
            markup.add(types.InlineKeyboardButton('رجوع', callback_data='ready_numbers_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="اختر الرقم الذي تريد حذفه من المخزون:", reply_markup=markup)

        elif data.startswith('confirm_delete_ready_'):
            phone_to_delete = data.split('_', 2)[-1]
            update_ready_numbers_stock(delete_key=phone_to_delete)
            
            # 💡 إعادة جلب البيانات لضمان تحديث ملف Ready Numbers في الذاكرة
            data_file = get_bot_data() 
            
            num_hidden = phone_to_delete[:len(phone_to_delete) - 4] + "••••"
            bot.send_message(chat_id, f"✅ تم حذف الرقم الجاهز **{num_hidden}** من المخزون بنجاح.")
            
            if not data_file.get('ready_numbers_stock', {}):
                 bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="❌ لا توجد أرقام متبقية في المخزون لحذفها.", reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('رجوع', callback_data='ready_numbers_menu')))
            else:
                 call.data = 'delete_ready_number_start'
                 handle_admin_callbacks(call)


    # -----------------------------------------------------------------------------------
    # القائمة الرئيسية للمشرف
    # -----------------------------------------------------------------------------------
    def show_admin_menu(chat_id, message_id=None):
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton('إحصائيات البوت 📊', callback_data='bot_stats'), types.InlineKeyboardButton('إدارة المستخدمين 👥', callback_data='manage_users'))
        markup.row(types.InlineKeyboardButton('إضافة رصيد 💰', callback_data='add_balance'), types.InlineKeyboardButton('خصم رصيد 💸', callback_data='deduct_balance'))
        markup.row(types.InlineKeyboardButton('إضافة/حذف دولة 🌐', callback_data='add_country'), types.InlineKeyboardButton('إدارة الرشق 🚀', callback_data='sh_admin_menu'))
        markup.row(types.InlineKeyboardButton('إدارة الأرقام الجاهزة 🔢', callback_data='ready_numbers_menu'), types.InlineKeyboardButton('الكشف عن أرصدة المواقع 💳', callback_data='show_api_balance_menu'))
        markup.row(types.InlineKeyboardButton('عرض الطلبات النشطة 📞', callback_data='view_active_requests'), types.InlineKeyboardButton('إلغاء جميع الطلبات 🚫', callback_data='cancel_all_requests'))
        markup.row(types.InlineKeyboardButton('إرسال رسالة جماعية 📣', callback_data='broadcast_message'))
        
        text_message = "أهلاً بك في لوحة تحكم المشرف!"
        if message_id:
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text_message, reply_markup=markup)
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in str(e):
                    bot.send_message(chat_id, text_message, reply_markup=markup)
        else:
            bot.send_message(chat_id, text_message, reply_markup=markup)
