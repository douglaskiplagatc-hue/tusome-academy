# services/sms.py
import requests
import logging
from flask import current_app

class SMSService:
    def __init__(self, app=None):
        self.api_key = None
        self.sender_id = None
        self.base_url = "https://api.africastalking.com/version1/messaging"
        if app:
            self.init_app(app)

    def init_app(self, app):
        self.api_key = app.config.get('SMS_API_KEY')
        self.sender_id = app.config.get('SMS_SENDER_ID', 'TUSOME')

    def send_sms(self, phone_number, message):
        """Low‑level method to send a raw SMS."""
        if not self.api_key:
            logging.error("SMS API key not configured")
            return False
        headers = {
            'apiKey': self.api_key,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = {
            'username': 'sandbox',  # change to your production username when ready
            'to': phone_number,
            'message': message,
            'from': self.sender_id
        }
        try:
            response = requests.post(self.base_url, headers=headers, data=data)
            return response.status_code == 200
        except Exception as e:
            logging.error(f"SMS sending failed: {e}")
            return False

    def send_notification_sms(self, phone, title, message):
        """Send a short, formatted notification SMS."""
        full_message = f"TUSOME: {title}\n{message[:140]}"
        return self.send_sms(phone, full_message)

# Global instance (to be initialised with app later)
sms_service = SMSService()