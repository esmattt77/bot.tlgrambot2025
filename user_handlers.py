from telebot import types
import json
import time
from telebot.apihelper import ApiTelegramException

# --- المتغيرات الخاصة بالقناة والمجموعة (قم بتحديثها) ---
CHANNEL_USERNAME = "EESSMT"  
GROUP_USERNAME = "wwesmaat"      
GROUP_ID = -1002691575929             

# --- Helper Functions (Shared) ---
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

def register_user(user_id, first_name, username):
    users_data = load_users()
    if str(user_id) not in users_data:
        users_data[str(user_id)] = {
            'id': user_id,
            'first_name': first_name,
            'username': username,
            'balance': 0,
            'join_date': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
            'has_received_bonus': False,
            'has_referrer': False  
        }
        save_users(users_data)

def get_main_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton('☎️︙شراء ارقـام وهمية', callback_data='Buynum'))
    markup.row(types.InlineKeyboardButton('💰︙شحن رصيدك', callback_data='Payment'), types.InlineKeyboardButton('👤︙قسم الرشق', callback_data='sh'))
    markup.row(types.InlineKeyboardButton('🅿️︙كشف الحساب', callback_data='Record'), types.InlineKeyboardButton('🛍︙قسم العروض', callback_data='Wo'))
    markup.row(types.InlineKeyboardButton('☑️︙قسم العشوائي', callback_data='worldwide'), types.InlineKeyboardButton('👑︙قسم الملكي', callback_data='saavmotamy'))
    markup.row(types.InlineKeyboardButton('💰︙ربح روبل مجاني 🤑', callback_data='assignment'))
    markup.row(types.InlineKeyboardButton('💳︙متجر الكروت', callback_data='readycard-10'), types.InlineKeyboardButton('🔰︙الارقام الجاهزة', callback_data='ready'))
    markup.row(types.InlineKeyboardButton('👨‍💻︙قسم الوكلاء', callback_data='gents'), types.inlinekeyboardbutton('⚙️︙إعدادات البوت', callback_data='MyAccount'))
    markup.row(types.InlineKeyboardButton('📮︙تواصل الدعم أونلاين', callback_data='super'))
    return markup


def setup_user_handlers(bot, DEVELOPER_ID, ESM7AT, EESSMT, viotp_client, smsman_api, tiger_sms_client):
    
    @bot.message_handler(func=lambda message: message.from_user.id != DEVELOPER_ID)
    def handle_user_messages(message):
        chat_id = message.chat.id
        user_id = message.from_user.id
        first_name = message.from_user.first_name
        username = message.from_user.username
        
        users_data = load_users()
        register_user(user_id, first_name, username)
        user_info = users_data.get(str(user_id))
        
        if message.text.startswith('/start'):
            start_parameter = message.text.split(' ')[1] if len(message.text.split(' ')) > 1 else None
            
            if start_parameter and str(user_id) not in users_data:
                referrer_id = start_parameter
                if referrer_id != str(user_id):
                    referrer_data = users_data.get(referrer_id)
                    if referrer_data:
                        referrer_data['balance'] += 1
                        users_data[str(user_id)]['has_referrer'] = True
                        save_users(users_data)
                        
                        bot.send_message(chat_id, f"🎉 لقد انضممت عبر رابط إحالة! تم إضافة 1 روبل إلى رصيد {referrer_data.get('first_name', 'صديقك')}.")
                        try:
                            bot.send_message(referrer_id, f"✅ تهانينا! لقد انضم مستخدم جديد من خلال رابطك. تم إضافة 1 روبل إلى رصيدك.", parse_mode='Markdown')
                        except Exception as e:
                            print(f"Failed to notify referrer: {e}")

            has_joined_channel = False
            has_joined_group = False
            
            try:
                channel_member = bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
                if channel_member.status in ['member', 'creator', 'administrator']:
                    has_joined_channel = True
                
                group_member = bot.get_chat_member(f"@{GROUP_USERNAME}", user_id)
                if group_member.status in ['member', 'creator', 'administrator']:
                    has_joined_group = True
            except Exception as e:
                print(f"Error checking membership: {e}")

            if has_joined_channel and not user_info.get('has_received_bonus', False):
                users_data[str(user_id)]['balance'] += 0.25
                users_data[str(user_id)]['has_received_bonus'] = True
                save_users(users_data)
                bot.send_message(chat_id, "🎉 تهانينا! لقد حصلت على مكافأة 0.25 روبل لاشتراكك في القناة.")

            if has_joined_channel and has_joined_group:
                bot.send_message(chat_id, f"☑️ *⁞ قناة البوت الرسمية: @{EESSMT}\n🎬︙قم بالتحكم بالبوت الأن عبر الضعط على الأزرار.*", parse_mode='Markdown', reply_markup=get_main_keyboard())
            else:
                markup = types.InlineKeyboardMarkup()
                if not has_joined_channel:
                    markup.add(types.InlineKeyboardButton('📢 اشترك في القناة الرسمية', url=f'https://t.me/{CHANNEL_USERNAME}'))
                if not has_joined_group:
                    markup.add(types.InlineKeyboardButton('👥 انضم إلى المجموعة', url=f'https://t.me/{GROUP_USERNAME}'))
                
                markup.add(types.InlineKeyboardButton('✅ تحقق من اشتراكي', callback_data='check_subscription'))
                
                bot.send_message(chat_id, "🛑 للبدء في استخدام البوت، يرجى الاشتراك في القنوات والمجموعات التالية:", reply_markup=markup)

        elif message.text in ['/balance', 'رصيدي']:
            users_data = load_users()
            balance = users_data.get(str(user_id), {}).get('balance', 0)
            bot.send_message(chat_id, f"💰 رصيدك الحالي هو: *{balance}* روبل.", parse_mode='Markdown')
    
    @bot.callback_query_handler(func=lambda call: call.from_user.id != DEVELOPER_ID)
    def handle_user_callbacks(call):
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        message_id = call.message.message_id
        data = call.data
        
        data_file = load_data()
        users_data = load_users()

        if data == 'assignment':
            try:
                invite_link = bot.create_chat_invite_link(GROUP_ID, creates_join_request=False, name=str(user_id)).invite_link
                
                message_text = (
                    f"🔗 **رابط إحالتك الشخصي:** `{invite_link}`\n\n"
                    "**انسخ الرابط وشاركه مع أصدقائك!** 📥\n"
                    "• كل شخص ينضم عبر رابطك، ستحصل على *1 روبل* 🔥\n\n"
                    "_*ملاحظة: تأكد من أن المستخدم الجديد لا يمتلك حسابًا في البوت مسبقاً.*_"
                )
                bot.send_message(chat_id, message_text, parse_mode='Markdown')
            except ApiTelegramException as e:
                if "Bad Request: not enough rights" in str(e):
                    error_message = "❌ البوت ليس مشرفًا في المجموعة أو ليس لديه صلاحية 'دعوة المستخدمين عبر الرابط'."
                elif "Bad Request: chat not found" in str(e):
                    error_message = "❌ معرف المجموعة (Group ID) غير صحيح."
                else:
                    error_message = f"❌ حدث خطأ غير معروف: {e}"
                bot.send_message(chat_id, f"**عذراً، لا يمكن إنشاء رابط إحالة الآن.**\n\n{error_message}", parse_mode='Markdown')
            except Exception as e:
                bot.send_message(chat_id, f"❌ حدث خطأ أثناء إنشاء رابط الإحالة: {e}")
            return

        elif data == 'check_subscription':
            has_joined_channel = False
            has_joined_group = False
            
            try:
                channel_member = bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
                if channel_member.status in ['member', 'creator', 'administrator']:
                    has_joined_channel = True
                
                group_member = bot.get_chat_member(f"@{GROUP_USERNAME}", user_id)
                if group_member.status in ['member', 'creator', 'administrator']:
                    has_joined_group = True
            except Exception as e:
                print(f"Error checking membership: {e}")

            user_info = users_data.get(str(user_id))
            if has_joined_channel and not user_info.get('has_received_bonus', False):
                users_data[str(user_id)]['balance'] += 0.25
                users_data[str(user_id)]['has_received_bonus'] = True
                save_users(users_data)
                bot.send_message(chat_id, "🎉 تهانينا! لقد حصلت على مكافأة 0.25 روبل لاشتراكك في القناة.")

            if has_joined_channel and has_joined_group:
                bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=f"☑️ *⁞ قناة البوت الرسمية: @{EESSMT}\n🎬︙قم بالتحكم بالبوت الأن عبر الضعط على الأزرار.*", parse_mode='Markdown', reply_markup=get_main_keyboard())
            else:
                bot.send_message(chat_id, "❌ لم يتم الاشتراك في جميع القنوات والمجموعات المطلوبة. يرجى الاشتراك ثم الضغط على 'تحقق' مرة أخرى.")
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
            user_balance = users_data.get(str(user_id), {}).get('balance', 0)
            
            if user_balance < service_price:
                bot.send_message(chat_id, f"❌ *عذرًا، رصيدك غير كافٍ لإتمام هذه العملية.*\n\n*الرصيد المطلوب:* {service_price} روبل.\n*رصيدك الحالي:* {user_balance} روبل.\n\n*يمكنك شحن رصيدك عبر زر شحن الرصيد.*", parse_mode='Markdown')
                return

            users_data[str(user_id)]['balance'] -= service_price
            save_users(users_data)
            
            bot.send_message(chat_id, f"✅ تم شراء خدمة `{service_name}` بنجاح! سيتم معالجة طلبك قريباً.")
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
        elif data == 'ready':
            bot.send_message(chat_id, "🔰 *لا توجد أرقام جاهزة متاحة حالياً.*", parse_mode='Markdown')
            return
        elif data == 'gents':
            bot.send_message(chat_id, "👨‍💻 *نظام الوكلاء قيد المراجعة. إذا كنت مهتماً، يمكنك التواصل مع المشرف.*", parse_mode='Markdown')
            return
        elif data == 'MyAccount':
            user_info = users_data.get(str(user_id), {})
            message_text = (
                f"⚙️ **إعدادات حسابك:**\n"
                f"**الآيدي:** `{user_info.get('id', 'غير متوفر')}`\n"
                f"**الاسم:** `{user_info.get('first_name', 'غير متوفر')}`\n"
                f"**اسم المستخدم:** `@{user_info.get('username', 'غير متوفر')}`\n"
                f"**الرصيد:** `{user_info.get('balance', 0)}` روبل\n"
            )
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message_text, parse_mode='Markdown', reply_markup=get_main_keyboard())
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
            user_info = users_data.get(str(user_id), {})
            balance = user_info.get('balance', 0)
            bot.send_message(chat_id, f"💰 رصيدك الحالي هو: *{balance}* روبل.", parse_mode='Markdown')
            
        elif data == 'back':
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"☑️ *⁞ قناة البوت الرسمية: @{EESSMT}\n🎬︙قم بالتحكم بالبوت الأن عبر الضعط على الأزرار.*", parse_mode='Markdown', reply_markup=get_main_keyboard())
        
        elif data.startswith('service_'):
            service = data.split('_')[1]
            markup = types.InlineKeyboardMarkup()
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
            try:
                parts = data.split('_')
                service, app_id = parts[2], parts[3]
                
                if service == 'viotp':
                    api_data = viotp_client.get_countries().get('countries', {}).get(app_id, {})
                elif service == 'smsman':
                    api_data = smsman_api.get_countries(app_id)
                elif service == 'tigersms':
                    api_data = tiger_sms_client.get_countries(app_id)
                else:
                    bot.send_message(chat_id, "❌ خدمة غير مدعومة.")
                    return

                if not api_data:
                    bot.send_message(chat_id, '❌ لا توجد دول متاحة لهذا التطبيق حاليًا.')
                    return

                markup = types.InlineKeyboardMarkup()
                for country_code, country_info in api_data.items():
                    display_price = country_info.get('price', 'غير متاح')
                    markup.row(types.InlineKeyboardButton(f"{country_info['name']} ({display_price} روبل)", callback_data=f'buy_{service}_{app_id}_{country_code}'))
                
                markup.row(types.InlineKeyboardButton('رجوع', callback_data='Buynum'))
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="اختر الدولة التي تريدها:", reply_markup=markup)

            except Exception as e:
                bot.send_message(chat_id, f"❌ حدث خطأ أثناء الاتصال بالـ API: {e}")

        elif data.startswith('buy_'):
            parts = data.split('_')
            service, app_id, country_code = parts[1], parts[2], parts[3]
            
            data_file = load_data()
            users_data = load_users()
            
            try:
                # تحديث الرصيد والسعر من API قبل الشراء
                if service == 'viotp':
                    country_info = viotp_client.get_countries().get('countries', {}).get(app_id, {}).get(country_code, {})
                elif service == 'smsman':
                    country_info = smsman_api.get_countries(app_id).get(country_code, {})
                elif service == 'tigersms':
                    country_info = tiger_sms_client.get_countries(app_id).get(country_code, {})
                else:
                    bot.send_message(chat_id, "❌ خدمة غير مدعومة.")
                    return

                price = country_info.get('price', 0)
                if not price:
                    bot.send_message(chat_id, "❌ لا يمكن العثور على سعر لهذا الرقم.")
                    return

                user_balance = users_data.get(str(user_id), {}).get('balance', 0)
            
                if user_balance < price:
                    bot.send_message(chat_id, f"❌ *عذرًا، رصيدك غير كافٍ لإتمام هذه العملية.*\n\n*الرصيد المطلوب:* {price} روبل.\n*رصيدك الحالي:* {user_balance} روبل.\n\n*يمكنك شحن رصيدك عبر زر شحن الرصيد.*", parse_mode='Markdown')
                    return
            except Exception as e:
                bot.send_message(chat_id, f"❌ حدث خطأ أثناء التحقق من الرصيد: {e}")
                return

            try:
                if service == 'viotp':
                    result = viotp_client.buy_number(app_id)
                elif service == 'smsman':
                    result = smsman_api.request_smsman_number(app_id, country_code)
                elif service == 'tigersms':
                    result = tiger_sms_client.get_number(app_id, country_code)

                if result and result.get('success'):
                    request_id = result.get('id')
                    phone_number = result.get('number', result.get('Phone', 'غير متوفر'))
                    
                    users_data[str(user_id)]['balance'] -= price
                    save_users(users_data)
                    
                    active_requests = data_file.get('active_requests', {})
                    active_requests[request_id] = {
                        'user_id': user_id,
                        'phone_number': phone_number,
                        'status': 'pending',
                        'service': service,
                        'price': price
                    }
                    data_file['active_requests'] = active_requests
                    save_data(data_file)
                    
                    markup = types.InlineKeyboardMarkup()
                    markup.row(types.InlineKeyboardButton('✅ الحصول على الكود', callback_data=f'get_otp_{service}_{request_id}'))
                    markup.row(types.InlineKeyboardButton('❌ إلغاء الطلب', callback_data=f'cancel_{service}_{request_id}'))
                    bot.send_message(chat_id, f"✅ تم طلب الرقم بنجاح: *{phone_number}*\n\nاضغط على الزر للحصول على الكود أو إلغاء الطلب.", parse_mode='Markdown', reply_markup=markup)
                else:
                    bot.send_message(chat_id, "❌ فشل طلب الرقم. قد يكون غير متوفر أو أن رصيدك في الخدمة غير كافٍ.")
            except Exception as e:
                bot.send_message(chat_id, f"❌ حدث خطأ أثناء الشراء: {e}")
                
        elif data.startswith('get_otp_'):
            parts = data.split('_')
            service, request_id = parts[2], parts[3]
            
            active_requests = data_file.get('active_requests', {})
            request_info = active_requests.get(request_id)

            if not request_info:
                bot.send_message(chat_id, '❌ هذا الطلب غير موجود أو انتهت صلاحيته.')
                return

            try:
                if service == 'viotp':
                    result = viotp_client.get_otp(request_id)
                elif service == 'smsman':
                    result = smsman_api.get_smsman_code(request_id)
                elif service == 'tigersms':
                    result = tiger_sms_client.get_code(request_id)
                
                if result and result.get('success'):
                    code = result.get('code')
                    bot.send_message(chat_id, f"✅ تم استلام الكود بنجاح!\n\n*الكود:* `{code}`", parse_mode='Markdown')
                    del data_file['active_requests'][request_id]
                    save_data(data_file)
                else:
                    bot.send_message(chat_id, '⏳ لم يتم استلام الكود بعد. يرجى المحاولة مرة أخرى لاحقاً.')
            except Exception as e:
                bot.send_message(chat_id, f"❌ حدث خطأ أثناء جلب الكود: {e}")


        elif data.startswith('cancel_'):
            parts = data.split('_')
            service, request_id = parts[1], parts[2]
            
            active_requests = data_file.get('active_requests', {})
            request_info = active_requests.get(request_id)
            
            if not request_info or request_info['user_id'] != user_id:
                bot.send_message(chat_id, '❌ هذا الطلب غير موجود أو لا يمكنك إلغاؤه.')
                return
            
            try:
                if service == 'viotp':
                    viotp_client.cancel_number(request_id)
                elif service == 'smsman':
                    smsman_api.cancel_smsman_number(request_id)
                elif service == 'tigersms':
                    tiger_sms_client.cancel_number(request_id)

                price = request_info['price']
                users_data[str(user_id)]['balance'] += price
                save_users(users_data)
                
                del data_file['active_requests'][request_id]
                save_data(data_file)
                
                bot.send_message(chat_id, f"✅ تم إلغاء الطلب بنجاح. تم استرجاع `{price}` روبل إلى رصيدك.", parse_mode='Markdown')
            except Exception as e:
                bot.send_message(chat_id, f"❌ حدث خطأ أثناء إلغاء الطلب: {e}")
