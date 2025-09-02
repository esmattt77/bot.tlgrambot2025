import requests
import os

def get_viotp_balance():
    try:
        # قراءة مفتاح الـ API من المتغيرات البيئية
        # يجب أن يكون اسم المتغير على منصة الاستضافة هو VIOTP_API_KEY
        api_key = os.environ.get('VIOTP_API_KEY')
        if not api_key:
            print("Error: VIOTP_API_KEY environment variable not set.")
            return False

        # استخدام 'token' كمعامل في الرابط، كما يتطلب API الخاص بـ ViOTP
        url = f"https://api.viotp.com/users/balance?token={api_key}"
        
        # إرسال طلب GET إلى الرابط مع مهلة 10 ثوانٍ
        response = requests.get(url, timeout=10)
        
        # التحقق من حالة الاستجابة. إذا كانت خطأ (مثل 404 أو 500)، سيتم إثارة خطأ
        response.raise_for_status()
        
        # تحليل الاستجابة من تنسيق JSON إلى قاموس Python
        data = response.json()
        
        # التحقق من أن الطلب كان ناجحًا والوصول إلى الرصيد من خلال المسار الصحيح
        # المسار هو: 'data' ثم 'balance'
        if data.get('status') == 'success' and 'data' in data and 'balance' in data['data']:
            balance_raw = data['data']['balance']
            
            # تطبيق نفس المعادلة الحسابية الموجودة في كود PHP الذي يعمل لديك
            balance_calculated = int((balance_raw / 22000) * 64)
            return balance_calculated
        else:
            # إرجاع قيمة False إذا كانت الاستجابة غير متوقعة
            return False
            
    except requests.exceptions.RequestException as e:
        # التعامل مع أخطاء الشبكة أو الاتصال
        print(f"Error connecting to ViOTP API: {e}")
        return False
    except (ValueError, KeyError) as e:
        # التعامل مع أخطاء تحليل JSON أو عدم وجود المفاتيح المطلوبة
        print(f"Error parsing ViOTP response: {e}")
        return False
