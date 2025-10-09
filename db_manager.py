# db_manager.py
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
    print(f"ERROR: Failed to connect to MongoDB: {e}")


# ----------------------------------------------------------------
# دوال المستخدمين (الأرصدة والمستندات)
# ----------------------------------------------------------------

def get_user_doc(user_id):
    """
    جلب مستند المستخدم بالكامل. (الدالة المفقودة التي سببت الخطأ)
    """
    return users_collection.find_one({"_id": str(user_id)})

def get_user_balance(user_id):
    """جلب رصيد المستخدم"""
    user_doc = get_user_doc(user_id)
    return user_doc.get("balance", 0) if user_doc else 0

def update_user_balance(user_id, amount, is_increment=True):
    """تحديث (إضافة/خصم) رصيد المستخدم"""
    if is_increment:
        update_op = {"$inc": {"balance": amount}}
    else:
        update_op = {"$set": {"balance": amount}}
        
    users_collection.update_one(
        {"_id": str(user_id)},
        {**update_op, "$set": {"id": str(user_id)}},
        upsert=True
    )

def register_user(user_id, first_name, username, new_purchase=None, update_purchase_status=None, delete_purchase_id=None):
    """
    تسجيل/تحديث بيانات المستخدم ومعالجة سجل المشتريات. (الدالة المفقودة)
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
        # لا نتابع باقي التحديثات لأننا قمنا بتحديث منفصل
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
# دوال بيانات البوت (الدول، States، الخدمات، إلخ) - تحل محل load_data و save_data
# ----------------------------------------------------------------

def get_bot_data():
    """جلب جميع بيانات البوت (الدول، States، الأرقام الجاهزة)"""
    data_doc = data_collection.find_one({"_id": "bot_settings"})
    
    default = {'countries': {}, 'states': {}, 'active_requests': {}, 'sh_services': {}, 'ready_numbers': []}
    
    return data_doc.get("value", default) if data_doc else default

def save_bot_data(data_dict):
    """حفظ جميع بيانات البوت"""
    data_collection.update_one(
        {"_id": "bot_settings"},
        {"$set": {"value": data_dict}},
        upsert=True
    )
