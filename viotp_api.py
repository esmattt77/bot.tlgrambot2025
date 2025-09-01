# viotp_api.py
import os
import requests
import json

# ViOTP API Settings (get key from environment variable)
VIOTP_API_KEY = os.environ.get('VIOTP_API_KEY')
API_VIOTP = 'https://api.viotp.com'

def get_viotp_balance():
    try:
        url = f"https://api.viotp.com/users/balance?token={VIOTP_API_KEY}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get('status') == 'success':
            return data.get('balance')
        else:
            print(f"Error from ViOTP API: {data.get('message', 'Unknown error')}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"Network error when trying to get ViOTP balance: {e}")
        return False
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error parsing ViOTP balance response: {e}")
        return False

def get_viotp_countries(app_id):
    try:
        url = f"https://api.viotp.com/countries/app?token={VIOTP_API_KEY}&app_id={app_id}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get('status') == 'success':
            countries = {
                item['country_id']: {'name': item['country_name'], 'price': item['price']}
                for item in data['countries']
            }
            return countries
        else:
            print(f"Error from ViOTP API: {data.get('message', 'Unknown error')}")
            return False
    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError) as e:
        print(f"Error getting ViOTP countries: {e}")
        return False

def request_viotp_number(app_id, country_code):
    try:
        url = f"https://api.viotp.com/services/request?token={VIOTP_API_KEY}&app_id={app_id}&country_code={country_code}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get('status') == 'success':
            return {'request_id': data.get('request_id'), 'Phone': data.get('number')}
        else:
            print(f"Error from ViOTP API: {data.get('message', 'Unknown error')}")
            return False
    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError) as e:
        print(f"Error requesting ViOTP number: {e}")
        return False

def get_viotp_code(request_id):
    try:
        url = f"https://api.viotp.com/services/status?token={VIOTP_API_KEY}&request_id={request_id}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get('status') == 'success' and 'code' in data:
            return {'Code': data.get('code')}
        else:
            return False
    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        print(f"Error getting ViOTP code: {e}")
        return False

def cancel_viotp_request(request_id):
    try:
        url = f"https://api.viotp.com/services/cancel?token={VIOTP_API_KEY}&request_id={request_id}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get('status') == 'success':
            return True
        else:
            return False
    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        print(f"Error canceling ViOTP request: {e}")
        return False
