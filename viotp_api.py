# viotp_api.py

import requests
import os
from typing import Dict, Any

class VIOTPAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        # Base URL for the ViOTP API.
        self.base_url = "https://api.viotp.com"

    def get_balance(self) -> Dict[str, Any]:
        """يجلب رصيد المستخدم من ViOTP."""
        try:
            url = f"{self.base_url}/users/balance?token={self.api_key}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"خطأ في الاتصال: {e}"}
            
    def get_services_by_country(self, country_code: str = 'vn') -> Dict[str, Any]:
        """
        يجلب قائمة الخدمات المتاحة لدولة معينة (مثل فيتنام 'vn').
        """
        try:
            url = f"{self.base_url}/service/getv2?token={self.api_key}&country={country_code}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"خطأ في الاتصال: {e}"}

    def buy_number(self, service_id: int) -> Dict[str, Any]:
        """يشتري رقمًا جديدًا لخدمة معينة."""
        try:
            url = f"{self.base_url}/request/getv2?token={self.api_key}&serviceId={service_id}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"خطأ في الاتصال: {e}"}

    def get_otp(self, request_id: str) -> Dict[str, Any]:
        """يجلب رمز التحقق (OTP) للرقم الذي تم شراؤه."""
        try:
            url = f"{self.base_url}/session/getv2?token={self.api_key}&requestId={request_id}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"خطأ في الاتصال: {e}"}

    def cancel_request(self, request_id: str) -> Dict[str, Any]:
        """يلغي طلب الرقم."""
        try:
            url = f"{self.base_url}/session/cancelv2?token={self.api_key}&requestId={request_id}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"خطأ في الاتصال: {e}"}
