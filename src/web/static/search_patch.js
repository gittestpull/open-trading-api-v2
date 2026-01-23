        // Override renderSearchResults to add History Button and Fix Credit/Short Data
        function renderScreenerResults(stocks) {
            const tbody = document.getElementById('screenerResults');
            if (!stocks || !stocks.length) { 
                tbody.innerHTML = '<tr><td colspan="11" class="px-4 py-8 text-center text-gray-600" data-i18n="no_results">No results</td></tr>'; 
                applyTranslations(); 
                return; 
            }
            const unit = t('unit_100m');
            tbody.innerHTML = stocks.map(s => `
                <tr class="hover:bg-dark-700 group">
                    <td class="px-4 py-3 text-accent-blue font-medium cursor-pointer hover:underline" onclick="selectStock('${s.ticker}')">${s.ticker}</td>
                    <td class="px-4 py-3 font-medium text-white">${s.name}</td>
                    <td class="px-4 py-3 text-right font-mono">${(s.close || 0).toLocaleString()}</td>
                    <td class="px-4 py-3 text-right font-mono ${(s.change_rate || 0) >= 0 ? 'text-accent-green' : 'text-accent-red'}">${(s.change_rate || 0).toFixed(2)}%</td>
                    <td class="px-4 py-3 text-right font-mono text-gray-400">${s.per ? s.per.toFixed(1) : '-'}</td>
                    <td class="px-4 py-3 text-right font-mono text-gray-400">${s.pbr ? s.pbr.toFixed(2) : '-'}</td>
                    <td class="px-4 py-3 text-right font-mono ${(s.foreign_net || 0) >= 0 ? 'text-accent-green' : 'text-accent-red'}">${s.foreign_net_amt ? (s.foreign_net_amt).toFixed(1) + unit : '-'}</td>
                    <td class="px-4 py-3 text-right font-mono ${(s.inst_net || 0) >= 0 ? 'text-accent-green' : 'text-accent-red'}">${s.inst_net_amt ? (s.inst_net_amt).toFixed(1) + unit : '-'}</td>
                    <td class="px-4 py-3 text-right font-mono text-gray-400">${s.short_ratio !== undefined && s.short_ratio !== null ? s.short_ratio.toFixed(2) + '%' : '-'}</td>
                    <td class="px-4 py-3 text-right font-mono text-gray-400">${s.credit_ratio !== undefined && s.credit_ratio !== null ? s.credit_ratio.toFixed(2) + '%' : '-'}</td>
                    <td class="px-4 py-3 text-center flex justify-center gap-2 opacity-80 group-hover:opacity-100 transition-opacity">
                        <button onclick="analyzeStock('${s.ticker}')" class="px-2 py-1 text-xs bg-dark-700 hover:bg-accent-purple hover:text-white text-gray-300 rounded transition" title="Analysis">📊</button>
                        <button onclick="openHistoryViewer('${s.ticker}', '${s.name}')" class="px-2 py-1 text-xs bg-dark-700 hover:bg-accent-blue hover:text-white text-gray-300 rounded transition" title="History">📅</button>
                    </td>
                </tr>
            `).join('');
            // Re-apply translations for static elements if any (mostly dynamic here)
        }
