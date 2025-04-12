document.addEventListener('DOMContentLoaded', function() {
    fetchActivityData();
    setInterval(fetchActivityData, 30000);
});

 // function to fetch activity data from the json file
async function fetchActivityData() {
    try {
        const response = await fetch('cat_activity_db.activity_logs.json');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        updateActivityCards(data);
        createActivityChart(data);
        generateBehaviorSummary(data);
    } catch (error) {
        console.error('Error fetching activity data:', error);
        document.querySelector('.activity-summary').innerHTML = 
            '<div class="activity-card"><h3>Error</h3><p>Could not load activity data</p></div>';
        document.getElementById('behavior-text').innerHTML = 
            '<p>Error loading activity data. Please try again later.</p>';
    }
}

 // function to dynamically update activity cards based on available data
function updateActivityCards(data) {
    const activitySummary = document.querySelector('.activity-summary');
    activitySummary.innerHTML = '';
    const activityCounts = {};
    data.forEach(activity => {
        if (activity.activity) {
            activityCounts[activity.activity] = (activityCounts[activity.activity] || 0) + 1;
        }
    });
    const sortedActivities = Object.entries(activityCounts)
        .sort((a, b) => b[1] - a[1]);
    sortedActivities.slice(0, 8).forEach(([activity, count]) => {
        const card = document.createElement('div');
        card.className = 'activity-card';
        const displayName = activity.charAt(0).toUpperCase() + activity.slice(1);
        card.innerHTML = `
            <h3>${displayName}</h3>
            <p class="count">${count}</p>
        `;
        activitySummary.appendChild(card);
    });
}

 // function to create/update the activity chart
function createActivityChart(data) {
    const activityTypes = new Set();
    data.forEach(item => {
        if (item.activity) {
            activityTypes.add(item.activity);
        }
    });
    const hourlyData = processHourlyData(data, Array.from(activityTypes));
    const ctx = document.getElementById('activity-chart').getContext('2d');
    if (window.activityChart instanceof Chart) {
        window.activityChart.destroy();
    }
    const colorPalette = [
        'rgba(255, 99, 132, 0.7)',
        'rgba(54, 162, 235, 0.7)',
        'rgba(255, 206, 86, 0.7)',
        'rgba(75, 192, 192, 0.7)',
        'rgba(153, 102, 255, 0.7)',
        'rgba(255, 159, 64, 0.7)',
        'rgba(201, 203, 207, 0.7)',
        'rgba(0, 204, 150, 0.7)',
        'rgba(255, 99, 71, 0.7)'
    ];
    const datasets = Array.from(activityTypes).map((type, index) => {
        return {
            label: type,
            data: hourlyData[type] || Array(24).fill(0),
            backgroundColor: colorPalette[index % colorPalette.length]
        };
    });
    window.activityChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: Array.from({length: 24}, (_, i) => `${i}:00`),
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: 'Hourly Activity Distribution'
                },
                legend: {
                    position: 'top'
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Hour of Day'
                    },
                    stacked: true
                },
                y: {
                    beginAtZero: true,
                    stacked: true,
                    title: {
                        display: true,
                        text: 'Number of Events'
                    }
                }
            }
        }
    });
}

 // function to process data to get hourly activity counts
function processHourlyData(activities, activityTypes) {
    const hourlyData = {};
    activityTypes.forEach(type => {
        hourlyData[type] = Array(24).fill(0);
    });
    activities.forEach(activity => {
        if (!activity.timestamp || !activity.timestamp.$date || !activity.activity) return;
        const timestamp = new Date(activity.timestamp.$date);
        const hour = timestamp.getHours();
        const activityType = activity.activity;
        if (hourlyData[activityType]) {
            hourlyData[activityType][hour]++;
        }
    });
    return hourlyData;
}

 // function to generate simplified behavior summary based on activity patterns
function generateBehaviorSummary(data) {
    const behaviorText = document.getElementById('behavior-text');
    const validActivities = data.filter(activity => 
        activity.activity && activity.timestamp && activity.timestamp.$date
    );
    const dates = validActivities.map(activity => {
        const date = new Date(activity.timestamp.$date);
        return date.toLocaleDateString();
    });
    const uniqueDates = [...new Set(dates)];
    const sortedActivities = [...validActivities].sort((a, b) => {
        return new Date(b.timestamp.$date) - new Date(a.timestamp.$date);
    });
    const activityCounts = {};
    validActivities.forEach(activity => {
        activityCounts[activity.activity] = (activityCounts[activity.activity] || 0) + 1;
    });
    const topActivities = Object.entries(activityCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3);
    const zoneCounts = {};
    validActivities.forEach(activity => {
        if (activity.zone) {
            zoneCounts[activity.zone] = (zoneCounts[activity.zone] || 0) + 1;
        }
    });
    const topZones = Object.entries(zoneCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3);
    let summary = '';
    summary += `<p>Data overview: ${validActivities.length} total activities recorded over ${uniqueDates.length} days.</p>`;
    summary += `<p>Most common activities: ${topActivities.map(([activity, count]) => 
        `${activity} (${count} events)`).join(', ')}.</p>`;
    summary += `<p>Preferred locations: ${topZones.map(([zone, count]) => 
        `${zone} (${count} events)`).join(', ')}.</p>`;
    if (sortedActivities.length > 0) {
        const latestActivity = sortedActivities[0];
        const latestTime = new Date(latestActivity.timestamp.$date);
        summary += `<p>Most recent activity: ${latestActivity.activity} in the ${latestActivity.zone || 'unknown area'} at ${latestTime.toLocaleTimeString()} on ${latestTime.toLocaleDateString()}.</p>`;
    }
    const sleepCount = activityCounts['Sleeping'] || 0;
    const playCount = activityCounts['Playing'] || 0;
    const eatCount = activityCounts['Eating'] || 0;
    if (playCount > eatCount && playCount > sleepCount) {
        summary += "<p>The cat appears to be quite playful based on the recorded activities.</p>";
    } else if (sleepCount > playCount && sleepCount > eatCount) {
        summary += "<p>The cat seems to enjoy a lot of rest based on the recorded activities.</p>";
    } else if (eatCount > playCount && eatCount > sleepCount) {
        summary += "<p>The cat has been eating frequently based on the recorded activities.</p>";
    }
    behaviorText.innerHTML = summary;
}
