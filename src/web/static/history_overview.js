    async function loadHistoryOverview() {
        const tbody = document.getElementById('histOverviewBody');
        try {
            const res = await fetch('/api/history/overview');
            const data = await res.json();
            
            if (!data.summary || !data.summary.length) {
                tbody.innerHTML = '<tr><td colspan="6" class="px-4 py-8 text-center text-gray-600">No collected data yet.</td></tr>';
                return;
            }

            tbody.innerHTML = data.summary.map(item => `
                <tr class="hover:bg-dark-700 transition-colors">
                    <td class="px-4 py-2 font-mono text-accent-blue">${item.ticker}</td>
                    <td class="px-4 py-2 text-white font-medium">${item.name}</td>
                    <td class="px-4 py-2">
                        <span class="px-2 py-0.5 rounded text-xs ${
                            item.timeframe === '1m' ? 'bg-purple-900/50 text-purple-200' : 
                            item.timeframe === 'D' ? 'bg-blue-900/50 text-blue-200' : 'bg-gray-700 text-gray-300'
                        }">${item.timeframe === '1m' ? '1 Min' : item.timeframe === 'D' ? 'Daily' : item.timeframe === 'W' ? 'Weekly' : 'Monthly'}</span>
                    </td>
                    <td class="px-4 py-2 text-right text-gray-300">${item.count.toLocaleString()}</td>
                    <td class="px-4 py-2 text-right text-xs text-gray-500">${item.start_date.substring(0,16)} ~ ${item.end_date.substring(0,16)}</td>
                    <td class="px-4 py-2 text-center">
                        <button onclick="openHistoryViewer('${item.ticker}', '${item.name}')" class="px-2 py-1 text-xs bg-dark-600 hover:bg-accent-blue hover:text-white rounded transition">View</button>
                    </td>
                </tr>
            `).join('');
        } catch (e) {
            console.error(e);
            tbody.innerHTML = '<tr><td colspan="6" class="px-4 py-8 text-center text-red-500">Failed to load overview</td></tr>';
        }
    }

    // Load overview when switching to History tab
    const originalShowTab = window.showTab; // If not already hooked
    // We can just add it to the existing click handler logic in index.html if possible, 
    // or rely on a global hook.
    // For now, let's call it once at startup if we start on the tab, or hook into the tab button click.
