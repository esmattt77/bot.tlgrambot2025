# viotp_api.py
import requests
from config import API_VIOTP, VIOTP_API_KEY

def get_viotp_balance():
    try:
        response = requests.get(f'{API_VIOTP}/api/?action=balance&key={VIOTP_API_KEY}')
        response.raise_for_status()
        data = response.json()
        return data.get('balance', False)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching ViOTP balance: {e}")
        return False

def get_viotp_countries(app_id):
    try:
        response = requests.get(f'{API_VIOTP}/api/?action=countries&service={app_id}&key={VIOTP_API_KEY}')
        response.raise_for_status()
        data = response.json()
        countries = {}
        if isinstance(data, dict):
            for code, info in data.items():
                countries[code] = {'name': info.get('name'), 'price': info.get('cost', 0)}
        return countries
    except requests.exceptions.RequestException as e:
        print(f"Error fetching ViOTP countries: {e}")
        return {}

def request_viotp_number(app_id, country_code):
    try:
        response = requests.get(f'{API_VIOTP}/api/?action=get&country={country_code}&service={app_id}&key={VIOTP_API_KEY}')
        response.raise_for_status()
        data = response.json()
        if data.get('ok') and data.get('code'):
            return {'request_id': data.get('id'), 'Phone': data.get('number')}
        return False
    except requests.exceptions.RequestException as e:
        print(f"Error requesting ViOTP number: {e}")
        return False

def get_viotp_code(request_id):
    try:
        response = requests.get(f'{API_VIOTP}/api/?action=check&id={request_id}&key={VIOTP_API_KEY}')
        response.raise_for_status()
        data = response.json()
        if data.get('ok') and data.get('sms'):
            return {'Code': data.get('sms')}
        return False
    except requests.exceptions.RequestException as e:
        print(f"Error fetching ViOTP code: {e}")
        return False

def cancel_viotp_request(request_id):
    try:
        response = requests.get(f'{API_VIOTP}/api/?action=cancel&id={request_id}&key={VIOTP_API_KEY}')
        response.raise_for_status()
        data = response.json()
        return data.get('ok', False)
    except requests.exceptions.RequestException as e:
        print(f"Error cancelling ViOTP request: {e}")
        return False
