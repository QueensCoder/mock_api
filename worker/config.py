from app.core.config import settings

# Broker & backend
broker_url = settings.REDIS_URL
result_backend = settings.REDIS_URL

# Serialization
task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]

# Time
timezone = "UTC"
enable_utc = True

# Result expiry (24 hours)
result_expires = 86400

# Prevent tasks from running forever (10 min hard limit)
task_soft_time_limit = 540
task_time_limit = 600

# Retry policy defaults
task_acks_late = True
task_reject_on_worker_lost = True

# Concurrency — override via CELERY_CONCURRENCY env var if needed
worker_prefetch_multiplier = 1
