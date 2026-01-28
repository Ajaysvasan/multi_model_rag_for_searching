const { app, BrowserWindow, ipcMain, dialog, Menu, protocol, net } = require('electron');
const path = require('node:path');
const fs = require('node:fs');
const url = require('node:url');
const ragService = require('./services/ragService');

// Register protocol for local images
protocol.registerSchemesAsPrivileged([
  { scheme: 'local-resource', privileges: { secure: true, standard: true, supportFetchAPI: true, bypassCSP: true, stream: true } }
]);

let mainWindow;
let mockStorage = []; // Simulated database for chat sessions
let documentStorage = []; // Simulated database for uploaded document metadata

/**
 * Recursively gets all file paths from a directory.
 * @param {string} dirPath 
 * @param {string[]} arrayOfFiles 
 * @returns {string[]}
 */
function getAllFiles(dirPath, arrayOfFiles) {
  const files = fs.readdirSync(dirPath);

  arrayOfFiles = arrayOfFiles || [];

  files.forEach(function(file) {
    const fullPath = path.join(dirPath, file);
    if (fs.statSync(fullPath).isDirectory()) {
      arrayOfFiles = getAllFiles(fullPath, arrayOfFiles);
    } else {
      arrayOfFiles.push(fullPath);
    }
  });

  return arrayOfFiles;
}

/**
 * Shared logic for uploading documents or folders.
 * Used by both IPC handlers and native menu items.
 * 
 * RAG INTEGRATION NOTE:
 * This function handles the OS-level file selection. The 'filePaths' array
 * contains absolute paths to the selected files/folders. These paths should
 * be sent to your backend or RAG service for chunking and embedding.
 */
async function performUpload(type = 'document') {
  let filters = [];
  let properties = ['openFile', 'multiSelections'];

  // Switch dialog mode based on whether user wants a specific file or a whole directory
  if (type === 'folder') {
    properties = ['openDirectory'];
  } else {
    if (type === 'video') {
      filters = [{ name: 'Videos', extensions: ['mp4', 'mkv', 'avi', 'mov'] }];
    } else if (type === 'audio') {
      filters = [{ name: 'Audio', extensions: ['mp3', 'wav', 'ogg', 'm4a'] }];
    } else if (type === 'image') {
      filters = [{ name: 'Images', extensions: ['jpg', 'jpeg', 'png', 'gif', 'webp'] }];
    } else {
      filters = [{ name: 'Documents', extensions: ['pdf', 'docx', 'txt', 'md'] }];
    }
  }

  const { canceled, filePaths: selectedPaths } = await dialog.showOpenDialog(mainWindow, {
    properties: properties,
    filters: filters
  });

  if (canceled) {
    return { success: false, message: 'Upload canceled' };
  }

  let finalFilePaths = selectedPaths;
  if (type === 'folder') {
    finalFilePaths = [];
    selectedPaths.forEach(folderPath => {
      finalFilePaths.push(...getAllFiles(folderPath));
    });
  }

  try {
    // BACKEND CALL: 'ragService.uploadDocuments' is where you'd trigger your
    // Python/Node service to start the ingestion pipeline (OCR -> Chunk -> Embed -> Vector DB).
    const result = await ragService.uploadDocuments(finalFilePaths, type);
    
    if (result.success) {
      const uploadedFiles = [];
      // Upon successful ingestion, we store the metadata locally to show in the UI.
      // In a production app, you might fetch this list from your Vector DB instead.
      finalFilePaths.forEach(filePath => {
        const doc = {
          name: path.basename(filePath),
          path: filePath,
          type: type === 'folder' ? 'document' : type,
          date: new Date().toLocaleString()
        };
        documentStorage.push(doc);
        uploadedFiles.push({ name: doc.name, type: doc.type });
      });
      
      // NOTIFY UI: If the upload was triggered via the Native Menu (Cmd+O),
      // the renderer doesn't know it happened yet. We send an IPC event to tell it to refresh.
      if (mainWindow) {
        mainWindow.webContents.send('documents:refreshed');
      }
      
      return { ...result, uploadedFiles };
    }
    return result;
  } catch (error) {
    console.error('Upload Error:', error);
    return { success: false, message: `Failed to upload ${type} files` };
  }
}

const createWindow = () => {
  // Create the browser window.
  mainWindow = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  // and load the index.html of the app.
  mainWindow.loadFile(path.join(__dirname, 'index.html'));

  mainWindow.webContents.on('context-menu', (e, props) => {
    const { x, y } = props;

    Menu.buildFromTemplate([
      {
        label: 'Developer Tools',
        click: () => {
          mainWindow.webContents.openDevTools();
        }
      }
    ]).popup(mainWindow);
  });

  // Open the DevTools.
  mainWindow.webContents.openDevTools();
};

// Handle creating/removing shortcuts on Windows when installing/uninstalling.
if (require('electron-squirrel-startup')) {
  app.quit();
}

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
// --- IPC Handlers ---
// These handlers catch requests from the Renderer process (UI) via the Preload bridge.

app.whenReady().then(() => {
  // Handle local resources
  protocol.handle('local-resource', async (request) => {
    try {
      const url = new URL(request.url);
      // On Windows, the path might be /C:/Users/... or C:/Users/...
      let decodedPath = decodeURIComponent(url.pathname);
      
      // If the pathname starts with / and then a drive letter (e.g., /C:/), remove the /
      if (process.platform === 'win32' && /^\/[a-zA-Z]:/.test(decodedPath)) {
        decodedPath = decodedPath.slice(1);
      }
      
      // Also handle the case where host + pathname is the full path
      // (Depends on how the URL was constructed)
      let finalPath = decodedPath;
      if (url.host && url.host !== '' && process.platform === 'win32') {
        finalPath = path.join(url.host + ':', decodedPath);
      }

      const data = await fs.promises.readFile(path.normalize(finalPath));
      return new Response(data);
    } catch (error) {
      console.error('Protocol error:', error);
      return new Response('File not found', { status: 404 });
    }
  });

  // Handler for sending messages to the chatbot
  ipcMain.handle('chat:send', async (event, message) => {
    try {
      // Pass the message to the RAG service for processing
      const response = await ragService.getResponse(message);
      return response;
    } catch (error) {
      console.error('RAG Service Error:', error);
      return "I'm sorry, I encountered an error processing your request.";
    }
  });

  // Handler for sending speech/audio queries (MP3 format) to the chatbot
  // This IPC handler receives a Uint8Array (MP3 Buffer) from the renderer
  ipcMain.handle('chat:send-speech', async (event, audioBuffer, fileName) => {
    try {
      // DEVELOPMENT TIP: audioBuffer is a standard Node.js Buffer containing MP3 data.
      // You can write this to disk, upload to S3, or stream it to an STT API.
      const response = await ragService.processSpeechQuery(audioBuffer, fileName);
      return response;
    } catch (error) {
      console.error('Speech RAG Service Error:', error);
      return "I'm sorry, I encountered an error processing your voice request.";
    }
  });

  // Handler for document uploads
  ipcMain.handle('documents:upload', async (event, type = 'document') => {
    return await performUpload(type);
  });

  ipcMain.handle('documents:get-all', async () => {
    return documentStorage;
  });

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

  // Handler for custom theme image selection
  ipcMain.handle('theme:select-image', async () => {
    const { canceled, filePaths } = await dialog.showOpenDialog(mainWindow, {
      title: 'Select Background Image',
      properties: ['openFile'],
      filters: [{ name: 'Images', extensions: ['jpg', 'jpeg', 'png', 'webp'] }]
    });

    if (canceled || filePaths.length === 0) return null;

    const sourcePath = filePaths[0];
    const themesDir = path.join(app.getPath('userData'), 'themes');
    
    if (!fs.existsSync(themesDir)) {
      fs.mkdirSync(themesDir, { recursive: true });
    }

    const fileName = `custom-theme${path.extname(sourcePath)}`;
    const destinationPath = path.join(themesDir, fileName);
    
    fs.copyFileSync(sourcePath, destinationPath);
    
    return destinationPath;
  });

  ipcMain.handle('theme:get-default-path', () => {
    return path.join(__dirname, 'optic.jpg');
  });

  createWindow();
  createMenu();

  // On OS X it's common to re-create a window in the app when the
  // dock icon is clicked and there are no other windows open.
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

/**
 * Creates the native application menu with RAG-specific upload options.
 */
function createMenu() {
  const template = [
    {
      label: 'File',
      submenu: [
        {
          label: 'Upload File',
          accelerator: 'CmdOrCtrl+O',
          click: async () => {
            await performUpload('document');
          }
        },
        {
          label: 'Upload Folder',
          accelerator: 'CmdOrCtrl+Shift+O',
          click: async () => {
            await performUpload('folder');
          }
        },
        { type: 'separator' },
        { role: 'quit' }
      ]
    }
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

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
