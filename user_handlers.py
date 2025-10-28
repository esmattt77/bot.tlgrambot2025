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
from db_manager import (
    get_user_doc,
    update_user_balance,
    register_user,
    get_bot_data,
    save_bot_data
)

# =========================================================================
# 💡 [دالة تنسيق رسالة الإشعار للقناة] - التعديل الجديد
# =========================================================================
def format_success_message(order_id, country_name, country_flag, user_id, price, phone_number, code, service_name, activation_type="يدوي"):
    """
    تقوم ببناء رسالة إشعار النجاح بالتنسيق المطلوب.
    """
    
    # إعداد التوقيت المحلي
    tz = pytz.timezone('Asia/Aden') 
    now = datetime.now(tz)
    
    # تنسيق التاريخ والوقت (يجب أن يتم تثبيت مكتبة locale أو استخدام دالة تحويل لتنسيق عربي مثالي)
    # سنستخدم التنسيق الإنجليزي القياسي لضمان عدم حدوث أخطاء
    date_time_str = now.strftime("%A %d %B %Y | %I:%M:%S %p")
    
    # إخفاء آخر 3 أرقام من معرف العميل وآخر 4 من رقم الهاتف
    user_id_str = str(user_id)
    masked_user_id = user_id_str[:-3] + "•••"
    
    # التأكد من أن رقم الهاتف يبدأ برمز الدولة
    masked_phone_number = phone_number[:-4] + "••••"

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

# 💡 [التعديل هنا] - تمت إضافة smmkings_client
def setup_user_handlers(bot, DEVELOPER_ID, ESM7AT, EESSMT, viotp_client, smsman_api, tiger_sms_client, smmkings_client):
    
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
            
            # حالة الطلب لا يجب أن تكون مكتملة أو ملغاة مسبقاً
            if is_match and p.get('status') not in ['completed', 'cancelled', 'ready_number_purchased', 'sh_purchased']: 
                
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
        markup.row(types.InlineKeyboardButton('💰︙شحن رصيدك', callback_data='Payment'), types.InlineKeyboardButton('👤︙قسم الرشق', callback_data='sh'))
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


    # 💡 [تعديل معالج الرسائل: دعم /start مع الإحالة والتحقق الإجباري وخدمات الرشق SMMKings]
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
        
        # 4. 🚀 [معالجة مدخلات خدمات الرشق SMMKings]
        data_file = get_bot_data()
        awaiting_sh_order = data_file.get('awaiting_sh_order', {})
        
        if awaiting_sh_order and awaiting_sh_order.get('user_id') == user_id:
            try:
                # محاولة فصل الرابط والكمية
                parts = message.text.split()
                if len(parts) != 2:
                    raise ValueError("التنسيق غير صحيح. يرجى إرسال الرابط والكمية مفصولين بمسافة واحدة.")
                
                link = parts[0]
                quantity = int(parts[1])
                
                if quantity <= 0:
                    raise ValueError("يجب أن تكون الكمية موجبة.")

                service_id = awaiting_sh_order['service_id']
                service_name = awaiting_sh_order['service_name']
                price_per_k = awaiting_sh_order['price'] # السعر المعروض للمستخدم هو سعر الخدمة بالكامل

                # ⚠️ يجب التأكد أن خدمة SMMKings تعمل بنظام (سعر/1000) أو (سعر/1)
                # بما أننا لا نعرف آلية التسعير الدقيقة لخدمة معينة، سنفترض أن السعر المعروض هو سعر الوحدة.
                # سنفترض أننا سنحتاج إلى حساب التكلفة الإجمالية بناءً على الكمية.
                # لنفترض أن: price_per_k هو سعر **1000** وحدة.
                
                # لحساب التكلفة الإجمالية: 
                # التكلفة = (سعر الألف / 1000) * الكمية
                # 💡 بما أننا لا نعرف التسعير، سنفترض أن service_price الذي تم تخزينه هو سعر الوحدة.
                # **يجب تعديل هذا الجزء بناءً على طريقة التسعير الفعلية في SMMKings API**
                
                user_doc = get_user_doc(user_id)
                user_balance = user_doc.get('balance', 0)
                
                # *** سنفترض أن سعر الخدمة بالكامل (Total Price) يتم حسابه في العميل smmkings_client. ***
                # *** سنستخدم منطق تقريبي: price_per_k هو سعر الوحدة. ***
                # *************************************************************************
                # التكلفة الكلية التقديرية (للتأكد من أن المستخدم يمكنه الدفع)
                # *************************************************************************
                
                # 💡 بما أننا لا نملك معلومات عن طريقة تسعير الـ SMMKings، 
                # سنعتمد على أن smmkings_client سيُعيد لنا التكلفة المطلوبة للخصم.
                
                # خصم المبلغ المتوفر في رصيد المستخدم بشكل مؤقت (للتأكد من عدم إجراء عملية أخرى)
                # في البداية، يجب التحقق من الرصيد:

                # **1. الاتصال بـ SMMKings لتحديد التكلفة وإرسال الطلب:**
                try:
                    # نستخدم دالة place_order التي يجب أن تكون موجودة في smmkings_client
                    # هذه الدالة يجب أن تحسب التكلفة الكلية وتُرسل الطلب.
                    smmkings_response = smmkings_client.place_order(
                        service_id=service_id, 
                        link=link, 
                        quantity=quantity
                    )
                except Exception as e:
                    logging.error(f"SMMKings API Error for user {user_id}: {e}")
                    bot.send_message(chat_id, "❌ **خطأ في API خدمات الرشق:** تعذر التواصل مع مزود الخدمة. يرجى المحاولة لاحقاً.")
                    # ⚠️ يجب مسح حالة الانتظار
                    data_file['awaiting_sh_order'] = {}
                    save_bot_data(data_file)
                    return

                if smmkings_response and smmkings_response.get('success'):
                    order_id = smmkings_response.get('order_id')
                    total_price = smmkings_response.get('charge') # السعر الفعلي الذي خصمه الموقع

                    if user_balance < total_price:
                        # هذا لا يجب أن يحدث إذا تم التحقق من الرصيد بشكل صحيح في Callback Query،
                        # ولكن في حال تغير السعر أو تأخر الطلب، نعالجها هنا.
                        bot.send_message(chat_id, f"❌ **عذرًا، رصيدك غير كافٍ الآن.** الرصيد المطلوب: {total_price} روبل.")
                        
                        # ⚠️ يجب الإلغاء في SMMKings إذا تم الطلب بنجاح وتم اكتشاف عدم كفاية الرصيد بعد ذلك
                        # (بافتراض أن الموقع لا يخصم إلا بعد التأكد من وجود الرصيد لديه)
                        # هنا سنفترض أن الموقع لم ينفذ الطلب بسبب الرصيد لدينا.
                        
                        # نمسح حالة الانتظار ونعيد المستخدم للقائمة
                        data_file['awaiting_sh_order'] = {}
                        save_bot_data(data_file)
                        return
                    
                    # 2. خصم الرصيد وتسجيل العملية
                    update_user_balance(user_id, -total_price, is_increment=True)
                    remaining_balance = user_balance - total_price

                    register_user(
                        user_id,
                        first_name, 
                        username,
                        new_purchase={
                            'request_id': str(order_id), 
                            'service': 'smmkings',
                            'price': total_price,
                            'status': 'sh_purchased', 
                            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
                            'app_name': service_name,
                            'link': link,
                            'quantity': quantity
                        }
                    )

                    # 3. إرسال رسالة النجاح
                    message_text = (
                        f"✅ **تم إرسال طلب الرشق بنجاح!**\n\n"
                        f"⭐ **الخدمة:** `{service_name}`\n"
                        f"🔗 **الرابط:** `{link}`\n"
                        f"🔢 **الكمية:** `{quantity}`\n"
                        f"💸 **التكلفة:** `{total_price}` روبل\n"
                        f"🆔 **رقم الطلب (SMMKings):** `{order_id}`\n\n"
                        f"💰 **رصيدك المتبقي:** `{remaining_balance}` روبل\n\n"
                        f"*⚠️ سيتم تنفيذ طلبك خلال وقت قصير. يمكنك التحقق من حالة طلبك في سجل المشتريات.*"
                    )
                    bot.send_message(chat_id, message_text, parse_mode='Markdown', reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('🔙 - رجوع', callback_data='back')))

                    # إشعار للمطور
                    bot.send_message(DEVELOPER_ID, 
                                     f"🔔 *تم إرسال طلب رشق جديد!*\n"
                                     f"**الخدمة:** {service_name} | **الكمية:** {quantity}\n"
                                     f"**التكلفة:** {total_price} روبل\n"
                                     f"*للمستخدم:* `@{username}`", 
                                     parse_mode='Markdown')

                else:
                    # فشل في إرسال الطلب إلى SMMKings
                    error_msg = smmkings_response.get('error', 'خطأ غير معروف في مزود الخدمة.') if smmkings_response else 'فشل في الاتصال.'
                    bot.send_message(chat_id, f"❌ **فشل إرسال طلب الرشق.** السبب: {error_msg}")
                    
                # 4. مسح حالة الانتظار
                data_file['awaiting_sh_order'] = {}
                save_bot_data(data_file)
                return # إنهاء معالجة الرسائل هنا
                
            except ValueError as ve:
                bot.send_message(chat_id, f"❌ **خطأ في الإدخال:** {ve}\n\nيرجى إرسال الرسالة بالتنسيق الصحيح: `الرابط الكمية`.")
                return
            except Exception as e:
                logging.error(f"Critical error processing SMMKings order for user {user_id}: {e}")
                bot.send_message(chat_id, "❌ **حدث خطأ غير متوقع** أثناء معالجة طلب الرشق. يرجى التواصل مع الدعم.")
                # مسح حالة الانتظار في حالة الخطأ
                data_file['awaiting_sh_order'] = {}
                save_bot_data(data_file)
                return
        # ---------------------------------------------------- [نهاية معالج الرشق]

        # 5. معالجة الرسائل العادية (غير الأوامر وغير الرشق)
        if message.text:
             bot.send_message(chat_id, "⚠️ *لم أفهم رسالتك. يرجى استخدام الأزرار أدناه أو قائمة /start.*", parse_mode='Markdown')


        
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
            # ⚠️ مسح حالة الانتظار لأمر الرشق عند العودة
            data_file['awaiting_sh_order'] = {}
            save_bot_data(data_file)
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

        # 💡 [التعديل الرئيسي هنا] - عرض خدمات الرشق SMMKings
        elif data == 'sh':
            bot.answer_callback_query(call.id, "⏳ جاري جلب خدمات الرشق...")
            markup = types.InlineKeyboardMarkup()
            
            # استدعاء للحصول على الخدمات من SMMKings API 
            try:
                # 💡 يجب أن تكون هذه الدالة موجودة في smmkings_api.py وتُرجع قائمة بالخدمات
                smm_services = smmkings_client.get_services() 
                
                # تخزين الخدمات التي سيتم عرضها فقط (بناءً على افتراض أن API SMMKings يرجع قائمة)
                sh_services_for_db = {}
                
                for service in smm_services:
                    # افتراضياً: الـ ID هو service['id']، والاسم هو service['name']، والسعر هو service['rate']
                    if service.get('available') and service.get('rate') is not None:
                        service_id = str(service['id'])
                        service_name = service['name']
                        service_price = float(service['rate'])
                        
                        sh_services_for_db[service_id] = {
                            'name': service_name, 
                            'price': service_price, # سعر الوحدة (قد يكون سعر 1000 أو 1)
                            'min_quantity': service.get('min', 100),
                            'max_quantity': service.get('max', 500000)
                        }
                        # نستخدم ID الخدمة مباشرة في الكولباك
                        markup.add(types.InlineKeyboardButton(f"⭐ {service_name} ({service_price:.2f} ₽)", callback_data=f'buy_sh_{service_id}')) 
                
                # حفظ قائمة الخدمات المتاحة
                data_file['sh_services'] = sh_services_for_db
                save_bot_data(data_file)
                
            except Exception as e:
                logging.error(f"Failed to fetch SMMKings services: {e}")
                data_file['sh_services'] = {}
                markup.add(types.InlineKeyboardButton("❌ لا توجد خدمات متاحة حاليًا (خطأ API)", callback_data='sh'))

            sh_services = data_file.get('sh_services', {})
            
            if not sh_services:
                bot.send_message(chat_id, "❌ لا توجد خدمات رشق متاحة حاليًا.")
                return
            
            markup.add(types.InlineKeyboardButton('- رجوع.', callback_data='back'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="🚀 اختر خدمة الرشق:", reply_markup=markup)
            return

        # 💡 [التعديل الرئيسي هنا] - معالج شراء خدمات الرشق SMMKings
        elif data.startswith('buy_sh_'):
            service_id = data.split('_')[-1]
            service_info = None
            
            sh_services = data_file.get('sh_services', {})
            service_info = sh_services.get(service_id)

            if not service_info:
                bot.send_message(chat_id, "❌ الخدمة غير متاحة حالياً.")
                return
                
            # نستخدم الحد الأدنى والحد الأقصى للتوجيه
            price_unit = service_info.get('price', 0)
            min_q = service_info.get('min_quantity', 100)
            max_q = service_info.get('max_quantity', 500000)
            service_name = service_info['name']
            
            # **هنا يجب أن نجعل التحقق من الرصيد مرناً بناءً على الحد الأدنى للكمية**
            # (نحتاج إلى سعر تقريبي أو سعر الوحدة للتحقق الأولي)
            # بما أننا لا نعرف سعر الوحدة (1 أو 1000)، سنفترض أن المستخدم يحتاج الحد الأدنى
            # وسنعتمد على أن السعر المخزن هو سعر الوحدة.
            # *التحقق الأولي من الرصيد (مؤقت):*
            
            # 💡 سنترك التحقق الفعلي للرصيد عند إدخال المستخدم للكمية لحساب التكلفة الدقيقة.
            # *التحقق الأولي: يجب أن يكون الرصيد كافياً لشراء وحدة واحدة على الأقل*
            
            if user_balance < price_unit * 1: # التحقق من رصيد الوحدة
                bot.send_message(chat_id, f"❌ *عذرًا، رصيدك غير كافٍ للبدء بهذه الخدمة.*\n\n*الرصيد المطلوب تقريبًا:* {price_unit:.2f} روبل.\n*رصيدك الحالي:* {user_balance} روبل.\n\n*يمكنك شحن رصيدك عبر زر شحن الرصيد.*", parse_mode='Markdown')
                return

            # 🛑 [خطوة جديدة] - طلب الرابط والكمية
            # سنطلب من المستخدم إرسال رسالة تحتوي على الرابط والكمية مفصولة بمسافة
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, 
                                  text=f"✅ *أنت على وشك شراء خدمة الرشق: {service_name}*\n\n"
                                       f"**الحد الأدنى للكمية:** `{min_q}`\n"
                                       f"**الحد الأقصى للكمية:** `{max_q}`\n"
                                       f"**سعر الوحدة:** `{price_unit:.2f}` روبل\n\n"
                                       f"يرجى إرسال رسالة تحتوي على *رابط* الهدف و *الكمية* المطلوبة مفصولين بمسافة واحدة.\n\n"
                                       f"*مثال:* `https://instagram.com/user 1000`", 
                                  parse_mode='Markdown',
                                  reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton('❌ إلغاء', callback_data='sh')))

            # حفظ حالة انتظار الإدخال (Link and Quantity) في قاعدة البيانات
            data_file['awaiting_sh_order'] = {
                'user_id': user_id, 
                'service_id': service_id, 
                'service_name': service_name,
                'price': price_unit, # سعر الوحدة (Unit Price)
                'min_q': min_q,
                'max_q': max_q
            }
            save_bot_data(data_file)
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
                    service_display = p.get('phone_number', p.get('app_name', p.get('service_name', 'غير متوفر'))) 
                    price = p.get('price', 0)
                    timestamp = p.get('timestamp', 'غير متوفر')
                    status = p.get('status', 'غير معروف')
                    
                    # تعديل عرض سجل الرشق
                    if p.get('status') == 'sh_purchased':
                        order_id = p.get('request_id', 'N/A')
                        link = p.get('link', 'N/A')
                        quantity = p.get('quantity', 'N/A')
                        message_text += f"*{i+1}. شراء خدمة رشق {service_display} ({quantity}) بسعر {price} روبل (طلب #{order_id}) في {timestamp}*\n"
                    else:
                        message_text += f"*{i+1}. شراء {service_display} بسعر {price} روبل ({status}) في {timestamp}*\n"
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
                # افتراضياً: 'request_smsman_number' هي دالة في الـ API
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
                markup.row(types.InlineKeyboardButton('♻️ - تحديث (جلب الكود)', callback_data=f'Code_{service}_{request_id}'))
                markup.row(types.InlineKeyboardButton('❌ إلغاء الطلب', callback_data=f'cancel_{service}_{request_id}'))
                markup.row(types.InlineKeyboardButton('🔄 - تغيير رقم آخر.', callback_data=f'ChangeNumber_{service}_{app_id}_{country_code}'))

                app_name = country_info.get('app_name', 'غير معروف')
                country_name = country_info.get('name', 'غير معروف')
                country_flag = country_info.get('flag', '') # افتراض أن العلم موجود في country_info

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
                    f"**🎦 - الموقع:** `soper.com`\n\n"
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
                        'country_name': country_name, # حفظ اسم الدولة
                        'country_flag': country_flag   # حفظ العلم
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
            if service_name == 'viotp':
                result = viotp_client.get_otp(request_id)
            elif service_name == 'smsman':
                # يتم استخدام دالة get_smsman_code المعدلة (المفترض تعديلها في smsman_api.py)
                result = smsman_api['get_smsman_code'](request_id) 
            elif service_name == 'tigersms':
                result = tiger_sms_client.get_code(request_id)

            otp_code = result.get('code') if result and result.get('status') == 'success' and result.get('code') else None
            
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
                    elif service_name == 'viotp':
                        viotp_client.set_status(request_id, 6)
                    elif service_name == 'tigersms':
                        tiger_sms_client.set_status(request_id, 'STATUS_SUCCESS') 
                        
                except Exception as e:
                    logging.error(f"Failed to set status to USED for {service_name} Req ID {request_id}: {e}")
                
                
                # ج. تعديل الرسالة الأصلية لوضع علامة (مكتمل) وإزالة الأزرار
                try:
                    new_text = call.message.text.replace("••• Pending", "✅ Completed")
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
                    save_bot_data({'active_requests': active_requests})
                
                # 💡 هـ. إرسال المنشور الترويجي إلى القناة (الإضافة المطلوبة)
                try:
                    # يجب أن تكون المتغيرات التالية مُخزّنة في active_request_info
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
                    # 💡 معالجة حالة الخطأ (مثل STATUS_CANCELLED من SmsMan API)
                    error_message = result.get('message', 'خطأ غير معروف')
                    
                    if error_message == 'STATUS_CANCELLED':
                        bot.send_message(chat_id, "❌ **فشل جلب الكود:** الرقم غير صالح أو تم إلغاؤه تلقائياً من الموقع. يرجى إلغاء الطلب (إذا كان مؤهلاً لاسترداد الرصيد) والمحاولة برقم جديد.", parse_mode='Markdown')
                        return # نوقف التنفيذ هنا ولا نغير حالة API

                # الإضافة الرئيسية لحل مشكلة التحديث اليدوي: إخبار API بالاستمرار في الانتظار
                try:
                    if service_name == 'viotp':
                        viotp_client.set_status(request_id, 3) 
                    elif service_name == 'smsman':
                        smsman_api['set_smsman_status'](request_id, 3) 
                    elif service_name == 'tigersms':
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
            service, request_id_raw = parts[1], parts[2]
            
            bot.answer_callback_query(call.id, "جاري معالجة طلب الإلغاء...")
            
            result = None
            success_api_call = False 
            
            # 1. محاولة الإلغاء في API الموقع
            if service == 'viotp':
                result = viotp_client.cancel_request(request_id_raw)
                if result and result.get('success'):
                    success_api_call = True
            
            elif service == 'smsman':
                # افتراضياً: 'cancel_smsman_request' هي دالة في الـ API
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
