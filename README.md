# Multi-Model RAG Chatbot with Electron Frontend

A sophisticated Retrieval-Augmented Generation (RAG) chatbot application with a modern Electron-based frontend and Python backend for multi-modal document processing (text, images, audio, video).

---

## 📋 Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Getting Started](#getting-started)
- [New Feature: Clickable Source Files](#new-feature-clickable-source-files)
- [Backend Integration](#backend-integration)
- [Project Structure](#project-structure)
- [Contributing](#contributing)

---

## ✨ Features

### Frontend (Electron)
- 🎨 Modern, ChatGPT-like interface with dark/light themes
- 💬 Real-time chat with streaming responses
- 🎤 Voice input with speech-to-text support
- 📁 Multi-format document upload (PDF, DOCX, TXT, images, videos, audio)
- 📂 Folder upload for batch processing
- 📸 Webcam capture for image queries
- 🔍 Chat history with search functionality
- 📌 **NEW**: Clickable source chips that open retrieved documents
- 🎭 Custom background themes

### Backend (Python - In Development)
- 🧠 Multi-model RAG pipeline
- 📊 Vector database integration for semantic search
- 🖼️ Image processing with OCR and captioning
- 🎵 Audio transcription and processing
- 🎬 Video analysis capabilities
- 💾 Efficient caching layer
- 📦 Chunking and embedding storage

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Electron Frontend                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Renderer   │  │   Preload    │  │     Main     │ │
│  │   (UI/React) │◄─┤   (Bridge)   │◄─┤   (Node.js)  │ │
│  └──────────────┘  └──────────────┘  └──────┬───────┘ │
└────────────────────────────────────────────────┼────────┘
                                                  │
                                                  │ IPC
                                                  │
┌─────────────────────────────────────────────────┼────────┐
│                  RAG Service Layer              │        │
│                 (ragService.js)                 │        │
└─────────────────────────────────────────────────┼────────┘
                                                  │
                                                  │ HTTP/API
                                                  │
┌─────────────────────────────────────────────────▼────────┐
│                    Python Backend                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Data Layer  │  │ Cache Layer  │  │  Vector DB   │  │
│  │ (Ingestion)  │◄─┤  (Redis)     │◄─┤  (Chroma)    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└──────────────────────────────────────────────────────────┘
```

---

## 🚀 Getting Started

### Prerequisites
- Node.js 18+ and npm
- Python 3.8+ (for backend)
- Git

### Frontend Setup

```bash
# Navigate to frontend directory
cd Frontend

# Install dependencies
npm install

# Start the Electron app
npm start

# Build for production (optional)
npm run make
```

### Backend Setup (Coming Soon)

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the backend server
python main.py
```

---

## 🆕 New Feature: Clickable Source Files

### What's New?

Users can now **click on source chips** to instantly open the retrieved documents in their system's default application!

![Source Chips Demo](docs/source-chips-demo.gif)

### How It Works

1. **User asks a question** → "What was the revenue in 2023?"
2. **RAG retrieves relevant documents** → Finds chunks from annual_report_2023.pdf
3. **Frontend displays sources** → Shows clickable chip below response
4. **User clicks source chip** → PDF opens in Adobe Reader/Browser

### Visual Feedback

- **Hoverable**: Chips highlight with accent color on hover
- **Clickable**: Cursor changes to pointer
- **Tooltip**: Shows full file path
- **Cross-platform**: Works on Windows, macOS, Linux

### Example

```javascript
// Backend Response Format
{
  "text": "The revenue in 2023 was $10M, showing 15% growth...",
  "sources": [
    {
      "name": "annual_report_2023.pdf",
      "path": "C:\\Users\\your-username\\Documents\\annual_report_2023.pdf"
    },
    {
      "name": "financial_summary_Q4.xlsx",
      "path": "/home/user/documents/financial_summary_Q4.xlsx"
    }
  ]
}
```

**Result in UI:**
```
Bot Response:
"The revenue in 2023 was $10M, showing 15% growth..."

Sources:
┌─────────────────────────────┐  ┌────────────────────────────────┐
│ 📄 annual_report_2023.pdf   │  │ 📊 financial_summary_Q4.xlsx   │
└─────────────────────────────┘  └────────────────────────────────┘
    (Click to open)                    (Click to open)
```

---

## 🔌 Backend Integration

### For Backend Developers

The frontend is **ready to integrate** with your Python RAG backend. Here's what you need to know:

#### 1. Response Format (CRITICAL)

Your RAG endpoint MUST return this exact format:

```python
{
    "text": str,              # LLM response (supports Markdown)
    "sources": [              # Array of source documents
        {
            "name": str,      # Filename to display
            "path": str       # ABSOLUTE path to file
        }
    ]
}
```

#### 2. Store File Paths During Upload

When users upload documents:

```python
# Store the original file path in vector DB metadata
for file_path in uploaded_files:
    chunks = process_document(file_path)
    for chunk in chunks:
        vector_db.add(
            text=chunk.text,
            embedding=chunk.embedding,
            metadata={
                "source_file": file_path,        # ← Store absolute path
                "file_name": os.path.basename(file_path),
                "page": chunk.page,
                "chunk_index": chunk.index
            }
        )
```

#### 3. Return Paths During Query

When processing queries:

```python
# After RAG retrieval
retrieved_chunks = vector_db.search(query_embedding, top_k=5)

# Extract unique source files
sources = []
seen_paths = set()

for chunk in retrieved_chunks:
    path = chunk.metadata["source_file"]
    name = chunk.metadata["file_name"]

    if path not in seen_paths:
        sources.append({"name": name, "path": path})
        seen_paths.add(path)

return {
    "text": llm_generated_response,
    "sources": sources
}
```

#### 📚 Complete Integration Documentation

- **Full Guide**: [`BACKEND_INTEGRATION_GUIDE.md`](BACKEND_INTEGRATION_GUIDE.md)
- **Quick Reference**: [`backend/FRONTEND_RESPONSE_FORMAT.md`](backend/FRONTEND_RESPONSE_FORMAT.md)
- **Architecture Flow**: [`FILE_OPENING_FLOW.md`](FILE_OPENING_FLOW.md)
- **Frontend Details**: [`Frontend/FILE_OPENING_FEATURE.md`](Frontend/FILE_OPENING_FEATURE.md)

---

## 📁 Project Structure

```
multi_model_rag_for_searching/
│
├── Frontend/                          # Electron frontend application
│   ├── src/
│   │   ├── index.js                  # Main process (Electron entry)
│   │   ├── preload.js                # Security bridge (IPC)
│   │   ├── renderer.js               # UI logic and interactions
│   │   ├── index.html                # Main HTML template
│   │   ├── index.css                 # Styling
│   │   └── services/
│   │       └── ragService.js         # Backend communication layer
│   ├── package.json
│   └── FILE_OPENING_FEATURE.md       # Feature documentation
│
├── backend/                           # Python RAG backend
│   ├── data_layer/                   # Document processing
│   │   ├── ingest/                   # File ingestion pipelines
│   │   │   ├── Text_files_processing/
│   │   │   ├── ImageProcessing/
│   │   │   ├── audio_processing/
│   │   │   ├── chunker.py
│   │   │   └── storage/              # Vector DB operations
│   │   └── chunkstore/               # Chunk storage
│   ├── cache_layer/                  # Caching system
│   ├── config.py                     # Configuration
│   ├── requirements.txt              # Python dependencies
│   └── FRONTEND_RESPONSE_FORMAT.md   # Quick ref for backend devs
│
├── BACKEND_INTEGRATION_GUIDE.md      # Complete integration guide
├── FILE_OPENING_FLOW.md              # Architecture documentation
└── README.md                         # This file
```

---

## 🛠️ Development

### Frontend Development

```bash
cd Frontend

# Install dependencies
npm install

# Start in development mode (with hot reload)
npm start

# Open DevTools automatically
# Edit src/index.js and set: mainWindow.webContents.openDevTools()
```

### Key Frontend Files

- **`src/renderer.js`**: All UI logic, message handling, source chip creation
- **`src/index.js`**: Main process, IPC handlers, file operations
- **`src/preload.js`**: Security bridge between renderer and main
- **`src/services/ragService.js`**: Backend communication (replace with real API)

### Backend Development

The backend structure is already set up for:
- Text processing (PDF, DOCX, TXT)
- Image processing (OCR, captioning, visual embeddings)
- Audio processing (transcription, Whisper integration)
- Vector database storage (HNSW, embeddings)
- Caching layer

**Next Steps for Backend:**
1. Implement API endpoints for frontend communication
2. Ensure file paths are stored in vector DB metadata
3. Return responses in the correct format (see `FRONTEND_RESPONSE_FORMAT.md`)

---

## 🧪 Testing

### Test File Opening Feature

1. **With Mock Data** (Current Setup):
   ```bash
   cd Frontend
   npm start
   # Type any message, click source chips
   # Note: Files won't open (mock paths don't exist)
   ```

2. **With Real Backend** (After Integration):
   - Upload a real document through the UI
   - Ask a question about that document
   - Click the source chip
   - Verify file opens in system default app

### Debug Mode

Open DevTools (F12) to see:
- Console logs for IPC communication
- Network requests to backend
- Source chip click events
- Error messages

---

## 🎯 Roadmap

### ✅ Completed
- [x] Electron frontend with modern UI
- [x] Multi-format document upload
- [x] Chat interface with history
- [x] Voice input support
- [x] Theme customization
- [x] **Clickable source files with system integration**

### 🚧 In Progress
- [ ] Python RAG backend implementation
- [ ] Vector database integration
- [ ] LLM integration (OpenAI/local models)
- [ ] Multi-modal processing pipelines

### 📋 Planned
- [ ] Real-time collaboration
- [ ] Advanced search filters
- [ ] Export conversations
- [ ] Custom model selection
- [ ] API key management UI

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### For Backend Developers

If you're working on the Python backend:
1. Read [`BACKEND_INTEGRATION_GUIDE.md`](BACKEND_INTEGRATION_GUIDE.md) first
2. Ensure responses match the required format
3. Test with the Electron frontend before submitting PR
4. Document any new endpoints or features

---

## 📄 License

MIT License - See LICENSE file for details

---

## 👥 Authors

- **Frankythecoder** - Frontend Architect & Integration Design

---

## 🙏 Acknowledgments

- Electron team for the amazing framework
- OpenAI for GPT models and inspiration
- Anthropic for Claude models
- The open-source community

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/multi-model-rag/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/multi-model-rag/discussions)
- **Documentation**: See `docs/` folder

---

**Status**: 🟢 Frontend Complete | 🟡 Backend In Development

**Last Updated**: February 6, 2026
