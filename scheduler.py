# scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import atexit
from services.notification import send_daily_reminders,send_weekly_grade_summary  # now points to our updated file

def init_scheduler(app):
    scheduler = BackgroundScheduler()

    def daily_reminders_job():
        with app.app_context():
            send_daily_reminders()

    def weekly_summary_job():
        with app.app_context():
            send_weekly_grade_summary()

    scheduler.add_job(
        func=daily_reminders_job,
        trigger=CronTrigger(hour=9, minute=0),
        id='daily_fee_reminders',
        name='Send daily fee reminders',
        replace_existing=True
    )

    scheduler.add_job(
        func=weekly_summary_job,
        trigger=CronTrigger(day_of_week='fri', hour=15, minute=0),
        id='weekly_grade_summary',
        name='Send weekly grade summary',
        replace_existing=True
    )

    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())