const socket = io({ transports: ['websocket'] });

const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const logContainer = document.getElementById('logContainer');

const numbersInput = document.getElementById('numbers');
const messageInput = document.getElementById('message');

socket.on('connect', () => {
    addLog('Connected to server.', 'info');
});

socket.on('log', (data) => {
    addLog(data.message, data.type);
});

socket.on('finished', () => {
    addLog('Batch processing finished.', 'success');
    setRunningState(false);
});

function startSending() {
    const numbers = numbersInput.value;
    const message = messageInput.value;

    if (!numbers.trim() || !message.trim()) {
        addLog('Please enter numbers and a message.', 'error');
        return;
    }

    setRunningState(true);
    socket.emit('start_sending', { numbers, message });
}

function stopSending() {
    socket.emit('stop_sending');
    stopBtn.disabled = true; // Prevent double click
}

function setRunningState(isRunning) {
    if (isRunning) {
        startBtn.disabled = true;
        stopBtn.disabled = false;
        numbersInput.disabled = true;
        messageInput.disabled = true;
    } else {
        startBtn.disabled = false;
        stopBtn.disabled = true;
        numbersInput.disabled = false;
        messageInput.disabled = false;
    }
}

function addLog(message, type = 'info') {
    const div = document.createElement('div');
    div.className = `log-entry ${type}`;
    const timestamp = new Date().toLocaleTimeString();
    div.textContent = `[${timestamp}] ${message}`;

    logContainer.appendChild(div);
    logContainer.scrollTop = logContainer.scrollHeight;
}

function clearLogs() {
    logContainer.innerHTML = '';
}
