#!/bin/bash

# AI Video Generation Platform - Management Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if .env file exists
check_env() {
    if [ ! -f .env ]; then
        print_warning ".env file not found. Creating from template..."
        cp .env.example .env
        print_error "Please edit .env file and add your KIEAI_API_KEY before continuing."
        exit 1
    fi
    
    if ! grep -q "KIEAI_API_KEY=" .env || grep -q "your_kieai_api_key_here" .env; then
        print_error "Please set your KIEAI_API_KEY in the .env file."
        exit 1
    fi
    
    print_success ".env file configured correctly."
}

# Function to start the services
start() {
    print_status "Starting AI Video Generation Platform..."
    check_env
    
    print_status "Building and starting Docker containers..."
    docker-compose up --build -d
    
    print_success "Services started successfully!"
    print_status "Frontend: http://localhost:3000"
    print_status "Backend API: http://localhost:8000"
    print_status "API Docs: http://localhost:8000/docs"
    
    echo ""
    print_status "To view logs: ./manage.sh logs"
    print_status "To stop: ./manage.sh stop"
}

# Function to stop the services
stop() {
    print_status "Stopping AI Video Generation Platform..."
    docker-compose down
    print_success "Services stopped successfully!"
}

# Function to restart the services
restart() {
    print_status "Restarting AI Video Generation Platform..."
    stop
    start
}

# Function to view logs
logs() {
    if [ -z "$2" ]; then
        print_status "Showing logs for all services (Ctrl+C to exit)..."
        docker-compose logs -f
    else
        print_status "Showing logs for $2 service (Ctrl+C to exit)..."
        docker-compose logs -f "$2"
    fi
}

# Function to check status
status() {
    print_status "Checking service status..."
    docker-compose ps
}

# Function to clean up everything
clean() {
    print_warning "This will remove all containers, images, and volumes. Are you sure? (y/N)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        print_status "Cleaning up..."
        docker-compose down -v --rmi all --remove-orphans
        print_success "Cleanup completed!"
    else
        print_status "Cleanup cancelled."
    fi
}

# Function to update the platform
update() {
    print_status "Updating AI Video Generation Platform..."
    stop
    print_status "Rebuilding containers..."
    docker-compose build --no-cache
    start
}

# Function to show help
show_help() {
    echo "AI Video Generation Platform - Management Script"
    echo ""
    echo "Usage: $0 {start|stop|restart|logs|status|clean|update|help}"
    echo ""
    echo "Commands:"
    echo "  start     Start the platform"
    echo "  stop      Stop the platform"
    echo "  restart   Restart the platform"
    echo "  logs      Show logs (add service name for specific service)"
    echo "  status    Show service status"
    echo "  clean     Remove all containers, images, and volumes"
    echo "  update    Rebuild and restart the platform"
    echo "  help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start"
    echo "  $0 logs backend"
    echo "  $0 logs frontend"
}

# Main script logic
case "${1:-help}" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    logs)
        logs "$@"
        ;;
    status)
        status
        ;;
    clean)
        clean
        ;;
    update)
        update
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac