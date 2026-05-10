const { app, BrowserWindow, shell, Menu } = require('electron')
const path = require('path')
const { spawn } = require('child_process')
const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged

let mainWindow = null
let backendProcess = null

function startBackend() {
  const backendDir = path.join(__dirname, '..', '..', 'backend')
  const pythonCmd = process.platform === 'win32' ? 'python' : 'python3'

  backendProcess = spawn(pythonCmd, ['main.py'], {
    cwd: backendDir,
    stdio: 'pipe',
    windowsHide: true,
  })

  backendProcess.stdout.on('data', (data) => {
    console.log('[Backend]', data.toString())
  })

  backendProcess.stderr.on('data', (data) => {
    console.error('[Backend Error]', data.toString())
  })

  backendProcess.on('close', (code) => {
    console.log('[Backend] exited with code', code)
  })
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
    titleBarStyle: 'hiddenInset',
    backgroundColor: '#0a0a12',
    show: false,
    icon: path.join(__dirname, '..', 'public', 'icon.ico'),
    title: 'AI Creative Studio',
  })

  const menu = Menu.buildFromTemplate([
    {
      label: 'File',
      submenu: [
        { label: 'Open Gallery', click: () => mainWindow?.webContents.executeJavaScript("window.__setTab?.('gallery')") },
        { type: 'separator' },
        { role: 'quit' },
      ],
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
      ],
    },
  ])
  Menu.setApplicationMenu(menu)

  const url = isDev ? 'http://localhost:5173' : `file://${path.join(__dirname, '..', 'dist', 'index.html')}`

  if (isDev) {
    // Wait for Vite to be ready
    const tryLoad = () => {
      mainWindow.loadURL(url).catch(() => setTimeout(tryLoad, 1000))
    }
    setTimeout(tryLoad, 2000)
  } else {
    mainWindow.loadURL(url)
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
    if (isDev) mainWindow.webContents.openDevTools()
  })

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

app.whenReady().then(() => {
  startBackend()
  // Give backend a moment to start
  setTimeout(createWindow, 1500)

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (backendProcess) {
    backendProcess.kill()
  }
  if (process.platform !== 'darwin') app.quit()
})

app.on('before-quit', () => {
  if (backendProcess) {
    backendProcess.kill()
  }
})
