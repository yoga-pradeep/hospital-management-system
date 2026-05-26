from celery import Celery
from celery.schedules import crontab

def create_celery(app):
    
    celery = Celery(
        app.import_name,
        broker  = 'redis://localhost:6379/0',
        backend = 'redis://localhost:6379/0'
    )

    # This makes Celery tasks run inside Flask app, task can access db
    
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask

    # SCHEDULED JOBS
    
    celery.conf.beat_schedule = {

        # Run reminder every 2 minutes 
        'daily-appointment-reminder': {
            'task'    : 'tasks.send_daily_reminders',
            'schedule': crontab(minute='*/1')
        },

        # Run report every 2 minutes 
        'monthly-doctor-report': {
            'task'    : 'tasks.send_monthly_reports',
            'schedule': crontab(minute='*/1')
        },
    }

    celery.conf.timezone = 'Asia/Kolkata'

    return celery