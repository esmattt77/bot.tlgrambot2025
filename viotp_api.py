import requests
import json
import os

class VIOTPAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://viotp.com/api/"

    def get_services_and_countries(self):
        url = self.base_url + "get-services-and-countries"
        params = {"apiKey": self.api_key}
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()  # This will raise an HTTPError if the HTTP request returned an unsuccessful status code
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching services and countries: {e}")
            return None

    def get_balance(self):
        url = self.base_url + "balance"
        params = {"apiKey": self.api_key}
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching balance: {e}")
            return None

    def buy_number(self, app_id, country_code):
        url = self.base_url + "buy"
        params = {
            "apiKey": self.api_key,
            "app_id": app_id,
            "country_code": country_code
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error buying number: {e}")
            return None

    def get_otp(self, request_id):
        url = self.base_url + "get-code"
        params = {
            "apiKey": self.api_key,
            "request_id": request_id
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting OTP: {e}")
            return None

    def cancel_request(self, request_id):
        url = self.base_url + "cancel"
        params = {
            "apiKey": self.api_key,
            "request_id": request_id
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error cancelling request: {e}")
            return None

if __name__ == "__main__":
    # هذا الجزء لتجربة الكلاس بشكل منفصل
    # تأكد من وضع مفتاح API الخاص بك في متغير البيئة VIOTP_API_KEY
    viotp_api_key = os.environ.get('VIOTP_API_KEY')
    if viotp_api_key:
        viotp = VIOTPAPI(viotp_api_key)
        
        print("Testing get_balance...")
        balance_data = viotp.get_balance()
        if balance_data and balance_data.get("success"):
            print(f"Success! Balance: {balance_data['data']['balance']}")
        else:
            print(f"Failed to get balance. Response: {balance_data}")

    else:
        print("Please set the VIOTP_API_KEY environment variable.")
