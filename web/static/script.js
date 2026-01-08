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
    connectWebSocket();
    loadBots();
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
        if (bot.buy_price > 0) optionBadges += `<span class="badge-option">Buy@${bot.buy_price}</span>`;
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
                ${bot.buy_price > 0 ? `<span class="badge badge-warning">${Math.round(bot.buy_price).toLocaleString()}원 지정가</span>` : ''}
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
            </div>
            <div class="card-actions">
                ${isRunning
                ? `<button onclick="stopBot('${bot.id}')" class="btn-stop">중지</button>`
                : `<button onclick="startBot('${bot.id}')" class="btn-start">시작</button>`
            }
                <button onclick="viewLogs('${bot.id}')" class="btn-log ${selectedBotId === bot.id ? 'active' : ''}">로그</button>
                ${!isRunning ? `<button onclick="showEditBotModal('${bot.id}')" class="btn-icon" title="설정 수정">⚙️</button>` : ''}
                <button onclick="panicSellBot('${bot.id}', '${bot.ticker}')" class="btn-panic" title="전량매도 및 리셋">⚡ 매도</button>
                <button onclick="deleteBot('${bot.id}')" class="btn-delete" title="삭제">🗑️</button>
            </div>
        `;
        container.appendChild(card);
    });
}

// Add Bot
function showAddBotModal() {
    document.getElementById('addBotModal').classList.remove('hidden');
}

function hideAddBotModal() {
    document.getElementById('addBotModal').classList.add('hidden');
}

async function addBot(event) {
    event.preventDefault();

    const config = {
        ticker: document.getElementById('tickerInput').value,
        budget: parseInt(document.getElementById('budgetInput').value),
        target: parseFloat(document.getElementById('targetInput').value),
        buy_price: parseFloat(document.getElementById('buyPriceInput').value || 0),
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
    document.getElementById('editTargetInput').value = parseFloat((bot.target * 100).toFixed(4));
    document.getElementById('editBuyPriceInput').value = bot.buy_price || 0;
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
        target: parseFloat(document.getElementById('editTargetInput').value),
        buy_price: parseFloat(document.getElementById('editBuyPriceInput').value || 0),
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

async function panicSellBot(botId, ticker) {
    const bot = bots.find(b => b.id === botId);
    const currentPrice = bot ? Math.round(bot.current_price || 0) : 0;

    // Prompt for price (Default to current price for convenience, or 0 for Market)
    let priceInput = prompt(`매도 가격을 입력하세요.\n(0 입력 시 '시장가'로 매도합니다)\n\n현재가: ${currentPrice.toLocaleString()}원`, currentPrice > 0 ? currentPrice : "0");

    if (priceInput === null) return; // Cancelled

    const price = parseInt(priceInput.replace(/,/g, ''));
    if (isNaN(price) || price < 0) {
        alert('올바른 가격을 입력해주세요.');
        return;
    }

    const typeStr = price === 0 ? "시장가" : `${price.toLocaleString()}원(지정가)`;

    if (!confirm(`🚨 [${ticker}] 경고 🚨\n\n1. 봇이 즉시 중지됩니다.\n2. 매도 주문: ${typeStr}\n3. 매매 기록이 초기화됩니다.\n\n정말 진행하시겠습니까?`)) return;

    try {
        const res = await api('POST', `/bots/${botId}/panic-sell`, { price: price });
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
