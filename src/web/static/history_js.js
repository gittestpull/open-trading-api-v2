        // WebSocket for Collection Logs
        let historyLogWs = null;
        let historyLogConnected = false;

        function connectHistoryLogStream() {
            if (historyLogWs) return;
            
            const container = document.getElementById('historyLogs');
            const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            historyLogWs = new WebSocket(`${wsProtocol}//${location.host}/ws/collection-logs`);
            
            historyLogWs.onopen = () => {
                historyLogConnected = true;
                const line = document.createElement('div');
                line.className = 'text-accent-green py-0.5';
                line.textContent = 'Log stream connected...';
                
                if (container.querySelector('.text-center')) {
                    container.innerHTML = '';
                }
                container.appendChild(line);
            };
            
            historyLogWs.onmessage = e => {
                try {
                    const log = JSON.parse(e.data);
                    // Filter only HumanIndex or relevant logs if needed, but showing all is fine for now
                    if (log.message.includes('[HumanIndex]')) {
                        const line = document.createElement('div');
                        line.className = `py-0.5 ${log.level === 'ERROR' ? 'text-accent-red' : 'text-gray-300'}`;
                        line.textContent = `[${log.timestamp}] ${log.message}`;
                        
                        container.appendChild(line);
                        container.scrollTop = container.scrollHeight;
                    }
                } catch (err) {
                    console.error(err);
                }
            };
            
            historyLogWs.onclose = () => {
                historyLogConnected = false;
                historyLogWs = null;
            };
        }

        document.getElementById('btnClearHistoryLogs').addEventListener('click', () => {
            document.getElementById('historyLogs').innerHTML = '<div class="text-gray-600 italic text-center py-10">Logs will appear here...</div>';
        });

        // Initialize connection when panel is shown (or just on load)
        connectHistoryLogStream();

        let historyLogWs = null;
        let historyLogConnected = false;

        function connectHistoryLogStream() {
            if (historyLogWs) return;
            
            const container = document.getElementById('historyLogs');
            const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            historyLogWs = new WebSocket(`${wsProtocol}//${location.host}/ws/collection-logs`);
            
            historyLogWs.onopen = () => {
                historyLogConnected = true;
                const line = document.createElement('div');
                line.className = 'text-accent-green py-0.5';
                line.textContent = 'Log stream connected...';
                
                if (container.querySelector('.text-center')) {
                    container.innerHTML = '';
                }
                container.appendChild(line);
            };
            
            historyLogWs.onmessage = e => {
                try {
                    const log = JSON.parse(e.data);
                    if (log.message.includes('[HumanIndex]')) {
                        const line = document.createElement('div');
                        line.className = `py-0.5 ${log.level === 'ERROR' ? 'text-accent-red' : 'text-gray-300'}`;
                        line.textContent = `[${log.timestamp}] ${log.message}`;
                        
                        container.appendChild(line);
                        container.scrollTop = container.scrollHeight;
                    }
                } catch (err) {
                    console.error(err);
                }
            };
            
            historyLogWs.onclose = () => {
                historyLogConnected = false;
                historyLogWs = null;
            };
        }

        document.getElementById('btnClearHistoryLogs').addEventListener('click', () => {
            document.getElementById('historyLogs').innerHTML = '<div class="text-gray-600 italic text-center py-10">Logs will appear here...</div>';
        });

        connectHistoryLogStream();

        document.getElementById('btnCollectHuman').addEventListener('click', async () => {
            const btn = document.getElementById('btnCollectHuman');
            const originalText = document.getElementById('humanBtnText').textContent;
            
            const ticker = document.getElementById('histTicker').value;
            const days = document.getElementById('histHumanDays').value || 30;
            
            if (!ticker) {
                alert('Please enter a ticker');
                return;
            }
            
            try {
                btn.disabled = true;
                document.getElementById('humanBtnText').textContent = 'Collecting...';
                
                const res = await fetch(`/api/human-index/${ticker}/collect?days=${days}`, {
                    method: 'POST'
                });
                
                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || 'Collection failed');
                }
                
                const result = await res.json();
                
                let msg = `Collection ${result.status}`;
                if (result.details) {
                    const updates = result.details.history_updates || 0;
                    msg += `\nUpdated ${updates} historical records.`;
                    
                    if (result.details.youtube) {
                        msg += `\nYouTube: ${result.details.youtube.details ? Object.keys(result.details.youtube.details).length : 0} videos`;
                    }
                    if (result.details.naver) {
                        msg += `\nNaver: ${result.details.naver.details ? Object.keys(result.details.naver.details).length : 0} days`;
                    }
                }
                
                alert(msg);
                
            } catch (e) {
                alert(e.message);
            } finally {
                btn.disabled = false;
                document.getElementById('humanBtnText').textContent = originalText;
            }
        });

        // History Tool Logic
        document.getElementById('historyForm').addEventListener('submit', async e => {
            e.preventDefault();
            const btn = e.target.querySelector('button');
            const originalText = document.getElementById('histBtnText').textContent;
            
            const ticker = document.getElementById('histTicker').value;
            const start = document.getElementById('histStart').value;
            const end = document.getElementById('histEnd').value;
            const timeframe = document.querySelector('input[name="histTimeframe"]:checked').value;

            if (!ticker || !start || !end) {
                alert('Please fill in all fields');
                return;
            }

            try {
                btn.disabled = true;
                document.getElementById('histBtnText').textContent = 'Collecting...';
                
                const res = await fetch('/api/history/collect', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ ticker, start_date: start, end_date: end, timeframe })
                });
                
                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || 'Collection failed');
                }
                
                const result = await res.json();
                alert(`Collected ${result.count} records for ${result.ticker}`);
                loadHistoryData(result.ticker, timeframe);
                
            } catch (e) {
                alert(e.message);
            } finally {
                btn.disabled = false;
                document.getElementById('histBtnText').textContent = originalText;
            }
        });

        async function loadHistoryData(ticker, timeframe) {
            try {
                const res = await fetch(`/api/history/${ticker}?timeframe=${timeframe}&limit=100`);
                const data = await res.json();
                renderHistoryTable(data.history);
                document.getElementById('histCount').textContent = `${data.count} records`;
            } catch (e) {
                console.error(e);
            }
        }

        function renderHistoryTable(rows) {
            const tbody = document.getElementById('histTableBody');
            if (!rows || !rows.length) {
                tbody.innerHTML = '<tr><td colspan="6" class="px-4 py-8 text-center text-gray-600">No data found</td></tr>';
                return;
            }
            tbody.innerHTML = rows.map(r => `
                <tr class="hover:bg-dark-700 transition-colors">
                    <td class="px-4 py-2 font-mono text-gray-400">${r.datetime}</td>
                    <td class="px-4 py-2 text-right">${r.open.toLocaleString()}</td>
                    <td class="px-4 py-2 text-right">${r.high.toLocaleString()}</td>
                    <td class="px-4 py-2 text-right">${r.low.toLocaleString()}</td>
                    <td class="px-4 py-2 text-right font-medium ${r.close >= r.open ? 'text-accent-red' : 'text-accent-blue'}">${r.close.toLocaleString()}</td>
                    <td class="px-4 py-2 text-right text-gray-500">${r.volume.toLocaleString()}</td>
                </tr>
            `).join('');
        }
