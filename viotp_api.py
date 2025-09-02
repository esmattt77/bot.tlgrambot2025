import requests

class VIOTPAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://viotp.com/api/"

    def make_request(self, endpoint, params=None):
        if params is None:
            params = {}
        params['apiKey'] = self.api_key
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API Error: {e}")
            return {'success': False, 'message': 'API request failed'}

    def get_balance(self):
        return self.make_request("balance")

    def get_services_and_countries(self):
        services_response = self.make_request("services")
        if not services_response.get('success'):
            return {}
        
        services_data = {}
        for service in services_response['data']['services']:
            service_id = service['id']
            countries_response = self.make_request("country-by-service", {'serviceId': service_id})
            
            if countries_response.get('success'):
                countries_data = {}
                for country in countries_response['data']['countries']:
                    countries_data[country['countryId']] = {
                        'name': country['name'],
                        'price': country['price']
                    }
                services_data[service_id] = {
                    'name': service['name'],
                    'countries': countries_data
                }
        return services_data

    def buy_number(self, service_id, country_code):
        params = {
            'serviceId': service_id,
            'countryId': country_code,
            'Action': 'get'
        }
        return self.make_request("number", params)

    def get_otp(self, order_id):
        params = {
            'orderId': order_id,
            'Action': 'getStatus'
        }
        return self.make_request("number", params)

    def cancel_request(self, order_id):
        params = {
            'orderId': order_id,
            'Action': 'cancel'
        }
        return self.make_request("number", params)
