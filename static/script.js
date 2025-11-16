// Fetch and render conversations
async function loadConversations() {
    const container = document.getElementById('conversations-container');
    container.innerHTML = '<div class="loading">Loading conversations...</div>';

    try {
        const response = await fetch('/api/conversations');
        if (!response.ok) {
            throw new Error('Failed to load conversations');
        }
        
        const conversations = await response.json();
        
        if (conversations.length === 0) {
            container.innerHTML = '<div class="error">No conversations found</div>';
            return;
        }

        container.innerHTML = '';
        
        conversations.forEach(conv => {
            const conversationElement = createConversationElement(conv);
            container.appendChild(conversationElement);
        });
    } catch (error) {
        console.error('Error loading conversations:', error);
        container.innerHTML = `<div class="error">Error loading conversations: ${error.message}</div>`;
    }
}

function createConversationElement(conv) {
    const div = document.createElement('div');
    div.className = 'conversation-item';

    // User prompt
    const userPromptDiv = document.createElement('div');
    userPromptDiv.className = 'user-prompt';
    const userBubble = document.createElement('div');
    userBubble.className = 'user-prompt-bubble';
    userBubble.textContent = conv.user_prompt || 'No prompt available';
    userPromptDiv.appendChild(userBubble);
    div.appendChild(userPromptDiv);

    // Responses container
    const responsesDiv = document.createElement('div');
    responsesDiv.className = 'responses-container';

    // Determine winner status for each panel
    const winnerA = conv.winner === 'model_a';
    const winnerB = conv.winner === 'model_b';
    const isTie = conv.winner === 'tie' || conv.winner === 'Tie' || conv.winner === 'TIE';
    
    // Response A
    const panelA = createResponsePanel(
        conv.model_a,
        conv.response_a,
        winnerA,
        isTie
    );
    responsesDiv.appendChild(panelA);

    // Response B
    const panelB = createResponsePanel(
        conv.model_b,
        conv.response_b,
        winnerB,
        isTie
    );
    responsesDiv.appendChild(panelB);

    div.appendChild(responsesDiv);
    return div;
}

function createResponsePanel(modelName, responseText, isWinner, isTie) {
    const panel = document.createElement('div');
    panel.className = 'response-panel';
    if (isTie) {
        panel.classList.add('tie');
    } else if (isWinner) {
        panel.classList.add('winner');
    }

    // Model header
    const header = document.createElement('div');
    header.className = 'model-header';
    
    const logo = document.createElement('div');
    logo.className = 'model-logo';
    // Extract first letter or use model name abbreviation
    const modelInitial = modelName ? modelName.charAt(0).toUpperCase() : '?';
    logo.textContent = modelInitial;
    header.appendChild(logo);
    
    const modelNameSpan = document.createElement('span');
    modelNameSpan.textContent = modelName || 'Unknown Model';
    header.appendChild(modelNameSpan);
    
    panel.appendChild(header);

    // Response content
    const content = document.createElement('div');
    content.className = 'response-content';
    content.textContent = responseText || 'No response available';
    panel.appendChild(content);

    // Action icons
    const actions = document.createElement('div');
    actions.className = 'response-actions';
    
    const copyIcon = document.createElement('span');
    copyIcon.className = 'action-icon';
    copyIcon.innerHTML = '📋';
    copyIcon.title = 'Copy';
    copyIcon.onclick = () => copyToClipboard(responseText);
    actions.appendChild(copyIcon);
    
    const expandIcon = document.createElement('span');
    expandIcon.className = 'action-icon expand-toggle';
    expandIcon.innerHTML = '↗️';
    expandIcon.title = 'Expand';
    expandIcon.onclick = (e) => {
        e.stopPropagation();
        toggleExpand(content, expandIcon);
    };
    actions.appendChild(expandIcon);
    
    panel.appendChild(actions);

    return panel;
}

function toggleExpand(contentElement, iconElement) {
    const isExpanded = contentElement.classList.contains('expanded');
    
    if (isExpanded) {
        contentElement.classList.remove('expanded');
        iconElement.innerHTML = '↗️';
        iconElement.title = 'Expand';
    } else {
        contentElement.classList.add('expanded');
        iconElement.innerHTML = '↘️';
        iconElement.title = 'Collapse';
    }
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        // Show a brief feedback
        const notification = document.createElement('div');
        notification.textContent = 'Copied!';
        notification.style.cssText = 'position: fixed; top: 20px; right: 20px; background: #4caf50; color: white; padding: 10px 20px; border-radius: 4px; z-index: 1000;';
        document.body.appendChild(notification);
        setTimeout(() => notification.remove(), 2000);
    }).catch(err => {
        console.error('Failed to copy:', err);
    });
}

// File upload and session selection
let currentFileId = null;

document.addEventListener('DOMContentLoaded', () => {
    const uploadBtn = document.getElementById('upload-btn');
    const fileInput = document.getElementById('csv-file');
    const sessionSelector = document.getElementById('session-selector');
    const sessionSelect = document.getElementById('session-select');
    const loadSessionBtn = document.getElementById('load-session-btn');
    
    uploadBtn.addEventListener('click', async () => {
        const file = fileInput.files[0];
        if (!file) {
            alert('Please select a CSV file');
            return;
        }
        
        const formData = new FormData();
        formData.append('file', file);
        
        uploadBtn.disabled = true;
        uploadBtn.textContent = 'Uploading...';
        
        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Upload failed');
            }
            
            currentFileId = data.file_id;
            
            if (data.count === 0) {
                alert('No evaluation sessions found in the file');
                uploadBtn.disabled = false;
                uploadBtn.textContent = 'Upload';
                return;
            }
            
            if (data.count === 1) {
                // Only one session, load it directly
                await loadConversationsFromFile(currentFileId, data.session_ids[0]);
            } else {
                // Multiple sessions, show selector
                sessionSelect.innerHTML = '<option value="">Select a session...</option>';
                data.session_ids.forEach(sessionId => {
                    const option = document.createElement('option');
                    option.value = sessionId;
                    option.textContent = sessionId;
                    sessionSelect.appendChild(option);
                });
                sessionSelector.style.display = 'block';
            }
            
            uploadBtn.disabled = false;
            uploadBtn.textContent = 'Upload';
        } catch (error) {
            console.error('Upload error:', error);
            alert(`Error: ${error.message}`);
            uploadBtn.disabled = false;
            uploadBtn.textContent = 'Upload';
        }
    });
    
    loadSessionBtn.addEventListener('click', async () => {
        const selectedSessionId = sessionSelect.value;
        if (!selectedSessionId) {
            alert('Please select a session');
            return;
        }
        
        if (!currentFileId) {
            alert('No file uploaded');
            return;
        }
        
        await loadConversationsFromFile(currentFileId, selectedSessionId);
    });
});

async function loadConversationsFromFile(fileId, sessionId = null) {
    const container = document.getElementById('conversations-container');
    container.innerHTML = '<div class="loading">Loading conversations...</div>';
    
    try {
        let url = `/api/conversations/${fileId}`;
        if (sessionId) {
            url += `?session_id=${encodeURIComponent(sessionId)}`;
        }
        
        const response = await fetch(url);
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to load conversations');
        }
        
        const conversations = await response.json();
        
        if (conversations.length === 0) {
            container.innerHTML = '<div class="error">No conversations found for this session</div>';
            return;
        }
        
        container.innerHTML = '';
        
        conversations.forEach(conv => {
            const conversationElement = createConversationElement(conv);
            container.appendChild(conversationElement);
        });
        
        // Hide session selector after loading
        document.getElementById('session-selector').style.display = 'none';
    } catch (error) {
        console.error('Error loading conversations:', error);
        container.innerHTML = `<div class="error">Error loading conversations: ${error.message}</div>`;
    }
}

