from telebot import types
import json
import time
import logging
import telebot.apihelper
import random # 🆕 لإضافة دالة توليد رقم عشوائي لمعرف المعاملة

# تهيئة نظام التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 💡 --- MongoDB IMPORTS ---
# يجب أن يكون ملف db_manager.py موجوداً في نفس المجلد
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

    # 💡 [التصحيح النهائي لنوع البيانات] دالة مساعدة مرنة للبحث عن الطلب في سجل المشتريات
    def get_cancellable_request_info(user_doc, request_id):
        purchases = user_doc.get('purchases', [])
        
        # تحويل request_id من الكولباك إلى سلسلة نصية لضمان التوافق في المقارنة
        request_id_str = str(request_id) 
        
        # البحث في جميع المشتريات بطرق متعددة للتأكد
        for p in purchases:
            # محاولات متعددة للمقارنة لتغطية جميع الاحتمالات
            request_id_matches = (
                str(p.get('request_id')) == request_id_str or  # الحالة الأساسية
                p.get('request_id') == request_id or           # في حال كان نفس النوع
                str(p.get('request_id')) == str(request_id)    # تأكيد إضافي
            )
            
            status_valid = p.get('status') not in ['completed', 'cancelled']
            
            if request_id_matches and status_valid:
                return {
                    'user_id': user_doc.get('_id'),
                    'price_to_restore': p.get('price', 0),
                    'purchase_record': p  # إرجاع السجل الكامل للتأكد
                }
        
        # إذا لم نجد في المشتريات الحديثة، نبحث في الطلبات النشطة
        data_file = get_bot_data()
        active_requests = data_file.get('active_requests', {})
        
        # البحث في الطلبات النشطة
        active_request = active_requests.get(request_id_str) or active_requests.get(str(request_id))
        
        if active_request and active_request.get('user_id') == user_doc.get('_id'):
            price = active_request.get('price', 0)
            # إنشاء سجل شراء افتراضي إذا لم يكن موجوداً
            if price > 0:
                return {
                    'user_id': user_doc.get('_id'),
                    'price_to_restore': price,
                    'from_active_requests': True  # للإشارة أننا استخرجنا من الطلبات النشطة
                }
        
        return None

    @bot.message_handler(func=lambda message: message.from_user.id != DEVELOPER_ID)
    def handle_user_messages(message):
        chat_id = message.chat.id
        user_id = message.from_user.id
        first_name = message.from_user.first_name
        username = message.from_user.username
        
        register_user(user_id, first_name, username)

        if message.text in ['/start', 'start/', 'بدء/']:
            show_main_menu(chat_id)
            return

        elif message.text in ['/balance', 'رصيدي']:
            user_doc = get_user_doc(user_id)
            balance = user_doc.get('balance', 0) if user_doc else 0
            bot.send_message(chat_id, f"💰 رصيدك الحالي هو: *{balance}* روبل.", parse_mode='Markdown')
    
    def show_main_menu(chat_id, message_id=None):
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton('☎️︙شراء ارقـام وهمية', callback_data='Buynum'))
        markup.row(types.InlineKeyboardButton('💰︙شحن رصيدك', callback_data='Payment'), types.InlineKeyboardButton('👤︙قسم الرشق', callback_data='sh'))
        markup.row(types.InlineKeyboardButton('🅿️︙كشف الحساب', callback_data='Record'), types.InlineKeyboardButton('🛍︙قسم العروض', callback_data='Wo'))
        markup.row(types.InlineKeyboardButton('☑️︙قسم العشوائي', callback_data='worldwide'), types.InlineKeyboardButton('👑︙قسم الملكي', callback_data='saavmotamy'))
        markup.row(types.InlineKeyboardButton('💰︙ربح روبل مجاني 🤑', callback_data='assignment'))
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


    @bot.callback_query_handler(func=lambda call: call.from_user.id != DEVELOPER_ID)
    def handle_user_callbacks(call):
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        message_id = call.message.message_id
        data = call.data
        
        data_file = get_bot_data()
        user_doc = get_user_doc(user_id)
        user_balance = user_doc.get('balance', 0) if user_doc else 0
        
        if data == 'back':
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
            bot.send_message(chat_id, "💰 *يمكنك ربح روبل مجانية عن طريق إكمال بعض المهام. تابع الإعلانات لمعرفة التفاصيل.*", parse_mode='Markdown')
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
                # هذه الرسالة لا يجب أن تظهر نظريًا لأننا تحققنا في الخطوة السابقة، لكنها طبقة أمان
                bot.send_message(chat_id, f"❌ *عذرًا، رصيدك غير كافٍ لإتمام هذه العملية. رصيدك الحالي: {user_balance}*", parse_mode='Markdown')
                return

            # 1. تنفيذ الخصم
            update_user_balance(user_id, -price, is_increment=True)
            
            # 2. إزالة الرقم من المخزون وحفظ التعديل
            data_file = get_bot_data()
            if number_key in data_file.get('ready_numbers_stock', {}):
                # 💡 يجب التأكد من استخدام save_bot_data بالشكل الصحيح
                # يتم حذف الرقم من نسخة الـ data_file ثم حفظ التحديث
                del data_file['ready_numbers_stock'][number_key] 
                save_bot_data({'ready_numbers_stock': data_file['ready_numbers_stock']})
            
            # 3. تسجيل عملية الشراء (استخدام رقم عشوائي كـ ID)
            # 💡 توليد رقم معاملة فريد
            idnums = random.randint(100000, 999999) 
            register_user(
                user_id,
                user_doc.get('first_name'), 
                user_doc.get('username'), 
                new_purchase={
                    'request_id': idnums, # استخدام idnums هنا
                    'phone_number': number_key,
                    'app': number_data.get('state', 'جاهز'),
                    'price': price,
                    'status': 'ready_number_purchased',
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
                }
            )

            # 4. تحديث الرصيد المتبقي
            new_user_doc = get_user_doc(user_id)
            remaining_balance = new_user_doc.get('balance', 0)

            # 5. إرسال رسالة الإيصال بالصيغة المطلوبة
            number = number_key
            code = number_data.get('code', 'غير متوفر (يرجى التواصل مع الدعم)')
            what = number_data.get('note', 'لا توجد ملاحظة')
            
            # استخدام الصيغة النصية المطلوبة
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
            
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message_text, parse_mode='Markdown')
            
            # إشعار للمطور
            bot.send_message(DEVELOPER_ID, 
                             f"🔔 *تم بيع رقم جاهز!*\n"
                             f"*الرقم:* `{number}`\n"
                             f"*السعر:* `{price}` روبل\n"
                             f"*للمستخدم:* `@{user_doc.get('username', 'غير متوفر')}`", 
                             parse_mode='Markdown')
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
                    phone_number = p.get('phone_number', p.get('service_name', 'غير متوفر')) 
                    price = p.get('price', 0)
                    timestamp = p.get('timestamp', 'غير متوفر')
                    status = p.get('status', 'غير معروف')
                    message_text += f"*{i+1}. شراء {phone_number} بسعر {price} روبل ({status}) في {timestamp}*\n"
            else:
                message_text += "❌ لا يوجد سجل مشتريات حتى الآن."
            
            bot.send_message(chat_id, message_text, parse_mode='Markdown')
            
        elif data.startswith('service_'):
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
            
            bot.answer_callback_query(call.id, "✅ جاري معالجة طلب الرقم...")

            country_info = data_file.get('countries', {}).get(service, {}).get(app_id, {}).get(country_code, {})
            price = country_info.get('price', 0)
            
            if user_balance < price:
                bot.send_message(chat_id, f"❌ *عذرًا، رصيدك غير كافٍ لإتمام هذه العملية.*\n\n*الرصيد المطلوب:* {price} روبل.\n*رصيدك الحالي:* {user_balance} روبل.\n\n*يمكنك شحن رصيدك عبر زر شحن الرصيد.*", parse_mode='Markdown')
                return

            result = None
            if service == 'viotp':
                result = viotp_client.buy_number(app_id)
            elif service == 'smsman':
                result = smsman_api['request_smsman_number'](app_id, country_code)
                if result and 'request_id' in result:
                    result['success'] = True
                    result['id'] = result['request_id']
                    result['number'] = result['Phone']
            elif service == 'tigersms':
                result = tiger_sms_client.get_number(app_id, country_code)

            logging.info(f"Response from {service}: {result}")

            if result and result.get('success'):
                request_id = result.get('id')
                phone_number = result.get('number', result.get('Phone', 'غير متوفر'))
                
                remaining_balance = user_balance - price
                
                markup = types.InlineKeyboardMarkup()
                markup.row(types.InlineKeyboardButton('✅ الحصول على الكود', callback_data=f'get_otp_{service}_{request_id}'))
                markup.row(types.InlineKeyboardButton('❌ إلغاء الطلب', callback_data=f'cancel_{service}_{request_id}'))

                app_name = country_info.get('name', 'غير معروف')
                country_name = country_info.get('name', 'غير معروف')
                
                message_text = (
                    f"**☎️ - الرقم:** `{phone_number}`\n"
                    f"**🧿 - التطبيق:** `{app_name}`\n"
                    f"**📥 - الدولة:** `{country_name}`\n"
                    f"**🔥 - الأيدي:** `{user_id}`\n"
                    f"**💸 - السعر:** `Ꝑ{price}`\n"
                    f"**🤖 - الرصيد المتبقي:** `{remaining_balance}`\n" 
                    f"**🔄 - معرف المشتري:** `@{user_doc.get('username', 'غير متوفر')}`\n"
                    f"**🎦 - الموقع:** `soper.com`\n\n"
                    f"⚠️ *ملاحظة هامة:* لا يمكنك إلغاء الرقم إلا بعد مرور دقيقتين (2) من وقت الحصول عليه."
                )

                sent_message = bot.send_message(chat_id, message_text, parse_mode='Markdown', reply_markup=markup)
                new_message_id = sent_message.message_id
                
                # 💡 [حفظ البيانات في MongoDB]
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
                
        elif data.startswith('get_otp_'):
            parts = data.split('_')
            service, request_id = parts[2], parts[3]
            
            result = None
            if service == 'viotp':
                result = viotp_client.get_otp(request_id)
            elif service == 'smsman':
                result = smsman_api['get_smsman_code'](request_id)
            elif service == 'tigersms':
                result = tiger_sms_client.get_code(request_id)

            if result and result.get('success') and result.get('code'):
                otp_code = result.get('code')
                data_file = get_bot_data()
                active_requests = data_file.get('active_requests', {})
                
                app_name = "غير معروف"
                # 💡 استخدام str(request_id) لضمان التوافق مع المفتاح في MongoDB
                if str(request_id) in active_requests: 
                    phone_number = active_requests[str(request_id)]['phone_number']
                    app_name = active_requests[str(request_id)].get('app_name', 'غير معروف')
                    
                    del active_requests[str(request_id)]
                    data_file['active_requests'] = active_requests
                    save_bot_data(data_file)

                    register_user(
                        user_id, 
                        user_doc.get('first_name'), 
                        user_doc.get('username'),
                        update_purchase_status={
                            'request_id': request_id, 
                            'status': 'completed'
                        }
                    )
                    
                    # 💡 [إضافة: إرسال المنشور الترويجي إلى القناة]
                    try:
                        promo_message = (
                            f"🎉 *تم شراء رقم جديد بنجاح!* 🎉\n\n"
                            f"**التطبيق:** `{app_name}`\n"
                            f"**الخدمة:** تم التفعيل بنجاح! ✅\n\n"
                            f"اشترِ رقمك الافتراضي الآن من @{EESSMT}"
                        )
                        bot.send_message(f'@{EESSMT}', promo_message, parse_mode='Markdown')
                        logging.info(f"Sent promo message to @{EESSMT} for Req ID {request_id}")
                    except Exception as e:
                        logging.error(f"Failed to send promo message to channel @{EESSMT}: {e}")
                    
                    bot.send_message(chat_id, f"✅ *رمزك هو: {otp_code}*\n\nالرقم: *{phone_number}*", parse_mode='Markdown')
                else:
                    bot.send_message(chat_id, "❌ حدث خطأ، لم يتم العثور على الطلب.")
            else:
                bot.send_message(chat_id, "❌ لا يوجد كود حتى الآن. حاول مجدداً.", reply_markup=call.message.reply_markup)
                
        elif data.startswith('cancel_'):
            parts = data.split('_')
            service, request_id = parts[1], parts[2]
            
            bot.answer_callback_query(call.id, "جاري معالجة طلب الإلغاء...")
            
            result = None
            success_api_call = False 
            
            # 1. محاولة الإلغاء في API الموقع
            if service == 'viotp':
                result = viotp_client.cancel_request(request_id)
                if result and result.get('success'):
                    success_api_call = True
            
            elif service == 'smsman':
                result = smsman_api['cancel_smsman_request'](request_id)
                if result and (result.get('message') == 'ACCESS_CANCEL' or result.get('status') == 'success' or result.get('status') == 'cancelled'):
                    success_api_call = True
            
            elif service == 'tigersms':
                result = tiger_sms_client.cancel_request(request_id)
                if result and result.get('success'):
                    success_api_call = True
            
            logging.info(f"Response from {service} for CANCEL Req ID {request_id}: {result}")
            
            # 2. إذا نجح الإلغاء في API، ننتقل لمعالجة الرصيد
            if success_api_call:
                
                # 💡 [استخدام الدالة المحسنة للبحث عن الطلب]
                request_info = get_cancellable_request_info(user_doc, request_id)
                
                if request_info:
                    try:
                        price_to_restore = request_info.get('price_to_restore', 0)
                        
                        if price_to_restore == 0:
                            # إذا كان السعر صفر، نحاول الحصول على السعر من بيانات الخدمة
                            country_info = data_file.get('countries', {}).get(service, {}).get(app_id, {}).get(country_code, {})
                            price_to_restore = country_info.get('price', 0)
                            
                        if price_to_restore == 0:
                            raise ValueError("Price to restore is zero, refund aborted.")

                        # أ. استرجاع الرصيد للمستخدم
                        update_user_balance(user_id, price_to_restore, is_increment=True)
                        
                        # ب. تحديث حالة الطلب في سجل المشتريات إلى "cancelled"
                        register_user(
                            user_id, 
                            user_doc.get('first_name'), 
                            user_doc.get('username'),
                            update_purchase_status={
                                'request_id': request_id, 
                                'status': 'cancelled'
                            }
                        )
                        
                        # ج. إزالة الطلب من الطلبات النشطة (إذا كان موجوداً)
                        data_file = get_bot_data()
                        active_requests = data_file.get('active_requests', {})
                        
                        # البحث بجميع الأشكال الممكنة للمفتاح
                        keys_to_remove = []
                        for key in active_requests.keys():
                            if key == str(request_id) or key == request_id or str(key) == str(request_id):
                                keys_to_remove.append(key)
                        
                        for key in keys_to_remove:
                            del active_requests[key]
                        
                        data_file['active_requests'] = active_requests
                        save_bot_data(data_file)
                        
                        # د. إرسال رسالة النجاح
                        new_balance = user_balance + price_to_restore
                        bot.send_message(chat_id, f"✅ **تم إلغاء الطلب بنجاح!**\n\nتم استرجاع مبلغ *{price_to_restore}* روبل إلى رصيدك.\n*الرصيد الحالي:* {new_balance} روبل", parse_mode='Markdown')
                        
                    except Exception as e:
                        logging.error(f"MongoDB/Refund Error during CANCEL for Req ID {request_id}: {e}")
                        bot.send_message(chat_id, f"⚠️ تم إلغاء طلبك في الموقع، ولكن حدث **خطأ أثناء استرجاع رصيدك**. يرجى التواصل مع الدعم (@{ESM7AT}) وذكر آيدي الطلب: `{request_id}`.", parse_mode='Markdown')
                        
                else:
                    # في هذه الحالة، فشلت الدالة في العثور على الطلب في السجل.
                    logging.warning(f"Could not find purchase record for cancellation. User: {user_id}, Req ID: {request_id}")
                    bot.send_message(chat_id, f"⚠️ تم إلغاء طلبك في الموقع بنجاح، لكنه **غير مسجل كطلب معلق في سجل مشترياتك**. لم يتم إرجاع الرصيد تلقائياً. يرجى التواصل فوراً مع الدعم (@{ESM7AT}) وتقديم آيدي الطلب: `{request_id}`.", parse_mode='Markdown')

            else:
                # هذا الرد في حالة فشل الإلغاء في API الموقع
                bot.send_message(chat_id, "❌ فشل إلغاء الطلب في الموقع. يرجى المحاولة مرة أخرى أو التواصل مع الدعم.")
