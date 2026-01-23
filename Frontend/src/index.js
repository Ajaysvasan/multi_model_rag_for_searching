const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('node:path');
const ragService = require('./services/ragService');

// Handle creating/removing shortcuts on Windows when installing/uninstalling.
if (require('electron-squirrel-startup')) {
  app.quit();
}

const createWindow = () => {
  // Create the browser window.
  const mainWindow = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  // and load the index.html of the app.
  mainWindow.loadFile(path.join(__dirname, 'index.html'));

  // Open the DevTools.
  mainWindow.webContents.openDevTools();
};

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.whenReady().then(() => {
  ipcMain.handle('chat:send', async (event, message) => {
    try {
      const response = await ragService.getResponse(message);
      return response;
    } catch (error) {
      console.error('RAG Service Error:', error);
      return "I'm sorry, I encountered an error processing your request.";
    }
  });

  ipcMain.handle('documents:upload', async (event, type = 'document') => {
    let filters = [];
    if (type === 'video') {
      filters = [{ name: 'Videos', extensions: ['mp4', 'mkv', 'avi', 'mov'] }];
    } else if (type === 'audio') {
      filters = [{ name: 'Audio', extensions: ['mp3', 'wav', 'ogg', 'm4a'] }];
    } else if (type === 'image') {
      filters = [{ name: 'Images', extensions: ['jpg', 'jpeg', 'png', 'gif', 'webp'] }];
    } else {
      filters = [{ name: 'Documents', extensions: ['pdf', 'docx', 'txt', 'md'] }];
    }

    const { canceled, filePaths } = await dialog.showOpenDialog({
      properties: ['openFile', 'multiSelections'],
      filters: filters
    });

    if (canceled) {
      return { success: false, message: 'Upload canceled' };
    }

    try {
      const result = await ragService.uploadDocuments(filePaths, type);
      return result;
    } catch (error) {
      console.error('Upload Error:', error);
      return { success: false, message: `Failed to upload ${type} files` };
    }
  });

  /**
   * BACKEND DEVELOPER NOTE:
   * The following handlers are placeholders for Chat History persistence.
   * You should replace the 'mockStorage' logic with a database (e.g., SQLite, PouchDB)
   * or a local file storage system (e.g., electron-store).
   */
  let mockStorage = []; // Replace with actual DB connection

  ipcMain.handle('history:save', async (event, chatSession) => {
    // Logic to save or update a chat session
    const index = mockStorage.findIndex(s => s.id === chatSession.id);
    if (index > -1) {
      mockStorage[index] = chatSession;
    } else {
      mockStorage.push(chatSession);
    }
    return { success: true };
  });

  ipcMain.handle('history:get-all', async () => {
    // Logic to retrieve all saved sessions
    return mockStorage;
  });

  ipcMain.handle('history:delete', async (event, sessionId) => {
    // Logic to delete a specific session
    mockStorage = mockStorage.filter(s => s.id !== sessionId);
    return { success: true };
  });

  createWindow();

  // On OS X it's common to re-create a window in the app when the
  // dock icon is clicked and there are no other windows open.
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

// Quit when all windows are closed, except on macOS. There, it's common
// for applications and their menu bar to stay active until the user quits
// explicitly with Cmd + Q.
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// In this file you can include the rest of your app's specific main process
// code. You can also put them in separate files and import them here.
