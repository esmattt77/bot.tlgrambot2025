import requests
import json
import os
import logging

# إعداد logging لطباعة الأخطاء في السجل
logger = logging.getLogger(__name__)

# تأكد أن المتغير البيئي مضبوط (HERO_SMS_API_KEY)
API_KEY = os.environ.get('HERO_SMS_API_KEY')
BASE_URL = 'https://hero-sms.com/stubs/handler_api.php'

class HeroSMSAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        
    def _make_request(self, params):
        params['api_key'] = self.api_key
        try:
            # إضافة timeout لتجنب التعليق
            response = requests.get(BASE_URL, params=params, timeout=10) 
            response.raise_for_status() # رفع استثناء لأخطاء HTTP 4xx/5xx
            return response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"HERO SMS API request failed with error: {e}, Params: {params}")
            return f"ERROR: API request failed - {e}"

    def get_balance(self):
        params = {'action': 'getBalance'}
        response = self._make_request(params)
        if response.startswith('ACCESS_BALANCE:'):
            balance = response.split(':')[1].strip()
            return {'success': True, 'balance': float(balance)}
        else:
            return {'success': False, 'error': response}

    def get_countries(self, service_name):
        params = {'action': 'getPrices'}
        response = self._make_request(params)
        if response.startswith('ERROR'):
            logger.error(f"HERO SMS getPrices failed: {response}")
            return {}
        try:
            # الاستجابة هي JSON لـ getPrices
            data = json.loads(response)
            countries = {}
            for country_id, services_info in data.items():
                if service_name in services_info and services_info[service_name].get('count', 0) > 0:
                    countries[country_id] = {
                        'name': self._get_country_name(country_id),
                        'price': services_info[service_name].get('cost'),
                        'count': services_info[service_name].get('count')
                    }
            return countries
        except json.JSONDecodeError:
            logger.error(f"HERO SMS failed to decode JSON from getPrices: {response}")
            return {}

    def get_number(self, service_name, country_id):
        params = {
            'action': 'getNumber',
            'service': service_name,
            'country': country_id
        }
        response = self._make_request(params)
        
        if response.startswith('ACCESS_NUMBER:'):
            parts = response.split(':')
            request_id = parts[1].strip()
            phone_number = parts[2].strip()
            return {'success': True, 'id': request_id, 'number': phone_number}
        else:
            logger.warning(f"HERO SMS getNumber failed: {response}")
            return {'success': False, 'error': response}
            
    def get_code(self, request_id):
        params = {
            'action': 'getStatus',
            'id': request_id
        }
        response = self._make_request(params)
        
        if response.startswith('STATUS_OK:'):
            code = response.split(':')[1].strip()
            return {'success': True, 'code': code, 'status': 'received'}
        elif response == 'STATUS_WAIT_CODE':
            return {'success': False, 'status': 'waiting'}
        elif response == 'STATUS_CANCEL' or response == 'STATUS_FREE':
            return {'success': False, 'status': 'cancelled', 'error': response}
        elif response.startswith('ERROR'):
            return {'success': False, 'status': 'error', 'error': response}
        else:
            return {'success': False, 'status': 'unknown', 'error': response}

    def set_status(self, request_id, status_code):
        """
        لتغيير حالة الطلب على Hero SMS.
        status_code = 3 لتأكيد استلام الكود (انتهاء العملية).
        status_code = 8 لإلغاء الطلب (استرداد المبلغ).
        """
        params = {
            'action': 'setStatus',
            'id': request_id,
            'status': status_code
        }
        response = self._make_request(params)
        
        if response == 'ACCESS_READY' or response == 'ACCESS_CANCEL': 
            return {'success': True, 'response': response}
        else:
            logger.error(f"HERO SMS set_status failed for ID {request_id} with status {status_code}, Response: {response}")
            return {'success': False, 'error': response}

    def confirm_request(self, request_id):
        return self.set_status(request_id, 3)

    def cancel_request(self, request_id):
        return self.set_status(request_id, 8) 
        
    def _get_country_name(self, country_id):
        countries = {
            '74': 'أفغانستان 🇦🇫', '155': 'ألبانيا 🇦🇱', '58': 'الجزائر 🇩🇿', '76': 'أنغولا 🇦🇴', '181': 'أنغويلا 🇦🇮',
            '169': 'أنتيجواباربودا 🇦🇬', '39': 'الأرجنتين 🇦🇷', '148': 'أرمينيا 🇦🇲', '179': 'اروبا 🇦🇼', '175': 'استراليا 🇦🇺',
            '50': 'النمسا 🇦🇹', '35': 'أذربيجان 🇦🇿', '122': 'جزر البهاما 🇧🇸', '145': 'البحرين 🇧🇭', '60': 'بنغلاديش 🇧🇩',
            '118': 'بربادوس 🇧🇧', '51': 'بيلاروسيا 🇧🇾', '82': 'بلجيكا 🇧🇪', '124': 'بليز 🇧🇿', '120': 'بنين 🇧🇯',
            '195': 'برمودا 🇧🇲', '158': 'بوتان 🇧🇹', '92': 'بوليفيا 🇧🇴', '108': 'البوسنة 🇧🇦', '123': 'بوتسوانا 🇧🇼',
            '73': 'البرازيل 🇧🇷', '121': 'بروناي 🇧🇳', '83': 'بلغاريا 🇧🇬', '152': 'بوركينا فاسو 🇧🇫', '119': 'بوروندي 🇧🇮',
            '24': 'كمبوديا 🇰🇭', '41': 'الكاميرون 🇨🇲', '36': 'كندا 🇨🇦', '186': 'الرأس الأخضر 🇨🇻', '170': 'جزر كايمان 🇰🇾',
            '125': 'إفريقيا الوسطى 🇨🇫', '42': 'تشاد 🇹🇩', '151': 'تشيلي 🇨🇱', '3': 'الصين 🇨🇳', '33': 'كولومبيا 🇨🇴',
            '133': 'جزر القمر 🇰🇲', '150': 'الكونغو 🇨🇬', '18': 'ديم الكونغو 🇨🇩', '93': 'كوستاريكا 🇨🇷', '27': 'ساحل العاج 🇨🇮',
            '45': 'كرواتيا 🇭🇷', '113': 'كوبا 🇨🇺', '77': 'قبرص 🇨🇾', '63': 'التشيك 🇨🇿', '172': 'الدنمارك 🇩🇰',
            '168': 'جيبوتي 🇩🇯', '126': 'دومينيكا 🇩🇲', '109': 'الدومينيكان 🇩🇴', '105': 'الاكوادور 🇪🇨', '21': 'مصر 🇪🇬',
            '101': 'سلفادور 🇸🇻', '167': 'غينيا الأستوائية 🇬🇶', '176': 'إريتريا 🇪🇷', '34': 'إستونيا 🇪🇪', '71': 'إثيوبيا 🇪🇹',
            '189': 'فيجي 🇫🇯', '163': 'فنلندا 🇫🇮', '78': 'فرنسا 🇫🇷', '162': 'غويانا الفرنسية 🇬🇫', '154': 'الغابون 🇬🇦',
            '28': 'غامبيا 🇬🇲', '128': 'جورجيا 🇬🇪', '43': 'المانيا 🇩🇪', '38': 'غانا 🇬🇭', '201': 'جبل طارق 🇬🇮',
            '129': 'اليونان 🇬🇷', '127': 'غرينادا 🇬🇩', '160': 'جوادلوب 🇬🇵', '94': 'غواتيمالا 🇬🇹', '68': 'غينيا 🇬🇳',
            '130': 'غينيا بيساو 🇬🇼', '131': 'غيانا 🇬🇾', '26': 'هايتي 🇭🇹', '88': 'هندوراس 🇭🇳', '14': 'هونغ كونغ 🇭🇰',
            '84': 'هنغاريا 🇭🇺', '132': 'أيسلندا 🇮🇸', '22': 'الهند 🇮🇳', '6': 'إندونيسيا 🇮🇩', '57': 'إيران 🇮🇷',
            '47': 'العراق 🇮🇶', '23': 'أيرلندا 🇮🇪', '13': 'إسرائيل 🇮🇱', '86': 'إيطاليا 🇮🇹', '103': 'جامايكا 🇯🇲',
            '182': 'اليابان 🇯🇵', '116': 'الأردن 🇯🇴', '2': 'كازاخستان 🇰🇿', '8': 'كينيا 🇰🇪', '190': 'كوريا الجنوبية 🇰🇷',
            '203': 'كوسوفو 🇽🇰', '100': 'الكويت 🇰🇼', '11': 'قيرغيزستان 🇰🇬', '25': 'لاوس 🇱🇦', '49': 'لاتفيا 🇱🇻',
            '153': 'لبنان 🇱🇧', '136': 'ليسوتو 🇱🇸', '135': 'ليبيريا 🇱🇷', '102': 'ليبيا 🇱🇾', '44': 'ليتوانيا 🇱🇹',
            '165': 'لوكسمبورغ 🇱🇺', '20': 'ماكاو 🇲🇴', '183': 'شمال مقدونيا 🇲🇰', '17': 'مدغشقر 🇲🇬', '137': 'ملاوي 🇲🇼',
            '7': 'ماليزيا 🇲🇾', '159': 'المالديف 🇲🇻', '69': 'مالي 🇲🇱', '199': 'مالطا 🇲🇹', '114': 'موريتانيا 🇲🇷',
            '157': 'موريشيوس 🇲🇺', '54': 'المكسيك 🇲🇽', '85': 'مولدوفا 🇲🇩', '144': 'موناكو 🇲🇨', '72': 'منغوليا 🇲🇳',
            '171': 'الجبل الأسود 🇲🇪', '180': 'مونتسيرات 🇲🇸', '37': 'المغرب 🇲🇦', '80': 'موزمبيق 🇲🇿', '5': 'ميانمار 🇲🇲',
            '138': 'ناميبيا 🇳🇦', '81': 'نيبال 🇳🇵', '48': 'هولندا 🇳🇱', '185': 'كاليدونيا 🇳🇨', '67': 'نيوزيلندا 🇳🇿',
            '90': 'نيكاراغوا 🇳🇮', '139': 'النيجر 🇳🇪', '19': 'نيجيريا 🇬🇳', '174': 'النرويج 🇳🇴', '107': 'عمان 🇴🇲',
            '66': 'باكستان 🇵🇰', '188': 'فلسطين 🇵🇸', '112': 'بنما 🇵🇦', '79': 'بابو 🇵🇬', '87': 'باراغواي 🇵🇾',
            '65': 'بيرو 🇵🇪', '4': 'الفلبين 🇵🇭', '15': 'بولندا 🇵🇱', '117': 'البرتغال 🇵🇹', '97': 'بورتوريكو 🇵🇷',
            '111': 'قطر 🇶🇦', '146': 'جمع-شمل 🇫🇷', '32': 'رومانيا 🇷🇴', '0': 'روسيا 🇷🇺', '140': 'رواندا 🇷🇼',
            '134': 'سانتكيتس 🇰🇳', '164': 'لوسيا 🇱🇨', '166': 'جزر غرينادين 🇻🇨', '198': 'ساموا 🇼🇸', '178': 'برينسيبي 🇸🇹',
            '53': 'السعودية 🇸🇦', '61': 'السنغال 🇸🇳', '29': 'صربيا 🇷🇸', '184': 'سيشيل 🇸🇨', '115': 'سيراليون 🇸🇱',
            '196': 'سنغافورة 🇸🇬', '141': 'سلوفاكيا 🇸🇰', '59': 'سلوفينيا 🇸🇮', '193': 'جزر سليمان 🇸🇧', '149': 'الصومال 🇸🇴',
            '31': 'جنوب إفريقيا 🇿🇦', '177': 'جنوب السودان 🇸🇸', '56': 'اسبانيا 🇪🇸', '64': 'سريلانكا 🇱🇰', '98': 'السودان 🇸🇩',
            '142': 'سورينام 🇸🇷', '106': 'سوازيلاند 🇸🇿', '46': 'السويد 🇸🇪', '173': 'سويسرا 🇨🇭', '110': 'سوريا 🇸🇾',
            '55': 'تايوان 🇹🇼', '143': 'طاجيكستان 🇹🇯', '9': 'تنزانيا 🇹🇿', '52': 'تايلاند 🇹🇭', '91': 'تيمور 🇹🇱',
            '99': 'توجو 🇹🇬', '197': 'تونغا 🇹🇴', '104': 'ترينيداد 🇹🇹', '89': 'تونس 🇹🇳', '62': 'تركيا 🇹🇷',
            '161': 'تركمانستان 🇹🇲', '75': 'أوغندا 🇺🇬', '1': 'أوكرانيا 🇺🇦', '95': 'الإمارات 🇦🇪', '16': 'بريطانيا 🇬🇧',
            '187': 'أمريكا 🇺🇸', '1001': 'أمريكا VIP', '12': 'أمريكا افتراضي', '156': 'اوروغواي 🇺🇾', '40': 'أوزبكستان 🇺🇿',
            '70': 'فنزويلا 🇻🇪', '10': 'فيتنام 🇻🇳', '30': 'اليمن 🇾🇪', '147': 'زامبيا 🇿🇲', '96': 'زيمبابوي 🇿🇼'
        }
        return countries.get(str(country_id), 'غير معروف')
