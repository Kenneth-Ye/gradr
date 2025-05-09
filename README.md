# PDF Test Marking Tool

This application allows for batch upload of PDF math tests and automatically marks them using AI and LLMs.

## Architecture

The application uses the following components:

- **FastAPI**: Backend API for handling file uploads and providing real-time status updates via Server-Sent Events (SSE).
- **Celery**: Distributed task queue for asynchronous processing of PDFs.
- **Redis**: Used as a broker for Celery, for rate limiting, and as a Pub/Sub mechanism for SSE.
- **Docker**: Containerization for easy deployment.

## Features

- Upload multiple PDF files of math tests.
- Optional upload of answer key PDFs.
- Asynchronous processing of test PDFs.
- Real-time progress updates via Server-Sent Events (SSE).
- Rate limiting to prevent abuse.
- AI-powered marking of math questions (placeholder implementation).

## Installation & Setup

### Requirements

- Docker and Docker Compose

### Running the Application

1. Clone the repository.
2. Ensure Tesseract OCR is installed on your system if not solely relying on Docker for local development where it's included in the image.
3. Start the services:

```bash
docker-compose up -d --build
```

This will start the FastAPI server, Celery worker(s), and Redis.

## API Endpoints

### Upload PDF Tests

```
POST /api/upload
```

**Parameters (form-data):**
- `files`: List of PDF files (required).
- `answer_key`: Optional PDF file containing answer key.

**Response:**
```json
{
  "job_id": "<uuid-string>",      // Unique ID for the entire job
  "task_id": "<celery-task-id>", // ID of the main Celery processing task
  "status": "processing",
  "subscribe_url": "/api/job/<uuid-string>/stream" // URL to subscribe for real-time updates
}
```

### Stream Job Updates (Server-Sent Events)

Connect to this endpoint using an EventSource client to receive real-time updates for a job.

```
GET /api/job/{job_id}/stream
```

**Events Streamed:**

Clients will receive messages as `data` events. The content of `data` will be a JSON string representing the update.

Example of an update event:
```sse
data: {"job_id": "<uuid-string>", "status": "PROCESSING", "progress": 50, "message": "Processing file example_test.pdf"}

...

data: {"job_id": "<uuid-string>", "status": "COMPLETED", "progress": 100, "message": "All files processed successfully.", "result": { ... }}
```

## Development

### Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI application (including SSE endpoint)
│   │   ├── celery_app.py     # Celery configuration and tasks (publishing to Redis)
│   │   └── (pdf_processor.py) # PDF processing logic (to be created/integrated)
│   ├── Dockerfile
│   └── requirements.txt
├── docker-compose.yml
└── README.md
```

### Notes on SSE Implementation:
- Celery tasks publish JSON-serialized updates to Redis channels (`job_updates:{job_id}`).
- The FastAPI SSE endpoint (`/api/job/{job_id}/stream`) subscribes to the relevant Redis channel and forwards messages to the connected client.
- The `sse-starlette` library is used for handling SSE connections in FastAPI.

## Extending the Application

- **PDF Processing**: Implement detailed PDF parsing and question/answer segmentation in a dedicated module (e.g., `pdf_processor.py`) and call it from Celery tasks.
- **LLM Integration**: Integrate with your chosen LLM provider within the `mark_question_task` in `celery_app.py`.
- **Error Handling**: Enhance error reporting in SSE messages.
- **Frontend**: Build a user interface that uploads files and uses an `EventSource` to display real-time progress. 