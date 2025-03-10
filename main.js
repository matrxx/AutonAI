// DOM Elements
const chatContainer = document.getElementById('chat-container');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');
const clearButton = document.getElementById('clear-button');
const fileUpload = document.getElementById('file-upload');
const uploadButton = document.getElementById('upload-button');
const fileInfo = document.getElementById('file-info');

// Event Listeners
sendButton.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        sendMessage();
    }
});
clearButton.addEventListener('click', clearConversation);
uploadButton.addEventListener('click', uploadFile);

// Display a welcome message
appendMessage('assistant', 'Hello! I\'m your AI assistant. You can ask me questions, and I can help with calculations, weather information, and more. You can also upload documents for me to analyze.');

// Functions
function appendMessage(role, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    messageDiv.textContent = content;
    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function sendMessage() {
    const message = userInput.value.trim();
    if (message === '') return;
    
    // Display user message
    appendMessage('user', message);
    
    // Clear input field
    userInput.value = '';
    
    // Show thinking indicator
    const thinkingDiv = document.createElement('div');
    thinkingDiv.className = 'message assistant thinking';
    thinkingDiv.textContent = 'Thinking...';
    chatContainer.appendChild(thinkingDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    
    // Send message to API
    fetch('/api/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: message }),
    })
    .then(response => response.json())
    .then(data => {
        // Remove thinking indicator
        chatContainer.removeChild(thinkingDiv);
        
        // Display assistant response
        appendMessage('assistant', data.response);
    })
    .catch(error => {
        // Remove thinking indicator
        chatContainer.removeChild(thinkingDiv);
        
        // Display error
        appendMessage('assistant', `Error: Something went wrong. Please try again.`);
        console.error('Error:', error);
    });
}

function uploadFile() {
    const file = fileUpload.files[0];
    if (!file) {
        fileInfo.textContent = 'Please select a file first.';
        return;
    }
    
    fileInfo.textContent = 'Uploading and processing...';
    
    const formData = new FormData();
    formData.append('file', file);
    
    fetch('/api/upload', {
        method: 'POST',
        body: formData,
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            fileInfo.textContent = data.error;
        } else {
            fileInfo.textContent = `${file.name} processed (${data.textLength} characters)`;
            appendMessage('assistant', `I've processed the document "${file.name}" and can now answer questions about it.`);
        }
    })
    .catch(error => {
        fileInfo.textContent = `Error uploading file. Please try again.`;
        console.error('Error:', error);
    });
}

function clearConversation() {
    fetch('/api/clear', {
        method: 'POST',
    })
    .then(response => response.json())
    .then(data => {
        chatContainer.innerHTML = '';
        fileInfo.textContent = '';
        fileUpload.value = '';
        appendMessage('assistant', 'Conversation and document context cleared. How can I help you?');
    })
    .catch(error => {
        appendMessage('assistant', `Error clearing conversation. Please try again.`);
        console.error('Error:', error);
    });
}