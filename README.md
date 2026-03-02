# 🎬 AI Video Generation Platform

A complete video generation platform using multiple AI services: Gemini for planning, Flux for avatar generation, and Veo for video creation.

## 🌟 Features

- **Modern Web Interface**: Clean, responsive frontend with real-time progress tracking
- **AI Pipeline**: Gemini → Flux → Veo for comprehensive video generation
- **Docker Ready**: Complete containerization with docker-compose
- **Real-time Status**: Live progress updates and detailed logging
- **Video Download**: Direct download of generated videos

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose installed
- KIE AI API Key

### Setup

1. **Clone and Navigate**
   ```bash
   cd /home/umar/Desktop/video_generation
   ```

2. **Environment Variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your KIEAI_API_KEY
   ```

3. **Build and Run**
   ```bash
   docker-compose up --build
   ```

4. **Access the Application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

## 📁 Project Structure

```
video_generation/
├── frontend/
│   └── index.html              # Web interface
├── final.py                    # Main FastAPI backend
├── generate_avatar.py          # Avatar generation utilities
├── generate_quality_video.py   # Video quality utilities
├── generate_video.py          # Video generation utilities
├── requirements.txt           # Python dependencies
├── Dockerfile.backend         # Backend container
├── Dockerfile.frontend        # Frontend container
├── docker-compose.yaml       # Container orchestration
├── nginx.conf                # Frontend proxy config
├── .env.example              # Environment template
└── README.md                 # This file
```

## 🔧 Configuration

### Environment Variables

- `KIEAI_API_KEY`: Your KIE AI API key (required)

### Docker Compose Services

- **backend**: FastAPI application (port 8000)
- **frontend**: Nginx-served web interface (port 3000)

## 🎯 Usage

1. **Open the Web Interface**
   Navigate to http://localhost:3000

2. **Enter Your Prompt**
   Describe the video you want to create, for example:
   "A mystical journey through the four elements with a wise narrator"

3. **Watch Progress**
   The interface will show real-time progress through these stages:
   - Planning (Gemini analysis)
   - Avatar generation (Flux)
   - Video creation (Veo)
   - Final assembly (FFmpeg)

4. **Download Your Video**
   Once complete, preview and download your generated video

## 🛠 API Endpoints

- `POST /jobs` - Create new video generation job
- `GET /jobs/{job_id}` - Get job status and progress
- `GET /jobs/{job_id}/download` - Download completed video

## 📊 Monitoring

- **Real-time Logs**: View processing logs in the web interface
- **Progress Tracking**: Visual progress bar with percentage
- **Status Updates**: Current step and completion status
- **Health Checks**: Docker health monitoring for both services

## 🔍 Troubleshooting

### Common Issues

1. **API Key Error**
   ```
   RuntimeError: KIEAI_API_KEY not found in .env
   ```
   Solution: Ensure your .env file contains a valid KIEAI_API_KEY

2. **Port Conflicts**
   If ports 3000 or 8000 are in use, modify docker-compose.yaml:
   ```yaml
   ports:
     - "3001:80"  # Change frontend port
     - "8001:8000"  # Change backend port
   ```

3. **Build Issues**
   ```bash
   # Clean rebuild
   docker-compose down
   docker-compose build --no-cache
   docker-compose up
   ```

### Logs

View logs for debugging:
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
```

## 🏗 Development

### Local Development (without Docker)

1. **Backend**
   ```bash
   pip install -r requirements.txt
   uvicorn final:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Frontend**
   Serve the frontend directory with any static server, or use:
   ```bash
   cd frontend
   python -m http.server 3000
   ```

### Extending the Platform

- **Custom Prompts**: Modify the prompt templates in `final.py`
- **UI Improvements**: Edit `frontend/index.html`
- **Additional Services**: Add new containers to `docker-compose.yaml`

## 📝 License

This project is for educational and development purposes.

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

---

Made with ❤️ using FastAPI, Docker, and AI