# sms_service.py
import requests
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
        """Send SMS using Africa's Talking API"""
        if not self.api_key:
            print("SMS API key not configured")
            return False
        
        headers = {
            'apiKey': self.api_key,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {
            'username': 'sandbox',  # Use 'sandbox' for testing
            'to': phone_number,
            'message': message,
            'from': self.sender_id
        }
        
        try:
            response = requests.post(self.base_url, headers=headers, data=data)
            return response.status_code == 200
        except Exception as e:
            print(f"SMS sending failed: {e}")
            return False
    
    def send_grade_sms(self, student, grade):
        """Send grade notification via SMS"""
        message = f"TUSOME Academy: New grade for {student.full_name} - {grade.subject.name}: {grade.grade_letter} ({grade.percentage}%). Login to view details."
        return self.send_sms(student.parent.phone, message)
    
    def send_fee_reminder_sms(self, student, total_balance):
        """Send fee reminder via SMS"""
        message = f"TUSOME Academy: Fee reminder for {student.full_name}. Outstanding balance: KES {total_balance:,.2f}. Please pay to avoid inconvenience."
        return self.send_sms(student.parent.phone, message)

sms_service = SMSService()
