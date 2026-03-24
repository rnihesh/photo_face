# Photo Face Detection System

A high-performance face detection and clustering system optimized for Apple Silicon (M4 Pro), designed to process large photo collections efficiently with a beautiful React UI.

## ✨ Features

- 🚀 **Apple Silicon Optimized** - Leverages M4 Pro's NPU and GPU using MLX and Metal Performance Shaders
- 📸 **Non-destructive** - Read-only access to your photos (never modifies originals)
- ⏸️ **Resumable** - Checkpoint system allows you to stop and resume scanning anytime
- 📊 **Progress Tracking** - Real-time progress bars at every step with tqdm and rich
- 🎯 **Stable Face Clustering** - Uses incremental clustering with stable cluster IDs instead of raw DBSCAN labels
- 🌐 **Modern UI** - Beautiful React frontend with Tailwind CSS and dark mode
- 💾 **Efficient Storage** - Stores only face embeddings and metadata, not photos
- 🔄 **Incremental Sync** - Backend detects only new or changed photos when the drive is available
- 🧠 **Learned Corrections** - Manual exclusions and reassignments improve later clustering
- 🧰 **Redis Runtime State** - Sync status, locks, and API caching use Redis when available

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

### Step 1: Configure the Photo Library and Redis

```bash
cp .env.example .env
nano .env
```

Recommended settings:

```bash
PHOTOS_PATH=/Volumes/Elements
REDIS_URL=redis://localhost:6379/0
AUTO_SYNC_ON_STARTUP=true
```

### Step 2: Start the API Server

```bash
cd /Users/nihesh/Nihesh/photo_face
source .venv/bin/activate
python backend/api.py
```

**What this does on startup:**

- Checks whether `PHOTOS_PATH` is available
- Detects only new or modified photos
- Processes only those files
- Reclusters only when there are new embeddings or pending cluster work

You can also trigger sync manually from the UI or `POST /sync/run`.

### Step 3: Optional CLI Scan

```bash
# Make sure you're in the project root with venv activated
source .venv/bin/activate
python backend/scan_photos.py
```

**What this does:**

- Recursively scans your photos directory
- Detects faces in each photo using local open-source face-recognition models
- Generates 128-dimensional face embeddings
- Saves progress continuously (you can stop and resume anytime!)
- Shows beautiful progress bars with file names and stats

**Optional arguments:**

```bash
# Scan specific directory
python backend/scan_photos.py --path /path/to/photos

# Disable resume (reprocess all)
python backend/scan_photos.py --no-resume

```

### Step 4: Optional CLI Rebuild

```bash
python backend/cluster_faces.py --rebuild
```

**What this does:**

- Rebuilds clusters using the current incremental clustering algorithm
- Preserves locked or manually named clusters where possible
- Reuses manual corrections as positive or negative learning signals

If you want a clean recluster without deleting scanned faces, run this first:

```bash
python backend/reset_clustering.py
```

**Optional arguments:**

```bash
# Minimum faces per cluster
python backend/cluster_faces.py --rebuild --min-size 5

# Clustering distance threshold (lower = stricter)
python backend/cluster_faces.py --rebuild --eps 0.28
```

Or with uvicorn directly:

```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

**API will be available at:** `http://localhost:8000`
**API docs:** `http://localhost:8000/docs`

### Step 5: Start the React Frontend

**In a new terminal:**

```bash
cd /Users/nihesh/Nihesh/photo_face/frontend
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
   - Search by name or cluster id
   - Filter by minimum photo count
   - Click on any collection to see all photos
3. **Naming People**
   - Rename clusters from the card or detail view
   - Naming a person locks that cluster as a stronger identity seed
4. **View Photos**
   - Click on any face collection
   - Exclude wrong matches or move a face to another person
   - Set a representative face for the cluster
   - Click on any photo to view the original image
5. **Sync Status**
   - Header shows whether the backend is discovering, processing, clustering, waiting, or ready
   - Trigger incremental sync directly from the UI

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
API_RELOAD=false

# Face detection model: 'hog' (faster) or 'cnn' (more accurate)
FACE_DETECTION_MODEL=hog
SCAN_WORKERS=0
ENABLE_FILE_HASH=false
PREBUILD_FACE_CROPS=false

# Clustering settings
MIN_CLUSTER_SIZE=3
CLUSTER_DBSCAN_EPSILON=0.34
CLUSTER_REFINE_EPSILON=0.36
CLUSTER_ASSIGN_EPSILON=0.30
LOCKED_CLUSTER_ASSIGN_EPSILON=0.28
CLUSTER_MERGE_EPSILON=0.29
CLUSTER_ASSIGN_MARGIN=0.04

# Supported image formats
IMAGE_EXTENSIONS=.jpg,.jpeg,.png,.bmp,.tiff,.tif,.heic,.heif
```

## 🧠 How It Works

### 1. **Scanning Phase**

- Recursively walks through your photo directories
- Uses local open-source face-recognition models for detection and embeddings
- Can use Apple Silicon acceleration where available
- Generates 128-dimensional face embeddings
- Stores embeddings in SQLite database (not the photos!)

### 2. **Clustering Phase**

- Retrieves all face embeddings from database
- Uses raw Euclidean face distances instead of over-normalized cosine distances
- Uses DBSCAN plus a refinement pass to stop giant chain-merged clusters
- Groups similar faces together (same person across photos)
- Each cluster = one person

### 3. **UI Phase**

- FastAPI serves face collections via REST API
- React frontend displays collections in grid view
- Lazy loading for performance
- Real-time name updates via API

## 🚄 Performance Tips

- **First scan is slowest** - Subsequent scans only process new photos
- **Incremental processing** - New scans only touch new, changed, or pending photos
- **Parallel scan workers** - Set `SCAN_WORKERS` above `0` to process multiple photos at once
- **Hashing disabled by default** - `ENABLE_FILE_HASH=false` avoids rereading every full file unnecessarily
- **HDD-friendly browsing** - `PREBUILD_FACE_CROPS=true` warms face thumbnails onto local cache during scan
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
# More conservative clustering (more unclustered faces, fewer false merges)
python backend/cluster_faces.py --eps 0.32 --min-size 3

# More merging (fewer groups, higher risk of mixing people)
python backend/cluster_faces.py --eps 0.38 --min-size 3
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

- **Too many unclustered faces or too many small groups?** Increase `CLUSTER_DBSCAN_EPSILON` slightly, for example `0.34 -> 0.35`
- **Too many people merged together?** Decrease `CLUSTER_DBSCAN_EPSILON` slightly, for example `0.34 -> 0.33`
- Adjust `MIN_CLUSTER_SIZE` to change minimum faces per person

### Performance Issues

- Keep Redis running if you want cached API responses and sync status shared across processes
- Use `FACE_DETECTION_MODEL=hog` unless you have a good reason to trade speed for accuracy

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
