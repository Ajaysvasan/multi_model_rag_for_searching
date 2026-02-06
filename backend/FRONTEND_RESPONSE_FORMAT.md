# Frontend Response Format - Quick Reference

> **IMPORTANT**: This document describes the exact format your RAG backend must return to enable clickable source files in the frontend.

---

## ✅ CORRECT Response Format

```json
{
  "text": "Your LLM response here (supports Markdown)",
  "sources": [
    {
      "name": "annual_report_2023.pdf",
      "path": "C:\\Users\\your-username\\Documents\\annual_report_2023.pdf"
    },
    {
      "name": "project_specs.docx",
      "path": "/home/user/documents/project_specs.docx"
    }
  ]
}
```

### Key Points:
- ✅ `sources` is an **array of objects**
- ✅ Each source has `name` (string) and `path` (string)
- ✅ `path` is an **ABSOLUTE** file path
- ✅ Works on Windows, macOS, and Linux

---

## ❌ INCORRECT Formats

### Wrong: Array of Strings
```json
{
  "text": "...",
  "sources": ["file1.pdf", "file2.docx"]
}
```
❌ Sources won't be clickable (no file paths)

### Wrong: Relative Paths
```json
{
  "text": "...",
  "sources": [
    {
      "name": "file.pdf",
      "path": "./documents/file.pdf"
    }
  ]
}
```
❌ Relative paths won't work - must be absolute

### Wrong: Missing name or path
```json
{
  "text": "...",
  "sources": [
    { "filename": "file.pdf", "location": "..." }
  ]
}
```
❌ Properties must be exactly `name` and `path`

---

## 📋 Implementation Checklist

### During Document Upload:
- [ ] Store original absolute file path in vector DB metadata
- [ ] Example metadata: `{"source_file": "C:\\Users\\...", "file_name": "doc.pdf"}`

### During Query Processing:
- [ ] Perform vector search to find relevant chunks
- [ ] Extract file paths from chunk metadata
- [ ] Remove duplicates (same file shouldn't appear twice)
- [ ] Format as array of objects with `name` and `path`
- [ ] Return in response along with LLM text

### Example Python Code:
```python
# Extract unique sources from retrieved chunks
sources = []
seen_paths = set()

for chunk in retrieved_chunks:
    path = chunk.metadata["source_file"]
    name = chunk.metadata["file_name"]

    if path not in seen_paths:
        sources.append({"name": name, "path": path})
        seen_paths.add(path)

return {
    "text": llm_response,
    "sources": sources
}
```

---

## 🧪 Testing Your Response

### 1. Check Response Structure
```python
import json

response = {
    "text": "Test response",
    "sources": [{"name": "test.pdf", "path": "C:\\test.pdf"}]
}

# Validate
assert "text" in response
assert "sources" in response
assert isinstance(response["sources"], list)
for src in response["sources"]:
    assert "name" in src
    assert "path" in src
    assert os.path.isabs(src["path"])  # Check if absolute

print("✅ Response format is valid!")
```

### 2. Test File Opening
1. Upload a real file through the frontend
2. Query to retrieve that file
3. Click the source chip in the UI
4. File should open in system's default app

---

## 🔧 Platform-Specific Path Examples

### Windows
```json
{
  "name": "document.pdf",
  "path": "C:\\Users\\your-username\\Documents\\document.pdf"
}
```
Note: Backslashes must be escaped in JSON!

### macOS
```json
{
  "name": "document.pdf",
  "path": "/Users/your-username/Documents/document.pdf"
}
```

### Linux
```json
{
  "name": "document.pdf",
  "path": "/home/your-username/documents/document.pdf"
}
```

---

## 📞 Questions?

See the full integration guide: `../BACKEND_INTEGRATION_GUIDE.md`

**Key Principle**: Always return the absolute path to where you stored the original uploaded file!
