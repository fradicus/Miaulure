document.addEventListener('DOMContentLoaded', function() {
    fetchLogs();
    
    const searchInput = document.getElementById('log-search');
    searchInput.addEventListener('input', filterLogs);
});

async function fetchLogs() {
    try {
        const response = await fetch('cat_activity_db.activity_logs.json');
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        displayLogs(data);
        
    } catch (error) {
        console.error('Error fetching logs:', error);
        
        const logsBody = document.getElementById('logs-body');
        logsBody.innerHTML = '<tr><td colspan="4">Error loading activity logs. Please try again later.</td></tr>';
    }
}

function displayLogs(events) {
    const logsBody = document.getElementById('logs-body');
    
    logsBody.innerHTML = '';
    
    if (events.length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = '<td colspan="4">No activity logs found.</td>';
        logsBody.appendChild(row);
        return;
    }
    
    events.sort((a, b) => {
        const dateA = a.timestamp && a.timestamp.$date ? new Date(a.timestamp.$date) : new Date(0);
        const dateB = b.timestamp && b.timestamp.$date ? new Date(b.timestamp.$date) : new Date(0);
        return dateB - dateA;
    });
    
    events.forEach(event => {
        const row = document.createElement('tr');
        
        if (!event.activity || !event.zone) {
            return;
        }
        
        row.dataset.activity = event.activity.toLowerCase();
        row.dataset.location = event.zone.toLowerCase();
        
        let formattedTimestamp = 'N/A';
        if (event.timestamp && event.timestamp.$date) {
            const timestamp = new Date(event.timestamp.$date);
            const formattedDate = timestamp.toLocaleDateString();
            const formattedTime = timestamp.toLocaleTimeString();
            formattedTimestamp = `${formattedDate} ${formattedTime}`;
        }
        
        const confidence = event.confidence !== null ? 
            `${(event.confidence * 100).toFixed(1)}%` : 'N/A';
        
        let position = 'N/A';
        if (event.position && event.position.x !== null && event.position.y !== null) {
            position = `x: ${event.position.x}, y: ${event.position.y}`;
        }
        
        row.innerHTML = `
            <td>${formattedTimestamp}</td>
            <td>${event.activity}</td>
            <td>${event.zone}</td>
            <td>${confidence}</td>
        `;
        
        logsBody.appendChild(row);
    });
}

function filterLogs() {
    const searchTerm = document.getElementById('log-search').value.toLowerCase();
    const rows = document.getElementById('logs-body').getElementsByTagName('tr');
    
    for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        const textContent = row.textContent.toLowerCase();
        
        if (textContent.indexOf(searchTerm) > -1) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    }
}