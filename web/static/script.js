const API_URL = '/api';
let token = localStorage.getItem('token');
let ws = null;
let bots = [];
let selectedBotId = null;

// On Load
document.addEventListener('DOMContentLoaded', () => {
    if (token) {
        initDashboard();
    } else {
        document.getElementById('loginModal').style.display = 'block';
    }

    // Update time
    setInterval(() => {
        const timeEl = document.getElementById('currentTime');
        if (timeEl) timeEl.innerText = new Date().toLocaleString();
    }, 1000);
});

// Utils
function escapeHtml(text) {
    if (!text) return text;
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Auth
async function login() {
    const password = document.getElementById('passwordInput').value;
    const credentials = btoa(`user:${password}`);
    token = `Basic ${credentials}`;

    try {
        await api('GET', '/bots'); // Test auth
        localStorage.setItem('token', token);
        document.getElementById('loginModal').style.display = 'none';
        initDashboard();
    } catch (e) {
        document.getElementById('loginError').innerText = '로그인 실패: 비밀번호를 확인하세요.';
        token = null;
    }
}

async function api(method, endpoint, body = null) {
    const headers = {
        'Authorization': token,
        'Content-Type': 'application/json'
    };

    const options = { method, headers };
    if (body) options.body = JSON.stringify(body);

    const res = await fetch(`${API_URL}${endpoint}`, options);
    if (res.status === 401) {
        localStorage.removeItem('token');
        location.reload();
        throw new Error('Unauthorized');
    }
    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'API Error');
    }
    return res.json();
}

// Dashboard Init
async function initDashboard() {
    document.getElementById('dashboard').classList.remove('hidden');
    updateEnvBadge();
    connectWebSocket();
    loadBots();
    loadScreenerStatus();
}

function updateEnvBadge() {
    const port = window.location.port;
    const badge = document.getElementById('envBadge');
    if (!badge) return;

    if (port === '8081') {
        badge.innerText = 'Dev (8081)';
        badge.className = 'env-badge dev';
        badge.title = '개발 환경: 실시간 코드 반영용 (테스트)';
    } else if (port === '8080') {
        badge.innerText = 'Staging (8080)';
        badge.className = 'env-badge staging';
        badge.title = '스테이징 환경: 상시 운영 및 안정성 검증용';
    } else {
        badge.innerText = 'Local';
        badge.className = 'env-badge';
    }
}

// Tab Management
function showTab(tabId) {
    // Buttons
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.getElementById(`tab-${tabId}`).classList.add('active');

    // Sections
    document.querySelectorAll('.tab-content').forEach(section => section.classList.remove('active'));
    document.getElementById(`${tabId}-section`).classList.add('active');

    // If switching to dashboard, maybe refresh bots
    if (tabId === 'dashboard') {
        loadBots();
    }
}


// WebSocket
function connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${location.host}/ws`);

    ws.onopen = () => {
        console.log('Connected to WebSocket');
        const statusEl = document.getElementById('connectionStatus');
        if (statusEl) statusEl.className = 'status-dot connected';
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'status') {
            bots = data.bots;
            renderBots();
        } else if (data.type === 'log') {
            console.log(`Received ${data.lines.length} log lines for ${data.bot_id}`);
            // Append real-time logs if viewing the specific bot
            if (selectedBotId === data.bot_id) {
                appendLogs(data.lines);
            }
        }
    };

    ws.onclose = () => {
        console.log('Disconnected');
        const statusEl = document.getElementById('connectionStatus');
        if (statusEl) statusEl.className = 'status-dot disconnected';
        setTimeout(connectWebSocket, 3000);
    };
}

// Bot Management
async function loadBots() {
    try {
        bots = await api('GET', '/bots');
        renderBots();
    } catch (e) {
        console.error(e);
    }
}

function renderBots() {
    const container = document.getElementById('botCards');
    const emptyState = document.getElementById('emptyState');

    if (bots.length === 0) {
        container.innerHTML = '';
        container.appendChild(emptyState);
        emptyState.style.display = 'block';
        return;
    }

    emptyState.style.display = 'none';
    container.innerHTML = '';
    container.appendChild(emptyState); // Keep it hidden

    bots.forEach(bot => {
        const card = document.createElement('div');
        card.className = `bot-card ${bot.status.toLowerCase()}`;
        if (selectedBotId === bot.id) card.classList.add('selected');

        const activeStates = ['RUNNING', 'SEARCHING', 'HOLDING', 'BUYING', 'SELLING'];
        const isRunning = activeStates.includes(bot.status.toUpperCase());
        const modeBadge = bot.live ?
            '<span class="mode-badge live">🔴 실전</span>' :
            '<span class="mode-badge paper">⚪ 모의</span>';

        // Badges for options
        let optionBadges = '';
        if (bot.orderbook) optionBadges += '<span class="badge-option">Orderbook</span>';
        if (bot.momentum) optionBadges += '<span class="badge-option">Momentum</span>';

        const buyPrices = bot.buy_prices || (bot.buy_price > 0 ? [bot.buy_price] : []);
        if (buyPrices.length > 0) {
            const firstPrice = buyPrices[0].toLocaleString();
            optionBadges += `<span class="badge-option">Buy@${firstPrice}${buyPrices.length > 1 ? `(+${buyPrices.length - 1})` : ''}</span>`;
        }
        if (optionBadges) optionBadges = `<div class="option-badges">${optionBadges}</div>`;

        let heartbeat = '⚫'; // Default Black (Stopped)
        let heartbeatTitle = '정지됨';

        if (bot.status === 'RUNNING') {
            const now = new Date();
            // Parse UTC string to local date logic if needed, but browser handles ISO string well
            const last = bot.last_update ? new Date(bot.last_update) : null;
            const diff = last ? (now - last) / 1000 : 9999;

            if (diff < 20) {
                heartbeat = '🟢';
                heartbeatTitle = '정상 작동 (20초 이내)';
            } else if (diff < 60) {
                heartbeat = '🟡';
                heartbeatTitle = '지연 (1분 이내)';
            } else {
                heartbeat = '🔴';
                heartbeatTitle = '응답 없음 (1분 이상)';
            }
        }

        card.innerHTML = `
            <div class="card-header">
                <h3>${bot.ticker === bot.ticker_code ? bot.ticker : `${bot.ticker} (${bot.ticker_code || ''})`}</h3>
                ${modeBadge}
            </div>
            ${optionBadges}
            <div class="card-status">
                <span class="status-indicator" title="${heartbeatTitle}">${heartbeat} ${bot.status}</span>
                <span class="profit ${bot.profit_rate >= 0 ? 'positive' : 'negative'}">
                    ${(bot.profit_rate * 100).toFixed(2)}%
                </span>
            </div>
            <div class="card-options">
                ${bot.orderbook ? '<span class="badge badge-info">호가창</span>' : ''}
                ${bot.momentum ? '<span class="badge badge-accent">모멘텀</span>' : ''}
                ${bot.ignore_market ? '<span class="badge badge-error">24h</span>' : ''}
                ${buyPrices.map(p => `<span class="badge badge-warning">${Math.round(p).toLocaleString()}원 지정가</span>`).join('')}
                ${!bot.live ? '<span class="badge badge-secondary">테스트</span>' : ''}
            </div>

            <div class="card-details">
                <div class="detail-row">
                    <span>예산</span>
                    <span class="budget-value">${(bot.budget || 0).toLocaleString()}원</span>
                </div>
                <div class="detail-row">
                    <span>현재가</span>
                    <span>
                        ${Math.round(bot.current_price || 0).toLocaleString()}원
                        <small class="text-muted" style="margin-left:4px; font-size:0.8em;">[${bot.current_exchange || 'KRX'}]</small>
                    </span>
                </div>
                <div class="detail-row">
                    <span>마지막 확인</span>
                    <span style="font-size:0.8em; color:#888;">${bot.last_update ? new Date(bot.last_update).toLocaleTimeString() : '-'}</span>
                </div>
                <div class="detail-row">
                    <span>평단가</span>
                    <span>${Math.round(bot.avg_price || 0).toLocaleString()}원</span>
                </div>
                <div class="detail-row">
                    <span>보유량</span>
                    <span>${bot.total_qty?.toLocaleString()}주</span>
                </div>
                <div class="detail-row">
                    <span>목표가</span>
                    <span>${Math.round(bot.avg_price * (1 + bot.target)).toLocaleString()}원 <small class="target-percent">(${(bot.target * 100).toFixed(1)}%)</small></span>
                </div>
                <div class="detail-row">
                    <span>추가 매수</span>
                    <span>평단가 -${(bot.pyramiding_threshold * 100).toFixed(1)}%</span>
                </div>
            </div>
            <div class="card-actions">
                ${isRunning
                ? `<span class="has-tooltip">
                    <button onclick="stopBot('${bot.id}')" class="btn-stop">중지</button>
                    <span class="tooltip-text">봇의 실시간 모니터링을 중지합니다. 보유 주식은 그대로 유지됩니다.</span>
                </span>`
                : `<span class="has-tooltip">
                    <button onclick="startBot('${bot.id}')" class="btn-start">시작</button>
                    <span class="tooltip-text">봇 프로세스를 시작합니다. 설정된 조건에 따라 자동 매매를 시작합니다.</span>
                </span>`
            }
                <span class="has-tooltip">
                    <button onclick="viewLogs('${bot.id}')" class="btn-log ${selectedBotId === bot.id ? 'active' : ''}">로그</button>
                    <span class="tooltip-text">현재 봇의 실시간 매매 로그 및 상태를 하단에서 확인합니다.</span>
                </span>
                ${!isRunning ? `
                <span class="has-tooltip">
                    <button onclick="showEditBotModal('${bot.id}')" class="btn-icon" title="설정 수정">⚙️</button>
                    <span class="tooltip-text">봇의 투자 예산, 목표가 등 설정을 변경합니다.</span>
                </span>` : ''}
                <span class="has-tooltip">
                    <button onclick="manualBuyBot('${bot.id}', '${bot.ticker}')" class="btn-buy" title="즉시 시장가 추가 매수">⚡ 매수</button>
                    <span class="tooltip-text" style="bottom: 150%;">클릭 시 전체 예산의 25%를 즉시 시장가로 수동 매수합니다.</span>
                </span>
                <span class="has-tooltip">
                    <button onclick="panicSellBot('${bot.id}', '${bot.ticker}')" class="btn-panic" title="전량매도 및 리셋">⚡ 매도</button>
                    <span class="tooltip-text">현재 보유 물량을 즉시 전량 매도하고 봇 데이터를 초기화합니다.</span>
                </span>
                <span class="has-tooltip">
                    <button onclick="deleteBot('${bot.id}')" class="btn-delete" title="삭제">🗑️</button>
                    <span class="tooltip-text">봇 프로세스를 종료하고 대시보드에서 삭제합니다.</span>
                </span>
            </div>
        `;
        container.appendChild(card);
    });
}

// Screener Management
async function loadScreenerStatus() {
    try {
        const data = await api('GET', '/screener/status');
        if (data.last_scan_time) {
            document.getElementById('lastScanTime').innerText = data.last_scan_time;
            document.getElementById('resultCount').innerText = `${data.result_count}개`;
            renderScreenerResults(data.stocks || []);
        }
    } catch (e) {
        console.error('Failed to load screener status:', e);
    }
}

async function startScan() {
    const btn = document.getElementById('scanBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="loading-spinner"></span> 전체 종목 검색 중...';

    // 조건별 체크박스 확인
    const useMinVolume = document.getElementById('useMinVolume')?.checked ?? true;
    const useMaxPer = document.getElementById('useMaxPer')?.checked ?? true;

    // 파라미터 구성 (캐시 API용)
    const params = new URLSearchParams();
    params.set('limit', 100);  // 결과 최대 100개

    if (useMinVolume) params.set('minVolume', document.getElementById('minVolume').value);
    else params.set('minVolume', 0);

    if (useMaxPer) params.set('maxPer', document.getElementById('maxPer').value);
    else params.set('maxPer', 9999);

    // 적용된 조건 표시
    const appliedFilters = [];
    if (useMinVolume) appliedFilters.push(`거래량≥${(document.getElementById('minVolume').value / 10000).toFixed(0)}만`);
    if (useMaxPer) appliedFilters.push(`PER≤${document.getElementById('maxPer').value}`);

    const filterSummary = appliedFilters.length > 0 ? appliedFilters.join(' / ') : '조건 없음';
    document.getElementById('lastScanTime').innerText = `📊 전체 종목 검색 중: ${filterSummary}`;

    try {
        // 캐시된 전체 종목에서 필터링 (3,993개 대상)
        const data = await api('GET', `/screener/cached?${params}`);
        const totalStocks = data.total_stocks || '?';
        document.getElementById('lastScanTime').innerText =
            `📊 전체 ${totalStocks}개 종목에서 필터링: ${filterSummary}`;
        document.getElementById('resultCount').innerText = `${data.count}개`;
        renderScreenerResults(data.items || []);
    } catch (e) {
        alert('검색 실패: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '🔍 전체 종목 검색';
    }
}


function renderScreenerResults(stocks) {
    const tbody = document.getElementById('screenerResults');
    if (!stocks || stocks.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" class="empty-state">조건에 맞는 종목이 없습니다.</td></tr>';
        return;
    }

    tbody.innerHTML = stocks.map(stock => `
        <tr>
            <td><strong>${stock.ticker}</strong></td>
            <td><a href="https://finance.naver.com/item/main.naver?code=${stock.ticker}" target="_blank" class="stock-link">${stock.name || '-'}</a></td>
            <td>${Math.round(stock.price || 0).toLocaleString()}원</td>
            <td class="${(stock.change_rate || 0) > 0 ? 'text-success' : (stock.change_rate || 0) < 0 ? 'text-danger' : ''}">
                ${(stock.change_rate || 0) > 0 ? '+' : ''}${stock.change_rate ? stock.change_rate.toFixed(2) + '%' : '0.00%'}
            </td>
            <td style="color: #90caf9;">${formatVolume(stock.volume || 0)}</td>
            <td>${stock.per ? stock.per.toFixed(1) : '-'}</td>
            <td class="${stock.op_rate >= 5 ? 'text-success' : ''}">
                <div style="font-size: 0.9rem;">${stock.op_rate ? stock.op_rate.toFixed(1) + '%' : '-'}</div>
                <div style="font-size: 0.7rem; color: #888;">${stock.sector || '-'}</div>
            </td>
            <td>
                ${stock.rsi ? `<span class="badge" style="background: ${stock.rsi > 60 ? '#ff9800' : stock.rsi < 40 ? '#03a9f4' : '#4caf50'}">RSI ${stock.rsi}</span>` : ''}
                ${stock.trend_ok ? '<span class="badge" style="background: #9c27b0">추세</span>' : ''}
            </td>
            <td>
                <div style="font-size: 0.8rem;">부채: ${stock.debt_rate ? stock.debt_rate.toFixed(1) + '%' : '-'}</div>
                <div style="font-size: 0.8rem;">유보: ${stock.rsrv_rate ? Math.round(stock.rsrv_rate) + '%' : '-'}</div>
            </td>
            <td>
                <button class="btn-add-quick" onclick="quickAddBot('${stock.ticker}', '${stock.name}')">봇 등록</button>
            </td>
        </tr>
    `).join('');
}


function renderBadge(passed, text) {
    const className = passed ? 'pass' : 'fail';
    const icon = passed ? '✓' : '✗';
    return `<span class="badge-mini ${className}" title="${text}">${icon}</span>`;
}

function renderScoreDots(score) {
    let dots = '<div class="score-dots">';
    for (let i = 1; i <= 4; i++) {
        dots += `<div class="dot ${i <= score ? 'filled' : ''}"></div>`;
    }
    dots += '</div>';
    return dots;
}

function formatVolume(vol) {
    if (vol >= 1000000) return (vol / 1000000).toFixed(1) + 'M';
    if (vol >= 1000) return (vol / 1000).toFixed(1) + 'K';
    return vol;
}

function quickAddBot(ticker, name) {
    document.getElementById('tickerInput').value = ticker;
    showAddBotModal();
}

// Toggle filter inputs enabled/disabled
function setFiltersEnabled(enabled) {
    const filterIds = ['minVolume', 'maxPer', 'minOpRate', 'maxDebtRate', 'maxRsrvRate',
        'requireDoubleBottom', 'requireInvestorFlow', 'optimalMode'];
    filterIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.disabled = !enabled;
            el.style.opacity = enabled ? '1' : '0.5';
        }
    });
}

// RAW Scan - No filters, just high volume stocks
async function startRawScan() {
    const minVolume = document.getElementById('minVolume').value || 0;

    setFiltersEnabled(false); // 필터 비활성화
    document.getElementById('lastScanTime').textContent = '📊 전체보기: 거래량 상위 종목 (필터 없음)';

    try {
        const response = await fetch(`/api/screener/raw?minVolume=${minVolume}`, {
            headers: { 'Authorization': token }
        });

        if (response.ok) {
            const data = await response.json();
            document.getElementById('lastScanTime').textContent =
                `📊 ${data.message || '전체보기'} | 거래량 ≥ ${(minVolume / 10000).toFixed(0)}만`;
            document.getElementById('resultCount').textContent = (data.count || 0) + '개';
            renderScreenerResults(data.items || []);
        } else {
            alert('조회 실패: ' + response.statusText);
            setFiltersEnabled(true);
        }
    } catch (e) {
        alert('조회 오류: ' + e.message);
        setFiltersEnabled(true);
    }
}

// Pre-built strategy runner - uses ONLY strategy preset conditions (ignores UI filters)
async function runStrategy(strategyName) {
    const strategies = {
        'surge': {
            name: '🔥 급등주',
            desc: '거래량 100만+ / 추세·모멘텀 정배열',
            params: { minVolume: 1000000, maxPer: 50, optimalMode: true }
        },
        'value': {
            name: '💰 저PER 가치주',
            desc: 'PER≤10 / 영업이익률≥5% / 부채≤100%',
            params: { minVolume: 500000, maxPer: 10, minOpRate: 5, maxDebtRate: 100, maxRsrvRate: 5000 }
        },
        'trend': {
            name: '📈 추세 돌파',
            desc: '5/20일 정배열 / RSI 30~70',
            params: { minVolume: 500000, maxPer: 30, optimalMode: true }
        },
        'institution': {
            name: '🏦 외인/기관 매집',
            desc: '3일 연속 순매수',
            params: { minVolume: 500000, maxPer: 30, requireInvestorFlow: true }
        }
    };

    const strategy = strategies[strategyName];
    if (!strategy) return;

    setFiltersEnabled(false);  // UI 필터 비활성화 (사용 안 함 표시)
    document.getElementById('lastScanTime').textContent = `${strategy.name}: ${strategy.desc}`;

    const params = new URLSearchParams(strategy.params);

    try {
        const response = await fetch(`/api/screener/scan?${params}`, {
            headers: { 'Authorization': token }
        });

        if (response.ok) {
            const data = await response.json();
            document.getElementById('lastScanTime').textContent = `${strategy.name}: ${strategy.desc}`;
            document.getElementById('resultCount').textContent = (data.count || 0) + '개';
            renderScreenerResults(data.items || []);
        } else {
            alert('검색 실패: ' + response.statusText);
        }
    } catch (e) {
        alert('검색 오류: ' + e.message);
    } finally {
        setFiltersEnabled(true);
    }
}



// Manual stock lookup
async function lookupStock() {
    const ticker = document.getElementById('manualTicker').value.trim();
    if (!ticker) {
        alert('종목코드 또는 이름을 입력하세요');
        return;
    }

    document.getElementById('lastScanTime').textContent = `🔎 "${ticker}" 검색 중...`;

    try {
        const response = await fetch(`/api/screener/lookup?query=${encodeURIComponent(ticker)}`, {
            headers: { 'Authorization': token }
        });

        if (response.ok) {
            const data = await response.json();
            document.getElementById('lastScanTime').textContent = `🔎 수동 조회: ${data.item.name} (${data.item.ticker})`;
            document.getElementById('resultCount').textContent = '1개';
            renderScreenerResults([data.item]);
        } else {
            const err = await response.json();
            alert('조회 실패: ' + (err.detail || response.statusText));
        }
    } catch (e) {
        alert('조회 오류: ' + e.message);
    }
}


// Add Bot
function showAddBotModal() {
    document.getElementById('addBotModal').classList.remove('hidden');
}

function hideAddBotModal() {
    document.getElementById('addBotModal').classList.add('hidden');
}

function showGuideModal() {
    document.getElementById('guideModal').classList.remove('hidden');
}

function hideGuideModal() {
    document.getElementById('guideModal').classList.add('hidden');
}

async function addBot(event) {
    event.preventDefault();

    const config = {
        ticker: document.getElementById('tickerInput').value,
        budget: parseInt(document.getElementById('budgetInput').value),
        target: parseFloat(document.getElementById('targetInput').value) / 100.0,
        pyramiding_threshold: parseFloat(document.getElementById('pyramidingInput').value || 1.0) / 100.0,
        buy_prices: [
            parseFloat(document.getElementById('buyPriceInput1').value || 0),
            parseFloat(document.getElementById('buyPriceInput2').value || 0),
            parseFloat(document.getElementById('buyPriceInput3').value || 0),
            parseFloat(document.getElementById('buyPriceInput4').value || 0)
        ].filter(p => p > 0),
        orderbook: document.getElementById('orderbookInput').checked,
        momentum: document.getElementById('momentumInput').checked,
        ignore_market: document.getElementById('ignoreMarketInput').checked,
        live: document.getElementById('liveInput').checked
    };

    try {
        await api('POST', '/bots', config);
        hideAddBotModal();
        loadBots();
    } catch (e) {
        alert('봇 추가 실패: ' + e.message);
    }
}

// Edit Bot
function showEditBotModal(botId) {
    const bot = bots.find(b => b.id === botId);
    if (!bot) return;

    document.getElementById('editBotId').value = botId;
    document.getElementById('editTickerInput').value = bot.ticker;
    document.getElementById('editBudgetInput').value = bot.budget;
    document.getElementById('editTargetInput').value = parseFloat((bot.target * 100).toFixed(1));
    document.getElementById('editPyramidingInput').value = parseFloat((bot.pyramiding_threshold * 100).toFixed(1));

    // Set buy prices
    const buyPrices = bot.buy_prices || (bot.buy_price ? [bot.buy_price] : []);
    for (let i = 1; i <= 4; i++) {
        document.getElementById(`editBuyPriceInput${i}`).value = buyPrices[i - 1] || 0;
    }

    document.getElementById('editOrderbookInput').checked = bot.orderbook || false;
    document.getElementById('editMomentumInput').checked = bot.momentum || false;
    document.getElementById('editIgnoreMarketInput').checked = bot.ignore_market || false;
    document.getElementById('editLiveInput').checked = bot.live;

    document.getElementById('editBotModal').classList.remove('hidden');
}

function hideEditBotModal() {
    document.getElementById('editBotModal').classList.add('hidden');
}

async function updateBot(event) {
    event.preventDefault();
    const botId = document.getElementById('editBotId').value;

    const config = {
        ticker: document.getElementById('editTickerInput').value,
        budget: parseInt(document.getElementById('editBudgetInput').value),
        target: parseFloat(document.getElementById('editTargetInput').value) / 100.0,
        pyramiding_threshold: parseFloat(document.getElementById('editPyramidingInput').value || 1.0) / 100.0,
        buy_prices: [
            parseFloat(document.getElementById('editBuyPriceInput1').value || 0),
            parseFloat(document.getElementById('editBuyPriceInput2').value || 0),
            parseFloat(document.getElementById('editBuyPriceInput3').value || 0),
            parseFloat(document.getElementById('editBuyPriceInput4').value || 0)
        ].filter(p => p > 0),
        orderbook: document.getElementById('editOrderbookInput').checked,
        momentum: document.getElementById('editMomentumInput').checked,
        ignore_market: document.getElementById('editIgnoreMarketInput').checked,
        live: document.getElementById('editLiveInput').checked
    };

    try {
        await api('PUT', `/bots/${botId}`, config);
        hideEditBotModal();
        loadBots();
        alert('설정이 저장되었습니다.');
    } catch (e) {
        alert('수정 실패: ' + e.message);
    }
}

// Actions
async function startBot(botId) {
    try {
        await api('POST', `/bots/${botId}/start`);
        viewLogs(botId);
        loadBots();
    } catch (e) {
        alert('봇 시작 실패: ' + e.message);
    }
}

async function stopBot(botId) {
    if (!confirm('봇을 중지하시겠습니까?')) return;
    try {
        await api('POST', `/bots/${botId}/stop`);
        loadBots();
    } catch (e) {
        alert('봇 중지 실패: ' + e.message);
    }
}

async function deleteBot(botId) {
    if (!confirm('이 봇을 삭제하시겠습니까?')) return;
    try {
        await api('DELETE', `/bots/${botId}`);
        loadBots();
    } catch (e) {
        alert('봇 삭제 실패: ' + e.message);
    }
}

async function manualBuyBot(botId, ticker) {
    if (!confirm(`[${ticker}] 즉시 시장가로 추가 매수하시겠습니까?`)) return;
    try {
        await api('POST', `/bots/${botId}/buy`, { price: 0 });
        showToast('시장가 매수 주문이 완료되었습니다.');
        loadBots();
    } catch (e) {
        showToast('매수 실패: ' + e.message, 'error');
    }
}

async function panicSellBot(botId, ticker) {
    const bot = bots.find(b => b.id === botId);
    if (!bot) return;

    // 1. Ask if it's a local reset only
    const isLocalReset = confirm(`🚨 [${ticker}] 로컬 데이터만 초기화하시겠습니까?\n\n'확인' -> 실제 매도 없이 데이터만 초기화\n'취소' -> 실제 매매 포함 진행`);

    if (isLocalReset) {
        if (!confirm(`정말 [${ticker}]의 로컬 데이터를 초기화하시겠습니까?\n- 실제 매도 주문은 나가지 않습니다.\n- 봇이 중지되고 보유량이 0으로 리셋됩니다.`)) return;
        try {
            const res = await api('POST', `/bots/${botId}/panic-sell`, { price: 0, skip_trade: true });
            alert(res.message);
            loadBots();
        } catch (e) {
            alert('초기화 실패: ' + e.message);
        }
        return;
    }

    // 2. Original Real Sell Logic
    const currentPrice = bot ? Math.round(bot.current_price || 0) : 0;

    // Prompt for price (Default to current price for convenience, or 0 for Market)
    let priceInput = prompt(`실제 매도 가격을 입력하세요.\n(0 입력 시 '시장가'로 매도합니다)\n\n현재가: ${currentPrice.toLocaleString()}원`, currentPrice > 0 ? currentPrice : "0");

    if (priceInput === null) return; // Cancelled

    const price = parseInt(priceInput.replace(/,/g, ''));
    if (isNaN(price) || price < 0) {
        alert('올바른 가격을 입력해주세요.');
        return;
    }

    const typeStr = price === 0 ? "시장가" : `${price.toLocaleString()}원(지정가)`;

    if (!confirm(`🚨 [${ticker}] 실제 매수/매도 경고 🚨\n\n1. 봇이 즉시 중지됩니다.\n2. 매도 주문: ${typeStr}\n3. 매매 기록이 초기화됩니다.\n\n정말 진행하시겠습니까?`)) return;

    try {
        const res = await api('POST', `/bots/${botId}/panic-sell`, { price: price, skip_trade: false });
        alert(res.message);
        loadBots();
    } catch (e) {
        alert('매도/리셋 실패: ' + e.message);
    }
}

async function viewLogs(botId) {
    selectedBotId = botId;
    refreshLogs();
    renderBots();

    // Mobile UX: Scroll to logs when viewing
    const logSection = document.querySelector('.log-section');
    if (logSection) {
        logSection.scrollIntoView({ behavior: 'smooth' });
    }
}

async function refreshLogs() {
    if (!selectedBotId) return;

    // Update Header
    const bot = bots.find(b => b.id === selectedBotId);
    if (bot) {
        const title = `📋 ${bot.ticker === bot.ticker_code ? bot.ticker : `${bot.ticker} (${bot.ticker_code || ''})`} 로그`;
        const header = document.getElementById('logHeaderTitle');
        if (header) header.innerText = title;
    }

    try {
        const data = await api('GET', `/bots/${selectedBotId}/logs?lines=100`);
        renderLogs(data.logs);
    } catch (e) {
        console.error('Failed to load logs:', e);
    }
}

function renderLogs(logs) {
    const viewer = document.getElementById('logViewer');
    viewer.innerHTML = logs.map(line => formatLogLine(line)).join('');
    viewer.scrollTop = viewer.scrollHeight;
}

function appendLogs(newLines) {
    const viewer = document.getElementById('logViewer');
    newLines.forEach(line => {
        viewer.insertAdjacentHTML('beforeend', formatLogLine(line));
    });
    viewer.scrollTop = viewer.scrollHeight;

    // Prune excessive logs to keep UI snappy (keep last 300)
    if (viewer.children.length > 300) {
        for (let i = 0; i < viewer.children.length - 300; i++) {
            viewer.removeChild(viewer.children[0]);
        }
    }
}

function formatLogLine(line) {
    let className = 'log-line';
    if (line.includes('INFO')) className += ' info';
    else if (line.includes('WARNING')) className += ' warning';
    else if (line.includes('ERROR') || line.includes('CRITICAL')) className += ' error';
    else if (line.includes('DEBUG')) className += ' debug';

    return `<div class="${className}">${escapeHtml(line)}</div>`;
}

// Security Management
function showSecurityModal() {
    document.getElementById('securityModal').classList.remove('hidden');
    loadBlockedIps();
}

function hideSecurityModal() {
    document.getElementById('securityModal').classList.add('hidden');
}

async function loadBlockedIps() {
    const list = document.getElementById('blockedIpList');
    list.innerHTML = '<p class="placeholder-text">로딩 중...</p>';

    try {
        const ips = await api('GET', '/blocked-ips');
        if (!ips || Object.keys(ips).length === 0) {
            list.innerHTML = '<p class="placeholder-text">차단된 IP가 없습니다.</p>';
            return;
        }

        list.innerHTML = Object.entries(ips).map(([ip, data]) => `
            <div class="ip-item">
                <div class="ip-info">
                    <span class="ip-addr">${escapeHtml(ip)}</span>
                    <span class="ip-date">${new Date(data.blocked_at).toLocaleString()} (시도: ${data.attempts})</span>
                </div>
                <button onclick="unblockIp('${escapeHtml(ip)}')" class="btn-small btn-danger">해제</button>
            </div>
        `).join('');
    } catch (e) {
        list.innerHTML = `<p class="error">로드 실패: ${e.message}</p>`;
    }
}

async function unblockIp(ip) {
    if (!confirm(`${ip} 차단을 해제하시겠습니까?`)) return;
    try {
        await api('DELETE', `/blocked-ips/${ip}`);
        loadBlockedIps();
    } catch (e) {
        alert('해제 실패: ' + e.message);
    }
}

async function emergencyReset() {
    if (!confirm('🚨 정말 초기화 하시겠습니까?\n\n이 작업은 되돌릴 수 없습니다:\n1. 모든 봇이 즉시 중지됩니다.\n2. 보유 중인 주식을 전량 시장가 매도합니다.\n3. 모든 설정과 로그가 삭제됩니다.')) return;

    const doubleCheck = prompt('확인을 위해 "초기화" 라고 입력하세요.');
    if (doubleCheck !== '초기화') {
        alert('취소되었습니다.');
        return;
    }

    try {
        document.body.style.cursor = 'wait';
        alert('초기화 작업이 시작되었습니다. 완료될 때까지 기다려주세요...');

        const res = await api('POST', '/factory-reset');

        alert(`✅ 초기화 완료\n\n결과:\n${res.results.join('\n')}`);
        location.reload();
    } catch (e) {
        alert('초기화 실패: ' + e.message);
    } finally {
        document.body.style.cursor = 'default';
    }
}
