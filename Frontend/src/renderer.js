// --- UI Component References ---
const chatContainer = document.getElementById('chat-container');
const mainContent = document.getElementById('main-content');
const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');
const micBtn = document.getElementById('mic-btn');
const chatHistoryList = document.getElementById('chat-history');
const chatSearch = document.getElementById('chat-search');
const documentList = document.getElementById('document-list');
const scrollDownBtn = document.getElementById('scroll-down-btn');
const sidebar = document.getElementById('sidebar');
const sidebarToggle = document.getElementById('sidebar-toggle');

// --- State Management ---
// Tracks the current active session (messages, title, id)
let currentSession = {
  id: Date.now().toString(),
  title: 'New Chat',
  messages: [] // Array of { isUser, content, sources }
};

// Tracks files uploaded by the user that are staged but not yet "sent" in a prompt
let uploadedDocs = [];

// --- Audio Recording State ---
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;

// --- Initialization ---
// Load initial data from the "Main Process" via IPC
window.addEventListener('DOMContentLoaded', async () => {
  await refreshHistorySidebar();
  await refreshDocumentList();

  // Initial state should be new chat mode if no session is loaded or active
  if (currentSession.messages.length === 0) {
    mainContent.classList.add('new-chat-mode');
    chatContainer.innerHTML = '';
  }

  // Listen for refresh requests from the native app menu (File -> Upload)
  // This ensures the sidebar updates even if the upload wasn't started from the UI buttons.
  window.electronAPI.onDocumentsRefreshed(async () => {
    await refreshDocumentList();
  });

  // Handle chat history search
  chatSearch.addEventListener('input', async (e) => {
    const searchTerm = e.target.value.toLowerCase();
    await refreshHistorySidebar(searchTerm);
  });
});

// Configure Markdown parser for bot responses
marked.setOptions({ breaks: true, gfm: true });

/**
 * Appends a message bubble to the chat container.
 *
 * This is called whenever a new message (user or bot) needs to be displayed in the chat.
 * For bot messages, it also handles displaying source documents as clickable chips.
 *
 * @param {boolean} isUser - Whether the message is from the user or bot
 * @param {string} content - The text content (plain text for user, Markdown for bot)
 * @param {Array<string|object>} sources - Array of source documents. Can be in two formats:
 *
 *   FORMAT 1 (Legacy - still supported):
 *   ["file.pdf", "doc.txt"]
 *
 *   FORMAT 2 (New - enables file opening):
 *   [
 *     {name: "file.pdf", path: "/absolute/path/to/file.pdf"},
 *     {name: "doc.txt", path: "C:\\docs\\doc.txt"}
 *   ]
 *
 * @param {boolean} shouldSave - Whether to persist this message to history
 *
 * BACKEND INTEGRATION NOTE:
 * When your RAG backend returns a response, include sources in Format 2 (with paths)
 * to enable clickable source chips that open files.
 */
function appendMessage(isUser, content, sources = [], shouldSave = true) {
  // Create the main message container
  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;

  // Create the content area
  const contentDiv = document.createElement('div');
  contentDiv.className = 'message-content';

  if (isUser) {
    // User messages: Use plain text for security (prevent XSS)
    contentDiv.textContent = content;
  } else {
    // Bot messages: Parse Markdown for rich formatting
    // Supports: **bold**, *italic*, `code`, ```blocks```, lists, links, etc.
    contentDiv.innerHTML = marked.parse(content);
  }

  messageDiv.appendChild(contentDiv);

  // ======================================================================
  // RENDER SOURCE CHIPS (only for bot messages with sources)
  // ======================================================================
  // This is where the source documents are displayed as clickable chips
  if (!isUser && sources && sources.length > 0) {
    // Create sources container
    const sourcesDiv = document.createElement('div');
    sourcesDiv.className = 'sources';
    sourcesDiv.innerHTML = '<h4>Sources:</h4><div class="source-chips"></div>';
    const chipsContainer = sourcesDiv.querySelector('.source-chips');

    // Create a chip for each source
    // The createSourceChip() function handles:
    // - Creating the visual chip element
    // - Making it clickable if path is provided
    // - Adding click handlers to open files
    sources.forEach(source => {
      const chip = createSourceChip(source);  // ✨ Uses the new function
      chipsContainer.appendChild(chip);
    });

    messageDiv.appendChild(sourcesDiv);
  }

  // Add message to chat and scroll to bottom
  chatContainer.appendChild(messageDiv);
  chatContainer.scrollTop = chatContainer.scrollHeight; // Auto-scroll to bottom

  // Save to chat history
  if (shouldSave) {
    currentSession.messages.push({ isUser, content, sources });

    // Auto-generate chat title from first user message
    if (isUser && currentSession.messages.length === 1) {
      currentSession.title = content.substring(0, 30) + (content.length > 30 ? '...' : '');
    }

    saveCurrentSession();
  }

  return contentDiv;
}

// ============================================================================
// ✨ NEW FUNCTION: CREATE CLICKABLE SOURCE CHIP
// ============================================================================
/**
 * Creates a clickable source chip element for displaying RAG source documents.
 *
 * WHAT THIS FUNCTION DOES:
 * ------------------------
 * 1. Creates a small "pill" UI element showing the source document name
 * 2. If a file path is provided, makes it clickable to open the file
 * 3. Adds visual feedback (hover effects, tooltips)
 * 4. Handles click events to open files in system default applications
 *
 * USER EXPERIENCE:
 * ----------------
 * - User sees: [📄 annual_report_2023.pdf] below the bot response
 * - Hover: Chip turns green with slight lift effect
 * - Click: File opens in Adobe Reader/Word/Excel/etc.
 * - Tooltip: Shows full file path on hover
 *
 * BACKEND INTEGRATION GUIDE:
 * ==========================
 * This function accepts TWO FORMATS for the 'source' parameter:
 *
 * FORMAT 1: Legacy (filename only) - BACKWARDS COMPATIBLE
 * --------------------------------------------------------
 * source = "annual_report_2023.pdf"
 *
 * Result:
 * - Displays filename in chip
 * - NOT clickable (no hover effect)
 * - Still works for displaying source names
 *
 * Example backend response:
 * {
 *   text: "Based on the documents...",
 *   sources: ["annual_report.pdf", "project_specs.docx"]
 * }
 *
 * FORMAT 2: With file path (object) - ✅ RECOMMENDED
 * --------------------------------------------------
 * source = {
 *   name: "annual_report_2023.pdf",
 *   path: "/absolute/path/to/documents/annual_report_2023.pdf"
 * }
 *
 * Result:
 * - Displays filename in chip
 * - CLICKABLE with green hover effect
 * - Opens file when clicked
 * - Shows path in tooltip
 *
 * Example backend response:
 * {
 *   text: "Based on the documents...",
 *   sources: [
 *     {
 *       name: "annual_report.pdf",
 *       path: "C:\\Users\\your-username\\Documents\\annual_report.pdf"
 *     },
 *     {
 *       name: "data.xlsx",
 *       path: "/home/user/files/data.xlsx"
 *     }
 *   ]
 * }
 *
 * CRITICAL REQUIREMENTS FOR BACKEND:
 * ==================================
 * 1. PATH MUST BE ABSOLUTE (not relative)
 *    ✅ Good: "C:\\Users\\your-username\\docs\\file.pdf"
 *    ✅ Good: "/home/user/documents/file.pdf"
 *    ❌ Bad:  "./documents/file.pdf"
 *    ❌ Bad:  "../file.pdf"
 *
 * 2. PATH SHOULD POINT TO ORIGINAL UPLOADED FILE
 *    - Store the upload path in your vector DB metadata
 *    - Return this path when chunks from that file are retrieved
 *
 * 3. CROSS-PLATFORM PATHS WORK
 *    - Windows: "C:\\Users\\your-username\\file.pdf" (backslashes)
 *    - macOS:   "/Users/your-username/file.pdf" (forward slashes)
 *    - Linux:   "/home/your-username/file.pdf" (forward slashes)
 *    - All formats work automatically!
 *
 * HOW BACKEND SHOULD IMPLEMENT:
 * ==============================
 * Step 1: Store paths during document upload
 * -------------------------------------------
 * When frontend uploads a file, it sends the absolute path.
 * Store this in your vector DB chunk metadata:
 *
 * Python example:
 * ```python
 * for file_path in uploaded_files:
 *     chunks = chunk_document(file_path)
 *     for chunk in chunks:
 *         vector_db.add(
 *             text=chunk.text,
 *             embedding=chunk.embedding,
 *             metadata={
 *                 "source_file": file_path,  # ← Store absolute path
 *                 "file_name": os.path.basename(file_path),
 *                 "page": chunk.page
 *             }
 *         )
 * ```
 *
 * Step 2: Return paths during RAG query
 * --------------------------------------
 * When processing a user query:
 *
 * Python example:
 * ```python
 * # Retrieve relevant chunks
 * results = vector_db.search(query_embedding, top_k=5)
 *
 * # Extract unique source files
 * sources = []
 * seen_paths = set()
 * for chunk in results:
 *     path = chunk.metadata["source_file"]
 *     name = chunk.metadata["file_name"]
 *     if path not in seen_paths:
 *         sources.append({"name": name, "path": path})
 *         seen_paths.add(path)
 *
 * # Return in correct format
 * return {
 *     "text": llm_generated_response,
 *     "sources": sources  # ← Array of {name, path} objects
 * }
 * ```
 *
 * TESTING YOUR BACKEND INTEGRATION:
 * ==================================
 * 1. Upload a real file through the frontend
 * 2. Note the file path that gets sent to your backend
 * 3. Verify that path is stored in your vector DB metadata
 * 4. Ask a question that should retrieve that file
 * 5. Check response includes source with correct name and path
 * 6. Click the source chip in the UI
 * 7. File should open in your system's default application
 *
 * DEBUGGING TIPS:
 * ===============
 * - Open browser DevTools (F12) to see console logs
 * - Check that sources array has {name, path} format
 * - Verify paths are absolute (start with C:\ or /)
 * - Ensure file exists at the specified path
 * - Test with a simple text file first
 *
 * @param {string|object} source - Either a filename string or an object with {name, path}
 * @returns {HTMLElement} A source chip element (clickable if path provided)
 *
 * @example
 * // Legacy format (still works, but not clickable)
 * createSourceChip("report.pdf");
 *
 * @example
 * // New format (clickable)
 * createSourceChip({
 *   name: "report.pdf",
 *   path: "C:\\Users\\your-username\\Documents\\report.pdf"
 * });
 */
function createSourceChip(source) {
  // STEP 1: Create the basic chip element
  const chip = document.createElement('span');
  chip.className = 'source-chip';

  // STEP 2: Extract name and path (handle both string and object formats)
  // This makes the function backwards compatible with old code that just passed strings
  const sourceName = typeof source === 'string' ? source : source.name;
  const sourcePath = typeof source === 'object' ? source.path : null;

  // STEP 3: Set the display text (filename)
  chip.textContent = sourceName;

  // STEP 4: If we have a file path, make the chip clickable
  if (sourcePath) {
    // Add 'clickable' class for CSS styling (green hover effect, pointer cursor)
    chip.classList.add('clickable');

    // Set tooltip to show full file path
    chip.title = `Click to open: ${sourcePath}`;

    // STEP 5: Add click event listener to open the file
    chip.addEventListener('click', async () => {
      try {
        // Call the Electron API to open the file
        // This goes through: renderer.js → preload.js → index.js → shell.openPath()
        const result = await window.electronAPI.openFile(sourcePath);

        // STEP 6: Handle errors (file not found, permission denied, etc.)
        if (!result.success) {
          console.error('Failed to open file:', result.error);
          // Show user-friendly error message
          alert(`Could not open file: ${result.error}`);
        }
        // If successful, the file is now open in the default application!
        // No need for additional feedback - the OS provides that

      } catch (error) {
        // Handle unexpected errors (network issues, IPC failure, etc.)
        console.error('Error opening file:', error);
        alert('An error occurred while trying to open the file.');
      }
    });

  } else {
    // STEP 7: No path provided - just show the filename (not clickable)
    // This maintains backwards compatibility with old backend responses
    chip.title = sourceName;
    // Note: Without the 'clickable' class, the chip won't have hover effects
  }

  return chip;
}

/**
 * Updates the UI to show staged document previews above the input box.
 * This mimics the ChatGPT behavior where uploads are visible before sending.
 */
function renderUploadedDocs() {
  const previewContainer = document.getElementById('uploaded-docs-preview');
  previewContainer.innerHTML = '';
  
  if (uploadedDocs.length === 0) {
    previewContainer.style.display = 'none';
    return;
  }
  
  previewContainer.style.display = 'flex';
  
  uploadedDocs.forEach((doc, index) => {
    const pill = document.createElement('div');
    pill.className = 'uploaded-doc-pill';
    
    const icon = getDocumentIcon(doc.type);
    
    pill.innerHTML = `
      ${icon}
      <span title="${doc.name}">${doc.name}</span>
      <div class="remove-doc" data-index="${index}">&times;</div>
    `;
    
    // Allow user to remove a staged document before sending
    pill.querySelector('.remove-doc').addEventListener('click', () => {
      uploadedDocs.splice(index, 1);
      renderUploadedDocs();
    });
    
    previewContainer.appendChild(pill);
  });

  // Display success message for batch uploads
  if (uploadedDocs.length >= 2) {
    const successMsg = document.createElement('div');
    successMsg.style.width = '100%';
    successMsg.style.fontSize = '0.75rem';
    successMsg.style.color = 'var(--accent-color)';
    successMsg.style.marginTop = '2px';
    successMsg.textContent = `Successfully uploaded ${uploadedDocs.length} documents`;
    previewContainer.appendChild(successMsg);
  }
}

async function saveCurrentSession() {
  await window.electronAPI.saveHistory(currentSession);
  await refreshHistorySidebar();
}

/**
 * Re-renders the sidebar chat history list.
 * @param {string} filter - Optional search term to filter chat titles.
 */
async function refreshHistorySidebar(filter = chatSearch ? chatSearch.value : '') {
  const history = await window.electronAPI.getHistory();
  chatHistoryList.innerHTML = '';
  
  
  const filteredHistory = history.filter(session => 
    session.title.toLowerCase().includes(filter.toLowerCase())
  );
  
  if (filteredHistory.length === 0) {
    chatHistoryList.innerHTML = `<li>${filter ? 'No matches' : 'No history'}</li>`;
    return;
  }

  filteredHistory.slice().reverse().forEach(session => {
    const li = document.createElement('li');
    li.dataset.id = session.id;
    if (session.id === currentSession.id) li.classList.add('active');
    
    const titleSpan = document.createElement('span');
    titleSpan.className = 'session-title';
    titleSpan.textContent = session.title;
    titleSpan.addEventListener('click', () => loadSession(session.id));
    
    const delBtn = document.createElement('button');
    delBtn.className = 'delete-session-btn';
    delBtn.innerHTML = '&#10005;'; // X symbol
    delBtn.title = 'Delete Chat';
    delBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      if (confirm('Are you sure you want to delete this chat?')) {
        await window.electronAPI.deleteHistory(session.id);
        if (currentSession.id === session.id) {
          startNewChat();
        } else {
          await refreshHistorySidebar();
        }
      }
    });

    li.appendChild(titleSpan);
    li.appendChild(delBtn);
    chatHistoryList.appendChild(li);
  });
}

/**
 * Re-renders the sidebar "Documents" list with all indexed files.
 */
async function refreshDocumentList() {
  const documents = await window.electronAPI.getDocuments();
  documentList.innerHTML = '';
  
  if (documents.length === 0) {
    documentList.innerHTML = '<li>No files uploaded</li>';
    return;
  }

  documents.slice().reverse().forEach(doc => {
    const li = document.createElement('li');
    li.className = 'document-item';
    
    const icon = getDocumentIcon(doc.type);
    
    li.innerHTML = `
      ${icon}
      <div class="document-info">
        <span class="document-name" title="${doc.path}">${doc.name}</span>
        <span class="document-date">${doc.date}</span>
      </div>
    `;
    documentList.appendChild(li);
  });
}

function getDocumentIcon(type) {
  switch (type) {
    case 'video':
      return '<svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M17,10.5V7A1,1 0 0,0 16,6H4A1,1 0 0,0 3,7V17A1,1 0 0,0 4,18H16A1,1 0 0,0 17,17V13.5L21,17.5V6.5L17,10.5Z"/></svg>';
    case 'audio':
      return '<svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M12,2A3,3 0 0,0 9,5V11A3,3 0 0,0 12,14A3,3 0 0,0 15,11V5A3,3 0 0,0 12,2M19,11C19,14.53 16.39,17.44 13,17.93V21H11V17.93C7.61,17.44 5,14.53 5,11H7A5,5 0 0,0 12,16A5,5 0 0,0 17,11H19Z"/></svg>';
    case 'image':
      return '<svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M8.5,13.5L11,16.5L14.5,12L19,18H5M21,19V5C21,3.89 20.1,3 19,3H5A2,2 0 0,0 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19Z"/></svg>';
    default:
      return '<svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M13,9V3.5L18.5,9H13Z"/></svg>';
  }
}

/**
 * Resets the UI for a fresh chat session.
 */
function startNewChat() {
  currentSession = {
    id: Date.now().toString(),
    title: 'New Chat',
    messages: []
  };
  uploadedDocs = [];
  renderUploadedDocs();
  chatContainer.innerHTML = '';

  // Clear any existing focus to prevent stuck cursor
  if (document.activeElement && document.activeElement !== messageInput) {
    document.activeElement.blur();
  }

  // Ensure input is enabled and cleared when starting a new chat
  messageInput.disabled = false;
  messageInput.readOnly = false;
  messageInput.value = '';
  messageInput.style.height = 'auto';

  if (chatSearch) chatSearch.value = '';

  // Add the class after preparing the input
  mainContent.classList.add('new-chat-mode');

  // Wait for CSS transition to complete (300ms) plus buffer
  // This is critical because #main-content has "transition: all 0.3s ease"
  setTimeout(() => {
    // Force focus multiple times to ensure it sticks
    const forceFocus = () => {
      messageInput.disabled = false;
      messageInput.readOnly = false;
      messageInput.focus();

      // Set cursor position
      const length = messageInput.value.length;
      messageInput.setSelectionRange(length, length);

      // Trigger click to ensure cursor visibility
      messageInput.click();
    };

    // Try focusing immediately
    forceFocus();

    // Try again after a small delay to be absolutely sure
    setTimeout(forceFocus, 50);
  }, 350); // Wait for 300ms transition + 50ms buffer

  refreshHistorySidebar();
}

/**
 * Loads a saved session from the simulated history database.
 */
async function loadSession(sessionId) {
  const history = await window.electronAPI.getHistory();
  const session = history.find(s => s.id === sessionId);
  if (!session) return;

  currentSession = session;
  chatContainer.innerHTML = '';
  mainContent.classList.remove('new-chat-mode');

  session.messages.forEach(msg => {
    appendMessage(msg.isUser, msg.content, msg.sources, false);
  });

  // Clear any existing focus to prevent stuck cursor
  if (document.activeElement) {
    document.activeElement.blur();
  }

  // Ensure input is enabled when switching sessions
  messageInput.disabled = false;

  // Focus with proper delay to ensure DOM is settled
  requestAnimationFrame(() => {
    setTimeout(() => {
      // Restore input state
      messageInput.disabled = false;
      messageInput.readOnly = false;

      // Focus and ensure cursor appears
      messageInput.focus();
      messageInput.click();

      // Explicitly set cursor position at the end
      const length = messageInput.value.length;
      messageInput.setSelectionRange(length, length);
    }, 100);
  });

  await refreshHistorySidebar();
}

/**
 * Simulates real-time token streaming for bot responses.
 * @param {HTMLElement} element - The DOM element to stream text into.
 * @param {string} text - The full response text.
 */
async function simulateStreaming(element, text) {
  element.innerHTML = '';
  const tokens = text.split(' ');
  let currentText = '';
  for (const token of tokens) {
    currentText += token + ' ';
    element.innerHTML = marked.parse(currentText);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    await new Promise(resolve => setTimeout(resolve, 20)); // Simulated speed
  }
}

/**
 * Toggles the audio recording state and handles the recording lifecycle.
 * Uses the Web MediaRecorder API to capture audio from the user's microphone.
 */
async function toggleRecording() {
  if (!isRecording) {
    try {
      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // Detect supported MIME type and determine the appropriate file extension
      // We check for MP3, WAV, Ogg, AAC/MP4, and WebM in order of preference
      let mimeType = 'audio/webm';
      let extension = 'webm';

      if (MediaRecorder.isTypeSupported('audio/mpeg')) {
        mimeType = 'audio/mpeg';
        extension = 'mp3';
      } else if (MediaRecorder.isTypeSupported('audio/wav')) {
        mimeType = 'audio/wav';
        extension = 'wav';
      } else if (MediaRecorder.isTypeSupported('audio/ogg; codecs=opus')) {
        mimeType = 'audio/ogg; codecs=opus';
        extension = 'ogg';
      } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
        mimeType = 'audio/mp4';
        extension = 'm4a';
      }
      
      mediaRecorder = new MediaRecorder(stream, { mimeType });
      audioChunks = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunks.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        // Create a Blob using the actual recorded MIME type to ensure file integrity
        const audioBlob = new Blob(audioChunks, { type: mimeType });
        
        // Generate a filename with the correct extension (mp3 or webm) based on browser support
        const audioFile = new File([audioBlob], `speech_query_${Date.now()}.${extension}`, { type: mimeType });
        
        // Add recorded audio to staged documents for preview
        uploadedDocs.push({
          name: audioFile.name,
          type: 'audio',
          path: URL.createObjectURL(audioBlob), // Local preview URL
          file: audioFile // Actual file object for the backend
        });
        
        renderUploadedDocs();
        
        // Stop all tracks in the stream to release the microphone
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      isRecording = true;
      micBtn.classList.add('recording');
      micBtn.title = 'Stop Recording';
      messageInput.placeholder = 'Recording... Speak now.';
    } catch (err) {
      console.error('Error accessing microphone:', err);
      alert('Could not access microphone. Please check permissions.');
    }
  } else {
    // Stop recording
    mediaRecorder.stop();
    isRecording = false;
    micBtn.classList.remove('recording');
    micBtn.title = 'Record Speech Query';
    messageInput.placeholder = 'Ask anything about your documents...';
  }
}

/**
 * Core function for handling user input and triggering the RAG response flow.
 *
 * FLOW OVERVIEW:
 * 1. User types message and clicks send
 * 2. Display user message in chat
 * 3. Send query to backend (via ragService.js)
 * 4. Backend processes query through RAG pipeline
 * 5. Backend returns {text, sources} response
 * 6. Display bot response with streaming effect
 * 7. Display source chips below response ✨
 * 8. User can click chips to open files
 *
 * BACKEND INTEGRATION:
 * This function expects the backend to return:
 * {
 *   text: string,         // LLM response (Markdown formatted)
 *   sources: Array        // Source documents
 * }
 */
async function handleSendMessage() {
  const message = messageInput.value.trim();
  const audioQuery = uploadedDocs.find(doc => doc.type === 'audio' && doc.file);

  // Don't send if both message, audio and staging area are empty
  if (!message && !audioQuery && uploadedDocs.length === 0) return;

  // STEP 1: Render user message bubble
  if (mainContent.classList.contains('new-chat-mode')) {
    mainContent.classList.remove('new-chat-mode');
  }

  if (audioQuery) {
    appendMessage(true, `🎤 Voice Query: ${audioQuery.name}`);
  } else {
    appendMessage(true, message);
  }

  messageInput.value = '';
  messageInput.style.height = 'auto';

  // STEP 2: Disable input while waiting for bot response
  messageInput.disabled = true;
  sendButton.disabled = true;
  micBtn.disabled = true;

  try {
    let response;

    // STEP 3: Send query to backend
    if (audioQuery) {
      // 3a. Send speech query if audio is present
      // DEVELOPMENT TIP: We convert the browser's Blob to an ArrayBuffer
      // because Electron's IPC works best with TypedArrays (like Uint8Array).
      // On the backend, this arrives as a Node.js Buffer.
      const arrayBuffer = await audioQuery.file.arrayBuffer();
      response = await window.electronAPI.sendSpeechQuery(new Uint8Array(arrayBuffer), audioQuery.name);
    } else {
      // 3b. Request normal text response
      // This calls: preload.js → index.js → ragService.js → YOUR BACKEND
      response = await window.electronAPI.sendMessage(message);
    }

    // STEP 4: Clear the staged uploads UI
    uploadedDocs = [];
    renderUploadedDocs();

    // STEP 5: Create bot message bubble
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot-message';
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    messageDiv.appendChild(contentDiv);
    chatContainer.appendChild(messageDiv);

    // STEP 6: Stream the response text with typing effect
    await simulateStreaming(contentDiv, response.text);

    // ======================================================================
    // STEP 7: RENDER SOURCE CHIPS ✨
    // ======================================================================
    // This is where source documents are displayed as clickable chips
    //
    // BACKEND INTEGRATION NOTE:
    // The 'response.sources' should be an array of objects like:
    // [
    //   {name: "report.pdf", path: "C:\\Users\\your-username\\Documents\\report.pdf"},
    //   {name: "data.xlsx", path: "/home/user/files/data.xlsx"}
    // ]
    //
    // Each source chip will be:
    // - Displayed below the bot response
    // - Clickable to open the file
    // - Show green hover effect
    // - Display tooltip with full path
    if (response.sources && response.sources.length > 0) {
      // Create sources container
      const sourcesDiv = document.createElement('div');
      sourcesDiv.className = 'sources';
      sourcesDiv.innerHTML = '<h4>Sources:</h4><div class="source-chips"></div>';
      const chipsContainer = sourcesDiv.querySelector('.source-chips');

      // Create a chip for each source
      // The createSourceChip() function handles:
      // - Creating the chip element
      // - Making it clickable if path is provided
      // - Adding click handler to open file
      // - Adding hover effects
      response.sources.forEach(source => {
        const chip = createSourceChip(source);  // ✨ Creates clickable chip
        chipsContainer.appendChild(chip);
      });

      messageDiv.appendChild(sourcesDiv);
    }

    // 6. Update session state after streaming completes
    currentSession.messages.push({ 
      isUser: false, 
      content: response.text, 
      sources: response.sources 
    });
    saveCurrentSession();
    
    chatContainer.scrollTop = chatContainer.scrollHeight;
  } catch (error) {
    console.error('Error:', error);
    appendMessage(false, 'Error: Failed to connect to RAG backend.', [], false);
  } finally {
    // Re-enable input
    messageInput.disabled = false;
    sendButton.disabled = false;
    micBtn.disabled = false;
    messageInput.focus();
  }
}

// --- Event Listeners ---

// Auto-expand textarea based on content
messageInput.addEventListener('input', function() {
  this.style.height = 'auto';
  this.style.height = (this.scrollHeight) + 'px';

  // Return to centered "New Chat" mode if input is cleared and no messages exist
  if (currentSession.messages.length === 0) {
    if (this.value.trim().length > 0) {
      mainContent.classList.remove('new-chat-mode');
    } else {
      mainContent.classList.add('new-chat-mode');
    }
  }
});

sendButton.addEventListener('click', handleSendMessage);
micBtn.addEventListener('click', toggleRecording);

// Explicit focus on click to ensure cursor appears
messageInput.addEventListener('click', () => {
  messageInput.focus();
});

// Allow Enter key to send (Shift+Enter for newline)
messageInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    handleSendMessage();
  }
});

document.getElementById('new-chat-btn').addEventListener('click', startNewChat);

// Toggle the upload type dropdown
document.getElementById('upload-btn').addEventListener('click', (e) => {
  e.stopPropagation();
  document.getElementById('upload-menu').classList.toggle('show');
});

window.addEventListener('click', () => {
  document.getElementById('upload-menu').classList.remove('show');
  document.getElementById('settings-menu').classList.remove('show');
});

// --- Settings & Appearance Logic ---

const settingsBtn = document.getElementById('settings-btn');
const settingsMenu = document.getElementById('settings-menu');

// Toggle Settings Menu
settingsBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  settingsMenu.classList.toggle('show');
  // Close upload menu if open
  document.getElementById('upload-menu').classList.remove('show');
});

// Theme Switching
document.querySelectorAll('.appearance-item').forEach(button => {
  button.addEventListener('click', async (e) => {
    e.stopPropagation();
    const theme = button.getAttribute('data-theme');
    
    if (theme === 'custom') {
      let imagePath = localStorage.getItem('customThemePath');
      if (!imagePath) {
        imagePath = await window.electronAPI.getDefaultImagePath();
      } else {
        // Optional: still allow user to pick a NEW one if they click it again?
        // Let's stick to the requirement: "When Custom Image theme is selected: Open a native Electron file picker"
        // But if they just want to use the existing one, we should probably check if they want to change it.
        // For simplicity and following the "it is not working" feedback, let's make it easy to select.
        const newPath = await window.electronAPI.selectThemeImage();
        if (newPath) imagePath = newPath;
      }
      
      if (imagePath) {
        applyCustomTheme(imagePath);
        localStorage.setItem('theme', 'custom');
        localStorage.setItem('customThemePath', imagePath);
      }
    } else {
      document.body.classList.remove('custom-theme');
      if (theme === 'dark') {
        document.body.classList.add('dark-mode');
        document.body.classList.remove('light-mode');
        localStorage.setItem('baseTheme', 'dark');
      } else {
        document.body.classList.add('light-mode');
        document.body.classList.remove('dark-mode');
        localStorage.setItem('baseTheme', 'light');
      }
      localStorage.setItem('theme', theme);
    }
    settingsMenu.classList.remove('show');
  });
});

function applyCustomTheme(imagePath) {
  document.body.classList.add('custom-theme');
  // Normalize backslashes to forward slashes for URL compatibility
  const normalizedPath = imagePath.replace(/\\/g, '/');
  const formattedPath = `local-resource://${normalizedPath}`;
  document.documentElement.style.setProperty('--bg-image', `url(${JSON.stringify(formattedPath)})`);
}

// Load saved theme
const savedTheme = localStorage.getItem('theme');
const savedBaseTheme = localStorage.getItem('baseTheme') || 'dark';

if (savedBaseTheme === 'dark') {
  document.body.classList.add('dark-mode');
  document.body.classList.remove('light-mode');
} else {
  document.body.classList.add('light-mode');
  document.body.classList.remove('dark-mode');
}

if (savedTheme === 'custom') {
  const customPath = localStorage.getItem('customThemePath');
  if (customPath) {
    applyCustomTheme(customPath);
  }
}

/**
 * Handles webcam photo capture and upload.
 */
async function handleWebcamCapture() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });

    // Create temporary video element
    const video = document.createElement('video');
    video.srcObject = stream;
    video.style.display = 'none';
    document.body.appendChild(video);
    video.play();

    // Wait for video metadata
    await new Promise(resolve => {
      video.onloadedmetadata = resolve;
    });

    // Create canvas for capture
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0);

    // Stop stream and remove video
    stream.getTracks().forEach(track => track.stop());
    document.body.removeChild(video);

    // Convert to buffer and upload
    canvas.toBlob(async blob => {
      const fileName = `webcam_${Date.now()}.png`;
      const arrayBuffer = await blob.arrayBuffer();
      const imageBuffer = new Uint8Array(arrayBuffer);

      // Upload via IPC
      const result = await window.electronAPI.uploadWebcam(imageBuffer, fileName);

      if (result.success) {
        if (result.uploadedFiles) {
          // Stage the files in the preview area
          uploadedDocs.push(...result.uploadedFiles);
          renderUploadedDocs();
        }
        // Refresh the sidebar list
        await refreshDocumentList();
      } else {
        appendMessage(false, `❌ **Error**: ${result.message}`);
      }
    }, 'image/png');
  } catch (error) {
    console.error('Webcam capture error:', error);
    alert('Could not access webcam. Please check permissions.');
  }
}

/**
 * Handles the upload trigger for specific media types.
 * @param {string} type - 'document', 'folder', 'video', etc.
 * @param {HTMLElement} sourceButton - The button that triggered the upload (for showing loading state).
 */
async function handleUpload(type, sourceButton = null) {
  const uploadBtn = sourceButton || document.getElementById('upload-btn');
  const uploadMenu = document.getElementById('upload-menu');
  const originalHTML = uploadBtn.innerHTML;

  if (uploadMenu) {
    uploadMenu.classList.remove('show');
  }

  if (type === 'webcam') {
    // Handle webcam capture directly in renderer
    await handleWebcamCapture();
    return;
  }

  try {
    // Show loading state while the Main process handles file selection and RAG ingestion.
    uploadBtn.disabled = true;
    uploadBtn.innerHTML = '<span class="loading-spinner"></span>';

    // Request Main process to open file dialog and process files.
    const result = await window.electronAPI.uploadDocuments(type);

    if (result.success) {
      if (result.uploadedFiles) {
        // Stage the files in the preview area if they are intended for the next chat prompt.
        uploadedDocs.push(...result.uploadedFiles);
        renderUploadedDocs();
      } else {
        // Show confirmation if it was a direct background ingestion.
        appendMessage(false, `✅ **Success**: ${result.message}`);
      }
      // Refresh the sidebar list to show the newly indexed documents.
      await refreshDocumentList();
    } else if (result.message !== 'Upload canceled') {
      appendMessage(false, `❌ **Error**: ${result.message}`);
    }
  } catch (error) {
    console.error('Upload Error:', error);
    appendMessage(false, `❌ **Error**: An unexpected error occurred during ${type} upload.`);
  } finally {
    uploadBtn.disabled = false;
    uploadBtn.innerHTML = originalHTML;
  }
}

// Attach listeners to all upload menu items
document.querySelectorAll('.upload-item').forEach(button => {
  button.addEventListener('click', (e) => {
    e.stopPropagation();
    const type = button.getAttribute('data-type');
    handleUpload(type);
  });
});

// --- Scroll Down Logic ---
chatContainer.addEventListener('scroll', () => {
  // Show button if user scrolls up more than 100px from the bottom
  const threshold = 100;
  const isAtBottom = chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight <= threshold;
  
  if (isAtBottom) {
    scrollDownBtn.classList.remove('show');
  } else {
    scrollDownBtn.classList.add('show');
  }
});

scrollDownBtn.addEventListener('click', () => {
  chatContainer.scrollTo({
    top: chatContainer.scrollHeight,
    behavior: 'smooth'
  });
});

// Sidebar Toggle Logic
sidebarToggle.addEventListener('click', () => {
  const isClosed = sidebar.classList.toggle('closed');
  sidebarToggle.title = isClosed ? 'Open Sidebar' : 'Close Sidebar';
});
