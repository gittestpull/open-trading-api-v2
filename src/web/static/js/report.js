
async function loadLatestReports() {
    try {
        const res = await fetch('/api/reports/latest');
        const data = await res.json();
        renderReports(data);
    } catch (e) { console.error(e); }
}

async function searchReports() {
    const keyword = document.getElementById('reportSearchInput').value.trim();
    if (!keyword) return loadLatestReports();
    
    try {
        const res = await fetch(`/api/reports/search?keyword=${encodeURIComponent(keyword)}`);
        const data = await res.json();
        renderReports(data);
    } catch (e) { 
        document.getElementById('reportList').innerHTML = `<div class="text-center text-accent-red">Search failed: ${e.message}</div>`;
    }
}

function renderReports(reports) {
    const container = document.getElementById('reportList');
    if (!reports || !reports.length) {
        container.innerHTML = '<div class="text-center text-gray-600 py-8">No reports found</div>';
        return;
    }
    
    container.innerHTML = reports.map(r => `
        <div class="glass p-5 rounded-lg border border-dark-600 hover:border-accent-blue transition">
            <div class="flex justify-between items-start mb-2">
                <div>
                    <h3 class="text-lg font-bold text-white mb-1">
                        ${r.link ? `<a href="${r.link}" target="_blank" class="hover:text-accent-blue">${r.title}</a>` : r.title}
                    </h3>
                    <div class="text-xs text-gray-500 flex gap-2">
                        <span>${r.source}</span>
                        <span>•</span>
                        <span>${r.analyst}</span>
                        <span>•</span>
                        <span>${r.date}</span>
                    </div>
                </div>
                ${r.opinion ? `<span class="px-2 py-1 text-xs rounded bg-dark-700 text-accent-yellow border border-dark-600">${r.opinion}</span>` : ''}
            </div>
            
            <p class="text-sm text-gray-400 mb-3">${r.summary || ''}</p>
            
            ${r.related_stocks && r.related_stocks.length ? `
            <div class="flex flex-wrap gap-2 mt-3 pt-3 border-t border-dark-700">
                <span class="text-xs text-gray-500 py-1">Related:</span>
                ${r.related_stocks.map(s => `
                    <button onclick="analyzeStock('${s}')" class="px-2 py-1 text-xs bg-dark-800 hover:bg-dark-700 text-accent-blue rounded border border-dark-600 transition">
                        ${s}
                    </button>
                `).join('')}
            </div>
            ` : ''}
        </div>
    `).join('');
}
