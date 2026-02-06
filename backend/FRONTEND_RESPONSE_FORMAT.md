# Frontend Response Format - Quick Reference

**For backend developers integrating with the Electron frontend.**

---

## ✅ Required Format

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

---

## 📋 Field Specifications

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `text` | string | ✅ | LLM response (Markdown formatted) |
| `sources` | array | ✅ | Array of source documents |
| `sources[].name` | string | ✅ | Display name (filename) |
| `sources[].path` | string | ✅ | **Absolute** file path |

---

## ✅ Correct Examples

### Single Source
```json
{
  "text": "Based on the document, the answer is...",
  "sources": [
    {
      "name": "report.pdf",
      "path": "C:\\Users\\your-username\\Documents\\report.pdf"
    }
  ]
}
```

### Multiple Sources
```json
{
  "text": "According to multiple documents...",
  "sources": [
    {
      "name": "Q1_report.pdf",
      "path": "C:\\Users\\your-username\\Documents\\Q1_report.pdf"
    },
    {
      "name": "Q2_report.pdf",
      "path": "C:\\Users\\your-username\\Documents\\Q2_report.pdf"
    }
  ]
}
```

### Cross-Platform Paths
```json
{
  "sources": [
    {
      "name": "windows_doc.pdf",
      "path": "C:\\Users\\your-username\\Documents\\windows_doc.pdf"
    },
    {
      "name": "mac_doc.pdf",
      "path": "/Users/your-username/Documents/mac_doc.pdf"
    },
    {
      "name": "linux_doc.pdf",
      "path": "/home/your-username/documents/linux_doc.pdf"
    }
  ]
}
```

---

## ❌ Incorrect Examples

### Wrong: Array of Strings
```json
{
  "text": "...",
  "sources": ["file1.pdf", "file2.docx"]
}
```
❌ Sources must be objects, not strings

### Wrong: Missing Path
```json
{
  "sources": [
    {
      "name": "file.pdf"
    }
  ]
}
```
❌ Must include `path` property

### Wrong: Relative Path
```json
{
  "sources": [
    {
      "name": "file.pdf",
      "path": "./documents/file.pdf"
    }
  ]
}
```
❌ Path must be absolute

### Wrong: Wrong Property Names
```json
{
  "sources": [
    {
      "filename": "file.pdf",
      "location": "C:\\..."
    }
  ]
}
```
❌ Must use `name` and `path` (not `filename`/`location`)

---

## 🔧 Backend Implementation

### Store Path on Upload
```python
@app.route('/api/upload', methods=['POST'])
def upload():
    file_paths = request.json['filePaths']

    for file_path in file_paths:
        # Store path in metadata
        vector_db.add(
            metadata={
                "source_file": file_path,  # ← Store this
                "file_name": os.path.basename(file_path)
            }
        )
```

### Return Path on Query
```python
@app.route('/api/query', methods=['POST'])
def query():
    results = vector_db.search(query_embedding, top_k=5)

    # Extract paths from metadata
    sources = []
    for result in results:
        sources.append({
            "name": result.metadata["file_name"],
            "path": result.metadata["source_file"]  # ← Return this
        })

    return jsonify({
        "text": llm_response,
        "sources": sources
    })
```

---

## ✅ Validation

Before returning response:

```python
# Validate format
assert isinstance(response["text"], str)
assert isinstance(response["sources"], list)

for source in response["sources"]:
    assert "name" in source
    assert "path" in source
    assert os.path.isabs(source["path"])  # Check absolute
```

---

## 🧪 Testing

### Test with curl
```bash
curl -X POST http://localhost:5000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'
```

### Expected Response
```json
{
  "text": "...",
  "sources": [
    {"name": "...", "path": "..."}
  ]
}
```

### Frontend Validation
The frontend will:
- ✅ Check `text` is string
- ✅ Check `sources` is array
- ✅ Check each source has `name` and `path`
- ✅ Display error if format is wrong

---

## 📚 More Information

- **Complete Guide**: `../BACKEND_INTEGRATION_GUIDE.md`
- **Quick Start**: `../BACKEND_DEVELOPER_START_HERE.md`
- **Architecture**: `../FILE_OPENING_FLOW.md`

---

**Key Principle**: Always return absolute file paths in the `sources` array!
