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

def register_user(user_id, first_name, username, new_purchase=None, update_purchase_status=None, delete_purchase_id=None):
    """
    🛠️ [التعديل الجذري]
    تسجيل/تحديث بيانات المستخدم ومعالجة سجل المشتريات بمرونة عالية.
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
    
    # تهيئة سجل المشتريات (إذا لم يكن موجوداً)
    # 💡 يتم سحب القائمة الحالية (أو قائمة فارغة) لمعالجتها
    purchases = user_doc.get("purchases", []) if user_doc and user_doc.get("purchases") is not None else []
    
    # 3. معالجة سجل المشتريات
    
    # أ. إضافة سجل شراء جديد
    if new_purchase:
        # 💡 [ضمان تخزين request_id كسلسلة نصية دائماً]
        if 'request_id' in new_purchase:
             new_purchase['request_id'] = str(new_purchase['request_id'])
             
        purchases.append(new_purchase)
    
    # ب. تحديث حالة سجل شراء موجود (إلغاء أو إتمام)
    if update_purchase_status:
        # 💡 نستخدم str() لضمان المطابقة حتى لو كان الطلب مخزناً كرقم
        request_id_to_update = str(update_purchase_status.get('request_id')) 
        new_status = update_purchase_status.get('status')
        
        found = False
        for p in purchases:
            # 💡 المطابقة بمرونة عالية (المخزن كسلسلة مقابل القادم كسلسلة)
            if str(p.get('request_id')) == request_id_to_update: 
                p['status'] = new_status
                found = True
                break
        
        if not found:
             # إشعار للتسجيل في حالة عدم العثور (للمراقبة)
             # هذا يحدث إذا فشل العثور على الطلب في السجل حتى بعد محاولة الإلغاء
             print(f"Warning: Purchase ID {request_id_to_update} not found for status update for user {user_id_str}.")

    # ج. حذف سجل شراء موجود
    if delete_purchase_id:
        purchases = [p for p in purchases if str(p.get('request_id')) != str(delete_purchase_id)]
        
    # 4. دمج التحديثات
    
    # 💡 تحديث قائمة المشتريات بالكامل كقائمة محدثة
    update_data['purchases'] = purchases
    
    # 5. تنفيذ عملية التحديث/الإنشاء
    users_collection.update_one(
        {"_id": user_id_str},
        {
            "$set": update_data, # تحديث البيانات الأساسية وسجل المشتريات الجديد بالكامل
            "$setOnInsert": { # إنشاء القيم الافتراضية إذا كان المستخدم جديداً
                "balance": 0,
                "join_date": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
            }
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
    
    # القيم الافتراضية
    default = {
        'countries': {}, 
        'states': {}, 
        'active_requests': {}, 
        'sh_services': {}, 
        'ready_numbers_stock': {} 
    }
    
    # 💡 نرجع المستند إذا وجد، أو القيم الافتراضية
    return data_doc if data_doc else default

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
