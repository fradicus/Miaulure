document.addEventListener('DOMContentLoaded', function() {
    fetchReports();
    
    document.getElementById('refresh-report').addEventListener('click', fetchReports);
    
    document.getElementById('download-pdf').addEventListener('click', downloadReportAsPDF);
});

let allReports = [];
let currentReportIndex = 0;

async function fetchReports() {
    try {
        const reportContent = document.getElementById('report-content');
        reportContent.innerHTML = '<p>Loading AI reports...</p>';
        
        const response = await fetch('cat_activity_db.daily_reports.json');
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const reports = await response.json();
        
        reports.sort((a, b) => {
            const dateA = a.report_date && a.report_date.$date ? new Date(a.report_date.$date) : new Date(0);
            const dateB = b.report_date && b.report_date.$date ? new Date(b.report_date.$date) : new Date(0);
            return dateB - dateA;
        });
        
        allReports = reports;
        currentReportIndex = 0;
        
        updateReportSelector(reports);
        
        if (reports.length > 0) {
            displayReport(reports[0]);
            updateLastUpdated(reports[0]);
        } else {
            reportContent.innerHTML = '<p>No reports available.</p>';
        }
        
    } catch (error) {
        console.error('Error fetching reports:', error);
        
        document.getElementById('report-content').innerHTML = 
            '<p>Error loading report data. Please try again later.</p>';
    }
}

function updateReportSelector(reports) {
    const selector = document.getElementById('report-selector');
    selector.innerHTML = '';
    
    reports.forEach((report, index) => {
        const option = document.createElement('option');
        option.value = index;
        
        const reportDate = report.report_date && report.report_date.$date 
            ? new Date(report.report_date.$date).toLocaleDateString()
            : "Unknown date";
            
        option.textContent = `Report: ${reportDate}`;
        selector.appendChild(option);
    });
    
    selector.addEventListener('change', function() {
        currentReportIndex = parseInt(this.value);
        displayReport(allReports[currentReportIndex]);
        updateLastUpdated(allReports[currentReportIndex]);
    });
}

function previousReport() {
    if (currentReportIndex > 0) {
        currentReportIndex--;
        document.getElementById('report-selector').value = currentReportIndex;
        displayReport(allReports[currentReportIndex]);
        updateLastUpdated(allReports[currentReportIndex]);
    }
}

function nextReport() {
    if (currentReportIndex < allReports.length - 1) {
        currentReportIndex++;
        document.getElementById('report-selector').value = currentReportIndex;
        displayReport(allReports[currentReportIndex]);
        updateLastUpdated(allReports[currentReportIndex]);
    }
}

function displayReport(reportData) {
    const reportContent = document.getElementById('report-content');
    
    let formattedReport = '';
    
    formattedReport += `<h3>Cat Activity Analysis Report</h3>`;
    
    const reportDate = reportData.report_date && reportData.report_date.$date 
        ? new Date(reportData.report_date.$date).toLocaleDateString()
        : "Unknown date";
    
    formattedReport += `<p class="report-date">Report date: ${reportDate}</p>`;
    
    formattedReport += `<h4>Activity Summary</h4>`;
    
    const formattedSummary = reportData.summary
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n-/g, '<br>-')
        .replace(/\n/g, '<br>');
    
    formattedReport += `<p>${formattedSummary}</p>`;
    
    if (reportData.model_used) {
        formattedReport += `<h4>Analysis Information</h4>`;
        formattedReport += `<p>This report was generated using the ${reportData.model_used} model.</p>`;
    }
    
    reportContent.innerHTML = formattedReport;
    
    const date = reportData.report_date && reportData.report_date.$date 
        ? new Date(reportData.report_date.$date) 
        : new Date();
    document.getElementById('analysis-period').textContent = date.toLocaleDateString();
    
    updateNavigationButtons();
}

function updateNavigationButtons() {
    const prevButton = document.getElementById('prev-report');
    const nextButton = document.getElementById('next-report');
    
    if (currentReportIndex === 0) {
        prevButton.classList.add('disabled');
        prevButton.setAttribute('disabled', 'disabled');
    } else {
        prevButton.classList.remove('disabled');
        prevButton.removeAttribute('disabled');
    }
    
    if (currentReportIndex === allReports.length - 1) {
        nextButton.classList.add('disabled');
        nextButton.setAttribute('disabled', 'disabled');
    } else {
        nextButton.classList.remove('disabled');
        nextButton.removeAttribute('disabled');
    }
}

function updateLastUpdated(reportData) {
    let timestamp;
    
    if (reportData.timestamp && reportData.timestamp.$date) {
        timestamp = new Date(reportData.timestamp.$date);
    } else {
        timestamp = new Date();
    }
    
    const formattedDate = timestamp.toLocaleDateString();
    const formattedTime = timestamp.toLocaleTimeString();
    
    document.getElementById('last-updated').textContent = `${formattedDate} ${formattedTime}`;
}

function downloadReportAsPDF() {
    const reportData = allReports[currentReportIndex];
    
    if (!reportData) {
        alert('No report available to download');
        return;
    }
    
    const reportContent = document.getElementById('report-content').innerText;
    
    const blob = new Blob([reportContent], { type: 'text/plain' });
    
    const url = URL.createObjectURL(blob);
    
    let dateStr = 'unknown-date';
    if (reportData.report_date && reportData.report_date.$date) {
        const date = new Date(reportData.report_date.$date);
        dateStr = date.toISOString().split('T')[0];
    }
    
    const a = document.createElement('a');
    a.href = url;
    a.download = `Cat_Activity_Report_${dateStr}.txt`;
    
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    
    URL.revokeObjectURL(url);
}

document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('prev-report').addEventListener('click', previousReport);
    document.getElementById('next-report').addEventListener('click', nextReport);
});