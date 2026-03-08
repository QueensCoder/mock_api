import logging

from worker.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(bind=True, name="example.add")
def add(self, x: int, y: int) -> int:
    logger.info("Running add task: %s + %s", x, y)
    return x + y


@celery.task(bind=True, name="example.send_email", max_retries=3, default_retry_delay=60)
def send_email(self, to: str, subject: str, body: str) -> dict:
    try:
        logger.info("Sending email to %s — subject: %s", to, subject)
        # TODO: plug in real email service
        return {"status": "sent", "to": to}
    except Exception as exc:
        logger.exception("Email task failed, retrying...")
        raise self.retry(exc=exc)
