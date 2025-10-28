import requests
import json
import logging
import os

logger = logging.getLogger(__name__)

# تأكد من إضافة هذا المتغير البيئي (SMM_API_KEY) إلى الاستضافة
API_KEY = os.environ.get('SMM_API_KEY') 
BASE_URL = 'https://smmkings.com/api/v2'

class SMMKingsAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        
    def _make_request(self, params):
        """دالة خاصة لإرسال الطلبات إلى SMMKings API."""
        params['key'] = self.api_key
        params['action'] = params.get('action') # إضافة "action" من الـ params
        
        try:
            # SMMKings تستخدم POST
            response = requests.post(BASE_URL, data=params, timeout=20) 
            response.raise_for_status()
            
            # محاولة قراءة الاستجابة كـ JSON
            try:
                return response.json()
            except json.JSONDecodeError:
                logger.error(f"SMMKings failed to decode JSON: {response.text}")
                return {"error": "JSON_DECODE_FAILED", "raw_response": response.text}

        except requests.exceptions.RequestException as e:
            logger.error(f"SMMKings API request failed: {e}, Params: {params}")
            return {"error": f"API_REQUEST_FAILED: {e}"}

    # 1. جلب قائمة الخدمات المتاحة
    def get_services(self):
        """جلب قائمة الخدمات والأسعار والمخزون."""
        params = {'action': 'services'}
        response = self._make_request(params)
        
        if isinstance(response, list):
            # الاستجابة الناجحة تكون قائمة من القواميس
            return {'success': True, 'services': response}
        else:
            # إذا كانت الاستجابة ليست قائمة، فهي تحتوي على خطأ
            error_msg = response.get('error', 'UNKNOWN_ERROR')
            logger.error(f"SMMKings get_services failed: {error_msg}")
            return {'success': False, 'error': error_msg}

    # 2. إضافة طلب جديد (شراء الخدمة)
    def add_order(self, service_id, link, quantity, runs=None, interval=None):
        """
        إضافة طلب رشق جديد.
        :param service_id: معرف الخدمة (Service ID).
        :param link: رابط الصفحة/الحساب.
        :param quantity: الكمية المطلوبة.
        """
        params = {
            'action': 'add',
            'service': service_id,
            'link': link,
            'quantity': quantity
        }
        
        if runs is not None:
            params['runs'] = runs
        if interval is not None:
            params['interval'] = interval

        response = self._make_request(params)
        
        # مثال على الاستجابة الناجحة: {"order": 23501}
        if 'order' in response:
            return {'success': True, 'order_id': response['order']}
        else:
            error_msg = response.get('error', 'FAILED_TO_ADD_ORDER')
            logger.warning(f"SMMKings add_order failed: {error_msg}, Link: {link}")
            return {'success': False, 'error': error_msg}

    # 3. التحقق من حالة طلب واحد
    def get_order_status(self, order_id):
        """الحصول على حالة طلب معين."""
        params = {
            'action': 'status',
            'order': order_id
        }
        response = self._make_request(params)
        
        # مثال على الاستجابة الناجحة: {"charge": "0.27819", "status": "Partial"}
        if 'status' in response:
            return {'success': True, 'status_info': response}
        else:
            error_msg = response.get('error', 'ORDER_STATUS_FETCH_FAILED')
            return {'success': False, 'error': error_msg}

    # 4. الحصول على رصيد المستخدم
    def get_balance(self):
        """الحصول على رصيد المستخدم وعملة الحساب."""
        params = {'action': 'balance'}
        response = self._make_request(params)
        
        # مثال على الاستجابة الناجحة: {"balance": "100.84292", "currency": "دولار أمريكي"}
        if 'balance' in response:
            return {'success': True, 
                    'balance': float(response['balance']), 
                    'currency': response['currency']}
        else:
            error_msg = response.get('error', 'BALANCE_FETCH_FAILED')
            logger.error(f"SMMKings get_balance failed: {error_msg}")
            return {'success': False, 'error': error_msg}
            
    # 5. إلغاء طلب واحد
    def cancel_order(self, order_id):
        """إلغاء طلب معين (يجب أن يكون الطلب جديدًا وقابلاً للإلغاء)."""
        # API SMMKings تتوقع قائمة من الطلبات
        params = {
            'action': 'cancel',
            'orders': str(order_id)
        }
        response = self._make_request(params)
        
        # مثال على الاستجابة: [{"order": 2, "cancel": 1}]
        if isinstance(response, list) and response:
            result = response[0]
            if result.get('order') == int(order_id) and isinstance(result.get('cancel'), int):
                return {'success': True, 'cancel_id': result['cancel']}
            elif isinstance(result.get('cancel'), dict) and 'error' in result['cancel']:
                 return {'success': False, 'error': result['cancel']['error']}

        return {'success': False, 'error': 'CANCEL_UNEXPECTED_RESPONSE'}
        
