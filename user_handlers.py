from telebot import types
import json
import time
import logging
import telebot.apihelper
import random 
from datetime import datetime 
import re 
import pytz 
from collections import defaultdict 

# تهيئة نظام التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 💡 [إضافة قنوات الاشتراك الإجباري]
CHANNEL_1_ID = '@wwesmaat' 
CHANNEL_2_ID = '@EESSMT'   
CHANNELS_LIST = [CHANNEL_1_ID, CHANNEL_2_ID] 

# 💥 التعديل الأول: استخدام المعرف الرقمي للقناة
# تم تعيين المعرف الرقمي للقناة: -1001158537466
CHANNEL_ID_FOR_NOTIFICATIONS = -1001158537466 

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

def setup_user_handlers(bot, DEVELOPER_ID, ESM7AT, EESSMT, smm_kings_api, smsman_api, hero_sms_client):
    
    # دالة مساعدة للوصول إلى مخزون الأرقام الجاهزة
    def get_ready_numbers_stock():
        return get_bot_data().get('ready_numbers_stock', {})

    # 💡 [دالة مساعدة مرنة للبحث عن الطلب في سجل المشتريات]
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
        
    # 💡 [دالة show_main_menu]
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
            
    # =========================================================================
    # 🚀 [الدالة المصححة: عرض فئات SMM مع ترقيم وفلترة]
    # =========================================================================
    def show_smm_categories(chat_id, message_id, page=1):
        """
        تجلب خدمات الرشق المخزنة محلياً، وتجمعها حسب 'category_id_short' مع ترقيم الصفحات، 
        وفلترة الخدمات التي لم يقم المشرف بتسعيرها (user_price > 0).
        """
        
        # 1. جلب البيانات والتجميع
        bot_data = get_bot_data()
        services = bot_data.get('smmkings_services', {})
        
        # 💥 التعديل هنا: التجميع حسب الآيدي القصير (category_id_short) 
        categories_dict = defaultdict(list)
        
        # قائمة لتخزين أزواج (الآيدي القصير، الاسم المترجم)
        category_map = {} 
        
        for service_id, info in services.items():
            category_name = info.get('category_name') 
            # 📌 يجب أن يتوفر هذا المفتاح بعد تحديث ملف admin_handlers.py
            category_id_short = info.get('category_id_short') 
            user_price = info.get('user_price', 0) 
            min_qty = info.get('min', 0)
            
            try:
                user_price = float(user_price)
            except (ValueError, TypeError):
                user_price = 0
            
            # 📌 التعديل الحاسم: التجميع بالآيدي القصير
            # شرط العرض: يجب أن يكون السعر للمستخدم أكبر من صفر والحد الأدنى للكمية أكبر من صفر ويجب وجود الآيدي القصير
            if category_name and user_price > 0 and min_qty > 0 and category_id_short:
                categories_dict[category_id_short].append(service_id)
                category_map[category_id_short] = category_name # نستخدم الآيدي لتخزين الاسم
                
        # 2. التحقق من وجود فئات
        if not categories_dict:
            message = "❌ لا توجد فئات الخدمات الرشق متاحة حالياً. يرجى من المشرف جلب وتحديث الخدمات وتحديد أسعارها."
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton('🔙 - رجوع', callback_data='back'))
            try:
                if message_id:
                    bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message, parse_mode='Markdown', reply_markup=markup)
                else:
                    bot.send_message(chat_id, message, parse_mode='Markdown', reply_markup=markup)
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in str(e):
                    bot.send_message(chat_id, message, parse_mode='Markdown', reply_markup=markup)
            except Exception:
                 bot.send_message(chat_id, message, parse_mode='Markdown', reply_markup=markup)
            return

        # 3. تطبيق الترقيم (Pagination)
        items_per_page = 10
        # 📌 فرز الفئات الآن يكون حسب الآيدي القصير (المفاتيح)
        sorted_category_ids = sorted(categories_dict.keys()) 
        total_categories = len(sorted_category_ids)
        total_pages = (total_categories + items_per_page - 1) // items_per_page
        
        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page
        current_page_ids = sorted_category_ids[start_index:end_index] # استبدلنا Names بـ IDs

        # 4. إنشاء أزرار الفئات للصفحة الحالية
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        for category_id_short in current_page_ids: # نمر على الآيديات القصيرة
            category_name = category_map[category_id_short] # نستخدم الآيدي لاسترجاع الاسم الطويل للعرض
            
            # 💥 الحل الجذري: استخدام الآيدي القصير في الـ callback_data
            callback_data = f'smmc_{category_id_short}' # هذا قصير جداً (مثلاً: smmc_Instagram)
            
            markup.add(types.InlineKeyboardButton(
                f"🚀 {category_name} ({len(categories_dict[category_id_short])})", # العرض بالاسم الطويل
                callback_data=callback_data # الكولباك بالآيدي القصير
            ))
            
        # 5. أزرار التنقل بين الصفحات
        nav_buttons = []
        if page > 1:
            nav_buttons.append(types.InlineKeyboardButton('◀️ السابق', callback_data=f'smm_page_{page - 1}'))
        if page < total_pages:
            nav_buttons.append(types.InlineKeyboardButton('التالي ▶️', callback_data=f'smm_page_{page + 1}'))
        
        if nav_buttons:
            markup.row(*nav_buttons)

        markup.add(types.InlineKeyboardButton('🔙 - رجوع', callback_data='back'))

        message_text = f"🚀 *اختر فئة الخدمة التي ترغب بطلبها:* (صفحة {page} من {total_pages})"
        
        try:
            if message_id:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message_text, parse_mode='Markdown', reply_markup=markup)
            else:
                 bot.send_message(chat_id, message_text, parse_mode='Markdown', reply_markup=markup)
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" not in str(e):
                bot.send_message(chat_id, message_text, parse_mode='Markdown', reply_markup=markup)
        
        return
    # =========================================================================
    # 🚀 [نهاية الدالة المصححة]
    # =========================================================================

    # ... (باقي معالجات Callbacks) ...
    @bot.callback_query_handler(func=lambda call: call.from_user.id != DEVELOPER_ID)
    def handle_user_callbacks(call):
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        message_id = call.message.message_id
        data = call.data
        
        data_file = get_bot_data()
        user_doc = get_user_doc(user_id)
        user_balance = user_doc.get('balance', 0) if user_doc else 0
        
        # 1. التحقق الإجباري من الاشتراك
        is_subscribed = True
        for channel in CHANNELS_LIST:
            if not check_subscription(bot, user_id, channel):
                is_subscribed = False
                break
                
        if not is_subscribed:
            markup = get_subscription_markup(CHANNELS_LIST)
            bot.answer_callback_query(call.id, "🛑 يرجى الاشتراك في القنوات الإجبارية أولاً.", show_alert=True)
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
        # 🚀 [معالج 'smm_services' - استدعاء الدالة المنفصلة بالصفحة الأولى]
        # =========================================================================
        elif data == 'smm_services': 
            show_smm_categories(chat_id, message_id, page=1) 
            return

        # 🆕 [معالج التنقل بين صفحات الفئات]
        elif data.startswith('smm_page_'):
            try:
                page = int(data.split('_')[-1])
                show_smm_categories(chat_id, message_id, page=page)
            except ValueError:
                bot.answer_callback_query(call.id, "❌ خطأ في رقم الصفحة.")
            return

        # =========================================================================
        # 🚀 [معالج 'smmc_' - عرض الخدمات داخل الفئة من المخزن]
        # =========================================================================
        elif data.startswith('smmc_'):
            # 💡 التعديل: استخراج الآيدي القصير مباشرةً من الكولباك داتا
            category_id_short = data.replace('smmc_', '', 1) 
            
            markup = types.InlineKeyboardMarkup()
            
            bot_data = get_bot_data()
            all_smm_services = bot_data.get('smmkings_services', {})

            # 1. فلترة الخدمات حسب الفئة
            services_in_category = {}
            # نحتاج الاسم للعرض فقط في النهاية، يمكننا البحث عنه الآن 
            category_name_for_display = "فئة غير معروفة" 
            
            for s_id, s_info in all_smm_services.items():
                
                # 💥 التعديل: المقارنة بالآيدي القصير المخزن
                stored_category_id_short = s_info.get('category_id_short')
                
                if stored_category_id_short == category_id_short: 
                    
                    # قراءة الاسم للعرض (إذا وجد)
                    if s_info.get('category_name'):
                        category_name_for_display = s_info['category_name']
                        
                    # 💥 الفلترة: قراءة السعر من المفتاح الصحيح 'user_price'
                    user_price = s_info.get('user_price', 0) 
                    min_qty = s_info.get('min', 0)
                    
                    try:
                        user_price = float(user_price)
                    except (ValueError, TypeError):
                        user_price = 0
                    
                    # 📌 عرض الخدمة فقط إذا كانت مسعرة ولها حد أدنى واسم
                    if s_info.get('name') and user_price > 0 and min_qty > 0:
                        services_in_category[s_id] = s_info
                
            if not services_in_category:
                bot.answer_callback_query(call.id, "❌ لا توجد خدمات متاحة في هذه الفئة حاليًا.")
                markup.add(types.InlineKeyboardButton('🔙 - رجوع لقائمة الفئات', callback_data='smm_services'))
                try:
                    bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"🔗 *اختر الخدمة التي تريد طلبها من فئة {category_name_for_display}:*", parse_mode='Markdown', reply_markup=markup)
                except:
                    bot.send_message(chat_id, f"🔗 *اختر الخدمة التي تريد طلبها من فئة {category_name_for_display}:*", parse_mode='Markdown', reply_markup=markup)
                return

            # 2. بناء الأزرار للخدمات
            for service_id, service_info in services_in_category.items():
                name = service_info.get('name', f"خدمة #{service_id}")
                min_order = str(service_info.get('min', 'Min'))
                
                # استخدام سعر المستخدم المخزن/المحسوب
                user_price = service_info.get('user_price', 0) 
                try:
                    user_price = float(user_price)
                except (ValueError, TypeError):
                    user_price = 0
                
                markup.add(types.InlineKeyboardButton(f"{name} | Min {min_order} | ₽ {user_price:.2f}", callback_data=f'smm_order_{service_id}'))
                
            markup.add(types.InlineKeyboardButton('🔙 - رجوع لقائمة الفئات', callback_data='smm_services'))
            
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"🔗 *اختر الخدمة التي تريد طلبها من فئة {category_name_for_display}:*", parse_mode='Markdown', reply_markup=markup)
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in str(e):
                    bot.send_message(chat_id, f"🔗 *اختر الخدمة التي تريد طلبها من فئة {category_name_for_display}:*", parse_mode='Markdown', reply_markup=markup)
            return

        # =========================================================================
        # 🚀 [معالج 'smm_order_' - جلب التفاصيل من المخزن وبدء الطلب]
        # =========================================================================
        elif data.startswith('smm_order_'):
            service_id = data.split('_')[-1]
            
            bot_data = get_bot_data()
            all_smm_services = bot_data.get('smmkings_services', {})
            service_details = all_smm_services.get(service_id, {})
            
            if not service_details:
                bot.answer_callback_query(call.id, "❌ خطأ: تفاصيل الخدمة غير متوفرة.")
                bot.send_message(chat_id, "❌ خطأ في جلب تفاصيل الخدمة. يرجى المحاولة لاحقاً.")
                return
            
            name = service_details.get('name', 'خدمة رشق')
            min_order = str(service_details.get('min', '1'))
            max_order = str(service_details.get('max', 'غير محدود'))
            
            # 💥 الإصلاح: قراءة السعر من المفتاح الصحيح 'user_price'
            user_price = service_details.get('user_price', 0)
            try:
                user_price = float(user_price)
            except (ValueError, TypeError):
                user_price = 0

            # 📌 تحديد حالة المستخدم للمتابعة (State Management)
            # 💥 الإصلاح: استخدام str(user_id) كمفتاح
            bot_data['user_states'][str(user_id)] = {
                'state': 'awaiting_smm_link',
                'service_id': service_id,
                'service_name': name,
                'rate': user_price, # 👈 تخزين السعر الصحيح (لكل 1000)
                'min': min_order,
                'max': max_order
            }
            # 📌 حفظ حالة المستخدم فقط
            save_bot_data({'user_states': bot_data['user_states']})
            
            message_text = (
                f"✅ **أنت على وشك طلب خدمة:** `{name}`\n"
                f"💰 **السعر:** `{user_price:.2f}` روبل لكل 1000\n"
                f"🔢 **الكمية:** الحد الأدنى {min_order} والأقصى {max_order}\n\n"
                f"🔗 **الخطوة 1:** يرجى إرسال **الرابط/الـ URL** الذي تريد الرشق إليه (مثال: رابط صورة، رابط حساب، إلخ).\n"
            )
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message_text, parse_mode='Markdown', reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('❌ إلغاء الطلب', callback_data='smm_services')))
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
            for number, num_data in ready_numbers_stock.items():
                country = num_data.get('country', 'الدولة')
                app_state = num_data.get('state', 'تطبيق')
                price = num_data.get('price', 0)
                num_hidden = number[:len(number) - 4] + "••••"
                
                markup.row(types.InlineKeyboardButton(f"[{country}] {app_state} - {num_hidden} ({price} روبل)", callback_data=f"confirm_buy_ready_{number}"))
            
            markup.row(types.InlineKeyboardButton('- رجوع.', callback_data='back'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="🔰 *الأرقام الجاهزة المتاحة حالياً:*", parse_mode='Markdown', reply_markup=markup)

        # 🆕 --- تأكيد الشراء (الصيغة المطلوبة الأولى) ---
        elif data.startswith('confirm_buy_ready_'):
            number_key = data.split('_', 3)[-1] 
            ready_numbers_stock = get_ready_numbers_stock()
            number_data = ready_numbers_stock.get(number_key)

            if not number_data:
                bot.send_message(chat_id, "❌ الرقم المحدد غير متوفر حالياً. يرجى العودة للقائمة الرئيسية.", reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('- رجوع.', callback_data='back')))
                return
            
            name = number_data.get('country', 'رقم جاهز')
            price = number_data.get('price', 0)

            if user_balance < price:
                bot.send_message(chat_id, f"❌ *عذرًا، رصيدك غير كافٍ لإتمام هذه العملية.*\n\n*الرصيد المطلوب:* {price} روبل.\n*رصيدك الحالي:* {user_balance} روبل.\n\n*يمكنك شحن رصيدك عبر زر شحن الرصيد.*", parse_mode='Markdown')
                return
                
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton(f"✅ تأكيد الشراء {price} روبل", callback_data=f"execute_buy_ready_{number_key}"))
            markup.row(types.InlineKeyboardButton('❌ إلغاء', callback_data='ready'))

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
            number_key = data.split('_', 3)[-1] 
            ready_numbers_stock = get_ready_numbers_stock()
            number_data = ready_numbers_stock.get(number_key)
            
            if not number_data:
                bot.send_message(chat_id, "❌ الرقم المحدد غير متوفر حالياً. ربما تم شراؤه للتو.", reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('- رجوع.', callback_data='back')))
                return
            
            price = number_data.get('price', 0)
            
            if user_balance < price:
                bot.send_message(chat_id, f"❌ *عذرًا، رصيدك غير كافٍ لإتمام هذه العملية. رصيدك الحالي: {user_balance}*", parse_mode='Markdown')
                return

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
                f"☑️ *- تم حذف الرقم* من قائمة الأرقام الجاهزة 🤙\n"
                f"✅ - تم خصم *₽ {price}* من نقودك *( {remaining_balance} )* 💰\n"
                f"💸"
            )
            
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message_text, parse_mode='Markdown')
                
                update_user_balance(user_id, -price, is_increment=True)
                
                data_file = get_bot_data()
                if number_key in data_file.get('ready_numbers_stock', {}):
                    # 📌 يتم تحديث 'ready_numbers_stock' فقط هنا
                    del data_file['ready_numbers_stock'][number_key] 
                    save_bot_data({'ready_numbers_stock': data_file['ready_numbers_stock']}) # تعديل مُقترح لتحسين الأداء
                
                register_user(
                    user_id,
                    user_doc.get('first_name'), 
                    user_doc.get('username'), 
                    new_purchase={
                        'request_id': str(idnums),
                        'phone_number': number_key,
                        'app': number_data.get('state', 'جاهز'),
                        'price': price,
                        'status': 'ready_number_purchased',
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
                    }
                )
                
                bot.send_message(DEVELOPER_ID, 
                                 f"🔔 *تم بيع رقم جاهز!*\n"
                                 f"*الرقم:* `{number}`\n"
                                 f"*السعر:* `{price}` روبل\n"
                                 f"*للمستخدم:* `@{user_doc.get('username', 'غير متوفر')}`", 
                                 parse_mode='Markdown')

            except telebot.apihelper.ApiTelegramException as e:
                logging.error(f"Failed to send Ready Number message (Req ID: {idnums}). Reverting purchase. Error: {e}")
                
                bot.send_message(DEVELOPER_ID, 
                                 f"🚨 *فشل حرج في بيع رقم جاهز!* لم يتم خصم الرصيد. يجب التحقق.\n"
                                 f"*رقم الهاتف:* `{number_key}`\n"
                                 f"*للمستخدم:* `{user_id}`\n"
                                 f"*الخطأ:* {e}", 
                                 parse_mode='Markdown')
                
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
            markup.row(types.InlineKeyboardButton('سيرفر 1', callback_data='service_smsman')) 
            markup.row(types.InlineKeyboardButton('سيرفر 2', callback_data='service_herosms')) 
            markup.row(types.InlineKeyboardButton('- رجوع.', callback_data='back'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="📞 *اختر الخدمة التي تريد الشراء منها:*", parse_mode='Markdown', reply_markup=markup)
        
        elif data == 'Record':
            user_info = get_user_doc(user_id)
            balance = user_info.get('balance', 0)
            purchases = user_info.get('purchases', [])
            
            message_text = f"💰 رصيدك الحالي هو: *{balance}* روبل.\n\n"
            if purchases:
                message_text += "📝 **سجل مشترياتك الأخيرة:**\n"
                for i, p in enumerate(purchases[-5:]):
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
            
            server_name = 'سيرفر 1' if service == 'smsman' else ('سيرفر 2' if service == 'herosms' else 'غير معروف') 

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
            elif service == 'herosms':
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
            
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"☑️ *اختر التطبيق* الذي تريد *شراء رقم وهمي* له من خدمة **{server_name}**.", parse_mode='Markdown', reply_markup=markup)

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
                markup.row(types.InlineKeyboardButton(f"{info.get('name', code)} ({display_price} روبل)", callback_data=f'buy_{service}_{app_id}_{code}'))
            
            nav_buttons = []
            base_callback = f'show_countries_{service}_{app_id}_page_' 
            
            if page > 1:
                nav_buttons.append(types.InlineKeyboardButton('◀️ السابق', callback_data=f'{base_callback}{page - 1}'))
            if page < total_pages:
                nav_buttons.append(types.InlineKeyboardButton('التالي ▶️', callback_data=f'{base_callback}{page + 1}'))
            if nav_buttons:
                markup.row(*nav_buttons)
            
            markup.row(types.InlineKeyboardButton('رجوع', callback_data='Buynum'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"اختر الدولة التي تريدها: (صفحة {page}/{total_pages})", reply_markup=markup)

        elif data.startswith('buy_'):
            parts = data.split('_')
            service, app_id, country_code = parts[1], parts[2], parts[3]
            
            bot.answer_callback_query(call.id, "✅ جاري معالجة طلب الرقم...")

            country_info = data_file.get('countries', {}).get(service, {}).get(app_id, {}).get(country_code, {})
            
            price = country_info.get('price', 0)
            
            if user_balance < price:
                bot.send_message(chat_id, f"❌ *عذرًا، رصيدك غير كافٍ لإتمام هذه العملية.*\n\n*الرصيد المطلوب:* {price} روبل.\n*رصيدك الحالي:* {user_balance} روبل.\n\n*يمكنك شحن رصيدك عبر زر شحن الرصيد.*", parse_mode='Markdown')
                return

            result = None
            if service == 'smsman':
                result = smsman_api['request_smsman_number'](app_id, country_code)
                if result and 'request_id' in result:
                    result['success'] = True
                    result['id'] = str(result['request_id'])
                    result['number'] = result.get('Phone', result.get('number'))
            elif service == 'herosms':
                result = hero_sms_client.get_number(app_id, country_code)

            logging.info(f"Response from {service}: {result}")

            if result and result.get('success'):
                request_id = str(result.get('id', result.get('request_id', random.randint(100000000, 999999999)))) 
                phone_number = result.get('number', result.get('Phone', 'غير متوفر'))
                
                remaining_balance = user_balance - price
                
                markup = types.InlineKeyboardMarkup()
                markup.row(types.InlineKeyboardButton('♻️ - تحديث (جلب الكود)', callback_data=f'Code_{service}_{request_id}'))
                markup.row(types.InlineKeyboardButton('❌ إلغاء الطلب', callback_data=f'cancel_{service}_{request_id}'))
                markup.row(types.InlineKeyboardButton('🔄 - تغيير رقم آخر.', callback_data=f'ChangeNumber_{service}_{app_id}_{country_code}'))

                app_name = country_info.get('app_name', 'غير معروف')
                country_name = country_info.get('name', 'غير معروف')
                country_flag = country_info.get('flag', '') 

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
                # 📌 حفظ 'active_requests' فقط
                save_bot_data({'active_requests': active_requests})
                
            else:
                bot.send_message(chat_id, "❌ فشل طلب الرقم. قد يكون غير متوفر أو أن رصيدك في الخدمة غير كافٍ.")
                
        elif data.startswith('Code_'):
            parts = data.split('_')
            
            if len(parts) < 3:
                bot.answer_callback_query(call.id, "خطأ في بيانات التحديث.")
                return

            service_name = parts[1]
            request_id = parts[2]
            
            bot.answer_callback_query(call.id, "⏳ جاري التحقق من وصول الكود...")

            data_file = get_bot_data()
            active_requests = data_file.get('active_requests', {})
            active_request_info = active_requests.get(request_id, {})
            
            if not active_request_info:
                bot.send_message(chat_id, "❌ عذراً، لم يتم العثور على معلومات الطلب النشط في قاعدة البيانات. يرجى التواصل مع الدعم.")
                return

            result = None
            if service_name == 'smmkings': 
                result = smm_kings_api.get_otp(request_id)
            elif service_name == 'smsman':
                result = smsman_api['get_smsman_code'](request_id) 
            elif service_name == 'herosms':
                result = hero_sms_client.get_code(request_id)

            otp_code = result.get("code") if result and result.get("status") in ["success", "COMPLETED", "received"] and result.get("code") else None 
            
            if otp_code:
                
                markup_final = types.InlineKeyboardMarkup().row(
                    types.InlineKeyboardButton('🔙 - رجوع للقائمة الرئيسية.', callback_data='back')
                )
                
                bot.send_message(chat_id, f"✅ *رمزك هو: {otp_code}*\n\nالرقم جاهز للاستخدام.", parse_mode='Markdown')
                
                try:
                    if service_name == 'smsman':
                        smsman_api['set_smsman_status'](request_id, 6) 
                    elif service_name == 'smmkings':
                        smm_kings_api.set_status(request_id, 'STATUS_ACTIVATION_SUCCESS') 
                    elif service_name == 'herosms':
                        hero_sms_client.confirm_request(request_id) 
                        
                except Exception as e:
                    logging.error(f"Failed to set status to USED for {service_name} Req ID {request_id}: {e}")
                
                
                try:
                    new_text = call.message.text.replace("••• Pending", "✅ Completed")
                    new_text = re.sub(r'\n\*تم التحقق الآن في .+\*\n', '', new_text) 
                    
                    bot.edit_message_text(
                        chat_id=chat_id, message_id=message_id, text=new_text, parse_mode='Markdown', reply_markup=markup_final
                    )
                except Exception as e:
                    logging.error(f"Failed to edit message upon completion: {e}")
                    
                register_user(user_id, user_doc.get('first_name'), user_doc.get('username'), update_purchase_status={'request_id': request_id, 'status': 'completed'})
                
                if request_id in active_requests:
                    # 📌 يتم تحديث 'active_requests' فقط هنا
                    del active_requests[request_id]
                    save_bot_data({'active_requests': active_requests})
                
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
                try:
                    if service_name == 'smmkings':
                        smm_kings_api.set_status(request_id, 'STATUS_WAIT_CODE') 
                    elif service_name == 'smsman':
                        smsman_api['set_smsman_status'](request_id, 3) 
                    elif service_name == 'herosms':
                        hero_sms_client.set_status(request_id, 1) 
                
                    logging.info(f"Set status for {service_name} Req ID {request_id} to WAIT_CODE.")

                except Exception as e:
                    logging.error(f"Failed to set status for {service_name} Req ID {request_id}: {e}")
                
                
                current_text = call.message.text
                
                new_text = re.sub(r'\n\*تم التحقق الآن في .+\*\n', '', current_text)
                
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
            
            if service == 'smmkings': 
                result = smm_kings_api.cancel_request(request_id_raw)
                if result and result.get('success'):
                    success_api_call = True
            
            elif service == 'smsman':
                result = smsman_api['cancel_smsman_request'](request_id_raw) 
                if result and (result.get('message') == 'STATUS_CANCEL' or result.get('status') in ['success', 'cancelled']):
                    success_api_call = True
            
            elif service == 'herosms':
                result = hero_sms_client.cancel_request(request_id_raw)
                if result and result.get('success'):
                    success_api_call = True
            
            logging.info(f"Response from {service} for CANCEL Req ID {request_id_raw}: {result}")
            
            if success_api_call:
                
                request_info_from_purchases = get_cancellable_request_info(user_doc, request_id_raw)
                
                if request_info_from_purchases and request_info_from_purchases.get('price_to_restore', 0) > 0:
                    try:
                        price_to_restore = request_info_from_purchases.get('price_to_restore')
                        request_id_in_db = request_info_from_purchases.get('request_id_in_db')
                        
                        update_user_balance(user_id, price_to_restore, is_increment=True)
                        
                        register_user(
                            user_id, 
                            user_doc.get('first_name'), 
                            user_doc.get('username'),
                            update_purchase_status={
                                'request_id': request_id_in_db, 
                                'status': 'cancelled'
                            }
                        )
                        
                        data_file = get_bot_data()
                        active_requests = data_file.get('active_requests', {})
                        if str(request_id_in_db) in active_requests:
                            del active_requests[str(request_id_in_db)]
                            # 📌 حفظ 'active_requests' فقط
                            save_bot_data({'active_requests': active_requests})
                        
                        bot.send_message(chat_id, f"✅ **تم إلغاء الطلب بنجاح!** تم استرجاع مبلغ *{price_to_restore}* روبل إلى رصيدك.", parse_mode='Markdown')
                        
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
                    bot.send_message(chat_id, f"⚠️ تم إلغاء طلبك في الموقع بنجاح، لكنه **غير مسجل كطلب معلق في سجل مشترياتك**. لم يتم إرجاع الرصيد تلقائياً. يرجى التواصل فوراً مع الدعم (@{ESM7AT}) وتقديم آيدي الطلب: `{request_id_raw}`.", parse_mode='Markdown')

            else:
                bot.send_message(chat_id, "❌ فشل إلغاء الطلب في الموقع. يرجى المحاولة مرة أخرى أو التواصل مع الدعم.")
        
        elif data.startswith('ChangeNumber_'):
            bot.send_message(chat_id, "🔄 *سيتم إضافة وظيفة تغيير الرقم قريباً.*")
            return
            
    # --------------------------------------------------------------------------
    # ⚔️ [المعالجات ذات الأولوية العالية: يجب أن تكون في المقدمة]
    # --------------------------------------------------------------------------
            
    # 💡 [معالج رسائل: إدخال الرابط لطلب SMM]
    @bot.message_handler(func=lambda message: get_bot_data().get('user_states', {}).get(str(message.from_user.id), {}).get('state') == 'awaiting_smm_link')
    def handle_smm_link_input(message):
        # 💥 الإصلاح: تحويل الآيدي إلى نص مباشرة
        user_id = str(message.from_user.id)
        link = message.text.strip()
        
        bot_data = get_bot_data()
        # 💥 الإصلاح: استخدام user_id كنص
        user_state = bot_data['user_states'].get(user_id)
        
        if not user_state:
            bot.send_message(int(user_id), "❌ انتهت صلاحية الطلب. يرجى البدء من جديد.", reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('🔙 - القائمة الرئيسية', callback_data='back')))
            return
        
        # 📌 الخطوة 1: تخزين الرابط وتغيير الحالة إلى انتظار الكمية
        user_state['link'] = link
        user_state['state'] = 'awaiting_smm_quantity'
        
        # 💥 الإصلاح: استخدام user_id كنص
        bot_data['user_states'][user_id] = user_state
        
        # حفظ المفتاح الذي تم تحديثه فقط
        save_bot_data({'user_states': bot_data['user_states']})
        
        min_qty = user_state.get('min', '1')
        max_qty = user_state.get('max', 'غير محدود')
        
        message_text = (
            f"🔗 **تم حفظ الرابط:** `{link}`\n"
            f"🔢 **الخطوة 2:** يرجى إرسال **الكمية المطلوبة** (أقل كمية هي {min_qty}، والحد الأقصى {max_qty})."
        )
        bot.send_message(int(user_id), message_text, parse_mode='Markdown')
    
    # 💡 [معالج رسائل: إدخال الكمية لطلب SMM]
    @bot.message_handler(func=lambda message: get_bot_data().get('user_states', {}).get(str(message.from_user.id), {}).get('state') == 'awaiting_smm_quantity')
    def handle_smm_quantity_input(message):
        # 💥 الإصلاح: تحويل الآيدي إلى نص مباشرة
        user_id = str(message.from_user.id)
        
        bot_data = get_bot_data()
        # 💥 الإصلاح: استخدام user_id كنص
        user_state = bot_data['user_states'].get(user_id)
        
        if not user_state:
            bot.send_message(int(user_id), "❌ انتهت صلاحية الطلب. يرجى البدء من جديد.", reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('🔙 - القائمة الرئيسية', callback_data='back')))
            return

        try:
            quantity = int(message.text.strip())
        except ValueError:
            bot.send_message(int(user_id), "❌ *الكمية غير صحيحة. يرجى إرسال رقم صحيح.*", parse_mode='Markdown')
            return
            
        if quantity <= 0:
            bot.send_message(int(user_id), "❌ *الكمية يجب أن تكون رقماً موجباً.*", parse_mode='Markdown')
            return
        
        service_id = user_state.get('service_id')
        link = user_state.get('link')
        rate_per_k = float(user_state.get('rate', 0)) # السعر لكل 1000 وحدة
        min_qty = int(user_state.get('min', 1))
        max_qty = int(user_state.get('max', 999999999)) 
        service_name = user_state.get('service_name', 'خدمة رشق')
        
        if quantity < min_qty:
            bot.send_message(int(user_id), f"❌ *الكمية المدخلة أقل من الحد الأدنى. الحد الأدنى هو {min_qty}.*", parse_mode='Markdown')
            return
        
        if quantity > max_qty:
             bot.send_message(int(user_id), f"❌ *الكمية المدخلة أكبر من الحد الأقصى. الحد الأقصى هو {max_qty}.*", parse_mode='Markdown')
             return
            
        price = (quantity / 1000) * rate_per_k
        user_doc = get_user_doc(int(user_id))
        user_balance = user_doc.get('balance', 0)
        
        if user_balance < price:
            bot.send_message(int(user_id), f"❌ *عذرًا، رصيدك غير كافٍ لإتمام هذه العملية. الرصيد المطلوب: {price:.2f} روبل.*", parse_mode='Markdown')
            
            # 💥 الإصلاح: استخدام user_id كنص عند الحذف
            del bot_data['user_states'][user_id]
            
            # حفظ حقل 'user_states' فقط
            save_bot_data({'user_states': bot_data['user_states']})
            return

        try:
            order_result = smm_kings_api.add_order(service_id, link, quantity)
            
            if order_result and 'order' in order_result:
                order_id = str(order_result.get('order'))
                remaining_balance = user_balance - price
                
                update_user_balance(int(user_id), -price, is_increment=True)
                
                register_user(
                    int(user_id), 
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
                
                message_text = (
                    f"✅ **تم تقديم طلب الرشق بنجاح!**\n"
                    f"🔥 **الخدمة:** `{service_name}`\n"
                    f"🔗 **الرابط:** `{link}`\n"
                    f"🔢 **الكمية:** `{quantity}`\n"
                    f"💸 **السعر:** `{price:.2f}` روبل\n"
                    f"🅿️ **رقم الطلب:** `{order_id}`\n\n"
                    f"🤖 **رصيدك المتبقي:** `{remaining_balance:.2f}` روبل."
                )
                bot.send_message(int(user_id), message_text, parse_mode='Markdown', reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('🔙 - القائمة الرئيسية', callback_data='back')))

            else:
                bot.send_message(int(user_id), f"❌ **فشل تقديم الطلب:** لم يتمكن البوت من إرسال الطلب إلى SMMKings. لم يتم خصم رصيدك. قد يكون السبب هو خطأ في الرابط أو عدم توفر الخدمة حالياً.", parse_mode='Markdown')
            
        except Exception as e:
            logging.error(f"SMMKings add_order exception: {e}")
            bot.send_message(int(user_id), "❌ **فشل حرج:** حدث خطأ غير متوقع أثناء محاولة تقديم الطلب. لم يتم خصم رصيدك. يرجى التواصل مع الدعم.", parse_mode='Markdown')

        # 📌 مسح حالة المستخدم بعد إكمال/فشل الطلب
        # 💥 الإصلاح: استخدام user_id كنص عند الحذف
        del bot_data['user_states'][user_id]
        
        # حفظ حقل 'user_states' فقط
        save_bot_data({'user_states': bot_data['user_states']})
        
    # --------------------------------------------------------------------------
    # 🛑 [المعالج الأقل أولوية: التقاط الرسائل العامة]
    # --------------------------------------------------------------------------

    # هذا المعالج يلتقط أي رسالة لا يلتقطها أي معالج آخر (مثل /start)
    @bot.message_handler(func=lambda message: message.from_user.id != DEVELOPER_ID)
    def handle_user_messages(message):
        chat_id = message.chat.id
        user_id = message.from_user.id
        first_name = message.from_user.first_name
        username = message.from_user.username
        
        if message.chat.type != "private":
            return
        
        referrer_id = None
        if message.text.startswith('/start'):
            try:
                payload = message.text.split()[1]
                if payload.isdigit():
                    referrer_id = int(payload)
            except:
                pass
        
        register_user(user_id, first_name, username, referrer_id=referrer_id)

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

        if message.text.startswith('/start'):
             show_main_menu(chat_id)
             return

        elif message.text in ['/balance', 'رصيدي']:
            user_doc = get_user_doc(user_id)
            balance = user_doc.get('balance', 0) if user_doc else 0
            bot.send_message(chat_id, f"💰 رصيدك الحالي هو: *{balance}* روبل.", parse_mode='Markdown')
            return

        elif message.text in ['/invite', 'رابط الإحالة']:
            bot.send_message(chat_id, 
                             f"🔗 *رابط الإحالة الخاص بك:*\n`https://t.me/{bot.get_me().username}?start={user_id}`\n\n"
                             f"🤑 *عندما يقوم صديقك بالتسجيل عبر هذا الرابط، ستحصل أنت على 0.25 روبل مجاناً.*", 
                             parse_mode='Markdown')
            return
        
        else:
            # رسالة افتراضية لأي رسالة أخرى
            bot.send_message(chat_id, "⚠️ **رسالة غير مفهومة.** يمكنك استخدام الأمر `/start` للعودة إلى القائمة الرئيسية أو استخدام الأزرار المتاحة.", parse_mode='Markdown')

    # --------------------------------------------------------------------------
