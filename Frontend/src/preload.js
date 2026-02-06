/**
 * PRELOAD SCRIPT
 * This script acts as a secure bridge between the Renderer process (UI)
 * and the Main process (OS/System). It exposes specific functions to
 * the 'window' object without giving the UI full access to Node.js.
 *
 * SECURITY NOTE:
 * The preload script runs in a separate context with access to Node.js APIs,
 * but the renderer process (UI) does not. This bridge pattern ensures security
 * by only exposing specific, controlled APIs to the UI.
 */
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // ========================================================================
  // CHAT MESSAGING APIs
  // ========================================================================

  /**
   * Send a text message to the RAG backend
   * @param {string} message - User's text query
   * @returns {Promise<{text: string, sources: Array}>} Response from backend
   *
   * BACKEND INTEGRATION NOTE:
   * This calls ragService.getResponse() which should return:
   * {
   *   text: "LLM response in Markdown format",
   *   sources: [{name: "file.pdf", path: "C:\\path\\to\\file.pdf"}]
   * }
   */
  sendMessage: (message) => ipcRenderer.invoke('chat:send', message),

  /**
   * Send an audio query to the RAG backend
   * @param {Uint8Array} audioBuffer - Audio data in MP3/WebM format
   * @param {string} fileName - Name of the audio file
   * @returns {Promise<{text: string, sources: Array}>} Response from backend
   *
   * BACKEND INTEGRATION NOTE:
   * Process: Audio -> STT (Whisper) -> Text Query -> RAG Pipeline
   */
  sendSpeechQuery: (audioBuffer, fileName) => ipcRenderer.invoke('chat:send-speech', audioBuffer, fileName),

  // ========================================================================
  // DOCUMENT MANAGEMENT APIs
  // ========================================================================

  /**
   * Trigger file upload dialog and process selected files
   * @param {string} type - 'document' | 'video' | 'audio' | 'image' | 'folder'
   * @returns {Promise<{success: boolean, uploadedFiles: Array}>}
   */
  uploadDocuments: (type) => ipcRenderer.invoke('documents:upload', type),

  /**
   * Upload a webcam-captured image
   * @param {Uint8Array} imageBuffer - Image data in PNG format
   * @param {string} fileName - Name for the captured image
   */
  uploadWebcam: (imageBuffer, fileName) => ipcRenderer.invoke('documents:upload-webcam', imageBuffer, fileName),

  /**
   * Get list of all uploaded/indexed documents
   * @returns {Promise<Array<{name: string, path: string, type: string, date: string}>>}
   */
  getDocuments: () => ipcRenderer.invoke('documents:get-all'),

  /**
   * Listen for document list refreshes triggered by the Main process.
   * This is essential when the user uses the Native Application Menu (File -> Upload).
   */
  onDocumentsRefreshed: (callback) => ipcRenderer.on('documents:refreshed', () => callback()),

  // ========================================================================
  // CHAT HISTORY APIs
  // ========================================================================

  saveHistory: (chatSession) => ipcRenderer.invoke('history:save', chatSession),
  getHistory: () => ipcRenderer.invoke('history:get-all'),
  deleteHistory: (sessionId) => ipcRenderer.invoke('history:delete', sessionId),

  // ========================================================================
  // THEME MANAGEMENT APIs
  // ========================================================================

  selectThemeImage: () => ipcRenderer.invoke('theme:select-image'),
  getDefaultImagePath: () => ipcRenderer.invoke('theme:get-default-path'),

  // ========================================================================
  // FILE OPERATIONS - ✨ NEW FEATURE: Clickable Source Files
  // ========================================================================

  /**
   * Opens a file in the system's default application
   *
   * HOW IT WORKS:
   * 1. User clicks on a source chip in the chat UI (renderer.js)
   * 2. renderer.js calls: window.electronAPI.openFile(filePath)
   * 3. This preload bridge sends the request to the main process
   * 4. Main process uses shell.openPath() to open the file
   * 5. File opens in: PDF reader, Word, Excel, Image viewer, etc.
   *
   * BACKEND INTEGRATION CRITICAL:
   * For this feature to work, your backend MUST return file paths in responses:
   * {
   *   text: "Your answer...",
   *   sources: [
   *     {
   *       name: "annual_report.pdf",           // Display name
   *       path: "C:\\Users\\...\\annual_report.pdf"  // ABSOLUTE path (required!)
   *     }
   *   ]
   * }
   *
   * The 'path' field is what gets passed to this function when users click.
   *
   * @param {string} filePath - ABSOLUTE path to the file to open
   * @returns {Promise<{success: boolean, error?: string}>}
   *
   * Example Usage in Renderer:
   * const result = await window.electronAPI.openFile("C:\\docs\\file.pdf");
   * if (!result.success) alert(result.error);
   */
  openFile: (filePath) => ipcRenderer.invoke('file:open', filePath)
});
