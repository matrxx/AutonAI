// DOM Elements
const chatContainer = document.getElementById('chat-container');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');
const clearButton = document.getElementById('clear-button');
const fileUpload = document.getElementById('file-upload');
const uploadButton = document.getElementById('upload-button');
const fileInfo = document.getElementById('file-info');
const progressBar = document.getElementById('progress-bar-fill');
const progressText = document.getElementById('progress-text');
const statusButton = document.getElementById('status-button');
const toggleConsoleButton = document.getElementById('toggle-console-button');
const consoleContainer = document.getElementById('console-container');
const consoleOutput = document.getElementById('console-output');
const refreshConsoleButton = document.getElementById('refresh-console-button');
const autoScrollCheckbox = document.getElementById('auto-scroll');
const filesContainer = document.getElementById('files-container');
const filesList = document.getElementById('files-list');
const toggleFilesButton = document.getElementById('toggle-files-button');
const refreshFilesButton = document.getElementById('refresh-files-button');
const toggleThemeButton = document.getElementById('toggle-theme-button');
const themeToggle = document.getElementById('theme-toggle');

// Configuration
const API_BASE_URL = 'http://127.0.0.1:5001';
const STATUS_POLL_INTERVAL = 5000; // 5 seconds
const CONSOLE_POLL_INTERVAL = 3000; // 3 seconds
const MAX_CONSOLE_LINES = 500; // Maximum number of console lines to kee
const MAX_CONSECUTIVE_ERRORS = 3;

// App state
let isProjectRunning = false;
let statusPollingInterval = null;
let consoleVisible = false;
let consolePollingInterval = null;
let lastSeenLogTimestamp = null;
let consecutiveErrors = 0;
let filesVisible = false;
let darkMode = false;

// Event Listeners
sendButton.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        sendMessage();
    }
});
clearButton.addEventListener('click', clearConversation);
uploadButton.addEventListener('click', uploadFile);
statusButton.addEventListener('click', requestStatusUpdate);
toggleConsoleButton.addEventListener('click', toggleConsole);
refreshConsoleButton.addEventListener('click', fetchConsoleLogs);
toggleFilesButton.addEventListener('click', toggleFiles);
refreshFilesButton.addEventListener('click', fetchFiles);
themeToggle.addEventListener('click', toggleTheme);

// Toggle files visibility
function toggleFiles() {
    filesVisible = !filesVisible;
    
    if (filesVisible) {
        filesContainer.style.display = 'block';
        toggleFilesButton.textContent = 'Hide Files';
        toggleFilesButton.classList.add('active');
        fetchFiles();
    } else {
        filesContainer.style.display = 'none';
        toggleFilesButton.textContent = 'Show Files';
        toggleFilesButton.classList.remove('active');
    }
}

// Enhanced fetchFiles function for main.js
function fetchFiles() {
    // Show loading state
    filesList.innerHTML = '<div class="loading-files">Loading files...</div>';
    
    fetch(`${API_BASE_URL}/api/files`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.files && data.files.length > 0) {
                // Group files by agent
                const filesByAgent = {};
                
                for (const file of data.files) {
                    if (!filesByAgent[file.agent]) {
                        filesByAgent[file.agent] = [];
                    }
                    filesByAgent[file.agent].push(file);
                }
                
                // Clear current list
                filesList.innerHTML = '';
                
                // Create sections for each agent
                for (const agent in filesByAgent) {
                    // Create agent section
                    const agentSection = document.createElement('div');
                    agentSection.className = 'agent-files-section';
                    
                    // Add header
                    const agentHeader = document.createElement('div');
                    agentHeader.className = `agent-files-header agent-${agent.toLowerCase()}`;
                    agentHeader.innerHTML = `<h4>${agent} Files</h4>`;
                    agentSection.appendChild(agentHeader);
                    
                    // Add files
                    const agentFiles = document.createElement('div');
                    agentFiles.className = 'agent-files-list';
                    
                    for (const file of filesByAgent[agent]) {
                        const fileItem = document.createElement('div');
                        fileItem.className = 'file-item';
                        
                        // Set file icon based on type
                        let fileIcon = '📄';
                        if (file.type === 'html') fileIcon = '🌐';
                        else if (file.type === 'css') fileIcon = '🎨';
                        else if (file.type === 'js') fileIcon = '⚙️';
                        else if (file.type === 'json') fileIcon = '📊';
                        
                        // Add preview button for HTML files
                        let previewButton = '';
                        if (file.type === 'html') {
                            previewButton = `<a href="#" class="preview-button" data-file="${file.path}">Preview</a>`;
                        }
                        
                        fileItem.innerHTML = `
                            <div class="file-info">
                                <div class="file-name">${fileIcon} ${file.name}</div>
                                <div class="file-meta">
                                    Created on ${file.timestamp} • ${formatFileSize(file.size)}
                                </div>
                            </div>
                            <div class="file-actions">
                                ${previewButton}
                                <a href="${API_BASE_URL}/api/files/${file.path}" download="${file.name}" class="download-button">Download</a>
                            </div>
                        `;
                        
                        agentFiles.appendChild(fileItem);
                    }
                    
                    agentSection.appendChild(agentFiles);
                    filesList.appendChild(agentSection);
                }
                
                // Add event listeners for preview buttons
                document.querySelectorAll('.preview-button').forEach(button => {
                    button.addEventListener('click', function(e) {
                        e.preventDefault();
                        const filePath = this.getAttribute('data-file');
                        previewHtmlFile(filePath);
                    });
                });
                
            } else {
                filesList.innerHTML = '<div class="no-files">No files available yet. The agents will save their outputs as files automatically.</div>';
            }
        })
        .catch(error => {
            console.error('Error fetching files:', error);
            filesList.innerHTML = '<div class="error">Error loading files. Make sure the backend server is running.</div>';
        });
}

// Function to preview HTML files
function previewHtmlFile(filePath) {
    // Create modal dialog
    const modal = document.createElement('div');
    modal.className = 'preview-modal';
    
    modal.innerHTML = `
        <div class="preview-modal-content">
            <div class="preview-modal-header">
                <h4>HTML Preview</h4>
                <button class="close-preview-button">&times;</button>
            </div>
            <div class="preview-modal-body">
                <iframe src="${API_BASE_URL}/api/files/${filePath}" class="preview-iframe"></iframe>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Add close button event
    modal.querySelector('.close-preview-button').addEventListener('click', function() {
        document.body.removeChild(modal);
    });
    
    // Close on click outside content
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            document.body.removeChild(modal);
        }
    });
}

// Format file size
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' bytes';
    else if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    else return (bytes / 1048576).toFixed(1) + ' MB';
}

// Toggle dark mode
function toggleTheme() {
    darkMode = !darkMode;
    
    if (darkMode) {
        document.body.classList.add('dark-mode');
    } else {
        document.body.classList.remove('dark-mode');
    }
    
    // Save preference
    localStorage.setItem('darkMode', darkMode);
}

// Check for saved theme preference
function loadSavedTheme() {
    const savedMode = localStorage.getItem('darkMode');
    if (savedMode === 'true') {
        darkMode = true;
        document.body.classList.add('dark-mode');
        toggleThemeButton.textContent = 'Light Mode';
    }
}

// Call this when the page loads
loadSavedTheme();

function fetchConsoleLogs() {
    // Only show the connecting message if we have no console content
    if (consoleOutput.children.length === 0) {
        consoleOutput.innerHTML = `<div class="console-line">
            <span class="console-timestamp">[${new Date().toISOString()}]</span>
            <span class="console-agent console-agent-system">[System]</span>
            <span class="console-message">Connecting to backend server...</span>
        </div>`;
    }
    
    fetch(`${API_BASE_URL}/api/logs`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error ${response.status}`);
            }
            consecutiveErrors = 0; // Reset error counter on success
            
            // Clear the initial connecting message if it exists
            if (consoleOutput.children.length === 1 && 
                consoleOutput.querySelector('.console-message').textContent.includes("Connecting to backend server")) {
                consoleOutput.innerHTML = "";
            }
            
            return response.json();
        })
        .then(data => {
            updateConsoleOutput(data.logs);
        })
        .catch(error => {
            consecutiveErrors++;
            
            // Only add error message if we don't already have an error showing
            if (!consoleOutput.querySelector('.console-message')?.textContent.includes('Error fetching logs')) {
                consoleOutput.innerHTML += `<div class="console-line error-line">
                    <span class="console-timestamp">[${new Date().toISOString()}]</span>
                    <span class="console-agent console-agent-system">[System]</span>
                    <span class="console-message">Error fetching logs: Backend server not available. Start the Python server to see logs.</span>
                </div>`;
            }
            
            // Auto-scroll to bottom if enabled
            if (autoScrollCheckbox.checked) {
                consoleOutput.scrollTop = consoleOutput.scrollHeight;
            }
            
            // If we've had too many consecutive errors, stop polling
            if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
                stopConsolePolling();
                consoleOutput.innerHTML += `<div class="console-line">
                    <span class="console-timestamp">[${new Date().toISOString()}]</span>
                    <span class="console-agent console-agent-system">[System]</span>
                    <span class="console-message">Stopped polling due to multiple connection failures. Click "Refresh" to try again.</span>
                </div>`;
            }
        });
}

// Also, let's not start polling immediately when the page loads
// Update the initializeUI function
function initializeUI() {
    // Display welcome message
    appendMessage('system', 'Multi-Agent System initialized. The following agents are ready to assist you:\n' +
        '- ProjectManager: Planning, coordination, delegation, evaluation\n' +
        '- FrontendDev: HTML, CSS, JavaScript, UI design, responsive design\n' +
        '- BackendDev: API design, database, server logic, authentication, security\n' +
        '- ContentWriter: Copywriting, SEO, storytelling, product descriptions, marketing\n\n' +
        'To start a project, type "start project: [your project description]"');

    // Don't fetch status automatically on page load
    // We'll only do this when the user explicitly interacts with the system
}

function toggleConsole() {
    consoleVisible = !consoleVisible;
    
    if (consoleVisible) {
        // Show the console without clearing its contents
        consoleContainer.style.display = 'flex';
        toggleConsoleButton.textContent = 'Hide Console';
        toggleConsoleButton.classList.add('active');
        
        // Only fetch new logs if we don't have any yet
        if (consoleOutput.children.length === 0) {
            fetchConsoleLogs();
        }
        
        // Start or resume polling for new logs
        startConsolePolling();
    } else {
        // Hide the console without clearing its contents
        consoleContainer.style.display = 'none';
        toggleConsoleButton.textContent = 'Show Console';
        toggleConsoleButton.classList.remove('active');
        
        // Stop polling when console is hidden to save resources
        stopConsolePolling();
    }
}

function updateConsoleOutput(logs) {
    // If there are no logs, don't update anything
    if (!logs || logs.length === 0) return;
    
    // Get the timestamp of the last log we've seen
    let lastSeenLog = null;
    if (consoleOutput.children.length > 0) {
        const lastTimestampEl = consoleOutput.querySelector('.console-line:last-child .console-timestamp');
        if (lastTimestampEl) {
            // Extract timestamp without the brackets
            lastSeenLog = lastTimestampEl.textContent.replace(/^\[|\]$/g, '');
        }
    }
    
    // Filter out logs we've already seen
    let newLogs = logs;
    if (lastSeenLog) {
        newLogs = logs.filter(log => {
            // Compare timestamps, accounting for the possibility of different formats
            return new Date(log.timestamp) > new Date(lastSeenLog);
        });
    }
    
    // If there are new logs
    if (newLogs.length > 0) {
        // Add new logs to the console
        for (const log of newLogs) {
            const agentClass = `console-agent-${log.agent.toLowerCase().replace(/[^a-z0-9]/g, '')}`;
            
            consoleOutput.innerHTML += `<div class="console-line">
                <span class="console-timestamp">[${log.timestamp}]</span>
                <span class="console-agent ${agentClass}">[${log.agent}]</span>
                <span class="console-message">${escapeHtml(log.message)}</span>
            </div>`;
        }
        
        // Trim the console if it gets too long
        const consoleLines = consoleOutput.querySelectorAll('.console-line');
        if (consoleLines.length > MAX_CONSOLE_LINES) {
            for (let i = 0; i < consoleLines.length - MAX_CONSOLE_LINES; i++) {
                consoleOutput.removeChild(consoleLines[i]);
            }
        }
        
        // Auto-scroll to bottom if enabled
        if (autoScrollCheckbox.checked) {
            consoleOutput.scrollTop = consoleOutput.scrollHeight;
        }
    }
}

function startConsolePolling() {
    // Clear any existing polling interval
    stopConsolePolling();
    
    // Start new polling interval
    consolePollingInterval = setInterval(fetchConsoleLogs, CONSOLE_POLL_INTERVAL);
    
    // Reset error counter
    consecutiveErrors = 0;
}

// Add this function to stop polling for console updates
function stopConsolePolling() {
    if (consolePollingInterval) {
        clearInterval(consolePollingInterval);
        consolePollingInterval = null;
    }
}

// Helper function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize the UI
initializeUI();

// Helper function to append messages to the chat
function appendMessage(role, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    // Check if the message is from a specific agent
    const agentMatch = content.match(/^\[(.*?)\]/);
    if (agentMatch && (role === 'agent' || role === 'system')) {
        const agentName = agentMatch[1].split(' - ')[0];
        const messageContent = content.replace(/^\[(.*?)\]\s*/, '');
        
        // Create agent label
        const agentLabel = document.createElement('div');
        agentLabel.className = 'agent-label';
        agentLabel.textContent = agentMatch[1]; // Agent name and role
        
        // Set agent-specific styling
        messageDiv.classList.add(`agent-${agentName.toLowerCase().replace(/[^a-z0-9]/g, '')}`);
        
        // Add agent label to message
        messageDiv.appendChild(agentLabel);
        
        // Add message content
        const contentEl = document.createElement('div');
        contentEl.className = 'agent-content';
        contentEl.innerHTML = formatMessageContent(messageContent);
        messageDiv.appendChild(contentEl);
    } else {
        // Regular message
        messageDiv.innerHTML = formatMessageContent(content);
    }
    
    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// Format message content to handle code blocks, lists, etc.
function formatMessageContent(content) {
    // Replace code blocks
    content = content.replace(/```(\w+)?\n([\s\S]*?)```/g, function(match, language, code) {
        return `<pre class="code ${language || ''}">${escapeHtml(code)}</pre>`;
    });
    
    // Replace inline code
    content = content.replace(/`([^`]+)`/g, '<code>$1</code>');
    
    // Replace line breaks
    content = content.replace(/\n/g, '<br>');
    
    return content;
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Send message to API
function sendMessage() {
    const message = userInput.value.trim();
    if (message === '') return;
    
    // Display user message
    appendMessage('user', message);
    
    // Clear input field
    userInput.value = '';
    
    // Check for project start command
    if (message.toLowerCase().startsWith('start project:') || message.toLowerCase().startsWith('create project:')) {
        startStatusPolling();
    }
    
    // Show thinking indicator
    const thinkingDiv = document.createElement('div');
    thinkingDiv.className = 'message system thinking';
    thinkingDiv.textContent = 'Processing your request...';
    chatContainer.appendChild(thinkingDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    
    // Send message to API
    fetch(`${API_BASE_URL}/api/chat`, {
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
        
        // Display agent response
        appendMessage('agent', data.response);
        
        // Update project status if available
        if (data.project_status) {
            updateProjectStatus(data.project_status);
        }
    })
    .catch(error => {
        // Remove thinking indicator
        chatContainer.removeChild(thinkingDiv);
        
        // Display error
        appendMessage('system', `Error: Something went wrong. Please try again.`);
        console.error('Error:', error);
    });
}

// Upload file to API
function uploadFile() {
    const file = fileUpload.files[0];
    if (!file) {
        fileInfo.textContent = 'Please select a file first.';
        return;
    }
    
    fileInfo.textContent = 'Uploading and processing...';
    
    const formData = new FormData();
    formData.append('file', file);
    
    fetch(`${API_BASE_URL}/api/upload`, {
        method: 'POST',
        body: formData,
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            fileInfo.textContent = data.error;
        } else {
            fileInfo.textContent = `${file.name} processed (${data.textLength} characters)`;
            appendMessage('system', `Document "${file.name}" has been processed and is now available to all agents for reference.`);
        }
    })
    .catch(error => {
        fileInfo.textContent = `Error uploading file. Please try again.`;
        console.error('Error:', error);
    });
}

// Clear conversation and reset system
function clearConversation() {
    if (confirm('This will stop all agent activities and clear the current project. Are you sure?')) {
        fetch(`${API_BASE_URL}/api/clear`, {
            method: 'POST',
        })
        .then(response => response.json())
        .then(data => {
            chatContainer.innerHTML = '';
            fileInfo.textContent = '';
            fileUpload.value = '';
            appendMessage('system', 'Multi-Agent System has been reset. All agent memories and document context have been cleared.');
            
            // Reset project status display
            updateProjectStatus({
                progress: 0,
                tasks_completed: 0,
                tasks_total: 0
            });
            
            // Stop status polling
            stopStatusPolling();
        })
        .catch(error => {
            appendMessage('system', `Error clearing conversation. Please try again.`);
            console.error('Error:', error);
        });
    }
}

// Fetch current system status
function fetchStatus() {
    fetch(`${API_BASE_URL}/api/status`)
        .then(response => response.json())
        .then(data => {
            // Update UI with current status
            if (data.project.description) {
                updateProjectStatus(data.project);
                
                // If project is running, start polling
                if (data.running) {
                    startStatusPolling();
                }
            }
        })
        .catch(error => {
            console.error('Error fetching status:', error);
        });
}

// Update project status in the UI
function updateProjectStatus(status) {
    if (status.progress !== undefined) {
        // Update progress bar
        progressBar.style.width = `${status.progress}%`;
        
        // Update progress text
        let statusText = `Progress: ${status.progress}%`;
        if (status.tasks_total > 0) {
            statusText += ` (${status.tasks_completed}/${status.tasks_total} tasks)`;
        }
        progressText.textContent = statusText;
        
        // Update project running status
        isProjectRunning = status.progress < 100 && status.progress > 0;
        
        // Show/hide status button based on project state
    }
}

    // Fetch current status
    fetch(`${API_BASE_URL}/api/status`)
        .then(response => response.json())
        .then(data => {
            // Update UI with current status
            if (data.project.description) {
                updateProjectStatus(data.project);
                
                // Always show the status button if there's a project
                statusButton.style.display = 'inline-block';
                
                // If project is running, start polling
                if (data.running) {
                    startStatusPolling();
                }
            }
        })
        .catch(error => {
            console.error('Error fetching status:', error);
        });

// Start polling for status updates
function startStatusPolling() {
    isProjectRunning = true;
    statusButton.style.display = 'inline-block'; // Show the status button
    
    // Stop existing interval if it exists
    stopStatusPolling();
    
    // Start new interval
    statusPollingInterval = setInterval(() => {
        // ... rest of the function ...
    }, STATUS_POLL_INTERVAL);
}
    
    // Stop existing interval if it exists
    stopStatusPolling();
    
    // Start new interval
    statusPollingInterval = setInterval(() => {
        fetch(`${API_BASE_URL}/api/status`)
            .then(response => response.json())
            .then(data => {
                // Update progress
                updateProjectStatus(data.project);
                
                // Display any new updates
                const updates = data.updates;
                if (updates && updates.length > 0) {
                    // Get the last update timestamp we've seen
                    const lastMsgEl = chatContainer.querySelector('.agent-update:last-child');
                    const lastTimestamp = lastMsgEl ? lastMsgEl.dataset.timestamp : null;
                    
                    // Filter updates newer than the last one we've seen
                    let newUpdates = updates;
                    if (lastTimestamp) {
                        newUpdates = updates.filter(update => update.timestamp > lastTimestamp);
                    }
                    
                    // Display new updates
                    newUpdates.forEach(update => {
                        if (update.agent !== 'User') {
                            const updateEl = document.createElement('div');
                            updateEl.className = 'message system agent-update';
                            updateEl.dataset.timestamp = update.timestamp;
                            updateEl.textContent = `[${update.agent}] ${update.message}`;
                            chatContainer.appendChild(updateEl);
                        }
                    });
                    
                    // Scroll to bottom if we added new updates
                    if (newUpdates.length > 0) {
                        chatContainer.scrollTop = chatContainer.scrollHeight;
                    }
                }
                
                // Stop polling if the project is no longer running
                if (!data.running) {
                    stopStatusPolling();
                }
            })
            .catch(error => {
                console.error('Error fetching status updates:', error);
            });
    }, STATUS_POLL_INTERVAL);

// Stop polling for status updates
function stopStatusPolling() {
    if (statusPollingInterval) {
        clearInterval(statusPollingInterval);
        statusPollingInterval = null;
    }
}

// Request a status update from the system
function requestStatusUpdate() {
    appendMessage('user', 'What\'s the current status?');
    
    // Show thinking indicator
    const thinkingDiv = document.createElement('div');
    thinkingDiv.className = 'message system thinking';
    thinkingDiv.textContent = 'Fetching status...';
    chatContainer.appendChild(thinkingDiv);
    
    // Fetch status directly
    fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: 'status update' }),
    })
    .then(response => response.json())
    .then(data => {
        // Remove thinking indicator
        chatContainer.removeChild(thinkingDiv);
        
        // Display agent response
        appendMessage('agent', data.response);
        
        // Update project status if available
        if (data.project_status) {
            updateProjectStatus(data.project_status);
        }
    })
    .catch(error => {
        // Remove thinking indicator
        chatContainer.removeChild(thinkingDiv);
        
        // Display error
        appendMessage('system', `Error fetching status. Please try again.`);
    });
}