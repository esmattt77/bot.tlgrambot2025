import json
import requests
import os

# Get API key from environment variables
SMSMAN_API_KEY = os.environ.get('SMSMAN_API_KEY')
BASE_URL = "https://api.sms-man.com/stubs/handler_api.php"

class SmsManApi:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.sms-man.com/stubs/handler_api.php"
        self.service_map = {
            '2': 'wa', '3': 'tg', '4': 'fb', '5': 'ig', '6': 'tw', '7': 'tt',
            '8': 'gl', '9': 'im', '11': 'sn', '13': 'hr', '14': 'ot'
        }
        self.country_map = {
            "49": "لاتفيا 🇱🇻", "21": "مصر 🇪🇬", "50": "النمسا 🇦🇹", "6": "إندونيسيا 🇮🇩",
            "24": "كمبوديا 🇰🇭", "77": "قبرص 🇨🇾", "84": "المجر 🇭🇺", "175": "استراليا 🇦🇺",
            "32": "رومانيا 🇷🇴", "35": "أذربيجان 🇦🇿", "185": "كاليدونيا 🇳🇨", "70": "فنزويلا 🇻🇪",
            "54": "المكسيك 🇲🇽", "88": "هندوراس 🇭🇳", "80": "موزمبيق 🇲🇿", "140": "رواندا 🇷🇼",
            "137": "ملاوي 🇲🇼", "76": "انغولا 🇦🇴", "19": "نيجيريا 🇳🇬", "69": "مالي 🇲🇱",
            "71": "إثيوبيا 🇪🇹", "27": "ساحل العاج 🇨🇮", "61": "السنغال 🇸🇳", "102": "ليبيا 🇱🇾",
            "99": "توجو 🇹🇬", "98": "السودان 🇸🇩", "133": "جزر القمر 🇰🇲", "58": "الجزائر 🇩🇿",
            "89": "تونس 🇹🇳", "114": "موريتانيا 🇲🇷", "31": "جنوب افريقيا 🇿🇦", "143": "طاجيكستان 🇹🇯",
            "158": "بوتان 🇧🇹", "128": "جورجيا 🇬🇪", "57": "إيران 🇮🇷", "25": "لاوس 🇱🇦",
            "66": "باكستان 🇵🇰", "60": "بنغلاديش 🇧🇩", "0": "روسيا 🇷🇺", "1": "أوكرانيا 🇺🇦",
            "3": "الصين 🇨🇳", "4": "الفلبين 🇵🇭", "5": "ميانمار 🇲🇲", "7": "ماليزيا 🇲🇾",
            "8": "كينيا 🇰🇪", "9": "تنزانيا 🇹🇿", "10": "فيتنام 🇻🇳", "11": "قيرغيزستان 🇰🇬",
            "14": "هونغ كونغ 🇭🇰", "15": "بولندا 🇵🇱", "20": "ماكاو 🇲🇴", "17": "مدغشقر 🇲🇬",
            "22": "الهند 🇮🇳", "23": "أيرلندا 🇮🇪", "26": "هايتي 🇭🇹", "30": "اليمن 🇾🇪",
            "33": "كولومبيا 🇨🇴", "36": "كندا 🇨🇦", "37": "المغرب 🇲🇦", "39": "الأرجنتين 🇦🇷",
            "38": "غانا 🇬🇭", "42": "تشاد 🇹🇩", "47": "العراق 🇮🇶", "44": "ليتوانيا 🇱🇹",
            "45": "كرواتيا 🇭🇷", "46": "السويد 🇸🇪", "53": "السعودية 🇸🇦", "52": "تايلاند 🇹🇭",
            "55": "تايوان 🇹🇼", "56": "اسبانيا 🇪🇸", "62": "تركيا 🇹🇷", "59": "سلوفينيا 🇸🇮",
            "63": "التشيك 🇨🇿", "64": "سريلانكا 🇱🇰", "65": "بيرو 🇵🇪", "67": "نيوزيلندا 🇳🇿",
            "68": "غينيا 🇬🇳", "72": "منغوليا 🇲🇳", "73": "البرازيل 🇧🇷", "74": "أفغانستان 🇦🇫",
            "75": "أوغندا 🇺🇬", "78": "فرنسا 🇫🇷", "82": "بلجيكا 🇧🇪", "81": "النيبال 🇳🇵",
            "83": "بلغاريا 🇧🇬", "86": "إيطاليا 🇮🇹", "87": "باراغواي 🇵🇾", "91": "تيمور 🇹🇱",
            "93": "كوستاريكا 🇨🇷", "95": "الإمارات 🇦🇪", "92": "بوليفيا 🇧🇴", "96": "زيمبابوي 🇿🇼",
            "100": "الكويت 🇰🇼", "101": "سلفادور 🇸🇻", "105": "الإكوادور 🇪🇨", "107": "عمان 🇴🇲",
            "110": "سوريا 🇸🇾", "111": "قطر 🇶🇦", "112": "بنما 🇵🇦", "113": "كوبا 🇨🇺",
            "115": "سيراليون 🇸🇱", "116": "الأردن 🇯🇴", "117": "البرتغال 🇵🇹", "120": "بنين 🇧🇯",
            "124": "بليز 🇧🇿", "129": "اليونان 🇬🇷", "145": "البحرين 🇧🇭", "135": "ليبيريا 🇱🇷",
            "187": "أمريكا 🇺🇸", "182": "اليابان 🇯🇵", "177": "جنوب السودان 🇸🇸", "174": "النرويج 🇳🇴",
            "173": "سويسرا 🇨🇭", "169": "أيسلندا 🇮🇸", "167": "غينيا الأستوائية 🇬🇶", "166": "لوكسمبورغ 🇱🇺",
            "165": "مونتسيرات 🇲🇸", "164": "أنغويلا 🇦🇮", "163": "فنلندا 🇫🇮", "162": "غويانا الفرنسية 🇬🇫",
            "161": "تركمانستان 🇹🇲", "160": "جوادلوب 🇬🇵", "159": "المالديف 🇲🇻", "157": "موريشيوس 🇲🇺",
            "156": "اوروغواي 🇺🇾", "155": "ألبانيا 🇦🇱", "154": "الغابون 🇬🇦", "153": "لبنان 🇱🇧",
            "152": "بوركينا فاسو 🇧🇫", "186": "كيريباتي 🇰🇮", "151": "تشيلي 🇨🇱", "150": "الكونغو 🇨🇬",
            "149": "الصومال 🇸🇴", "148": "أرمينيا 🇦🇲", "141": "رواندا 🇷🇼",
        }

    def _api_call(self, action, params=None):
        if params is None:
            params = {}
        params['action'] = action
        params['api_key'] = self.api_key
        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"Error making SMS-Man API call: {e}")
            return 'ERROR_REQUEST_FAILED'

    def get_balance(self):
        response = self._api_call('getBalance')
        if response == 'ERROR_REQUEST_FAILED':
            return {"success": False, "message": "Failed to connect to API"}
            
        if response.startswith('ACCESS_BALANCE:'):
            try:
                balance = float(response.split(':')[1])
                return {"success": True, "balance": balance}
            except (ValueError, IndexError):
                print("Error parsing SMS-Man balance response.")
                return {"success": False, "message": "Error parsing API response"}
        return {"success": False, "message": response}

    def get_countries(self):
        try:
            response_json = self._api_call('getPrices')
            if response_json == 'ERROR_REQUEST_FAILED':
                return {"success": False, "message": "Failed to connect to API"}
            
            data = json.loads(response_json)
            countries_data = []
            
            for country_id, services in data.items():
                total_count = sum(int(s.get('count', 0)) for s in services.values())
                if total_count > 0:
                    country_name = self.country_map.get(country_id, f"غير معروف ({country_id})")
                    countries_data.append({
                        'id': country_id,
                        'name': country_name,
                        'count': total_count
                    })
            return {"success": True, "data": countries_data}
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing SMS-Man countries JSON: {e}")
            return {"success": False, "message": "Error parsing countries data"}
    
    def get_applications(self, country_id):
        try:
            response_json = self._api_call('getPrices', {'country': country_id})
            if response_json == 'ERROR_REQUEST_FAILED':
                return {"success": False, "message": "Failed to connect to API"}
            
            data = json.loads(response_json)
            applications_data = []

            if country_id in data:
                for service_name, service_info in data[country_id].items():
                    # Find our mapped service ID from the service_name
                    service_id = next((k for k, v in self.service_map.items() if v == service_name), None)
                    if service_id and float(service_info['cost']) > 0 and int(service_info['count']) > 0:
                        applications_data.append({
                            'id': service_id,
                            'name': service_name,
                            'price': float(service_info['cost']),
                            'count': int(service_info['count'])
                        })
            
            return {"success": True, "data": applications_data}
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing SMS-Man services JSON: {e}")
            return {"success": False, "message": "Error parsing services data"}

    def request_smsman_number(self, service_id, country_id):
        service_name = self.service_map.get(str(service_id))
        if not service_name:
            return {"success": False, "message": "Service not found"}

        response = self._api_call('getNumber', {
            'service': service_name,
            'country': country_id,
        })
        
        if response.startswith('ACCESS_NUMBER:'):
            parts = response.split(':')
            return {
                'success': True,
                'request_id': parts[1],
                'number': parts[2],
            }
        return {"success": False, "message": response}

    def get_smsman_code(self, request_id):
        response = self._api_call('getStatus', {'id': request_id})
        
        if response == 'ERROR_REQUEST_FAILED':
            return {"success": False, "message": "Failed to connect to API"}

        if response.startswith('STATUS_OK:'):
            code = response.split(':')[1]
            return {"success": True, "data": {"code": code}}
        elif response == 'STATUS_WAIT_CODE':
            return {"success": False, "data": "Pending"}
        elif response == 'STATUS_CANCEL':
            return {"success": False, "data": "Cancelled"}
        elif response == 'STATUS_WAIT_RETRY':
            return {"success": False, "data": "Waiting for retry"}
        
        return {"success": False, "data": response}

    def cancel_smsman_request(self, request_id):
        response = self._api_call('setStatus', {'id': request_id, 'status': -1})
        
        if response == 'ERROR_REQUEST_FAILED':
            return {"success": False, "message": "Failed to connect to API"}
            
        if response == 'STATUS_CANCEL':
            return {"success": True, "message": "CANCELED"}
        return {"success": False, "message": response}

    def get_full_services(self, country_id):
        try:
            response_json = self._api_call('getPrices', {'country': country_id})
            if response_json == 'ERROR_REQUEST_FAILED':
                return {"success": False, "message": "Failed to connect to API"}
            
            data = json.loads(response_json)
            if not data:
                return {"success": True, "data": []}

            # Return the raw data for the specified country
            return {"success": True, "data": data.get(country_id, {})}
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing SMS-Man services JSON: {e}")
            return {"success": False, "message": "Error parsing services data"}
