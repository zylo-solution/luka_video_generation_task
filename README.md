# AI Documentary Video Generator

This project implements a full-stack application that converts a plain English prompt into a 30‑second documentary‑style video. It features a beautiful web frontend and demonstrates how multiple AI services can be orchestrated through a modern API:

* **Google Gemini** – generates a five‑scene script from a user prompt
* **HeyGen** – synthesizes a talking‑head video with lip‑synced avatar and ElevenLabs voice
* **Submagic** – transcribes the generated video and burns in captions
* **Redis** – provides persistent job storage across server restarts
* **Web Frontend** – intuitive interface for video generation with real-time progress tracking

The result is a captioned MP4 video ready for social media, with all jobs tracked asynchronously.

### ⚡ TL;DR - Get Started in 3 Steps

```bash
# 1. Create .env file with your API keys
cp .env.example .env
# Edit .env and add your API keys

# 2. Build and run with Docker Compose
docker compose up --build

# 3. Open http://localhost:3000 in your browser
```

That's it! The frontend, backend, and Redis will all start automatically. 🎉

---

## 🚀 Quick Start with Docker (Recommended)

### Prerequisites
- Docker and Docker Compose installed
- API keys for Gemini, HeyGen, and Submagic

### Setup and Run

1. **Clone the repository:**
   ```bash
   git clone git@github.com:zylo-solution/luka_video_generation_task.git
   cd luka_video_generation_task
   ```

2. **Create a `.env` file** from the example:
   ```bash
   cp .env.example .env
   ```

3. **Edit `.env` file** and add your API keys:
   ```env
   GEMINI_API_KEY=your_gemini_key_here
   HEYGEN_API_KEY=your_heygen_key_here
   SUBMAGIC_API_KEY=your_submagic_key_here
   ```

4. **Build and run with Docker Compose:**
   ```bash
   docker compose up --build
   ```

5. **Access the application:**
   
   - **Web Frontend:** Open your browser to **http://localhost:3000**
   - **API Documentation (Swagger UI):** **http://localhost:8000/docs**
   - **Backend API:** **http://localhost:8000**

That's it! The application runs with Redis for persistent job storage, the backend API on port 8000, and the frontend on port 3000.

### Managing Services

```bash
# Stop services
docker compose down

# View logs for all services
docker compose logs -f

# View logs for specific service
docker compose logs -f video-generator
docker compose logs -f frontend

# Restart a service
docker compose restart video-generator

# View all running containers
docker compose ps
```

---

## 🎨 Using the Web Frontend

The easiest way to generate videos is through the web interface at **http://localhost:3000**

### Steps:

1. **Open the frontend** in your browser: `http://localhost:3000`

2. **Enter your prompt** in the text area, for example:
   - "A coffee shop owner discovers AI"
   - "The future of renewable energy"
   - "AI transforming healthcare"

3. **Click "Generate Video"** button

4. **Monitor progress** in real-time:
   - Job ID and creation time are displayed
   - Progress bar shows completion percentage
   - Status updates automatically (Pending → Processing → Complete)

5. **View and Download:**
   - Once complete, the video plays automatically
   - Click the "📥 Download Video" button to save it locally

### Features:

✅ Real-time progress tracking  
✅ Automatic status polling  
✅ In-browser video playback  
✅ One-click download  
✅ Beautiful, responsive UI  
✅ Error handling and notifications  

---

## 📋 Testing the API

### Using Swagger UI (Interactive)

1. Open http://localhost:8000/docs in your browser

2. **Generate a Video:**
   - Click `POST /generate`
   - Click "Try it out"
   - Enter prompt: `{"prompt": "AI transforming healthcare"}`
   - Click "Execute"
   - Copy the `job_id` from response

3. **Check Status:**
   - Click `GET /status/{job_id}`
   - Paste your `job_id`
   - Click "Execute"
   - Monitor progress (0.0 to 1.0)

4. **Download Video:**
   - Wait until status shows "complete"
   - Click `GET /download/{job_id}`
   - Paste your `job_id`
   - Copy the `video_url` and open in browser

### Using cURL

```bash
# 1. Generate video
curl -X POST http://localhost:8000/generate \
     -H "Content-Type: application/json" \
     -d '{"prompt": "A coffee shop owner discovers AI"}'

# 2. Check status (replace JOB_ID)
curl http://localhost:8000/status/JOB_ID

# 3. Download video (when complete)
curl http://localhost:8000/download/JOB_ID
```

---

## 🧪 Running Tests

The project includes a comprehensive test suite covering API endpoints, job storage, video generation logic, and frontend integration.

### Prerequisites for Testing

Make sure the application is running first:
```bash
# Create .env file with your API keys
cp .env.example .env
# Edit .env and add your keys

# Start all services
docker compose up --build
```

### Run Tests with Docker

Once the services are running, open a new terminal and run tests:

```bash
# Run all backend tests (in Docker container)
docker compose exec video-generator pytest tests/ -v

# Run specific test file
docker compose exec video-generator pytest tests/test_api.py -v

# Run with coverage report
docker compose exec video-generator pytest tests/ --cov=. --cov-report=html

# Run specific test class
docker compose exec video-generator pytest tests/test_api.py::TestGenerateEndpoint -v
```

### Run Frontend Integration Tests

Frontend integration tests run from your host machine (not in Docker):

```bash
# Run frontend integration tests
pytest tests/test_frontend_integration.py -v

# Run with detailed output
pytest tests/test_frontend_integration.py -v --tb=short
```

### Run All Tests (Full Test Suite)

```bash
# Run frontend tests (from host)
pytest tests/test_frontend_integration.py -v

# Run backend tests (in Docker)
docker compose exec video-generator pytest tests/ -v
```

### Run Tests Locally (without Docker)

```bash
# Install dependencies
pip install -r requirements.txt -r requirements-redis.txt

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=term-missing
```

### Test Coverage

The test suite validates:
- ✅ All API endpoints (`/generate`, `/status`, `/download`)
- ✅ Job creation and lifecycle management
- ✅ Redis persistence and fallback to in-memory storage
- ✅ Error handling and validation
- ✅ Request/response schemas
- ✅ Multiple concurrent jobs
- ✅ OpenAPI documentation availability
- ✅ Frontend HTML serving and UI elements
- ✅ Frontend-backend communication via CORS
- ✅ Cross-origin request handling
- ✅ Job status polling and progress tracking
- ✅ Full end-to-end workflow

**Test Results:**
- Frontend Integration Tests: 21 tests
- Backend API Tests: 15 tests
- Video Generator Tests: 5 tests
- **Total: 41 tests**
```
20 passed in 0.99s
```

See [tests/README.md](tests/README.md) for detailed test documentation.

---

## 🏗️ Architecture

### Docker Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Docker Compose Stack                       │
│                                                         │
│  ┌────────────────┐    ┌────────────────┐             │
│  │  Web Frontend  │───▶│  FastAPI App   │───┐         │
│  │  (Port 3000)   │    │  (Port 8000)   │   │         │
│  │                │    │                │   │         │
│  │  Nginx Server  │    │  - Swagger UI  │   │         │
│  │  index.html    │    │  - Job Storage │   │         │
│  │                │    │  - Generator   │   ▼         │
│  └────────────────┘    └────────────────┘  ┌────────┐ │
│                                            │ Redis  │ │
│                                            │ Server │ │
│                                            └────────┘ │
│                            │                          │
│                            ▼                          │
│      ┌──────────────────────────────────────┐        │
│      │      External APIs                   │        │
│      │  - Gemini (Script Generation)       │        │
│      │  - HeyGen (Video + ElevenLabs Voice)│        │
│      │  - Submagic (Caption Burn-in)       │        │
│      └──────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────┘
```

### Services:

1. **Frontend (Port 3000)**
   - Nginx serving static HTML
   - Real-time progress tracking
   - Video playback and download

2. **Backend API (Port 8000)**
   - FastAPI with CORS enabled
   - RESTful endpoints
   - Async job processing

3. **Redis (Port 6379)**
   - Job persistence
   - 24-hour TTL
   - Automatic failover

### Application Architecture

The service is organized into modular components:

* **API layer (main.py)** – FastAPI application with three endpoints
  - Enqueues jobs and returns immediately
  - Background task processing via asyncio
  - CORS middleware for frontend access
  
* **Pipeline layer (video_generator.py)** – VideoGenerator class
  - Generates structured script via Gemini
  - Selects avatar and voice from HeyGen
  - Assembles video through HeyGen API
  - Applies captions using Submagic
  
* **Storage layer (job_storage.py)** – JobStorage class
  - Persists jobs in Redis with 24-hour expiration
  - Falls back to in-memory storage if Redis unavailable
  - Survives server restarts and code changes

* **Frontend layer (frontend/index.html)** – Web interface
  - Single-page application
  - Polls backend for status updates
  - Displays videos with download capability

### Job States

Jobs progress through the following states:
1. `pending` → Job created, waiting to start
2. `generating_script` → Gemini generating 5-scene script
3. `generating_video` → HeyGen creating avatar video (15-20 minutes)
4. `adding_captions` → Submagic burning in captions
5. `complete` → Video ready for download
6. `error` → Something went wrong (see error message)

---

## 🔧 Manual Setup (Without Docker)

If you prefer to run without Docker:

### 1. Install Redis

```bash
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis

# macOS
brew install redis
brew services start redis

# Verify Redis is running
redis-cli ping  # Should return "PONG"
```

### 2. Install Python Dependencies

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt -r requirements-redis.txt
```

### 3. Configure Environment

Create a `.env` file with your API keys:
```env
GEMINI_API_KEY=your_gemini_key_here
HEYGEN_API_KEY=your_heygen_key_here
SUBMAGIC_API_KEY=your_submagic_key_here
```

### 4. Run the Server

```bash
uvicorn main:app --reload
```

Access the API at http://localhost:8000/docs

---

## 🛠️ Docker Troubleshooting

### Port Already in Use

```bash
# Check what's using the port
sudo lsof -i :8000
sudo lsof -i :6379

# Stop conflicting containers
docker stop <container-name>

# Or change ports in docker-compose.yaml
ports:
  - "8080:8000"  # Use different port
```

### View Container Logs

```bash
# Follow all logs
docker compose logs -f

# View specific service
docker compose logs video-generator
docker compose logs redis

# Last 100 lines
docker compose logs --tail=100 video-generator
```

### Rebuild from Scratch

```bash
docker compose down
docker compose build --no-cache
docker compose up
```

### Access Container Shell

```bash
# Application container
docker compose exec video-generator bash

# Redis container
docker compose exec redis redis-cli
```

### Check Redis Connection

```bash
# From host
docker compose exec redis redis-cli ping

# List all jobs
docker compose exec redis redis-cli KEYS "job:*"

# Get specific job
docker compose exec redis redis-cli GET "job:YOUR_JOB_ID"
```

---

## 📚 API Reference

### POST /generate

Creates a new video generation job.

**Request:**
```json
{
  "prompt": "Your documentary topic here"
}
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### GET /status/{job_id}

Returns current job status and progress.

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "generating_video",
  "progress": 0.45,
  "created_at": "2026-01-29T10:30:00Z",
  "error": null
}
```

### GET /download/{job_id}

Returns video URL when job is complete.

**Response (complete):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "complete",
  "video_url": "https://heygen.com/video/abc123.mp4"
}
```

**Response (pending):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "generating_video",
  "message": "Video not ready yet. Check the status endpoint for progress."
}
```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Google Gemini API key for script generation |
| `HEYGEN_API_KEY` | Yes | HeyGen API key for avatar video creation |
| `SUBMAGIC_API_KEY` | Yes | Submagic API key for caption burn-in |
| `REDIS_URL` | No | Redis connection URL (default: `redis://redis:6379/0`) |
| `ELEVENLABS_API_KEY` | No | Optional, for future direct ElevenLabs integration |

### Docker Compose Configuration

Key settings in [docker-compose.yaml](docker-compose.yaml):

- **Hot Reload**: Enabled via volume mounts (development mode)
- **Health Checks**: Both Redis and FastAPI monitored
- **Auto Restart**: Containers restart on failure
- **Redis Persistence**: Data stored in Docker volume
- **Network Isolation**: Services on dedicated bridge network

To disable hot reload for production:
1. Remove volume mounts from `docker-compose.yaml`
2. Remove `--reload` flag from Dockerfile CMD

---

## 🚨 Known Limitations

* **Timing approximation**: HeyGen controls actual speech duration. The pipeline targets 30 seconds but may vary by a few seconds.
* **Background imagery**: Uses solid dark background. Could be enhanced with cinematic b-roll via additional APIs.
* **Rate limiting**: No rate limiting implemented. Add nginx with rate limiting for production.
* **Job cleanup**: Redis auto-expires jobs after 24 hours. Completed jobs should be archived if long-term storage needed.
* **Error retry**: Failed jobs are not automatically retried. Manual resubmission required.

---

## 📝 Development

### Project Structure

```
video_generation_agent/
├── main.py                  # FastAPI application
├── video_generator.py       # Video generation pipeline
├── job_storage.py          # Redis storage layer
├── requirements.txt        # Python dependencies
├── requirements-redis.txt  # Redis client
├── docker-compose.yaml     # Docker orchestration (3 services)
├── Dockerfile              # Container image
├── pytest.ini              # Test configuration
├── .env                    # API keys (not in git)
├── frontend/               # Web frontend
│   └── index.html         # Single-page application
├── tests/
│   ├── __init__.py
│   ├── test_api.py        # API integration tests
│   ├── test_video_generator.py  # Unit tests
│   └── README.md          # Test documentation
└── README.md              # This file
```

### Docker Services

The application runs three services in Docker:

1. **redis** (Port 6379)
   - Redis 7 Alpine
   - Persistent storage with volumes
   - Health checks enabled

2. **video-generator** (Port 8000)
   - FastAPI backend
   - Hot reload for development
   - Connects to Redis
   - Exposes API endpoints

3. **frontend** (Port 3000)
   - Nginx Alpine serving static HTML
   - Web interface for video generation
   - Communicates with backend API

### Adding New Features

1. **Add code**: Implement in appropriate module
2. **Add tests**: Write tests in `tests/` directory
3. **Update docs**: Document in README.md
4. **Test locally**: Run `pytest tests/ -v`
5. **Test in Docker**: Run `docker compose exec video-generator pytest tests/ -v`

### Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

---

## 🎯 Production Deployment

For production environments, consider:

1. **Security**
   - Remove `--reload` flag from Dockerfile
   - Use secrets management (AWS Secrets Manager, HashiCorp Vault)
   - Enable HTTPS with reverse proxy (nginx, Traefik)
   - Add rate limiting and request validation
   - Configure specific CORS origins instead of "*"

2. **Scalability**
   - Use gunicorn with multiple workers
   - Add horizontal scaling with load balancer
   - Implement job queue with Celery/RQ
   - Use managed Redis (AWS ElastiCache, Redis Cloud)

3. **Monitoring**
   - Add application metrics (Prometheus)
   - Set up logging aggregation (ELK stack)
   - Configure alerting (PagerDuty, Opsgenie)
   - Add health check endpoints

4. **Storage**
   - Archive completed videos to S3/Cloud Storage
   - Implement job result cleanup policy
   - Add database for long-term job history

---

## 🙏 Credits

- **FastAPI** – Modern Python web framework
- **HeyGen** – AI avatar video generation
- **Google Gemini** – Script generation
- **Submagic** – Caption generation
- **ElevenLabs** – Human-like voices (via HeyGen)
- **Redis** – Job persistence

---

## 📄 License

[Add your license here]

---

## 📞 Support

For issues and questions:
- Open an issue on GitHub
- Check [tests/README.md](tests/README.md) for testing help
- Review logs: `docker compose logs -f video-generator`
