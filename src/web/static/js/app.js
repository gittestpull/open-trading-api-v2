let ws = null;
let currentTab = 'scalper';
let currentLang = localStorage.getItem('lang') || 'en';

const translations = {
    en: {
        subtitle: 'AI-Powered Investment Analysis Platform',
        tab_scalper: 'Scalper', tab_screener: 'Screener', tab_deepdive: 'Deep Dive',
        tab_human: 'Human Index', tab_backtest: 'Backtest', tab_global: 'Global', tab_sector: 'Sector',
        tab_journal: 'Journal', tab_simulator: 'Simulator', tab_admin: 'Admin', tab_history: 'Data Tool',
        new_scalper: 'New Scalper', ticker: 'Ticker', budget: 'Budget (₩)',
        target: 'Target (%)', start_scalper: 'Start Scalper',
        running_processes: 'Running Processes', saved_states: 'Saved States',
        live_logs: 'Live Logs', select_ticker: 'Select ticker...',
        select_process: 'Select a process to view logs',
        no_running: 'No running processes', no_saved: 'No saved states',
        filter_stocks: 'Filter Stocks', search: 'Search', analyze: 'Analyze',
        ai_report: 'AI Report', stock_analysis: 'Stock Analysis',
        key_metrics: 'Key Metrics', enter_ticker: 'Enter a ticker to see analysis',
        fomo_alerts: 'FOMO Alerts (Overheated)', bottom_signals: 'Bottom Signals (Opportunity)',
        refresh: 'Refresh', individual_human: 'Individual Stock Human Index',
        check: 'Check', attention_score: 'Attention Score', fomo_level: 'FOMO Level',
        crowd_sentiment: 'Crowd Sentiment', run_backtest: 'Run Backtest',
        start_date: 'Start Date', end_date: 'End Date', strategy: 'Strategy',
        initial_capital: 'Initial Capital', total_return: 'Total Return',
        win_rate: 'Win Rate', max_drawdown: 'Max Drawdown', sharpe_ratio: 'Sharpe Ratio',
        past_results: 'Past Results', commodities_bonds: 'Commodities & Bonds',
        analysis: 'Analysis', market_sentiment: 'Market Sentiment',
        add_trade: 'Add Trade Entry', statistics: 'Statistics', trade_history: 'Trade History',
        total_trades: 'Total Trades', total_pnl: 'Total P&L', best_trade: 'Best Trade',
        worst_trade: 'Worst Trade', total_value: 'Total Value', return_pct: 'Return %',
        trade: 'Trade', positions: 'Positions', recent_trades: 'Recent Trades',
        reset_simulator: 'Reset Simulator', data_collection: 'Data Collection',
        load_stocks: 'Load Stocks', collect_data: 'Collect Data',
        start_scheduler: 'Start Scheduler', stop_scheduler: 'Stop Scheduler',
        collect_global: 'Collect Global Market', test_telegram: 'Test Telegram',
        collection_logs: 'Collection Logs', db_stats: 'Database Stats',
        total_stocks: 'Total Stocks', scheduler: 'Scheduler',
        foreign_net: 'Foreign Net ≥', per_max: 'PER ≤', pbr_max: 'PBR ≤',
        market: 'Market', sort_by: 'Sort By', price: 'Price', change: 'Change',
        foreign: 'Foreign', action: 'Action', short_ratio: 'Short(%)', credit_ratio: 'Credit(%)', enter_ticker_placeholder: 'Enter ticker or company name...',
        no_positions: 'No positions', no_trades: 'No trades yet',
        no_entries: 'No entries yet', no_results: 'No results', no_alerts: 'No FOMO alerts',
        no_signals: 'No bottom signals', loading: 'Loading...',
        click_refresh: 'Click Refresh to load', no_past_results: 'No past results',
        all: 'All', market_cap: 'Market Cap', change_pct: 'Change %', volume: 'Volume',
        foreign_net_opt: 'Foreign Net', name: 'Name', enter_filters: 'Enter filters and click Search',
        ai_analysis_report: 'AI Analysis Report', run_backtest_btn: 'Run Backtest',
        backtest_result: 'Backtest Result', vix_fear: 'VIX (Fear)',
        market_data_refresh: 'Market data will appear after refresh',
        buy: 'BUY', sell: 'SELL', qty: 'Qty', thesis: 'Thesis (optional)', pnl: 'P&L', add: 'Add',
        qty_optional: 'Qty (optional)', no_collection_logs: 'No collection logs', unit_100m: '00M',
        edit_trade: 'Edit Trade Entry', search_stock: 'Search Stock',
        search_stock_placeholder: 'Enter name or code...', enter_search_term: 'Enter search term...',
        cancel: 'Cancel', save: 'Save', delete_confirm: 'Delete this entry?', side: 'Side',
        realtime_logs: 'Real-time Logs', connect: 'Connect', disconnect: 'Disconnect',
        clear: 'Clear', click_connect: 'Click Connect to start streaming logs',
        investor_trend_chart: 'Foreign/Institutional Trend', investor_trend_table: 'Daily Details',
        date: 'Date', retail: 'Retail', institution: 'Institution',
        human_index_trend: 'Human Index Trend (30 days)',
        youtube_trend: 'YouTube Trend', naver_trend: 'Naver Trend',
        login: 'Login', login_title: 'Welcome Back', username: 'Username', username_placeholder: 'Enter your username',
        password: 'Password', password_placeholder: 'Enter your password', forgot_password: 'Forgot?',
        login_btn: 'Sign In', or_continue: 'Or continue with', no_account: "Don't have an account?", signup: 'Sign up',
    },
    ko: {
        subtitle: 'AI 기반 투자 분석 플랫폼',
        tab_scalper: '스캘퍼', tab_screener: '종목검색', tab_deepdive: '딥다이브',
        tab_human: '인간지표', tab_backtest: '백테스트', tab_global: '글로벌', tab_sector: '섹터',
        tab_journal: '매매일지', tab_simulator: '시뮬레이터', tab_admin: '관리자', tab_history: '데이터 도구',
        new_scalper: '새 스캘퍼', ticker: '종목코드', budget: '예산 (원)',
        target: '목표 (%)', start_scalper: '스캘퍼 시작',
        running_processes: '실행 중', saved_states: '저장된 상태',
        live_logs: '실시간 로그', select_ticker: '종목 선택...',
        select_process: '로그를 볼 프로세스를 선택하세요',
        no_running: '실행 중인 프로세스 없음', no_saved: '저장된 상태 없음',
        filter_stocks: '종목 필터', search: '검색', analyze: '분석',
        ai_report: 'AI 리포트', stock_analysis: '종목 분석',
        key_metrics: '핵심 지표', enter_ticker: '분석할 종목을 입력하세요',
        fomo_alerts: 'FOMO 경보 (과열)', bottom_signals: '바닥 신호 (기회)',
        refresh: '새로고침', individual_human: '개별 종목 인간지표',
        check: '확인', attention_score: '관심도', fomo_level: 'FOMO 지수',
        crowd_sentiment: '군중 감성', run_backtest: '백테스트 실행',
        start_date: '시작일', end_date: '종료일', strategy: '전략',
        initial_capital: '초기 자본', total_return: '총 수익률',
        win_rate: '승률', max_drawdown: '최대 낙폭', sharpe_ratio: '샤프 비율',
        past_results: '과거 결과', commodities_bonds: '원자재 & 채권',
        analysis: '분석', market_sentiment: '시장 심리',
        add_trade: '거래 기록 추가', statistics: '통계', trade_history: '거래 내역',
        total_trades: '총 거래', total_pnl: '총 손익', best_trade: '최고 수익',
        worst_trade: '최대 손실', total_value: '총 가치', return_pct: '수익률 %',
        trade: '거래', positions: '포지션', recent_trades: '최근 거래',
        reset_simulator: '시뮬레이터 초기화', data_collection: '데이터 수집',
        load_stocks: '종목 로드', collect_data: '데이터 수집',
        start_scheduler: '스케줄러 시작', stop_scheduler: '스케줄러 중지',
        collect_global: '글로벌 시장 수집', test_telegram: '텔레그램 테스트',
        collection_logs: '수집 로그', db_stats: '데이터베이스 현황',
        total_stocks: '전체 종목', scheduler: '스케줄러',
        foreign_net: '외인순매수 ≥', per_max: 'PER ≤', pbr_max: 'PBR ≤',
        market: '시장', sort_by: '정렬', price: '가격', change: '등락률',
        foreign: '외인', action: '액션', short_ratio: '공매도(%)', credit_ratio: '신용(%)', enter_ticker_placeholder: '종목코드 또는 회사명 입력...',
        no_positions: '포지션 없음', no_trades: '거래 내역 없음',
        no_entries: '기록 없음', no_results: '결과 없음', no_alerts: 'FOMO 경보 없음',
        no_signals: '바닥 신호 없음', loading: '로딩 중...',
        click_refresh: '새로고침을 클릭하세요', no_past_results: '과거 결과 없음',
        all: '전체', market_cap: '시가총액', change_pct: '등락률 %', volume: '거래량',
        foreign_net_opt: '외인순매수', name: '종목명', enter_filters: '필터를 입력하고 검색을 클릭하세요',
        ai_analysis_report: 'AI 분석 리포트', run_backtest_btn: '백테스트 실행',
        backtest_result: '백테스트 결과', vix_fear: 'VIX (공포지수)',
        market_data_refresh: '새로고침 후 시장 데이터가 표시됩니다',
        buy: '매수', sell: '매도', qty: '수량', thesis: '투자 논거 (선택)', pnl: '손익', add: '추가',
        qty_optional: '수량 (선택)', no_collection_logs: '수집 로그 없음', unit_100m: '억',
        edit_trade: '거래 기록 수정', search_stock: '종목 검색',
        search_stock_placeholder: '종목명 또는 코드 입력...', enter_search_term: '검색어를 입력하세요...',
        cancel: '취소', save: '저장', delete_confirm: '이 항목을 삭제하시겠습니까?', side: '방향',
        realtime_logs: '실시간 로그', connect: '연결', disconnect: '연결 해제',
        clear: '지우기', click_connect: '연결을 클릭하여 로그 스트리밍 시작',
        investor_trend_chart: '외인/기관 동향', investor_trend_table: '일별 상세',
        date: '날짜', retail: '개인', institution: '기관',
        human_index_trend: '인간지표 추이 (30일)',
        youtube_trend: '유튜브 추이', naver_trend: '네이버 추이',
        login: '로그인', login_title: '환영합니다', username: '아이디', username_placeholder: '아이디를 입력하세요',
        password: '비밀번호', password_placeholder: '비밀번호를 입력하세요', forgot_password: '비밀번호 찾기',
        login_btn: '로그인', or_continue: '또는', no_account: '계정이 없으신가요?', signup: '회원가입',
    }
};

function t(key) {
    return translations[currentLang][key] || translations['en'][key] || key;
}

function applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        el.textContent = t(key);
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        el.placeholder = t(key);
    });
    document.getElementById('langLabel').textContent = currentLang === 'ko' ? 'English' : '한국어';
}

function toggleLanguage() {
    currentLang = currentLang === 'en' ? 'ko' : 'en';
    localStorage.setItem('lang', currentLang);
    applyTranslations();
}

function showTab(tab) {
    document.querySelectorAll('[id^="panel-"]').forEach(p => p.classList.add('hidden'));
    document.querySelectorAll('[id^="tab-"]').forEach(t => { t.classList.remove('tab-active'); t.classList.add('text-gray-500'); });
    document.getElementById(`panel-${tab}`).classList.remove('hidden');
    document.getElementById(`tab-${tab}`).classList.add('tab-active');
    document.getElementById(`tab-${tab}`).classList.remove('text-gray-500');
    currentTab = tab;
    if (tab === 'screener') loadScreenerData();
    if (tab === 'admin') loadAdminData();
    if (tab === 'global') loadGlobalMarket();
    if (tab === 'sector') loadSavedSectors();
    if (tab === 'journal') { loadJournalEntries(); loadJournalStats(); }
    if (tab === 'simulator') loadSimulatorPortfolio();
    if (tab === 'backtest') loadBacktestHistory();
    if (tab === "history") {
        const today = new Date();
        const start = new Date(today); start.setMonth(start.getMonth() - 1);
        document.getElementById("histEnd").value = today.toISOString().slice(0, 10).replace(/-/g, "");
        document.getElementById("histStart").value = start.toISOString().slice(0, 10).replace(/-/g, "");
    }
}

async function fetchStatus() {
    try {
        const res = await fetch('/api/scalper/status');
        const data = await res.json();
        renderProcesses(data.processes);
        document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
    } catch (e) { console.error(e); }
}

async function fetchStates() {
    try {
        const res = await fetch('/api/scalper/states');
        const data = await res.json();
        renderStates(data.states);
    } catch (e) { console.error(e); }
}

function renderProcesses(processes) {
    const container = document.getElementById('processList');
    const select = document.getElementById('logTicker');
    if (!processes.length) {
        container.innerHTML = '<div class="text-center text-gray-600 py-8">No running processes</div>';
        select.innerHTML = '<option value="">Select ticker...</option>';
        return;
    }
    container.innerHTML = processes.map(p => `
                <div class="flex justify-between items-center p-3 bg-dark-900 rounded-lg">
                    <div>
                        <div class="font-medium text-accent-blue">${p.ticker}
                            <span class="ml-2 px-2 py-0.5 text-xs rounded ${p.live_mode ? 'bg-accent-red' : 'bg-accent-blue'}">${p.live_mode ? 'LIVE' : 'DRY'}</span>
                            ${p.llm_mode ? '<span class="ml-1 px-2 py-0.5 text-xs rounded bg-accent-purple">LLM</span>' : ''}
                        </div>
                        <div class="text-xs text-gray-500 mt-1">PID: ${p.pid} | Budget: ${p.budget.toLocaleString()} | ${formatUptime(p.uptime_seconds)}</div>
                    </div>
                    <div class="flex gap-2">
                        <button onclick="viewLogs('${p.ticker}')" class="px-3 py-1 text-xs bg-dark-700 hover:bg-dark-600 rounded">Logs</button>
                        <button onclick="resetScalper('${p.ticker}')" class="px-3 py-1 text-xs bg-accent-yellow hover:bg-yellow-600 text-black rounded">Reset</button>
                        <button onclick="stopScalper('${p.ticker}')" class="px-3 py-1 text-xs bg-accent-red hover:bg-red-600 rounded">Stop</button>
                    </div>
                </div>
            `).join('');
    select.innerHTML = '<option value="">Select ticker...</option>' + processes.map(p => `<option value="${p.ticker}">${p.ticker}</option>`).join('');
}

function renderStates(states) {
    const container = document.getElementById('stateList');
    if (!states.length) { container.innerHTML = '<div class="text-center text-gray-600 py-8">No saved states</div>'; return; }
    container.innerHTML = states.map(s => `
                <div class="p-3 bg-dark-900 rounded-lg">
                    <div class="font-medium text-accent-yellow">${s.ticker} - ${s.state}</div>
                    <div class="text-xs text-gray-500 mt-1">
                        Avg: ${s.avg_buy_price?.toLocaleString() || 0} | Qty: ${s.total_qty || 0} | Step: ${s.current_step || 0}
                        <span class="${(s.daily_realized_profit || 0) >= 0 ? 'text-accent-green' : 'text-accent-red'}">
                            P&L: ${(s.daily_realized_profit || 0).toLocaleString()}
                        </span>
                    </div>
                </div>
            `).join('');
}

function formatUptime(s) { const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60); return h > 0 ? `${h}h ${m}m` : `${m}m`; }

async function stopScalper(ticker) {
    if (!confirm(`Stop ${ticker}?`)) return;
    try {
        await fetch(`/api/scalper/stop/${ticker}`, { method: 'POST' });
        fetchStatus();
    } catch (e) { alert(e.message); }
}

async function resetScalper(ticker) {
    if (!confirm(`Reset state for ${ticker}? This will clear internal state/positions.`)) return;
    try {
        await fetch(`/api/scalper/reset/${ticker}`, { method: 'POST' });
        alert(`Reset ${ticker} successfully`);
        fetchStatus();
    } catch (e) { alert(e.message); }
}

function viewLogs(ticker) {
    document.getElementById('logTicker').value = ticker;
    connectWebSocket(ticker);
}

function connectWebSocket(ticker) {
    if (ws) ws.close();
    const container = document.getElementById('logContainer');
    container.innerHTML = '';
    if (!ticker) { container.innerHTML = '<div class="text-gray-600">Select a process</div>'; return; }
    ws = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws/logs/${ticker}`);
    ws.onmessage = e => {
        const line = document.createElement('div');
        line.textContent = e.data;
        line.className = 'py-0.5';
        container.appendChild(line);
        container.scrollTop = container.scrollHeight;
    };
    ws.onclose = () => { container.innerHTML += '<div class="text-accent-red">[Disconnected]</div>'; };
}

document.getElementById('startForm').addEventListener('submit', async e => {
    e.preventDefault();
    const data = {
        ticker: document.getElementById('ticker').value,
        budget: parseFloat(document.getElementById('budget').value),
        target: parseFloat(document.getElementById('target').value) / 100,
        live_mode: document.getElementById('liveMode').checked,
        llm_mode: document.getElementById('llmMode').checked,
        orderbook: document.getElementById('orderbook').checked,
        momentum: document.getElementById('momentum').checked,
    };
    try {
        const res = await fetch('/api/scalper/start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
        if (!res.ok) { const err = await res.json(); alert(err.detail); return; }
        document.getElementById('ticker').value = '';
        fetchStatus();
    } catch (e) { alert(e.message); }
});

document.getElementById('logTicker').addEventListener('change', e => connectWebSocket(e.target.value));

document.getElementById('screenerForm').addEventListener('submit', async e => {
    e.preventDefault();
    loadScreenerData();
});

async function loadScreenerData() {
    const data = {
        per_max: document.getElementById('perMax').value ? parseFloat(document.getElementById('perMax').value) : null,
        pbr_max: document.getElementById('pbrMax').value ? parseFloat(document.getElementById('pbrMax').value) : null,
        foreign_net_min: document.getElementById('foreignMin').value ? parseInt(document.getElementById('foreignMin').value) : null,
        market: document.getElementById('market').value || null,
        sort_by: document.getElementById('sortBy').value,
        limit: 50
    };
    try {
        const tbody = document.getElementById('screenerResults');
        tbody.innerHTML = '<tr><td colspan="11" class="px-4 py-8 text-center text-gray-600" data-i18n="loading">Loading...</td></tr>';
        applyTranslations();
        const res = await fetch('/api/screener', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
        const result = await res.json();
        renderScreenerResults(result.stocks);
    } catch (e) {
        document.getElementById('screenerResults').innerHTML = `<tr><td colspan="11" class="px-4 py-8 text-center text-accent-red">Error: ${e.message}</td></tr>`;
    }
}

function renderScreenerResults(stocks) {
    const tbody = document.getElementById('screenerResults');
    if (!stocks || !stocks.length) {
        tbody.innerHTML = '<tr><td colspan="11" class="px-4 py-8 text-center text-gray-600" data-i18n="no_results">No results</td></tr>';
        applyTranslations();
        return;
    }
    const unit = t('unit_100m');
    tbody.innerHTML = stocks.map(s => `
                <tr class="hover:bg-dark-700">
                    <td class="px-4 py-3 text-accent-blue">${s.ticker}</td>
                    <td class="px-4 py-3">${s.name}</td>
                    <td class="px-4 py-3 text-right">${(s.close || 0).toLocaleString()}</td>
                    <td class="px-4 py-3 text-right ${(s.change_rate || 0) >= 0 ? 'text-accent-green' : 'text-accent-red'}">${(s.change_rate || 0).toFixed(2)}%</td>
                    <td class="px-4 py-3 text-right">${s.per ? s.per.toFixed(1) : '-'}</td>
                    <td class="px-4 py-3 text-right">${s.pbr ? s.pbr.toFixed(2) : '-'}</td>
                    <td class="px-4 py-3 text-right ${(s.foreign_net || 0) >= 0 ? 'text-accent-green' : 'text-accent-red'}">${s.foreign_net ? (s.foreign_net_amt || 0).toFixed(1) + unit : '-'}</td>
                    <td class="px-4 py-3 text-right ${(s.inst_net || 0) >= 0 ? 'text-accent-green' : 'text-accent-red'}">${s.inst_net ? (s.inst_net_amt || 0).toFixed(1) + unit : '-'}</td>
                    <td class="px-4 py-3 text-right">${s.short_ratio ? s.short_ratio.toFixed(2) + '%' : '-'}</td>
                    <td class="px-4 py-3 text-right">${s.credit_ratio ? s.credit_ratio.toFixed(2) + '%' : '-'}</td>
                    <td class="px-4 py-3 text-center">
                        <button onclick="analyzeStock('${s.ticker}')" class="px-2 py-1 text-xs bg-accent-purple hover:bg-purple-600 rounded" data-i18n="analyze">Analyze</button>
                    </td>
                </tr>
            `).join('');
    document.querySelectorAll('#screenerResults [data-i18n]').forEach(el => el.textContent = t(el.getAttribute('data-i18n')));
}

function analyzeStock(ticker) {
    document.getElementById('deepdiveSearch').value = ticker;
    showTab('deepdive');
    loadDeepDive();
}

async function loadDeepDive() {
    const ticker = document.getElementById('deepdiveSearch').value.trim();
    if (!ticker) return;
    document.getElementById('aiReportContent').classList.add('hidden');
    try {
        const res = await fetch(`/api/deepdive/${ticker}`);
        if (!res.ok) { throw new Error('Stock not found'); }
        const data = await res.json();
        renderDeepDive(data);
    } catch (e) {
        document.getElementById('stockInfo').innerHTML = `<div class="text-accent-red">${e.message}</div>`;
    }
}

async function loadAIDeepDive(mode = 'simple') {
    const ticker = document.getElementById('deepdiveSearch').value.trim();
    if (!ticker) return;
    document.getElementById('aiReportContent').classList.remove('hidden');
    const modeLabel = mode === 'deep' ? 'Deep (GPT-4o)' : 'Simple (GPT-4o-mini)';
    document.getElementById('aiReport').innerHTML = `<div class="text-gray-500">Generating ${modeLabel} AI report...</div>`;
    try {
        const res = await fetch(`/api/ai/deepdive/${ticker}?mode=${mode}`);
        if (!res.ok) throw new Error('Failed to generate report');
        const data = await res.json();
        renderAIReport(data, mode);
    } catch (e) {
        document.getElementById('aiReport').innerHTML = `<div class="text-accent-red">${e.message}</div>`;
    }
}

function renderAIReport(data, mode = 'simple') {
    const a = data.analysis || {};
    const rec = a.recommendation || 'HOLD';
    const recClass = rec === 'BUY' ? 'text-accent-green' : rec === 'SELL' ? 'text-accent-red' : 'text-accent-yellow';
    const modeLabel = mode === 'deep' ? '🔍 Deep' : '⚡ Simple';
    const modeBadge = mode === 'deep' ? 'bg-accent-green' : 'bg-accent-blue';
    document.getElementById('aiReport').innerHTML = `
                <div class="flex items-center gap-4 mb-4">
                    <span class="text-2xl font-bold ${recClass}">${rec}</span>
                    <span class="px-3 py-1 rounded text-sm ${modeBadge} text-white">${modeLabel}</span>
                    <span class="px-3 py-1 rounded text-sm ${a.risk_level === 'HIGH' ? 'bg-accent-red' : a.risk_level === 'LOW' ? 'bg-accent-green' : 'bg-accent-yellow'} text-black">Risk: ${a.risk_level || '-'}</span>
                    ${a.target_price ? `<span class="text-gray-400">Target: ${a.target_price.toLocaleString()}원</span>` : ''}
                </div>
                <div class="grid md:grid-cols-2 gap-4 text-sm">
                    <div class="p-3 bg-dark-900 rounded"><div class="text-xs text-gray-500 mb-1">Technical</div>${a.technical || '-'}</div>
                    <div class="p-3 bg-dark-900 rounded"><div class="text-xs text-gray-500 mb-1">Fundamental</div>${a.fundamental || '-'}</div>
                    <div class="p-3 bg-dark-900 rounded"><div class="text-xs text-gray-500 mb-1">Flow</div>${a.flow || '-'}</div>
                    <div class="p-3 bg-dark-900 rounded"><div class="text-xs text-gray-500 mb-1">Human Indicator</div>${a.human_indicator || '-'}</div>
                </div>
                <div class="mt-4 p-3 bg-dark-900 rounded">
                    <div class="text-xs text-gray-500 mb-1">Summary</div>
                    <div>${a.summary || '-'}</div>
                </div>
                ${a.key_points?.length ? `<div class="mt-4"><div class="text-xs text-gray-500 mb-2">Key Points</div><ul class="list-disc list-inside space-y-1">${a.key_points.map(p => `<li>${p}</li>`).join('')}</ul></div>` : ''}
            `;
}

function renderDeepDive(data) {
    const stock = data.stock;
    const latestPrice = data.price_history[0] || {};
    const latestStats = data.stats_history[0] || {};
    const latestInvestor = data.investor_history[0] || {};
    const latestShortCredit = data.short_credit?.[0] || {};

    document.getElementById('stockInfo').innerHTML = `
                <div class="space-y-4">
                    <div class="flex justify-between items-start">
                        <div>
                            <h2 class="text-2xl font-bold text-white">${stock.name}</h2>
                            <div class="text-gray-500">${stock.ticker} · ${stock.market}</div>
                        </div>
                        <div class="text-right">
                            <div class="text-3xl font-bold">${(latestPrice.close || 0).toLocaleString()}</div>
                            <div class="${(latestPrice.change_rate || 0) >= 0 ? 'text-accent-green' : 'text-accent-red'}">
                                ${(latestPrice.change_rate || 0) >= 0 ? '+' : ''}${(latestPrice.change_rate || 0).toFixed(2)}%
                            </div>
                        </div>
                    </div>
                    <div class="grid grid-cols-4 gap-4 pt-4 border-t border-dark-600">
                        <div><div class="text-xs text-gray-500">Volume</div><div class="font-medium">${((latestPrice.volume || 0) / 1000).toFixed(0)}K</div></div>
                        <div><div class="text-xs text-gray-500">Market Cap</div><div class="font-medium">${(latestPrice.market_cap || 0).toLocaleString()}억</div></div>
                        <div><div class="text-xs text-gray-500">Foreign</div><div class="font-medium ${(latestInvestor.foreign_net || 0) >= 0 ? 'text-accent-green' : 'text-accent-red'}">${((latestInvestor.foreign_net || 0) / 100000000).toFixed(1)}억</div></div>
                        <div><div class="text-xs text-gray-500">Institution</div><div class="font-medium ${(latestInvestor.inst_net || 0) >= 0 ? 'text-accent-green' : 'text-accent-red'}">${((latestInvestor.inst_net || 0) / 100000000).toFixed(1)}억</div></div>
                    </div>
                </div>
            `;

    document.getElementById('keyMetrics').innerHTML = `
                <div class="space-y-3">
                    <div class="flex justify-between"><span class="text-gray-500">PER</span><span>${latestStats.per ? latestStats.per.toFixed(1) : '-'}</span></div>
                    <div class="flex justify-between"><span class="text-gray-500">PBR</span><span>${latestStats.pbr ? latestStats.pbr.toFixed(2) : '-'}</span></div>
                    <div class="flex justify-between"><span class="text-gray-500">EPS</span><span>${latestStats.eps ? latestStats.eps.toLocaleString() : '-'}</span></div>
                    <div class="flex justify-between">
                        <span class="text-gray-500 border-b border-dotted border-gray-600 has-tooltip cursor-help">
                            Real-time PER
                            <span class="tooltip-text" style="width:200px; bottom: 100%;">Current Price / EPS (Last 4Q)</span>
                        </span>
                        <span class="text-accent-blue font-medium">
                            ${(latestPrice.close && latestStats.eps && latestStats.eps > 0)
            ? (latestPrice.close / latestStats.eps).toFixed(2)
            : '-'}
                        </span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-gray-500 border-b border-dotted border-gray-600 has-tooltip cursor-help">
                            Forward PER
                            <span class="tooltip-text" style="width:200px; bottom: 100%;">Current Price / Forward EPS (Estimated)</span>
                        </span>
                        <span class="text-accent-purple font-medium">
                            ${(latestPrice.close && stock.fwd_eps && stock.fwd_eps > 0)
            ? (latestPrice.close / stock.fwd_eps).toFixed(2)
            : '-'}
                        </span>
                    </div>
                    <div class="flex justify-between"><span class="text-gray-500">BPS</span><span>${latestStats.bps ? latestStats.bps.toLocaleString() : '-'}</span></div>
                    <div class="flex justify-between">
                        <span class="text-gray-500 border-b border-dotted border-gray-600 has-tooltip cursor-help">
                            Live Talk Users
                            <span class="tooltip-text" style="width:200px; bottom: 100%;">Current Participants in Naver Open Talk</span>
                        </span>
                        <span class="text-accent-green font-medium">
                            ${stock.opentalk_users ? stock.opentalk_users.toLocaleString() : '-'}
                        </span>
                    </div>
                    <div class="flex justify-between"><span class="text-gray-500">Foreign Ratio</span><span>${latestInvestor.foreign_ratio ? latestInvestor.foreign_ratio.toFixed(1) + '%' : '-'}</span></div>
                    <div class="border-t border-dark-600 pt-2 mt-2"></div>
                    <div class="flex justify-between"><span class="text-gray-500">Short Ratio</span><span class="text-accent-red">${latestShortCredit.short_ratio ? latestShortCredit.short_ratio.toFixed(2) + '%' : '-'}</span></div>
                    <div class="flex justify-between"><span class="text-gray-500">Credit Ratio</span><span class="text-yellow-500">${latestShortCredit.credit_ratio ? latestShortCredit.credit_ratio.toFixed(2) + '%' : '-'}</span></div>
                    <div class="flex justify-between text-xs text-gray-500 mt-1"><span>Short Bal</span><span>${latestShortCredit.short_balance ? (latestShortCredit.short_balance / 1000).toFixed(0) + 'K' : '-'}</span></div>
                    <div class="flex justify-between text-xs text-gray-500"><span>Credit Bal</span><span>${latestShortCredit.credit_balance ? (latestShortCredit.credit_balance / 1000).toFixed(0) + 'K' : '-'}</span></div>
                </div>
            `;

    // Render Open Talk Trend
    if (data.opentalk_history && data.opentalk_history.length > 0) {
        document.getElementById('opentalkTrendSection').classList.remove('hidden');
        renderOpentalkChart(data.opentalk_history);
    } else {
        document.getElementById('opentalkTrendSection').classList.add('hidden');
    }

    renderInvestorTrend(data.investor_history || []);
    renderShortCreditTrend(data.short_credit || []);
}

let investorChart = null;

function renderInvestorTrend(investorHistory) {
    const section = document.getElementById('investorTrendSection');

    if (!investorHistory || investorHistory.length === 0) {
        section.classList.add('hidden');
        return;
    }

    section.classList.remove('hidden');

    const sorted = [...investorHistory].sort((a, b) => a.date.localeCompare(b.date));

    const labels = sorted.map(d => d.date.slice(5));
    const foreignData = sorted.map(d => (d.foreign_net || 0) / 100000000);
    const instData = sorted.map(d => (d.inst_net || 0) / 100000000);
    const retailData = sorted.map(d => (d.retail_net || 0) / 100000000);

    const ctx = document.getElementById('investorTrendChart').getContext('2d');

    if (investorChart) {
        investorChart.destroy();
    }

    investorChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: t('foreign') || 'Foreign',
                    data: foreignData,
                    backgroundColor: foreignData.map(v => v >= 0 ? 'rgba(88, 166, 255, 0.8)' : 'rgba(248, 81, 73, 0.8)'),
                    borderColor: foreignData.map(v => v >= 0 ? '#58a6ff' : '#f85149'),
                    borderWidth: 1
                },
                {
                    label: t('institution') || 'Institution',
                    data: instData,
                    backgroundColor: instData.map(v => v >= 0 ? 'rgba(163, 113, 247, 0.8)' : 'rgba(210, 153, 34, 0.8)'),
                    borderColor: instData.map(v => v >= 0 ? '#a371f7' : '#d29922'),
                    borderWidth: 1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: { color: '#9ca3af', font: { size: 11 } }
                },
                tooltip: {
                    callbacks: {
                        label: ctx => `${ctx.dataset.label}: ${ctx.raw >= 0 ? '+' : ''}${ctx.raw.toFixed(1)} 억`
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#6b7280', font: { size: 10 } },
                    grid: { color: '#30363d' }
                },
                y: {
                    ticks: {
                        color: '#6b7280',
                        font: { size: 10 },
                        callback: v => v + '억'
                    },
                    grid: { color: '#30363d' }
                }
            }
        }
    });

    const tbody = document.getElementById('investorTrendBody');
    const reversed = [...sorted].reverse();
    tbody.innerHTML = reversed.map(d => {
        const fNet = (d.foreign_net || 0) / 100000000;
        const iNet = (d.inst_net || 0) / 100000000;
        const rNet = (d.retail_net || 0) / 100000000;
        return `
                    <tr>
                        <td class="py-2 text-gray-400">${d.date}</td>
                        <td class="py-2 text-right ${fNet >= 0 ? 'text-accent-blue' : 'text-accent-red'}">${fNet >= 0 ? '+' : ''}${fNet.toFixed(1)}억</td>
                        <td class="py-2 text-right ${iNet >= 0 ? 'text-accent-purple' : 'text-accent-yellow'}">${iNet >= 0 ? '+' : ''}${iNet.toFixed(1)}억</td>
                        <td class="py-2 text-right ${rNet >= 0 ? 'text-accent-green' : 'text-accent-red'}">${rNet >= 0 ? '+' : ''}${rNet.toFixed(1)}억</td>
                    </tr>
                `;
    }).join('');
}

let shortCreditChart = null;

function renderShortCreditTrend(history) {
    const section = document.getElementById('shortCreditTrendSection');

    if (!history || history.length === 0) {
        section.classList.add('hidden');
        return;
    }

    section.classList.remove('hidden');

    const sorted = [...history].sort((a, b) => a.date.localeCompare(b.date));
    const labels = sorted.map(d => d.date.slice(5));
    const shortData = sorted.map(d => (d.short_balance || 0));
    const creditData = sorted.map(d => (d.credit_balance || 0));

    const ctx = document.getElementById('shortCreditTrendChart').getContext('2d');

    if (shortCreditChart) {
        shortCreditChart.destroy();
    }

    shortCreditChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: t('credit_bal') || 'Credit Bal',
                    data: creditData,
                    borderColor: '#d29922', // yellow
                    backgroundColor: 'rgba(210, 153, 34, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    yAxisID: 'y'
                },
                {
                    label: t('short_bal') || 'Short Bal',
                    data: shortData,
                    borderColor: '#f85149', // red
                    backgroundColor: 'rgba(248, 81, 73, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: { color: '#9ca3af', font: { size: 11 } }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#6b7280', font: { size: 10 } },
                    grid: { color: '#30363d' }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    ticks: {
                        color: '#d29922',
                        font: { size: 10 },
                        callback: v => (v / 1000).toFixed(0) + 'K'
                    },
                    grid: { color: '#30363d' },
                    title: { display: true, text: 'Credit', color: '#d29922' }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    ticks: {
                        color: '#f85149',
                        font: { size: 10 },
                        callback: v => (v / 1000).toFixed(0) + 'K'
                    },
                    grid: { drawOnChartArea: false },
                    title: { display: true, text: 'Short', color: '#f85149' }
                }
            }
        }
    });

    const tbody = document.getElementById('shortCreditTrendBody');
    const reversed = [...sorted].reverse();
    tbody.innerHTML = reversed.map(d => {
        const sBal = (d.short_balance || 0);
        const cBal = (d.credit_balance || 0);
        const sRatio = (d.short_ratio || 0).toFixed(2);
        const cRatio = (d.credit_ratio || 0).toFixed(2);

        return `
                    <tr>
                        <td class="py-2 text-gray-400">${d.date}</td>
                        <td class="py-2 text-right text-accent-red">${(sBal / 1000).toFixed(0)}K</td>
                        <td class="py-2 text-right text-accent-yellow">${(cBal / 1000).toFixed(0)}K</td>
                        <td class="py-2 text-right text-gray-300">S:${sRatio}% C:${cRatio}%</td>
                    </tr>
                `;
    }).join('');
}

async function loadFomoAlerts() {
    try {
        const res = await fetch('/api/human-index/fomo-alerts?threshold=70');
        const data = await res.json();
        const container = document.getElementById('fomoAlerts');
        if (!data.stocks?.length) { container.innerHTML = '<div class="text-center text-gray-600 py-4">No FOMO alerts</div>'; return; }
        container.innerHTML = data.stocks.map(s => `
                <div class="p-3 bg-dark-900 rounded-lg heatmap-hot text-white cursor-pointer hover:bg-dark-700 transition" onclick="loadHumanIndexFromSignal('${s.ticker}')">
                        <div class="font-medium">${s.name || s.ticker} <span class="text-xs opacity-75">${s.ticker}</span></div>
                        <div class="text-sm mt-1">FOMO: ${s.fomo_level?.toFixed(0) || 0} | Attention: ${s.attention_score?.toFixed(0) || 0}</div>
                    </div>
                `).join('');
    } catch (e) { console.error(e); }
}

async function loadBottomSignals() {
    try {
        const res = await fetch('/api/human-index/bottom-signals?threshold=20');
        const data = await res.json();
        const container = document.getElementById('bottomSignals');
        if (!data.stocks?.length) { container.innerHTML = '<div class="text-center text-gray-600 py-4">No bottom signals</div>'; return; }
        container.innerHTML = data.stocks.map(s => `
                <div class="p-3 bg-dark-900 rounded-lg heatmap-cool text-white cursor-pointer hover:bg-dark-700 transition" onclick="loadHumanIndexFromSignal('${s.ticker}')">
                        <div class="font-medium">${s.name || s.ticker} <span class="text-xs opacity-75">${s.ticker}</span></div>
                        <div class="text-sm mt-1">Attention: ${s.attention_score?.toFixed(0) || 0} | Sentiment: ${s.crowd_sentiment?.toFixed(2) || 0}</div>
                    </div>
                `).join('');
    } catch (e) { console.error(e); }
}

async function loadHumanIndexFromSignal(ticker) {
    document.getElementById('humanIndexTicker').value = ticker;
    await loadHumanIndex();
}

async function collectHumanIndexNow() {
    const btn = document.getElementById('btnCollectHumanNow');
    const originalText = btn.textContent;

    const ticker = document.getElementById('humanIndexTicker').value.trim();
    const days = document.getElementById('humanIndexDays').value || 30;

    if (!ticker) {
        alert('Please enter a ticker');
        return;
    }

    try {
        btn.disabled = true;
        btn.textContent = 'Collecting...';

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
        }

        alert(msg);
        loadHumanIndex(); // Reload charts

    } catch (e) {
        alert(e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

async function loadHumanIndex() {
    const ticker = document.getElementById('humanIndexTicker').value.trim();
    if (!ticker) return;
    try {
        const [res, historyRes, youtubeRes, naverRes] = await Promise.all([
            fetch(`/api/human-index/${ticker}`),
            fetch(`/api/human-index/${ticker}/history?days=30`),
            fetch(`/api/human-index/${ticker}/youtube-history?days=30`),
            fetch(`/api/human-index/${ticker}/naver-history?days=30`)
        ]);
        const data = await res.json();
        const historyData = await historyRes.json();
        const youtubeData = await youtubeRes.json();
        const naverData = await naverRes.json();

        document.getElementById('hiAttention').textContent = data.attention_score?.toFixed(1) || '-';
        document.getElementById('hiFomo').textContent = data.fomo_level?.toFixed(1) || '-';
        document.getElementById('hiSentiment').textContent = data.crowd_sentiment?.toFixed(2) || '-';

        const details = document.getElementById('humanIndexDetails');
        details.innerHTML = '';
        if (data.youtube || data.naver) {
            details.classList.remove('hidden');

            if (data.youtube) {
                details.innerHTML += `
                            <div class="bg-dark-900 rounded p-4 border border-dark-600">
                                <div class="text-accent-red font-semibold mb-3 flex items-center gap-2">
                                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0-3.897.266-4.356 2.62-4.385 8.816.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0 3.897-.266 4.356-2.62 4.385-8.816-.029-6.185-.484-8.549-4.385-8.816zm-10.615 12.816v-8l8 3.993-8 4.007z"/></svg>
                                    <span>YouTube Stats</span>
                                </div>
                                <div class="grid grid-cols-3 gap-2 text-sm text-center">
                                    <div class="p-2 bg-dark-800 rounded"><div class="text-xs text-gray-500 mb-1">Videos</div><div class="font-bold">${data.youtube.video_count?.toLocaleString() || 0}</div></div>
                                    <div class="p-2 bg-dark-800 rounded"><div class="text-xs text-gray-500 mb-1">Total Views</div><div class="font-bold">${data.youtube.total_views ? (data.youtube.total_views / 10000).toFixed(0) + '만' : '-'}</div></div>
                                    <div class="p-2 bg-dark-800 rounded"><div class="text-xs text-gray-500 mb-1">Avg Likes</div><div class="font-bold">${data.youtube.avg_likes?.toLocaleString() || '-'}</div></div>
                                </div>
                            </div>`;
            }

            if (data.naver) {
                details.innerHTML += `
                            <div class="bg-dark-900 rounded p-4 border border-dark-600">
                                <div class="text-accent-green font-semibold mb-3 flex items-center gap-2">
                                    <span class="font-bold text-lg">N</span>
                                    <span>Naver Stats</span>
                                </div>
                                <div class="grid grid-cols-3 gap-2 text-sm text-center">
                                    <div class="p-2 bg-dark-800 rounded"><div class="text-xs text-gray-500 mb-1">Posts</div><div class="font-bold">${data.naver.post_count?.toLocaleString() || 0}</div></div>
                                    <div class="p-2 bg-dark-800 rounded"><div class="text-xs text-gray-500 mb-1">Avg Views</div><div class="font-bold">${data.naver.avg_views?.toLocaleString() || '-'}</div></div>
                                    <div class="p-2 bg-dark-800 rounded"><div class="text-xs text-gray-500 mb-1">Like Ratio</div><div class="font-bold">${(data.naver.like_ratio || 0).toFixed(1)}%</div></div>
                                </div>
                            </div>`;
            }
        } else {
            details.classList.add('hidden');
        }

        renderHumanIndexChart(historyData.history || []);
        renderYoutubeNaverCharts(youtubeData.history || [], naverData.history || []);
    } catch (e) { console.error(e); }
}

let humanIndexChart = null;

function renderHumanIndexChart(history) {
    const section = document.getElementById('humanIndexChartSection');

    if (!history || history.length === 0) {
        section.classList.add('hidden');
        return;
    }

    section.classList.remove('hidden');

    const sorted = [...history].sort((a, b) => a.date.localeCompare(b.date));

    const labels = sorted.map(d => d.date.slice(5));
    const attentionData = sorted.map(d => d.attention_score || 0);
    const fomoData = sorted.map(d => d.fomo_level || 0);
    const sentimentData = sorted.map(d => (d.crowd_sentiment || 0) * 100);

    const ctx = document.getElementById('humanIndexChart').getContext('2d');

    if (humanIndexChart) {
        humanIndexChart.destroy();
    }

    humanIndexChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: t('attention_score') || 'Attention',
                    data: attentionData,
                    borderColor: '#58a6ff',
                    backgroundColor: 'rgba(88, 166, 255, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: false
                },
                {
                    label: t('fomo_level') || 'FOMO',
                    data: fomoData,
                    borderColor: '#f85149',
                    backgroundColor: 'rgba(248, 81, 73, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: false
                },
                {
                    label: t('crowd_sentiment') || 'Sentiment',
                    data: sentimentData,
                    borderColor: '#a371f7',
                    backgroundColor: 'rgba(163, 113, 247, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: { color: '#9ca3af', font: { size: 11 } }
                },
                tooltip: {
                    callbacks: {
                        label: ctx => `${ctx.dataset.label}: ${ctx.raw.toFixed(1)}`
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#6b7280', font: { size: 10 } },
                    grid: { color: '#30363d' }
                },
                y: {
                    min: 0,
                    max: 100,
                    ticks: { color: '#6b7280', font: { size: 10 } },
                    grid: { color: '#30363d' }
                }
            }
        }
    });
}

let youtubeChart = null;
let naverChart = null;

function renderYoutubeNaverCharts(youtubeHistory, naverHistory) {
    const section = document.getElementById('youtubeNaverChartSection');

    if ((!youtubeHistory || youtubeHistory.length === 0) && (!naverHistory || naverHistory.length === 0)) {
        section.classList.add('hidden');
        return;
    }

    section.classList.remove('hidden');

    if (youtubeHistory && youtubeHistory.length > 0) {
        const sorted = [...youtubeHistory].sort((a, b) => a.date.localeCompare(b.date));
        const labels = sorted.map(d => d.date.slice(5));
        const videoData = sorted.map(d => d.video_count || 0);
        const viewsData = sorted.map(d => (d.total_views || 0) / 10000);

        const ctx = document.getElementById('youtubeChart').getContext('2d');
        if (youtubeChart) youtubeChart.destroy();

        youtubeChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Videos',
                        data: videoData,
                        backgroundColor: 'rgba(248, 81, 73, 0.7)',
                        borderColor: '#f85149',
                        borderWidth: 1,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Views (만)',
                        data: viewsData,
                        type: 'line',
                        borderColor: '#58a6ff',
                        backgroundColor: 'rgba(88, 166, 255, 0.1)',
                        borderWidth: 2,
                        tension: 0.3,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top', labels: { color: '#9ca3af', font: { size: 10 } } }
                },
                scales: {
                    x: { ticks: { color: '#6b7280', font: { size: 9 } }, grid: { color: '#30363d' } },
                    y: { position: 'left', ticks: { color: '#f85149', font: { size: 9 } }, grid: { color: '#30363d' } },
                    y1: { position: 'right', ticks: { color: '#58a6ff', font: { size: 9 } }, grid: { display: false } }
                }
            }
        });
    }

    if (naverHistory && naverHistory.length > 0) {
        const sorted = [...naverHistory].sort((a, b) => a.date.localeCompare(b.date));
        const labels = sorted.map(d => d.date.slice(5));
        const postData = sorted.map(d => d.post_count || 0);
        const likeData = sorted.map(d => (d.like_ratio || 0) * 100);

        const ctx = document.getElementById('naverChart').getContext('2d');
        if (naverChart) naverChart.destroy();

        naverChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Posts',
                        data: postData,
                        backgroundColor: 'rgba(63, 185, 80, 0.7)',
                        borderColor: '#3fb950',
                        borderWidth: 1,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Like %',
                        data: likeData,
                        type: 'line',
                        borderColor: '#a371f7',
                        backgroundColor: 'rgba(163, 113, 247, 0.1)',
                        borderWidth: 2,
                        tension: 0.3,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top', labels: { color: '#9ca3af', font: { size: 10 } } }
                },
                scales: {
                    x: { ticks: { color: '#6b7280', font: { size: 9 } }, grid: { color: '#30363d' } },
                    y: { position: 'left', ticks: { color: '#3fb950', font: { size: 9 } }, grid: { color: '#30363d' } },
                    y1: { position: 'right', min: 0, max: 100, ticks: { color: '#a371f7', font: { size: 9 } }, grid: { display: false } }
                }
            }
        });
    }
}

document.getElementById('backtestForm').addEventListener('submit', async e => {
    e.preventDefault();
    const data = {
        ticker: document.getElementById('btTicker').value,
        start_date: document.getElementById('btStartDate').value,
        end_date: document.getElementById('btEndDate').value,
        strategy: document.getElementById('btStrategy').value,
        initial_capital: parseFloat(document.getElementById('btCapital').value)
    };
    try {
        const res = await fetch('/api/backtest/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
        const result = await res.json();
        renderBacktestResult(result);
    } catch (e) { alert(e.message); }
});

function renderBacktestResult(r) {
    document.getElementById('backtestResult').classList.remove('hidden');
    document.getElementById('btReturn').textContent = `${r.total_return >= 0 ? '+' : ''}${r.total_return}%`;
    document.getElementById('btReturn').className = `text-2xl font-bold ${r.total_return >= 0 ? 'text-accent-green' : 'text-accent-red'}`;
    document.getElementById('btWinRate').textContent = `${r.win_rate}%`;
    document.getElementById('btMDD').textContent = `-${r.max_drawdown}%`;
    document.getElementById('btSharpe').textContent = r.sharpe_ratio.toFixed(2);

    if (r.trades?.length) {
        document.getElementById('btTrades').innerHTML = r.trades.slice(-20).reverse().map(t => `
                    <div class="flex justify-between items-center p-2 bg-dark-900 rounded text-xs">
                        <span class="${t.action === 'BUY' ? 'text-accent-green' : 'text-accent-red'}">${t.action}</span>
                        <span>${t.date}</span>
                        <span>${t.price?.toLocaleString()}</span>
                        <span>${t.quantity}주</span>
                        ${t.pnl !== undefined ? `<span class="${t.pnl >= 0 ? 'text-accent-green' : 'text-accent-red'}">${t.pnl >= 0 ? '+' : ''}${t.pnl.toLocaleString()}</span>` : '<span>-</span>'}
                    </div>
                `).join('');
    }
}

async function loadBacktestHistory() {
    try {
        const res = await fetch('/api/backtest/results?limit=10');
        const data = await res.json();
        const container = document.getElementById('backtestHistory');
        if (!data.results?.length) { container.innerHTML = '<div class="text-center text-gray-600 py-4">No past results</div>'; return; }
        container.innerHTML = data.results.map(r => `
                    <div class="flex justify-between items-center p-2 bg-dark-900 rounded text-sm">
                        <span class="text-accent-blue">${r.strategy_name}</span>
                        <span class="${r.total_return >= 0 ? 'text-accent-green' : 'text-accent-red'}">${r.total_return >= 0 ? '+' : ''}${r.total_return}%</span>
                        <span class="text-gray-500 text-xs">${r.start_date} ~ ${r.end_date}</span>
                    </div>
                `).join('');
    } catch (e) { console.error(e); }
}

async function loadGlobalMarket() {
    try {
        const res = await fetch('/api/global-market');
        const data = await res.json();
        const us = data.us_stocks || {};
        const vol = data.volatility || {};

        if (us.SPY) {
            document.getElementById('globalSPY').textContent = us.SPY.price;
            document.getElementById('globalSPYChange').textContent = `${us.SPY.change >= 0 ? '+' : ''}${us.SPY.change}%`;
            document.getElementById('globalSPYChange').className = `text-sm ${us.SPY.change >= 0 ? 'text-accent-green' : 'text-accent-red'}`;
        }
        if (us.QQQ) {
            document.getElementById('globalQQQ').textContent = us.QQQ.price;
            document.getElementById('globalQQQChange').textContent = `${us.QQQ.change >= 0 ? '+' : ''}${us.QQQ.change}%`;
            document.getElementById('globalQQQChange').className = `text-sm ${us.QQQ.change >= 0 ? 'text-accent-green' : 'text-accent-red'}`;
        }
        if (vol.VIX) {
            document.getElementById('globalVIX').textContent = vol.VIX.price;
            document.getElementById('globalVIXChange').textContent = `${vol.VIX.change >= 0 ? '+' : ''}${vol.VIX.change}%`;
            document.getElementById('globalVIXChange').className = `text-sm ${vol.VIX.change >= 0 ? 'text-accent-red' : 'text-accent-green'}`;
        }

        const sentiment = data.sentiment || 'neutral';
        const sentEl = document.getElementById('globalSentiment');
        sentEl.textContent = sentiment.toUpperCase();
        sentEl.className = `text-2xl font-bold ${sentiment === 'bullish' ? 'text-accent-green' : sentiment === 'bearish' ? 'text-accent-red' : 'text-accent-yellow'}`;

        const comm = data.commodities || {};
        const bonds = data.bonds || {};
        const other = document.getElementById('globalOther');
        other.innerHTML = Object.entries({ ...comm, ...bonds }).map(([k, v]) => `
                    <div class="flex justify-between p-2 bg-dark-900 rounded">
                        <span class="text-gray-400">${k}</span>
                        <span>${v.price}</span>
                        <span class="${v.change >= 0 ? 'text-accent-green' : 'text-accent-red'}">${v.change >= 0 ? '+' : ''}${v.change}%</span>
                    </div>
                `).join('');

        document.getElementById('globalAnalysis').innerHTML = `
                    <p class="mb-2">Market sentiment: <span class="font-bold ${sentiment === 'bullish' ? 'text-accent-green' : sentiment === 'bearish' ? 'text-accent-red' : 'text-accent-yellow'}">${sentiment}</span></p>
                    <p class="text-sm text-gray-400">Updated: ${data.updated_at || '-'}</p>
                `;
    } catch (e) { console.error(e); }
}

// --- Journal & Stock Search Logic ---

let currentSearchInputId = 'jTicker';

// Stock Search
function openStockSearch(inputId) {
    if (inputId) currentSearchInputId = inputId;
    document.getElementById('modal-stock-search').classList.remove('hidden');
    const input = document.getElementById('stockSearchInput');
    input.focus();
    input.select();
}

function closeStockSearch() {
    document.getElementById('modal-stock-search').classList.add('hidden');
    document.getElementById('stockSearchInput').value = '';
    document.getElementById('stockSearchResults').innerHTML = '<div class="text-center text-gray-600 py-8" data-i18n="enter_search_term">Enter search term...</div>';
    applyTranslations();
}

let searchTimeout;
const stockInput = document.getElementById('stockSearchInput');

stockInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
        e.preventDefault();
        const first = document.querySelector('#stockSearchResults > div');
        if (first && !first.dataset.i18n) first.click(); // Avoid clicking 'No results' message
    }
    if (e.key === 'Escape') closeStockSearch();
});

stockInput.addEventListener('input', e => {
    clearTimeout(searchTimeout);
    const q = e.target.value.trim();
    if (q.length < 2) return;
    searchTimeout = setTimeout(() => searchStocks(q), 300);
});

async function searchStocks(query) {
    try {
        const res = await fetch(`/api/stocks/search?q=${encodeURIComponent(query)}`);
        const data = await res.json();
        const container = document.getElementById('stockSearchResults');
        if (!data.stocks?.length) {
            container.innerHTML = '<div class="text-center text-gray-600 py-8" data-i18n="no_results">No results</div>';
            applyTranslations();
            return;
        }
        container.innerHTML = data.stocks.map(s => `
                    <div onclick="selectStock('${s.ticker}')" class="flex justify-between items-center p-3 bg-dark-800 hover:bg-dark-700 rounded-lg cursor-pointer transition">
                        <div>
                            <div class="font-bold text-white">${s.name}</div>
                            <div class="text-xs text-gray-500">${s.ticker} · ${s.market}</div>
                        </div>
                        <div class="text-accent-blue text-sm">Select</div>
                    </div>
                `).join('');
    } catch (e) { console.error(e); }
}

function selectStock(ticker) {
    const target = document.getElementById(currentSearchInputId);
    if (target) target.value = ticker;
    closeStockSearch();
}

// Journal Edit/Delete
function openEditJournalModal(id, ticker, side, price, qty, thesis, pnl) {
    document.getElementById('editId').value = id;
    document.getElementById('editTicker').value = ticker;
    document.getElementById('editSide').value = side;
    document.getElementById('editPrice').value = price;
    document.getElementById('editQty').value = qty;
    document.getElementById('editThesis').value = thesis === 'null' ? '' : thesis;
    document.getElementById('editPnl').value = pnl === 'null' ? '' : pnl;
    document.getElementById('modal-journal-edit').classList.remove('hidden');
}

function closeEditJournalModal() {
    document.getElementById('modal-journal-edit').classList.add('hidden');
}

document.getElementById('journalEditForm').addEventListener('submit', async e => {
    e.preventDefault();
    const id = document.getElementById('editId').value;
    const data = {
        ticker: document.getElementById('editTicker').value,
        side: document.getElementById('editSide').value,
        price: parseFloat(document.getElementById('editPrice').value),
        qty: parseInt(document.getElementById('editQty').value),
        thesis: document.getElementById('editThesis').value || null,
        pnl: document.getElementById('editPnl').value ? parseFloat(document.getElementById('editPnl').value) : null
    };
    try {
        await fetch(`/api/journal/entry/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
        closeEditJournalModal();
        loadJournalEntries();
        loadJournalStats();
    } catch (e) { alert(e.message); }
});

async function deleteJournalEntry(id) {
    if (!confirm(t('delete_confirm'))) return;
    try {
        await fetch(`/api/journal/entry/${id}`, { method: 'DELETE' });
        loadJournalEntries();
        loadJournalStats();
    } catch (e) { alert(e.message); }
}

// Modified Journal Add & List
document.getElementById('journalForm').addEventListener('submit', async e => {
    e.preventDefault();
    const data = {
        ticker: document.getElementById('jTicker').value,
        side: document.getElementById('jSide').value,
        price: parseFloat(document.getElementById('jPrice').value),
        qty: parseInt(document.getElementById('jQty').value),
        thesis: document.getElementById('jThesis').value || null,
        pnl: document.getElementById('jPnl').value ? parseFloat(document.getElementById('jPnl').value) : null
    };
    try {
        await fetch('/api/journal/entry', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
        document.getElementById('jTicker').value = '';
        document.getElementById('jPrice').value = '';
        document.getElementById('jQty').value = '';
        document.getElementById('jThesis').value = '';
        document.getElementById('jPnl').value = '';
        loadJournalEntries();
        loadJournalStats();
    } catch (e) { alert(e.message); }
});

async function loadJournalEntries() {
    try {
        const res = await fetch('/api/journal/entries?limit=30');
        const data = await res.json();
        const container = document.getElementById('journalEntries');
        if (!data.entries?.length) { container.innerHTML = '<div class="text-center text-gray-600 py-8" data-i18n="no_entries">No entries yet</div>'; applyTranslations(); return; }
        container.innerHTML = data.entries.map(e => `
                    <div class="flex justify-between items-center p-3 bg-dark-900 rounded-lg group hover:bg-dark-800 transition">
                        <div>
                            <span class="${e.side === 'BUY' ? 'text-accent-green' : 'text-accent-red'}">${e.side}</span>
                            <span class="text-accent-blue ml-2 font-medium">${e.stock_name || e.ticker}</span>
                            <div class="text-xs text-gray-500 mt-1">${e.date}</div>
                        </div>
                        <div class="text-right text-sm">
                            <div>${e.price?.toLocaleString()}원 × ${e.qty}주</div>
                            ${e.pnl !== null ? `<div class="${e.pnl >= 0 ? 'text-accent-green' : 'text-accent-red'}">${e.pnl >= 0 ? '+' : ''}${e.pnl.toLocaleString()}</div>` : ''}
                        </div>
                        <div class="flex gap-2 opacity-0 group-hover:opacity-100 transition">
                            <button onclick="openEditJournalModal('${e.id}', '${e.ticker}', '${e.side}', ${e.price}, ${e.qty}, '${e.thesis || 'null'}', '${e.pnl || 'null'}')" class="p-1.5 bg-dark-700 hover:bg-accent-blue hover:text-white rounded text-gray-400 transition">✏️</button>
                            <button onclick="deleteJournalEntry('${e.id}')" class="p-1.5 bg-dark-700 hover:bg-accent-red hover:text-white rounded text-gray-400 transition">🗑️</button>
                        </div>
                    </div>
                `).join('');
    } catch (e) { console.error(e); }
}

async function loadJournalStats() {
    try {
        const res = await fetch('/api/journal/statistics');
        const s = await res.json();
        document.getElementById('jsTotal').textContent = s.total_trades || 0;
        document.getElementById('jsWinRate').textContent = `${s.win_rate || 0}%`;
        document.getElementById('jsPnl').textContent = `${s.total_pnl >= 0 ? '+' : ''}${(s.total_pnl || 0).toLocaleString()}`;
        document.getElementById('jsPnl').className = s.total_pnl >= 0 ? 'text-accent-green' : 'text-accent-red';
        document.getElementById('jsBest').textContent = `+${(s.max_profit || 0).toLocaleString()}`;
        document.getElementById('jsWorst').textContent = (s.max_loss || 0).toLocaleString();
    } catch (e) { console.error(e); }
}

async function loadSimulatorPortfolio() {
    try {
        const res = await fetch('/api/simulator/portfolio');
        const p = await res.json();
        document.getElementById('simValue').textContent = (p.total_value || 0).toLocaleString();
        document.getElementById('simPnl').textContent = `${p.total_pnl >= 0 ? '+' : ''}${(p.total_pnl || 0).toLocaleString()}`;
        document.getElementById('simPnl').className = `text-2xl font-bold ${p.total_pnl >= 0 ? 'text-accent-green' : 'text-accent-red'}`;
        document.getElementById('simReturn').textContent = `${p.total_return_pct >= 0 ? '+' : ''}${p.total_return_pct || 0}%`;
        document.getElementById('simReturn').className = `text-2xl font-bold ${p.total_return_pct >= 0 ? 'text-accent-green' : 'text-accent-red'}`;
        document.getElementById('simWinRate').textContent = `${p.win_rate || 0}%`;

        const posContainer = document.getElementById('simPositions');
        if (!p.positions?.length) { posContainer.innerHTML = '<div class="text-center text-gray-600 py-4">No positions</div>'; }
        else {
            posContainer.innerHTML = p.positions.map(pos => `
                        <div class="flex justify-between items-center p-2 bg-dark-900 rounded text-sm">
                            <span class="text-accent-blue">${pos.name || pos.ticker}</span>
                            <span>${pos.quantity}주</span>
                            <span>${pos.current_price?.toLocaleString()}</span>
                            <span class="${pos.unrealized_pnl >= 0 ? 'text-accent-green' : 'text-accent-red'}">${pos.unrealized_pnl >= 0 ? '+' : ''}${pos.unrealized_pnl?.toLocaleString()}</span>
                        </div>
                    `).join('');
        }

        const trRes = await fetch('/api/simulator/trades?limit=20');
        const trData = await trRes.json();
        const trContainer = document.getElementById('simTrades');
        if (!trData.trades?.length) { trContainer.innerHTML = '<div class="text-center text-gray-600 py-4">No trades yet</div>'; }
        else {
            trContainer.innerHTML = trData.trades.map(t => `
                        <div class="flex justify-between items-center p-2 bg-dark-900 rounded text-xs">
                            <span class="${t.side === 'BUY' ? 'text-accent-green' : 'text-accent-red'}">${t.side}</span>
                            <span class="text-accent-blue">${t.ticker}</span>
                            <span>${t.price?.toLocaleString()}</span>
                            <span>${t.quantity}주</span>
                            ${t.pnl !== undefined ? `<span class="${t.pnl >= 0 ? 'text-accent-green' : 'text-accent-red'}">${t.pnl >= 0 ? '+' : ''}${t.pnl?.toLocaleString()}</span>` : '<span>-</span>'}
                        </div>
                    `).join('');
        }
    } catch (e) { console.error(e); }
}

async function simBuy() {
    const ticker = document.getElementById('simTicker').value;
    const price = parseFloat(document.getElementById('simPrice').value);
    const qty = document.getElementById('simQty').value ? parseInt(document.getElementById('simQty').value) : null;
    if (!ticker || !price) { alert('Ticker and price required'); return; }
    try {
        await fetch('/api/simulator/buy', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ticker, price, quantity: qty }) });
        loadSimulatorPortfolio();
    } catch (e) { alert(e.message); }
}

async function simSell() {
    const ticker = document.getElementById('simTicker').value;
    const price = parseFloat(document.getElementById('simPrice').value);
    const qty = document.getElementById('simQty').value ? parseInt(document.getElementById('simQty').value) : null;
    if (!ticker || !price) { alert('Ticker and price required'); return; }
    try {
        await fetch('/api/simulator/sell', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ticker, price, quantity: qty }) });
        loadSimulatorPortfolio();
    } catch (e) { alert(e.message); }
}

async function resetSimulator() {
    if (!confirm('Reset simulator? All positions and trades will be cleared.')) return;
    try {
        await fetch('/api/simulator/reset', { method: 'POST' });
        loadSimulatorPortfolio();
    } catch (e) { alert(e.message); }
}

async function loadAdminData() {
    try {
        const [statsRes, schedulerRes, logsRes] = await Promise.all([
            fetch('/api/stocks/count'),
            fetch('/api/admin/scheduler/status'),
            fetch('/api/admin/collection-logs?limit=10')
        ]);
        const stats = await statsRes.json();
        const scheduler = await schedulerRes.json();
        const logs = await logsRes.json();

        document.getElementById('statTotal').textContent = stats.total?.toLocaleString() || '0';
        document.getElementById('statKospi').textContent = stats.kospi?.toLocaleString() || '0';
        document.getElementById('statKosdaq').textContent = stats.kosdaq?.toLocaleString() || '0';
        document.getElementById('statScheduler').textContent = scheduler.is_running ? 'ON' : 'OFF';

        document.getElementById('schedulerStatus').innerHTML = `
                    <div class="flex justify-between"><span class="text-gray-500">Status</span><span class="${scheduler.is_running ? 'text-accent-green' : 'text-gray-500'}">${scheduler.is_running ? 'Running' : 'Stopped'}</span></div>
                    <div class="flex justify-between"><span class="text-gray-500">Mode</span><span>${scheduler.is_live ? 'LIVE' : 'Demo'}</span></div>
                    <div class="flex justify-between"><span class="text-gray-500">Last Collection</span><span>${scheduler.last_collection || 'Never'}</span></div>
                `;

        if (logs.logs?.length) {
            document.getElementById('collectionLogs').innerHTML = logs.logs.map(l => `
                        <div class="p-2 bg-dark-900 rounded text-xs">
                            <div class="flex justify-between">
                                <span class="text-accent-blue">${l.collection_type}</span>
                                <span class="text-gray-500">${l.date}</span>
                            </div>
                            <div class="text-gray-400 mt-1">${l.success_count}/${l.total_count} success (${l.duration_seconds?.toFixed(1)}s)</div>
                        </div>
                    `).join('');
        }
    } catch (e) { console.error(e); }
}

async function loadStocks() {
    try {
        const res = await fetch('/api/admin/load-stocks', { method: 'POST' });
        const data = await res.json();
        alert(`Loaded ${data.count} stocks`);
        loadAdminData();
    } catch (e) { alert(e.message); }
}

async function triggerCollection() {
    if (!confirm('Start data collection? This may take 10-15 minutes.')) return;
    try {
        const res = await fetch('/api/admin/collect', { method: 'POST' });
        const data = await res.json();
        alert(data.message);
    } catch (e) { alert(e.message); }
}

async function startScheduler() {
    try {
        await fetch('/api/admin/scheduler/start', { method: 'POST' });
        loadAdminData();
    } catch (e) { alert(e.message); }
}

async function stopScheduler() {
    try {
        await fetch('/api/admin/scheduler/stop', { method: 'POST' });
        loadAdminData();
    } catch (e) { alert(e.message); }
}

async function collectGlobalMarket() {
    try {
        await fetch('/api/global-market/collect', { method: 'POST' });
        alert('Global market collection started');
    } catch (e) { alert(e.message); }
}

async function testTelegram() {
    try {
        const res = await fetch('/api/telegram/test', { method: 'POST' });
        const data = await res.json();
        alert(data.success ? 'Telegram test sent!' : 'Telegram test failed');
    } catch (e) { alert(e.message); }
}

let collectionLogWs = null;
let collectionLogConnected = false;

function toggleCollectionLogStream() {
    if (collectionLogConnected) {
        disconnectCollectionLogStream();
    } else {
        connectCollectionLogStream();
    }
}

function connectCollectionLogStream() {
    if (collectionLogWs) collectionLogWs.close();

    const container = document.getElementById('realtimeLogs');
    container.innerHTML = '<div class="text-gray-500">Connecting...</div>';

    const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    collectionLogWs = new WebSocket(`${wsProtocol}//${location.host}/ws/collection-logs`);

    collectionLogWs.onopen = () => {
        collectionLogConnected = true;
        updateLogConnectionUI(true);
        container.innerHTML = '<div class="text-accent-green">Connected. Waiting for logs...</div>';
    };

    collectionLogWs.onmessage = e => {
        try {
            const log = JSON.parse(e.data);
            const line = document.createElement('div');
            line.className = `py-0.5 ${log.level === 'ERROR' ? 'text-accent-red' : 'text-gray-300'}`;
            line.textContent = `[${log.timestamp}] ${log.message}`;

            const firstChild = container.firstElementChild;
            if (firstChild && firstChild.textContent.includes('Connected. Waiting')) {
                container.innerHTML = '';
            }

            container.appendChild(line);
            container.scrollTop = container.scrollHeight;

            while (container.children.length > 200) {
                container.removeChild(container.firstChild);
            }
        } catch (err) {
            console.error('Failed to parse log:', err);
        }
    };

    collectionLogWs.onclose = () => {
        collectionLogConnected = false;
        updateLogConnectionUI(false);
        const disc = document.createElement('div');
        disc.className = 'text-accent-red py-0.5';
        disc.textContent = '[Disconnected]';
        container.appendChild(disc);
    };

    collectionLogWs.onerror = () => {
        collectionLogConnected = false;
        updateLogConnectionUI(false);
    };
}

function disconnectCollectionLogStream() {
    if (collectionLogWs) {
        collectionLogWs.close();
        collectionLogWs = null;
    }
    collectionLogConnected = false;
    updateLogConnectionUI(false);
}

function updateLogConnectionUI(connected) {
    const statusEl = document.getElementById('logConnectionStatus');
    const btnEl = document.getElementById('btnToggleLogStream');

    if (connected) {
        statusEl.textContent = 'Connected';
        statusEl.className = 'px-2 py-1 text-xs rounded bg-accent-green text-white';
        btnEl.textContent = t('disconnect') || 'Disconnect';
        btnEl.className = 'px-3 py-1 text-xs bg-accent-red hover:bg-red-600 text-white rounded';
    } else {
        statusEl.textContent = 'Disconnected';
        statusEl.className = 'px-2 py-1 text-xs rounded bg-dark-700 text-gray-500';
        btnEl.textContent = t('connect') || 'Connect';
        btnEl.className = 'px-3 py-1 text-xs bg-accent-green hover:bg-green-600 text-white rounded';
    }
}

function clearCollectionLogs() {
    const container = document.getElementById('realtimeLogs');
    if (collectionLogConnected) {
        container.innerHTML = '<div class="text-accent-green">Connected. Waiting for logs...</div>';
    } else {
        container.innerHTML = '<div class="text-gray-600" data-i18n="click_connect">Click Connect to start streaming logs</div>';
        applyTranslations();
    }
}

function openLoginModal() {
    document.getElementById('modal-login').classList.remove('hidden');
}

function closeLoginModal() {
    document.getElementById('modal-login').classList.add('hidden');
}

document.getElementById('loginForm').addEventListener('submit', (e) => {
    e.preventDefault();
    const username = document.getElementById('loginUsername').value;
    // Mock login logic
    alert(`Login attempt for user: ${username}`);
    closeLoginModal();
});

fetchStatus();
fetchStates();
setInterval(fetchStatus, 5000);
setInterval(fetchStates, 10000);
applyTranslations();
// WebSocket for History Logs
let historyLogWs = null;
let historyLogConnected = false;

function connectHistoryLogStream() {
    if (historyLogWs) return;

    const container = document.getElementById('historyLogs');
    if (!container) return; // Guard in case element doesn't exist yet

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

document.getElementById('btnClearHistoryLogs')?.addEventListener('click', () => {
    const container = document.getElementById('historyLogs');
    if (container) container.innerHTML = '<div class="text-gray-600 italic text-center py-10">Logs will appear here...</div>';
});

// Initialize connection
// Use timeout to ensure DOM is ready if script is at bottom
setTimeout(connectHistoryLogStream, 1000);

// Append History Logic
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

document.getElementById('historyForm').addEventListener('submit', async e => {
    e.preventDefault();
    const btn = e.target.querySelector('button');
    const originalText = document.getElementById('histBtnText').textContent;

    const ticker = document.getElementById('histTicker').value;
    const start = document.getElementById('histStart').value;
    const end = document.getElementById('histEnd').value;
    const time = document.getElementById("histTime").value;
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
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticker, start_date: start, end_date: end, timeframe, time })
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

const bulkSelectedTickers = new Map();

function openBulkStockSearch() {
    document.getElementById('modal-bulk-stock-search').classList.remove('hidden');
    document.getElementById('bulkSearchInput').focus();
}

function closeBulkStockSearch() {
    document.getElementById('modal-bulk-stock-search').classList.add('hidden');
}

async function searchBulkStocks(query) {
    if (!query || query.length < 1) {
        document.getElementById('bulkSearchResults').innerHTML = '<div class="text-center text-gray-500 py-4">Type to search</div>';
        return;
    }
    try {
        const res = await fetch(`/api/stocks/search?q=${encodeURIComponent(query)}&limit=20`);
        const data = await res.json();
        const stocks = data.stocks || data;
        if (!stocks || !stocks.length) {
            document.getElementById('bulkSearchResults').innerHTML = '<div class="text-center text-gray-500 py-4">No results</div>';
            return;
        }
        document.getElementById('bulkSearchResults').innerHTML = stocks.map(s => `
                <div class="flex justify-between items-center p-2 hover:bg-dark-700 rounded cursor-pointer" onclick="toggleBulkTicker('${s.ticker}', '${s.name}')">
                    <div>
                        <span class="text-white font-medium">${s.ticker}</span>
                        <span class="text-gray-400 text-sm ml-2">${s.name}</span>
                    </div>
                    <span class="text-lg ${bulkSelectedTickers.has(s.ticker) ? 'text-accent-green' : 'text-gray-600'}">${bulkSelectedTickers.has(s.ticker) ? '✓' : '+'}</span>
                </div>
            `).join('');
    } catch (e) {
        console.error(e);
    }
}

function toggleBulkTicker(ticker, name) {
    if (bulkSelectedTickers.has(ticker)) {
        bulkSelectedTickers.delete(ticker);
    } else {
        bulkSelectedTickers.set(ticker, name);
    }
    updateBulkTickerTags();
    searchBulkStocks(document.getElementById('bulkSearchInput').value);
}

function removeBulkTicker(ticker) {
    bulkSelectedTickers.delete(ticker);
    updateBulkTickerTags();
}

function updateBulkTickerTags() {
    const container = document.getElementById('bulkTickerTags');
    if (bulkSelectedTickers.size === 0) {
        container.innerHTML = '<span class="text-xs text-gray-600">Click + to add</span>';
        return;
    }
    container.innerHTML = Array.from(bulkSelectedTickers.entries()).map(([ticker, name]) => `
            <span class="inline-flex items-center gap-1 px-2 py-1 bg-accent-green/20 text-accent-green text-xs rounded-full">
                ${ticker}
                <button onclick="removeBulkTicker('${ticker}')" class="hover:text-white">×</button>
            </span>
        `).join('');
}

async function collectBulk() {
    if (bulkSelectedTickers.size === 0) {
        alert('Add at least one stock');
        return;
    }

    const tickers = Array.from(bulkSelectedTickers.keys());
    const timeframes = [];
    if (document.getElementById('bulk1m').checked) timeframes.push('1m');
    if (document.getElementById('bulkD').checked) timeframes.push('D');
    if (document.getElementById('bulkW').checked) timeframes.push('W');
    if (document.getElementById('bulkM').checked) timeframes.push('M');

    if (timeframes.length === 0) {
        alert('Select at least one timeframe');
        return;
    }

    const today = new Date();
    const endDate = today.toISOString().slice(0, 10).replace(/-/g, '');
    const startDate = new Date(today.setFullYear(today.getFullYear() - 1)).toISOString().slice(0, 10).replace(/-/g, '');

    const btn = document.getElementById('bulkBtnText');
    const progress = document.getElementById('bulkProgress');

    try {
        btn.textContent = 'Collecting...';
        progress.classList.remove('hidden');
        progress.textContent = `0/${tickers.length} stocks`;

        const res = await fetch('/api/history/collect-bulk-sync', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tickers, start_date: startDate, end_date: endDate, timeframes })
        });

        const result = await res.json();
        progress.textContent = `Done! ${result.total_records} records collected`;
        alert(`Collected ${result.total_records} records for ${tickers.length} stocks`);
        loadHistoryOverview();
    } catch (e) {
        alert('Error: ' + e.message);
    } finally {
        btn.textContent = 'Collect 1 Year';
    }
}

async function loadHistoryOverview() {
    const tbody = document.getElementById('histOverviewBody');
    tbody.innerHTML = '<tr><td colspan="6" class="px-3 py-4 text-center text-gray-600">Loading...</td></tr>';

    try {
        const res = await fetch('/api/history/overview');
        const data = await res.json();

        if (!data.summary || !data.summary.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="px-3 py-4 text-center text-gray-600">No data collected yet</td></tr>';
            return;
        }

        tbody.innerHTML = data.summary.map(r => `
                <tr class="hover:bg-dark-700">
                    <td class="px-3 py-2 text-accent-blue font-medium">${r.ticker}</td>
                    <td class="px-3 py-2 text-gray-300">${r.name}</td>
                    <td class="px-3 py-2"><span class="px-1.5 py-0.5 rounded text-xs ${r.timeframe === '1m' ? 'bg-accent-yellow/20 text-accent-yellow' : 'bg-dark-700'}">${r.timeframe}</span></td>
                    <td class="px-3 py-2 text-right text-gray-400">${r.count.toLocaleString()}</td>
                    <td class="px-3 py-2 text-gray-500 text-xs">${r.start_date.split(' ')[0]} ~ ${r.end_date.split(' ')[0]}</td>
                    <td class="px-3 py-2 text-center">
                        <button onclick="openHistoryViewer('${r.ticker}', '${r.name}')" class="px-2 py-1 text-xs bg-accent-blue/20 hover:bg-accent-blue text-accent-blue hover:text-white rounded transition">View</button>
                    </td>
                </tr>
            `).join('');
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="6" class="px-3 py-4 text-center text-accent-red">${e.message}</td></tr>`;
    }
}
let currentHistTicker = '';
let currentHistTimeframe = 'D';

function openHistoryViewer(ticker, name) {
    currentHistTicker = ticker;
    currentHistTimeframe = 'D';

    document.getElementById('histViewTitle').textContent = name || ticker;
    document.getElementById('histViewSubtitle').textContent = ticker;
    document.getElementById('modal-history-viewer').classList.remove('hidden');

    // Close search modal if open
    document.getElementById('modal-stock-search').classList.add('hidden');

    switchHistTab('D'); // Load default
}

function closeHistoryViewer() {
    document.getElementById('modal-history-viewer').classList.add('hidden');
}

function switchHistTab(tf) {
    currentHistTimeframe = tf;
    // Update UI
    ['1m', 'D', 'W', 'M'].forEach(t => {
        const tab = document.getElementById(`tab-hist-${t}`);
        if (t === tf) {
            tab.className = "px-4 py-2 text-sm text-accent-blue border-b-2 border-accent-blue font-medium";
        } else {
            tab.className = "px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors border-b-2 border-transparent";
        }
    });
    loadHistoryViewData();
}

async function refreshHistoryData() {
    if (!currentHistTicker) return;

    const btn = document.querySelector('#modal-history-viewer button[onclick="refreshHistoryData()"]');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span>...</span> Collecting';

    try {
        // Determine dates
        const today = new Date();
        const endStr = today.toISOString().slice(0, 10).replace(/-/g, "");
        const start = new Date(today);
        start.setMonth(start.getMonth() - 6); // 6 months back default
        const startStr = start.toISOString().slice(0, 10).replace(/-/g, "");

        const res = await fetch('/api/history/collect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ticker: currentHistTicker,
                start_date: startStr,
                end_date: endStr,
                timeframe: currentHistTimeframe
            })
        });

        if (res.ok) {
            loadHistoryViewData();
        } else {
            alert('Collection failed');
        }
    } catch (e) {
        console.error(e);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

async function loadHistoryViewData() {
    const tbody = document.getElementById('histViewBody');
    tbody.innerHTML = '<tr><td colspan="6" class="px-4 py-8 text-center text-gray-600">Loading...</td></tr>';

    try {
        const limit = currentHistTimeframe === '1m' ? 500 : 200;
        const res = await fetch(`/api/history/${currentHistTicker}?timeframe=${currentHistTimeframe}&limit=${limit}`);
        const data = await res.json();

        if (!data.history || !data.history.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="px-4 py-8 text-center text-gray-600">No data. Click Refresh to collect.</td></tr>';
            return;
        }

        let rows = data.history;
        if (currentHistTimeframe === '1m') {
            rows = rows.slice().sort((a, b) => a.datetime.localeCompare(b.datetime));
        }

        tbody.innerHTML = rows.map(r => `
                    <tr class="hover:bg-dark-700 transition-colors">
                        <td class="px-4 py-2 font-mono text-gray-400 text-xs">${r.datetime}</td>
                        <td class="px-4 py-2 text-right">${r.open.toLocaleString()}</td>
                        <td class="px-4 py-2 text-right">${r.high.toLocaleString()}</td>
                        <td class="px-4 py-2 text-right">${r.low.toLocaleString()}</td>
                        <td class="px-4 py-2 text-right font-medium ${r.close >= r.open ? 'text-accent-red' : 'text-accent-blue'}">${r.close.toLocaleString()}</td>
                        <td class="px-4 py-2 text-right text-gray-500 text-xs">${r.volume.toLocaleString()}</td>
                    </tr>
                `).join('');
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="6" class="px-4 py-8 text-center text-accent-red">${e.message}</td></tr>`;
    }
}

// Override renderSearchResults to add History Button
// We inject this into the existing script by redefining the function if possible,
// or we modify the HTML file to update the function.
// For robustness, let's update the original renderSearchResults in the file.
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
// Scheduler Logic Override
function startScheduler() {
    // Open Modal instead of direct call
    document.getElementById('modal-scheduler-time').classList.remove('hidden');
}

async function confirmSchedulerStart() {
    const hour = parseInt(document.getElementById('schedHour').value);
    const minute = parseInt(document.getElementById('schedMinute').value);

    if (hour < 0 || hour > 23 || minute < 0 || minute > 59) {
        alert('Invalid time');
        return;
    }

    try {
        const res = await fetch(`/api/admin/scheduler/start?hour=${hour}&minute=${minute}`, { method: 'POST' });
        if (res.ok) {
            document.getElementById('modal-scheduler-time').classList.add('hidden');
            loadAdminData(); // Refresh admin panel data
            alert('Scheduler started successfully!');
        } else {
            alert('Failed to start scheduler');
        }
    } catch (e) {
        console.error(e);
        alert(e.message);
    }
}

async function loadSchedulerStatus() {
    // Alias for loadAdminData to maintain compatibility
    await loadAdminData();
}
// Coverage Map Logic
async function loadCoverageData(timeframeOverride = null) {
    const container = document.getElementById('coverageCalendar');
    container.innerHTML = '<div class="text-center text-gray-500 py-10">Loading map...</div>';

    try {
        // Use override if provided (e.g. 'H'), otherwise use current (e.g. 'D' for coverage tab)
        const tf = timeframeOverride || currentHistTimeframe;
        const res = await fetch(`/api/history/coverage/${currentHistTicker}?timeframe=${tf}`);
        const data = await res.json();
        const dateSet = new Set(data.dates);

        renderCalendarHeatmap(dateSet);
    } catch (e) {
        container.innerHTML = `<div class="text-center text-accent-red py-10">${e.message}</div>`;
    }
}

function renderCalendarHeatmap(dateSet) {
    const container = document.getElementById('coverageCalendar');
    container.innerHTML = '';

    const today = new Date();
    const yearAgo = new Date(today);
    yearAgo.setFullYear(today.getFullYear() - 1);

    // Group by month
    let currentMonth = new Date(yearAgo.getFullYear(), yearAgo.getMonth(), 1);
    const endMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0);

    const grid = document.createElement('div');
    grid.className = 'grid grid-cols-3 md:grid-cols-4 gap-4';

    while (currentMonth <= endMonth) {
        const monthDiv = document.createElement('div');
        monthDiv.className = 'bg-dark-800/50 p-3 rounded-lg border border-dark-700';

        const monthName = currentMonth.toLocaleString('default', { month: 'short', year: 'numeric' });
        monthDiv.innerHTML = `<div class="text-xs font-bold text-gray-400 mb-2">${monthName}</div>`;

        const daysGrid = document.createElement('div');
        daysGrid.className = 'grid grid-cols-7 gap-1 text-[10px] text-center';

        // Weekday headers
        ['S', 'M', 'T', 'W', 'T', 'F', 'S'].forEach(d => {
            daysGrid.innerHTML += `<div class="text-gray-600">${d}</div>`;
        });

        // Days
        const year = currentMonth.getFullYear();
        const month = currentMonth.getMonth();
        const firstDay = new Date(year, month, 1).getDay();
        const daysInMonth = new Date(year, month + 1, 0).getDate();

        // Padding
        for (let i = 0; i < firstDay; i++) {
            daysGrid.innerHTML += `<div></div>`;
        }

        for (let d = 1; d <= daysInMonth; d++) {
            const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
            const hasData = dateSet.has(dateStr);
            const isToday = (dateStr === today.toISOString().slice(0, 10));

            let bgClass = hasData ? 'bg-accent-green hover:bg-green-400' : 'bg-dark-700 hover:bg-dark-600';
            if (isToday) bgClass += ' ring-1 ring-white';

            daysGrid.innerHTML += `
                    <div class="w-full aspect-square rounded-sm ${bgClass} cursor-pointer transition-colors" 
                         title="${dateStr}: ${hasData ? 'Collected' : 'No Data'}">
                    </div>`;
        }

        monthDiv.appendChild(daysGrid);
        grid.appendChild(monthDiv);

        currentMonth.setMonth(currentMonth.getMonth() + 1);
    }

    container.appendChild(grid);
}

// Hook into tab switching
const originalSwitchHistTab = window.switchHistTab; // Save original function if possible or overwrite smart
window.switchHistTab = function (tf) {
    currentHistTimeframe = (tf === 'C' || tf === 'H') ? 'D' : tf; // Default to Daily for coverage view logic if 'C' or 'H' selected

    // Tab Styles
    ['1m', 'D', 'W', 'M', 'C', 'H'].forEach(t => {
        const tab = document.getElementById(`tab-hist-${t}`);
        if (tab) {
            if (t === tf) {
                tab.className = "px-4 py-2 text-sm text-accent-blue border-b-2 border-accent-blue font-medium";
            } else {
                tab.className = "px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors border-b-2 border-transparent";
            }
        }
    });

    const tableView = document.querySelector('#modal-history-viewer table').parentNode; // The scrollable div
    const coverageView = document.getElementById('histCoverageView');

    if (tf === 'C' || tf === 'H') {
        tableView.classList.add('hidden');
        coverageView.classList.remove('hidden');

        // Set title based on type
        const titleEl = coverageView.querySelector('h4');
        if (tf === 'H') {
            titleEl.textContent = 'Human Index Availability Heatmap (Last 1 Year)';
            // Change logic to load human index coverage
            loadCoverageData('H');
        } else {
            titleEl.textContent = 'Data Availability Heatmap (Last 1 Year)';
            loadCoverageData('D');
        }
    } else {
        tableView.classList.remove('hidden');
        coverageView.classList.add('hidden');
        loadHistoryViewData();
    }
};

let currentSectorData = null;

async function loadSavedSectors() {
    try {
        const res = await fetch('/api/global/sectors');
        const data = await res.json();
        const list = document.getElementById('savedSectorsList');
        if (!data.sectors || !data.sectors.length) {
            list.innerHTML = '<div class="text-center text-gray-600 py-4">No saved sectors</div>';
            return;
        }
        list.innerHTML = data.sectors.map(s => `
                <div onclick="openSector('${s.sector_name}')" class="p-3 bg-dark-900 rounded cursor-pointer hover:bg-dark-700 transition border border-transparent hover:border-accent-blue group">
                    <div class="font-medium text-white group-hover:text-accent-blue">${s.sector_name}</div>
                    <div class="text-xs text-gray-500 mt-1">${new Date(s.updated_at).toLocaleString()}</div>
                </div>
            `).join('');
    } catch (e) {
        console.error(e);
    }
}

async function openSector(sector) {
    document.getElementById('sectorInput').value = sector;
    loadSectorLeaders(false);
}

async function loadSectorLeaders(forceRefresh = false) {
    const sector = document.getElementById('sectorInput').value.trim();
    if (!sector) return;

    const container = document.getElementById('sectorResults');
    container.innerHTML = `<div class="col-span-4 text-center py-12 text-gray-500">${forceRefresh ? 'Regenerating' : 'Analyzing'} global market... This may take up to 30 seconds.</div>`;

    try {
        const res = await fetch('/api/global/sector-leaders', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sector: sector, force_refresh: forceRefresh })
        });

        if (!res.ok) {
            let errorMsg = 'Analysis failed';
            try {
                const err = await res.json();
                errorMsg = err.detail || errorMsg;
            } catch (e) { }
            throw new Error(`${res.status} ${res.statusText}: ${errorMsg}`);
        }
        const data = await res.json();
        currentSectorData = data;
        renderSectorResults(data);
        loadSavedSectors(); // Refresh list
    } catch (e) {
        container.innerHTML = `<div class="col-span-4 text-center py-12 text-accent-red">Error: ${e.message}</div>`;
    }
}

function renderSectorResults(data) {
    const container = document.getElementById('sectorResults');
    if (!data) return;

    const regions = [
        { code: 'KR', name: 'South Korea 🇰🇷' },
        { code: 'US', name: 'United States 🇺🇸' },
        { code: 'JP', name: 'Japan 🇯🇵' },
        { code: 'CN', name: 'China 🇨🇳' }
    ];

    let html = regions.map(r => `
            <div class="glass rounded-lg p-4 border border-dark-600">
                <h3 class="text-lg font-bold text-white mb-4 border-b border-dark-600 pb-2">${r.name}</h3>
                <div class="space-y-3">
                    ${(data[r.code] || []).map(stock => `
                        <div class="p-3 bg-dark-900 rounded border ${stock.type === 'Vendor' ? 'border-accent-purple' : 'border-dark-700'} hover:border-accent-blue transition group relative">
                            ${stock.type === 'Vendor' ? `<div class="absolute -top-2 -right-2 bg-accent-purple text-white text-[10px] px-1.5 py-0.5 rounded shadow">Vendor</div>` : ''}
                            <div class="flex justify-between items-start mb-1">
                                <div class="font-bold text-accent-blue group-hover:text-blue-400">${stock.ticker}</div>
                                <div class="text-xs text-gray-500 bg-dark-800 px-1.5 py-0.5 rounded">${stock.type || 'Leader'}</div>
                            </div>
                            <div class="font-medium text-sm text-gray-200 mb-1">${stock.name}</div>
                            ${stock.related_to && stock.related_to !== 'Self' ? `<div class="text-xs text-purple-400 mb-1">🔗 ${stock.related_to}</div>` : ''}
                            ${stock.logic ? `<div class="text-[10px] text-gray-400 bg-dark-800 p-1 rounded italic mt-1">💡 ${stock.logic}</div>` : ''}
                        </div>
                    `).join('')}
                </div>
            </div>
        `).join('');

    // Add Edit & Regenerate Buttons
    html += `
            <div class="col-span-4 flex justify-between mt-4 pt-4 border-t border-dark-600">
                <div class="flex gap-2">
                    <button onclick="loadSectorLeaders(true)" class="px-6 py-2 bg-dark-800 hover:bg-dark-700 text-accent-yellow font-medium rounded-md transition flex items-center gap-2 border border-dark-600 hover:border-accent-yellow">
                        <span>↻ Regenerate with AI</span>
                    </button>
                    <button onclick="collectSectorData()" class="px-6 py-2 bg-accent-purple hover:bg-purple-600 text-white font-medium rounded-md transition flex items-center gap-2">
                        <span>📥 Collect Data (1Y)</span>
                    </button>
                </div>
                <button onclick="openEditSectorModal()" class="px-6 py-2 bg-dark-700 hover:bg-dark-600 text-white font-medium rounded-md transition flex items-center gap-2">
                    <span>✏️ Edit Analysis</span>
                </button>
            </div>
        `;

    container.innerHTML = html;
}

async function collectSectorData() {
    if (!currentSectorData) return;

    if (!confirm(`Start collecting 1 year historical data for all companies in '${currentSectorData.sector}'? This may take a while.`)) return;

    try {
        const res = await fetch('/api/history/collect-sector', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sector: currentSectorData.sector, data: currentSectorData })
        });

        if (!res.ok) throw new Error('Request failed');
        const result = await res.json();
        alert(`Started! ${result.message}\nCheck 'Data Tool' or logs for progress.`);
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

let opentalkChartInstance = null;

function renderOpentalkChart(history) {
    const ctx = document.getElementById('opentalkTrendChart').getContext('2d');
    if (opentalkChartInstance) opentalkChartInstance.destroy();

    // Sort by date
    const sorted = history.slice().sort((a, b) => a.date.localeCompare(b.date));
    const dates = sorted.map(h => h.date);
    const data = sorted.map(h => h.user_count);

    opentalkChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: dates,
            datasets: [{
                label: 'Participants',
                data: data,
                borderColor: '#22c55e', // accent-green
                backgroundColor: 'rgba(34, 197, 94, 0.1)',
                borderWidth: 2,
                tension: 0.3,
                fill: true,
                pointRadius: 3,
                pointHoverRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(22, 27, 34, 0.9)',
                    titleColor: '#e5e7eb',
                    bodyColor: '#e5e7eb',
                    borderColor: '#374151',
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    display: true,
                    grid: { display: false, color: '#374151' },
                    ticks: { color: '#9ca3af', maxTicksLimit: 10 }
                },
                y: {
                    display: true,
                    grid: { color: 'rgba(55, 65, 81, 0.3)' },
                    ticks: { color: '#9ca3af' }
                }
            }
        }
    });
}

function openEditSectorModal() {
    if (!currentSectorData) return;

    const modal = document.getElementById('modal-sector-edit');
    const container = document.getElementById('editSectorContainer');
    document.getElementById('editSectorName').value = currentSectorData.sector;

    const regions = ['KR', 'US', 'JP', 'CN'];

    container.innerHTML = regions.map(code => `
            <div class="bg-dark-900/50 p-4 rounded-lg border border-dark-600">
                <h4 class="font-bold text-accent-yellow mb-3">${code} Companies</h4>
                <div id="edit-${code}" class="space-y-4">
                    ${(currentSectorData[code] || []).map((stock, idx) => `
                        <div class="grid grid-cols-12 gap-2 items-start bg-dark-800 p-2 rounded">
                            <div class="col-span-2">
                                <label class="text-[10px] text-gray-500">Ticker</label>
                                <input type="text" value="${stock.ticker}" class="w-full bg-dark-900 border border-dark-600 rounded px-2 py-1 text-xs text-accent-blue font-bold" data-field="ticker">
                            </div>
                            <div class="col-span-3">
                                <label class="text-[10px] text-gray-500">Name</label>
                                <input type="text" value="${stock.name}" class="w-full bg-dark-900 border border-dark-600 rounded px-2 py-1 text-xs" data-field="name">
                            </div>
                            <div class="col-span-6">
                                <label class="text-[10px] text-gray-500">Reason</label>
                                <textarea class="w-full bg-dark-900 border border-dark-600 rounded px-2 py-1 text-xs h-16" data-field="reason">${stock.reason}</textarea>
                            </div>
                            <div class="col-span-1 flex justify-center items-center h-full pt-4">
                                <button type="button" onclick="this.parentElement.parentElement.remove()" class="text-gray-500 hover:text-accent-red text-lg">×</button>
                            </div>
                        </div>
                    `).join('')}
                </div>
                <button type="button" onclick="addCompanyRow('${code}')" class="mt-2 text-xs text-accent-green hover:underline">+ Add Company</button>
            </div>
        `).join('');

    modal.classList.remove('hidden');
}

function addCompanyRow(code) {
    const container = document.getElementById(`edit-${code}`);
    const div = document.createElement('div');
    div.className = 'grid grid-cols-12 gap-2 items-start bg-dark-800 p-2 rounded';
    div.innerHTML = `
            <div class="col-span-2">
                <label class="text-[10px] text-gray-500">Ticker</label>
                <input type="text" value="" class="w-full bg-dark-900 border border-dark-600 rounded px-2 py-1 text-xs text-accent-blue font-bold" data-field="ticker">
            </div>
            <div class="col-span-3">
                <label class="text-[10px] text-gray-500">Name</label>
                <input type="text" value="" class="w-full bg-dark-900 border border-dark-600 rounded px-2 py-1 text-xs" data-field="name">
            </div>
            <div class="col-span-6">
                <label class="text-[10px] text-gray-500">Reason</label>
                <textarea class="w-full bg-dark-900 border border-dark-600 rounded px-2 py-1 text-xs h-16" data-field="reason"></textarea>
            </div>
            <div class="col-span-1 flex justify-center items-center h-full pt-4">
                <button type="button" onclick="this.parentElement.parentElement.remove()" class="text-gray-500 hover:text-accent-red text-lg">×</button>
            </div>
        `;
    container.appendChild(div);
}

function closeEditSectorModal() {
    document.getElementById('modal-sector-edit').classList.add('hidden');
}

document.getElementById('sectorEditForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const sectorName = document.getElementById('editSectorName').value;
    const newData = { sector: sectorName };

    ['KR', 'US', 'JP', 'CN'].forEach(code => {
        newData[code] = [];
        const rows = document.getElementById(`edit-${code}`).children;
        for (let row of rows) {
            newData[code].push({
                ticker: row.querySelector('[data-field="ticker"]').value,
                name: row.querySelector('[data-field="name"]').value,
                reason: row.querySelector('[data-field="reason"]').value
            });
        }
    });

    try {
        const res = await fetch('/api/global/sector-leaders', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sector: sectorName, data: newData })
        });

        if (!res.ok) throw new Error('Update failed');

        currentSectorData = newData;
        renderSectorResults(newData);
        closeEditSectorModal();
        loadSavedSectors(); // Update timestamp in list
    } catch (e) {
        alert('Failed to save changes: ' + e.message);
    }
});

