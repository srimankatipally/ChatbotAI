document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const messagesContainer = document.getElementById('chat-messages');
    const clearChatBtn = document.getElementById('clear-chat-btn');
    
    // Function to scroll to the bottom of the chat
    function scrollToBottom() {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
    
    // Function to add a message to the chat
    function addMessage(content, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender === 'user' ? 'user-message' : 'assistant-message'}`;
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        messageContent.innerText = content;
        
        messageDiv.appendChild(messageContent);
        messagesContainer.appendChild(messageDiv);
        
        scrollToBottom();
    }
    
    // Function to disable/enable input during processing
    function setInputState(isDisabled) {
        userInput.disabled = isDisabled;
        document.getElementById('submit-btn').disabled = isDisabled;
        
        if (isDisabled) {
            // Show a thinking indicator
            const thinkingDiv = document.createElement('div');
            thinkingDiv.className = 'message assistant-message';
            thinkingDiv.id = 'thinking-indicator';
            
            const thinkingContent = document.createElement('div');
            thinkingContent.className = 'message-content';
            thinkingContent.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
            
            thinkingDiv.appendChild(thinkingContent);
            messagesContainer.appendChild(thinkingDiv);
            scrollToBottom();
        } else {
            // Remove thinking indicator
            const thinkingIndicator = document.getElementById('thinking-indicator');
            if (thinkingIndicator) {
                thinkingIndicator.remove();
            }
        }
    }
    
    // Handle chat form submission
    chatForm.addEventListener('submit', function(event) {
        event.preventDefault();
        
        const userMessage = userInput.value.trim();
        if (!userMessage) return;
        
        // Add user message to chat
        addMessage(userMessage, 'user');
        
        // Clear input
        userInput.value = '';
        
        // Disable input while processing
        setInputState(true);
        
        // Send message to server
        fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: userMessage })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            // Enable input
            setInputState(false);
            
            // Add assistant response to chat
            addMessage(data.response, 'assistant');
        })
        .catch(error => {
            console.error('Error:', error);
            setInputState(false);
            addMessage('Sorry, there was an error processing your request. Please try again.', 'assistant');
        });
    });
    
    // Handle clear chat button
    if (clearChatBtn) {
        clearChatBtn.addEventListener('click', function() {
            if (confirm('Are you sure you want to clear the chat history?')) {
                fetch('/api/clear-chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    return response.json();
                })
                .then(data => {
                    // Clear the messages container
                    messagesContainer.innerHTML = '';
                    
                    // Add a system message
                    addMessage('Chat history cleared.', 'assistant');
                })
                .catch(error => {
                    console.error('Error:', error);
                    addMessage('Sorry, there was an error clearing the chat. Please try again.', 'assistant');
                });
            }
        });
    }
    
    // Initial scroll to bottom on page load
    scrollToBottom();
});
