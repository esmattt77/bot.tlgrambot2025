from telebot import types
import json
import time
import logging
import telebot.apihelper

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

    @bot.message_handler(func=lambda message: message.from_user.id != DEVELOPER_ID)
    def handle_user_messages(message):
        chat_id = message.chat.id
        user_id = message.from_user.id
        first_name = message.from_user.first_name
        username = message.from_user.username
        
        # 💡 تسجيل/تحديث بيانات المستخدم في MongoDB
        register_user(user_id, first_name, username)

        if message.text in ['/start', 'start/', 'بدء/']:
            show_main_menu(chat_id)
            return

        elif message.text in ['/balance', 'رصيدي']:
            # 💡 جلب معلومات المستخدم من MongoDB
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
        
        text = f"☑️ *⁞ قناة البوت الرسمية: @{EESSMT}\n🎬︙قم بالتحكم بالبوت الأن عبر الضعط على الأزرار.*"
        
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
        
        # 💡 التحميل من MongoDB
        data_file = get_bot_data()
        user_doc = get_user_doc(user_id)
        user_balance = user_doc.get('balance', 0) if user_doc else 0
        
        if data == 'back':
            show_main_menu(chat_id, message_id)
            return
        
        elif data == 'Payment':
            bot.send_message(chat_id, f"💰 *لشحن رصيدك، يرجى التواصل مع المشرف عبر هذا الحساب: @{ESM7AT}.*", parse_mode='Markdown')
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

            # 💡 خصم الرصيد من MongoDB مباشرة
            update_user_balance(user_id, -service_price, is_increment=True)
            
            # 💡 تحديث سجل المشتريات
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

            # 💡 يجب إعادة جلب الرصيد المتبقي
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

        elif data == 'ready':
            ready_numbers = data_file.get('ready_numbers', [])
            if not ready_numbers:
                bot.send_message(chat_id, "❌ لا توجد أرقام جاهزة متاحة حالياً.")
                return

            markup = types.InlineKeyboardMarkup()
            for i, num_data in enumerate(ready_numbers):
                markup.row(types.InlineKeyboardButton(f"{num_data.get('app', 'غير معروف')} - {num_data.get('price', 'غير معروف')} روبل", callback_data=f"buy_ready_{i}"))
            markup.row(types.InlineKeyboardButton('- رجوع.', callback_data='back'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="🔰 *الأرقام الجاهزة المتاحة حالياً:*", parse_mode='Markdown', reply_markup=markup)

        elif data.startswith('buy_ready_'):
            index_to_buy = int(data.split('_')[-1])
            ready_numbers = data_file.get('ready_numbers', [])

            if 0 <= index_to_buy < len(ready_numbers):
                number_data = ready_numbers[index_to_buy]
                price = number_data.get('price', 0)

                if user_balance < price:
                    bot.send_message(chat_id, f"❌ *عذرًا، رصيدك غير كافٍ لإتمام هذه العملية.*\n\n*الرصيد المطلوب:* {price} روبل.\n*رصيدك الحالي:* {user_balance} روبل.\n\n*يمكنك شحن رصيدك عبر زر شحن الرصيد.*", parse_mode='Markdown')
                    return
                
                # 💡 خصم الرصيد من MongoDB مباشرة
                update_user_balance(user_id, -price, is_increment=True)

                # 💡 تحديث سجل المشتريات
                register_user(
                    user_id,
                    user_doc.get('first_name'), 
                    user_doc.get('username'), 
                    new_purchase={
                        'phone_number': number_data.get('number'),
                        'app': number_data.get('app'),
                        'price': price,
                        'status': 'ready_number_purchased',
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
                    }
                )

                # حذف الرقم من قائمة الأرقام الجاهزة في بيانات البوت
                del ready_numbers[index_to_buy]
                data_file['ready_numbers'] = ready_numbers
                # 💡 حفظ بيانات البوت في MongoDB
                save_bot_data(data_file)
                
                # 💡 إعادة جلب الرصيد المتبقي
                new_user_doc = get_user_doc(user_id)
                remaining_balance = new_user_doc.get('balance', 0)
                
                bot.send_message(chat_id, f"✅ تم شراء الرقم `{number_data.get('number')}` بنجاح.\n\nالرصيد المتبقي: `{remaining_balance}` روبل.")
                
                # إرسال إشعار للمشرف
                bot.send_message(DEVELOPER_ID, f"🔔 *تم بيع رقم جاهز!*\n\n*الرقم:* `{number_data.get('number')}`\n*التطبيق:* `{number_data.get('app')}`\n*السعر:* `{price}` روبل\n*للمستخدم:* `@{user_doc.get('username', 'غير متوفر')}`", parse_mode='Markdown')
            else:
                bot.send_message(chat_id, "❌ حدث خطأ. الرقم المحدد غير متوفر.")

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
            # 💡 نستخدم الحقل 'purchases' من مستند MongoDB للمستخدم
            purchases = user_info.get('purchases', [])
            
            message_text = f"💰 رصيدك الحالي هو: *{balance}* روبل.\n\n"
            if purchases:
                message_text += "📝 **سجل مشترياتك الأخيرة:**\n"
                # نعرض آخر 5 مشتريات
                for i, p in enumerate(purchases[-5:]):
                    phone_number = p.get('phone_number', p.get('service_name', 'غير متوفر')) # عرض الرقم أو اسم الخدمة
                    price = p.get('price', 0)
                    timestamp = p.get('timestamp', 'غير متوفر')
                    # تم تعديل النص ليناسب سجل الشراء العام (أرقام + رشق)
                    message_text += f"*{i+1}. شراء {phone_number} بسعر {price} روبل في {timestamp}*\n"
            else:
                message_text += "❌ لا يوجد سجل مشتريات حتى الآن."
            
            bot.send_message(chat_id, message_text, parse_mode='Markdown')
            
        elif data.startswith('service_'):
            service = data.split('_')[1]
            markup = types.InlineKeyboardMarkup()
            # ... (باقي أزرار التطبيقات كما هي)
            if service == 'viotp':
                markup.row(types.InlineKeyboardButton('⁞ واتسأب 💬', callback_data=f'show_countries_{service}_2'))
                markup.row(types.InlineKeyboardButton('⁞ تيليجرام 📢', callback_data=f'show_countries_{service}_3'))
                markup.row(types.InlineKeyboardButton('⁞ فيسبوك 🏆', callback_data=f'show_countries_{service}_4'))
                markup.row(types.InlineKeyboardButton('⁞ إنستقرام 🎥', callback_data=f'show_countries_{service}_5'))
                markup.row(types.InlineKeyboardButton('⁞ تويتر 🚀', callback_data=f'show_countries_{service}_6'))
                markup.row(types.InlineKeyboardButton('⁞ تيكتوك 🎬', callback_data=f"show_countries_{service}_7"))
                markup.row(types.InlineKeyboardButton('⁞ قوقل 🌐', callback_data=f'show_countries_{service}_8'))
                markup.row(types.InlineKeyboardButton('⁞ إيمو 🐦', callback_data=f'show_countries_{service}_9'))
                markup.row(types.InlineKeyboardButton('⁞ سناب 🐬', callback_data=f'show_countries_{service}_11'))
                markup.row(types.InlineKeyboardButton('⁞ OK 🌟', callback_data=f'show_countries_{service}_12'))
                markup.row(types.InlineKeyboardButton('⁞ Viber 📲', callback_data=f'show_countries_{service}_16'))
                markup.row(types.InlineKeyboardButton('⁞ حراج 🛍', callback_data=f'show_countries_{service}_13'))
                markup.row(types.InlineKeyboardButton('⁞ السيرفر العام ☑️', callback_data=f'show_countries_{service}_14'))
            elif service == 'smsman':
                markup.row(types.InlineKeyboardButton('⁞ واتسأب 💬', callback_data=f'show_countries_{service}_2'))
                markup.row(types.InlineKeyboardButton('⁞ تيليجرام 📢', callback_data=f'show_countries_{service}_3'))
                markup.row(types.InlineKeyboardButton('⁞ فيسبوك 🏆', callback_data=f'show_countries_{service}_4'))
                markup.row(types.InlineKeyboardButton('⁞ إنستقرام 🎥', callback_data=f'show_countries_{service}_5'))
                markup.row(types.InlineKeyboardButton('⁞ تويتر 🚀', callback_data=f'show_countries_{service}_6'))
                markup.row(types.InlineKeyboardButton('⁞ تيكتوك 🎬', callback_data=f"show_countries_{service}_7"))
                markup.row(types.InlineKeyboardButton('⁞ قوقل 🌐', callback_data=f'show_countries_{service}_8'))
                markup.row(types.InlineKeyboardButton('⁞ إيمو 🐦', callback_data=f'show_countries_{service}_9'))
                markup.row(types.InlineKeyboardButton('⁞ سناب 🐬', callback_data=f'show_countries_{service}_11'))
                markup.row(types.InlineKeyboardButton('⁞ OK 🌟', callback_data=f'show_countries_{service}_12'))
                markup.row(types.InlineKeyboardButton('⁞ Viber 📲', callback_data=f'show_countries_{service}_16'))
                markup.row(types.InlineKeyboardButton('⁞ حراج 🛍', callback_data=f'show_countries_{service}_13'))
                markup.row(types.InlineKeyboardButton('⁞ السيرفر العام ☑️', callback_data=f'show_countries_{service}_14'))
            elif service == 'tigersms':
                markup.row(types.InlineKeyboardButton('⁞ واتسأب 💬', callback_data=f'show_countries_{service}_wa'))
                markup.row(types.InlineKeyboardButton('⁞ تيليجرام 📢', callback_data=f'show_countries_{service}_tg'))
                markup.row(types.InlineKeyboardButton('⁞ فيسبوك 🏆', callback_data=f'show_countries_{service}_fb'))
                markup.row(types.InlineKeyboardButton('⁞ إنستقرام 🎥', callback_data=f'show_countries_{service}_ig'))
                markup.row(types.InlineKeyboardButton('⁞ تويتر 🚀', callback_data=f'show_countries_{service}_tw'))
                markup.row(types.InlineKeyboardButton('⁞ تيكتوك 🎬', callback_data=f"show_countries_{service}_tt"))
                markup.row(types.InlineKeyboardButton('⁞ قوقل 🌐', callback_data=f'show_countries_{service}_go'))
                markup.row(types.InlineKeyboardButton('⁞ سناب 🐬', callback_data=f'show_countries_{service}_sn'))
                markup.row(types.InlineKeyboardButton('⁞ ديسكورد 🎮', callback_data=f'show_countries_{service}_ds'))
                markup.row(types.InlineKeyboardButton('⁞ تيندر ❤️', callback_data=f'show_countries_{service}_td'))
                markup.row(types.InlineKeyboardButton('⁞ أوبر 🚕', callback_data=f'show_countries_{service}_ub'))
                markup.row(types.InlineKeyboardButton('⁞ أوكي 🌟', callback_data=f'show_countries_{service}_ok'))
                markup.row(types.InlineKeyboardButton('⁞ لاين 📲', callback_data=f'show_countries_{service}_li'))
                markup.row(types.InlineKeyboardButton('⁞ أمازون 🛒', callback_data=f'show_countries_{service}_am'))

            markup.row(types.InlineKeyboardButton('- رجوع.', callback_data='Buynum'))
            server_name = 'سيرفر 1' if service == 'viotp' else ('سيرفر 2' if service == 'smsman' else 'سيرفر 3')
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"☑️ *اختر التطبيق* الذي تريد *شراء رقم وهمي* له من خدمة **{server_name}**.", parse_mode='Markdown', reply_markup=markup)

        elif data.startswith('show_countries_'):
            parts = data.split('_')
            service, app_id = parts[2], parts[3]
            page = int(parts[5]) if len(parts) > 5 else 1
            
            # 💡 جلب الدول من بيانات البوت المحفوظة في MongoDB
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
            
            # 💡 [الخطوة 1] الرد الفوري على ضغطة الزر لتجنب المهلة
            bot.answer_callback_query(call.id, "✅ جاري معالجة طلب الرقم...")

            # جلب البيانات من MongoDB
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
                
                # -----------------------------------------------------------
                # 💡 [الخطوة 2: إرسال رسالة الرد أولاً]
                # -----------------------------------------------------------
                
                # حساب الرصيد المتبقي (قبل التحديث الفعلي في DB)
                remaining_balance = user_balance - price
                
                markup = types.InlineKeyboardMarkup()
                markup.row(types.InlineKeyboardButton('✅ الحصول على الكود', callback_data=f'get_otp_{service}_{request_id}'))
                markup.row(types.InlineKeyboardButton('❌ إلغاء الطلب', callback_data=f'cancel_{service}_{request_id}'))

                service_name = 'سيرفر 1' if service == 'viotp' else ('سيرفر 2' if service == 'smsman' else 'سيرفر 3')
                app_name = country_info.get('name', 'غير معروف')
                country_name = country_info.get('name', 'غير معروف')
                
                message_text = (
                    f"**☎️ - الرقم:** `{phone_number}`\n"
                    f"**🧿 - التطبيق:** `{app_name}`\n"
                    f"**📥 - الدولة:** `{country_name}`\n"
                    f"**🔥 - الأيدي:** `{user_id}`\n"
                    f"**💸 - السعر:** `Ꝑ{price}`\n"
                    f"**🤖 - الرصيد المتبقي:** `{remaining_balance}`\n" # استخدام الرصيد المحسوب
                    f"**🔄 - معرف المشتري:** `@{user_doc.get('username', 'غير متوفر')}`\n"
                    f"**🎦 - الموقع:** `soper.com`"
                )

                # 💡 إرسال الرسالة والتقاط معرفها الصحيح
                sent_message = bot.send_message(chat_id, message_text, parse_mode='Markdown', reply_markup=markup)
                new_message_id = sent_message.message_id
                
                # -----------------------------------------------------------
                # 💡 [الخطوة 3: حفظ البيانات في MongoDB الآن]
                # -----------------------------------------------------------
                
                # 1. خصم الرصيد
                update_user_balance(user_id, -price, is_increment=True)
                
                # 2. تحديث سجل المشتريات
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
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
                    }
                )
                
                # 3. حفظ الطلب النشط وتفاصيل الرسالة الجديدة
                data_file = get_bot_data()
                active_requests = data_file.get('active_requests', {})
                active_requests[request_id] = {
                    'user_id': user_id,
                    'phone_number': phone_number,
                    'status': 'pending',
                    'service': service,
                    'price': price,
                    'message_id': new_message_id # 💡 [تصحيح] استخدام الـ ID الصحيح
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
                
                if request_id in active_requests:
                    phone_number = active_requests[request_id]['phone_number']
                    del active_requests[request_id]
                    data_file['active_requests'] = active_requests
                    # 💡 حفظ بيانات البوت في MongoDB
                    save_bot_data(data_file)

                    # 💡 تحديث حالة الطلب في سجل المشتريات إلى "completed"
                    register_user(
                        user_id, 
                        user_doc.get('first_name'), 
                        user_doc.get('username'),
                        update_purchase_status={
                            'request_id': request_id, 
                            'status': 'completed'
                        }
                    )

                    bot.send_message(chat_id, f"✅ *رمزك هو: {otp_code}*\n\nالرقم: *{phone_number}*", parse_mode='Markdown')
                else:
                    bot.send_message(chat_id, "❌ حدث خطأ، لم يتم العثور على الطلب.")
            else:
                bot.send_message(chat_id, "❌ لا يوجد كود حتى الآن. حاول مجدداً.", reply_markup=call.message.reply_markup)
                
        elif data.startswith('cancel_'):
            parts = data.split('_')
            service, request_id = parts[1], parts[2]
            
            # 💡 [تعديل] الرد الفوري على ضغطة الزر
            bot.answer_callback_query(call.id, "جاري معالجة طلب الإلغاء...")
            
            result = None
            if service == 'viotp':
                result = viotp_client.cancel_request(request_id)
            elif service == 'smsman':
                result = smsman_api['cancel_smsman_request'](request_id)
                # 💡 توحيد استجابة smsman (التأكد من أن حالة 'success' موجودة)
                if result and result.get('status') == 'success':
                    result['success'] = True
            elif service == 'tigersms':
                result = tiger_sms_client.cancel_request(request_id)
            
            # 💡 التحقق من نجاح عملية الإلغاء في API الموقع
            if result and result.get('success'):
                data_file = get_bot_data()
                active_requests = data_file.get('active_requests', {})
                
                if request_id in active_requests:
                    try:
                        # 💡 [تحسين] استخدام try/except لتأمين عمليات MongoDB
                        request_info = active_requests[request_id]
                        user_id_from_request = request_info['user_id']
                        price_to_restore = request_info['price']
                        
                        # 1. استرجاع الرصيد للمستخدم مباشرة
                        update_user_balance(user_id_from_request, price_to_restore, is_increment=True)
                        
                        # 2. حذف سجل الطلب من قائمة المشتريات (أو تحديث حالته إلى 'cancelled')
                        register_user(
                            user_id_from_request, 
                            user_doc.get('first_name'), 
                            user_doc.get('username'),
                            delete_purchase_id=request_id
                        )
                        
                        # 3. حذف الطلب من الطلبات النشطة
                        del active_requests[request_id]
                        data_file['active_requests'] = active_requests
                        save_bot_data(data_file)
                        
                        # 4. إرسال رسالة النجاح
                        bot.send_message(chat_id, f"✅ **تم إلغاء الطلب بنجاح!** تم استرجاع مبلغ *{price_to_restore}* روبل إلى رصيدك.", parse_mode='Markdown')
                        
                    except Exception as e:
                        # 💡 في حال فشل أي عملية MongoDB، نسجل الخطأ ونبلغ المستخدم
                        logging.error(f"MongoDB Error during CANCEL/REFUND for Req ID {request_id}: {e}")
                        bot.send_message(chat_id, f"⚠️ تم إلغاء طلبك في الموقع، ولكن حدث **خطأ أثناء استرجاع رصيدك**. يرجى التواصل مع الدعم (@{ESM7AT}) وذكر آيدي الطلب: `{request_id}`.", parse_mode='Markdown')
                        
                else:
                    # هذه الحالة تحدث إذا تم حذف الطلب من active_requests مسبقاً
                    bot.send_message(chat_id, "❌ حدث خطأ: لا يوجد طلب نشط بهذا الآيدي في البوت. يرجى مراجعة رصيدك وسجل مشترياتك.", parse_mode='Markdown')

            else:
                # هذا الرد في حالة فشل الاتصال/الإلغاء في API الموقع
                bot.send_message(chat_id, "❌ فشل إلغاء الطلب في الموقع. يرجى المحاولة مرة أخرى أو التواصل مع الدعم.")
