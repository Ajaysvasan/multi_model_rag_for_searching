# Backend Integration Guide for RAG Chatbot

This guide explains how to integrate your Python RAG backend with the Electron frontend.

## Table of Contents
1. [Overview](#overview)
2. [Response Format](#response-format)
3. [File Path Requirements](#file-path-requirements)
4. [Integration Points](#integration-points)
5. [Testing](#testing)
6. [Common Issues](#common-issues)

---

## Overview

The frontend Electron app communicates with the backend through the `ragService.js` file located at:
```
Frontend/src/services/ragService.js
```

The frontend has been updated to support **clickable source chips** that allow users to open retrieved documents directly in their system's default application (e.g., PDF reader, Word processor).

---

## Response Format

### Required Response Structure

When your RAG backend returns a response, it **MUST** follow this format:

```javascript
{
  text: string,           // The LLM's generated response (supports Markdown)
  sources: Array<object>  // Array of source documents
}
```

### Sources Array Format (IMPORTANT!)

Each source in the `sources` array **MUST** be an object with two properties:

```javascript
{
  name: string,  // Display name (usually the filename)
  path: string   // ABSOLUTE file path to the original document
}
```

### Complete Example Response

```javascript
{
  text: "Based on the retrieved documents, here's what I found:\n\n1. **Key Finding**: ...\n2. **Recommendation**: ...",
  sources: [
    {
      name: "annual_report_2023.pdf",
      path: "C:\\Users\\your-username\\Documents\\annual_report_2023.pdf"
    },
    {
      name: "project_specs_v2.docx",
      path: "/home/user/documents/project_specs_v2.docx"
    },
    {
      name: "company_policy.txt",
      path: "/Users/your-username/policies/company_policy.txt"
    }
  ]
}
```

### Legacy Format (NOT Recommended)

The old format with just filenames is still supported but sources won't be clickable:

```javascript
{
  text: "...",
  sources: ["file1.pdf", "file2.docx"]  // ❌ Not clickable
}
```

---

## File Path Requirements

### Critical Requirements

1. **ABSOLUTE PATHS ONLY**: Paths must be absolute, not relative
   - ✅ Good: `C:\Users\your-username\Documents\file.pdf`
   - ✅ Good: `/home/user/documents/file.pdf`
   - ❌ Bad: `./documents/file.pdf`
   - ❌ Bad: `../file.pdf`

2. **ORIGINAL FILE LOCATION**: Path must point to where the actual file is stored
   - Store the original file path when users upload documents
   - Include this path in your vector database metadata
   - Return this path when chunks from that document are retrieved

3. **CROSS-PLATFORM COMPATIBILITY**:
   - Windows: `C:\\Users\\your-username\\Documents\\file.pdf`
   - macOS: `/Users/your-username/Documents/file.pdf`
   - Linux: `/home/your-username/documents/file.pdf`

### How to Store File Paths in Your Backend

When users upload documents through the frontend:

1. The frontend sends absolute file paths to `ragService.uploadDocuments()`
2. Your backend should:
   - Process and chunk the document
   - Create embeddings
   - Store chunks in vector database
   - **IMPORTANT**: Store the original file path in the metadata for each chunk

Example vector DB metadata:
```python
{
  "chunk_id": "abc123",
  "text": "Annual revenue increased by 15%...",
  "embedding": [...],
  "metadata": {
    "source_file": "C:\\Users\\your-username\\Documents\\annual_report_2023.pdf",
    "file_name": "annual_report_2023.pdf",
    "page": 5,
    "chunk_index": 3
  }
}
```

When retrieving similar chunks:
```python
# After vector search
retrieved_chunks = vector_db.search(query_embedding, top_k=5)

# Extract unique source files
sources = []
seen_paths = set()

for chunk in retrieved_chunks:
    source_path = chunk.metadata["source_file"]
    file_name = chunk.metadata["file_name"]

    if source_path not in seen_paths:
        sources.append({
            "name": file_name,
            "path": source_path
        })
        seen_paths.add(source_path)

return {
    "text": llm_response,
    "sources": sources
}
```

---

## Integration Points

### 1. Text Query Handler

**Location**: `Frontend/src/index.js` → `ipcMain.handle('chat:send', ...)`
**Calls**: `ragService.getResponse(message)`

Your backend should implement an endpoint that:
- Receives: User's text query
- Returns: `{ text: string, sources: Array<{name, path}> }`

### 2. Speech Query Handler

**Location**: `Frontend/src/index.js` → `ipcMain.handle('chat:send-speech', ...)`
**Calls**: `ragService.processSpeechQuery(audioBuffer, fileName)`

Your backend should:
1. Receive audio buffer and filename
2. Transcribe audio using STT (e.g., Whisper)
3. Process transcribed text through RAG pipeline
4. Returns: Same format as text query

### 3. Document Upload Handler

**Location**: `Frontend/src/index.js` → `performUpload()`
**Calls**: `ragService.uploadDocuments(filePaths, type)`

Your backend receives:
- `filePaths`: Array of absolute file paths
- `type`: 'document' | 'video' | 'audio' | 'image' | 'folder'

Store these paths in your vector DB metadata!

---

## Testing

### Step 1: Update ragService.js

Replace the mock implementation in `Frontend/src/services/ragService.js` with actual backend calls:

```javascript
async getResponse(message) {
  try {
    // Replace with your actual backend endpoint
    const response = await fetch('http://localhost:5000/api/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: message })
    });

    const data = await response.json();

    // Validate response format
    if (!data.text || !Array.isArray(data.sources)) {
      throw new Error('Invalid response format');
    }

    return data;
  } catch (error) {
    console.error('Backend error:', error);
    throw error;
  }
}
```

### Step 2: Test File Opening

1. Upload a document through the frontend
2. Send a query that should retrieve that document
3. Check the response contains sources with valid paths
4. Click on the source chip
5. Verify the file opens in the system's default application

### Step 3: Verify Path Format

Log the sources to ensure they're in the correct format:

```javascript
console.log(JSON.stringify(response.sources, null, 2));
// Expected output:
// [
//   {
//     "name": "file.pdf",
//     "path": "C:\\Users\\your-username\\Documents\\file.pdf"
//   }
// ]
```

---

## Common Issues

### Issue 1: "File not found" when clicking source

**Cause**: The file path in the response doesn't point to an existing file
**Solution**:
- Verify the path stored in your vector DB metadata is correct
- Check file wasn't moved or deleted after upload
- Ensure you're using absolute paths, not relative

### Issue 2: Sources aren't clickable

**Cause**: Sources returned as strings instead of objects
**Solution**: Update backend to return objects with `name` and `path`:
```javascript
// ❌ Wrong
sources: ["file.pdf", "doc.txt"]

// ✅ Correct
sources: [
  { name: "file.pdf", path: "C:\\path\\to\\file.pdf" },
  { name: "doc.txt", path: "/path/to/doc.txt" }
]
```

### Issue 3: Path separators on Windows

**Cause**: Windows uses backslashes (`\`) which need escaping in JSON
**Solution**: Either:
- Escape backslashes: `"C:\\Users\\your-username\\file.pdf"`
- Or use forward slashes: `"C:/Users/your-username/file.pdf"` (works on Windows too!)

### Issue 4: No sources returned

**Cause**: Vector search returns empty results
**Solution**:
- Check embeddings are generated correctly
- Verify vector DB has indexed documents
- Test with a simpler query
- Return mock sources for testing

---

## Quick Start Checklist

- [ ] Backend returns `{ text, sources }` format
- [ ] Each source has both `name` and `path` properties
- [ ] Paths are absolute, not relative
- [ ] File paths stored in vector DB metadata during upload
- [ ] File paths retrieved from metadata during search
- [ ] Tested file opening by clicking source chips
- [ ] Works across different file types (PDF, DOCX, TXT, etc.)

---

## Example Python Backend Implementation

```python
from flask import Flask, request, jsonify
import chromadb  # or your vector DB

app = Flask(__name__)
vector_db = chromadb.Client()

@app.route('/api/query', methods=['POST'])
def query():
    data = request.json
    user_query = data['query']

    # 1. Generate query embedding
    query_embedding = generate_embedding(user_query)

    # 2. Search vector database
    results = vector_db.search(
        embedding=query_embedding,
        top_k=5
    )

    # 3. Extract unique source files
    sources = []
    seen_paths = set()

    for result in results:
        source_path = result['metadata']['source_file']
        file_name = result['metadata']['file_name']

        if source_path not in seen_paths:
            sources.append({
                'name': file_name,
                'path': source_path
            })
            seen_paths.add(source_path)

    # 4. Generate LLM response
    context = "\n\n".join([r['text'] for r in results])
    llm_response = generate_llm_response(user_query, context)

    # 5. Return formatted response
    return jsonify({
        'text': llm_response,
        'sources': sources
    })

if __name__ == '__main__':
    app.run(port=5000)
```

---

## Need Help?

If you encounter any issues:
1. Check the browser console for errors (F12 in Electron)
2. Check the Electron main process logs
3. Verify response format matches the specification
4. Test with mock data first before connecting real backend

---



# 🚀 Backend Developer - Start Here!

**Welcome!** This guide will get you up to speed on integrating your RAG backend with the Electron frontend.

---

## ⚡ Quick Start (5 Minutes)

### 1. **Read This First** 📖
Open this file and read the comments:
```
Frontend/src/services/ragService.js
```

Look for the **MASSIVE comment block** at line ~25 in the `getResponse()` method. It contains:
- Complete integration guide
- Python code examples
- Required response format
- Testing checklist

### 2. **Understand the Flow** 🔄
The file opening feature works like this:

```
User Query
    ↓
Backend Response: {text: "...", sources: [{name, path}]}
    ↓
Frontend Displays: [📄 file.pdf] (clickable chip)
    ↓
User Clicks Chip
    ↓
File Opens in System App (Adobe, Word, etc.)
```

### 3. **The One Thing You MUST Do** ⚠️

**Store absolute file paths in your vector database!**

When users upload files, you receive absolute paths like:
- `C:\Users\your-username\Documents\report.pdf` (Windows)
- `/home/user/documents/report.pdf` (Linux/Mac)

**Store these paths in your chunk metadata!**

---

## 📋 What You Need to Return

### Required Response Format:

```json
{
  "text": "Your LLM response here...",
  "sources": [
    {
      "name": "annual_report.pdf",
      "path": "C:\\Users\\your-username\\Documents\\annual_report.pdf"
    }
  ]
}
```

### ✅ DO:
- Return objects with `name` and `path`
- Use **absolute** paths
- Store paths during upload
- Retrieve paths from metadata

### ❌ DON'T:
- Return just filenames: `["file.pdf"]`
- Use relative paths: `"./docs/file.pdf"`
- Forget to store paths in metadata
- Use different property names

---

## 🔍 Where to Look in the Code

### All the comments you need are in these files:

1. **`Frontend/src/services/ragService.js`**
   - Lines 25-220: Complete integration guide
   - Lines 360-450: Deployment checklist
   - **START HERE!**

2. **`Frontend/src/renderer.js`**
   - Lines 112-310: `createSourceChip()` function
   - Shows exactly what happens when user clicks
   - Python examples for backend implementation

3. **`Frontend/src/index.js`**
   - Lines 315-400: File opening handler
   - More Python examples
   - Path storage guidance

4. **`Frontend/src/preload.js`**
   - Lines 20-60: API bridge explanation
   - Shows how frontend calls backend

5. **`Frontend/src/index.css`**
   - Lines 650-700: Visual styling explanation
   - User experience details

---

## 💻 Python Implementation Template

Based on the comments in the code, here's a quick template:

```python
from flask import Flask, request, jsonify
import os

app = Flask(__name__)

@app.route('/api/query', methods=['POST'])
def query():
    data = request.json
    user_query = data['query']

    # 1. Generate embeddings
    query_embedding = generate_embedding(user_query)

    # 2. Search vector DB
    results = vector_db.search(query_embedding, top_k=5)

    # 3. Extract unique source files
    sources = []
    seen_paths = set()

    for chunk in results:
        # Get path from metadata (stored during upload)
        path = chunk.metadata["source_file"]
        name = chunk.metadata["file_name"]

        if path not in seen_paths:
            sources.append({
                "name": name,
                "path": path  # ← ABSOLUTE PATH!
            })
            seen_paths.add(path)

    # 4. Generate LLM response
    context = "\n".join([r.text for r in results])
    llm_response = generate_llm_response(user_query, context)

    # 5. Return in correct format
    return jsonify({
        "text": llm_response,
        "sources": sources
    })

# During upload, store paths like this:
@app.route('/api/upload', methods=['POST'])
def upload():
    file_paths = request.json['filePaths']  # Already absolute

    for file_path in file_paths:
        chunks = process_document(file_path)
        for chunk in chunks:
            vector_db.add(
                text=chunk.text,
                embedding=chunk.embedding,
                metadata={
                    "source_file": file_path,  # ← Store this!
                    "file_name": os.path.basename(file_path)
                }
            )

    return jsonify({"success": True})
```

---

## ✅ Testing Checklist

After implementing your backend:

1. ✅ Start your backend server
2. ✅ Update `ragService.js` to call your API (see comments in file)
3. ✅ Run the Electron app: `cd Frontend && npm start`
4. ✅ Upload a real file through the UI
5. ✅ Open browser DevTools (F12)
6. ✅ Send a query
7. ✅ Check response format in Console tab
8. ✅ Verify sources have `{name, path}` format
9. ✅ Click the source chip
10. ✅ File should open!

---

## 📚 Documentation Files

If you want more details:

| Document | What's Inside | When to Read |
|----------|---------------|--------------|
| `BACKEND_INTEGRATION_GUIDE.md` | Complete guide (7000+ words) | For comprehensive understanding |
| `backend/FRONTEND_RESPONSE_FORMAT.md` | Quick format reference | When implementing response format |
| `FILE_OPENING_FLOW.md` | Visual architecture diagram | To understand the flow |
| `INLINE_COMMENTS_SUMMARY.md` | Summary of code comments | To know where to find what |

**But honestly, the comments in the code files are enough to get started!**

---

## 🎯 Your Mission

1. **Store file paths** when users upload documents
2. **Return file paths** when RAG retrieves documents
3. **Test** that clicking source chips opens files

That's it! The frontend handles everything else.

---

## 🐛 Common Issues

### "File not found" error
- Check paths are absolute (start with `C:\` or `/`)
- Verify file wasn't moved after upload
- Ensure path is stored correctly in metadata

### Sources not clickable
- Response has strings instead of objects
- Fix: Return `[{name, path}]` not `["filename"]`

### Wrong file opens
- Path points to wrong location
- Check metadata is correct during storage

---

## 💡 Pro Tips

1. **Test with a text file first** - easier to debug
2. **Check browser console** (F12) for errors
3. **Verify paths in your vector DB** after upload
4. **Use absolute paths everywhere** - no exceptions
5. **Keep source file name in metadata** for display

---

## 🎓 Learning Resources

### In the Code Comments:
- Complete Python examples
- Step-by-step guides
- Testing instructions
- Error handling patterns

### Look for These Markers:
- `// ✨ NEW FEATURE` - New functionality
- `// BACKEND INTEGRATION` - What you need to do
- `// STEP 1, 2, 3...` - Sequential instructions
- Python code blocks in comments

---

## 🚀 Ready to Start?

1. Open `Frontend/src/services/ragService.js`
2. Read the big comment block in `getResponse()`
3. Implement the Python template above
4. Test using the checklist
5. Done! 🎉

---

## 📞 Need Help?

- **Code Comments**: All files have extensive inline documentation
- **Python Examples**: Found throughout the comments
- **Testing Guide**: In ragService.js comments
- **Architecture**: FILE_OPENING_FLOW.md

---

**Remember**: The code is heavily commented specifically for YOU. Just read the comments in the files! They contain everything you need including Python code examples.