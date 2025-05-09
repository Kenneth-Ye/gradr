import os
from celery import Celery
from celery.utils.log import get_task_logger
import json
import redis as sync_redis # Using sync redis client for Celery tasks

logger = get_task_logger(__name__)

# Celery configuration
redis_host_env = os.getenv("REDIS_HOST", "localhost")
redis_port_env = int(os.getenv("REDIS_PORT", 6379))
redis_url_env = f"redis://{redis_host_env}:{redis_port_env}"

celery_app = Celery(
    "pdf_processor",
    broker=redis_url_env,
    backend=redis_url_env,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour task time limit
    worker_max_tasks_per_child=10,
)

def get_redis_client_for_publish():
    return sync_redis.Redis(host=redis_host_env, port=redis_port_env)

@celery_app.task(bind=True, name="process_pdf_task")
def process_pdf_task(self, job_id, pdf_files, answer_key=None):
    redis_client = None
    channel_name = f"job_updates:{job_id}"
    try:
        redis_client = get_redis_client_for_publish()

        def publish_update(status, progress, message, **extra_data):
            payload = {"job_id": job_id, "status": status, "progress": progress, "message": message, **extra_data}
            redis_client.publish(channel_name, json.dumps(payload))
            logger.info(f"Published to {channel_name}: {payload}")

        logger.info(f"Starting to process job {job_id} with {len(pdf_files)} PDFs")
        self.update_state(state="PROCESSING", meta={"job_id": job_id, "progress": 0})
        publish_update(status="INITIALIZING", progress=0, message="Job accepted and initializing.")

        # Simulate initial processing step
        # import time; time.sleep(1)
        self.update_state(state="PROCESSING", meta={"job_id": job_id, "progress": 10, "current_file": "N/A"})
        publish_update(status="PROCESSING", progress=10, message="Initial setup complete.")
        
        total_files = len(pdf_files)
        processed_files_details = []
        for i, pdf_file_path in enumerate(pdf_files):
            file_name = os.path.basename(pdf_file_path)
            current_progress = 10 + int(((i + 1) / total_files) * 80) # Progress from 10% to 90% during file processing
            
            publish_update(status="PROCESSING", progress=current_progress - (40/total_files), message=f"Starting to process file: {file_name}", current_file=file_name)
            # Actual PDF processing logic would go here
            # e.g., text extraction, calling other tasks like mark_question_task
            # import time; time.sleep(2) # Simulate work
            
            processed_files_details.append({"file": file_name, "status": "processed_text_extraction"})
            self.update_state(state="PROCESSING", meta={"job_id": job_id, "progress": current_progress, "current_file": file_name})
            publish_update(status="PROCESSING", progress=current_progress, message=f"Finished processing file: {file_name}", current_file=file_name)

        final_progress = 100
        self.update_state(state="COMPLETED", meta={"job_id": job_id, "progress": final_progress})
        
        final_result_payload = {
            "files_processed_count": len(pdf_files),
            "processed_files_details": processed_files_details,
            "answer_key_provided": answer_key is not None
        }
        publish_update(status="COMPLETED", progress=final_progress, message="All files processed successfully.", result=final_result_payload)
        
        # Celery task result (can be same as final payload or more detailed internal one)
        return {"job_id": job_id, "status": "COMPLETED", **final_result_payload}
    
    except Exception as e:
        logger.error(f"Error processing job {job_id}: {str(e)}", exc_info=True)
        error_payload = {"error": str(e), "details": "An unexpected error occurred during processing."}
        if redis_client: # Check if redis_client was initialized
            publish_update(status="FAILURE", progress=0, message="Job failed due to an error.", error_details=error_payload)
        self.update_state(state="FAILURE", meta={"job_id": job_id, "error": str(e)})
        raise
    finally:
        if redis_client:
            # Optionally send a final "CLOSED" or "STREAM_ENDED" message if your client expects it.
            # publish_update(status="STREAM_ENDED", progress=100, message="Update stream ended for this job.")
            redis_client.close()

@celery_app.task(bind=True, name="mark_question_task")
def mark_question_task(self, job_id, question_id, student_answer, correct_answer=None):
    redis_client = None
    channel_name = f"job_updates:{job_id}" # Could also be a more granular channel
    try:
        redis_client = get_redis_client_for_publish()
        def publish_progress(message, **extra_data):
            # This task might be part of a larger job, so progress is relative
            payload = {"job_id": job_id, "task_type": "mark_question", "question_id": question_id, "status": "PROCESSING", "message": message, **extra_data}
            redis_client.publish(channel_name, json.dumps(payload))

        logger.info(f"Marking question {question_id} for job {job_id}")
        publish_progress(message=f"Starting to mark question {question_id}")

        # import time; time.sleep(1) # Simulate LLM call

        result = {
            "question_id": question_id,
            "score": 7, 
            "feedback": "This is placeholder feedback. AI would provide detailed feedback."
        }
        # Publish result specific to this question
        payload_done = {"job_id": job_id, "task_type": "mark_question", "question_id": question_id, "status": "COMPLETED", "result": result}
        redis_client.publish(channel_name, json.dumps(payload_done))

        return result
    except Exception as e:
        logger.error(f"Error marking question {question_id} for job {job_id}: {str(e)}", exc_info=True)
        error_payload = {"job_id": job_id, "task_type": "mark_question", "question_id": question_id, "status": "FAILURE", "error": str(e)}
        if redis_client:
            redis_client.publish(channel_name, json.dumps(error_payload))
        raise
    finally:
        if redis_client:
            redis_client.close() 