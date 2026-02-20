# scheduler.py
from notifications import notification_service
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import atexit

def init_scheduler(app):
    scheduler = BackgroundScheduler()
    
    # Daily fee reminders at 9 AM
    scheduler.add_job(
        func=notification_service.send_daily_reminders,
        trigger=CronTrigger(hour=9, minute=0),
        id='daily_fee_reminders',
        name='Send daily fee reminders',
        replace_existing=True
    )
    
    # Weekly grade summary on Fridays at 3 PM
    scheduler.add_job(
        func=send_weekly_grade_summary,
        trigger=CronTrigger(day_of_week='fri', hour=15, minute=0),
        id='weekly_grade_summary',
        name='Send weekly grade summary',
        replace_existing=True
    )
    
    scheduler.start()
    
    # Shut down the scheduler when exiting the app
    atexit.register(lambda: scheduler.shutdown())

def send_weekly_grade_summary():
    """Send weekly grade summary to all parents"""
    # Implementation for weekly summaries
    pass
