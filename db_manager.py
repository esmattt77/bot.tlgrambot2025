from pymongo import MongoClient
import time

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
    # 💡 يجب التعامل مع فشل الاتصال بخروج أو تسجيل (log) مناسب
    print(f"ERROR: Failed to connect to MongoDB: {e}")
    # يمكنك إضافة sys.exit(1) هنا لإيقاف البوت إذا فشل الاتصال بالقاعدة

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
        # يستخدم $inc لزيادة أو إنقاص الرصيد (مقدار سالب)
        update_op = {"$inc": {"balance": amount}}
    else:
        # يستخدم $set لضبط قيمة الرصيد
        update_op = {"$set": {"balance": amount}}
        
    users_collection.update_one(
        {"_id": user_id_str},
        {**update_op, "$set": {"id": user_id_str}},
        upsert=True
    )

def register_user(user_id, first_name, username, new_purchase=None, update_purchase_status=None, delete_purchase_id=None):
    """
    تسجيل/تحديث بيانات المستخدم ومعالجة سجل المشتريات.
    """
    user_id_str = str(user_id)
    
    update_data = {
        "first_name": first_name,
        "username": username,
        "last_active": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
    }
    
    update_op = {"$set": update_data}
    
    # إضافة سجل شراء جديد
    if new_purchase:
        update_op.setdefault("$push", {})["purchases"] = new_purchase
    
    # تحديث حالة سجل شراء موجود (كود تم استلامه)
    if update_purchase_status:
        # نبحث عن الطلب داخل مصفوفة purchases ونحدث حالته
        users_collection.update_one(
            {"_id": user_id_str, "purchases.request_id": update_purchase_status['request_id']},
            {"$set": {"purchases.$.status": update_purchase_status['status']}}
        )
        return

    # حذف سجل شراء موجود (إلغاء الطلب)
    if delete_purchase_id:
        # نستخدم $pull لإزالة العنصر من المصفوفة بناءً على request_id
        update_op.setdefault("$pull", {})["purchases"] = {"request_id": delete_purchase_id}

    # إذا كان المستخدم جديدًا، نضبط القيم الافتراضية
    users_collection.update_one(
        {"_id": user_id_str},
        {
            **update_op,
            "$setOnInsert": {
                "balance": 0,
                "join_date": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
                "purchases": []
            }
        },
        upsert=True
    )
    
def get_all_users_keys():
    """جلب آيديات جميع المستخدمين للبث الجماعي"""
    # نستخدم "_id" لأننا نضبطه ليكون آيدي المستخدم
    return [doc["_id"] for doc in users_collection.find({}, {"_id": 1})]


# ----------------------------------------------------------------
# دوال بيانات البوت (الإعدادات العامة - الدول، States، الخدمات، الأرقام الجاهزة)
# ----------------------------------------------------------------

def get_bot_data():
    """جلب جميع بيانات البوت (الدول، States، الأرقام الجاهزة، إلخ) من المستند bot_settings"""
    data_doc = data_collection.find_one({"_id": "bot_settings"})
    
    # 💡 تحديث القيم الافتراضية لتشمل المخزون الجديد
    default = {
        'countries': {}, 
        'states': {}, 
        'active_requests': {}, 
        'sh_services': {}, 
        'ready_numbers_stock': {} # 🆕 المخزون الجديد سيكون كائن/ديكشنري
    }
    
    # نحفظ البيانات كحقول مباشرة في المستند بدلاً من داخل حقل "value" كما كان في السابق
    return data_doc if data_doc else default

def save_bot_data(data_dict):
    """
    حفظ/تحديث بيانات البوت بشكل جزئي (مهم للتزامن).
    نمرر فقط الحقول التي نريد تحديثها في data_dict.
    """
    if not data_dict:
        return
        
    # نستخدم $set لتحديث الحقول الممررة فقط
    data_collection.update_one(
        {"_id": "bot_settings"},
        {"$set": data_dict},
        upsert=True
    )
    
# ----------------------------------------------------------------
# 🚫 دوال الأرقام الجاهزة القديمة محذوفة (get_ready_numbers_stock, update_ready_numbers_stock)
# تم دمج عملها في دالتي get_bot_data و save_bot_data
# ----------------------------------------------------------------
