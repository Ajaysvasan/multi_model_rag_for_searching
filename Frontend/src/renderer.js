// --- UI Component References ---
const chatContainer = document.getElementById('chat-container');
const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');
const micBtn = document.getElementById('mic-btn');
const chatHistoryList = document.getElementById('chat-history');
const documentList = document.getElementById('document-list');

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
});

// Configure Markdown parser for bot responses
marked.setOptions({ breaks: true, gfm: true });

/**
 * Appends a message bubble to the chat container.
 * @param {boolean} isUser - Whether the message is from the user or bot.
 * @param {string} content - The text content (supports markdown for bot).
 * @param {string[]} sources - Array of source filenames used by the bot.
 * @param {boolean} shouldSave - Whether to persist this message to history.
 */
function appendMessage(isUser, content, sources = [], shouldSave = true) {
  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;
  
  const contentDiv = document.createElement('div');
  contentDiv.className = 'message-content';
  
  if (isUser) {
    contentDiv.textContent = content; // Escape user input for security
  } else {
    contentDiv.innerHTML = marked.parse(content); // Parse bot response as Markdown
  }
  
  messageDiv.appendChild(contentDiv);

  // If the bot provides sources, render them as chips
  if (!isUser && sources && sources.length > 0) {
    const sourcesDiv = document.createElement('div');
    sourcesDiv.className = 'sources';
    sourcesDiv.innerHTML = '<h4>Sources:</h4><div class="source-chips"></div>';
    const chipsContainer = sourcesDiv.querySelector('.source-chips');
    sources.forEach(source => {
      const chip = document.createElement('span');
      chip.className = 'source-chip';
      chip.textContent = source;
      chipsContainer.appendChild(chip);
    });
    messageDiv.appendChild(sourcesDiv);
  }

  chatContainer.appendChild(messageDiv);
  chatContainer.scrollTop = chatContainer.scrollHeight; // Auto-scroll to bottom

  // Persist session to local storage (simulated in Main process)
  if (shouldSave) {
    currentSession.messages.push({ isUser, content, sources });
    // Auto-generate title from the first user message
    if (isUser && currentSession.messages.length === 1) {
      currentSession.title = content.substring(0, 30) + (content.length > 30 ? '...' : '');
    }
    saveCurrentSession();
  }

  return contentDiv;
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
 */
async function refreshHistorySidebar() {
  const history = await window.electronAPI.getHistory();
  chatHistoryList.innerHTML = '';
  
  if (history.length === 0) {
    chatHistoryList.innerHTML = '<li>No history</li>';
  }

  history.slice().reverse().forEach(session => {
    const li = document.createElement('li');
    li.dataset.id = session.id;
    if (session.id === currentSession.id) li.style.backgroundColor = '#2b2c2f';
    
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
    documentList.innerHTML = '<li>No documents uploaded</li>';
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
  chatContainer.innerHTML = '<div class="message bot-message"><div class="message-content">New session started. How can I help?</div></div>';
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
  
  session.messages.forEach(msg => {
    appendMessage(msg.isUser, msg.content, msg.sources, false);
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
 */
async function handleSendMessage() {
  const message = messageInput.value.trim();
  const audioQuery = uploadedDocs.find(doc => doc.type === 'audio' && doc.file);

  // Don't send if both message, audio and staging area are empty
  if (!message && !audioQuery && uploadedDocs.length === 0) return;

  // 1. Render user message bubble
  if (audioQuery) {
    appendMessage(true, `🎤 Voice Query: ${audioQuery.name}`);
  } else {
    appendMessage(true, message);
  }
  
  messageInput.value = '';
  messageInput.style.height = 'auto';
  
  // Disable input while waiting for bot
  messageInput.disabled = true;
  sendButton.disabled = true;
  micBtn.disabled = true;

  try {
    let response;
    
    if (audioQuery) {
      // 3a. Send speech query if audio is present
      // DEVELOPMENT TIP: We convert the browser's Blob to an ArrayBuffer 
      // because Electron's IPC works best with TypedArrays (like Uint8Array).
      // On the backend, this arrives as a Node.js Buffer.
      const arrayBuffer = await audioQuery.file.arrayBuffer();
      response = await window.electronAPI.sendSpeechQuery(new Uint8Array(arrayBuffer), audioQuery.name);
    } else {
      // 3b. Request normal text response
      response = await window.electronAPI.sendMessage(message);
    }
    
    // 2. Clear the staged uploads UI
    uploadedDocs = [];
    renderUploadedDocs();
    
    // 4. Create bot bubble and begin streaming response
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot-message';
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    messageDiv.appendChild(contentDiv);
    chatContainer.appendChild(messageDiv);
    
    await simulateStreaming(contentDiv, response.text);
    
    // 5. Append sources if provided by the backend
    if (response.sources && response.sources.length > 0) {
      const sourcesDiv = document.createElement('div');
      sourcesDiv.className = 'sources';
      sourcesDiv.innerHTML = '<h4>Sources:</h4><div class="source-chips"></div>';
      const chipsContainer = sourcesDiv.querySelector('.source-chips');
      response.sources.forEach(source => {
        const chip = document.createElement('span');
        chip.className = 'source-chip';
        chip.textContent = source;
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
});

sendButton.addEventListener('click', handleSendMessage);
micBtn.addEventListener('click', toggleRecording);

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
});

/**
 * Handles the upload trigger for specific media types.
 */
async function handleUpload(type) {
  const uploadBtn = document.getElementById('upload-btn');
  const uploadMenu = document.getElementById('upload-menu');
  const originalHTML = uploadBtn.innerHTML;
  
  uploadMenu.classList.remove('show');

  try {
    uploadBtn.disabled = true;
    uploadBtn.innerHTML = '<span class="loading-spinner"></span>';
    
    // Request Main process to open file dialog
    const result = await window.electronAPI.uploadDocuments(type);
    
    if (result.success) {
      if (result.uploadedFiles) {
        // Stage the files in the preview area
        uploadedDocs.push(...result.uploadedFiles);
        renderUploadedDocs();
      } else {
        appendMessage(false, `✅ **Success**: ${result.message}`);
      }
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
  button.addEventListener('click', () => {
    const type = button.getAttribute('data-type');
    handleUpload(type);
  });
});
