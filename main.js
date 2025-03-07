const { app, BrowserWindow } = require('electron');
const { exec } = require('child_process');

let mainWindow;
let flaskProcess;

app.on('ready', () => {
    // Start the Flask server
    flaskProcess = exec("python app.py");

    // Create Electron window
    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        webPreferences: {
            nodeIntegration: false,
        }
    });

    // Load the Flask app
    setTimeout(() => {
        mainWindow.loadURL('http://127.0.0.1:5000');
    }, 5000); // Delay 5 seconds to let Flask start

    mainWindow.on('closed', () => {
        if (flaskProcess) flaskProcess.kill(); // Kill Flask when closing
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});
