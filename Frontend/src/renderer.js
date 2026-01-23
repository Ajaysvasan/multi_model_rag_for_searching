const chatContainer = document.getElementById('chat-container');
const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');
const chatHistoryList = document.getElementById('chat-history');

// --- State Management ---
let currentSession = {
  id: Date.now().toString(),
  title: 'New Chat',
  messages: [] // Array of { isUser, content, sources }
};

// --- Initialization ---
window.addEventListener('DOMContentLoaded', async () => {
  await refreshHistorySidebar();
});

marked.setOptions({ breaks: true, gfm: true });

function appendMessage(isUser, content, sources = [], shouldSave = true) {
  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;
  
  const contentDiv = document.createElement('div');
  contentDiv.className = 'message-content';
  
  if (isUser) {
    contentDiv.textContent = content;
  } else {
    contentDiv.innerHTML = marked.parse(content);
  }
  
  messageDiv.appendChild(contentDiv);

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
  chatContainer.scrollTop = chatContainer.scrollHeight;

  // Add to session state
  if (shouldSave) {
    currentSession.messages.push({ isUser, content, sources });
    // Update title if it's the first message
    if (isUser && currentSession.messages.length === 1) {
      currentSession.title = content.substring(0, 30) + (content.length > 30 ? '...' : '');
    }
    saveCurrentSession();
  }

  return contentDiv;
}

async function saveCurrentSession() {
  await window.electronAPI.saveHistory(currentSession);
  await refreshHistorySidebar();
}

async function refreshHistorySidebar() {
  const history = await window.electronAPI.getHistory();
  chatHistoryList.innerHTML = '';
  
  history.reverse().forEach(session => {
    const li = document.createElement('li');
    li.dataset.id = session.id;
    if (session.id === currentSession.id) li.style.backgroundColor = '#2b2c2f';
    
    // Title span
    const titleSpan = document.createElement('span');
    titleSpan.className = 'session-title';
    titleSpan.textContent = session.title;
    titleSpan.addEventListener('click', () => loadSession(session.id));
    
    // Delete button
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

function startNewChat() {
  currentSession = {
    id: Date.now().toString(),
    title: 'New Chat',
    messages: []
  };
  chatContainer.innerHTML = '<div class="message bot-message"><div class="message-content">New session started. How can I help?</div></div>';
  refreshHistorySidebar();
}

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

async function simulateStreaming(element, text) {
  element.innerHTML = '';
  const tokens = text.split(' ');
  let currentText = '';
  for (const token of tokens) {
    currentText += token + ' ';
    element.innerHTML = marked.parse(currentText);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    await new Promise(resolve => setTimeout(resolve, 20));
  }
}

async function handleSendMessage() {
  const message = messageInput.value.trim();
  if (!message) return;

  appendMessage(true, message);
  messageInput.value = '';
  messageInput.style.height = 'auto';
  
  messageInput.disabled = true;
  sendButton.disabled = true;

  try {
    const response = await window.electronAPI.sendMessage(message);
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot-message';
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    messageDiv.appendChild(contentDiv);
    chatContainer.appendChild(messageDiv);
    
    await simulateStreaming(contentDiv, response.text);
    
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

    // Add bot response to session state after streaming
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
    messageInput.disabled = false;
    sendButton.disabled = false;
    messageInput.focus();
  }
}

// Event Listeners
messageInput.addEventListener('input', function() {
  this.style.height = 'auto';
  this.style.height = (this.scrollHeight) + 'px';
});

sendButton.addEventListener('click', handleSendMessage);

messageInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    handleSendMessage();
  }
});

document.getElementById('new-chat-btn').addEventListener('click', startNewChat);

document.getElementById('upload-btn').addEventListener('click', (e) => {
  e.stopPropagation();
  document.getElementById('upload-menu').classList.toggle('show');
});

// Close dropdown when clicking elsewhere
window.addEventListener('click', () => {
  document.getElementById('upload-menu').classList.remove('show');
});

async function handleUpload(type) {
  const uploadBtn = document.getElementById('upload-btn');
  const uploadMenu = document.getElementById('upload-menu');
  const originalHTML = uploadBtn.innerHTML;
  
  uploadMenu.classList.remove('show');

  try {
    uploadBtn.disabled = true;
    uploadBtn.innerHTML = '<span class="loading-spinner"></span>';
    
    const result = await window.electronAPI.uploadDocuments(type);
    
    if (result.success) {
      appendMessage(false, `✅ **Success**: ${result.message}`);
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

document.querySelectorAll('.upload-item').forEach(button => {
  button.addEventListener('click', () => {
    const type = button.getAttribute('data-type');
    handleUpload(type);
  });
});
