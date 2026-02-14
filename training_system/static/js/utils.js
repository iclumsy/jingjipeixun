function showMessage(message, type = 'info') {
    const existingMessage = document.querySelector('.custom-message');
    if (existingMessage) {
        existingMessage.remove();
    }

    const messageElement = document.createElement('div');
    messageElement.className = `custom-message ${type}`;
    messageElement.style.position = 'fixed';
    messageElement.style.top = '20px';
    messageElement.style.right = '20px';
    messageElement.style.padding = '15px 20px';
    messageElement.style.borderRadius = '8px';
    messageElement.style.fontSize = '0.95rem';
    messageElement.style.zIndex = '10000';
    messageElement.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
    messageElement.style.transition = 'all 0.3s ease';
    messageElement.style.maxWidth = '400px';
    messageElement.style.wordWrap = 'break-word';

    if (type === 'success') {
        messageElement.style.backgroundColor = '#dcfce7';
        messageElement.style.color = '#166534';
        messageElement.style.border = '1px solid #bbf7d0';
    } else if (type === 'error') {
        messageElement.style.backgroundColor = '#fee2e2';
        messageElement.style.color = '#991b1b';
        messageElement.style.border = '1px solid #fecaca';
    } else {
        messageElement.style.backgroundColor = '#dbeafe';
        messageElement.style.color = '#1e40af';
        messageElement.style.border = '1px solid #bfdbfe';
    }

    messageElement.textContent = message;
    document.body.appendChild(messageElement);

    setTimeout(() => {
        if (messageElement.parentNode) {
            messageElement.style.opacity = '0';
            messageElement.style.transform = 'translateY(-20px)';
            setTimeout(() => {
                messageElement.remove();
            }, 300);
        }
    }, 4000);
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function showSaveStatus(container, message, type = 'info') {
    const existingStatus = container.querySelector('.save-status');
    if (existingStatus) {
        existingStatus.remove();
    }

    const statusElement = document.createElement('div');
    statusElement.className = `save-status ${type}`;
    statusElement.style.position = 'fixed';
    statusElement.style.top = '20px';
    statusElement.style.right = '20px';
    statusElement.style.padding = '10px 15px';
    statusElement.style.borderRadius = '4px';
    statusElement.style.fontSize = '0.9rem';
    statusElement.style.zIndex = '1000';
    statusElement.style.boxShadow = '0 2px 8px rgba(0,0,0,0.15)';
    statusElement.style.transition = 'all 0.3s ease';

    if (type === 'success') {
        statusElement.style.backgroundColor = '#dcfce7';
        statusElement.style.color = '#166534';
        statusElement.style.border = '1px solid #bbf7d0';
    } else if (type === 'error') {
        statusElement.style.backgroundColor = '#fee2e2';
        statusElement.style.color = '#991b1b';
        statusElement.style.border = '1px solid #fecaca';
    } else {
        statusElement.style.backgroundColor = '#dbeafe';
        statusElement.style.color = '#1e40af';
        statusElement.style.border = '1px solid #bfdbfe';
    }

    statusElement.textContent = message;
    container.appendChild(statusElement);

    setTimeout(() => {
        if (statusElement.parentNode) {
            statusElement.style.opacity = '0';
            statusElement.style.transform = 'translateX(100%)';
            setTimeout(() => {
                statusElement.remove();
            }, 300);
        }
    }, 3000);
}
