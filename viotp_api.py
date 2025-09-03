import requests
import json
import os
from typing import Dict, Any

class VIOTPAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://viotp.com/api/"

    def get_services_and_countries(self) -> Dict[str, Any]:
        """Fetches available services and countries from ViOTP."""
        try:
            url = f"{self.base_url}get-services-and-countries"
            params = {"apiKey": self.api_key}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data and data.get("success"):
                return data.get("data", {})
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error fetching services and countries from VIOTP: {e}")
            return None

    def get_balance(self) -> Dict[str, Any]:
        """Fetches the user's account balance from ViOTP."""
        try:
            url = f"{self.base_url}balance"
            params = {"apiKey": self.api_key}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"Connection error: {e}"}

    def buy_number(self, app_id: int, country_code: str) -> Dict[str, Any]:
        """Buys a new number for a specific service and country."""
        try:
            url = f"{self.base_url}buy"
            params = {
                "apiKey": self.api_key,
                "app_id": app_id,
                "country_code": country_code
            }
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"Connection error: {e}"}

    def get_otp(self, request_id: str) -> Dict[str, Any]:
        """Fetches the OTP for a purchased number."""
        try:
            url = f"{self.base_url}get-code"
            params = {
                "apiKey": self.api_key,
                "request_id": request_id
            }
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"Connection error: {e}"}

    def cancel_request(self, request_id: str) -> Dict[str, Any]:
        """Cancels a number request."""
        try:
            url = f"{self.base_url}cancel"
            params = {
                "apiKey": self.api_key,
                "request_id": request_id
            }
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"Connection error: {e}"}
