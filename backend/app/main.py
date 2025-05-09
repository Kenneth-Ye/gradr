from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
import redis.asyncio as redis
import os
import uuid
from typing import List, Optional
import aiofiles
import asyncio
import json
from sse_starlette.sse import EventSourceResponse
from celery_app import celery_app, process_pdf_task

app = FastAPI()
app.state.redis_pubsub_client = None # For Server-Sent Events

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    redis_url = f"redis://{redis_host}:{redis_port}"

    # For Rate Limiter
    # Note: Ensure this redis client is suitable for FastAPILimiter or if it needs its own
    r_limiter = await redis.from_url(redis_url)
    await FastAPILimiter.init(r_limiter)

    # For PubSub for SSE
    app.state.redis_pubsub_client = await redis.from_url(redis_url)

@app.on_event("shutdown")
async def shutdown():
    if app.state.redis_pubsub_client:
        await app.state.redis_pubsub_client.close()

# PDF upload directory
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/api/upload", dependencies=[Depends(RateLimiter(times=10, seconds=60))])
async def upload_pdfs(
    files: List[UploadFile] = File(...),
    answer_key: Optional[UploadFile] = File(None)
):
    if not files:
        raise HTTPException(status_code=400, detail="No PDF files provided")
    
    for file in files:
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    
    job_id = str(uuid.uuid4())
    job_dir = os.path.join(UPLOAD_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    
    saved_files = []
    for file in files:
        file_path = os.path.join(job_dir, file.filename)
        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await file.read()
            await out_file.write(content)
        saved_files.append(file_path)
    
    answer_key_path = None
    if answer_key:
        answer_key_path = os.path.join(job_dir, "answer_key.pdf")
        async with aiofiles.open(answer_key_path, 'wb') as out_file:
            content = await answer_key.read()
            await out_file.write(content)
    
    task = process_pdf_task.delay(job_id, saved_files, answer_key_path)
    
    return {"job_id": job_id, "task_id": task.id, "status": "processing", "subscribe_url": f"/api/job/{job_id}/stream"}

@app.get("/api/job/{job_id}/stream")
async def stream_job_updates(request: Request, job_id: str):
    if not app.state.redis_pubsub_client:
        # This case should ideally not happen if startup event succeeded
        raise HTTPException(status_code=503, detail="Redis PubSub service not available.")

    async def event_generator():
        pubsub_client = app.state.redis_pubsub_client
        pubsub_connection = pubsub_client.pubsub()
        channel_name = f"job_updates:{job_id}"
        await pubsub_connection.subscribe(channel_name)
        
        try:
            while True:
                # Check if client is still connected
                if await request.is_disconnected():
                    # print(f"Client for job {job_id} disconnected.") # For debugging
                    break
                
                message = await pubsub_connection.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    try:
                        data_decoded = message["data"].decode("utf-8")
                        # sse-starlette expects a dict that can be json-serialized
                        # if data_decoded is already a JSON string, parse it
                        yield {"data": json.loads(data_decoded)} 
                    except json.JSONDecodeError:
                        # If it's not JSON, send as plain text (or handle as error)
                        yield {"data": data_decoded}
                    except Exception as e:
                        # print(f"Error processing message for SSE: {e}") # For debugging
                        yield {"data": json.dumps({"error": "Error processing message"})}

                await asyncio.sleep(0.1) # Prevent tight loop, adjust as needed
        except asyncio.CancelledError:
            # print(f"SSE Task for job {job_id} cancelled.") # For debugging
            pass # Task was cancelled, usually due to client disconnect
        finally:
            if pubsub_connection.subscribed:
                await pubsub_connection.unsubscribe(channel_name)
            await pubsub_connection.close() # Close this specific pubsub instance
            # print(f"Unsubscribed and closed pubsub for job {job_id}.") # For debugging

    return EventSourceResponse(event_generator())

