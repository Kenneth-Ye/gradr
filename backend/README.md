## Architecture

- **FastAPI**: Web API with async endpoints
- **Celery**: Distributed task queue for background processing
- **Redis**: Message broker and pub/sub for real-time updates
- **Server-Sent Events (SSE)**: Real-time progress streaming to clients

## Prerequisites

- Python 3.8+
- Redis server
- Virtual environment (recommended)

## Installation

### 1. Install Redis

**macOS (using Homebrew):**
```bash
brew install redis
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install redis-server
```

**Or use Docker:**
```bash
docker run -d -p 6379:6379 --name redis-server redis:alpine
```

### 2. Set up Python Environment

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
```

## Running the Services

### Terminal 1: Start Redis Server

```bash
redis-server
```

### Terminal 2: Start Celery Worker
```bash
cd backend
source venv/bin/activate
celery -A app.tasks worker --loglevel=info
```

### Terminal 3: Start FastAPI Server
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Server will be available at: http://localhost:8000