# db_manager.py
from pymongo import MongoClient

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
    # إذا فشل الاتصال هنا، لن يعمل البوت. تحقق من رابط MONGO_URI وكلمة المرور.


# ----------------------------------------------------------------
# دوال المستخدمين (الأرصدة) - تحل محل load_users و save_users
# ----------------------------------------------------------------

def get_user_balance(user_id):
    """جلب رصيد المستخدم"""
    user_doc = users_collection.find_one({"_id": str(user_id)})
    return user_doc.get("balance", 0) if user_doc else 0

def update_user_balance(user_id, amount, is_increment=True):
    """تحديث (إضافة/خصم) رصيد المستخدم"""
    if is_increment:
        # للإضافة نستخدم $inc مع القيمة الموجبة، للخصم نستخدم $inc مع القيمة السالبة
        update_op = {"$inc": {"balance": amount}}
    else:
        # لتعيين قيمة محددة (في حالة كانت هناك حاجة لتعيين رصيد محدد)
        update_op = {"$set": {"balance": amount}}
        
    users_collection.update_one(
        {"_id": str(user_id)},
        {**update_op, "$set": {"id": str(user_id)}}, # نستخدم id في حالة لم يكن _id موجوداً
        upsert=True
    )
    
def get_all_users_keys():
    """جلب آيديات جميع المستخدمين للبث الجماعي"""
    return [doc["_id"] for doc in users_collection.find({}, {"_id": 1})]


# ----------------------------------------------------------------
# دوال بيانات البوت (الدول، States، الخدمات، إلخ) - تحل محل load_data و save_data
# ----------------------------------------------------------------

def get_bot_data():
    """جلب جميع بيانات البوت (الدول، States، الأرقام الجاهزة)"""
    data_doc = data_collection.find_one({"_id": "bot_settings"})
    
    # القيم الافتراضية المطلوبة لكي لا يتعطل البوت عند التشغيل لأول مرة
    default = {'countries': {}, 'states': {}, 'active_requests': {}, 'sh_services': {}, 'ready_numbers': []}
    
    # في MongoDB، نخزن القاموس كاملاً في حقل 'value'
    return data_doc.get("value", default) if data_doc else default

def save_bot_data(data_dict):
    """حفظ جميع بيانات البوت"""
    # حفظ القاموس كاملاً في مستند واحد باسم "bot_settings"
    data_collection.update_one(
        {"_id": "bot_settings"},
        {"$set": {"value": data_dict}},
        upsert=True
    )

