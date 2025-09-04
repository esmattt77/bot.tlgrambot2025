import requests
import json
import os

API_KEY = os.environ.get('TIGER_SMS_API_KEY')
BASE_URL = 'https://api.tiger-sms.com/stubs/handler_api.php'

class TigerSMSAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        
    def _make_request(self, params):
        params['api_key'] = self.api_key
        try:
            response = requests.get(BASE_URL, params=params)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            return f"ERROR: API request failed - {e}"

    def get_balance(self):
        params = {'action': 'getBalance'}
        response = self._make_request(params)
        if response.startswith('ACCESS_BALANCE:'):
            balance = response.split(':')[1].strip()
            return {'success': True, 'balance': float(balance)}
        else:
            return {'success': False, 'error': response}

    def get_services(self):
        params = {'action': 'getPrices'}
        response = self._make_request(params)
        if response.startswith('ERROR'):
            return {'success': False, 'error': response}
        try:
            data = json.loads(response)
            services = {}
            for service_name, countries in data.items():
                service_id = self._get_service_id(service_name)
                if service_id:
                    services[service_id] = {'name': service_name, 'countries': countries}
            return {'success': True, 'data': services}
        except json.JSONDecodeError:
            return {'success': False, 'error': 'Invalid JSON response from API'}

    def get_countries(self, service_id):
        service_name = self._get_service_name(service_id)
        params = {'action': 'getPrices', 'service': service_name}
        response = self._make_request(params)
        if response.startswith('ERROR'):
            return {}
        try:
            data = json.loads(response)
            if service_name in data:
                countries = {}
                for country_id, country_info in data[service_name].items():
                    countries[country_id] = {
                        'name': self._get_country_name(country_id),
                        'price': country_info.get('price'),
                        'count': country_info.get('phones')
                    }
                return countries
            return {}
        except json.JSONDecodeError:
            return {}

    def get_number(self, service_id, country_id):
        service_name = self._get_service_name(service_id)
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
            return {'success': False, 'error': response}
            
    def get_code(self, request_id):
        params = {
            'action': 'getStatus',
            'id': request_id
        }
        response = self._make_request(params)
        if response.startswith('STATUS_OK:'):
            code = response.split(':')[1].strip()
            return {'success': True, 'code': code}
        elif response == 'STATUS_WAIT_CODE':
            return {'success': False, 'status': 'waiting'}
        else:
            return {'success': False, 'error': response}

    def cancel_request(self, request_id):
        params = {
            'action': 'setStatus',
            'id': request_id,
            'status': 8
        }
        response = self._make_request(params)
        if response == 'ACCESS_CANCEL':
            return {'success': True}
        else:
            return {'success': False, 'error': response}

    def _get_country_name(self, country_id):
        countries = {
            '74': 'Afghanistan', '155': 'Albania', '58': 'Algeria', '76': 'Angola', '181': 'Anguilla',
            '169': 'Antigua and Barbuda', '39': 'Argentinas', '148': 'Armenia', '179': 'Aruba', '175': 'Australia',
            '50': 'Austria', '35': 'Azerbaijan', '122': 'Bahamas', '145': 'Bahrain', '60': 'Bangladesh',
            '118': 'Barbados', '51': 'Belarus', '82': 'Belgium', '124': 'Belize', '120': 'Benin',
            '195': 'Bermuda', '158': 'Bhutan', '92': 'Bolivia', '108': 'Bosnia and Herzegovina', '123': 'Botswana',
            '73': 'Brazil', '121': 'Brunei Darussalam', '83': 'Bulgaria', '152': 'Burkina Faso', '119': 'Burundi',
            '24': 'Cambodia', '41': 'Cameroon', '36': 'Canada', '186': 'Cape Verde', '170': 'Cayman islands',
            '125': 'Central African Republic', '42': 'Chad', '151': 'Chile', '3': 'China', '33': 'Colombia',
            '133': 'Comoros', '150': 'Congo', '18': 'Congo (Dem. Republic)', '93': 'Costa Rica', '27': "Cote d'Ivoire/Ivory Coast",
            '45': 'Croatia', '113': 'Cuba', '77': 'Cyprus', '63': 'Czech Republic', '172': 'Denmark',
            '168': 'Djibouti', '126': 'Dominica', '109': 'Dominican Republic', '105': 'Ecuador', '21': 'Egypt',
            '101': 'El Salvador', '167': 'Equatorial Guinea', '176': 'Eritrea', '34': 'Estonia', '71': 'Ethiopia',
            '189': 'Fiji', '163': 'Finland', '78': 'France', '162': 'French Guiana', '154': 'Gabon',
            '28': 'Gambia', '128': 'Georgia', '43': 'Germany', '38': 'Ghana', '201': 'Gibraltar',
            '129': 'Greece', '127': 'Grenada', '160': 'Guadeloupe', '94': 'Guatemala', '68': 'Guinea',
            '130': 'Guinea-Bissau', '131': 'Guyana', '26': 'Haiti', '88': 'Honduras', '14': 'Hong Kong',
            '84': 'Hungary', '132': 'Iceland', '22': 'India', '6': 'Indonesia', '57': 'Iran',
            '47': 'Iraq', '23': 'Ireland', '13': 'Israel', '86': 'Italy', '103': 'Jamaica',
            '182': 'Japan', '116': 'Jordan', '2': 'Kazakhstan', '8': 'Kenya', '190': 'Korea',
            '203': 'Kosovo', '100': 'Kuwait', '11': 'Kyrgyzstan', '25': "Lao People's", '49': 'Latvia',
            '153': 'Lebanon', '136': 'Lesotho', '135': 'Liberia', '102': 'Libya', '44': 'Lithuania',
            '165': 'Luxembourg', '20': 'Macau', '183': 'Macedonia', '17': 'Madagascar', '137': 'Malawi',
            '7': 'Malaysia', '159': 'Maldives', '69': 'Mali', '199': 'Malta', '114': 'Mauritania',
            '157': 'Mauritius', '54': 'Mexico', '85': 'Moldova, Republic of', '144': 'Monaco', '72': 'Mongolia',
            '171': 'Montenegro', '180': 'Montserrat', '37': 'Morocco', '80': 'Mozambique', '5': 'Myanmar',
            '138': 'Nambia', '81': 'Nepal', '48': 'Netherlands', '185': 'New Caledonia', '67': 'New Zealand',
            '90': 'Nicaragua', '139': 'Niger', '19': 'Nigeria', '174': 'Norway', '107': 'Oman',
            '66': 'Pakistan', '188': 'Palestine', '112': 'Panama', '79': 'Papua new gvineya', '87': 'Paraguay',
            '65': 'Peru', '4': 'Philippines', '15': 'Poland', '117': 'Portugal', '97': 'Puerto Rico',
            '111': 'Qatar', '146': 'Reunion', '32': 'Romania', '140': 'Rwanda', '134': 'Saint Kitts and Nevis',
            '164': 'Saint Lucia', '166': 'Saint Vincent', '198': 'Samoa', '178': 'Sao Tome and Principe',
            '53': 'Saudi Arabia', '61': 'Senegal', '29': 'Serbia', '184': 'Seychelles', '115': 'Sierra Leone',
            '196': 'Singapore', '141': 'Slovakia', '59': 'Slovenia', '193': 'Solomon Islands', '149': 'Somalia',
            '31': 'South Africa', '177': 'South Sudan', '56': 'Spain', '64': 'Sri Lanka', '98': 'Sudan',
            '142': 'Suriname', '106': 'Swaziland', '46': 'Sweden', '173': 'Switzerland', '110': 'Syrian Arab Republic',
            '55': 'Taiwan', '143': 'Tajikistan', '9': 'Tanzania', '52': 'Thailand', '91': 'Timor-Leste',
            '99': 'Togo', '197': 'Tonga', '104': 'Trinidad and Tobago', '89': 'Tunisia', '62': 'Turkey',
            '161': 'Turkmenistan', '75': 'Uganda', '1': 'Ukraine', '95': 'United Arab Emirates', '16': 'United Kingdom',
            '187': 'United States', '1001': 'United States VIP', '12': 'United States virt', '156': 'Uruguay',
            '40': 'Uzbekistan', '70': 'Venezuela', '10': 'Viet nam', '30': 'Yemen', '96': 'Zimbabwe',
        }
        return countries.get(str(country_id), 'Unknown')
        
    def _get_service_id(self, service_name):
        services = {
            "telegram": "tg", "whatsapp": "wa", "instagram": "ig", "facebook": "fb",
            "twitter": "tw", "google": "go", "imo": "im", "tiktok": "tk",
            "vk": "vk", "ok": "ok", "wechat": "wb", "viber": "vi", "olx": "ol",
            "avito": "av", "youla": "yl", "yandex": "ya", "uber": "ub", "avito": "av",
            "blablacar": "bl", "badoo": "bd", "snapchat": "sn", "gismeteo": "gm",
            "craigslist": "cl", "didi": "di", "alipay": "ap", "kvartplata": "kv",
            "line": "li", "mamba": "mb", "mail.ru": "ml", "microsoft": "mc",
            "discord": "ds", "tinder": "td", "other": "ot", "hamrahaval": "hm",
            "ebay": "eb", "linkedin": "ln", "twitch": "tc", "aliexpress": "al",
            "jd": "jd", "paltalk": "pt", "steam": "st", "signal": "si", "sberbank": "sb",
            "qiwi": "qw", "webmoney": "wm", "skout": "sk", "meetme": "mm",
            "mega": "mg", "airbnb": "ab", "ssoid": "so", "paypal": "pp", "garena": "ga",
            "kakaotalk": "kt", "paxful": "px", "zomato": "zm", "drom": "dr",
            "kufar": "kf", "wildberries": "wb" # Added vk to the mapping based on common use
        }
        return services.get(service_name)
    
    def _get_service_name(self, service_id):
        services = {
            "tg": "telegram", "wa": "whatsapp", "ig": "instagram", "fb": "facebook",
            "tw": "twitter", "go": "google", "im": "imo", "tk": "tiktok",
            "vk": "vk", "ok": "ok", "wb": "wechat", "vi": "viber", "ol": "olx",
            "av": "avito", "yl": "youla", "ya": "yandex", "ub": "uber", "av": "avito",
            "bl": "blablacar", "bd": "badoo", "sn": "snapchat", "gm": "gismeteo",
            "cl": "craigslist", "di": "didi", "ap": "alipay", "kv": "kvartplata",
            "li": "line", "mb": "mamba", "ml": "mail.ru", "mc": "microsoft",
            "ds": "discord", "td": "tinder", "ot": "other", "hm": "hamrahaval",
            "eb": "ebay", "ln": "linkedin", "tc": "twitch", "al": "aliexpress",
            "jd": "jd", "pt": "paltalk", "st": "steam", "si": "signal", "sb": "sberbank",
            "qw": "qiwi", "wm": "webmoney", "sk": "skout", "mm": "meetme",
            "mg": "mega", "ab": "airbnb", "so": "ssoid", "pp": "paypal", "ga": "garena",
            "kt": "kakaotalk", "px": "paxful", "zm": "zomato", "dr": "drom",
            "kf": "kufar", "wb": "wildberries"
        }
        return services.get(service_id)
