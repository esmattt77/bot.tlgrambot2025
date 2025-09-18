# smsman_api.py
import json
import requests
import os

# Get SMSMAN_API_KEY from environment variables
SMSMAN_API_KEY = os.environ.get('SMSMAN_API_KEY')

# A dictionary to map SMS-Man internal codes to country names and flags
smsman_country_map = {
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

# Mapping our app IDs to SMS-Man service names
service_map = {
    '2': 'wa', '3': 'tg', '4': 'fb', '5': 'ig', '6': 'tw', '7': 'tt',
    '8': 'gl', '9': 'im', '11': 'sn', '13': 'hr', '14': 'ot'
}

BASE_URL = "https://api.sms-man.com/stubs/handler_api.php"

def smsman_api_call(action, params=None):
    if params is None:
        params = {}
    params['action'] = action
    params['api_key'] = SMSMAN_API_KEY
    try:
        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error making SMS-Man API call: {e}")
        return 'ERROR_REQUEST_FAILED'

def get_smsman_balance():
    response = smsman_api_call('getBalance')
    if response == 'ERROR_REQUEST_FAILED':
        return {'success': False, 'error': 'Request to API failed.'}
        
    if response.startswith('ACCESS_BALANCE:'):
        try:
            balance = float(response.split(':')[1])
            return {'success': True, 'balance': balance}
        except (ValueError, IndexError):
            print("Error parsing SMS-Man balance response.")
            return {'success': False, 'error': 'Error parsing balance response.'}
    return {'success': False, 'error': response}

def request_smsman_number(service_id, country_code):
    service_name = service_map.get(str(service_id))
    if not service_name:
        return {'success': False, 'error': 'Service name not found.'}

    response = smsman_api_call('getNumber', {
        'service': service_name,
        'country': country_code,
    })

    if response == 'ERROR_REQUEST_FAILED':
        return {'success': False, 'error': 'Request to API failed.'}

    if not response.startswith('ACCESS_NUMBER:'):
        return {'success': False, 'error': response}

    try:
        parts = response.split(':')
        request_id = parts[1]
        phone_number = parts[2]
        return {
            'success': True,
            'id': request_id,
            'number': phone_number,
        }
    except (ValueError, IndexError):
        return {'success': False, 'error': 'Failed to parse API response.'}

def get_smsman_code(request_id):
    response = smsman_api_call('getStatus', {'id': request_id})
    
    if response == 'ERROR_REQUEST_FAILED':
        return {'success': False, 'error': 'Request to API failed.'}

    if response.startswith('STATUS_OK:'):
        code = response.split(':')[1]
        return {'success': True, 'code': code}
    elif response == 'STATUS_WAIT_CODE':
        return {'success': False, 'status': 'pending'}

    return {'success': False, 'error': response}

def cancel_smsman_number(request_id):
    response = smsman_api_call('setStatus', {'id': request_id, 'status': -1})

    if response == 'ERROR_REQUEST_FAILED':
        return {'success': False, 'error': 'Request to API failed.'}
        
    if response == 'STATUS_CANCEL':
        return {'success': True}
    return {'success': False, 'error': response}
    
def get_smsman_countries(app_id):
    service_name = service_map.get(str(app_id))
    if not service_name:
        return {'success': False, 'error': 'Service not found.'}

    response_json = smsman_api_call('getPrices', {'service': service_name})
    
    if response_json == 'ERROR_REQUEST_FAILED':
        return {'success': False, 'error': 'Request to API failed.'}
    
    try:
        data = json.loads(response_json)
        # The API returns an error message as a string if there's an issue
        if isinstance(data, str):
             return {'success': False, 'error': data}
        
        countries_data = {}
        for country_code, services in data.get('price', {}).items():
            if service_name in services:
                service_info = services[service_name]
                if service_info['count'] > 0:
                    country_display_name = smsman_country_map.get(country_code, f"غير معروف ({country_code})")
                    
                    countries_data[country_code] = {
                        'name': country_display_name,
                        'price': float(service_info['price']),
                        'count': int(service_info['count'])
                    }

        return {'success': True, 'countries': countries_data}
    
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        print(f"Error parsing SMS-Man JSON response: {e}")
        return {'success': False, 'error': f"Failed to parse API response: {e}"}

