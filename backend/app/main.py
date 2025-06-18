from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
import uuid
import redis.asyncio as redis
import asyncio
import json
from .tasks import parse_pdf_to_latex

app = FastAPI()
redis_client = redis.Redis(host="localhost", port=6379, db=0)

@app.post("/mark-pdf")
async def start_task():
    task_id = str(uuid.uuid4())
    parse_pdf_to_latex.delay(task_id)
    return JSONResponse({"task_id": task_id})

@app.get("/events/{task_id}")
async def sse(task_id: str):
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"mark-pdf:{task_id}")

    async def event_generator():
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=10)
                if message:
                    data = json.loads(message["data"])
                    yield f"data: {json.dumps(data)}\n\n"
                await asyncio.sleep(0.5)
        finally:
            await pubsub.unsubscribe(f"mark-pdf:{task_id}")
            await pubsub.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")
