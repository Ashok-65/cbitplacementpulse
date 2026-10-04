function getApiBaseUrl(locationInfo = window.location) {
    const override = new URLSearchParams(locationInfo.search).get('apiBase');
    if (override) return override.replace(/\/$/, '');

    const localHosts = ['localhost', '127.0.0.1', '::1'];
    const localPreview = localHosts.includes(locationInfo.hostname) && locationInfo.port && locationInfo.port !== '5000';
    if (locationInfo.protocol === 'file:' || localPreview) {
        return 'http://127.0.0.1:5000/api';
    }

    return `${locationInfo.origin}/api`;
}

const API_BASE_URL = getApiBaseUrl();

async function fetchAlumni(filters = {}, paging = {}) {
    const params = new URLSearchParams({ ...filters, ...paging });
    const response = await fetch(`${API_BASE_URL}/alumni?${params}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Unable to load alumni records');
    return data;
}

async function fetchStatistics() {
    try {
        const response = await fetch(`${API_BASE_URL}/statistics`);
        if (!response.ok) throw new Error('Failed to fetch');
        return await response.json();
    } catch (error) {
        console.error('Error:', error);
        return {
            total_students: 0,
            placed: 0,
            higher_studies: 0,
            core_mechanical: 0,
            it: 0,
            avg_salary: 0,
            placement_rate: 0,
            api_error: error.message
        };
    }
}

async function uploadFile(formData) {
    try {
        const response = await fetch(`${API_BASE_URL}/upload`, {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Upload failed');
        return data;
    } catch (error) {
        console.error('Error:', error);
        throw error;
    }
}

async function fetchTopCompanies() {
    try {
        const response = await fetch(`${API_BASE_URL}/top-companies`);
        if (!response.ok) throw new Error('Failed to fetch');
        return await response.json();
    } catch (error) {
        console.error('Error:', error);
        return [];
    }
}

async function fetchYearlyInsights() {
    try {
        const response = await fetch(`${API_BASE_URL}/yearly-insights`);
        if (!response.ok) throw new Error('Failed to fetch yearly insights');
        return await response.json();
    } catch (error) {
        console.error('Error:', error);
        return { years: [] };
    }
}

async function seedSampleData() {
    try {
        const response = await fetch(`${API_BASE_URL}/seed`, {
            method: 'POST'
        });
        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.error || 'Unable to load sample data');
        }
        const data = await response.json();
        await loadDashboard();
        return data;
    } catch (error) {
        console.error('Error loading sample data:', error);
        throw error;
    }
}