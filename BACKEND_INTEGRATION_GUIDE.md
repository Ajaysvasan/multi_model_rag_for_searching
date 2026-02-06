# Backend Integration Guide

**Audience**: Backend developers with an existing RAG system ready to integrate with this Electron frontend.

**Prerequisites**:
- ✅ Working RAG backend (ingestion, embeddings, vector DB, LLM)
- ✅ Document upload endpoint
- ✅ Query/search endpoint

---

## Table of Contents
1. [Quick Start](#quick-start)
2. [Required Response Format](#required-response-format)
3. [File Path Integration](#file-path-integration)
4. [Frontend Connection](#frontend-connection)
5. [Testing Integration](#testing-integration)
6. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Your Backend Already Has:
- Document ingestion pipeline
- Vector database (Chroma, Pinecone, Weaviate, etc.)
- LLM integration
- Query endpoint

### What You Need to Change:
1. **Store file paths** in vector DB metadata
2. **Return paths** in query responses
3. **Update response format** to match frontend expectations
4. **Connect frontend** to your API

**Time Required**: 15-30 minutes

---

## Required Response Format

### Your Query Endpoint Must Return:

```json
{
  "text": "Your LLM's response (Markdown supported)",
  "sources": [
    {
      "name": "document.pdf",
      "path": "C:\\Users\\your-username\\Documents\\document.pdf"
    }
  ]
}
```

### Field Specifications:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | ✅ Yes | LLM response (supports Markdown) |
| `sources` | array | ✅ Yes | Retrieved source documents |
| `sources[].name` | string | ✅ Yes | Display name (usually filename) |
| `sources[].path` | string | ✅ Yes | **Absolute** file path |

### ✅ Correct Example:

```json
{
  "text": "Based on the Q4 report, revenue increased by 15%...",
  "sources": [
    {
      "name": "Q4_report_2023.pdf",
      "path": "C:\\Users\\your-username\\Documents\\Q4_report_2023.pdf"
    },
    {
      "name": "financial_summary.xlsx",
      "path": "/home/user/files/financial_summary.xlsx"
    }
  ]
}
```

### ❌ Incorrect Examples:

**Missing paths:**
```json
{
  "text": "...",
  "sources": ["file1.pdf", "file2.docx"]  // ❌ Just strings
}
```

**Relative paths:**
```json
{
  "sources": [
    {
      "name": "file.pdf",
      "path": "./documents/file.pdf"  // ❌ Relative
    }
  ]
}
```

---

## File Path Integration

### Step 1: Modify Document Upload Handler

**When frontend uploads a document**, it sends absolute file paths.

**Your backend receives**:
```python
POST /api/upload
{
  "filePaths": [
    "C:\\Users\\your-username\\Documents\\report.pdf",
    "/home/user/files/data.xlsx"
  ],
  "type": "document"
}
```

**What to do**: Store the `filePath` in your vector DB chunk metadata:

```python
# Your existing upload handler
@app.route('/api/upload', methods=['POST'])
def upload():
    file_paths = request.json['filePaths']

    for file_path in file_paths:
        # Your existing processing
        chunks = your_chunking_function(file_path)
        embeddings = your_embedding_function(chunks)

        # ADD THIS: Include source_file in metadata
        for chunk, embedding in zip(chunks, embeddings):
            vector_db.add(
                text=chunk.text,
                embedding=embedding,
                metadata={
                    "source_file": file_path,  # ← ADD THIS
                    "file_name": os.path.basename(file_path),
                    # ... your other metadata
                }
            )

    return jsonify({"success": True})
```

### Step 2: Modify Query Handler

**When frontend sends a query**, retrieve file paths from metadata:

```python
# Your existing query handler
@app.route('/api/query', methods=['POST'])
def query():
    user_query = request.json['query']

    # Your existing RAG pipeline
    query_embedding = your_embedding_function(user_query)
    results = vector_db.search(query_embedding, top_k=5)
    context = "\n".join([r.text for r in results])
    llm_response = your_llm_function(user_query, context)

    # ADD THIS: Extract file paths from metadata
    sources = []
    seen_paths = set()
    for result in results:
        path = result.metadata.get("source_file")  # ← GET THIS
        name = result.metadata.get("file_name")

        if path and path not in seen_paths:
            sources.append({
                "name": name,
                "path": path  # ← RETURN THIS
            })
            seen_paths.add(path)

    # Return in required format
    return jsonify({
        "text": llm_response,
        "sources": sources
    })
```

### Key Points:

✅ **Absolute paths only**: `C:\Users\...` or `/home/...`
✅ **Store during upload**: Add to vector DB metadata
✅ **Retrieve during query**: Extract from search results
✅ **Remove duplicates**: Same file shouldn't appear twice

---

## Frontend Connection

### Update `Frontend/src/services/ragService.js`

Replace the mock implementation with your API:

```javascript
class RAGService {
  async getResponse(message) {
    try {
      // Replace with your backend URL
      const response = await fetch('http://localhost:5000/api/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          // Add auth if needed: 'Authorization': 'Bearer YOUR_TOKEN'
        },
        body: JSON.stringify({ query: message })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();

      // Validate response format
      if (!data.text || !Array.isArray(data.sources)) {
        console.error('Invalid response format:', data);
        throw new Error('Invalid response format');
      }

      return data;
    } catch (error) {
      console.error('Backend error:', error);
      throw error;
    }
  }

  async processSpeechQuery(audioBuffer, fileName) {
    // If you support audio queries
    const formData = new FormData();
    formData.append('audio', new Blob([audioBuffer]));
    formData.append('fileName', fileName);

    const response = await fetch('http://localhost:5000/api/speech-query', {
      method: 'POST',
      body: formData
    });

    return await response.json();
  }

  async uploadDocuments(filePaths, type) {
    const response = await fetch('http://localhost:5000/api/upload', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filePaths, type })
    });

    return await response.json();
  }
}

module.exports = new RAGService();
```

### Configuration:

1. **Backend URL**: Replace `http://localhost:5000` with your server address
2. **Authentication**: Add headers if your API requires auth
3. **CORS**: Ensure your backend allows requests from `file://` origin (Electron)

---

## Testing Integration

### Step-by-Step Testing:

#### 1. Start Your Backend
```bash
# Your backend startup command
python app.py
# or
uvicorn main:app --reload
```

#### 2. Start Frontend
```bash
cd Frontend
npm start
```

#### 3. Test Upload
- Click upload button in UI
- Select a real file
- **Check**: Your backend receives absolute path
- **Check**: Path is stored in vector DB metadata
- **Verify**: `db.get_metadata(chunk_id)` contains `source_file`

#### 4. Test Query
- Ask a question about the uploaded file
- **Check**: Your backend returns `{text, sources}` format
- **Check**: Sources include `name` and `path`
- **Check**: Path is absolute (starts with `C:\` or `/`)
- **Verify**: Source chips appear below response

#### 5. Test File Opening
- Click on a source chip
- **Check**: File opens in default application
- **If fails**: Path is likely incorrect or file doesn't exist

### Debugging:

**Open Browser DevTools** (F12 in Electron):

```javascript
// In Console tab, check response format:
{
  "text": "Your response",
  "sources": [
    {
      "name": "file.pdf",  // ✅ Should see name
      "path": "C:\\..."    // ✅ Should see full path
    }
  ]
}
```

**Check Network Tab**:
- Verify API calls are reaching your backend
- Check request/response payloads
- Look for CORS errors

**Check Console Logs**:
- Frontend logs errors if response format is wrong
- Check for "Invalid response format" messages

---

## Troubleshooting

### Issue: "File not found" when clicking source

**Cause**: Path in response doesn't point to existing file

**Solutions**:
- ✅ Verify path stored in vector DB is correct
- ✅ Check file wasn't moved after upload
- ✅ Ensure using absolute paths, not relative
- ✅ Test: `os.path.exists(stored_path)` in your backend

### Issue: Sources not clickable

**Cause**: Response has strings instead of objects

**Fix**:
```python
# ❌ Wrong
sources = ["file.pdf", "doc.txt"]

# ✅ Correct
sources = [
    {"name": "file.pdf", "path": "/full/path/to/file.pdf"},
    {"name": "doc.txt", "path": "C:\\path\\to\\doc.txt"}
]
```

### Issue: CORS errors

**Cause**: Backend not configured for Electron origin

**Fix**:
```python
# Flask
from flask_cors import CORS
CORS(app, origins=['file://', 'http://localhost:*'])

# FastAPI
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or specify Electron origin
    allow_methods=["*"],
    allow_headers=["*"]
)
```

### Issue: No sources returned

**Cause**: Metadata not stored or retrieved correctly

**Debug**:
```python
# Check if path is in metadata
chunk = vector_db.get(chunk_id)
print(chunk.metadata)  # Should contain 'source_file'

# Check retrieval
results = vector_db.search(query_embedding, top_k=5)
for r in results:
    print(r.metadata.get("source_file"))  # Should print paths
```

### Issue: Wrong file opens

**Cause**: Path points to wrong location

**Fix**:
- Verify the path stored matches the actual file location
- Don't transform paths (keep them exactly as received)
- Test path before storing: `assert os.path.exists(path)`

---

## Platform-Specific Notes

### Windows Paths
```json
{
  "path": "C:\\Users\\your-username\\Documents\\file.pdf"
}
```
- Use double backslashes in JSON: `\\`
- Or use forward slashes: `C:/Users/...` (also works!)

### macOS Paths
```json
{
  "path": "/Users/your-username/Documents/file.pdf"
}
```

### Linux Paths
```json
{
  "path": "/home/your-username/documents/file.pdf"
}
```

**All formats work automatically** - Electron handles platform differences.

---

## API Endpoint Summary

Your backend should expose:

| Endpoint | Method | Input | Output |
|----------|--------|-------|--------|
| `/api/upload` | POST | `{filePaths: string[], type: string}` | `{success: boolean}` |
| `/api/query` | POST | `{query: string}` | `{text: string, sources: [{name, path}]}` |
| `/api/speech-query` | POST | FormData with audio | `{text: string, sources: [{name, path}]}` |

---

## Validation Checklist

Before going to production:

- [ ] Upload endpoint stores absolute file paths in metadata
- [ ] Query endpoint returns `{text, sources}` format
- [ ] Each source has `name` and `path` properties
- [ ] Paths are absolute (not relative)
- [ ] Paths point to existing files
- [ ] Frontend successfully calls your API
- [ ] Source chips appear in UI
- [ ] Clicking chips opens files
- [ ] Works with different file types (PDF, DOCX, etc.)
- [ ] CORS configured correctly
- [ ] Error handling in place

---

## Need Help?

1. **Check browser console** (F12) for errors
2. **Check Network tab** to see API calls
3. **Validate response format** matches specification exactly
4. **Test with curl** to isolate backend issues:

```bash
# Test query endpoint
curl -X POST http://localhost:5000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test question"}'

# Should return:
# {"text": "...", "sources": [{"name": "...", "path": "..."}]}
```

---

**Integration complete!** Your RAG backend is now connected to the Electron frontend with clickable source files. 🎉
