// WebSocket connection for real-time updates
let ws = null;

// Initialize WebSocket
function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
    
    ws.onopen = () => {
        console.log('WebSocket connected');
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
    
    ws.onclose = () => {
        console.log('WebSocket disconnected, reconnecting...');
        setTimeout(initWebSocket, 3000);
    };
}

// Handle WebSocket messages
function handleWebSocketMessage(data) {
    if (data.type === 'healing_complete') {
        updateHealingStatus(data.result);
    } else if (data.type === 'healing_error') {
        showError(data.error);
    } else if (data.type === 'notification') {
        addNotification(data.notification);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initWebSocket();
    loadNotifications();
    
    // Setup form handler if exists
    const healForm = document.getElementById('heal-form');
    if (healForm) {
        healForm.addEventListener('submit', handleHealSubmit);
    }
    
    // Setup notification link
    const notifLink = document.getElementById('notifications-link');
    if (notifLink) {
        notifLink.addEventListener('click', (e) => {
            e.preventDefault();
            toggleNotifications();
        });
    }
});

// Handle heal form submission
async function handleHealSubmit(e) {
    e.preventDefault();
    
    const targetFile = document.getElementById('target-file').value;
    const stackTrace = document.getElementById('stack-trace').value;
    const repoPath = document.getElementById('repo-path').value || '.';
    
    if (!targetFile && !stackTrace) {
        alert('Please provide either a target file or stack trace');
        return;
    }
    
    // Show status section
    const statusSection = document.getElementById('status-section');
    statusSection.style.display = 'block';
    
    // Reset progress
    updateProgress(10, 'Analyzing code...');
    
    try {
        const response = await fetch('/api/heal', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                target_file: targetFile || null,
                stack_trace: stackTrace || null,
                repo_path: repoPath
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            updateProgress(30, 'Self-healing started...');
            
            // Simulate progress (real updates will come via WebSocket)
            simulateProgress();
        } else {
            showError(data.detail || 'Failed to start healing');
        }
    } catch (error) {
        showError('Network error: ' + error.message);
    }
}

// Update progress bar
function updateProgress(percent, message) {
    const progress = document.getElementById('progress');
    const statusMessage = document.getElementById('status-message');
    
    progress.style.width = percent + '%';
    progress.textContent = percent + '%';
    statusMessage.textContent = message;
}

// Simulate progress updates
function simulateProgress() {
    let progress = 30;
    const messages = [
        'Creating repair plan...',
        'Generating patch...',
        'Running tests...',
        'Evaluating quality...'
    ];
    
    const interval = setInterval(() => {
        progress += 15;
        const msgIndex = Math.floor((progress - 30) / 20);
        
        if (progress >= 90) {
            clearInterval(interval);
            updateProgress(90, 'Finalizing...');
        } else {
            updateProgress(progress, messages[msgIndex] || 'Processing...');
        }
    }, 2000);
}

// Update healing status from WebSocket
function updateHealingStatus(result) {
    updateProgress(100, 'Complete!');
    
    setTimeout(() => {
        if (result.status === 'SUCCESS') {
            if (result.details.requires_approval) {
                alert('Patch generated successfully! Please review and approve.');
                window.location.href = `/patch-review/${result.run_id}`;
            } else {
                alert('Fix applied successfully!');
                window.location.href = '/dashboard';
            }
        } else if (result.status === 'ESCALATED') {
            alert('Manual review required. Check notifications.');
            window.location.href = '/dashboard';
        } else {
            alert('Healing completed with status: ' + result.status);
            window.location.href = '/dashboard';
        }
    }, 1000);
}

// Show error message
function showError(message) {
    const statusSection = document.getElementById('status-section');
    statusSection.style.display = 'block';
    statusSection.innerHTML = `
        <h3 style="color: var(--danger);">Error</h3>
        <p>${message}</p>
    `;
}

// Load notifications
async function loadNotifications() {
    try {
        const response = await fetch('/api/notifications?unread_only=true');
        const data = await response.json();
        
        const badge = document.getElementById('notification-badge');
        if (badge) {
            badge.textContent = data.notifications.length;
        }
    } catch (error) {
        console.error('Failed to load notifications:', error);
    }
}

// Toggle notifications panel
async function toggleNotifications() {
    const panel = document.getElementById('notifications-panel');
    
    if (!panel) {
        // Create panel if it doesn't exist
        const newPanel = document.createElement('section');
        newPanel.id = 'notifications-panel';
        newPanel.className = 'notifications-panel';
        newPanel.innerHTML = '<h2>Notifications</h2><div id="notifications-container"></div>';
        document.querySelector('main').appendChild(newPanel);
    }
    
    const notifPanel = document.getElementById('notifications-panel');
    
    if (notifPanel.style.display === 'none' || !notifPanel.style.display) {
        notifPanel.style.display = 'block';
        await fetchAndDisplayNotifications();
    } else {
        notifPanel.style.display = 'none';
    }
}

// Fetch and display notifications
async function fetchAndDisplayNotifications() {
    try {
        const response = await fetch('/api/notifications');
        const data = await response.json();
        
        const container = document.getElementById('notifications-container');
        
        if (data.notifications.length === 0) {
            container.innerHTML = '<p class="empty-state">No notifications</p>';
            return;
        }
        
        container.innerHTML = data.notifications.map(notif => `
            <div class="notification ${notif.type} ${notif.read ? '' : 'unread'}" 
                 onclick="markAsRead('${notif.id}')">
                <h4>${notif.title}</h4>
                <p>${notif.message}</p>
                <small>${new Date(notif.timestamp).toLocaleString()}</small>
                ${notif.requires_action ? '<br><strong>Action Required</strong>' : ''}
            </div>
        `).join('');
    } catch (error) {
        console.error('Failed to fetch notifications:', error);
    }
}

// Mark notification as read
async function markAsRead(notificationId) {
    try {
        await fetch(`/api/notifications/${notificationId}/read`, {
            method: 'POST'
        });
        
        loadNotifications();
        fetchAndDisplayNotifications();
    } catch (error) {
        console.error('Failed to mark notification as read:', error);
    }
}

// Add new notification (from WebSocket)
function addNotification(notification) {
    loadNotifications();
    
    // Show browser notification if permitted
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(notification.title, {
            body: notification.message,
            icon: '/static/icon.png'
        });
    }
}
// Refresh notification badge
async function refreshNotificationBadge() {
    try {
        const response = await fetch('/api/notifications?unread_only=true');
        const data = await response.json();
        
        const badge = document.getElementById('notification-badge');
        if (badge) {
            const count = data.notifications.length;
            badge.textContent = count;
            badge.style.display = count > 0 ? 'inline' : 'none';
        }
    } catch (error) {
        console.error('Failed to refresh badge:', error);
    }
}

// Refresh badge every 5 seconds
setInterval(refreshNotificationBadge, 5000);

// Call immediately
refreshNotificationBadge();