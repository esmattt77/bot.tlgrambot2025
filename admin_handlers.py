import telebot
from telebot import types
import json
import time

def setup_admin_handlers(bot, DEVELOPER_ID, data_file, users_data, viotp_client, smsman_api, tiger_sms_client):
    
    @bot.message_handler(func=lambda message: message.from_user.id == DEVELOPER_ID)
    def handle_admin_messages(message):
        chat_id = message.chat.id
        user_id = message.from_user.id
        data_file = load_data()
        state = data_file.get('states', {}).get(str(user_id))
        
        if message.text in ['/admin']:
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('إحصائيات البوت 📊', callback_data='bot_stats'), types.InlineKeyboardButton('إدارة المستخدمين 👥', callback_data='manage_users'))
            markup.row(types.InlineKeyboardButton('إضافة رصيد 💰', callback_data='add_balance'), types.InlineKeyboardButton('خصم رصيد 💸', callback_data='deduct_balance'))
            markup.row(types.InlineKeyboardButton('إضافة دولة 🌐', callback_data='add_country'), types.InlineKeyboardButton('حذف دولة ❌', callback_data='delete_country'))
            markup.row(types.InlineKeyboardButton('عرض الطلبات النشطة 📞', callback_data='view_active_requests'), types.InlineKeyboardButton('إلغاء جميع الطلبات 🚫', callback_data='cancel_all_requests'))
            markup.row(types.InlineKeyboardButton('إرسال رسالة جماعية 📣', callback_data='broadcast_message'), types.InlineKeyboardButton('الكشف عن أرصدة المواقع 💳', callback_data='show_api_balance_menu'))
            markup.row(types.InlineKeyboardButton('إدارة الرشق 🚀', callback_data='sh_admin_menu'))
            bot.send_message(chat_id, "أهلاً بك في لوحة تحكم المشرف!", reply_markup=markup)

        if state and state.get('step') == 'waiting_for_add_coin_id':
            target_id = message.text
            data_file['states'][str(user_id)]['target_id'] = target_id
            data_file['states'][str(user_id)]['step'] = 'waiting_for_add_coin_amount'
            save_data(data_file)
            bot.send_message(chat_id, "تم حفظ الآيدي. الآن أرسل **المبلغ** الذي تريد إضافته للمستخدم.")
        
        elif state and state.get('step') == 'waiting_for_add_coin_amount':
            try:
                amount = int(message.text)
                target_id = state.get('target_id')
                users_data = load_users()
                if str(target_id) not in users_data:
                    users_data[str(target_id)] = {'balance': 0}
                users_data[str(target_id)]['balance'] += amount
                save_users(users_data)
                
                try:
                    bot.send_message(target_id, f"🎉 تم إضافة {amount} روبل إلى رصيدك من قبل المشرف!")
                except telebot.apihelper.ApiException as e:
                    bot.send_message(chat_id, f"✅ تم إضافة الرصيد بنجاح، لكن لا يمكن إرسال رسالة للمستخدم: {e}")

                del data_file['states'][str(user_id)]
                save_data(data_file)
                bot.send_message(chat_id, f"✅ تم إضافة {amount} روبل إلى المستخدم ذو الآيدي: {target_id}")
            except ValueError:
                bot.send_message(chat_id, "❌ المبلغ الذي أدخلته غير صحيح. يرجى إدخال رقم.")
        
        # ... Other message handlers for admin ...

    @bot.callback_query_handler(func=lambda call: call.from_user.id == DEVELOPER_ID)
    def handle_admin_callbacks(call):
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        message_id = call.message.message_id
        data = call.data

        if data == 'admin_main_menu':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton('إحصائيات البوت 📊', callback_data='bot_stats'), types.InlineKeyboardButton('إدارة المستخدمين 👥', callback_data='manage_users'))
            markup.row(types.InlineKeyboardButton('إضافة رصيد 💰', callback_data='add_balance'), types.InlineKeyboardButton('خصم رصيد 💸', callback_data='deduct_balance'))
            markup.row(types.InlineKeyboardButton('إضافة دولة 🌐', callback_data='add_country'), types.InlineKeyboardButton('حذف دولة ❌', callback_data='delete_country'))
            markup.row(types.InlineKeyboardButton('عرض الطلبات النشطة 📞', callback_data='view_active_requests'), types.InlineKeyboardButton('إلغاء جميع الطلبات 🚫', callback_data='cancel_all_requests'))
            markup.row(types.InlineKeyboardButton('إرسال رسالة جماعية 📣', callback_data='broadcast_message'), types.InlineKeyboardButton('الكشف عن أرصدة المواقع 💳', callback_data='show_api_balance_menu'))
            markup.row(types.InlineKeyboardButton('إدارة الرشق 🚀', callback_data='sh_admin_menu'))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="أهلاً بك في لوحة تحكم المشرف!", reply_markup=markup)
            return

        # ... Other callback handlers for admin ...

