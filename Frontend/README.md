# RAG Chatbot Professional - Frontend Documentation

This project is a professional-grade Electron-based frontend for a RAG (Retrieval-Augmented Generation) Chatbot. It features a ChatGPT-style UI with document management, chat history, speech-to-text queries, and real-time streaming simulations.

## ✨ Key Features
- **Multi-Modal Uploads**: Support for Documents, Videos, Audio, and Images.
- **Speech Queries**: Record voice prompts directly in the UI (MP3 format).
- **ChatGPT UI**: Modern, responsive layout with staged document previews.
- **Real-time Streaming**: Simulated token-by-token response generation.

## 🏗 Project Architecture

The application follows the Electron standard architecture, separating the **Main Process** (System/Node.js) from the **Renderer Process** (UI).

- **Main Process (`Frontend/src/index.js`)**: Handles window management, OS-level file dialogs, and simulated data storage.
- **Preload Script (`Frontend/src/preload.js`)**: A secure bridge that exposes specific Electron APIs to the frontend via `window.electronAPI`.
- **Renderer Process (`Frontend/src/renderer.js`)**: Manages the UI state, DOM updates, and user interactions.
- **Service Layer (`Frontend/src/services/ragService.js`)**: Contains the core logic for chatting and uploading. **This is the primary integration point for the backend.**

---

## 📂 File-by-File Explanation

### 1. `Frontend/src/index.js` (Main Process)
- **IPC Handlers**: Listens for requests from the frontend (e.g., `chat:send`, `chat:send-speech`, `documents:upload`).
- **Speech Support**: Receives raw MP3 buffers from the renderer and passes them to the service layer.
- **File Dialogs**: Uses Electron's `dialog.showOpenDialog` to allow users to select multiple documents, videos, audio, or images from their local system.

### 2. `Frontend/src/services/ragService.js` (RAG Logic)
This file simulates the RAG pipeline. To integrate a real backend, replace these methods with `fetch` or `axios` calls to your API.
- **`getResponse(message)`**: 
    - *Current*: Simulates a 1.5s delay, returns a mock markdown response, and randomly picks "sources".
    - *Integration*: Should POST the user message to your backend and return the LLM response + source metadata.
- **`processSpeechQuery(audioBuffer, fileName)`**:
    - *Current*: Receives a Node.js Buffer containing MP3 data, simulates transcription delay, and returns a mock response.
    - *Integration*: Should upload the MP3 buffer to your STT service (e.g., OpenAI Whisper), transcribe it, and then run the standard RAG flow on the text.
- **`uploadDocuments(filePaths, type)`**:
    - *Current*: Simulates a 2s delay and returns a success message.
    - *Integration*: Should send the file paths (or upload the files themselves) to your backend for chunking, embedding, and storage in a Vector DB.

### 3. `Frontend/src/renderer.js` (UI Logic)
- **State Management**:
    - `currentSession`: Tracks the active chat messages and session metadata.
    - `uploadedDocs`: A temporary "staging" area for files uploaded or **recorded audio** (MP3) before sending.
- **Key Functions**:
    - `toggleRecording()`: Uses the MediaRecorder API to capture audio, converts it to an MP3-compatible blob, and stages it for sending.
    - `renderUploadedDocs()`: Dynamically updates the preview area with document icons or a microphone icon for audio queries.
    - `handleSendMessage()`: Orchestrates sending text or **speech queries**, triggering the "streaming" bot response.

### 4. `Frontend/src/index.html` & `index.css`
- **Mic Icon**: A new interactive mic button with a pulsing recording animation.
- **Input Area**: Optimized for multi-document previews with a auto-expanding textarea.

---

## 🚀 Backend Integration

**For complete integration instructions**, see the main documentation:
- **Quick Start**: `../BACKEND_DEVELOPER_START_HERE.md` (5 minutes)
- **Full Guide**: `../BACKEND_INTEGRATION_GUIDE.md`
- **Format Reference**: `../backend/FRONTEND_RESPONSE_FORMAT.md`

### What Frontend Provides

The frontend sends these requests to your backend:

1. **Document Upload**
   - **Request**: `POST /api/upload`
   - **Body**: `{filePaths: string[], type: string}`
   - **FilePaths**: Absolute paths to documents on user's system
   - **Your Backend**: Store paths in vector DB metadata

2. **Text Query**
   - **Request**: `POST /api/query`
   - **Body**: `{query: string}`
   - **Your Backend**: Return LLM response + source file paths

3. **Speech Query** (optional)
   - **Request**: `POST /api/speech-query`
   - **Body**: FormData with MP3 audio buffer
   - **Your Backend**: Transcribe audio, then process as text query

### Required Response Format

**CRITICAL**: Backend must return sources as objects with `name` and `path`:

```json
{
  "text": "Your LLM response (Markdown supported)",
  "sources": [
    {
      "name": "document.pdf",
      "path": "C:\\Users\\your-username\\Documents\\document.pdf"
    }
  ]
}
```

**Why absolute paths?** The frontend opens source files directly on user's system when they click source chips.

---

## 🛠 Setup & Development

1. **Install Dependencies**:
   ```bash
   cd Frontend
   npm install
   ```
2. **Start Application**:
   ```bash
   npm start
   ```
3. **Distribution**:
   ```bash
   npm run make
   ```

---
*Note: The current implementation uses a `mockStorage` in `index.js`. For a production app, replace this with a local SQLite database or a persistent cloud backend.*
