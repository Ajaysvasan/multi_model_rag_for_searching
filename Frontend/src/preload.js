const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {

  sendMessage: (message) => ipcRenderer.invoke('chat:send', message),

  sendSpeechQuery: (audioBuffer, fileName) => ipcRenderer.invoke('chat:send-speech', audioBuffer, fileName),

  uploadDocuments: (type) => ipcRenderer.invoke('documents:upload', type),

  
  uploadWebcam: (imageBuffer, fileName) => ipcRenderer.invoke('documents:upload-webcam', imageBuffer, fileName),


  getDocuments: () => ipcRenderer.invoke('documents:get-all'),

  onDocumentsRefreshed: (callback) => ipcRenderer.on('documents:refreshed', () => callback()),


  saveHistory: (chatSession) => ipcRenderer.invoke('history:save', chatSession),
  getHistory: () => ipcRenderer.invoke('history:get-all'),
  deleteHistory: (sessionId) => ipcRenderer.invoke('history:delete', sessionId),

  selectThemeImage: () => ipcRenderer.invoke('theme:select-image'),
  getDefaultImagePath: () => ipcRenderer.invoke('theme:get-default-path'),


  openFile: (filePath) => ipcRenderer.invoke('file:open', filePath)
});