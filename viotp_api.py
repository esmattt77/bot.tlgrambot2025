import requests
import os
import json

class VIOTPAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.BASE_URL = "https://api.viotp.com"

    def _api_call(self, endpoint, params=None):
        if params is None:
            params = {}
        params['token'] = self.api_key
        try:
            response = requests.get(f"{self.BASE_URL}{endpoint}", params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"Request failed: {e}"}

    def get_balance(self):
        response = self._api_call("/users/balance")
        if not response.get('success'):
            return {'success': False, 'error': response.get('message', 'Failed to get balance.')}
        
        balance = response.get('data', {}).get('balance', 0)
        return {'success': True, 'balance': balance}

    def get_countries(self):
        countries_data = {}
        # The API doesn't have a "get all countries" endpoint. We'll list services for known countries.
        supported_countries = [
            {'code': 'vn', 'name': 'Vietnam 🇻🇳'},
            {'code': 'la', 'name': 'Laos 🇱🇦'}
        ]

        for country_info in supported_countries:
            response = self._api_call("/service/getv2", params={'country': country_info['code']})
            if response.get('success'):
                services = response.get('data', [])
                for service in services:
                    service_id = str(service.get('id'))
                    if service_id not in countries_data:
                        countries_data[service_id] = {}
                    
                    countries_data[service_id][country_info['code']] = {
                        'name': f"{service.get('name')} - {country_info['name']}",
                        'price': float(service.get('price', 0)),
                        'count': -1 # The API does not provide number counts.
                    }

        return {'success': True, 'countries': countries_data}

    def buy_number(self, service_id, country_code):
        params = {'serviceId': service_id, 'country': country_code}
        response = self._api_call("/request/getv2", params=params)
        
        if not response.get('success'):
            return {'success': False, 'error': response.get('message', 'Failed to buy number.')}

        data = response.get('data', {})
        return {
            'success': True,
            'id': str(data.get('request_id')),
            'number': str(data.get('phone_number'))
        }

    def get_otp(self, request_id):
        response = self._api_call("/session/getv2", params={'requestId': request_id})
        
        if not response.get('success'):
            return {'success': False, 'error': response.get('message', 'Failed to get OTP.')}

        data = response.get('data', {})
        status = data.get('Status')
        
        if status == 1: # 1: Hoàn thành (Completed)
            code = data.get('Code')
            return {'success': True, 'code': code}
        elif status == 0: # 0: Đợi tin nhắn (Waiting for message)
            return {'success': False, 'status': 'pending'}
        else: # 2: Hết hạn (Expired) or other
            return {'success': False, 'error': 'Request expired or invalid.'}

    def cancel_number(self, request_id):
        # The VIOTP API documentation does not provide a cancellation endpoint.
        # This function is a placeholder to prevent errors in the main bot logic.
        return {'success': False, 'error': 'Cancellation is not supported by the VIOTP API.'}
