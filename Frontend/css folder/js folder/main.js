let currentPage = 1;
let currentFilters = {};
let chartsInstance = {};

function switchTab(tabName) {
    document.querySelectorAll('.section').forEach(section => {
        section.classList.remove('active');
    });

    document.querySelectorAll('.sidebar-menu li').forEach(li => {
        li.classList.remove('active');
    });

    document.getElementById(tabName).classList.add('active');
    event.target.closest('li').classList.add('active');
}

async function loadDashboard() {
    try {
        const stats = await fetchStatistics();
        updateStats(stats);
        await loadPlacements();
        await loadTopCompanies();
        initCharts(stats);
    } catch (error) {
        console.error('Error loading dashboard:', error);
    }
}

function updateStats(stats) {
    document.getElementById('totalStudents').textContent = stats.total_students || 0;
    document.getElementById('placedStudents').textContent = stats.placed || 0;
    document.getElementById('higherStudies').textContent = stats.higher_studies || 0;
    document.getElementById('avgPackage').textContent = `₹${stats.avg_salary || 0}L`;
}

async function loadPlacements(page = 1) {
    try {
        const data = await fetchAlumni(currentFilters);
        displayPlacements(data);
    } catch (error) {
        console.error('Error loading placements:', error);
    }
}

function displayPlacements(data) {
    const tbody = document.getElementById('placementTable');
    
    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center;">No data found</td></tr>';
        return;
    }

    tbody.innerHTML = data.map(student => `
        <tr>
            <td>${student.name}</td>
            <td>${student.year}</td>
            <td><span class="badge ${student.stream === 'Core Mechanical' ? 'core' : 'it'}">${student.stream}</span></td>
            <td>${student.company || 'N/A'}</td>
            <td>${student.job_title || 'N/A'}</td>
            <td>${student.salary ? `₹${student.salary}L` : 'N/A'}</td>
        </tr>
    `).join('');
}

async function loadTopCompanies() {
    try {
        const companies = await fetchTopCompanies();
        const container = document.getElementById('topCompanies');
        
        if (companies.length === 0) {
            container.innerHTML = '<div class="loading">No company data</div>';
            return;
        }

        container.innerHTML = companies.map(c => `
            <div class="company-item">
                <span class="company-name">${c.name}</span>
                <span class="company-count">${c.count} students</span>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error:', error);
    }
}

function applyFilters() {
    currentFilters = {
        name: document.getElementById('filterName').value,
        stream: document.getElementById('filterStream').value
    };
    currentPage = 1;
    loadPlacements();
}

async function handleFileSelect() {
    const file = document.getElementById('fileInput').files[0];
    if (file) {
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            await uploadFile(formData);
            alert('File uploaded successfully!');
        } catch (error) {
            alert('Error uploading file: ' + error.message);
        }
    }
}

async function startScraping() {
    const file = document.getElementById('fileInput').files[0];
    if (!file) {
        alert('Please select a file first');
        return;
    }

    const progressContainer = document.getElementById('progressContainer');
    progressContainer.style.display = 'block';
    
    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/scrape', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Scraping failed');
        }

        let progress = 0;
        const interval = setInterval(() => {
            progress += Math.random() * 30;
            if (progress > 100) progress = 100;
            
            document.getElementById('progressBar').style.width = progress + '%';
            document.getElementById('progressText').textContent = Math.round(progress) + '%';
            
            if (progress === 100) {
                clearInterval(interval);
                setTimeout(() => {
                    alert('Data updated successfully!');
                    progressContainer.style.display = 'none';
                    loadDashboard();
                }, 1000);
            }
        }, 300);
    } catch (error) {
        alert('Error: ' + error.message);
        progressContainer.style.display = 'none';
    }
}

async function exportData(format) {
    try {
        window.location.href = `/api/export?format=${format}`;
    } catch (error) {
        alert('Error exporting: ' + error.message);
    }
}

async function initCharts(stats) {
    // Stream Chart
    const streamCtx = document.getElementById('streamChart');
    if (streamCtx && !chartsInstance.stream) {
        chartsInstance.stream = new Chart(streamCtx, {
            type: 'bar',
            data: {
                labels: ['Core Mechanical', 'IT'],
                datasets: [{
                    label: 'Number of Students',
                    data: [stats.core_mechanical || 0, stats.it || 0],
                    backgroundColor: ['#fb6340', '#5e72e4']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true } }
            }
        });
    }

    // Category Chart
    const categoryCtx = document.getElementById('categoryChart');
    if (categoryCtx && !chartsInstance.category) {
        chartsInstance.category = new Chart(categoryCtx, {
            type: 'doughnut',
            data: {
                labels: ['Core Mechanical', 'IT', 'Higher Studies'],
                datasets: [{
                    data: [stats.core_mechanical || 0, stats.it || 0, stats.higher_studies || 0],
                    backgroundColor: ['#fb6340', '#5e72e4', '#2dce89']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'bottom' } }
            }
        });
    }

    // Trend Chart
    const trendCtx = document.getElementById('trendChart');
    if (trendCtx && !chartsInstance.trend) {
        chartsInstance.trend = new Chart(trendCtx, {
            type: 'line',
            data: {
                labels: ['2020', '2021', '2022', '2023', '2024'],
                datasets: [{
                    label: 'Placement Rate (%)',
                    data: [68, 71, 74, 75, stats.placement_rate || 0],
                    borderColor: '#5e72e4',
                    backgroundColor: 'rgba(94, 114, 228, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true, max: 100 } }
            }
        });
    }

    // Salary Chart
    const salaryCtx = document.getElementById('salaryChart');
    if (salaryCtx && !chartsInstance.salary) {
        chartsInstance.salary = new Chart(salaryCtx, {
            type: 'bar',
            data: {
                labels: ['3-4L', '4-5L', '5-6L', '6-8L', '8-10L'],
                datasets: [{
                    label: 'Number of Students',
                    data: [15, 28, 45, 60, 30],
                    backgroundColor: ['#fb6340', '#f5365c', '#ff6b6b', '#ffa07a', '#ffb3ba']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true } }
            }
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('placementTable')) {
        loadDashboard();
    }
});