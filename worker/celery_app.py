from celery import Celery

celery = Celery("worker")

celery.config_from_object("worker.config")

celery.autodiscover_tasks(["worker.tasks"])
