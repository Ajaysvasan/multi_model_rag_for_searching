/**
 * ============================================================================
 * RAG SERVICE - Backend Integration Layer
 * ============================================================================
 *
 * This service acts as the bridge between the Electron frontend and your
 * Python RAG backend. It handles all communication with the backend API.
 *
 * CURRENT STATE: Mock implementation with fake data
 * PRODUCTION: Replace methods with actual HTTP requests to your backend
 *
 * INTEGRATION STEPS:
 * 1. Replace mock responses with fetch/axios calls to your backend API
 * 2. Ensure backend returns responses in the correct format (see below)
 * 3. Test with real uploaded files
 * 4. Verify source chips are clickable and open files
 *
 * ============================================================================
 */
class RAGService {
  // ==========================================================================
  // TEXT QUERY HANDLER - Main RAG Query Method
  // ==========================================================================
  /**
   * BACKEND INTEGRATION POINT:
   * Replace this ENTIRE method with a fetch/axios call to your RAG API endpoint.
   *
   * -------------------------------------------------------------------------
   * INPUT PARAMETERS:
   * -------------------------------------------------------------------------
   * @param {string} message - The user's text query
   *
   * Example: "What was the revenue in 2023?"
   *
   * -------------------------------------------------------------------------
   * OUTPUT FORMAT (CRITICAL - MUST FOLLOW EXACTLY):
   * -------------------------------------------------------------------------
   * @returns {Promise<Object>} Response object with this exact structure:
   * {
   *   text: string,              // LLM's response (supports Markdown formatting)
   *   sources: Array<object>     // Array of source documents with name AND path
   * }
   *
   * -------------------------------------------------------------------------
   * SOURCES ARRAY FORMAT (THIS IS THE IMPORTANT PART!):
   * -------------------------------------------------------------------------
   * Each source MUST be an object with TWO properties:
   *
   * {
   *   name: string,  // Display name (usually the filename)
   *   path: string   // ABSOLUTE file path to the original document
   * }
   *
   * ✅ CORRECT EXAMPLE (enables file opening):
   * {
   *   text: "Based on the analysis, the revenue in 2023 was $10M...",
   *   sources: [
   *     {
   *       name: "annual_report_2023.pdf",
   *       path: "C:\\Users\\your-username\\Documents\\annual_report_2023.pdf"
   *     },
   *     {
   *       name: "project_specs.docx",
   *       path: "/home/user/documents/project_specs.docx"
   *     }
   *   ]
   * }
   *
   * ❌ WRONG EXAMPLE 1 (files won't be clickable):
   * {
   *   text: "...",
   *   sources: ["annual_report_2023.pdf", "project_specs.docx"]  // Just strings
   * }
   *
   * ❌ WRONG EXAMPLE 2 (relative paths won't work):
   * {
   *   text: "...",
   *   sources: [
   *     {name: "report.pdf", path: "./documents/report.pdf"}  // Relative path
   *   ]
   * }
   *
   * -------------------------------------------------------------------------
   * WHY ABSOLUTE PATHS ARE REQUIRED:
   * -------------------------------------------------------------------------
   * 1. Enables clickable source chips in the UI
   * 2. Files open in system default application when clicked
   * 3. Works across all operating systems (Windows, macOS, Linux)
   * 4. Provides users with quick access to source documents
   *
   * -------------------------------------------------------------------------
   * HOW TO IMPLEMENT IN YOUR BACKEND:
   * -------------------------------------------------------------------------
   *
   * STEP 1: Store file paths during document upload
   * ------------------------------------------------
   * When users upload documents through the frontend, you receive absolute paths.
   * Store these paths in your vector DB chunk metadata:
   *
   * Python example:
   * ```python
   * def process_upload(file_paths):
   *     for file_path in file_paths:  # These are absolute paths
   *         # Process document
   *         chunks = chunk_document(file_path)
   *
   *         # Store each chunk with metadata
   *         for chunk in chunks:
   *             vector_db.add(
   *                 text=chunk.text,
   *                 embedding=chunk.embedding,
   *                 metadata={
   *                     "source_file": file_path,  # ← Store absolute path here!
   *                     "file_name": os.path.basename(file_path),
   *                     "page": chunk.page,
   *                     "chunk_index": chunk.index
   *                 }
   *             )
   * ```
   *
   * STEP 2: Retrieve paths during RAG query
   * ----------------------------------------
   * When processing a user query, retrieve file paths from metadata:
   *
   * Python example:
   * ```python
   * def rag_query(user_query):
   *     # 1. Generate query embedding
   *     query_embedding = embed_text(user_query)
   *
   *     # 2. Search vector database
   *     retrieved_chunks = vector_db.search(
   *         embedding=query_embedding,
   *         top_k=5
   *     )
   *
   *     # 3. Extract unique source files
   *     sources = []
   *     seen_paths = set()
   *
   *     for chunk in retrieved_chunks:
   *         # Get stored path from metadata
   *         path = chunk.metadata["source_file"]
   *         name = chunk.metadata["file_name"]
   *
   *         # Avoid duplicates
   *         if path not in seen_paths:
   *             sources.append({
   *                 "name": name,
   *                 "path": path
   *             })
   *             seen_paths.add(path)
   *
   *     # 4. Generate LLM response
   *     context = "\n\n".join([c.text for c in retrieved_chunks])
   *     llm_response = generate_response(user_query, context)
   *
   *     # 5. Return in correct format
   *     return {
   *         "text": llm_response,
   *         "sources": sources
   *     }
   * ```
   *
   * STEP 3: Replace this mock method with actual API call
   * ------------------------------------------------------
   * Production example:
   * ```javascript
   * async getResponse(message) {
   *   try {
   *     const response = await fetch('http://localhost:5000/api/query', {
   *       method: 'POST',
   *       headers: {'Content-Type': 'application/json'},
   *       body: JSON.stringify({ query: message })
   *     });
   *
   *     const data = await response.json();
   *
   *     // Validate format
   *     if (!data.text || !Array.isArray(data.sources)) {
   *       throw new Error('Invalid response format');
   *     }
   *
   *     return data;
   *   } catch (error) {
   *     console.error('Backend error:', error);
   *     throw error;
   *   }
   * }
   * ```
   *
   * -------------------------------------------------------------------------
   * PLATFORM-SPECIFIC PATH FORMATS:
   * -------------------------------------------------------------------------
   * Windows:  "C:\\Users\\your-username\\Documents\\file.pdf"
   * macOS:    "/Users/your-username/Documents/file.pdf"
   * Linux:    "/home/your-username/documents/file.pdf"
   *
   * All formats work automatically with Electron's shell.openPath()!
   *
   * -------------------------------------------------------------------------
   * TESTING CHECKLIST:
   * -------------------------------------------------------------------------
   * 1. Upload a document through the frontend
   * 2. Note the absolute path that gets sent to your backend
   * 3. Verify the path is stored in your vector DB metadata
   * 4. Send a query that should retrieve that document
   * 5. Check the response has sources with {name, path} format
   * 6. Verify paths are absolute (start with C:\ or /)
   * 7. Click the source chip in the UI
   * 8. File should open in system's default application
   *
   * -------------------------------------------------------------------------
   * ADDITIONAL RESOURCES:
   * -------------------------------------------------------------------------
   * - Full Integration Guide: ../BACKEND_INTEGRATION_GUIDE.md
   * - Quick Reference: ../backend/FRONTEND_RESPONSE_FORMAT.md
   * - Architecture Flow: ../FILE_OPENING_FLOW.md
   *
   * -------------------------------------------------------------------------
   */
  async getResponse(message) {
    // Simulate network latency
    await new Promise(resolve => setTimeout(resolve, 1500));

    // Simulated Vector DB Retrieval Logic
    // In a real implementation, your backend would:
    // 1. Convert the user's query to embeddings
    // 2. Search the vector database for similar chunks
    // 3. Retrieve the top-k most relevant chunks
    // 4. Return the source file paths associated with those chunks

    const allSources = [
      {
        name: "annual_report_2023.pdf",
        path: "C:\\Users\\your-username\\Documents\\annual_report_2023.pdf"  // Windows path example
      },
      {
        name: "project_specs_v2.docx",
        path: "/home/user/documents/project_specs_v2.docx"  // Linux/Mac path example
      },
      {
        name: "company_policy_handbook.txt",
        path: "C:\\Company\\Policies\\company_policy_handbook.txt"
      },
      {
        name: "market_research_q4.pdf",
        path: "/Users/your-username/work/market_research_q4.pdf"
      }
    ];

    // Pick 1-3 random sources to simulate RAG retrieval
    const selectedSources = allSources
      .sort(() => 0.5 - Math.random())
      .slice(0, Math.floor(Math.random() * 3) + 1);

    // Simulated LLM Response Generation (Markdown)
    const responseText = `### Analysis of your query: "${message}"

Based on the retrieved documents, here is what I found:

1. **Key Insight**: The data suggests a strong correlation between user engagement and feature accessibility.
2. **Recommendation**: We should focus on optimizing the onboarding flow for new users.

\`\`\`javascript
// Example logic based on the docs
function optimizeFlow(user) {
  if (user.isNew) {
    return showSimplifiedDashboard();
  }
}
\`\`\`

You can find more details in the attached sources below. **Click on any source to open the file!**`;

    return {
      text: responseText,
      sources: selectedSources
    };
  }

  /**
   * BACKEND INTEGRATION POINT:
   * Speech-to-Text and Speech-to-RAG logic.
   * This method handles the raw MP3 audio buffer from the frontend.
   *
   * DEVELOPMENT TIP for Backend/Vector DB Developers:
   * 1. MP3 Audio Storage: Store the raw 'audioBuffer' (now in MP3 format) in Cloud Storage.
   * 2. Transcription: Use a Speech-to-Text model (e.g., OpenAI Whisper)
   *    to convert the MP3 audio into text.
   * 3. RAG Flow: Once transcribed, treat the text as a normal 'message' for the RAG pipeline.
   *
   * OUTPUT FORMAT: Same as getResponse() - must include sources with name AND path
   *
   * @param {Buffer} audioBuffer - The raw MP3 audio data from the microphone.
   * @param {string} fileName - Filename (ends in .mp3).
   */
  async processSpeechQuery(audioBuffer, fileName) {
    // Simulate Speech-to-Text processing delay
    await new Promise(resolve => setTimeout(resolve, 2000));

    console.log(`Processing speech query: ${fileName}, buffer size: ${audioBuffer.length} bytes`);

    // In a real RAG system, you would:
    // const transcript = await whisperModel.transcribe(audioBuffer);
    // const response = await this.getResponse(transcript);

    // For simulation, we'll return a response suggesting we heard the user.
    const responseText = `### Audio Query Processed

I've received your voice message: **"${fileName}"**.

**Backend Processing Summary:**
- **Step 1**: Audio received as a Node.js Buffer.
- **Step 2**: Sent to an STT (Speech-to-Text) engine like **Whisper**.
- **Step 3**: Transcribed text used to query the Vector Database.
- **Step 4**: Context retrieved and LLM response generated.

*Simulated Transcription*: "How do I optimize the onboarding flow for new users?"

**Click on the sources below to open the files!**`;

    return {
      text: responseText,
      sources: [
        {
          name: "onboarding_manual.pdf",
          path: "C:\\Users\\your-username\\Documents\\onboarding_manual.pdf"
        },
        {
          name: "ux_best_practices.docx",
          path: "/home/user/guides/ux_best_practices.docx"
        }
      ]
    };
  }

  /**
   * BACKEND INTEGRATION POINT:
   * Replace this with a call to your document indexing service.
   * @param {string[]} filePaths - Absolute paths to the local files.
   * @param {string} type - 'document', 'video', 'audio', or 'image'.
   */
  async uploadDocuments(filePaths, type = 'document') {
    // Simulate indexing delay
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    console.log(`Uploading ${filePaths.length} ${type} files to vector database:`, filePaths);
    
    // NOTE: In production, you would typically upload these files to a cloud storage (S3)
    // and then trigger an indexing job in your Vector DB (Pinecone, Chroma, etc.).
    
    return {
      success: true,
      message: `${filePaths.length} ${type}(s) uploaded and indexed successfully.`
    };
  }
}

// ============================================================================
// EXPORT & DEPLOYMENT NOTES
// ============================================================================

/**
 * CURRENT STATE: Mock Implementation
 * -----------------------------------
 * This RAGService class currently returns FAKE data for testing the UI.
 * The mock responses demonstrate the correct format but don't connect to
 * a real backend.
 *
 * PRODUCTION DEPLOYMENT CHECKLIST:
 * ---------------------------------
 * Before deploying to production, you MUST:
 *
 * ✅ 1. Set up your Python RAG backend with API endpoints
 * ✅ 2. Replace getResponse() with actual HTTP request
 * ✅ 3. Replace processSpeechQuery() with actual HTTP request
 * ✅ 4. Replace uploadDocuments() with actual HTTP request
 * ✅ 5. Ensure backend stores absolute file paths in vector DB metadata
 * ✅ 6. Ensure backend returns sources in {name, path} format
 * ✅ 7. Test file opening works with real uploaded files
 * ✅ 8. Handle errors properly (network failures, backend errors)
 * ✅ 9. Add loading states and user feedback
 * ✅ 10. Set up proper authentication if needed
 *
 * EXAMPLE PRODUCTION IMPLEMENTATION:
 * -----------------------------------
 * Replace the mock methods with actual API calls like this:
 *
 * ```javascript
 * async getResponse(message) {
 *   try {
 *     const response = await fetch('http://your-backend:5000/api/query', {
 *       method: 'POST',
 *       headers: {
 *         'Content-Type': 'application/json',
 *         'Authorization': 'Bearer YOUR_TOKEN'  // If using auth
 *       },
 *       body: JSON.stringify({ query: message })
 *     });
 *
 *     if (!response.ok) {
 *       throw new Error(`Backend error: ${response.status}`);
 *     }
 *
 *     const data = await response.json();
 *
 *     // Validate response format
 *     if (!data.text || !Array.isArray(data.sources)) {
 *       throw new Error('Invalid response format from backend');
 *     }
 *
 *     // Validate sources have required fields
 *     for (const source of data.sources) {
 *       if (!source.name || !source.path) {
 *         console.warn('Source missing name or path:', source);
 *       }
 *     }
 *
 *     return data;
 *   } catch (error) {
 *     console.error('RAG Service Error:', error);
 *     throw error;  // Let calling code handle the error
 *   }
 * }
 * ```
 *
 * BACKEND API ENDPOINT REQUIREMENTS:
 * -----------------------------------
 * Your Python backend should expose these endpoints:
 *
 * 1. POST /api/query
 *    - Input: {query: string}
 *    - Output: {text: string, sources: [{name, path}]}
 *
 * 2. POST /api/speech-query
 *    - Input: {audio: buffer, fileName: string}
 *    - Output: {text: string, sources: [{name, path}]}
 *
 * 3. POST /api/upload
 *    - Input: {filePaths: string[], type: string}
 *    - Output: {success: boolean, message: string}
 *
 * TESTING INTEGRATION:
 * --------------------
 * 1. Start your Python backend server
 * 2. Update the URLs in this file to point to your backend
 * 3. Upload a test document through the frontend
 * 4. Send a query and check browser DevTools (F12) for:
 *    - Network tab: verify API calls succeed
 *    - Console tab: check for errors
 * 5. Click source chips to verify files open
 *
 * ADDITIONAL RESOURCES:
 * ---------------------
 * - Backend Integration Guide: ../BACKEND_INTEGRATION_GUIDE.md
 * - Response Format Reference: ../backend/FRONTEND_RESPONSE_FORMAT.md
 * - Architecture Documentation: ../FILE_OPENING_FLOW.md
 *
 * NEED HELP?
 * ----------
 * If you encounter issues:
 * 1. Check that your backend returns the correct JSON format
 * 2. Verify file paths in responses are absolute
 * 3. Ensure CORS is configured if backend is on different port
 * 4. Check browser console for detailed error messages
 */

module.exports = new RAGService();
