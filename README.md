# Multi-Model RAG for Searching

A professional-grade, multi-modal Retrieval-Augmented Generation (RAG) system with a modern Electron frontend and a robust FastAPI Python backend. This project features a full chat interface with authentication, document management, and AI-driven document search and Q&A.

## ✨ Features

- **Multi-Modal Support**: Process and search through various file types including text, documents (PDF, DOCX), audio, video, and images.
- **Modern User Interface**: A ChatGPT-style Electron application supporting multi-document previews, real-time message streaming, and an intuitive chat window.
- **Speech Queries**: Record and upload voice prompts directly from the user interface.
- **Robust Authentication**: JWT-based login, registration, and session token refreshing securely backed by PostgreSQL endpoints.
- **Locally Run RAG Pipeline**: Built with advanced chunking, FAISS-based vector database integration, and LLM-powered answer generation.
- **Dockerized Setup**: Easily orchestrated using `docker-compose` to run the frontend and backend uniformly.

## 🏗 Architecture layout

The application is cleanly decoupled into two main environments:

### 1. Frontend (`/Frontend`)

An **Electron** desktop application.

- **Architecture**: Separates the Node.js main process from the UI renderer process.
- **Communication**: Interfaces strictly with backend standard HTTP endpoints.
- **Tech Stack**: Electron, Vanilla JavaScript, HTML/CSS.

### 2. Backend (`/backend`)

A **FastAPI Python** server doing the heavy lifting.

- **Core Engine**: Handles vector embeddings, document chunking, LLM ingestion, and RAG retrieval pipelines.
- **System Services**: Orchestrates PostgreSQL (state management and history caching) alongside FAISS (vector similarity search).
- **Tech Stack**: FastAPI, PyTorch, Transformers, Sentence-Transformers, Llama.cpp, SQLAlchemy, FAISS, and PostgreSQL.

---

## 🚀 Getting Started

You can run the application either easily through Docker or by setting up the individual components manually.

### Option 1: Docker Compose (Recommended)

Make sure you have [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/) installed on your machine.

```bash
# Clone the repository
git clone <your-repository-url>
cd multi_model_rag_for_searching

# Build and spin up the backend and frontend services
docker-compose up --build
```

The Electron app should pop up automatically after the backend initializes.

### Option 2: Manual Setup

**Backend Setup**

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create the necessary environment variables
cp .env.example .env

# Run the backend server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

_Note: Make sure your local PostgreSQL and FAISS dependancies are properly configured per details inside `backend/BACKEND_INTEGRATION_GUIDE.md`._

**Frontend Setup**

```bash
cd Frontend
npm install

# Start the Electron User Interface
npm start
```

## 📖 Related Documentation

- [Backend Integration API Guide](./BACKEND_INTEGRATION_GUIDE.md)
- [Frontend Development Details](./Frontend/README.md)
- [Frontend Response Format Constraints](./backend/FRONTEND_RESPONSE_FORMAT.md)
- [File Opening Architecture Flow](./FILE_OPENING_FLOW.md)

## 🤝 Contributing

Contributions are welcome. Please fork the repository and raise a pull request for review.
For the backend contributions , kindly visit the todo.txt file to see the things that are to be done
And for the frontend any creative design and bugs fixes are welcomed

