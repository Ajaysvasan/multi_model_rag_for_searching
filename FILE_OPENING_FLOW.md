# File Opening Flow - Complete Architecture

This document explains how the file opening feature works from end to end.

---

## 🔄 Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER UPLOADS DOCUMENT                        │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Frontend (Electron Main Process)                                   │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ File Path: C:\Users\your-username\Documents\annual_report_2023.pdf   │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Backend (Python RAG Service)                                        │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ 1. Load file and extract text                                │  │
│  │ 2. Chunk the text                                            │  │
│  │ 3. Generate embeddings                                       │  │
│  │ 4. Store in Vector DB with metadata:                        │  │
│  │    {                                                         │  │
│  │      "chunk_text": "...",                                   │  │
│  │      "embedding": [...],                                    │  │
│  │      "metadata": {                                          │  │
│  │        "source_file": "C:\Users\...\annual_report_2023.pdf",│  │
│  │        "file_name": "annual_report_2023.pdf",               │  │
│  │        "page": 5,                                           │  │
│  │        "chunk_index": 3                                     │  │
│  │      }                                                       │  │
│  │    }                                                         │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘

                             ⏱️ (Time passes...)

┌─────────────────────────────────────────────────────────────────────┐
│                        USER ASKS A QUESTION                          │
│              "What was the revenue in 2023?"                         │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Backend (RAG Query Processing)                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ 1. Generate query embedding                                  │  │
│  │ 2. Search vector DB for similar chunks                       │  │
│  │ 3. Retrieve top-k chunks with metadata                       │  │
│  │ 4. Extract unique file paths from metadata                   │  │
│  │ 5. Generate LLM response                                     │  │
│  │ 6. Return response in frontend format                        │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Response to Frontend                                                │
│  {                                                                   │
│    "text": "The revenue in 2023 was $10M...",                       │
│    "sources": [                                                      │
│      {                                                               │
│        "name": "annual_report_2023.pdf",                            │
│        "path": "C:\\Users\\your-username\\Documents\\annual_report_2023.pdf"│
│      }                                                               │
│    ]                                                                 │
│  }                                                                   │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Frontend (Renderer Process - UI)                                   │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Display LLM Response:                                        │  │
│  │ "The revenue in 2023 was $10M..."                           │  │
│  │                                                              │  │
│  │ Sources:                                                     │  │
│  │ ┌────────────────────────────────┐                         │  │
│  │ │ 📄 annual_report_2023.pdf      │  ← Clickable!          │  │
│  │ └────────────────────────────────┘                         │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                    (User clicks source chip)
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Frontend (Renderer) - createSourceChip() click handler             │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ chip.addEventListener('click', async () => {                │  │
│  │   await window.electronAPI.openFile(sourcePath);           │  │
│  │ });                                                         │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Preload Script (Security Bridge)                                   │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ openFile: (filePath) =>                                     │  │
│  │   ipcRenderer.invoke('file:open', filePath)                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Main Process - IPC Handler                                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ ipcMain.handle('file:open', async (event, filePath) => {   │  │
│  │   // Check file exists                                      │  │
│  │   if (!fs.existsSync(filePath)) return error;              │  │
│  │                                                             │  │
│  │   // Open file with system default app                     │  │
│  │   await shell.openPath(filePath);                          │  │
│  │ });                                                         │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   SYSTEM OPENS FILE                                  │
│  - PDF opens in Adobe Reader / Browser                              │
│  - DOCX opens in Microsoft Word                                     │
│  - TXT opens in Notepad / TextEdit                                  │
│  - Images open in default image viewer                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🗂️ File Structure

```
multi_model_rag_for_searching/
│
├── Frontend/
│   └── src/
│       ├── index.js              # Main process (IPC handler for file:open)
│       ├── preload.js            # Security bridge (exposes openFile API)
│       ├── renderer.js           # UI logic (createSourceChip with click handler)
│       └── services/
│           └── ragService.js     # Mock/Real backend communication
│
├── backend/
│   ├── data_layer/               # Your RAG implementation
│   ├── FRONTEND_RESPONSE_FORMAT.md  # Quick reference for response format
│   └── (your Python files)
│
├── BACKEND_INTEGRATION_GUIDE.md  # Full integration documentation
└── FILE_OPENING_FLOW.md          # This file
```

---

## 🔑 Critical Integration Points

### Point 1: Document Upload (Store Path)
**File**: `Frontend/src/index.js` → `performUpload()`
**Action**: Backend receives absolute file paths
**Backend Must Do**: Store `filePath` in vector DB metadata

```python
# When processing upload
for file_path in uploaded_files:
    chunks = process_document(file_path)
    for chunk in chunks:
        vector_db.add(
            text=chunk.text,
            embedding=chunk.embedding,
            metadata={
                "source_file": file_path,  # ← CRITICAL: Store this!
                "file_name": os.path.basename(file_path)
            }
        )
```

### Point 2: Query Processing (Return Path)
**File**: `Frontend/src/services/ragService.js` → `getResponse()`
**Action**: Frontend expects response with sources
**Backend Must Return**:

```python
# After RAG retrieval
retrieved_chunks = vector_db.search(query)

# Extract unique file paths
sources = []
seen = set()
for chunk in retrieved_chunks:
    path = chunk.metadata["source_file"]
    name = chunk.metadata["file_name"]
    if path not in seen:
        sources.append({"name": name, "path": path})
        seen.add(path)

return {
    "text": llm_generated_response,
    "sources": sources  # ← CRITICAL: Format like this!
}
```

### Point 3: User Interaction (Click to Open)
**File**: `Frontend/src/renderer.js` → `createSourceChip()`
**Action**: User clicks source chip
**Flow**:
1. Click event → `window.electronAPI.openFile(path)`
2. Preload → `ipcRenderer.invoke('file:open', path)`
3. Main → `shell.openPath(path)`
4. System opens file

---

## 🧪 Testing Checklist

### Backend Developer Testing:

1. **Test Response Format**
   ```python
   # Your endpoint should return this structure
   response = your_rag_query("test query")
   assert "text" in response
   assert "sources" in response
   assert isinstance(response["sources"], list)
   assert all("name" in s and "path" in s for s in response["sources"])
   ```

2. **Test Path Storage**
   ```python
   # After uploading a file, check vector DB
   chunks = vector_db.get_all()
   assert chunks[0].metadata.get("source_file")  # Should exist
   assert os.path.isabs(chunks[0].metadata["source_file"])  # Should be absolute
   ```

3. **Test Path Retrieval**
   ```python
   # After query, check sources contain valid paths
   response = your_rag_query("test query")
   for source in response["sources"]:
       assert os.path.exists(source["path"])  # File should exist
   ```

### Frontend Testing:

1. Open Developer Tools (F12) in Electron
2. Upload a document
3. Send a query
4. Check console for response format
5. Click source chip
6. Verify file opens

---

## 🐛 Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Sources not clickable | Response has strings instead of objects | Return `[{name, path}]` not `["file.pdf"]` |
| "File not found" error | Path in DB doesn't match actual file location | Store absolute paths during upload |
| File doesn't open | Relative path used | Convert to absolute: `os.path.abspath(path)` |
| Sources empty | Metadata not stored properly | Add `source_file` to chunk metadata |

---

## 📚 Related Files

1. **Full Documentation**: `BACKEND_INTEGRATION_GUIDE.md`
2. **Quick Reference**: `backend/FRONTEND_RESPONSE_FORMAT.md`
3. **Frontend Code**:
   - `Frontend/src/renderer.js` (lines 58-155)
   - `Frontend/src/preload.js` (lines 9-33)
   - `Frontend/src/index.js` (lines 307-353)

---

**Remember**: The key to making this work is storing and returning **absolute file paths**!
