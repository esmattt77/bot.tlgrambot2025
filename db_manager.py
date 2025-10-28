from pymongo import MongoClient
import time
import logging

# تهيئة التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# *** مهم: استبدل YOUR_MONGO_CONNECTION_STRING برابط الاتصال الفعلي الخاص بك ***
MONGO_URI = "mongodb+srv://Esmat:_.SASet#aKcU6Zu@bottlegrmbot2025.gccpnku.mongodb.net/?retryWrites=true&w=majority&appName=bottlegrmbot2025" 

try:
    client = MongoClient(MONGO_URI)
    db = client["bot_database"]  # اسم قاعدة البيانات الافتراضي
    
    # Collections (جداول)
    users_collection = db["users"] 
    data_collection = db["bot_data"] 
    
    print("MongoDB connection established successfully.")
except Exception as e:
    print(f"ERROR: Failed to connect to MongoDB: {e}")


# ----------------------------------------------------------------
# دوال المستخدمين (الأرصدة والمستندات)
# ----------------------------------------------------------------

def get_user_doc(user_id):
    """
    جلب مستند المستخدم بالكامل.
    """
    # 💡 [ملاحظة]: يفضل تخزين الـ _id دائماً كسلسلة نصية (str) لتجنب مشاكل النوع
    return users_collection.find_one({"_id": str(user_id)})

def get_user_balance(user_id):
    """جلب رصيد المستخدم"""
    user_doc = get_user_doc(user_id)
    return user_doc.get("balance", 0) if user_doc else 0

def update_user_balance(user_id, amount, is_increment=True):
    """تحديث (إضافة/خصم) رصيد المستخدم"""
    user_id_str = str(user_id)
    if is_increment:
        update_op = {"$inc": {"balance": amount}}
    else:
        # هذه الحالة لا تستخدم عادةً لزيادة/نقصان الرصيد، بل لضبطه على قيمة محددة
        update_op = {"$set": {"balance": amount}} 
        
    users_collection.update_one(
        {"_id": user_id_str},
        {**update_op, "$set": {"id": user_id_str}},
        upsert=True
    )

def register_user(user_id, first_name, username, new_purchase=None, update_purchase_status=None, delete_purchase_id=None, referrer_id=None):
    """
    🛠️ [مُراجعة للتأكد من دعم SMMKings]
    تسجيل/تحديث بيانات المستخدم ومعالجة سجل المشتريات بمرونة عالية، ومعالجة الإحالة.
    """
    user_id_str = str(user_id)
    
    # 1. جلب المستند الحالي
    user_doc = users_collection.find_one({'_id': user_id_str})
    
    # 2. إعداد الحقول الأساسية للتحديث
    update_data = {
        "first_name": first_name,
        "username": username,
        "last_active": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
    }
    
    # 3. معالجة الإحالة (Referral)
    
    # التحقق مما إذا كان المستخدم جديداً (لم يتم العثور على مستند)
    is_new_user = user_doc is None
    
    if is_new_user and referrer_id:
        referrer_id_str = str(referrer_id)
        
        # التأكد من أن المُحيل ليس هو نفسه المستخدم الجديد
        if referrer_id_str != user_id_str:
            
            # التأكد من أن المُحيل موجود في قاعدة البيانات
            referrer_doc = users_collection.find_one({'_id': referrer_id_str})
            
            if referrer_doc:
                # أ. تخزين معرف المُحيل للمستخدم الجديد
                update_data["referred_by"] = referrer_id_str
                
                # ب. منح مكافأة الإحالة للمُحيل (0.25 روبل)
                REFERRAL_BONUS = 0.25
                update_user_balance(referrer_id_str, REFERRAL_BONUS, is_increment=True)
                
                logging.info(f"User {user_id_str} referred by {referrer_id_str}. Awarded {REFERRAL_BONUS} RUB to referrer.")
            else:
                logging.info(f"Referrer ID {referrer_id_str} not found in DB.")
        else:
            logging.info(f"Self-referral attempt detected by {user_id_str}, ignored.")


    # 4. معالجة سجل المشتريات (هذه الدالة مرنة بما يكفي لدعم شراء الرشق)
    
    # تهيئة سجل المشتريات (إذا لم يكن موجوداً)
    purchases = user_doc.get("purchases", []) if user_doc and user_doc.get("purchases") is not None else []
    
    # أ. إضافة سجل شراء جديد
    if new_purchase:
        if 'request_id' in new_purchase:
             new_purchase['request_id'] = str(new_purchase['request_id'])
             
        # يتم تسجيل عمليات الرشق (SMMKings) بحالة 'sh_purchased' في user_handlers.py
        purchases.append(new_purchase)
    
    # ب. تحديث حالة سجل شراء موجود (إلغاء أو إتمام)
    if update_purchase_status:
        request_id_to_update = str(update_purchase_status.get('request_id')) 
        new_status = update_purchase_status.get('status')
        
        found = False
        for p in purchases:
            # البحث عن الطلب سواء كان رقم وهمي أو طلب رشق
            if str(p.get('request_id')) == request_id_to_update: 
                p['status'] = new_status
                found = True
                break
        
        if not found:
             print(f"Warning: Purchase ID {request_id_to_update} not found for status update for user {user_id_str}.")

    # ج. حذف سجل شراء موجود
    if delete_purchase_id:
        purchases = [p for p in purchases if str(p.get('request_id')) != str(delete_purchase_id)]
        
    # 5. دمج التحديثات
    
    update_data['purchases'] = purchases
    
    # 6. تنفيذ عملية التحديث/الإنشاء
    
    # إعداد البيانات التي سيتم تعيينها عند الإنشاء فقط
    set_on_insert_data = {
        "balance": 0,
        "join_date": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
    }
    
    # إذا كان المستخدم جديداً ومُحالاً، سنحتاج لتعيين "referred_by" في $setOnInsert لضمان تخزينه عند الإنشاء
    if is_new_user and referrer_id and str(referrer_id) != user_id_str:
        # إذا تم تخزينها في update_data بالفعل، لا نحتاج لتكرارها هنا، لكن للتأكد:
        if "referred_by" in update_data:
             set_on_insert_data["referred_by"] = update_data["referred_by"]
             # إذا تم تخزينها في $setOnInsert، نزيلها من $set لمنع كتابة القيمة الفارغة لاحقاً.
             if "referred_by" in update_data:
                del update_data["referred_by"]

    
    users_collection.update_one(
        {"_id": user_id_str},
        {
            "$set": update_data,
            "$setOnInsert": set_on_insert_data
        },
        upsert=True
    )
    
def get_all_users_keys():
    """جلب آيديات جميع المستخدمين للبث الجماعي"""
    # نستخدم "_id" لأننا نضبطه ليكون آيدي المستخدم
    return [doc["_id"] for doc in users_collection.find({}, {"_id": 1})]


# ----------------------------------------------------------------
# دوال بيانات البوت (الدول، States، الخدمات، إلخ)
# ----------------------------------------------------------------

def get_bot_data():
    """جلب جميع بيانات البوت (الدول، States، الأرقام الجاهزة)"""
    # 💡 نبحث عن المستند bot_settings
    data_doc = data_collection.find_one({"_id": "bot_settings"})
    
    # 💡 [التأكيد على حقل sh_services] - التأكد من وجوده كقيمة افتراضية
    default = {
        '_id': 'bot_settings', # إضافة الـ ID الافتراضي
        'countries': {}, 
        'states': {}, 
        'active_requests': {}, 
        'sh_services': {},       # ⬅️ **تم التأكد من وجود هذا الحقل لخدمات SMMKings**
        'awaiting_sh_order': {}, # ⬅️ **تم التأكد من وجود هذا الحقل لحالة انتظار الرشق**
        'ready_numbers_stock': {} 
    }
    
    # 💡 نرجع المستند إذا وجد، أو القيم الافتراضية
    
    if data_doc:
        # إذا وُجد المستند، نتأكد من إضافة الحقول الجديدة إذا كانت مفقودة (مرونة إضافية)
        for key, value in default.items():
            if key not in data_doc:
                data_doc[key] = value
        return data_doc
    else:
        return default

def save_bot_data(data_dict):
    """
    حفظ/تحديث بيانات البوت بشكل جزئي.
    """
    if not data_dict:
        return
        
    data_collection.update_one(
        {"_id": "bot_settings"},
        {"$set": data_dict}, 
        upsert=True
    )
