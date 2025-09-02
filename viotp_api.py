import requests
import os

# Base URL for the ViOTP API.
BASE_URL = "https://api.viotp.com/users/"

def get_viotp_balance():
    """Fetches the user's balance from the ViOTP API."""
    try:
        api_key = os.environ.get('VIOTP_API_KEY')
        if not api_key:
            return False

        url = f"{BASE_URL}balance?token={api_key}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('status') == 'success' and 'data' in data and 'balance' in data['data']:
            balance_raw = data['data']['balance']
            balance_calculated = int((balance_raw / 22000) * 64)
            return balance_calculated
        else:
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to ViOTP API: {e}")
        return False
    except (ValueError, KeyError) as e:
        print(f"Error parsing ViOTP response: {e}")
        return False

def get_viotp_countries(app_id):
    """Fetches the list of available countries and their prices for a given app."""
    try:
        api_key = os.environ.get('VIOTP_API_KEY')
        if not api_key:
            return {}

        url = f"{BASE_URL}services?token={api_key}&app_id={app_id}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('status') == 'success' and 'data' in data:
            return {item['id']: {'name': item['country_name'], 'price': item['price']} for item in data['data']}
        else:
            return {}
            
    except requests.exceptions.RequestException:
        return {}

def request_viotp_number(app_id, country_code):
    """Requests a new number from the ViOTP API."""
    try:
        api_key = os.environ.get('VIOTP_API_KEY')
        if not api_key:
            return None

        url = f"{BASE_URL}request?token={api_key}&app_id={app_id}&country_code={country_code}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('status') == 'success' and 'data' in data:
            return {'request_id': data['data']['id'], 'Phone': data['data']['number']}
        else:
            return None
    except requests.exceptions.RequestException:
        return None

def get_viotp_code(request_id):
    """Checks for the SMS code for a requested number."""
    try:
        api_key = os.environ.get('VIOTP_API_KEY')
        if not api_key:
            return None

        url = f"{BASE_URL}check?token={api_key}&id={request_id}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('status') == 'success' and 'data' in data and data['data']['status'] == 'success':
            return {'Code': data['data']['sms_code']}
        else:
            return None
    except requests.exceptions.RequestException:
        return None

def cancel_viotp_request(request_id):
    """Cancels a pending number request."""
    try:
        api_key = os.environ.get('VIOTP_API_KEY')
        if not api_key:
            return False

        url = f"{BASE_URL}cancel?token={api_key}&id={request_id}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('status') == 'success':
            return True
        else:
            return False
    except requests.exceptions.RequestException:
        return False
