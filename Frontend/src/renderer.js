const chatContainer = document.getElementById("chat-container");
const mainContent = document.getElementById("main-content");
const messageInput = document.getElementById("message-input");
const sendButton = document.getElementById("send-button");
const micBtn = document.getElementById("mic-btn");
const chatHistoryList = document.getElementById("chat-history");
const chatSearch = document.getElementById("chat-search");
const documentList = document.getElementById("document-list");
const scrollDownBtn = document.getElementById("scroll-down-btn");
const sidebar = document.getElementById("sidebar");
const sidebarToggle = document.getElementById("sidebar-toggle");

// Tracks the current active session (messages, title, id)
let currentSession = {
  id: Date.now().toString(),
  title: "New Chat",
  messages: [], // Array of { isUser, content, sources }
};

// Tracks files uploaded by the user that are staged but not yet "sent" in a prompt
let uploadedDocs = [];

// --- Audio Recording State ---
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;

// --- Initialization ---
// Load initial data from the "Main Process" via IPC
window.addEventListener("DOMContentLoaded", async () => {
  await refreshHistorySidebar();
  await refreshDocumentList();

  // Initial state should be new chat mode if no session is loaded or active
  if (currentSession.messages.length === 0) {
    mainContent.classList.add("new-chat-mode");
    chatContainer.innerHTML = "";
  }

  // Listen for refresh requests from the native app menu (File -> Upload)
  // This ensures the sidebar updates even if the upload wasn't started from the UI buttons.
  window.electronAPI.onDocumentsRefreshed(async () => {
    await refreshDocumentList();
  });

  // Handle chat history search
  chatSearch.addEventListener("input", async (e) => {
    const searchTerm = e.target.value.toLowerCase();
    await refreshHistorySidebar(searchTerm);
  });
});

// Configure Markdown parser for bot responses
marked.setOptions({ breaks: true, gfm: true });

function appendMessage(isUser, content, sources = [], shouldSave = true) {
  // Create the main message container
  const messageDiv = document.createElement("div");
  messageDiv.className = `message ${isUser ? "user-message" : "bot-message"}`;

  // Create the content area
  const contentDiv = document.createElement("div");
  contentDiv.className = "message-content";

  if (isUser) {
    // User messages: Use plain text for security (prevent XSS)
    contentDiv.textContent = content;
  } else {
    contentDiv.innerHTML = marked.parse(content);
  }

  messageDiv.appendChild(contentDiv);

  // This is where the source documents are displayed as clickable chips
  if (!isUser && sources && sources.length > 0) {
    // Create sources container
    const sourcesDiv = document.createElement("div");
    sourcesDiv.className = "sources";
    sourcesDiv.innerHTML = '<h4>Sources:</h4><div class="source-chips"></div>';
    const chipsContainer = sourcesDiv.querySelector(".source-chips");

    sources.forEach((source) => {
      const chip = createSourceChip(source);
      chipsContainer.appendChild(chip);
    });

    messageDiv.appendChild(sourcesDiv);
  }

  // Add message to chat and scroll to bottom
  chatContainer.appendChild(messageDiv);
  chatContainer.scrollTop = chatContainer.scrollHeight;
  // Save to chat history
  if (shouldSave) {
    currentSession.messages.push({ isUser, content, sources });

    // Auto-generate chat title from first user message
    if (isUser && currentSession.messages.length === 1) {
      currentSession.title =
        content.substring(0, 30) + (content.length > 30 ? "..." : "");
    }

    saveCurrentSession();
  }

  return contentDiv;
}

function createSourceChip(source) {
  const chip = document.createElement("span");
  chip.className = "source-chip";

  // This makes the function backwards compatible with old code that just passed strings
  const sourceName = typeof source === "string" ? source : source.name;
  const sourcePath = typeof source === "object" ? source.path : null;

  chip.textContent = sourceName;

  if (sourcePath) {
    // Add 'clickable' class for CSS styling (green hover effect, pointer cursor)
    chip.classList.add("clickable");

    // Set tooltip to show full file path
    chip.title = `Click to open: ${sourcePath}`;

    chip.addEventListener("click", async () => {
      try {
        // Call the Electron API to open the file
        // This goes through: renderer.js → preload.js → index.js → shell.openPath()
        const result = await window.electronAPI.openFile(sourcePath);

        if (!result.success) {
          console.error("Failed to open file:", result.error);
          // Show user-friendly error message
          alert(`Could not open file: ${result.error}`);
        }
        // If successful, the file is now open in the default application!
        // No need for additional feedback - the OS provides that
      } catch (error) {
        // Handle unexpected errors (network issues, IPC failure, etc.)
        console.error("Error opening file:", error);
        alert("An error occurred while trying to open the file.");
      }
    });
  } else {
    // This maintains backwards compatibility with old backend responses
    chip.title = sourceName;
    // Note: Without the 'clickable' class, the chip won't have hover effects
  }

  return chip;
}

function renderUploadedDocs() {
  const previewContainer = document.getElementById("uploaded-docs-preview");
  previewContainer.innerHTML = "";

  if (uploadedDocs.length === 0) {
    previewContainer.style.display = "none";
    return;
  }

  previewContainer.style.display = "flex";

  uploadedDocs.forEach((doc, index) => {
    const pill = document.createElement("div");
    pill.className = "uploaded-doc-pill";

    const icon = getDocumentIcon(doc.type);

    pill.innerHTML = `
      ${icon}
      <span title="${doc.name}">${doc.name}</span>
      <div class="remove-doc" data-index="${index}">&times;</div>
    `;

    // Allow user to remove a staged document before sending
    pill.querySelector(".remove-doc").addEventListener("click", () => {
      uploadedDocs.splice(index, 1);
      renderUploadedDocs();
    });

    previewContainer.appendChild(pill);
  });

  // Display success message for batch uploads
  if (uploadedDocs.length >= 2) {
    const successMsg = document.createElement("div");
    successMsg.style.width = "100%";
    successMsg.style.fontSize = "0.75rem";
    successMsg.style.color = "var(--accent-color)";
    successMsg.style.marginTop = "2px";
    successMsg.textContent = `Successfully uploaded ${uploadedDocs.length} documents`;
    previewContainer.appendChild(successMsg);
  }
}

async function saveCurrentSession() {
  await window.electronAPI.saveHistory(currentSession);
  await refreshHistorySidebar();
}

async function refreshHistorySidebar(
  filter = chatSearch ? chatSearch.value : "",
) {
  const history = await window.electronAPI.getHistory();
  chatHistoryList.innerHTML = "";

  const filteredHistory = history.filter((session) =>
    session.title.toLowerCase().includes(filter.toLowerCase()),
  );

  if (filteredHistory.length === 0) {
    chatHistoryList.innerHTML = `<li>${filter ? "No matches" : "No history"}</li>`;
    return;
  }

  filteredHistory
    .slice()
    .reverse()
    .forEach((session) => {
      const li = document.createElement("li");
      li.dataset.id = session.id;
      if (session.id === currentSession.id) li.classList.add("active");

      const titleSpan = document.createElement("span");
      titleSpan.className = "session-title";
      titleSpan.textContent = session.title;
      titleSpan.addEventListener("click", () => loadSession(session.id));

      const delBtn = document.createElement("button");
      delBtn.className = "delete-session-btn";
      delBtn.innerHTML = "&#10005;"; // X symbol
      delBtn.title = "Delete Chat";
      delBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        if (confirm("Are you sure you want to delete this chat?")) {
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

async function refreshDocumentList() {
  const documents = await window.electronAPI.getDocuments();
  documentList.innerHTML = "";

  if (documents.length === 0) {
    documentList.innerHTML = "<li>No files uploaded</li>";
    return;
  }

  documents
    .slice()
    .reverse()
    .forEach((doc) => {
      const li = document.createElement("li");
      li.className = "document-item";

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
    case "video":
      return '<svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M17,10.5V7A1,1 0 0,0 16,6H4A1,1 0 0,0 3,7V17A1,1 0 0,0 4,18H16A1,1 0 0,0 17,17V13.5L21,17.5V6.5L17,10.5Z"/></svg>';
    case "audio":
      return '<svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M12,2A3,3 0 0,0 9,5V11A3,3 0 0,0 12,14A3,3 0 0,0 15,11V5A3,3 0 0,0 12,2M19,11C19,14.53 16.39,17.44 13,17.93V21H11V17.93C7.61,17.44 5,14.53 5,11H7A5,5 0 0,0 12,16A5,5 0 0,0 17,11H19Z"/></svg>';
    case "image":
      return '<svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M8.5,13.5L11,16.5L14.5,12L19,18H5M21,19V5C21,3.89 20.1,3 19,3H5A2,2 0 0,0 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19Z"/></svg>';
    default:
      return '<svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M13,9V3.5L18.5,9H13Z"/></svg>';
  }
}

function startNewChat() {
  currentSession = {
    id: Date.now().toString(),
    title: "New Chat",
    messages: [],
  };
  uploadedDocs = [];
  renderUploadedDocs();
  chatContainer.innerHTML = "";

  // Clear any existing focus to prevent stuck cursor
  if (document.activeElement && document.activeElement !== messageInput) {
    document.activeElement.blur();
  }

  // Ensure input is enabled and cleared when starting a new chat
  messageInput.disabled = false;
  messageInput.readOnly = false;
  messageInput.value = "";
  messageInput.style.height = "auto";

  if (chatSearch) chatSearch.value = "";

  // Add the class after preparing the input
  mainContent.classList.add("new-chat-mode");

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

async function loadSession(sessionId) {
  const history = await window.electronAPI.getHistory();
  const session = history.find((s) => s.id === sessionId);
  if (!session) return;

  currentSession = session;
  chatContainer.innerHTML = "";
  mainContent.classList.remove("new-chat-mode");

  session.messages.forEach((msg) => {
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

async function simulateStreaming(element, text) {
  element.innerHTML = "";
  const tokens = text.split(" ");
  let currentText = "";
  for (const token of tokens) {
    currentText += token + " ";
    element.innerHTML = marked.parse(currentText);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    await new Promise((resolve) => setTimeout(resolve, 20)); // Simulated speed
  }
}

async function toggleRecording() {
  if (!isRecording) {
    try {
      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      // Detect supported MIME type and determine the appropriate file extension
      // We check for MP3, WAV, Ogg, AAC/MP4, and WebM in order of preference
      let mimeType = "audio/webm";
      let extension = "webm";

      if (MediaRecorder.isTypeSupported("audio/mpeg")) {
        mimeType = "audio/mpeg";
        extension = "mp3";
      } else if (MediaRecorder.isTypeSupported("audio/wav")) {
        mimeType = "audio/wav";
        extension = "wav";
      } else if (MediaRecorder.isTypeSupported("audio/ogg; codecs=opus")) {
        mimeType = "audio/ogg; codecs=opus";
        extension = "ogg";
      } else if (MediaRecorder.isTypeSupported("audio/mp4")) {
        mimeType = "audio/mp4";
        extension = "m4a";
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
        const audioFile = new File(
          [audioBlob],
          `speech_query_${Date.now()}.${extension}`,
          { type: mimeType },
        );

        // Add recorded audio to staged documents for preview
        uploadedDocs.push({
          name: audioFile.name,
          type: "audio",
          path: URL.createObjectURL(audioBlob), // Local preview URL
          file: audioFile, // Actual file object for the backend
        });

        renderUploadedDocs();

        // Stop all tracks in the stream to release the microphone
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start();
      isRecording = true;
      micBtn.classList.add("recording");
      micBtn.title = "Stop Recording";
      messageInput.placeholder = "Recording... Speak now.";
    } catch (err) {
      console.error("Error accessing microphone:", err);
      alert("Could not access microphone. Please check permissions.");
    }
  } else {
    // Stop recording
    mediaRecorder.stop();
    isRecording = false;
    micBtn.classList.remove("recording");
    micBtn.title = "Record Speech Query";
    messageInput.placeholder = "Ask anything about your documents...";
  }
}

async function handleSendMessage() {
  const message = messageInput.value.trim();
  const audioQuery = uploadedDocs.find(
    (doc) => doc.type === "audio" && doc.file,
  );

  // Don't send if both message, audio and staging area are empty
  if (!message && !audioQuery && uploadedDocs.length === 0) return;

  if (mainContent.classList.contains("new-chat-mode")) {
    mainContent.classList.remove("new-chat-mode");
  }

  if (audioQuery) {
    appendMessage(true, `🎤 Voice Query: ${audioQuery.name}`);
  } else {
    appendMessage(true, message);
  }

  messageInput.value = "";
  messageInput.style.height = "auto";

  messageInput.disabled = true;
  sendButton.disabled = true;
  micBtn.disabled = true;

  try {
    let response;

    if (audioQuery) {
      const arrayBuffer = await audioQuery.file.arrayBuffer();
      response = await window.electronAPI.sendSpeechQuery(
        new Uint8Array(arrayBuffer),
        audioQuery.name,
      );
    } else {
      response = await window.electronAPI.sendMessage(message);
    }

    uploadedDocs = [];
    renderUploadedDocs();

    const messageDiv = document.createElement("div");
    messageDiv.className = "message bot-message";
    const contentDiv = document.createElement("div");
    contentDiv.className = "message-content";
    messageDiv.appendChild(contentDiv);
    chatContainer.appendChild(messageDiv);

    await simulateStreaming(contentDiv, response.text);

    if (response.sources && response.sources.length > 0) {
      const sourcesDiv = document.createElement("div");
      sourcesDiv.className = "sources";
      sourcesDiv.innerHTML =
        '<h4>Sources:</h4><div class="source-chips"></div>';
      const chipsContainer = sourcesDiv.querySelector(".source-chips");

      response.sources.forEach((source) => {
        const chip = createSourceChip(source);
        chipsContainer.appendChild(chip);
      });

      messageDiv.appendChild(sourcesDiv);
    }

    currentSession.messages.push({
      isUser: false,
      content: response.text,
      sources: response.sources,
    });
    saveCurrentSession();

    chatContainer.scrollTop = chatContainer.scrollHeight;
  } catch (error) {
    console.error("Error:", error);
    appendMessage(false, "Error: Failed to connect to RAG backend.", [], false);
  } finally {
    // Re-enable input
    messageInput.disabled = false;
    sendButton.disabled = false;
    micBtn.disabled = false;
    messageInput.focus();
  }
}

messageInput.addEventListener("input", function () {
  this.style.height = "auto";
  this.style.height = this.scrollHeight + "px";

  if (currentSession.messages.length === 0) {
    if (this.value.trim().length > 0) {
      mainContent.classList.remove("new-chat-mode");
    } else {
      mainContent.classList.add("new-chat-mode");
    }
  }
});

sendButton.addEventListener("click", handleSendMessage);
micBtn.addEventListener("click", toggleRecording);

messageInput.addEventListener("click", () => {
  messageInput.focus();
});

messageInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    handleSendMessage();
  }
});

document.getElementById("new-chat-btn").addEventListener("click", startNewChat);

document.getElementById("upload-btn").addEventListener("click", (e) => {
  e.stopPropagation();
  document.getElementById("upload-menu").classList.toggle("show");
});

window.addEventListener("click", () => {
  document.getElementById("upload-menu").classList.remove("show");
  document.getElementById("settings-menu").classList.remove("show");
});

const settingsBtn = document.getElementById("settings-btn");
const settingsMenu = document.getElementById("settings-menu");

settingsBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  settingsMenu.classList.toggle("show");
  document.getElementById("upload-menu").classList.remove("show");
});

document.querySelectorAll(".appearance-item").forEach((button) => {
  button.addEventListener("click", async (e) => {
    e.stopPropagation();
    const theme = button.getAttribute("data-theme");

    if (theme === "custom") {
      let imagePath = localStorage.getItem("customThemePath");
      if (!imagePath) {
        imagePath = await window.electronAPI.getDefaultImagePath();
      } else {
        const newPath = await window.electronAPI.selectThemeImage();
        if (newPath) imagePath = newPath;
      }

      if (imagePath) {
        applyCustomTheme(imagePath);
        localStorage.setItem("theme", "custom");
        localStorage.setItem("customThemePath", imagePath);
      }
    } else {
      document.body.classList.remove("custom-theme");
      if (theme === "dark") {
        document.body.classList.add("dark-mode");
        document.body.classList.remove("light-mode");
        localStorage.setItem("baseTheme", "dark");
      } else {
        document.body.classList.add("light-mode");
        document.body.classList.remove("dark-mode");
        localStorage.setItem("baseTheme", "light");
      }
      localStorage.setItem("theme", theme);
    }
    settingsMenu.classList.remove("show");
  });
});

function applyCustomTheme(imagePath) {
  document.body.classList.add("custom-theme");
  const normalizedPath = imagePath.replace(/\\/g, "/");
  const formattedPath = `local-resource://${normalizedPath}`;
  document.documentElement.style.setProperty(
    "--bg-image",
    `url(${JSON.stringify(formattedPath)})`,
  );
}

const savedTheme = localStorage.getItem("theme");
const savedBaseTheme = localStorage.getItem("baseTheme") || "dark";

if (savedBaseTheme === "dark") {
  document.body.classList.add("dark-mode");
  document.body.classList.remove("light-mode");
} else {
  document.body.classList.add("light-mode");
  document.body.classList.remove("dark-mode");
}

if (savedTheme === "custom") {
  const customPath = localStorage.getItem("customThemePath");
  if (customPath) {
    applyCustomTheme(customPath);
  }
}

async function handleWebcamCapture() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });

    const video = document.createElement("video");
    video.srcObject = stream;
    video.style.display = "none";
    document.body.appendChild(video);
    video.play();

    await new Promise((resolve) => {
      video.onloadedmetadata = resolve;
    });

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0);

    stream.getTracks().forEach((track) => track.stop());
    document.body.removeChild(video);

    canvas.toBlob(async (blob) => {
      const fileName = `webcam_${Date.now()}.png`;
      const arrayBuffer = await blob.arrayBuffer();
      const imageBuffer = new Uint8Array(arrayBuffer);

      const result = await window.electronAPI.uploadWebcam(
        imageBuffer,
        fileName,
      );

      if (result.success) {
        if (result.uploadedFiles) {
          uploadedDocs.push(...result.uploadedFiles);
          renderUploadedDocs();
        }
        await refreshDocumentList();
      } else {
        appendMessage(false, `❌ **Error**: ${result.message}`);
      }
    }, "image/png");
  } catch (error) {
    console.error("Webcam capture error:", error);
    alert("Could not access webcam. Please check permissions.");
  }
}

async function handleUpload(type, sourceButton = null) {
  const uploadBtn = sourceButton || document.getElementById("upload-btn");
  const uploadMenu = document.getElementById("upload-menu");
  const originalHTML = uploadBtn.innerHTML;

  if (uploadMenu) {
    uploadMenu.classList.remove("show");
  }

  if (type === "webcam") {
    // Handle webcam capture directly in renderer
    await handleWebcamCapture();
    return;
  }

  try {
    uploadBtn.disabled = true;
    uploadBtn.innerHTML = '<span class="loading-spinner"></span>';

    const result = await window.electronAPI.uploadDocuments(type);

    if (result.success) {
      if (result.uploadedFiles) {
        uploadedDocs.push(...result.uploadedFiles);
        renderUploadedDocs();
      } else {
        appendMessage(false, `✅ **Success**: ${result.message}`);
      }
      await refreshDocumentList();
    } else if (result.message !== "Upload canceled") {
      appendMessage(false, `❌ **Error**: ${result.message}`);
    }
  } catch (error) {
    console.error("Upload Error:", error);
    appendMessage(
      false,
      `❌ **Error**: An unexpected error occurred during ${type} upload.`,
    );
  } finally {
    uploadBtn.disabled = false;
    uploadBtn.innerHTML = originalHTML;
  }
}

document.querySelectorAll(".upload-item").forEach((button) => {
  button.addEventListener("click", (e) => {
    e.stopPropagation();
    const type = button.getAttribute("data-type");
    handleUpload(type);
  });
});

chatContainer.addEventListener("scroll", () => {
  const threshold = 100;
  const isAtBottom =
    chatContainer.scrollHeight -
      chatContainer.scrollTop -
      chatContainer.clientHeight <=
    threshold;

  if (isAtBottom) {
    scrollDownBtn.classList.remove("show");
  } else {
    scrollDownBtn.classList.add("show");
  }
});

scrollDownBtn.addEventListener("click", () => {
  chatContainer.scrollTo({
    top: chatContainer.scrollHeight,
    behavior: "smooth",
  });
});

sidebarToggle.addEventListener("click", () => {
  const isClosed = sidebar.classList.toggle("closed");
  sidebarToggle.title = isClosed ? "Open Sidebar" : "Close Sidebar";
});
