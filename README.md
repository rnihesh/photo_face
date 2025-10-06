# Photo Face Detection System

A high-performance face detection and clustering system optimized for Apple Silicon (M4 Pro), designed to process large photo collections efficiently with a beautiful React UI.

## ✨ Features

- 🚀 **Apple Silicon Optimized** - Leverages M4 Pro's NPU and GPU using MLX and Metal Performance Shaders
- 📸 **Non-destructive** - Read-only access to your photos (never modifies originals)
- ⏸️ **Resumable** - Checkpoint system allows you to stop and resume scanning anytime
- 📊 **Progress Tracking** - Real-time progress bars at every step with tqdm and rich
- 🎯 **Face Clustering** - Automatically groups similar faces using DBSCAN algorithm
- 🌐 **Modern UI** - Beautiful React frontend with Tailwind CSS and dark mode
- 💾 **Efficient Storage** - Stores only face embeddings and metadata, not photos
- 🔄 **Real-time Updates** - API-driven architecture with FastAPI backend

## 🖥️ System Requirements

- macOS with Apple Silicon (M4 Pro recommended)
- Python 3.9+ (Python 3.13 recommended)
- Node.js 18+ (for React frontend)
- 24GB RAM (you have this!)
- Homebrew (for dependencies)

## 📦 Installation

### 1. Backend Setup

**Navigate to project directory:**

```bash
cd /Users/nihesh/Nihesh/photo_face
```

**Activate your virtual environment:**

```bash
source .venv/bin/activate
```

**All Python dependencies are already installed!** ✅
If you need to reinstall:

```bash
pip install -r requirements.txt
```

**Configure your settings:**

```bash
# Edit .env and set PHOTOS_PATH to your external drive
nano .env
```

Update this line in `.env`:

```
PHOTOS_PATH=/Volumes/Elements/
```

### 2. Frontend Setup

**Install Node dependencies:**

```bash
cd frontend
npm install
```

Frontend already has Tailwind CSS and Axios configured! ✅

## 🚀 Usage

### Step 1: Scan Photos and Detect Faces

```bash
# Make sure you're in the project root with venv activated
source .venv/bin/activate
python backend/scan_photos.py
```

**What this does:**

- Recursively scans your photos directory
- Detects faces in each photo using InsightFace (optimized for Apple Silicon)
- Generates 128-dimensional face embeddings
- Saves progress continuously (you can stop and resume anytime!)
- Shows beautiful progress bars with file names and stats

**Optional arguments:**

```bash
# Scan specific directory
python backend/scan_photos.py --path /path/to/photos

# Disable resume (reprocess all)
python backend/scan_photos.py --no-resume

# Adjust batch size
python backend/scan_photos.py --batch-size 64
```

### Step 2: Cluster Faces

```bash
python backend/cluster_faces.py
```

**What this does:**

- Groups similar face embeddings using DBSCAN algorithm
- Creates collections of the same person across multiple photos
- Shows clustering statistics and top collections

**Optional arguments:**

```bash
# Minimum faces per cluster
python backend/cluster_faces.py --min-size 5

# Clustering distance threshold (lower = stricter)
python backend/cluster_faces.py --eps 0.4
```

### Step 3: Start the API Server

```bash
cd backend
python api.py
```

Or with uvicorn directly:

```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

**API will be available at:** `http://localhost:8000`
**API docs:** `http://localhost:8000/docs`

### Step 4: Start the React Frontend

**In a new terminal:**

```bash
cd frontend
npm run dev
```

**Frontend will open at:** `http://localhost:5173`

## 🎨 Using the Web Interface

1. **Dashboard** - View overall statistics
   - Total photos processed
   - Total faces detected
   - Number of face collections
2. **Collections** - Browse and manage face collections
   - Grid view of all people detected
   - Filter by minimum photo count
   - Click on any collection to see all photos
3. **Naming People**
   - Double-click on any collection name to edit
   - Or click the edit (✏️) button
   - Press Enter to save, Escape to cancel
4. **View Photos**
   - Click on any face collection
   - See all photos of that person
   - Click on any photo to view full size
5. **Dark Mode** - Toggle with the 🌙/☀️ button in the header

## 📁 Project Structure

```
photo_face/
├── backend/
│   ├── database.py          # SQLite database models and operations
│   ├── face_detector.py     # Face detection with Apple Silicon optimization
│   ├── scan_photos.py       # Photo scanning script with progress tracking
│   ├── cluster_faces.py     # Face clustering with DBSCAN
│   └── api.py              # FastAPI REST API
├── frontend/                # React application
│   ├── src/
│   │   ├── components/
│   │   │   ├── Dashboard.jsx
│   │   │   ├── ClusterList.jsx
│   │   │   ├── ClusterCard.jsx
│   │   │   └── ClusterDetail.jsx
│   │   ├── services/
│   │   │   └── api.js       # API client with Axios
│   │   ├── App.jsx          # Main application
│   │   └── main.jsx
│   └── package.json
├── .venv/                   # Python virtual environment
├── .env                     # Configuration
├── requirements.txt         # Python dependencies
└── photo_face.db           # SQLite database (auto-created)
```

## 🔧 Configuration

Edit `.env` file to customize:

```bash
# Path to your photos
PHOTOS_PATH=/Volumes/Elements/

# Database location
DATABASE_PATH=./photo_face.db

# API settings
API_HOST=0.0.0.0
API_PORT=8000

# Processing settings
BATCH_SIZE=32
MAX_WORKERS=4

# Face detection model: 'hog' (faster) or 'cnn' (more accurate)
FACE_DETECTION_MODEL=hog

# Clustering settings
MIN_CLUSTER_SIZE=3
CLUSTER_EPSILON=0.5

# Supported image formats
IMAGE_EXTENSIONS=.jpg,.jpeg,.png,.bmp,.tiff,.tif,.heic,.heif
```

## 🧠 How It Works

### 1. **Scanning Phase**

- Recursively walks through your photo directories
- Uses InsightFace with ONNX Runtime for face detection
- Optimized for Apple Silicon with Metal acceleration
- Generates 128-dimensional face embeddings using deep learning
- Stores embeddings in SQLite database (not the photos!)

### 2. **Clustering Phase**

- Retrieves all face embeddings from database
- Normalizes embeddings for better clustering
- Uses DBSCAN (Density-Based Spatial Clustering) algorithm
- Groups similar faces together (same person across photos)
- Each cluster = one person

### 3. **UI Phase**

- FastAPI serves face collections via REST API
- React frontend displays collections in grid view
- Lazy loading for performance
- Real-time name updates via API

## 🚄 Performance Tips

- **First scan is slowest** - Subsequent scans only process new photos
- **Batch processing** - Optimizes memory usage for large collections
- **Progress is saved** - Stop anytime, resume where you left off
- **MLX & MPS** - Automatically uses Apple Silicon GPU/NPU when available
- **Read-only** - Never modifies your original photos

## 🎯 Common Workflows

### Initial Setup & First Scan

```bash
# 1. Configure
nano .env  # Set PHOTOS_PATH

# 2. Scan photos
source .venv/bin/activate
python backend/scan_photos.py

# 3. Cluster faces
python backend/cluster_faces.py

# 4. Start services (in separate terminals)
python backend/api.py
cd frontend && npm run dev
```

### Adding New Photos

```bash
# Just run scan again - it will only process new photos!
python backend/scan_photos.py

# Re-cluster to include new faces
python backend/cluster_faces.py
```

### Re-clustering with Different Parameters

```bash
# Stricter clustering (fewer, larger groups)
python backend/cluster_faces.py --eps 0.4 --min-size 5

# Looser clustering (more, smaller groups)
python backend/cluster_faces.py --eps 0.7 --min-size 2
```

## 🐛 Troubleshooting

### API Server Won't Start

```bash
# Check if port 8000 is in use
lsof -i :8000

# Try different port
API_PORT=8001 python backend/api.py
```

### Frontend Can't Connect to API

- Make sure API server is running: `http://localhost:8000/health`
- Check `.env` in frontend folder has correct `VITE_API_URL`
- CORS is configured for `localhost:5173` and `localhost:3000`

### Face Detection Not Finding Faces

- Try different model: Set `FACE_DETECTION_MODEL=cnn` in `.env`
- Check image formats are supported
- Some very low-resolution photos may not detect faces well

### Clustering Creates Too Many/Few Groups

- **Too many groups?** Increase `CLUSTER_EPSILON` (e.g., 0.7)
- **Too few groups?** Decrease `CLUSTER_EPSILON` (e.g., 0.4)
- Adjust `MIN_CLUSTER_SIZE` to change minimum faces per person

### Performance Issues

```bash
# Reduce batch size if running out of memory
python backend/scan_photos.py --batch-size 16

# Increase for faster processing (if you have RAM)
python backend/scan_photos.py --batch-size 64
```

## 🔐 Privacy & Security

- ✅ All processing happens **locally** on your Mac
- ✅ **No data** is sent to external servers
- ✅ Photos are **never modified** or copied
- ✅ Only face embeddings (numbers) are stored in database
- ✅ Database is stored locally in project folder
- ✅ You can delete the database anytime - photos remain untouched

## 📊 Database Info

The SQLite database stores:

- Photo metadata (path, size, dimensions)
- Face locations (bounding boxes)
- Face embeddings (128-dimensional vectors)
- Cluster assignments
- User-assigned names

**To reset everything:**

```bash
rm photo_face.db
# Then re-run scan and cluster
```

## 🛠️ Technology Stack

**Backend:**

- Python 3.13
- MLX - Apple's ML framework for M-series chips
- InsightFace - State-of-the-art face recognition
- PyTorch with MPS - Metal Performance Shaders
- FastAPI - Modern Python web framework
- SQLAlchemy - SQL toolkit and ORM
- scikit-learn - Machine learning (DBSCAN clustering)
- Rich & tqdm - Beautiful terminal output

**Frontend:**

- React 18
- Vite - Next generation frontend tooling
- Tailwind CSS - Utility-first CSS framework
- Axios - HTTP client

**Apple Silicon Optimizations:**

- Metal Performance Shaders (MPS) for GPU
- ONNX Runtime for optimized inference
- Native ARM64 compilation
- Batch processing for efficiency

## 📝 License

MIT License - Feel free to use and modify!

## 🙏 Acknowledgments

- InsightFace team for excellent face recognition models
- Apple for MLX and Metal Performance Shaders
- All the amazing open-source contributors

---

**Built with ❤️ for Apple Silicon M4 Pro**
