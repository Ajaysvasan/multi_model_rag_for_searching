/**
 * ChatManager — Handles chat message rendering, session management, and history.
 * Attaches to window.App.ChatManager
 */
(function () {
    const ns = (window.App = window.App || {});

    // ── State ──────────────────────────────────────────────────────────────
    let currentSession = {
        id: Date.now().toString(),
        title: "New Chat",
        messages: [],
    };

    let uploadedDocs = [];

    // ── DOM refs (resolved once on init) ───────────────────────────────────
    let chatContainer,
        mainContent,
        messageInput,
        sendButton,
        micBtn,
        chatHistoryList,
        chatSearch,
        documentList;

    // ── Helpers ────────────────────────────────────────────────────────────

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

    function createSourceChip(source) {
        const chip = document.createElement("span");
        chip.className = "source-chip";

        const sourceName = typeof source === "string" ? source : source.name;
        const sourcePath = typeof source === "object" ? source.path : null;

        chip.textContent = sourceName;

        if (sourcePath) {
            chip.classList.add("clickable");
            chip.title = `Click to open: ${sourcePath}`;

            chip.addEventListener("click", async () => {
                try {
                    const result = await window.electronAPI.openFile(sourcePath);
                    if (!result.success) {
                        console.error("Failed to open file:", result.error);
                        alert(`Could not open file: ${result.error}`);
                    }
                } catch (error) {
                    console.error("Error opening file:", error);
                    alert("An error occurred while trying to open the file.");
                }
            });
        } else {
            chip.title = sourceName;
        }

        return chip;
    }

    // ── Message rendering ──────────────────────────────────────────────────

    function appendMessage(isUser, content, sources = [], shouldSave = true) {
        const messageDiv = document.createElement("div");
        messageDiv.className = `message ${isUser ? "user-message" : "bot-message"}`;

        const contentDiv = document.createElement("div");
        contentDiv.className = "message-content";

        if (isUser) {
            contentDiv.textContent = content;
        } else {
            contentDiv.innerHTML = marked.parse(content);
        }

        messageDiv.appendChild(contentDiv);

        if (!isUser && sources && sources.length > 0) {
            const sourcesDiv = document.createElement("div");
            sourcesDiv.className = "sources";
            sourcesDiv.innerHTML =
                '<h4>Sources:</h4><div class="source-chips"></div>';
            const chipsContainer = sourcesDiv.querySelector(".source-chips");

            sources.forEach((source) => {
                const chip = createSourceChip(source);
                chipsContainer.appendChild(chip);
            });

            messageDiv.appendChild(sourcesDiv);
        }

        chatContainer.appendChild(messageDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;

        if (shouldSave) {
            currentSession.messages.push({ isUser, content, sources });

            if (isUser && currentSession.messages.length === 1) {
                currentSession.title =
                    content.substring(0, 30) + (content.length > 30 ? "..." : "");
            }

            saveCurrentSession();
        }

        return contentDiv;
    }

    async function simulateStreaming(element, text) {
        element.innerHTML = "";
        const tokens = text.split(" ");
        let currentText = "";
        for (const token of tokens) {
            currentText += token + " ";
            element.innerHTML = marked.parse(currentText);
            chatContainer.scrollTop = chatContainer.scrollHeight;
            await new Promise((resolve) => setTimeout(resolve, 20));
        }
    }

    // ── Uploaded-docs preview ──────────────────────────────────────────────

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

            pill.querySelector(".remove-doc").addEventListener("click", () => {
                uploadedDocs.splice(index, 1);
                renderUploadedDocs();
            });

            previewContainer.appendChild(pill);
        });

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

    // ── Session persistence ────────────────────────────────────────────────

    async function saveCurrentSession() {
        await window.electronAPI.saveHistory(currentSession);
        await refreshHistorySidebar();
    }

    async function refreshHistorySidebar(
        filter = chatSearch ? chatSearch.value : ""
    ) {
        const history = await window.electronAPI.getHistory();
        chatHistoryList.innerHTML = "";

        const filteredHistory = history.filter((session) =>
            session.title.toLowerCase().includes(filter.toLowerCase())
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
                delBtn.innerHTML = "&#10005;";
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

    // ── New chat / Load session ────────────────────────────────────────────

    function startNewChat() {
        currentSession = {
            id: Date.now().toString(),
            title: "New Chat",
            messages: [],
        };
        uploadedDocs = [];
        renderUploadedDocs();
        chatContainer.innerHTML = "";

        if (document.activeElement && document.activeElement !== messageInput) {
            document.activeElement.blur();
        }

        messageInput.disabled = false;
        messageInput.readOnly = false;
        messageInput.value = "";
        messageInput.style.height = "auto";

        if (chatSearch) chatSearch.value = "";

        mainContent.classList.add("new-chat-mode");

        setTimeout(() => {
            const forceFocus = () => {
                messageInput.disabled = false;
                messageInput.readOnly = false;
                messageInput.focus();

                const length = messageInput.value.length;
                messageInput.setSelectionRange(length, length);
                messageInput.click();
            };

            forceFocus();
            setTimeout(forceFocus, 50);
        }, 350);

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

        if (document.activeElement) {
            document.activeElement.blur();
        }

        messageInput.disabled = false;

        requestAnimationFrame(() => {
            setTimeout(() => {
                messageInput.disabled = false;
                messageInput.readOnly = false;
                messageInput.focus();
                messageInput.click();

                const length = messageInput.value.length;
                messageInput.setSelectionRange(length, length);
            }, 100);
        });

        await refreshHistorySidebar();
    }

    // ── Send message ───────────────────────────────────────────────────────

    async function handleSendMessage() {
        const message = messageInput.value.trim();
        const audioQuery = uploadedDocs.find(
            (doc) => doc.type === "audio" && doc.file
        );

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
                    audioQuery.name
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
            appendMessage(
                false,
                "Error: Failed to connect to RAG backend.",
                [],
                false
            );
        } finally {
            messageInput.disabled = false;
            sendButton.disabled = false;
            micBtn.disabled = false;
            messageInput.focus();
        }
    }

    // ── Init ───────────────────────────────────────────────────────────────

    function init() {
        chatContainer = document.getElementById("chat-container");
        mainContent = document.getElementById("main-content");
        messageInput = document.getElementById("message-input");
        sendButton = document.getElementById("send-button");
        micBtn = document.getElementById("mic-btn");
        chatHistoryList = document.getElementById("chat-history");
        chatSearch = document.getElementById("chat-search");
        documentList = document.getElementById("document-list");

        // Configure Markdown parser
        marked.setOptions({ breaks: true, gfm: true });

        // Wire up core input events
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

        messageInput.addEventListener("click", () => {
            messageInput.focus();
        });

        messageInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage();
            }
        });

        document
            .getElementById("new-chat-btn")
            .addEventListener("click", startNewChat);

        // Chat history search
        chatSearch.addEventListener("input", async (e) => {
            const searchTerm = e.target.value.toLowerCase();
            await refreshHistorySidebar(searchTerm);
        });

        // Listen for refresh from native menu uploads
        window.electronAPI.onDocumentsRefreshed(async () => {
            await refreshDocumentList();
        });

        // Initial data load
        (async () => {
            await refreshHistorySidebar();
            await refreshDocumentList();

            if (currentSession.messages.length === 0) {
                mainContent.classList.add("new-chat-mode");
                chatContainer.innerHTML = "";
            }
        })();
    }

    // ── Public API ─────────────────────────────────────────────────────────
    ns.ChatManager = {
        init,
        appendMessage,
        getUploadedDocs: () => uploadedDocs,
        setUploadedDocs: (docs) => {
            uploadedDocs = docs;
        },
        pushUploadedDoc: (doc) => {
            uploadedDocs.push(doc);
        },
        pushUploadedDocs: (docs) => {
            uploadedDocs.push(...docs);
        },
        renderUploadedDocs,
        refreshDocumentList,
        getDocumentIcon,
    };
})();
