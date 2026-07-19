# services/email.py
from flask_mail import Mail, Message
from flask import current_app
import threading
import logging

mail = Mail()

def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            logging.error(f"Email send failed: {e}")

def send_email(subject, sender, recipients, text_body, html_body):
    """Low‑level email sender (async)."""
    msg = Message(subject, sender=sender, recipients=recipients)
    msg.body = text_body
    msg.html = html_body
    threading.Thread(target=send_async_email,
                     args=(current_app._get_current_object(), msg)).start()

def send_notification_email(recipient_email, title, message):
    """Send a simple HTML email for a notification."""
    subject = f"TUSOME Notification: {title}"
    html_body = f"""
    <h2>{title}</h2>
    <p>{message}</p>
    <hr>
    <p><small>This is an automated message from TUSOME Academy.</small></p>
    """
    text_body = f"{title}\n\n{message}\n\n-- TUSOME Academy"
    send_email(subject,
               current_app.config['SCHOOL_EMAIL'],
               [recipient_email],
               text_body,
               html_body)