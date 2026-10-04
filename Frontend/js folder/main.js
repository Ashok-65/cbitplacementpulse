let currentPage = 1;
let currentFilters = {};
let chartsInstance = {};
let suggestionTimer = null;
let suggestionRequestId = 0;
let activeSuggestionIndex = -1;
let dashboardStats = null;
let expandedChart = null;
let chartModalReturnFocus = null;

function escapeHtml(value) {
    const entities = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
    return String(value ?? '').replace(/[&<>"']/g, character => entities[character]);
}

function safeExternalUrl(value) {
    try {
        const url = new URL(value);
        return ['http:', 'https:'].includes(url.protocol) ? escapeHtml(url.href) : '';
    } catch {
        return '';
    }
}

function switchTab(tabName) {
    const tabs = document.querySelectorAll('.section');
    const menuItems = document.querySelectorAll('.sidebar-menu li');
    const target = document.getElementById(tabName);

    if (!target || !target.classList.contains('section')) return;

    tabs.forEach(section => section.classList.remove('active'));
    menuItems.forEach(li => li.classList.remove('active'));
    target.classList.add('active');

    const activeLink = document.querySelector(`.sidebar-menu a[data-tab="${tabName}"]`);
    if (activeLink && activeLink.closest('li')) {
        activeLink.closest('li').classList.add('active');
    }
    document.querySelectorAll('.sidebar-menu a[data-tab]').forEach(link => {
        if (link === activeLink) link.setAttribute('aria-current', 'page');
        else link.removeAttribute('aria-current');
    });
}

function getRecentSearchHistory() {
    try {
        const history = JSON.parse(window.localStorage.getItem('alumniRecentSearches') || '[]');
        return Array.isArray(history) ? history.filter(item => typeof item === 'string') : [];
    } catch {
        return [];
    }
}

function setBackendStatus(message) {
    const banner = document.getElementById('backendStatus');
    const messageNode = document.getElementById('backendStatusMessage');
    if (!banner || !messageNode) return;
    if (message) {
        messageNode.textContent = `${message}. Confirm Flask is running, or open the local dashboard link.`;
        banner.classList.remove('hidden');
    } else {
        banner.classList.add('hidden');
    }
}

async function loadDashboard() {
    try {
        const placementRequest = loadPlacements();
        const [stats, companies, yearlyInsights] = await Promise.all([
            fetchStatistics(),
            loadTopCompanies(),
            fetchYearlyInsights()
        ]);
        setBackendStatus(stats.api_error || '');
        dashboardStats = stats;
        populateOverviewYears(stats);
        populatePlacementFilters(stats);
        updateStats(stats);
        try {
            initCharts(stats, companies);
        } catch (error) {
            console.error('Chart rendering failed:', error);
            renderChartFallback(stats, companies);
        }
        displayYearlyInsights(yearlyInsights);
        await placementRequest;
    } catch (error) {
        console.error('Error loading dashboard:', error);
    }
}

function updateStats(stats) {
    const yearSelect = document.getElementById('overviewYear');
    const selectedYear = yearSelect?.value;
    const yearlyData = stats.yearly_data || [];
    const selected = selectedYear === 'all'
        ? null
        : yearlyData.find(year => year.academic_year === selectedYear) || yearlyData.find(year => year.academic_year === stats.latest_academic_year);
    const total = selected
        ? Number(selected.students || 0)
        : yearlyData.reduce((sum, year) => sum + Number(year.students || 0), 0);
    const placed = selected
        ? Number(selected.placed || 0)
        : yearlyData.reduce((sum, year) => sum + Number(year.placed || 0), 0);
    const offerCount = selected
        ? Number(selected.offer_count || 0)
        : yearlyData.reduce((sum, year) => sum + Number(year.offer_count || 0), 0);
    const placementRate = selected
        ? Number(selected.placement_rate || 0)
        : total ? Math.round(placed / total * 1000) / 10 : 0;

    document.getElementById('totalStudents').textContent = total;
    document.getElementById('placedStudents').textContent = placed;
    document.getElementById('placementRate').textContent = `${placementRate}%`;
    document.getElementById('offerCount').textContent = offerCount;
    document.querySelectorAll('.yearly-card').forEach(card => {
        card.classList.toggle('is-selected', card.dataset.year === selected?.academic_year);
    });
}

function populateOverviewYears(stats) {
    const select = document.getElementById('overviewYear');
    if (!select) return;
    const currentValue = select.value;
    const years = (stats.yearly_data || []).map(year => year.academic_year);
    select.innerHTML = [
        '<option value="all">All years</option>',
        ...years.map(year => `<option value="${escapeHtml(year)}">${escapeHtml(year)}</option>`)
    ].join('');
    select.value = years.includes(currentValue) || currentValue === 'all'
        ? currentValue
        : stats.latest_academic_year || 'all';
}

function populatePlacementFilters(stats) {
    const branchSelect = document.getElementById('filterBranch');
    const yearSelect = document.getElementById('filterPlacementYear');
    const selectedBranch = branchSelect?.value || '';
    const selectedYear = yearSelect?.value || '';
    const branches = stats.branch_labels || [];
    const years = (stats.yearly_data || []).map(year => year.academic_year);

    if (branchSelect) {
        branchSelect.innerHTML = [
            '<option value="">All branches</option>',
            ...branches.map(branch => `<option value="${escapeHtml(branch)}">${escapeHtml(branch)}</option>`)
        ].join('');
        branchSelect.value = branches.includes(selectedBranch) ? selectedBranch : '';
    }
    if (yearSelect) {
        yearSelect.innerHTML = [
            '<option value="">All placement years</option>',
            ...years.map(year => `<option value="${escapeHtml(year)}">${escapeHtml(year)}</option>`)
        ].join('');
        yearSelect.value = years.includes(selectedYear) ? selectedYear : '';
    }
}

function selectOverviewYear(year) {
    const select = document.getElementById('overviewYear');
    if (select) select.value = year;
    if (dashboardStats) updateStats(dashboardStats);
}

async function loadPlacements(page = currentPage) {
    try {
        currentPage = Math.max(page, 1);
        const result = await fetchAlumni(currentFilters, { page: currentPage, limit: 50 });
        displayPlacements(result.items || []);
        const resultsSummary = document.getElementById('resultsSummary');
        if (resultsSummary) {
            const filters = [currentFilters.name, currentFilters.branch, currentFilters.placement_year, currentFilters.placement].filter(Boolean);
            resultsSummary.textContent = `${Number(result.total || 0).toLocaleString()} records${filters.length ? ` matching ${filters.join(' · ')}` : ' in verified placement data'}`;
        }
        const pageStatus = document.getElementById('pageStatus');
        const previousPage = document.getElementById('previousPage');
        const nextPage = document.getElementById('nextPage');
        if (pageStatus) {
            const pages = Math.max(result.pages || 1, 1);
            pageStatus.textContent = `Page ${result.page || currentPage} of ${pages} · ${result.total || 0} records`;
            previousPage.disabled = currentPage <= 1;
            nextPage.disabled = currentPage >= pages;
        }
    } catch (error) {
        console.error('Error loading placements:', error);
        setBackendStatus(error.message);
        const tbody = document.getElementById('placementTable');
        const resultsSummary = document.getElementById('resultsSummary');
        const detailCard = document.getElementById('studentDetailCard');
        if (tbody) tbody.innerHTML = '<tr><td colspan="6" class="table-error">Could not load placement records.</td></tr>';
        if (resultsSummary) resultsSummary.textContent = `Search failed: ${escapeHtml(error.message)}. Please retry.`;
        if (detailCard) detailCard.classList.add('hidden');
        document.getElementById('previousPage').disabled = true;
        document.getElementById('nextPage').disabled = true;
    }
}

function changePage(offset) {
    loadPlacements(currentPage + offset);
}

async function fetchSuggestions(query, requestId) {
    const container = document.getElementById('searchSuggestions');
    if (!query || query.trim().length < 2) {
        container.classList.add('hidden');
        document.getElementById('filterName').setAttribute('aria-expanded', 'false');
        return;
    }

    let items;
    try {
        const result = await fetchAlumni({ name: query.trim() }, { page: 1, limit: 6 });
        if (requestId !== suggestionRequestId) return;
        items = (result.items || []).slice(0, 6);
    } catch (error) {
        if (requestId !== suggestionRequestId) return;
        container.innerHTML = `<div class="suggestion-message">Suggestions unavailable: ${escapeHtml(error.message)}</div>`;
        container.classList.remove('hidden');
        document.getElementById('filterName').setAttribute('aria-expanded', 'true');
        return;
    }

    if (!items.length) {
        activeSuggestionIndex = -1;
        container.classList.add('hidden');
        document.getElementById('filterName').setAttribute('aria-expanded', 'false');
        return;
    }

    activeSuggestionIndex = -1;
    container.setAttribute('role', 'listbox');
    container.innerHTML = items.map((student, index) => {
        const companies = student.companies?.length
            ? student.companies
            : (student.offers || []).map(offer => offer.company).filter(Boolean);
        const placementYears = getPlacementYears(student);
        return `
        <button class="suggestion-item" id="searchSuggestion-${index}" role="option" aria-selected="false" data-value="${escapeHtml(student.name)}">
            <span class="suggestion-main">
                <strong>${escapeHtml(student.name)}</strong>
                <small>${escapeHtml(student.branch || student.stream || 'Branch not listed')} · Class of ${escapeHtml(student.year || 'N/A')}</small>
            </span>
            <span class="suggestion-details">
                <span><b>Company</b> ${escapeHtml(companies.join(', ') || 'Not listed')}</span>
                <span><b>Placed</b> ${escapeHtml(placementYears.join(', ') || 'Year not listed')}</span>
                <span><b>Package</b> ${escapeHtml(formatSalary(student.salary))}</span>
            </span>
        </button>
        `;
    }).join('');

    container.classList.remove('hidden');
    document.getElementById('filterName').setAttribute('aria-expanded', 'true');
    container.querySelectorAll('.suggestion-item').forEach(button => {
        button.addEventListener('click', () => {
            selectSuggestion(button);
        });
    });
}

function getPlacementYears(student) {
    const offerYears = (student.offers || []).map(offer => offer.academic_year).filter(Boolean);
    return [...new Set(offerYears)];
}

function selectSuggestion(button) {
    const input = document.getElementById('filterName');
    input.value = button.dataset.value;
    document.getElementById('searchSuggestions').classList.add('hidden');
    input.setAttribute('aria-expanded', 'false');
    input.removeAttribute('aria-activedescendant');
    activeSuggestionIndex = -1;
    applyFilters();
}

function moveSuggestionSelection(direction) {
    const input = document.getElementById('filterName');
    const items = [...document.querySelectorAll('#searchSuggestions .suggestion-item')];
    if (!items.length) return false;

    activeSuggestionIndex = activeSuggestionIndex === -1
        ? direction > 0 ? 0 : items.length - 1
        : (activeSuggestionIndex + direction + items.length) % items.length;
    items.forEach((item, index) => {
        const active = index === activeSuggestionIndex;
        item.classList.toggle('is-active', active);
        item.setAttribute('aria-selected', String(active));
    });
    input.setAttribute('aria-activedescendant', items[activeSuggestionIndex].id);
    items[activeSuggestionIndex].scrollIntoView({ block: 'nearest' });
    return true;
}

function displayPlacements(data) {
    const tbody = document.getElementById('placementTable');
    const detailCard = document.getElementById('studentDetailCard');
    const detailContent = document.getElementById('studentDetailContent');

    if (!tbody) return;

    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center;">No data found</td></tr>';
        if (detailCard) {
            detailCard.classList.add('hidden');
        }
        if (detailContent) {
            detailContent.innerHTML = '';
        }
        return;
    }

    tbody.innerHTML = data.map(student => `
        <tr data-id="${student.id}" class="student-row">
            <td>${escapeHtml(student.name)}</td>
            <td>${escapeHtml(student.year ? `Class of ${student.year}` : 'N/A')}</td>
            <td><span class="badge ${student.branch === 'Core Mechanical' ? 'core' : 'it'}">${escapeHtml(student.branch || student.stream || 'N/A')}</span></td>
            <td>${escapeHtml(student.companies?.length ? `${student.companies.slice(0, 2).join(', ')}${student.companies.length > 2 ? ` +${student.companies.length - 2}` : ''}` : student.company || 'N/A')}</td>
            <td>${escapeHtml(getPlacementYears(student).join(', ') || 'Not listed')}</td>
            <td>${escapeHtml(formatSalary(student.salary))}</td>
        </tr>
    `).join('');

    document.querySelectorAll('.student-row').forEach(row => {
        row.addEventListener('click', () => {
            document.querySelectorAll('.student-row').forEach(item => item.classList.remove('is-selected'));
            row.classList.add('is-selected');
            const student = data.find(item => String(item.id) === row.dataset.id);
            showStudentDetails(student);
        });
    });

    if (currentFilters.name) {
        const matchingStudent = data.find(student => student.name.toLowerCase() === currentFilters.name.trim().toLowerCase()) || data[0];
        showStudentDetails(matchingStudent);
        document.querySelector(`.student-row[data-id="${matchingStudent.id}"]`)?.classList.add('is-selected');
    } else {
        detailCard.classList.add('hidden');
    }
}

function formatSalary(value) {
    if (value === null || value === undefined || value === '') return 'Not listed';
    return `₹${Number(value).toFixed(2)}L`;
}

function showStudentDetails(student) {
    const detailCard = document.getElementById('studentDetailCard');
    const content = document.getElementById('studentDetailContent');

    if (!student) {
        detailCard.classList.add('hidden');
        return;
    }

    const linkedinUrl = safeExternalUrl(student.linkedin_url);
    const placementUrl = safeExternalUrl(student.cbit_placement_url);
    const offers = student.offers || [];
    const initials = `${student.first_name?.[0] || ''}${student.last_name?.[0] || ''}`.toUpperCase();
    const offerCards = offers.length
        ? offers.map(offer => {
            const sourceUrl = safeExternalUrl(offer.source_url);
            return `
                <article class="profile-offer">
                    <strong>${escapeHtml(offer.company)}</strong>
                    <span>${escapeHtml(offer.academic_year)} offer</span>
                    ${sourceUrl ? `<a class="profile-source" href="${sourceUrl}" target="_blank" rel="noopener noreferrer">CBIT source</a>` : ''}
                </article>
            `;
        }).join('')
        : `<article class="profile-offer"><strong>${escapeHtml(student.company || 'No employer listed')}</strong><span>Placement record</span></article>`;
    content.innerHTML = `
        <div class="profile-summary">
            <div class="profile-avatar" aria-hidden="true">${escapeHtml(initials)}</div>
            <div>
                <h4>${escapeHtml(student.name)}</h4>
                <p class="profile-subtitle">${escapeHtml(student.branch || student.stream || 'Branch unavailable')} · Class of ${escapeHtml(student.year || student.passed_out_year || 'N/A')}</p>
            </div>
            <span class="profile-state">${escapeHtml(student.placement_status || 'Status unavailable')}</span>
        </div>
        <h4 class="profile-section-title">Verified employer offers · ${offers.length || (student.company ? 1 : 0)}</h4>
        <div class="profile-offers">${offerCards}</div>
        <div class="detail-grid">
            <div><strong>Current role:</strong> ${escapeHtml(student.job_title || 'Not listed by source')}</div>
            <div><strong>Package:</strong> ${formatSalary(student.salary)}</div>
            <div><strong>Location:</strong> ${escapeHtml(student.location || 'Not listed')}</div>
            <div><strong>Previous employer:</strong> ${escapeHtml(student.previous_company || 'Not listed')}</div>
            <div><strong>LinkedIn:</strong> ${linkedinUrl ? `<a href="${linkedinUrl}" target="_blank" rel="noopener noreferrer">Open profile</a>` : 'Not provided'}</div>
            <div><strong>CBIT profile source:</strong> ${placementUrl ? `<a href="${placementUrl}" target="_blank" rel="noopener noreferrer">Open source</a>` : 'Not provided'}</div>
        </div>
    `;

    detailCard.classList.remove('hidden');
}

function displayYearlyInsights(data) {
    const container = document.getElementById('yearlyInsights');
    if (!container) return;

    const years = data?.years || [];
    if (!years.length) {
        container.innerHTML = '<p class="muted">CBIT yearly data is unavailable right now.</p>';
        return;
    }

    container.innerHTML = years.map(year => {
        const rate = Math.max(0, Math.min(100, Number(year.placement_rate) || 0));
        const recruiters = year.top_recruiters?.length
            ? `<ol>${year.top_recruiters.map(recruiter => `<li><strong>${escapeHtml(recruiter.name)}</strong> · ${escapeHtml(recruiter.offers)} offers</li>`).join('')}</ol>`
            : '<p>Recruiter ranking not available in the named workbook.</p>';
        const recruiterSource = safeExternalUrl(year.recruiter_source_url);
        const packageSource = safeExternalUrl(year.package_source_url);
        const packageInfo = year.featured_package
            ? `<div class="yearly-package"><strong>Featured CTC:</strong> ₹${escapeHtml(year.featured_package.ctc_lpa)} LPA · ${escapeHtml(year.featured_package.company)}${packageSource ? ` <a href="${packageSource}" target="_blank" rel="noopener noreferrer">Source</a>` : ''}</div>`
            : '<div class="yearly-package">No year-specific package highlight found.</div>';
        return `
            <article class="yearly-card" data-year="${escapeHtml(year.academic_year)}">
                <header>
                    <h3>${escapeHtml(year.academic_year)}</h3>
                    <span class="yearly-rate">${rate}%</span>
                </header>
                <div class="yearly-meter" role="img" aria-label="${rate}% placement rate"><span style="width:${rate}%"></span></div>
                <p>${escapeHtml(year.placed)} placed of ${escapeHtml(year.students)} students</p>
                <strong>Top recruiters</strong>
                ${recruiters}
                ${recruiterSource ? `<footer><a href="${recruiterSource}" target="_blank" rel="noopener noreferrer">Workbook source</a></footer>` : ''}
                ${packageInfo}
            </article>
        `;
    }).join('');

    if (dashboardStats) updateStats(dashboardStats);
}

async function loadTopCompanies() {
    try {
        const companies = await fetchTopCompanies();
        const container = document.getElementById('topCompanies');
        
        if (companies.length === 0) {
            container.innerHTML = '<div class="loading">No company data</div>';
            return [];
        }

        container.innerHTML = companies.map(c => `
            <div class="company-item">
                <span class="company-name">${escapeHtml(c.name)}</span>
                <span class="company-count">${escapeHtml(c.count)} offers</span>
            </div>
        `).join('');
        return companies;
    } catch (error) {
        console.error('Error:', error);
        return [];
    }
}

function saveRecentSearch(value) {
    if (!value || value.trim().length < 2) return;
    const history = getRecentSearchHistory();
    const cleaned = value.trim();
    const next = [cleaned, ...history.filter(item => item.toLowerCase() !== cleaned.toLowerCase())].slice(0, 5);
    try {
        window.localStorage.setItem('alumniRecentSearches', JSON.stringify(next));
    } catch (error) {
        console.warn('Recent searches could not be saved:', error);
    }
    renderRecentSearches();
}

function renderRecentSearches() {
    const history = getRecentSearchHistory();
    const container = document.getElementById('recentSearches');
    if (!container) return;
    if (!history.length) {
        container.innerHTML = '<span class="muted">No recent searches</span>';
        return;
    }
    container.innerHTML = history.map(item => `
        <button class="recent-search" data-value="${escapeHtml(item)}">${escapeHtml(item)}</button>
    `).join('');

    container.querySelectorAll('.recent-search').forEach(button => {
        button.addEventListener('click', () => {
            const input = document.getElementById('filterName');
            if (input) {
                input.value = button.dataset.value;
                applyFilters();
            }
        });
    });
}

function applyFilters() {
    const nameValue = document.getElementById('filterName')?.value || '';
    const branchValue = document.getElementById('filterBranch')?.value || '';
    const placementYear = document.getElementById('filterPlacementYear')?.value || '';

    currentFilters = {
        name: nameValue.trim(),
        branch: branchValue,
        placement_year: placementYear
    };

    saveRecentSearch(nameValue);
    clearTimeout(suggestionTimer);
    suggestionRequestId += 1;
    document.getElementById('searchSuggestions')?.classList.add('hidden');
    document.getElementById('filterName')?.setAttribute('aria-expanded', 'false');
    document.querySelectorAll('.quick-chip').forEach(chip => chip.classList.remove('active'));
    currentPage = 1;
    loadPlacements();
}

function resetPlacementFilters() {
    document.getElementById('filterName').value = '';
    document.getElementById('filterBranch').value = '';
    document.getElementById('filterPlacementYear').value = '';
    document.getElementById('searchSuggestions').classList.add('hidden');
    document.getElementById('filterName').setAttribute('aria-expanded', 'false');
    document.getElementById('filterName').removeAttribute('aria-activedescendant');
    activeSuggestionIndex = -1;
    currentFilters = {};
    currentPage = 1;
    document.querySelectorAll('.quick-chip').forEach(chip => {
        chip.classList.toggle('active', chip.dataset.filter === 'all');
    });
    loadPlacements(1);
}

async function handleFileSelect() {
    const fileInput = document.getElementById('fileInput');
    const status = document.getElementById('importStatus');
    const file = fileInput?.files[0];
    if (!file) {
        status.textContent = 'Choose a CSV file to import.';
        return;
    }

    const formData = new FormData();
    formData.append('file', file);
    status.textContent = 'Importing CSV...';

    try {
        const result = await uploadFile(formData);
        await loadDashboard();
        const errorSummary = result.row_errors?.length
            ? ` First issue: row ${result.row_errors[0].row}, ${result.row_errors[0].error}.`
            : '';
        status.textContent = `Import complete: ${result.imported} added, ${result.updated} updated, ${result.skipped} skipped.${errorSummary}`;
        fileInput.value = '';
    } catch (error) {
        status.textContent = `Import failed: ${error.message}`;
    }
}

async function exportData(format) {
    try {
        window.location.href = `/api/export?format=${format}`;
    } catch (error) {
        alert('Error exporting: ' + error.message);
    }
}

async function initCharts(stats, companies) {
    if (typeof Chart !== 'function') {
        renderChartFallback(stats, companies);
        return;
    }

    const streamCtx = document.getElementById('streamChart');
    if (streamCtx) {
        const chartData = {
            labels: stats.branch_labels || [],
            datasets: [{
                label: 'Imported alumni',
                data: stats.branch_counts || [],
                backgroundColor: ['#1b7f79', '#e2a33a', '#4169a1', '#bf6955', '#65734a', '#956c9b']
            }]
        };
        if (chartsInstance.stream) {
            chartsInstance.stream.data = chartData;
            chartsInstance.stream.update();
        } else {
            chartsInstance.stream = new Chart(streamCtx, {
            type: 'bar',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true } }
            }
            });
        }
    }

    const companyCtx = document.getElementById('companyChart');
    if (companyCtx) {
        const chartData = {
            labels: companies.map(company => company.name),
            datasets: [{
                data: companies.map(company => company.count),
                backgroundColor: ['#1b7f79', '#e2a33a', '#4169a1', '#bf6955', '#65734a', '#956c9b', '#418c9e', '#c9853d', '#67748e', '#9c6b57']
            }]
        };
        if (chartsInstance.company) {
            chartsInstance.company.data = chartData;
            chartsInstance.company.update();
        } else {
            chartsInstance.company = new Chart(companyCtx, {
            type: 'doughnut',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                plugins: { legend: { position: 'bottom' } }
            }
            });
        }
    }

    const trendCtx = document.getElementById('trendChart');
    if (trendCtx) {
        const yearly = stats.yearly_data || [];
        const chartData = {
            labels: yearly.map(item => item.academic_year),
            datasets: [
                {
                    label: 'Cohort students',
                    data: yearly.map(item => item.students),
                    borderColor: '#e2a33a',
                    backgroundColor: 'rgba(226, 163, 58, 0.12)',
                    borderWidth: 2,
                    tension: 0.25
                },
                {
                    label: 'Placed students',
                    data: yearly.map(item => item.placed),
                    borderColor: '#1b7f79',
                    backgroundColor: 'rgba(27, 127, 121, 0.12)',
                    borderWidth: 2,
                    tension: 0.25
                }
            ]
        };
        if (chartsInstance.trend) {
            chartsInstance.trend.data = chartData;
            chartsInstance.trend.update();
        } else {
            chartsInstance.trend = new Chart(trendCtx, {
            type: 'line',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                scales: { y: { beginAtZero: true } }
            }
            });
        }
    }
}

function renderChartFallback(stats, companies) {
    const chartRows = [
        {
            id: 'streamChart',
            title: 'Students by Branch',
            entries: (stats.branch_labels || []).map((label, index) => ({ label, value: Number(stats.branch_counts?.[index] || 0) })).sort((a, b) => b.value - a.value).slice(0, 6)
        },
        {
            id: 'companyChart',
            title: 'Offers by Company',
            entries: (companies || []).slice(0, 6).map(company => ({ label: company.name, value: company.count }))
        },
        {
            id: 'trendChart',
            title: 'Official Placement Trend',
            entries: (stats.yearly_data || []).map(year => ({
                label: year.academic_year,
                value: Number(year.placement_rate || 0),
                detail: `${year.placed} / ${year.students} placed`
            }))
        }
    ];

    chartRows.forEach(chart => {
        const canvas = document.getElementById(chart.id);
        const card = canvas?.closest('.chart-card');
        if (!canvas || !card) return;
        canvas.hidden = true;
        let fallback = card.querySelector('.chart-fallback');
        if (!fallback) {
            fallback = document.createElement('div');
            fallback.className = 'chart-fallback';
            canvas.insertAdjacentElement('afterend', fallback);
        }
        const maximum = Math.max(...chart.entries.map(entry => entry.value), 1);
        fallback.innerHTML = chart.entries.map(entry => `
            <div class="chart-fallback-row">
                <div class="chart-fallback-label"><span>${escapeHtml(entry.label)}</span><strong>${escapeHtml(entry.detail || entry.value)}</strong></div>
                <div class="chart-fallback-track"><span style="width:${Math.max(3, entry.value / maximum * 100)}%"></span></div>
            </div>
        `).join('') || '<p class="muted">Chart data is unavailable.</p>';
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const hashTab = window.location.hash.slice(1);
    switchTab(document.getElementById(hashTab)?.classList.contains('section') ? hashTab : 'overview');
    window.addEventListener('hashchange', () => {
        const requestedTab = window.location.hash.slice(1);
        if (document.getElementById(requestedTab)?.classList.contains('section')) switchTab(requestedTab);
    });

    renderRecentSearches();

    document.getElementById('filterName')?.addEventListener('input', (event) => {
        clearTimeout(suggestionTimer);
        const query = event.target.value;
        const container = document.getElementById('searchSuggestions');
        const requestId = ++suggestionRequestId;
        if (query.trim().length < 2) {
            container.innerHTML = '';
            container.classList.add('hidden');
            return;
        }
        container.innerHTML = '<div class="suggestion-message">Searching...</div>';
        container.classList.remove('hidden');
        event.target.setAttribute('aria-expanded', 'true');
        suggestionTimer = setTimeout(() => fetchSuggestions(query, requestId), 180);
    });

    document.getElementById('filterName')?.addEventListener('keydown', event => {
        if (event.key === 'ArrowDown') {
            if (moveSuggestionSelection(1)) event.preventDefault();
        } else if (event.key === 'ArrowUp') {
            if (moveSuggestionSelection(-1)) event.preventDefault();
        } else if (event.key === 'Enter') {
            event.preventDefault();
            const selected = document.querySelector('#searchSuggestions .suggestion-item.is-active');
            if (selected) {
                selectSuggestion(selected);
            } else {
                document.getElementById('searchSuggestions')?.classList.add('hidden');
                applyFilters();
            }
        } else if (event.key === 'Escape') {
                clearTimeout(suggestionTimer);
                suggestionRequestId += 1;
                document.getElementById('searchSuggestions')?.classList.add('hidden');
                document.getElementById('filterName')?.setAttribute('aria-expanded', 'false');
                document.getElementById('filterName')?.removeAttribute('aria-activedescendant');
                activeSuggestionIndex = -1;
        }
    });

    document.addEventListener('click', (event) => {
        const suggestions = document.getElementById('searchSuggestions');
        if (suggestions && !event.target.closest('.search-shell')) {
            suggestions.classList.add('hidden');
            document.getElementById('filterName')?.setAttribute('aria-expanded', 'false');
        }
    });

    document.querySelectorAll('.quick-chip').forEach(button => {
        button.addEventListener('click', () => {
            const filter = button.dataset.filter;
            const input = document.getElementById('filterName');
            const branch = document.getElementById('filterBranch');
            const year = document.getElementById('filterPlacementYear');

            document.querySelectorAll('.quick-chip').forEach(chip => chip.classList.remove('active'));
            button.classList.add('active');
            input.value = '';
            branch.value = '';
            year.value = '';

            if (filter === 'placed') {
                currentFilters = { placement: 'Placed' };
            } else if (filter === 'higher') {
                currentFilters = { placement: 'Higher Studies' };
            } else {
                currentFilters = {};
            }

            currentPage = 1;
            document.querySelectorAll('.quick-chip').forEach(chip => chip.classList.remove('active'));
            button.classList.add('active');
            currentPage = 1;
            loadPlacements(currentPage);
        });
    });

    document.querySelectorAll('.chart-expand').forEach(button => {
        button.addEventListener('click', () => openChartModal(button.dataset.chart, button));
    });
    document.getElementById('closeChartModal')?.addEventListener('click', closeChartModal);
    document.getElementById('chartModal')?.addEventListener('click', event => {
        if (event.target.id === 'chartModal') closeChartModal();
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && !document.getElementById('chartModal')?.classList.contains('hidden')) {
            closeChartModal();
        }
    });

    if (document.getElementById('placementTable')) {
        loadDashboard();
    }
});

function openChartModal(chartKey, trigger) {
    const modal = document.getElementById('chartModal');
    const body = document.getElementById('chartModalBody');
    const sourceCanvas = document.getElementById(`${chartKey}Chart`);
    const chartCard = sourceCanvas?.closest('.chart-card');
    if (!modal || !body || !chartCard) return;

    chartModalReturnFocus = trigger;
    document.getElementById('chartModalTitle').textContent = chartCard.querySelector('h3')?.textContent || 'Chart details';
    body.replaceChildren();
    modal.classList.remove('hidden');
    document.body.classList.add('modal-open');

    const sourceChart = chartsInstance[chartKey];
    if (sourceChart && typeof Chart === 'function') {
        const canvas = document.createElement('canvas');
        canvas.setAttribute('aria-label', `${chartCard.querySelector('h3')?.textContent || 'Expanded chart'} data visualization`);
        body.append(canvas);
        const type = sourceChart.config.type;
        expandedChart = new Chart(canvas, {
            type,
            data: JSON.parse(JSON.stringify(sourceChart.data)),
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                plugins: { legend: { display: type === 'doughnut', position: 'bottom' } },
                scales: type === 'doughnut' ? {} : { y: { beginAtZero: true } }
            }
        });
    } else {
        const fallback = chartCard.querySelector('.chart-fallback');
        if (fallback) body.append(fallback.cloneNode(true));
        else body.innerHTML = '<p class="muted">Chart details are unavailable in this browser.</p>';
    }
    document.getElementById('closeChartModal').focus();
}

function closeChartModal() {
    const modal = document.getElementById('chartModal');
    if (!modal) return;
    expandedChart?.destroy();
    expandedChart = null;
    modal.classList.add('hidden');
    document.body.classList.remove('modal-open');
    chartModalReturnFocus?.focus();
}