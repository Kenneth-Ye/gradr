import os
from celery import Celery
import redis
import time
import json

celery_app = Celery("worker")
celery_app.config_from_object("celeryconfig")

r = redis.Redis(host="localhost", port=6379, db=0)

@celery_app.task
def parse_pdf_to_latex(task_id: str):
    pdf_path = "" # temp
    try:
        r.publish(f"mark-pdf:{task_id}", json.dumps({"progress": "Reading PDF..."}))

        # call model
        time.sleep(10)
        r.publish(f"mark-pdf:{task_id}", json.dumps({
            "progress": "marking pdf",
            "latex": ""
        }))
        time.sleep(10)

        r.publish(f"mark-pdf:{task_id}", json.dumps({
            "progress": "done",
            "latex": ""
        }))

    except Exception as e:
        r.publish(f"mark-pdf:{task_id}", json.dumps({
            "progress": "error",
            "error": str(e)
        }))
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
