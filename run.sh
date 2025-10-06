#!/bin/bash

# Photo Face Detection System - Startup Script
# This script helps you easily run different parts of the system

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}   Photo Face Detection System${NC}"
echo -e "${BLUE}   Optimized for Apple Silicon M4 Pro${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env file not found!${NC}"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo -e "${GREEN}✓ Created .env file${NC}"
    echo -e "${YELLOW}📝 Please edit .env and set your PHOTOS_PATH${NC}"
    echo ""
fi

# Function to activate venv
activate_venv() {
    if [ -d ".venv" ]; then
        source .venv/bin/activate
        echo -e "${GREEN}✓ Virtual environment activated${NC}"
    else
        echo -e "${RED}❌ Virtual environment not found at .venv${NC}"
        echo "Please create it first: python3 -m venv .venv"
        exit 1
    fi
}

# Function to check if API is running
check_api() {
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Menu
show_menu() {
    echo ""
    echo "What would you like to do?"
    echo ""
    echo "  ${GREEN}1${NC}) 📸 Scan photos (detect faces)"
    echo "  ${GREEN}2${NC}) 🧩 Cluster faces (group similar faces)"
    echo "  ${GREEN}3${NC}) 🚀 Start API server"
    echo "  ${GREEN}4${NC}) 🌐 Start React frontend"
    echo "  ${GREEN}5${NC}) 🔥 Start everything (API + Frontend)"
    echo "  ${GREEN}6${NC}) 📊 View statistics"
    echo "  ${GREEN}7${NC}) 🗑️  Reset database"
    echo "  ${GREEN}0${NC}) 👋 Exit"
    echo ""
}

# Scan photos
scan_photos() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}   Scanning Photos${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    activate_venv
    python backend/scan_photos.py "$@"
}

# Cluster faces
cluster_faces() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}   Clustering Faces${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    activate_venv
    python backend/cluster_faces.py "$@"
}

# Start API
start_api() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}   Starting API Server${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    activate_venv
    cd backend
    echo -e "${GREEN}🚀 API will be available at http://localhost:8000${NC}"
    echo -e "${GREEN}📚 API docs at http://localhost:8000/docs${NC}"
    echo ""
    python api.py
}

# Start frontend
start_frontend() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}   Starting React Frontend${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    cd frontend
    
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}Installing dependencies...${NC}"
        npm install
    fi
    
    echo -e "${GREEN}🌐 Frontend will be available at http://localhost:5173${NC}"
    echo ""
    npm run dev
}

# Start both
start_all() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}   Starting API + Frontend${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    # Check if API is already running
    if check_api; then
        echo -e "${GREEN}✓ API server already running${NC}"
    else
        echo -e "${YELLOW}Starting API server in background...${NC}"
        activate_venv
        cd backend
        python api.py > ../api.log 2>&1 &
        API_PID=$!
        echo $API_PID > ../api.pid
        cd ..
        echo -e "${GREEN}✓ API server started (PID: $API_PID)${NC}"
        echo -e "  Log: api.log"
        
        # Wait for API to be ready
        echo -n "Waiting for API to be ready"
        for i in {1..10}; do
            if check_api; then
                echo ""
                echo -e "${GREEN}✓ API is ready!${NC}"
                break
            fi
            echo -n "."
            sleep 1
        done
    fi
    
    echo ""
    echo -e "${GREEN}🚀 API: http://localhost:8000${NC}"
    echo -e "${GREEN}🌐 Frontend: http://localhost:5173${NC}"
    echo ""
    
    # Start frontend (this will block)
    start_frontend
}

# View stats
view_stats() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}   Database Statistics${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    activate_venv
    python -c "
from backend.database import DatabaseManager
from rich.console import Console
from rich.table import Table

db = DatabaseManager()
stats = db.get_stats()
console = Console()

table = Table(title='Photo Face Detection Statistics', show_header=True)
table.add_column('Metric', style='cyan', no_wrap=True)
table.add_column('Value', style='green')

table.add_row('Total Photos', str(stats['total_photos']))
table.add_row('Processed Photos', str(stats['processed_photos']))
table.add_row('Total Faces', str(stats['total_faces']))
table.add_row('Face Collections', str(stats['total_clusters']))
table.add_row('Named Collections', str(stats['named_clusters']))

console.print(table)
"
}

# Reset database
reset_database() {
    echo ""
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}   ⚠️  Reset Database${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${YELLOW}This will delete all scanned data and face collections.${NC}"
    echo -e "${YELLOW}Your photos will NOT be affected.${NC}"
    echo ""
    read -p "Are you sure? (yes/no): " confirm
    
    if [ "$confirm" = "yes" ]; then
        if [ -f "photo_face.db" ]; then
            rm photo_face.db
            echo -e "${GREEN}✓ Database deleted${NC}"
            echo -e "${BLUE}Run scan and cluster again to rebuild.${NC}"
        else
            echo -e "${YELLOW}No database found.${NC}"
        fi
    else
        echo -e "${BLUE}Cancelled.${NC}"
    fi
}

# Main menu loop
if [ $# -eq 0 ]; then
    while true; do
        show_menu
        read -p "Enter your choice (0-7): " choice
        
        case $choice in
            1) scan_photos ;;
            2) cluster_faces ;;
            3) start_api ;;
            4) start_frontend ;;
            5) start_all ;;
            6) view_stats ;;
            7) reset_database ;;
            0) 
                echo ""
                echo -e "${BLUE}👋 Goodbye!${NC}"
                echo ""
                
                # Kill API if we started it
                if [ -f "api.pid" ]; then
                    API_PID=$(cat api.pid)
                    if ps -p $API_PID > /dev/null; then
                        echo "Stopping API server..."
                        kill $API_PID
                    fi
                    rm api.pid
                fi
                
                exit 0
                ;;
            *) 
                echo -e "${RED}Invalid option. Please try again.${NC}"
                ;;
        esac
        
        echo ""
        read -p "Press Enter to continue..."
    done
else
    # Command line arguments provided
    case "$1" in
        scan) scan_photos "${@:2}" ;;
        cluster) cluster_faces "${@:2}" ;;
        api) start_api ;;
        frontend) start_frontend ;;
        start) start_all ;;
        stats) view_stats ;;
        reset) reset_database ;;
        *)
            echo "Usage: $0 [scan|cluster|api|frontend|start|stats|reset]"
            echo ""
            echo "Commands:"
            echo "  scan      - Scan photos and detect faces"
            echo "  cluster   - Cluster detected faces"
            echo "  api       - Start API server"
            echo "  frontend  - Start React frontend"
            echo "  start     - Start both API and frontend"
            echo "  stats     - View database statistics"
            echo "  reset     - Reset database"
            echo ""
            echo "Or run without arguments for interactive menu."
            exit 1
            ;;
    esac
fi
