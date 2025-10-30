from telebot import types
import json
import time
import logging
import telebot.apihelper
import random 
from datetime import datetime 
import re 
import pytz 

# تهيئة نظام التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 💡 [إضافة قنوات الاشتراك الإجباري]
CHANNEL_1_ID = '@wwesmaat' 
CHANNEL_2_ID = '@EESSMT'   
CHANNELS_LIST = [CHANNEL_1_ID, CHANNEL_2_ID] 
CHANNEL_ID_FOR_NOTIFICATIONS = CHANNEL_2_ID # القناة التي سيتم إرسال إشعارات النجاح إليها

# 💡 --- MongoDB IMPORTS ---
# يتم افتراض وجود هذه الدوال في ملف db_manager.py
from db_manager import (
    get_user_doc,
    update_user_balance,
    register_user,
    get_bot_data,
    save_bot_data
)

# =========================================================================
# 💡 [دالة تنسيق رسالة الإشعار للقناة]
# =========================================================================
def format_success_message(order_id, country_name, country_flag, user_id, price, phone_number, code, service_name, activation_type="يدوي"):
    """
    تقوم ببناء رسالة إشعار النجاح بالتنسيق المطلوب.
    """
    
    # إعداد التوقيت المحلي
    tz = pytz.timezone('Asia/Aden') 
    now = datetime.now(tz)
    
    date_time_str = now.strftime("%A %d %B %Y | %I:%M:%S %p")
    
    # إخفاء آخر 3 أرقام من معرف العميل وآخر 4 من رقم الهاتف
    user_id_str = str(user_id)
    masked_user_id = user_id_str[:-3] + "•••"
    
    # التعامل مع رقم الهاتف الذي قد يكون None في حال كان طلب SMM
    masked_phone_number = (phone_number[:-4] + "••••") if phone_number and len(phone_number) > 4 else (phone_number if phone_number else 'N/A')

    # بناء نص الرسالة باستخدام F-string
    message = (
        f"➖ تم شراء رقم من البوت بنجاح 📢\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"➖ رقم الطلب | {order_id} 🛎•\n"
        f"➖ الــدولة : {country_name} {country_flag} •\n"
        f"➖ التفعيل : {activation_type} 👍🏻•\n"
        f"➖ السيرفر : عروض واتساب •\n"
        f"➖ المنصة : #{service_name} 🌐•\n"
        f"➖ العمـيل : {masked_user_id} 🆔.\n"
        f"➖ الـسعر : ₽ {price:.2f} 💙•\n"
        f"➖ الرقم : {masked_phone_number}\n"
        f"➖ الكود : [ {code} ]💡\n"
        f"➖ المرسل : {service_name} 🧿•\n" 
        f"➖ الحالة : تم التفعيل ✅•\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"📆 {date_time_str}"
    )
    
    return message
# =========================================================================
# 💡 [نهاية دالة تنسيق رسالة الإشعار]
# =========================================================================

def setup_user_handlers(bot, DEVELOPER_ID, ESM7AT, EESSMT, smm_kings_api, smsman_api, tiger_sms_client):
    
    # دالة مساعدة للوصول إلى مخزون الأرقام الجاهزة
    def get_ready_numbers_stock():
        return get_bot_data().get('ready_numbers_stock', {})

    # 💡 [التصحيح النهائي لمرونة المطابقة] دالة مساعدة مرنة للبحث عن الطلب في سجل المشتريات
    def get_cancellable_request_info(user_doc, request_id):
        purchases = user_doc.get('purchases', [])
        request_id_str = str(request_id) 
        
        try:
            request_id_int = int(request_id_str) 
        except ValueError:
            request_id_int = None 
        
        for p in purchases:
            p_request_id = p.get('request_id')

            is_match = False
            # 1. محاولة المطابقة كسلسلة نصية
            if str(p_request_id) == request_id_str:
                is_match = True
            # 2. محاولة المطابقة كرقم صحيح (في حال تم تخزينه كرقم في الماضي)
            elif request_id_int is not None and str(p_request_id) == str(request_id_int):
                is_match = True
            
            # حالة الطلب لا يجب أن تكون مكتملة أو ملغاة مسبقاً (تشمل SMM أيضاً)
            if is_match and p.get('status') not in ['completed', 'cancelled', 'ready_number_purchased', 'smm_completed', 'smm_cancelled']: 
                
                # وجدنا الطلب، نُعيد معلوماته لاسترجاع الرصيد
                return {
                    'user_id': user_doc.get('_id'),
                    'price_to_restore': p.get('price', 0),
                    'request_id_in_db': p_request_id, # نُعيد المعرف كما هو مخزن
                    'service': p.get('service'),
                    'app_name': p.get('app_name'),
                    'phone_number': p.get('phone_number')
                }
        return None

    # 💡 [دالة مساعدة للتحقق من اشتراك المستخدم في القنوات]
    def check_subscription(bot, user_id, channel_id):
        try:
            member = bot.get_chat_member(channel_id, user_id)
            if member.status in ['member', 'administrator', 'creator']:
                return True
            return False
        except Exception as e:
            logging.error(f"Error checking subscription for {user_id} in {channel_id}: {e}")
            return False
            
    # 💡 [دالة مساعدة لإنشاء أزرار الاشتراك]
    def get_subscription_markup(channels_list):
        markup = types.InlineKeyboardMarkup()
        for channel in channels_list:
            channel_link_name = channel.replace('@', '') 
            markup.add(types.InlineKeyboardButton(f"اشترك في {channel}", url=f"https://t.me/{channel_link_name}"))
        markup.add(types.InlineKeyboardButton("✅ تم الاشتراك، تحقق الآن", callback_data='check_sub_and_continue'))
        return markup
        
    # 💡 [تعديل دالة show_main_menu]
    def show_main_menu(chat_id, message_id=None):
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton('☎️︙شراء ارقـام وهمية', callback_data='Buynum'))
        markup.row(types.InlineKeyboardButton('💰︙شحن رصيدك', callback_data='Payment'), types.InlineKeyboardButton('👤︙قسم الرشق', callback_data='smm_services')) 
        markup.row(types.InlineKeyboardButton('🅿️︙كشف الحساب', callback_data='Record'), types.InlineKeyboardButton('🛍︙قسم العروض', callback_data='Wo'))
        markup.row(types.InlineKeyboardButton('☑️︙قسم العشوائي', callback_data='worldwide'), types.InlineKeyboardButton('👑︙قسم الملكي', callback_data='saavmotamy'))
        markup.row(types.InlineKeyboardButton('🔗︙رابط الإحالة (0.25 ₽)', callback_data='invite_link')) 
        markup.row(types.InlineKeyboardButton('💳︙متجر الكروت', callback_data='readycard-10'), types.InlineKeyboardButton('🔰︙الارقام الجاهزة', callback_data='ready'))
        markup.row(types.InlineKeyboardButton('👨‍💻︙قسم الوكلاء', callback_data='gents'), types.InlineKeyboardButton('⚙️︙إعدادات البوت', callback_data='MyAccount'))
        markup.row(types.InlineKeyboardButton('📮︙تواصل الدعم أونلاين', callback_data='super'))
        
        text = f"مرحباً بك في *بوت الأسطورة لخدمات الأرقام الافتراضية*.\n\n☑️ *⁞ قناة البوت الرسمية: @{EESSMT}\n🎬︙قم بالتحكم بالبوت الأن عبر الضعط على الأزرار.*"
        
        if message_id:
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode='Markdown', reply_markup=markup)
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in str(e):
                    bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=markup)
        else:
            bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=markup)


    # 💡 [معالج الرسائل: دعم /start مع الإحالة والتحقق الإجباري]
    @bot.message_handler(func=lambda message: message.from_user.id != DEVELOPER_ID)
    def handle_user_messages(message):
        chat_id = message.chat.id
        user_id = message.from_user.id
        first_name = message.from_user.first_name
        username = message.from_user.username
        
        # 🛑 إضافة الشرط الحاسم: منع ظهور رسالة الاشتراك الإجباري في الجروبات
        if message.chat.type != "private":
            return # إيقاف التنفيذ فوراً إذا لم تكن الدردشة خاصة
        # ----------------------------------------------------
        
        # 1. معالجة رابط الإحالة من /start XXX
        referrer_id = None
        if message.text.startswith('/start'):
            try:
                payload = message.text.split()[1]
                if payload.isdigit():
                    referrer_id = int(payload)
            except:
                pass
        
        # تسجيل/تحديث المستخدم (سيتم هنا مكافأة المُحيل في db_manager)
        register_user(user_id, first_name, username, referrer_id=referrer_id)

        # 2. التحقق الإجباري من الاشتراك
        is_subscribed = True
        for channel in CHANNELS_LIST:
            if not check_subscription(bot, user_id, channel):
                is_subscribed = False
                break

        if not is_subscribed:
            markup = get_subscription_markup(CHANNELS_LIST)
            
            bot.send_message(chat_id, 
                             "🛑 **يجب عليك الاشتراك في قنوات البوت الإجبارية لاستخدام الخدمة.**\n\nيرجى الاشتراك في جميع القنوات ثم الضغط على زر **تم الاشتراك**.", 
                             parse_mode='Markdown', 
                             reply_markup=markup)
            return

        # 3. معالجة الأوامر الرئيسية بعد النجاح
        if message.text.startswith('/start'):
             show_main_menu(chat_id)
             return

        elif message.text in ['/balance', 'رصيدي']:
            user_doc = get_user_doc(user_id)
            balance = user_doc.get('balance', 0) if user_doc else 0
            bot.send_message(chat_id, f"💰 رصيدك الحالي هو: *{balance}* روبل.", parse_mode='Markdown')
            return

        # 💡 [معالج أمر /invite]
        elif message.text in ['/invite', 'رابط الإحالة']:
            bot.send_message(chat_id, 
                             f"🔗 *رابط الإحالة الخاص بك:*\n`https://t.me/{bot.get_me().username}?start={user_id}`\n\n"
                             f"🤑 *عندما يقوم صديقك بالتسجيل عبر هذا الرابط، ستحصل أنت على 0.25 روبل مجاناً.*", 
                             parse_mode='Markdown')
            return
        
        # 💡 [معالج رسالة عادية غير معرفة]
        else:
            # يمكن تجاهل الرسائل النصية غير المعرفة هنا
            pass
        
    # 💡 [تعديل معالج Callbacks: تطبيق التحقق الإجباري ومعالج زر التحقق والإحالة]
    @bot.callback_query_handler(func=lambda call: call.from_user.id != DEVELOPER_ID)
    def handle_user_callbacks(call):
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        message_id = call.message.message_id
        data = call.data
        
        data_file = get_bot_data()
        user_doc = get_user_doc(user_id)
        user_balance = user_doc.get('balance', 0) if user_doc else 0
        
        # 1. التحقق الإجباري من الاشتراك (هذا الفحص ضروري لإيقاف العمليات في البوت)
        is_subscribed = True
        for channel in CHANNELS_LIST:
            if not check_subscription(bot, user_id, channel):
                is_subscribed = False
                break
                
        if not is_subscribed:
            markup = get_subscription_markup(CHANNELS_LIST)
            bot.answer_callback_query(call.id, "🛑 يرجى الاشتراك في القنوات الإجبارية أولاً.", show_alert=True)
            # محاولة إرسال رسالة الاشتراك مجدداً
            try:
                 bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id, 
                    text="🛑 **يجب عليك الاشتراك في قنوات البوت الإجبارية لاستخدام الخدمة.**", 
                    parse_mode='Markdown', 
                    reply_markup=markup
                )
            except telebot.apihelper.ApiTelegramException:
                 bot.send_message(chat_id, 
                                 "🛑 **يجب عليك الاشتراك في قنوات البوت الإجبارية لاستخدام الخدمة.**", 
                                 parse_mode='Markdown', 
                                 reply_markup=markup)
            return

        # 2. معالج زر "تم الاشتراك، تحقق الآن"
        if data == 'check_sub_and_continue':
            bot.answer_callback_query(call.id, "✅ تم التحقق بنجاح! شكراً لاشتراكك.")
            show_main_menu(chat_id, message_id)
            return

        # 3. معالج زر رابط الإحالة في القائمة الرئيسية
        elif data == 'invite_link':
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"🔗 *رابط الإحالة الخاص بك:*\n`https://t.me/{bot.get_me().username}?start={user_id}`\n\n"
                     f"🤑 *عندما يقوم صديقك بالتسجيل عبر هذا الرابط، ستحصل أنت على 0.25 روبل مجاناً.*",
                parse_mode='Markdown',
                reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('🔙 - رجوع', callback_data='back'))
            )
            return
            
        # 💡 [من هنا يبدأ باقي منطق Callbacks الأصلي]
        elif data == 'back':
            show_main_menu(chat_id, message_id)
            return
        
        elif data == 'Payment':
            # 💡 [طرق شحن جديدة]
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('💳 كريمي كول', callback_data='pay_karemi'))
            markup.row(types.InlineKeyboardButton('📱 محفظة جوالي', callback_data='pay_jawali'))
            markup.row(types.InlineKeyboardButton('🌐 بينانس (Binance)', callback_data='pay_binance'))
            markup.row(types.InlineKeyboardButton('💵 بايير (Payeer)', callback_data='pay_payeer'))
            markup.row(types.InlineKeyboardButton('🔙 رجوع', callback_data='back'))
            
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, 
                                  text="💰 *اختر طريقة شحن الرصيد المفضلة لديك. سيتم تحويلك لمحادثة المشرف لإتمام عملية الشحن.*\n\n*ملاحظة:* الحد الأدنى للشحن هو 100 روبل.", 
                                  parse_mode='Markdown', reply_markup=markup)
            return
            
        elif data.startswith('pay_'):
            method = {
                'pay_karemi': 'كريمي كول',
                'pay_jawali': 'محفظة جوالي',
                'pay_binance': 'بينانس',
                'pay_payeer': 'بايير'
            }.get(data, 'طريقة دفع غير معروفة')
            
            message_text = (
                f"✅ *تم اختيار طريقة الشحن: {method}.*\n\n"
                f"لإتمام عملية الشحن، يرجى التواصل مع المشرف (@{ESM7AT}) وإرسال الآتي:\n"
                f"1. *الكمية* التي تريد شحنها (بالروبل).\n"
                f"2. إثبات الدفع (لقطة شاشة).\n"
                f"3. *آيدي حسابك:* `{user_id}`"
            )
            bot.send_message(chat_id, message_text, parse_mode='Markdown')
            return

        # =========================================================================
        # 🚀 [معالج 'smm_services' - عرض الفئات من المخزن] (مُعدَّل)
        # =========================================================================
        elif data == 'smm_services': 
            markup = types.InlineKeyboardMarkup()
            
            # 1. جلب الخدمات المخزنة محلياً
            bot_data = get_bot_data()
            all_smm_services = bot_data.get('smmkings_services', {}) 
            
            # 2. استخراج الفئات الفريدة (مع حساب عدد الخدمات داخل كل فئة)
            categories_with_count = {}
            for service_id, info in all_smm_services.items():
                category_name = info.get('category_name', 'فئة عامة')
                # 💡 التصحيح: التأكد من أن الخدمة تحتوي على اسم وسعر قبل إضافتها للفئة
                if info.get('name') and info.get('rate') is not None:
                    categories_with_count[category_name] = categories_with_count.get(category_name, 0) + 1
            
            if not categories_with_count:
                bot.answer_callback_query(call.id, "❌ لا توجد فئات لخدمات الرشق متاحة حاليًا.")
                markup.add(types.InlineKeyboardButton('🔙 - رجوع', callback_data='back'))
                try:
                    bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="🚀 *اختر الفئة التي تريد الرشق لها:*", parse_mode='Markdown', reply_markup=markup)
                except:
                    bot.send_message(chat_id, "🚀 *اختر الفئة التي تريد الرشق لها:*", parse_mode='Markdown', reply_markup=markup)
                return
            
            # 3. بناء الأزرار للفئات
            for category_name in sorted(categories_with_count.keys()):
                count = categories_with_count[category_name]
                
                # 💡 التعديل الحاسم: استخدم دالة .replace(' ', '_') فقط لإنشاء callback_data نظيف
                clean_category_name = category_name.replace(' ', '_')
                
                # نرسل اسم الفئة النظيف وعدد الخدمات
                markup.add(types.InlineKeyboardButton(f"🔗 {category_name} ({count} خدمات)", callback_data=f'smm_cat_{clean_category_name}'))
                
            markup.add(types.InlineKeyboardButton('🔙 - رجوع', callback_data='back'))
            
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="🚀 *اختر الفئة التي تريد الرشق لها:*", parse_mode='Markdown', reply_markup=markup)
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in str(e):
                    bot.send_message(chat_id, "🚀 *اختر الفئة التي تريد الرشق لها:*", parse_mode='Markdown', reply_markup=markup)
            return

        # =========================================================================
        # 🚀 [معالج 'smm_cat_' - عرض الخدمات داخل الفئة من المخزن] (مُعدَّل)
        # =========================================================================
        elif data.startswith('smm_cat_'):
            # 💡 التعديل الحاسم: استعادة اسم الفئة المشفر عبر إزالة المقدمة فقط
            clean_category_name_raw = data.replace('smm_cat_', '', 1) 
            
            # 💡 استعادة الاسم الأصلي للفئة (للعرض في الرسالة)
            category_name = clean_category_name_raw.replace('_', ' ') 
            
            markup = types.InlineKeyboardMarkup()
            
            bot_data = get_bot_data()
            all_smm_services = bot_data.get('smmkings_services', {})

            # 1. فلترة الخدمات حسب الفئة
            services_in_category = {}
            for s_id, s_info in all_smm_services.items():
                stored_category_name = s_info.get('category_name', 'فئة عامة')
                
                # 💡 المنطق الجديد: قارن بين الاسم النظيف الذي تم تخزينه والاسم النظيف المستعاد من الكولباك
                if stored_category_name.replace(' ', '_') == clean_category_name_raw: 
                    # التأكد من أن الخدمة تحتوي على جميع الحقول المطلوبة قبل إضافتها
                    if s_info.get('name') and s_info.get('rate') is not None:
                        services_in_category[s_id] = s_info
                
            if not services_in_category:
                bot.answer_callback_query(call.id, "❌ لا توجد خدمات متاحة في هذه الفئة حاليًا.")
                # 💡 تصحيح: الرجوع لقائمة الفئات بدلاً من رسالة خطأ صماء
                markup.add(types.InlineKeyboardButton('🔙 - رجوع لقائمة الفئات', callback_data='smm_services'))
                try:
                    bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"🔗 *اختر الخدمة التي تريد طلبها من فئة {category_name}:*", parse_mode='Markdown', reply_markup=markup)
                except:
                    bot.send_message(chat_id, f"🔗 *اختر الخدمة التي تريد طلبها من فئة {category_name}:*", parse_mode='Markdown', reply_markup=markup)
                return

            # 2. بناء الأزرار للخدمات
            for service_id, service_info in services_in_category.items():
                name = service_info.get('name', f"خدمة #{service_id}")
                min_order = service_info.get('min', 'Min')
                rate_api = float(service_info.get('rate', '0.00'))
                
                # 💡 افتراض سعر بيع للمستخدم (سعر API * 2 مؤقتاً)
                user_rate_per_k = rate_api * 2 
                
                # نستخدم 'smm_order_SERVICE_ID' للانتقال إلى شاشة الطلب
                markup.add(types.InlineKeyboardButton(f"{name} | Min {min_order} | ₽ {user_rate_per_k:.2f}", callback_data=f'smm_order_{service_id}'))
                
            markup.add(types.InlineKeyboardButton('🔙 - رجوع لقائمة الفئات', callback_data='smm_services'))
            
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"🔗 *اختر الخدمة التي تريد طلبها من فئة {category_name}:*", parse_mode='Markdown', reply_markup=markup)
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in str(e):
                    bot.send_message(chat_id, f"🔗 *اختر الخدمة التي تريد طلبها من فئة {category_name}:*", parse_mode='Markdown', reply_markup=markup)
            return

        # =========================================================================
        # 🚀 [معالج 'smm_order_' - جلب التفاصيل من المخزن وبدء الطلب]
        # =========================================================================
        elif data.startswith('smm_order_'):
            service_id = data.split('_')[-1]
            
            # جلب تفاصيل الخدمة من المخزن المحلي
            bot_data = get_bot_data()
            all_smm_services = bot_data.get('smmkings_services', {})
            service_details = all_smm_services.get(service_id, {})
            
            if not service_details:
                bot.answer_callback_query(call.id, "❌ خطأ: تفاصيل الخدمة غير متوفرة.")
                bot.send_message(chat_id, "❌ خطأ في جلب تفاصيل الخدمة. يرجى المحاولة لاحقاً.")
                return
            
            name = service_details.get('name', 'خدمة رشق')
            rate_api = float(service_details.get('rate', '0.00')) # سعر API بالدولار/الروبل
            min_order = str(service_details.get('min', '1'))
            max_order = str(service_details.get('max', 'غير محدود'))
            
            # 💡 افتراض سعر بيع للمستخدم (يجب جلب هذا من إعدادات المشرف)
            user_rate_per_k = rate_api * 2 

            # حفظ حالة المستخدم (الخدمة التي يريد طلبها)
            bot_data['user_states'][user_id] = {
                'state': 'awaiting_smm_link',
                'service_id': service_id,
                'service_name': name,
                'rate': user_rate_per_k, # استخدام سعر البيع للمستخدم
                'min': min_order,
                'max': max_order
            }
            save_bot_data(bot_data)
            
            # إرسال الرسالة للمستخدم
            message_text = (
                f"✅ **أنت على وشك طلب خدمة:** `{name}`\n"
                f"💰 **السعر:** `{user_rate_per_k:.2f}` روبل لكل 1000\n"
                f"🔢 **الكمية:** الحد الأدنى {min_order} والأقصى {max_order}\n\n"
                f"🔗 **الخطوة 1:** يرجى إرسال **الرابط/الـ URL** الذي تريد الرشق إليه (مثال: رابط صورة، رابط حساب، إلخ).\n"
            )
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message_text, parse_mode='Markdown', reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('❌ إلغاء الطلب', callback_data='smm_services')))
            return

        # 💡 [نهاية معالجات SMMKings الأساسية]

        elif data == 'Wo':
            bot.send_message(chat_id, "🛍 *لا توجد عروض خاصة متاحة حالياً. تابعنا للحصول على التحديثات!*", parse_mode='Markdown')
            return
        elif data == 'worldwide':
            bot.send_message(chat_id, "☑️ *قسم الأرقام العشوائية قيد الإعداد. يرجى العودة لاحقاً.*", parse_mode='Markdown')
            return
        elif data == 'saavmotamy':
            bot.send_message(chat_id, "👑 *خدمة الأرقام الملكية قادمة قريباً، تابعنا لمعرفة المزيد.*", parse_mode='Markdown')
            return
        elif data == 'readycard-10':
            bot.send_message(chat_id, "💳 *متجر الكروت متوفر الآن! تواصل مع الدعم لشراء كرت.*", parse_mode='Markdown')
            return

        # 🆕 --- قائمة الأرقام الجاهزة (العرض) ---
        elif data == 'ready':
            ready_numbers_stock = get_ready_numbers_stock()
            
            if not ready_numbers_stock:
                bot.send_message(chat_id, "❌ لا توجد أرقام جاهزة متاحة حالياً.")
                return

            markup = types.InlineKeyboardMarkup()
            # 💡 نستخدم رقم الهاتف كـ key في المخزون
            for number, num_data in ready_numbers_stock.items():
                country = num_data.get('country', 'الدولة')
                app_state = num_data.get('state', 'تطبيق')
                price = num_data.get('price', 0)
                # إخفاء جزء من الرقم للعرض
                num_hidden = number[:len(number) - 4] + "••••"
                
                # استخدام رقم الهاتف كاملاً في الكولباك لسهولة التعامل (buy_ready_NUMBER)
                markup.row(types.InlineKeyboardButton(f"[{country}] {app_state} - {num_hidden} ({price} روبل)", callback_data=f"confirm_buy_ready_{number}"))
            
            markup.row(types.InlineKeyboardButton('- رجوع.', callback_data='back'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="🔰 *الأرقام الجاهزة المتاحة حالياً:*", parse_mode='Markdown', reply_markup=markup)

        # 🆕 --- تأكيد الشراء (الصيغة المطلوبة الأولى) ---
        elif data.startswith('confirm_buy_ready_'):
            # رقم الهاتف بالكامل هو key
            number_key = data.split('_', 3)[-1] 
            ready_numbers_stock = get_ready_numbers_stock()
            number_data = ready_numbers_stock.get(number_key)

            if not number_data:
                bot.send_message(chat_id, "❌ الرقم المحدد غير متوفر حالياً. يرجى العودة للقائمة الرئيسية.", reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('- رجوع.', callback_data='back')))
                return
            
            name = number_data.get('country', 'رقم جاهز')
            price = number_data.get('price', 0)

            # 🚨 التحقق من الرصيد قبل عرض التأكيد
            if user_balance < price:
                bot.send_message(chat_id, f"❌ *عذرًا، رصيدك غير كافٍ لإتمام هذه العملية.*\n\n*الرصيد المطلوب:* {price} روبل.\n*رصيدك الحالي:* {user_balance} روبل.\n\n*يمكنك شحن رصيدك عبر زر شحن الرصيد.*", parse_mode='Markdown')
                return
                
            markup = types.InlineKeyboardMarkup()
            # الكولباك الحقيقي للشراء
            markup.row(types.InlineKeyboardButton(f"✅ تأكيد الشراء {price} روبل", callback_data=f"execute_buy_ready_{number_key}"))
            markup.row(types.InlineKeyboardButton('❌ إلغاء', callback_data='ready'))

            # استخدام الصيغة النصية المطلوبة
            message_text = (
                f"☑️ أنت الان تقوم بشراء رقم جاهز من البوت.\n"
                f"⚠️ *ملاحظة* : \n"
                f"1⃣ > *لا نتحمل مسؤلية حضر الرقم من واتساب بسبب إهمالك*\n"
                f"2⃣ > *لا نتحمل مسؤلية تخريب الكود بمخالفة التعليمات*\n"
                f"3⃣ > *بعد شراء الرقم لاتستطيع ان تقوم بإلغاء الشراء أو التراجع*\n\n"
                f"📮 > هل تريد شراء دولة -> *{name}* بسعر -> *₽ {price}* ⬇️"
            )
            
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message_text, parse_mode='Markdown', reply_markup=markup)

        # 🆕 --- تنفيذ الشراء (الصيغة المطلوبة الثانية) ---
        elif data.startswith('execute_buy_ready_'):
            # رقم الهاتف بالكامل هو key
            number_key = data.split('_', 3)[-1] 
            ready_numbers_stock = get_ready_numbers_stock()
            number_data = ready_numbers_stock.get(number_key)
            
            if not number_data:
                bot.send_message(chat_id, "❌ الرقم المحدد غير متوفر حالياً. ربما تم شراؤه للتو.", reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('- رجوع.', callback_data='back')))
                return
            
            price = number_data.get('price', 0)
            
            # 🚨 التحقق النهائي من الرصيد والوجود
            if user_balance < price:
                bot.send_message(chat_id, f"❌ *عذرًا، رصيدك غير كافٍ لإتمام هذه العملية. رصيدك الحالي: {user_balance}*", parse_mode='Markdown')
                return

            # 💡 [تصحيح المشكلة الثانية] - 1. بناء الرسالة أولاً
            idnums = random.randint(100000, 999999) 
            number = number_key
            code = number_data.get('code', 'غير متوفر (يرجى التواصل مع الدعم)')
            what = number_data.get('note', 'لا توجد ملاحظة')
            remaining_balance = user_balance - price
            
            message_text = (
                f"☑️ *- تم شراء الرقم بنجاح* 🙂🖤\n\n"
                f"📞 > الرقم : *{number}*\n"
                f"🔥 > الكود : *{code}*\n"
                f"♨️ > السعر : *₽ {price}*\n"
                f"⚠️ > ملاحضة : *{what}*\n"
                f"🅿️ > رقم المعاملة : *{idnums}*\n\n"
                f"☑️ *- تم حذف الرقم* من قائمة الأرقام الجاهزة\n"
                f"🗃 *- تم حفظ الرقم* في سجلك للأرقام 🤙\n"
                f"✅ - تم خصم *₽ {price}* من نقودك *( {remaining_balance} )* 💰\n"
                f"💸"
            )
            
            try:
                # 💡 [تصحيح المشكلة الثانية] - 2. محاولة إرسال رسالة الإيصال (إذا نجح الإرسال، ننتقل للخصم)
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message_text, parse_mode='Markdown')
                
                # 💡 [تصحيح المشكلة الثانية] - 3. تنفيذ الخصم وتحديث قاعدة البيانات
                update_user_balance(user_id, -price, is_increment=True)
                
                # 4. إزالة الرقم من المخزون وحفظ التعديل
                data_file = get_bot_data()
                if number_key in data_file.get('ready_numbers_stock', {}):
                    del data_file['ready_numbers_stock'][number_key] 
                    save_bot_data(data_file) # حفظ كامل البيانات بعد التعديل
                
                # 5. تسجيل عملية الشراء
                register_user(
                    user_id,
                    user_doc.get('first_name'), 
                    user_doc.get('username'), 
                    new_purchase={
                        'request_id': str(idnums), # يتم تخزين request_id كسلسلة نصية
                        'phone_number': number_key,
                        'app': number_data.get('state', 'جاهز'),
                        'price': price,
                        'status': 'ready_number_purchased', # حالة خاصة للطلبات المكتملة
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
                    }
                )
                
                # إشعار للمطور
                bot.send_message(DEVELOPER_ID, 
                                 f"🔔 *تم بيع رقم جاهز!*\n"
                                 f"*الرقم:* `{number}`\n"
                                 f"*السعر:* `{price}` روبل\n"
                                 f"*للمستخدم:* `@{user_doc.get('username', 'غير متوفر')}`", 
                                 parse_mode='Markdown')

            except telebot.apihelper.ApiTelegramException as e:
                # إذا فشل إرسال الرسالة، لن يتم خصم الرصيد ولن يتم تحديث MongoDB
                logging.error(f"Failed to send Ready Number message (Req ID: {idnums}). Reverting purchase. Error: {e}")
                
                # إشعار للمطور بالخطأ الحرج
                bot.send_message(DEVELOPER_ID, 
                                 f"🚨 *فشل حرج في بيع رقم جاهز!* لم يتم خصم الرصيد. يجب التحقق.\n"
                                 f"*رقم الهاتف:* `{number_key}`\n"
                                 f"*للمستخدم:* `{user_id}`\n"
                                 f"*الخطأ:* {e}", 
                                 parse_mode='Markdown')
                
                # إرسال رسالة خطأ للمستخدم
                bot.send_message(chat_id, "❌ *فشل إتمام عملية الشراء.* لم يتم خصم رصيدك. يرجى المحاولة مجدداً أو التواصل مع الدعم.", parse_mode='Markdown')
            
            return

        elif data == 'gents':
            bot.send_message(chat_id, "👨‍💻 *نظام الوكلاء قيد المراجعة. إذا كنت مهتماً، يمكنك التواصل مع المشرف.*", parse_mode='Markdown')
            return
        elif data == 'MyAccount':
            user_info = get_user_doc(user_id)
            message_text = (
                f"⚙️ **إعدادات حسابك:**\n"
                f"**الآيدي:** `{user_info.get('_id', 'غير متوفر')}`\n"
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
            # 🛑 التعديل المطلوب: حذف SMMKings وإعادة تسمية المتبقيين
            markup.row(types.InlineKeyboardButton('سيرفر 1', callback_data='service_smsman')) # كان سابقا SmsMan
            markup.row(types.InlineKeyboardButton('سيرفر 2', callback_data='service_tigersms')) # كان سابقا TigerSMS
            markup.row(types.InlineKeyboardButton('- رجوع.', callback_data='back'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="📞 *اختر الخدمة التي تريد الشراء منها:*", parse_mode='Markdown', reply_markup=markup)
        
        elif data == 'Record':
            user_info = get_user_doc(user_id)
            balance = user_info.get('balance', 0)
            purchases = user_info.get('purchases', [])
            
            message_text = f"💰 رصيدك الحالي هو: *{balance}* روبل.\n\n"
            if purchases:
                message_text += "📝 **سجل مشترياتك الأخيرة:**\n"
                # عرض آخر 5 مشتريات
                for i, p in enumerate(purchases[-5:]):
                    # نستخدم phone_number أو app_name أو service_name
                    item_name = p.get('phone_number', p.get('app_name', p.get('service_name', 'غير متوفر'))) 
                    price = p.get('price', 0)
                    timestamp = p.get('timestamp', 'غير متوفر')
                    status = p.get('status', 'غير معروف')
                    message_text += f"*{i+1}. شراء {item_name} بسعر {price} روبل ({status}) في {timestamp}*\n"
            else:
                message_text += "❌ لا يوجد سجل مشتريات حتى الآن."
            
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message_text, parse_mode='Markdown', reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('🔙 - رجوع', callback_data='back')))
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in str(e):
                    bot.send_message(chat_id, message_text, parse_mode='Markdown', reply_markup=types.InlineKeyboardButton('🔙 - رجوع', callback_data='back'))
            return
            
        elif data.startswith('service_'):
            parts = data.split('_')
            service = parts[1]
            markup = types.InlineKeyboardMarkup()
            
            # 🛑 التعديل المطلوب: تم تغيير اسم السيرفر المعروض للمستخدم
            server_name = 'سيرفر 1' if service == 'smsman' else ('سيرفر 2' if service == 'tigersms' else 'غير معروف') 

            # 💡 تم حذف المنطق المكرر لـ SMMKings والتركيز على SmsMan و TigerSMS
            if service == 'smsman':
                markup.row(types.InlineKeyboardButton('⁞ واتسأب 💬', callback_data=f'show_countries_{service}_2_page_1'))
                markup.row(types.InlineKeyboardButton('⁞ تيليجرام 📢', callback_data=f'show_countries_{service}_3_page_1'))
                markup.row(types.InlineKeyboardButton('⁞ فيسبوك 🏆', callback_data=f'show_countries_{service}_4_page_1'))
                markup.row(types.InlineKeyboardButton('⁞ إنستقرام 🎥', callback_data=f'show_countries_{service}_5_page_1'))
                markup.row(types.InlineKeyboardButton('⁞ تويتر 🚀', callback_data=f'show_countries_{service}_6_page_1'))
                markup.row(types.InlineKeyboardButton('⁞ تيكتوك 🎬', callback_data=f"show_countries_{service}_7_page_1"))
                markup.row(types.InlineKeyboardButton('⁞ قوقل 🌐', callback_data=f'show_countries_{service}_8_page_1'))
                markup.row(types.InlineKeyboardButton('⁞ إيمو 🐦', callback_data=f'show_countries_{service}_9_page_1'))
                markup.row(types.InlineKeyboardButton('⁞ سناب 🐬', callback_data=f'show_countries_{service}_11_page_1'))
                markup.row(types.InlineKeyboardButton('⁞ OK 🌟', callback_data=f'show_countries_{service}_12_page_1'))
                markup.row(types.InlineKeyboardButton('⁞ Viber 📲', callback_data=f'show_countries_{service}_16_page_1'))
                markup.row(types.InlineKeyboardButton('⁞ حراج 🛍', callback_data=f'show_countries_{service}_13_page_1'))
                markup.row(types.InlineKeyboardButton('⁞ السيرفر العام ☑️', callback_data=f'show_countries_{service}_14_page_1'))
            elif service == 'tigersms':
                markup.row(types.InlineKeyboardButton('⁞ واتسأب 💬', callback_data=f'show_countries_{service}_wa_page_1'))
                markup.row(types.InlineKeyboardButton('⁞ تيليجرام 📢', callback_data=f'show_countries_{service}_tg_page_1'))
                markup.row(types.InlineKeyboardButton('⁞ فيسبوك 🏆', callback_data=f'show_countries_{service}_fb_page_1'))
                markup.row(types.InlineKeyboardButton('⁞ إنستقرام 🎥', callback_data=f'show_countries_{service}_ig_page_1'))
                markup.row(types.InlineKeyboardButton('⁞ تويتر 🚀', callback_data=f'show_countries_{service}_tw_page_1'))
                markup.row(types.InlineKeyboardButton('⁞ تيكتوك 🎬', callback_data=f"show_countries_{service}_tt_page_1"))
                markup.row(types.InlineKeyboardButton('⁞ قوقل 🌐', callback_data=f'show_countries_{service}_go_page_1'))
                markup.row(types.InlineKeyboardButton('⁞ سناب 🐬', callback_data=f'show_countries_{service}_sn_page_1'))
                markup.row(types.InlineKeyboardButton('⁞ ديسكورد 🎮', callback_data=f'show_countries_{service}_ds_page_1'))
                markup.row(types.InlineKeyboardButton('⁞ تيندر ❤️', callback_data=f'show_countries_{service}_td_page_1'))
                markup.row(types.InlineKeyboardButton('⁞ أوبر 🚕', callback_data=f'show_countries_{service}_ub_page_1'))
                markup.row(types.InlineKeyboardButton('⁞ أوكي 🌟', callback_data=f'show_countries_{service}_ok_page_1'))
                markup.row(types.InlineKeyboardButton('⁞ لاين 📲', callback_data=f'show_countries_{service}_li_page_1'))
                markup.row(types.InlineKeyboardButton('⁞ أمازون 🛒', callback_data=f'show_countries_{service}_am_page_1'))
            
            markup.row(types.InlineKeyboardButton('- رجوع.', callback_data='Buynum'))
            
            # تم استخدام server_name الجديد هنا
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"☑️ *اختر التطبيق* الذي تريد *شراء رقم وهمي* له من خدمة **{server_name}**.", parse_mode='Markdown', reply_markup=markup)

        elif data.startswith('show_countries_'):
            parts = data.split('_')
            service, app_id = parts[2], parts[3]
            page = int(parts[5]) if len(parts) > 5 else 1
            
            # 💡 للمواقع الأخرى (smsman, tigersms)، نعتمد على البيانات المحلية المخزنة
            local_countries = data_file.get('countries', {}).get(service, {}).get(app_id, {})
            
            if not local_countries:
                bot.send_message(chat_id, '❌ لا توجد دول متاحة لهذا التطبيق حاليًا.')
                return

            # 🛑 معالجة مشكلة 414: تقسيم القائمة
            items_per_page = 10
            country_items = list(local_countries.items())
            total_pages = (len(country_items) + items_per_page - 1) // items_per_page
            start_index = (page - 1) * items_per_page
            end_index = start_index + items_per_page
            current_countries = country_items[start_index:end_index]
            
            markup = types.InlineKeyboardMarkup()
            for code, info in current_countries:
                display_price = info.get('price', 'غير متاح')
                markup.row(types.InlineKeyboardButton(f"{info.get('name', code)} ({display_price} روبل)", callback_data=f'buy_{service}_{app_id}_{code}'))
            
            nav_buttons = []
            # 💡 يتم تجميع الكولباك ليعمل مع TigerSMS و SmsMan
            base_callback = f'show_countries_{service}_{app_id}_page_' 
            
            if page > 1:
                nav_buttons.append(types.InlineKeyboardButton('◀️ السابق', callback_data=f'{base_callback}{page - 1}'))
            if page < total_pages:
                nav_buttons.append(types.InlineKeyboardButton('التالي ▶️', callback_data=f'{base_callback}{page + 1}'))
            if nav_buttons:
                markup.row(*nav_buttons)
            
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='Buynum'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"اختر الدولة التي تريدها: (صفحة {page}/{total_pages})", reply_markup=markup)

        # 💡 [بداية التعديل الأساسي: معالج الشراء]
        elif data.startswith('buy_'):
            parts = data.split('_')
            service, app_id, country_code = parts[1], parts[2], parts[3]
            
            bot.answer_callback_query(call.id, "✅ جاري معالجة طلب الرقم...")

            # 💡 جلب معلومات الدولة والسعر من البيانات المخزنة
            country_info = data_file.get('countries', {}).get(service, {}).get(app_id, {}).get(country_code, {})
            
            price = country_info.get('price', 0)
            
            if user_balance < price:
                bot.send_message(chat_id, f"❌ *عذرًا، رصيدك غير كافٍ لإتمام هذه العملية.*\n\n*الرصيد المطلوب:* {price} روبل.\n*رصيدك الحالي:* {user_balance} روبل.\n\n*يمكنك شحن رصيدك عبر زر شحن الرصيد.*", parse_mode='Markdown')
                return

            # *** 1. الاتصال بالـ API وجلب الرقم ***
            result = None
            if service == 'smsman':
                # تم الإبقاء على كود smsman كما هو مع الإشارة إلى التعديل المطلوب لـ smsman_api.py
                result = smsman_api['request_smsman_number'](app_id, country_code)
                if result and 'request_id' in result:
                    result['success'] = True
                    result['id'] = str(result['request_id'])
                    result['number'] = result.get('Phone', result.get('number'))
            elif service == 'tigersms':
                result = tiger_sms_client.get_number(app_id, country_code)

            logging.info(f"Response from {service}: {result}")

            if result and result.get('success'):
                request_id = str(result.get('id', result.get('request_id', random.randint(100000000, 999999999)))) 
                phone_number = result.get('number', result.get('Phone', 'غير متوفر'))
                
                remaining_balance = user_balance - price
                
                # *** 2. إعداد الأزرار الجديدة (التحديث اليدوي) ***
                markup = types.InlineKeyboardMarkup()
                markup.row(types.InlineKeyboardButton('♻️ - تحديث (جلب الكود)', callback_data=f'Code_{service}_{request_id}'))
                markup.row(types.InlineKeyboardButton('❌ إلغاء الطلب', callback_data=f'cancel_{service}_{request_id}'))
                markup.row(types.InlineKeyboardButton('🔄 - تغيير رقم آخر.', callback_data=f'ChangeNumber_{service}_{app_id}_{country_code}'))

                app_name = country_info.get('app_name', 'غير معروف')
                country_name = country_info.get('name', 'غير معروف')
                country_flag = country_info.get('flag', '') 

                # 💡 استخدام التوقيت المحلي لزيادة الدقة
                tz = pytz.timezone('Asia/Aden') 
                current_time = datetime.now(tz).strftime('%I:%M:%S %p')
                
                message_text = (
                    f"**☎️ - الرقم:** `{phone_number}`\n"
                    f"**🧿 - التطبيق:** `{app_name}`\n"
                    f"**📥 - الدولة:** `{country_name} {country_flag}`\n"
                    f"**🔥 - الأيدي:** `{user_id}`\n"
                    f"**💸 - السعر:** `₽{price}`\n"
                    f"**🤖 - الرصيد المتبقي:** `{remaining_balance}`\n" 
                    f"**🔄 - معرف المشتري:** `@{user_doc.get('username', 'غير متوفر')}`\n"
                    f"**🎦 - الموقع:** `{service}.com`\n\n" 
                    f"**🌀 - الحالة:** *••• Pending*\n"
                    f"**⏰ - وقت الطلب:** {current_time}\n\n"
                    f"⚠️ *ملاحظة هامة:* أدخل الرقم في التطبيق ثم اضغط على زر *تحديث* لجلب الكود."
                )

                sent_message = bot.send_message(chat_id, message_text, parse_mode='Markdown', reply_markup=markup)
                new_message_id = sent_message.message_id
                
                # *** 3. حفظ البيانات في MongoDB ***
                update_user_balance(user_id, -price, is_increment=True)
                
                register_user(
                    user_id, 
                    user_doc.get('first_name'), 
                    user_doc.get('username'), 
                    new_purchase={
                        'request_id': request_id, 
                        'phone_number': phone_number,
                        'service': service,
                        'price': price,
                        'status': 'pending',
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
                        'app_name': app_name,
                        'country_name': country_name, 
                        'country_flag': country_flag   
                    }
                )
                
                # حفظ الطلب في active_requests لسهولة الوصول إليه
                data_file = get_bot_data()
                active_requests = data_file.get('active_requests', {})
                active_requests[request_id] = { 
                    'user_id': user_id,
                    'phone_number': phone_number,
                    'status': 'pending',
                    'service': service,
                    'price': price,
                    'message_id': new_message_id,
                    'app_name': app_name,
                    'country_name': country_name,
                    'country_flag': country_flag,
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
                }
                data_file['active_requests'] = active_requests
                save_bot_data(data_file)
                
            else:
                # 💡 رسالة فشل معطاة للمستخدم
                bot.send_message(chat_id, "❌ فشل طلب الرقم. قد يكون غير متوفر أو أن رصيدك في الخدمة غير كافٍ.")
                
        # 💡 [المعالج المُعدَّل: التحديث اليدوي للكود وإرسال الإشعار]
        elif data.startswith('Code_'):
            parts = data.split('_')
            
            if len(parts) < 3:
                bot.answer_callback_query(call.id, "خطأ في بيانات التحديث.")
                return

            service_name = parts[1]
            request_id = parts[2]
            
            bot.answer_callback_query(call.id, "⏳ جاري التحقق من وصول الكود...")

            # 1. استرجاع بيانات الطلب من active_requests
            data_file = get_bot_data()
            active_requests = data_file.get('active_requests', {})
            active_request_info = active_requests.get(request_id, {})
            
            if not active_request_info:
                bot.send_message(chat_id, "❌ عذراً، لم يتم العثور على معلومات الطلب النشط في قاعدة البيانات. يرجى التواصل مع الدعم.")
                return

            # 2. استدعاء API لمرة واحدة
            result = None
            if service_name == 'smmkings': 
                result = smm_kings_api.get_otp(request_id)
            elif service_name == 'smsman':
                # يتم استخدام دالة get_smsman_code المعدلة (المفترض تعديلها في smsman_api.py)
                result = smsman_api['get_smsman_code'](request_id) 
            elif service_name == 'tigersms':
                result = tiger_sms_client.get_code(request_id)

            otp_code = result.get('code') if result and result.get('status') in ['success', 'COMPLETED'] and result.get('code') else None 
            
            # 3. معالجة النتيجة
            if otp_code:
                # [نجاح - تم العثور على الكود]
                
                # إعداد لوحة المفاتيح النهائية
                markup_final = types.InlineKeyboardMarkup().row(
                    types.InlineKeyboardButton('🔙 - رجوع للقائمة الرئيسية.', callback_data='back')
                )
                
                # أ. إرسال الكود في رسالة جديدة
                bot.send_message(chat_id, f"✅ *رمزك هو: {otp_code}*\n\nالرقم جاهز للاستخدام.", parse_mode='Markdown')
                
                # ب. إخبار API بـ "تم الاستخدام" (Completed) لإنهاء الطلب
                try:
                    if service_name == 'smsman':
                        smsman_api['set_smsman_status'](request_id, 6) 
                    elif service_name == 'smmkings':
                        smm_kings_api.set_status(request_id, 'STATUS_ACTIVATION_SUCCESS') 
                    elif service_name == 'tigersms':
                        tiger_sms_client.set_status(request_id, 'STATUS_SUCCESS') 
                        
                except Exception as e:
                    logging.error(f"Failed to set status to USED for {service_name} Req ID {request_id}: {e}")
                
                
                # ج. تعديل الرسالة الأصلية لوضع علامة (مكتمل) وإزالة الأزرار
                try:
                    new_text = call.message.text.replace("••• Pending", "✅ Completed")
                    # إزالة رسالة التحقق السابقة إذا وجدت
                    new_text = re.sub(r'\n\*تم التحقق الآن في .+\*\n', '', new_text) 
                    
                    bot.edit_message_text(
                        chat_id=chat_id, message_id=message_id, text=new_text, parse_mode='Markdown', reply_markup=markup_final
                    )
                except Exception as e:
                    logging.error(f"Failed to edit message upon completion: {e}")
                    
                # د. تحديث قاعدة البيانات وحذف الطلب من active_requests
                register_user(user_id, user_doc.get('first_name'), user_doc.get('username'), update_purchase_status={'request_id': request_id, 'status': 'completed'})
                
                # حذف الطلب من الطلبات النشطة
                if request_id in active_requests:
                    del active_requests[request_id]
                    save_bot_data(data_file)
                
                # 💡 هـ. إرسال المنشور الترويجي إلى القناة (الإضافة المطلوبة)
                try:
                    country_name = active_request_info.get('country_name', 'غير معروف')
                    country_flag = active_request_info.get('country_flag', '')
                    price = active_request_info.get('price', 0)
                    phone_number = active_request_info.get('phone_number', 'غير متوفر')
                    service_app_name = active_request_info.get('app_name', 'غير متوفر')
                    
                    notification_message = format_success_message(
                        order_id=request_id,
                        country_name=country_name,
                        country_flag=country_flag,
                        user_id=user_id,
                        price=price,
                        phone_number=phone_number,
                        code=otp_code,
                        service_name=service_app_name
                    )
                    
                    bot.send_message(CHANNEL_ID_FOR_NOTIFICATIONS, notification_message, parse_mode='Markdown')
                    
                except Exception as e:
                    logging.error(f"Failed to send success notification to channel: {e}")

            else:
                # [فشل - الكود لم يصل بعد أو حالة خطأ]
                
                if result and result.get('status') == 'error': 
                    error_message = result.get('message', 'خطأ غير معروف')
                    
                    if error_message == 'STATUS_CANCELLED':
                        bot.send_message(chat_id, "❌ **فشل جلب الكود:** الرقم غير صالح أو تم إلغاؤه تلقائياً من الموقع. يرجى إلغاء الطلب (إذا كان مؤهلاً لاسترداد الرصيد) والمحاولة برقم جديد.", parse_mode='Markdown')
                        return

                # الإضافة الرئيسية لحل مشكلة التحديث اليدوي: إخبار API بالاستمرار في الانتظار
                try:
                    if service_name == 'smmkings':
                        smm_kings_api.set_status(request_id, 'STATUS_WAIT_CODE') 
                    elif service_name == 'smsman':
                        smsman_api['set_smsman_status'](request_id, 3) 
                    elif service_name == 'tigersms':
                        tiger_sms_client.set_status(request_id, 'STATUS_WAIT_CODE') 
                
                    logging.info(f"Set status for {service_name} Req ID {request_id} to WAIT_CODE.")

                except Exception as e:
                    logging.error(f"Failed to set status for {service_name} Req ID {request_id}: {e}")
                
                
                current_text = call.message.text
                
                # إزالة أي رسالة تحقق سابقة
                new_text = re.sub(r'\n\*تم التحقق الآن في .+\*\n', '', current_text)
                
                # إضافة رسالة التحقق الجديدة
                tz = pytz.timezone('Asia/Aden') 
                check_time = datetime.now(tz).strftime('%I:%M:%S %p')
                
                new_text += f"\n\n*تم التحقق الآن في {check_time}. الكود لم يصل بعد. يرجى الانتظار والمحاولة مرة أخرى.*"
                
                try:
                    bot.edit_message_text(
                        chat_id=chat_id, message_id=message_id, text=new_text, parse_mode='Markdown', reply_markup=call.message.reply_markup
                    )
                except telebot.apihelper.ApiTelegramException as e:
                    if "message is not modified" not in str(e):
                        logging.error(f"Error editing message after manual refresh failure: {e}")
            
            return
                
        elif data.startswith('cancel_'):
            parts = data.split('_')
            service, request_id_raw = parts[1], parts[2]
            
            bot.answer_callback_query(call.id, "جاري معالجة طلب الإلغاء...")
            
            result = None
            success_api_call = False 
            
            # 1. محاولة الإلغاء في API الموقع
            if service == 'smmkings': 
                result = smm_kings_api.cancel_request(request_id_raw)
                if result and result.get('success'):
                    success_api_call = True
            
            elif service == 'smsman':
                result = smsman_api['cancel_smsman_request'](request_id_raw) 
                if result and (result.get('message') == 'STATUS_CANCEL' or result.get('status') in ['success', 'cancelled']):
                    success_api_call = True
            
            elif service == 'tigersms':
                result = tiger_sms_client.cancel_request(request_id_raw)
                if result and result.get('success'):
                    success_api_call = True
            
            logging.info(f"Response from {service} for CANCEL Req ID {request_id_raw}: {result}")
            
            # 2. إذا نجح الإلغاء في API، ننتقل لمعالجة الرصيد
            if success_api_call:
                
                # 💡 [استخدام الدالة الجديدة المرنة لضمان العثور على السعر]
                request_info_from_purchases = get_cancellable_request_info(user_doc, request_id_raw)
                
                if request_info_from_purchases and request_info_from_purchases.get('price_to_restore', 0) > 0:
                    try:
                        price_to_restore = request_info_from_purchases.get('price_to_restore')
                        request_id_in_db = request_info_from_purchases.get('request_id_in_db')
                        
                        # أ. استرجاع الرصيد للمستخدم
                        update_user_balance(user_id, price_to_restore, is_increment=True)
                        
                        # ب. تحديث حالة الطلب في سجل المشتريات إلى "cancelled"
                        register_user(
                            user_id, 
                            user_doc.get('first_name'), 
                            user_doc.get('username'),
                            update_purchase_status={
                                'request_id': request_id_in_db, 
                                'status': 'cancelled'
                            }
                        )
                        
                        # ج. إزالة الطلب من الطلبات النشطة (إذا كان موجوداً)
                        data_file = get_bot_data()
                        active_requests = data_file.get('active_requests', {})
                        if str(request_id_in_db) in active_requests:
                            del active_requests[str(request_id_in_db)]
                            data_file['active_requests'] = active_requests
                            save_bot_data(data_file)
                        
                        # د. إرسال رسالة النجاح
                        bot.send_message(chat_id, f"✅ **تم إلغاء الطلب بنجاح!** تم استرجاع مبلغ *{price_to_restore}* روبل إلى رصيدك.", parse_mode='Markdown')
                        
                        # هـ. تعديل الرسالة الأصلية لوضع علامة (ملغى) وإزالة الأزرار
                        try:
                            final_text = call.message.text.replace("••• Pending", "❌ Cancelled")
                            final_text = re.sub(r'\n\*تم التحقق الآن في .+\*\n', '', final_text) 
                            
                            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=final_text, parse_mode='Markdown', reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('🔙 - رجوع للقائمة الرئيسية.', callback_data='back')))
                        except:
                            pass
                        
                    except Exception as e:
                        logging.error(f"MongoDB/Refund Error during CANCEL for Req ID {request_id_raw}: {e}")
                        bot.send_message(chat_id, f"⚠️ تم إلغاء طلبك في الموقع، ولكن حدث **خطأ أثناء استرجاع رصيدك**. يرجى التواصل مع الدعم (@{ESM7AT}) وذكر آيدي الطلب: `{request_id_raw}`.", parse_mode='Markdown')
                        
                else:
                    # هذه الحالة تعني أن الطلب ألغي في الموقع لكن لم يتم العثور عليه في سجل المشتريات.
                    bot.send_message(chat_id, f"⚠️ تم إلغاء طلبك في الموقع بنجاح، لكنه **غير مسجل كطلب معلق في سجل مشترياتك**. لم يتم إرجاع الرصيد تلقائياً. يرجى التواصل فوراً مع الدعم (@{ESM7AT}) وتقديم آيدي الطلب: `{request_id_raw}`.", parse_mode='Markdown')

            else:
                # هذا الرد في حالة فشل الإلغاء في API الموقع
                bot.send_message(chat_id, "❌ فشل إلغاء الطلب في الموقع. يرجى المحاولة مرة أخرى أو التواصل مع الدعم.")
        
        elif data.startswith('ChangeNumber_'):
            # (باقي كود تغيير الرقم)
            bot.send_message(chat_id, "🔄 *سيتم إضافة وظيفة تغيير الرقم قريباً.*")
            return

    # 💡 [معالج رسائل: إدخال الرابط لطلب SMM]
    @bot.message_handler(func=lambda message: get_bot_data().get('user_states', {}).get(message.from_user.id, {}).get('state') == 'awaiting_smm_link')
    def handle_smm_link_input(message):
        user_id = message.from_user.id
        link = message.text.strip()
        
        bot_data = get_bot_data()
        user_state = bot_data['user_states'].get(user_id)
        
        if not user_state:
            bot.send_message(user_id, "❌ انتهت صلاحية الطلب. يرجى البدء من جديد.", reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('🔙 - القائمة الرئيسية', callback_data='back')))
            return
        
        # 1. حفظ الرابط وتغيير الحالة لطلب الكمية
        user_state['link'] = link
        user_state['state'] = 'awaiting_smm_quantity'
        bot_data['user_states'][user_id] = user_state
        save_bot_data(bot_data)
        
        # 2. طلب الكمية من المستخدم
        message_text = (
            f"🔗 **تم حفظ الرابط:** `{link}`\n"
            f"🔢 **الخطوة 2:** يرجى إرسال **الكمية المطلوبة** (أقل كمية هي {user_state.get('min', '1')}، والحد الأقصى {user_state.get('max', 'غير محدود')})."
        )
        bot.send_message(user_id, message_text, parse_mode='Markdown')
    
    # 💡 [معالج رسائل: إدخال الكمية لطلب SMM] (مُعدَّل)
    @bot.message_handler(func=lambda message: get_bot_data().get('user_states', {}).get(message.from_user.id, {}).get('state') == 'awaiting_smm_quantity')
    def handle_smm_quantity_input(message):
        user_id = message.from_user.id
        
        bot_data = get_bot_data()
        user_state = bot_data['user_states'].get(user_id)
        
        if not user_state:
            bot.send_message(user_id, "❌ انتهت صلاحية الطلب. يرجى البدء من جديد.", reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('🔙 - القائمة الرئيسية', callback_data='back')))
            return

        try:
            quantity = int(message.text.strip())
        except ValueError:
            bot.send_message(user_id, "❌ *الكمية غير صحيحة. يرجى إرسال رقم صحيح.*", parse_mode='Markdown')
            return
            
        # 🆕 التعديل: التأكد أن الكمية موجبة
        if quantity <= 0:
            bot.send_message(user_id, "❌ *الكمية يجب أن تكون رقماً موجباً.*", parse_mode='Markdown')
            return
        
        service_id = user_state.get('service_id')
        link = user_state.get('link')
        rate_per_k = float(user_state.get('rate', 0))
        min_qty = int(user_state.get('min', 1))
        max_qty = int(user_state.get('max', 999999999)) # قيمة عالية لـ "غير محدود"
        service_name = user_state.get('service_name', 'خدمة رشق')
        
        if quantity < min_qty:
            bot.send_message(user_id, f"❌ *الكمية المدخلة أقل من الحد الأدنى. الحد الأدنى هو {min_qty}.*", parse_mode='Markdown')
            return
        
        if quantity > max_qty:
             bot.send_message(user_id, f"❌ *الكمية المدخلة أكبر من الحد الأقصى. الحد الأقصى هو {max_qty}.*", parse_mode='Markdown')
             return
            
        # 3. حساب السعر وتأكيد الطلب
        price = (quantity / 1000) * rate_per_k
        user_doc = get_user_doc(user_id)
        user_balance = user_doc.get('balance', 0)
        
        if user_balance < price:
            bot.send_message(user_id, f"❌ *عذرًا، رصيدك غير كافٍ لإتمام هذه العملية. الرصيد المطلوب: {price:.2f} روبل.*", parse_mode='Markdown')
            # 💡 حذف حالة المستخدم
            del bot_data['user_states'][user_id]
            save_bot_data(bot_data)
            return

        # 4. تأكيد الشراء وتنفيذ الطلب
        try:
            # 💡 استدعاء API SMMKings لتقديم الطلب
            order_result = smm_kings_api.add_order(service_id, link, quantity)
            
            if order_result and 'order' in order_result:
                order_id = str(order_result.get('order'))
                remaining_balance = user_balance - price
                
                # خصم الرصيد
                update_user_balance(user_id, -price, is_increment=True)
                
                # تسجيل العملية
                register_user(
                    user_id, 
                    user_doc.get('first_name'), 
                    user_doc.get('username'), 
                    new_purchase={
                        'request_id': order_id, 
                        'link': link,
                        'service': 'smmkings',
                        'service_name': service_name,
                        'price': price,
                        'quantity': quantity,
                        'status': 'smm_pending',
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
                    }
                )
                
                # إرسال رسالة النجاح
                message_text = (
                    f"✅ **تم تقديم طلب الرشق بنجاح!**\n"
                    f"🔥 **الخدمة:** `{service_name}`\n"
                    f"🔗 **الرابط:** `{link}`\n"
                    f"🔢 **الكمية:** `{quantity}`\n"
                    f"💸 **السعر:** `{price:.2f}` روبل\n"
                    f"🅿️ **رقم الطلب:** `{order_id}`\n\n"
                    f"🤖 **رصيدك المتبقي:** `{remaining_balance:.2f}` روبل."
                )
                bot.send_message(user_id, message_text, parse_mode='Markdown', reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('🔙 - القائمة الرئيسية', callback_data='back')))

            else:
                bot.send_message(user_id, f"❌ **فشل تقديم الطلب:** لم يتمكن البوت من إرسال الطلب إلى SMMKings. لم يتم خصم رصيدك. قد يكون السبب هو خطأ في الرابط أو عدم توفر الخدمة حالياً.", parse_mode='Markdown')
            
        except Exception as e:
            logging.error(f"SMMKings add_order exception: {e}")
            bot.send_message(user_id, "❌ **فشل حرج:** حدث خطأ غير متوقع أثناء محاولة تقديم الطلب. لم يتم خصم رصيدك. يرجى التواصل مع الدعم.", parse_mode='Markdown')

        # 5. حذف حالة المستخدم سواء نجح أو فشل
        del bot_data['user_states'][user_id]
        save_bot_data(bot_data)
