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

# 💡 --- MongoDB IMPORTS ---
from db_manager import (
    get_user_doc,
    update_user_balance,
    register_user,
    get_bot_data,
    save_bot_data
)

def setup_user_handlers(bot, DEVELOPER_ID, ESM7AT, EESSMT, viotp_client, smsman_api, tiger_sms_client):
    
    # دالة مساعدة للوصول إلى مخزون الأرقام الجاهزة
    def get_ready_numbers_stock():
        return get_bot_data().get('ready_numbers_stock', {})

    # 💡 [التصحيح النهائي لمرونة المطابقة] دالة مساعدة مرنة للبحث عن الطلب في سجل المشتريات
    def get_cancellable_request_info(user_doc, request_id):
        purchases = user_doc.get('purchases', [])
        # تحويل request_id القادم من الكولباك إلى سلسلة نصية
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
            
            # حالة الطلب لا يجب أن تكون مكتملة أو ملغاة مسبقاً
            if is_match and p.get('status') not in ['completed', 'cancelled', 'ready_number_purchased']: 
                # الطلبات الجاهزة لها حالة خاصة لا تحتاج للإلغاء في API
                
                # وجدنا الطلب، نُعيد معلوماته لاسترجاع الرصيد
                return {
                    'user_id': user_doc.get('_id'),
                    'price_to_restore': p.get('price', 0),
                    'request_id_in_db': p_request_id # نُعيد المعرف كما هو مخزن
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
        markup.row(types.InlineKeyboardButton('💰︙شحن رصيدك', callback_data='Payment'), types.InlineKeyboardButton('👤︙قسم الرشق', callback_data='sh'))
        markup.row(types.InlineKeyboardButton('🅿️︙كشف الحساب', callback_data='Record'), types.InlineKeyboardButton('🛍︙قسم العروض', callback_data='Wo'))
        markup.row(types.InlineKeyboardButton('☑️︙قسم العشوائي', callback_data='worldwide'), types.InlineKeyboardButton('👑︙قسم الملكي', callback_data='saavmotamy'))
        # 💡 [تم تحديث الزر إلى رابط الإحالة]
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


    # 💡 [تعديل معالج الرسائل: دعم /start مع الإحالة والتحقق الإجباري]
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
        
        # 💡 [تم حذف معالجات /start, /balance القديمة من هنا]
        
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
            
            if user_balance < service_price:
                bot.send_message(chat_id, f"❌ *عذرًا، رصيدك غير كافٍ لإتمام هذه العملية.*\n\n*الرصيد المطلوب:* {service_price} روبل.\n*رصيدك الحالي:* {user_balance} روبل.\n\n*يمكنك شحن رصيدك عبر زر شحن الرصيد.*", parse_mode='Markdown')
                return

            update_user_balance(user_id, -service_price, is_increment=True)
            
            register_user(
                user_id, 
                user_doc.get('first_name'), 
                user_doc.get('username'), 
                new_purchase={
                    'service_name': service_name,
                    'price': service_price,
                    'status': 'sh_purchased',
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
                }
            )

            new_user_doc = get_user_doc(user_id)
            remaining_balance = new_user_doc.get('balance', 0)

            bot.send_message(chat_id, f"✅ تم شراء خدمة `{service_name}` بنجاح! سيتم معالجة طلبك قريباً.\n*رصيدك المتبقي:* `{remaining_balance}` روبل.", parse_mode='Markdown')
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
            # 💡 [تم حذف معالج assignment القديم لأنه تم استبداله بزر الإحالة]
            bot.send_message(chat_id, "💰 *يمكنك ربح روبل مجانية عن طريق مشاركة رابط الإحالة. عد للقائمة الرئيسية واضغط على 'رابط الإحالة'.*", parse_mode='Markdown')
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
                    save_bot_data({'ready_numbers_stock': data_file['ready_numbers_stock']})
                
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
            markup.row(types.InlineKeyboardButton('سيرفر 1', callback_data='service_viotp'))
            markup.row(types.InlineKeyboardButton('سيرفر 2', callback_data='service_smsman'))
            markup.row(types.InlineKeyboardButton('سيرفر 3', callback_data='service_tigersms'))
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
                    phone_number = p.get('phone_number', p.get('app_name', p.get('service_name', 'غير متوفر'))) 
                    price = p.get('price', 0)
                    timestamp = p.get('timestamp', 'غير متوفر')
                    status = p.get('status', 'غير معروف')
                    message_text += f"*{i+1}. شراء {phone_number} بسعر {price} روبل ({status}) في {timestamp}*\n"
            else:
                message_text += "❌ لا يوجد سجل مشتريات حتى الآن."
            
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message_text, parse_mode='Markdown', reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('🔙 - رجوع', callback_data='back')))
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in str(e):
                    bot.send_message(chat_id, message_text, parse_mode='Markdown', reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('🔙 - رجوع', callback_data='back')))
            return
            
        elif data.startswith('service_'):
            parts = data.split('_')
            service = parts[1]
            markup = types.InlineKeyboardMarkup()
            
            if service == 'viotp':
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
            elif service == 'smsman':
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
            server_name = 'سيرفر 1' if service == 'viotp' else ('سيرفر 2' if service == 'smsman' else 'سيرفر 3')
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

        # 💡 [بداية التعديل الأساسي: معالج الشراء]
        elif data.startswith('buy_'):
            parts = data.split('_')
            service, app_id, country_code = parts[1], parts[2], parts[3]
            
            bot.answer_callback_query(call.id, "✅ جاري معالجة طلب الرقم...")

            country_info = data_file.get('countries', {}).get(service, {}).get(app_id, {}).get(country_code, {})
            price = country_info.get('price', 0)
            
            if user_balance < price:
                bot.send_message(chat_id, f"❌ *عذرًا، رصيدك غير كافٍ لإتمام هذه العملية.*\n\n*الرصيد المطلوب:* {price} روبل.\n*رصيدك الحالي:* {user_balance} روبل.\n\n*يمكنك شحن رصيدك عبر زر شحن الرصيد.*", parse_mode='Markdown')
                return

            # *** 1. الاتصال بالـ API وجلب الرقم ***
            result = None
            if service == 'viotp':
                result = viotp_client.buy_number(app_id, country_code) 
            elif service == 'smsman':
                result = smsman_api['request_smsman_number'](app_id, country_code)
                if result and 'request_id' in result:
                    result['success'] = True
                    result['id'] = str(result['request_id'])
                    result['number'] = result['Phone']
            elif service == 'tigersms':
                result = tiger_sms_client.get_number(app_id, country_code)

            logging.info(f"Response from {service}: {result}")

            if result and result.get('success'):
                request_id = str(result.get('id', result.get('request_id', random.randint(100000000, 999999999)))) 
                phone_number = result.get('number', result.get('Phone', 'غير متوفر'))
                
                remaining_balance = user_balance - price
                
                # *** 2. إعداد الأزرار الجديدة (التحديث اليدوي) ***
                markup = types.InlineKeyboardMarkup()
                # 💡 الزر الرئيسي الجديد: جلب الكود (Code_)
                markup.row(types.InlineKeyboardButton('♻️ - تحديث (جلب الكود)', callback_data=f'Code_{service}_{request_id}'))
                # 💡 زر الإلغاء
                markup.row(types.InlineKeyboardButton('❌ إلغاء الطلب', callback_data=f'cancel_{service}_{request_id}'))
                # 💡 زر تغيير الرقم 
                markup.row(types.InlineKeyboardButton('🔄 - تغيير رقم آخر.', callback_data=f'ChangeNumber_{service}_{app_id}_{country_code}'))

                app_name = country_info.get('name', 'غير معروف')
                country_name = country_info.get('name', 'غير معروف')
                
                # 💡 استخدام التوقيت المحلي لزيادة الدقة
                tz = pytz.timezone('Asia/Aden') 
                current_time = datetime.now(tz).strftime('%I:%M:%S %p')
                
                message_text = (
                    f"**☎️ - الرقم:** `{phone_number}`\n"
                    f"**🧿 - التطبيق:** `{app_name}`\n"
                    f"**📥 - الدولة:** `{country_name}`\n"
                    f"**🔥 - الأيدي:** `{user_id}`\n"
                    f"**💸 - السعر:** `Ꝑ{price}`\n"
                    f"**🤖 - الرصيد المتبقي:** `{remaining_balance}`\n" 
                    f"**🔄 - معرف المشتري:** `@{user_doc.get('username', 'غير متوفر')}`\n"
                    f"**🎦 - الموقع:** `soper.com`\n\n"
                    f"**🌀 - الحالة:** *••• Pending*\n"
                    f"**⏰ - وقت الطلب:** {current_time}\n\n"
                    f"⚠️ *ملاحظة هامة:* أدخل الرقم في التطبيق ثم اضغط على زر *تحديث* لجلب الكود."

                    # 💡 [إضافة منطق setStatus بعد الشراء لـ VIOTP]
                    # من الأفضل دائماً إرسال setStatus(3) لـ VIOTP بعد الحصول على الرقم لضمان الانتظار
                    # تم حذف هذه الخطوة هنا وتركها في زر Code_ لتقليل التعقيد
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
                        'app_name': app_name
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
                    'app_name': app_name
                }
                data_file['active_requests'] = active_requests
                save_bot_data(data_file)
                
            else:
                bot.send_message(chat_id, "❌ فشل طلب الرقم. قد يكون غير متوفر أو أن رصيدك في الخدمة غير كافٍ.")
                
        # 💡 [المعالج المُعدَّل: التحديث اليدوي للكود]
        elif data.startswith('Code_'):
            parts = data.split('_')
            
            if len(parts) < 3:
                bot.answer_callback_query(call.id, "خطأ في بيانات التحديث.")
                return

            service_name = parts[1]
            request_id = parts[2]
            
            bot.answer_callback_query(call.id, "⏳ جاري التحقق من وصول الكود...")

            # 1. استدعاء API لمرة واحدة
            result = None
            if service_name == 'viotp':
                result = viotp_client.get_otp(request_id)
            elif service_name == 'smsman':
                # تم افتراض أن get_smsman_code تم تعديلها لتعيد المفتاح 'code'
                result = smsman_api['get_smsman_code'](request_id) 
            elif service_name == 'tigersms':
                result = tiger_sms_client.get_code(request_id)

            otp_code = result.get('code') if result and result.get('success') and result.get('code') else None
            
            # 2. معالجة النتيجة
            if otp_code:
                # [نجاح - تم العثور على الكود]
                
                # إعداد لوحة المفاتيح النهائية
                markup_final = types.InlineKeyboardMarkup().row(
                    types.InlineKeyboardButton('🔙 - رجوع للقائمة الرئيسية.', callback_data='back')
                )
                
                # إرسال الكود في رسالة جديدة
                bot.send_message(chat_id, f"✅ *رمزك هو: {otp_code}*\n\nالرقم جاهز للاستخدام.", parse_mode='Markdown')
                
                # ----------------------------------------------------------------------------------
                # 💡 [إضافة مهمة: إخبار API بـ "تم الاستخدام" (Completed) لإنهاء الطلب]
                # ----------------------------------------------------------------------------------
                try:
                    # الحالة 6 تعني "تم الانتهاء/الاستخدام" في SMSMAN
                    if service_name == 'smsman':
                        smsman_api['set_smsman_status'](request_id, 6) 
                    elif service_name == 'viotp':
                        # الحالة 6 تعني "تم النجاح" (Success) في VIOTP (الافتراض)
                        viotp_client.set_status(request_id, 6)
                    elif service_name == 'tigersms':
                        # نستخدم حالة SUCCESS لـ TigerSMS (الافتراض)
                        tiger_sms_client.set_status(request_id, 'STATUS_SUCCESS') 
                        
                except Exception as e:
                    logging.error(f"Failed to set status to USED for {service_name} Req ID {request_id}: {e}")
                
                
                # تعديل الرسالة الأصلية لوضع علامة (مكتمل) وإزالة الأزرار
                try:
                    new_text = call.message.text.replace("••• Pending", "✅ Completed")
                    # 💡 حذف رسائل التحقق السابقة باستخدام مكتبة re
                    new_text = re.sub(r'\n\*تم التحقق الآن في .+\*\n', '', new_text) 
                    
                    bot.edit_message_text(
                        chat_id=chat_id, message_id=message_id, text=new_text, parse_mode='Markdown', reply_markup=markup_final
                    )
                except Exception as e:
                    logging.error(f"Failed to edit message upon completion: {e}")
                    
                # تحديث قاعدة البيانات وحذف الطلب من active_requests
                register_user(user_id, user_doc.get('first_name'), user_doc.get('username'), update_purchase_status={'request_id': request_id, 'status': 'completed'})
                
                data_file = get_bot_data()
                if request_id in data_file.get('active_requests', {}):
                    active_request_info = data_file['active_requests'].pop(request_id) # استخدام .pop لحذف العنصر والحصول عليه
                    save_bot_data({'active_requests': data_file['active_requests']})
                
                # 💡 إرسال المنشور الترويجي إلى القناة
                try:
                    app_name = active_request_info.get('app_name', 'غير معروف')
                    promo_message = (
                        f"🎉 *تم شراء رقم جديد بنجاح!* 🎉\n\n"
                        f"**التطبيق:** `{app_name}`\n"
                        f"**الخدمة:** تم التفعيل بنجاح! ✅\n\n"
                        f"اشترِ رقمك الافتراضي الآن من @{EESSMT}"
                    )
                    bot.send_message(f'@{EESSMT}', promo_message, parse_mode='Markdown')
                except Exception as e:
                    logging.error(f"Failed to send promo message upon completion: {e}")

            else:
                # [فشل - الكود لم يصل بعد]
                
                # 💡 [الإضافة الرئيسية لحل مشكلة التحديث اليدوي: إخبار API بالاستمرار في الانتظار]
                try:
                    if service_name == 'viotp':
                        # الحالة 3 لـ VIOTP تعني "جاهز، لكن بانتظار الكود" (الافتراض)
                        viotp_client.set_status(request_id, 3) 
                    elif service_name == 'smsman':
                        # 💥 نستخدم الحالة 3 لطلب "انتظار الكود" في SMSMAN
                        smsman_api['set_smsman_status'](request_id, 3) 
                    elif service_name == 'tigersms':
                        # نستخدم حالة STATUS_WAIT_CODE لطلب الانتظار في TigerSMS (الافتراض)
                        tiger_sms_client.set_status(request_id, 'STATUS_WAIT_CODE') 
                
                    logging.info(f"Set status for {service_name} Req ID {request_id} to WAIT_CODE (Status 3/WAIT_CODE).")

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
            service, request_id_raw = parts[1], parts[2] # request_id_raw هو الآن سلسلة نصية
            
            bot.answer_callback_query(call.id, "جاري معالجة طلب الإلغاء...")
            
            result = None
            success_api_call = False 
            
            # 1. محاولة الإلغاء في API الموقع
            if service == 'viotp':
                result = viotp_client.cancel_request(request_id_raw)
                if result and result.get('success'):
                    success_api_call = True
            
            elif service == 'smsman':
                # ملاحظة: API SMSMAN تتطلب set_smsman_status برمز -1 للإلغاء
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
                        # نستخدم المعرف كما هو مخزن في قاعدة البيانات لضمان تحديث صحيح
                        request_id_in_db = request_info_from_purchases.get('request_id_in_db')
                        
                        # أ. استرجاع الرصيد للمستخدم
                        update_user_balance(user_id, price_to_restore, is_increment=True)
                        
                        # ب. تحديث حالة الطلب في سجل المشتريات إلى "cancelled"
                        register_user(
                            user_id, 
                            user_doc.get('first_name'), 
                            user_doc.get('username'),
                            update_purchase_status={
                                'request_id': request_id_in_db, # نستخدم request_id_in_db للتحديث
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
                            final_text = re.sub(r'\n\*تم التحقق الآن في .+\*\n', '', final_text) # إزالة أي رسائل تحقق سابقة
                            
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
