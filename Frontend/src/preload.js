const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  sendMessage: (message) => ipcRenderer.invoke('chat:send', message),
  uploadDocuments: (type) => ipcRenderer.invoke('documents:upload', type),
  // History Management
  saveHistory: (chatSession) => ipcRenderer.invoke('history:save', chatSession),
  getHistory: () => ipcRenderer.invoke('history:get-all'),
  deleteHistory: (sessionId) => ipcRenderer.invoke('history:delete', sessionId)
});
