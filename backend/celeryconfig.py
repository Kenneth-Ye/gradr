import os

# Redis configuration
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = os.getenv("REDIS_PORT", 6379)
redis_url = f"redis://{redis_host}:{redis_port}/0"

# Celery configuration
broker_url = redis_url
result_backend = redis_url

# Serialization
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']

# Timezone
timezone = 'UTC'
enable_utc = True

# Worker settings
task_track_started = True
task_time_limit = 3600  # 1 hour
worker_max_tasks_per_child = 10 