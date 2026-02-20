# email_service.py
from flask_mail import Mail, Message
from flask import current_app
import threading

mail = Mail()

def send_async_email(app, msg):
    with app.app_context():
        mail.send(msg)

def send_email(subject, sender, recipients, text_body, html_body):
    msg = Message(subject, sender=sender, recipients=recipients)
    msg.body = text_body
    msg.html = html_body
    threading.Thread(target=send_async_email,
                    args=(current_app._get_current_object(), msg)).start()

def send_grade_notification(student, grades):
    """Send grade notification to parent"""
    subject = f"New Grades Available for {student.full_name}"
    
    html_body = f"""
    <h2>Grade Notification - {current_app.config['SCHOOL_NAME']}</h2>
    <p>Dear Parent,</p>
    <p>New grades have been posted for <strong>{student.full_name}</strong> ({student.admission_number}).</p>
    
    <table border="1" style="border-collapse: collapse; width: 100%;">
        <tr style="background-color: #f2f2f2;">
            <th>Subject</th>
            <th>Grade</th>
            <th>Percentage</th>
            <th>Term</th>
        </tr>
    """
    
    for grade in grades:
        html_body += f"""
        <tr>
            <td>{grade.subject.name}</td>
            <td>{grade.grade_letter}</td>
            <td>{grade.percentage}%</td>
            <td>{grade.term}</td>
        </tr>
        """
    
    html_body += """
    </table>
    <p>Please log in to the parent portal to view detailed reports.</p>
    <p>Best regards,<br>TUSOME Academy</p>
    """
    
    text_body = f"New grades available for {student.full_name}. Please check the parent portal."
    
    send_email(subject, 
              current_app.config['SCHOOL_EMAIL'], 
              [student.parent.email], 
              text_body, 
              html_body)

def send_fee_reminder(student, overdue_fees):
    """Send fee payment reminder"""
    subject = f"Fee Payment Reminder - {student.full_name}"
    
    total_overdue = sum(fee.balance for fee in overdue_fees)
    
    html_body = f"""
    <h2>Fee Payment Reminder - {current_app.config['SCHOOL_NAME']}</h2>
    <p>Dear Parent,</p>
    <p>This is a reminder that there are outstanding fees for <strong>{student.full_name}</strong>.</p>
    
    <h3>Overdue Fees:</h3>
    <table border="1" style="border-collapse: collapse; width: 100%;">
        <tr style="background-color: #f2f2f2;">
            <th>Fee Type</th>
            <th>Amount Due</th>
            <th>Due Date</th>
        </tr>
    """
    
    for fee in overdue_fees:
        html_body += f"""
        <tr>
            <td>{fee.fee_type}</td>
            <td>KES {fee.balance:,.2f}</td>
            <td>{fee.due_date.strftime('%Y-%m-%d') if fee.due_date else 'N/A'}</td>
        </tr>
        """
    
    html_body += f"""
    </table>
    <p><strong>Total Outstanding: KES {total_overdue:,.2f}</strong></p>
    <p>Please make payment as soon as possible to avoid any inconvenience.</p>
    <p>Payment Methods:</p>
    <ul>
        <li>M-Pesa Pay Bill: 123456</li>
        <li>Bank Transfer: Account 1234567890</li>
        <li>Cash at School Office</li>
    </ul>
    <p>Best regards,<br>TUSOME Academy</p>
    """
    
    text_body = f"Fee payment reminder for {student.full_name}. Total outstanding: KES {total_overdue:,.2f}"
    
    send_email(subject, 
              current_app.config['SCHOOL_EMAIL'], 
              [student.parent.email], 
              text_body, 
              html_body)
