# viotp_api.py

import requests
import os
from typing import Dict, Any

class VIOTPAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        # Base URL for the ViOTP API.
        self.base_url = "https://api.viotp.com"

    def get_services_and_countries(self) -> Dict[str, Any]:
        """Fetches available services and countries from ViOTP."""
        try:
            url = "https://viotp.com/api/get-services-and-countries"
            params = {"apiKey": self.api_key}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data and data.get("success"):
                return data.get("data", {})
            return {"success": False, "message": "API response error"}
        except requests.exceptions.RequestException as e:
            print(f"Error fetching services and countries from VIOTP: {e}")
            return {"success": False, "message": f"Connection error: {e}"}

    def get_balance(self) -> Dict[str, Any]:
        """Fetches the user's account balance from ViOTP."""
        try:
            url = f"{self.base_url}/users/balance?token={self.api_key}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"Connection error: {e}"}

    def get_services(self) -> Dict[str, Any]:
        """Fetches the list of available services and their prices."""
        try:
            url = f"{self.base_url}/service/getv2?token={self.api_key}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"Connection error: {e}"}

    def buy_number(self, service_id: int) -> Dict[str, Any]:
        """Buys a new number for a specific service."""
        try:
            url = f"{self.base_url}/request/getv2?token={self.api_key}&serviceId={service_id}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"Connection error: {e}"}

    def get_otp(self, request_id: str) -> Dict[str, Any]:
        """Fetches the OTP for a purchased number."""
        try:
            url = f"{self.base_url}/session/getv2?token={self.api_key}&requestId={request_id}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"Connection error: {e}"}

    def cancel_request(self, request_id: str) -> Dict[str, Any]:
        """Cancels a number request. Note: this API might not be officially supported."""
        try:
            url = f"{self.base_url}/session/cancelv2?token={self.api_key}&requestId={request_id}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"Connection error: {e}"}
