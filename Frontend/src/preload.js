/**
 * PRELOAD SCRIPT
 * This script acts as a secure bridge between the Renderer process (UI) 
 * and the Main process (OS/System). It exposes specific functions to 
 * the 'window' object without giving the UI full access to Node.js.
 */
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Chat messaging
  sendMessage: (message) => ipcRenderer.invoke('chat:send', message),
  sendSpeechQuery: (audioBuffer, fileName) => ipcRenderer.invoke('chat:send-speech', audioBuffer, fileName),
  
  // Document management
  uploadDocuments: (type) => ipcRenderer.invoke('documents:upload', type),
  getDocuments: () => ipcRenderer.invoke('documents:get-all'),
  
  /**
   * Listen for document list refreshes triggered by the Main process.
   * This is essential when the user uses the Native Application Menu (File -> Upload).
   */
  onDocumentsRefreshed: (callback) => ipcRenderer.on('documents:refreshed', () => callback()),
  
  // History management
  saveHistory: (chatSession) => ipcRenderer.invoke('history:save', chatSession),
  getHistory: () => ipcRenderer.invoke('history:get-all'),
  deleteHistory: (sessionId) => ipcRenderer.invoke('history:delete', sessionId),

  // Theme management
  selectThemeImage: () => ipcRenderer.invoke('theme:select-image'),
  getDefaultImagePath: () => ipcRenderer.invoke('theme:get-default-path')
});
