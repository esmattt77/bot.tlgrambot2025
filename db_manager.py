from pymongo import MongoClient
import time
import logging

# تهيئة التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# *** مهم: استبدل YOUR_MONGO_CONNECTION_STRING برابط الاتصال الفعلي الخاص بك ***
# استخدم رابط الاتصال الذي أرسلته لي مسبقاً
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
        update_op = {"$set": {"balance": amount}} # لضبط قيمة محددة
        
    users_collection.update_one(
        {"_id": user_id_str},
        # 💡 ندمج العمليات ونستخدم $set لتحديث حقل 'id' للتأكد من وجوده
        {**update_op, "$set": {"id": user_id_str}},
        upsert=True
    )

def register_user(user_id, first_name, username, new_purchase=None, update_purchase_status=None, delete_purchase_id=None, referrer_id=None):
    """
    تسجيل/تحديث بيانات المستخدم ومعالجة سجل المشتريات ومعالجة الإحالة.
    """
    user_id_str = str(user_id)
    user_doc = users_collection.find_one({'_id': user_id_str})
    is_new_user = user_doc is None
    
    update_data = {
        "first_name": first_name,
        "username": username,
        "last_active": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
    }
    
    # 3. معالجة الإحالة (Referral)
    if is_new_user and referrer_id and str(referrer_id) != user_id_str:
        referrer_id_str = str(referrer_id)
        if users_collection.find_one({'_id': referrer_id_str}):
            # A. تخزين معرف المُحيل للمستخدم الجديد في $setOnInsert
            # B. منح مكافأة الإحالة (0.25 روبل)
            REFERRAL_BONUS = 0.25
            update_user_balance(referrer_id_str, REFERRAL_BONUS, is_increment=True)
            logging.info(f"User {user_id_str} referred by {referrer_id_str}. Awarded {REFERRAL_BONUS} RUB to referrer.")

    # 4. معالجة سجل المشتريات
    purchases = user_doc.get("purchases", []) if user_doc else []
    
    if new_purchase:
        if 'request_id' in new_purchase: new_purchase['request_id'] = str(new_purchase['request_id'])
        purchases.append(new_purchase)
    
    if update_purchase_status:
        request_id_to_update = str(update_purchase_status.get('request_id')) 
        new_status = update_purchase_status.get('status')
        for p in purchases:
            if str(p.get('request_id')) == request_id_to_update: 
                p['status'] = new_status
                break
        
    if delete_purchase_id:
        purchases = [p for p in purchases if str(p.get('request_id')) != str(delete_purchase_id)]
        
    update_data['purchases'] = purchases
    
    # 5. تنفيذ عملية التحديث/الإنشاء
    set_on_insert_data = {
        "balance": 0,
        "join_date": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
    }
    
    # تخزين 'referred_by' عند الإنشاء فقط
    if is_new_user and referrer_id and str(referrer_id) != user_id_str and users_collection.find_one({'_id': str(referrer_id)}):
        set_on_insert_data["referred_by"] = str(referrer_id)
    
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
    return [doc["_id"] for doc in users_collection.find({}, {"_id": 1})]


# ----------------------------------------------------------------
# دوال بيانات البوت (الدول، States، الخدمات، إلخ)
# ----------------------------------------------------------------

def get_bot_data():
    """جلب جميع بيانات البوت (الدول، States، الأرقام الجاهزة)"""
    # 💡 نبحث عن المستند bot_settings
    data_doc = data_collection.find_one({"_id": "bot_settings"})
    
    # 🚀 القيم الافتراضية الموحدة مع المفتاح الصحيح لخدمات الرشق
    default = {
        '_id': 'bot_settings', 
        'countries': {}, 
        'states': {}, 
        'active_requests': {}, 
        'smmkings_services': {},   # ⬅️ المفتاح الصحيح الذي يجب أن يستخدمه الجميع
        'user_states': {},       
        'ready_numbers_stock': {} 
    }
    
    if data_doc:
        # إضافة الحقول الافتراضية إذا كانت مفقودة
        for key, value in default.items():
            if key not in data_doc:
                data_doc[key] = value
        
        # 📌 هام: هنا نقوم بتحويل المفتاح القديم (إن وجد) إلى المفتاح الجديد
        if 'sh_services' in data_doc and not data_doc.get('smmkings_services'):
            data_doc['smmkings_services'] = data_doc['sh_services']
            # لا نحذف المفتاح القديم مباشرة هنا لمنع الكتابة غير الضرورية على DB
            
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
