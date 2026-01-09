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
                <span class="has-tooltip">
                    <h3>${bot.ticker === bot.ticker_code ? bot.ticker : `${bot.ticker} (${bot.ticker_code || ''})`}</h3>
                    <span class="tooltip-text" style="width:280px; left:0; transform:none;">
                        <b>[누가]</b> KRX 상장 종목<br>
                        <b>[무엇을]</b> 이 봇이 감시/매매하는 종목<br>
                        <b>[언제]</b> 봇 생성 시 지정됨 (변경 불가)<br>
                        <b>[어디서]</b> 네이버 금융에서 종목명 조회<br>
                        <b>[왜]</b> 자동매매 대상 종목 식별용
                    </span>
                </span>
                <span class="has-tooltip">
                    ${modeBadge}
                    <span class="tooltip-text" style="width:280px; right:0; left:auto;">
                        <b>[누가]</b> 사용자가 봇 생성 시 설정<br>
                        <b>[무엇을]</b> ${bot.live ? '🔴 실전: 실제 계좌에서 주문 집행' : '⚪ 테스트: 모의 투자 (실제 주문 없음)'}<br>
                        <b>[언제]</b> 봇 추가/수정 시 설정<br>
                        <b>[어디서]</b> KIS API (실전) 또는 로컬 시뮬레이션 (테스트)<br>
                        <b>[왜]</b> 실제 자금 투입 여부 구분<br>
                        <b>[어떻게]</b> 봇 수정에서 체크박스로 변경 가능
                    </span>
                </span>
            </div>
            ${optionBadges}
            <div class="card-status">
                <span class="has-tooltip">
                    <span class="status-indicator" title="${heartbeatTitle}">${heartbeat} ${bot.status}</span>
                    <span class="tooltip-text" style="width:300px; left:0; transform:none;">
                        <b>[누가]</b> 서버 봇 프로세스<br>
                        <b>[무엇을]</b> ${bot.status === 'RUNNING' ? '실행 중 - 10초마다 시세 조회 및 매매 판단' : '중지됨 - 시세 조회/매매 없음'}<br>
                        <b>[언제]</b> ${bot.status === 'RUNNING' ? '시작 버튼 클릭 후 계속' : '중지 버튼 클릭 또는 익절 완료 시'}<br>
                        <b>[어디서]</b> monitor_scalp_universal.py 스크립트<br>
                        <b>[왜]</b> 현재 봇 활성화 상태 표시<br>
                        <b>[어떻게]</b> 아래 시작/중지 버튼으로 제어
                    </span>
                </span>
                <span class="has-tooltip">
                    <span class="profit ${bot.profit_rate >= 0 ? 'positive' : 'negative'}">
                        ${(bot.profit_rate * 100).toFixed(2)}%
                    </span>
                    <span class="tooltip-text" style="width:300px; right:0; left:auto;">
                        <b>[누가]</b> 시스템이 자동 계산<br>
                        <b>[무엇을]</b> 현재 평가 수익률 = (현재가 - 평단가) / 평단가<br>
                        <b>[언제]</b> 봇 실행 중 10초마다 갱신<br>
                        <b>[어디서]</b> 실시간 시세 기반 계산<br>
                        <b>[왜]</b> 현재 수익/손실 상태 확인<br>
                        <b>[어떻게]</b> 🟢 양수: 수익 중 / 🔴 음수: 손실 중
                    </span>
                </span>
            </div>
            <div class="card-options">
                ${bot.orderbook ? '<span class="badge badge-info" title="[누가] 사용자 설정&#10;[무엇을] 호가잔량 필터 활성화&#10;[왜] 매수/매도 호가 잔량 확인 후 매매">호가창</span>' : ''}
                ${bot.momentum ? '<span class="badge badge-accent" title="[누가] 사용자 설정&#10;[무엇을] 모멘텀 모드 활성화&#10;[왜] RSI/볼린저 무시하고 거래량 돌파 시 추격매수">모멘텀</span>' : ''}
                ${bot.ignore_market ? '<span class="badge badge-error" title="[누가] 사용자 설정&#10;[무엇을] 장외시간(NXT) 무시&#10;[왜] 24시간 매매 허용 (야간 시장 포함)">24h</span>' : ''}
                ${buyPrices.map(p => `<span class="badge badge-warning" title="[누가] 사용자 설정 지정가&#10;[무엇을] ${Math.round(p).toLocaleString()}원 도달 시 즉시 매수&#10;[왜] RSI/볼린저 무시하고 특정 가격에 매수">${Math.round(p).toLocaleString()}원 지정가</span>`).join('')}
                ${!bot.live ? '<span class="badge badge-secondary" title="[누가] 사용자 설정&#10;[무엇을] 테스트 모드 (모의 투자)&#10;[왜] 실제 주문 없이 전략 검증">테스트</span>' : ''}
            </div>

            <div class="card-details">
                <div class="detail-row">
                    <span class="has-tooltip">예산
                        <span class="tooltip-text" style="width:250px; left:0; transform:none;">
                            <b>📊 유형:</b> 사용자 설정값<br>
                            <b>📍 출처:</b> 봇 생성 시 입력한 투자 예산<br>
                            <b>🔄 갱신:</b> 봇 설정 수정 시에만 변경<br><br>
                            이 금액 내에서 매수가 진행됩니다.
                        </span>
                    </span>
                    <span class="budget-value">${(bot.budget || 0).toLocaleString()}원</span>
                </div>
                <div class="detail-row">
                    <span class="has-tooltip">현재가
                        <span class="tooltip-text" style="width:280px; left:0; transform:none;">
                            <b>📊 유형:</b> 실시간 데이터<br>
                            <b>📍 출처:</b> KIS API (장중) / 네이버 금융 (장외)<br>
                            <b>🔄 갱신:</b> 약 10초마다 자동 조회<br><br>
                            [${bot.current_exchange || 'KRX'}]는 현재 시세를 제공하는 거래소입니다.
                        </span>
                    </span>
                    <span>
                        ${Math.round(bot.current_price || 0).toLocaleString()}원
                        <small class="text-muted" style="margin-left:4px; font-size:0.8em;">[${bot.current_exchange || 'KRX'}]</small>
                    </span>
                </div>
                <div class="detail-row">
                    <span class="has-tooltip">마지막 확인
                        <span class="tooltip-text" style="width:250px; left:0; transform:none;">
                            <b>📊 유형:</b> 봇 활동 시간<br>
                            <b>📍 출처:</b> 봇 프로세스가 마지막으로 시세를 조회한 시각<br>
                            <b>🔄 갱신:</b> 봇 실행 중 10초마다<br><br>
                            🟢 20초 이내 = 정상 | 🟡 1분 이내 = 지연 | 🔴 1분 이상 = 이상
                        </span>
                    </span>
                    <span style="font-size:0.8em; color:#888;">${bot.last_update ? new Date(bot.last_update).toLocaleTimeString() : '-'}</span>
                </div>
                <div class="detail-row">
                    <span class="has-tooltip">평단가
                        <span class="tooltip-text" style="width:280px; left:0; transform:none;">
                            <b>📊 유형:</b> 계산값 (서버 저장)<br>
                            <b>📍 출처:</b> 총 매수금액 ÷ 총 보유수량<br>
                            <b>🔄 갱신:</b> 매수 체결 시 자동 계산<br><br>
                            물타기 시 평단가가 낮아지며, 익절/추가매수 기준이 됩니다.
                        </span>
                    </span>
                    <span>${Math.round(bot.avg_price || 0).toLocaleString()}원</span>
                </div>
                <div class="detail-row">
                    <span class="has-tooltip">보유량
                        <span class="tooltip-text" style="width:250px; left:0; transform:none;">
                            <b>📊 유형:</b> 실시간 (KIS 계좌 연동)<br>
                            <b>📍 출처:</b> KIS 계좌 잔고 조회 API<br>
                            <b>🔄 갱신:</b> 매수/매도 체결 후 즉시 반영<br><br>
                            실제 증권사 계좌의 보유 수량입니다.
                        </span>
                    </span>
                    <span>${bot.total_qty?.toLocaleString()}주</span>
                </div>
                <div class="detail-row">
                    <span class="has-tooltip">목표가
                        <span class="tooltip-text" style="width:280px; left:0; transform:none;">
                            <b>📊 유형:</b> 계산값<br>
                            <b>📍 계산식:</b> 평단가 × (1 + 목표수익률)<br>
                            <b>🔄 갱신:</b> 평단가 변경 시 자동 재계산<br><br>
                            현재가가 이 가격에 도달하면 <b>전량 익절 매도</b>합니다.
                        </span>
                    </span>
                    <span>${Math.round(bot.avg_price * (1 + bot.target)).toLocaleString()}원 <small class="target-percent">(${(bot.target * 100).toFixed(1)}%)</small></span>
                </div>
                <div class="detail-row">
                    <span class="has-tooltip">추가 매수
                        <span class="tooltip-text" style="width:300px; left:0; transform:none;">
                            <b>📊 유형:</b> 설정값 기반 계산<br>
                            <b>📍 계산식:</b> 평단가 × (1 - 하락폭)<br>
                            <b>🔄 갱신:</b> 평단가 변경 시 자동 재계산<br><br>
                            현재가가 이 가격 이하로 떨어지면 <b>1:2:4:8 가중치</b>로 물타기 매수합니다.<br>
                            (최대 4회, 점점 더 많은 금액을 투입)
                        </span>
                    </span>
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
                    <span class="tooltip-text" style="width: 280px; left: 0; transform: none;">
                        <strong>monitor_scalp_universal.py</strong> 스크립트를 실행합니다.<br><br>
                        <b>매수 조건:</b> RSI ≤ 30 또는 볼린저 밴드 하단 반등 시 자동 매수.<br>
                        <b>매도 조건:</b> 평단가 대비 '목표 수익률' 도달 시 전량 익절.<br>
                        <b>물타기:</b> 평단가 대비 '하락폭' 도달 시 1:2:4:8 가중치로 추가 매수.
                    </span>
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

    // Load cache status
    try {
        const cache = await api('GET', '/screener/cache-status');
        const cacheEl = document.getElementById('cacheStatus');
        if (cacheEl && cache.last_update) {
            const updateTime = new Date(cache.last_update).toLocaleTimeString('ko-KR');
            cacheEl.innerText = `${updateTime} (${cache.stock_count}종목)`;
            cacheEl.title = `다음 갱신: 약 ${cache.next_update_in || '5'}분 후`;
        } else if (cacheEl) {
            cacheEl.innerHTML = `<span style="color:#ffd54f; cursor:help;" title="⏳ 캐시 준비 중&#10;&#10;[누가] 시스템이 준비 중&#10;[무엇을] 전체 종목 데이터 수집&#10;[언제] 첫 검색 시 생성됨&#10;[어디서] 네이버 금융에서 수집&#10;[왜] 아직 검색을 실행하지 않음&#10;&#10;👉 [사용자가 할 일]&#10;위의 '🔍 전체 종목 검색' 버튼을 클릭하세요!&#10;→ 클릭하면 데이터가 자동으로 수집되고&#10;→ 이후 5분마다 자동 갱신됩니다">⏳ 준비 중 (클릭하면 생성됩니다)</span>`;
        }
    } catch (e) {
        const cacheEl = document.getElementById('cacheStatus');
        if (cacheEl) {
            cacheEl.innerHTML = `<span style="color:#ff6b6b; cursor:help;" title="❌ 캐시 로드 실패&#10;&#10;[누가] 시스템이 자동으로 시도했으나 실패&#10;[무엇을] 종목 데이터 캐시 로드&#10;[언제] 페이지 접속 시 자동&#10;[어디서] 서버 캐시 저장소&#10;[왜] 아직 검색을 한 적이 없거나 서버 연결 끊김&#10;&#10;👉 [사용자가 할 일]&#10;1. 위의 '🔍 전체 종목 검색' 버튼 클릭하세요&#10;   → 클릭하면 캐시가 자동 생성됩니다&#10;2. 또는 F5 눌러 페이지 새로고침&#10;3. 헤더 오른쪽 연결 상태 점이 🟢인지 확인">❌ 캐시 실패 (마우스 올려 해결방법 확인)</span>`;
        }
    }
}

async function startScan() {
    const btn = document.getElementById('scanBtn');
    const statusEl = document.getElementById('lastScanTime');
    const progressEl = document.getElementById('cacheStatus');

    btn.disabled = true;
    btn.innerHTML = '<span class="loading-spinner"></span> 수집 준비 중...';

    // 진행 상황 표시 함수
    function updateProgress(step, detail) {
        statusEl.innerHTML = `<span style="color:#4fc3f7;">📡 ${step}</span>`;
        if (progressEl) {
            progressEl.innerHTML = `<span style="color:#ffd54f;">${detail}</span>`;
        }
    }

    // Step 1: 초기화
    updateProgress('[1/4] 캐시 확인 중...', '[어디서] 서버 캐시 저장소 → 확인 중');

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

    try {
        // Step 2: 캐시 상태 확인
        btn.innerHTML = '<span class="loading-spinner"></span> 캐시 확인 중...';
        updateProgress('[2/4] 캐시 상태 조회', '[어디서] /screener/cache-status API');

        let cacheInfo = null;
        try {
            cacheInfo = await api('GET', '/screener/cache-status');
        } catch (e) {
            // 캐시 없으면 수집 필요
            updateProgress('[2/4] 캐시 없음 → 수집 시작', '[상태] 신규 데이터 수집 필요');
        }

        // Step 3: 데이터 수집/조회
        btn.innerHTML = '<span class="loading-spinner"></span> 네이버 금융에서 수집 중...';
        updateProgress('[3/4] 네이버 금융에서 데이터 수집 중...', `[어디서] finance.naver.com → 전체 종목 시세/재무 수집`);

        // 캐시된 전체 종목에서 필터링 (3,993개 대상)
        const data = await api('GET', `/screener/cached?${params}`);
        const totalStocks = data.total_stocks || '?';

        // Step 4: 필터링 완료
        btn.innerHTML = '<span class="loading-spinner"></span> 필터링 중...';
        updateProgress('[4/4] 필터링 완료', `[결과] ${totalStocks}개 종목 중 ${data.count}개 조건 충족`);

        // 최종 결과 표시
        statusEl.innerHTML = `✅ ${totalStocks}개 종목에서 ${filterSummary} 조건으로 검색 완료`;
        document.getElementById('resultCount').innerText = `${data.count}개`;

        if (progressEl) {
            const now = new Date().toLocaleTimeString('ko-KR');
            progressEl.innerHTML = `<span style="color:#81c784;" title="[누가] 스크리너 시스템&#10;[무엇을] 네이버 금융에서 시세/재무 데이터 수집&#10;[언제] ${now}&#10;[어디서] finance.naver.com&#10;[왜] 필터링 및 종목 분석용&#10;[다음 갱신] 5분 후 자동">✅ ${now} 수집 완료 (${totalStocks}종목)</span>`;
        }

        renderScreenerResults(data.items || []);
    } catch (e) {
        statusEl.innerHTML = `<span style="color:#ff6b6b;">❌ 검색 실패: ${e.message}</span>`;
        if (progressEl) {
            progressEl.innerHTML = `<span style="color:#ff6b6b;" title="[누가] 스크리너 시스템&#10;[무엇을] API 호출 실패&#10;[왜] 서버 연결 끊김 또는 네이버 금융 접속 불가&#10;&#10;👉 [사용자가 할 일]&#10;1. 헤더 연결 상태 점 확인 (🟢인지)&#10;2. 페이지 새로고침 후 재시도&#10;3. 잠시 후 다시 시도">❌ 수집 실패 (마우스 올려 확인)</span>`;
        }
    } finally {
        btn.disabled = false;
        btn.innerHTML = '🔍 전체 종목 검색';
    }
}


function renderScreenerResults(stocks, filterInfo = null) {
    const tbody = document.getElementById('screenerResults');
    if (!stocks || stocks.length === 0) {
        // 적용된 필터 정보 수집
        const useMinVolume = document.getElementById('useMinVolume')?.checked;
        const useMaxPer = document.getElementById('useMaxPer')?.checked;
        const useMinOpRate = document.getElementById('useMinOpRate')?.checked;
        const useMaxDebtRate = document.getElementById('useMaxDebtRate')?.checked;
        const minVolume = document.getElementById('minVolume')?.value || 500000;
        const maxPer = document.getElementById('maxPer')?.value || 30;

        let filterDetails = '<div style="text-align:left; padding:20px; background:#1e2530; border-radius:8px; margin:10px;">';
        filterDetails += '<h4 style="color:#ff9800; margin-bottom:15px;">🔍 검색 결과가 없습니다 - 육하원칙 안내</h4>';

        filterDetails += '<div style="margin-bottom:15px; padding:10px; background:#252d3a; border-radius:6px;">';
        filterDetails += '<p style="color:#4fc3f7; margin-bottom:8px;"><b>[누가]</b> 스크리너 시스템이 자동 실행</p>';
        filterDetails += '<p style="color:#4fc3f7; margin-bottom:8px;"><b>[무엇을]</b> 조건에 맞는 종목을 필터링</p>';
        filterDetails += '<p style="color:#4fc3f7; margin-bottom:8px;"><b>[언제]</b> 방금 \'전체 종목 검색\' 버튼 클릭 시</p>';
        filterDetails += '<p style="color:#4fc3f7; margin-bottom:8px;"><b>[어디서]</b> /screener/scan API (네이버 금융 캐시 데이터)</p>';
        filterDetails += '</div>';

        filterDetails += '<p style="color:#aaa; margin-bottom:10px;"><b>[왜] 적용된 필터 조건:</b></p><ul style="color:#888; font-size:0.85rem; margin-left:20px; margin-bottom:15px;">';
        if (useMinVolume) filterDetails += `<li>최소 거래량: ${Number(minVolume).toLocaleString()}주 이상</li>`;
        if (useMaxPer) filterDetails += `<li>최대 PER: ${maxPer} 이하</li>`;
        if (useMinOpRate) filterDetails += `<li>최소 영업이익률: ${document.getElementById('minOpRate')?.value || 0}% 이상</li>`;
        if (useMaxDebtRate) filterDetails += `<li>최대 부채비율: ${document.getElementById('maxDebtRate')?.value || 200}% 이하</li>`;
        if (!useMinVolume && !useMaxPer && !useMinOpRate && !useMaxDebtRate) filterDetails += '<li>필터 없음 (전체 조회)</li>';
        filterDetails += '</ul>';

        filterDetails += '<p style="color:#81c784; margin-bottom:10px;"><b>[어떻게 해결?]</b></p>';
        filterDetails += '<ul style="color:#a5d6a7; font-size:0.85rem; margin-left:20px;">';
        filterDetails += '<li><b>거래량 조건 완화:</b> 최소 거래량 값을 낮춰보세요</li>';
        filterDetails += '<li><b>PER 조건 완화:</b> 최대 PER 값을 올려보세요</li>';
        filterDetails += '<li><b>필터 해제:</b> 체크박스를 해제하고 다시 검색</li>';
        filterDetails += '<li><b>캐시 갱신 대기:</b> 장중에는 5분마다 데이터 갱신</li>';
        filterDetails += '<li><b>장 마감 확인:</b> 장외 시간에는 데이터가 제한될 수 있음</li>';
        filterDetails += '</ul></div>';

        tbody.innerHTML = `<tr><td colspan="10">${filterDetails}</td></tr>`;
        return;
    }

    tbody.innerHTML = stocks.map(stock => `
        <tr>
            <td title="[누가] KRX 상장 종목&#10;[무엇을] 종목 고유 코드&#10;[어디서] 한국거래소(KRX)&#10;[왜] 종목 식별용 (변경 불가)"><strong>${stock.ticker}</strong></td>
            <td title="[누가] 상장 기업&#10;[무엇을] 회사 공식 상장명&#10;[어디서] 네이버 금융&#10;[왜] 클릭하면 네이버 금융 상세페이지로 이동"><a href="https://finance.naver.com/item/main.naver?code=${stock.ticker}" target="_blank" class="stock-link">${stock.name || '-'}</a></td>
            <td title="[누가] 시장 체결가&#10;[무엇을] 마지막 체결된 가격&#10;[언제] 캐시 갱신 시 (5분마다)&#10;[어디서] 네이버 금융 시세&#10;[왜] 현재 매수 가능 가격 확인">${Math.round(stock.price || 0).toLocaleString()}원</td>
            <td class="${(stock.change_rate || 0) > 0 ? 'text-success' : (stock.change_rate || 0) < 0 ? 'text-danger' : ''}" title="[누가] 시스템 자동 계산&#10;[무엇을] (현재가 - 전일종가) / 전일종가&#10;[언제] 캐시 갱신 시 (5분마다)&#10;[어디서] 네이버 금융&#10;[왜] 당일 상승/하락 확인&#10;🟢 양수=상승 / 🔴 음수=하락">
                ${(stock.change_rate || 0) > 0 ? '+' : ''}${stock.change_rate ? stock.change_rate.toFixed(2) + '%' : '0.00%'}
            </td>
            <td style="color: #90caf9;" title="[누가] 시장 참여자 거래&#10;[무엇을] 당일 누적 거래량&#10;[언제] 캐시 갱신 시 (5분마다)&#10;[어디서] 네이버 금융&#10;[왜] 유동성 확인 (높을수록 좋음)&#10;[단위] K=천주, M=백만주">${formatVolume(stock.volume || 0)}</td>
            <td title="[누가] 기업 재무정보&#10;[무엇을] 주가수익비율 = 주가/주당순이익&#10;[언제] 분기별 재무제표 기준&#10;[어디서] 네이버 금융 재무정보&#10;[왜] 저평가 판단 (낮을수록 저평가)&#10;음수=적자 기업">${stock.per ? stock.per.toFixed(1) : '-'}</td>
            <td class="${stock.op_rate >= 5 ? 'text-success' : ''}" title="[누가] 기업 재무정보&#10;[무엇을] 영업이익률 = 영업이익/매출액&#10;[언제] 분기별 재무제표 기준&#10;[어디서] 네이버 금융 재무정보&#10;[왜] 사업 수익성 확인 (5% 이상 양호)">
                <div style="font-size: 0.9rem;">${stock.op_rate ? stock.op_rate.toFixed(1) + '%' : '-'}</div>
                <div style="font-size: 0.7rem; color: #888;">${stock.sector || '-'}</div>
            </td>
            <td title="[누가] 시스템 자동 계산&#10;[무엇을] RSI: 14일간 상승폭/하락폭 비율&#10;[언제] 캐시 갱신 시 (5분마다)&#10;[어디서] 가격 데이터 기반 계산&#10;[왜] 과매수/과매도 판단&#10;RSI≤30=과매도(매수기회) / RSI≥70=과매수(매도고려)">
                ${stock.rsi ? `<span class="badge" style="background: ${stock.rsi > 60 ? '#ff9800' : stock.rsi < 40 ? '#03a9f4' : '#4caf50'}">RSI ${stock.rsi}</span>` : '-'}
                ${stock.trend_ok ? '<span class="badge" style="background: #9c27b0" title="[무엇을] 20일 이평선 돌파 + 거래량 급증">추세</span>' : ''}
            </td>
            <td title="[누가] 기업 재무정보&#10;[무엇을] 부채비율=부채/자본, 유보율=유보금/자본금&#10;[언제] 분기별 재무제표 기준&#10;[어디서] 네이버 금융 재무정보&#10;[왜] 재무 안정성 확인&#10;부채비율 100% 이하=안정적">
                <div style="font-size: 0.8rem;">부채: ${stock.debt_rate ? stock.debt_rate.toFixed(1) + '%' : '-'}</div>
                <div style="font-size: 0.8rem;">유보: ${stock.rsrv_rate ? Math.round(stock.rsrv_rate) + '%' : '-'}</div>
            </td>
            <td>
                <span class="has-tooltip">
                    <button class="btn-add-quick" onclick="quickAddBot('${stock.ticker}', '${stock.name}')">봇 등록</button>
                    <span class="tooltip-text" style="width:280px; right:0; left:auto;">
                        <b>[누가]</b> 사용자 클릭 시<br>
                        <b>[무엇을]</b> 이 종목으로 트레이딩 봇 생성<br>
                        <b>[언제]</b> 클릭 즉시 모달 열림<br>
                        <b>[어디서]</b> 대시보드 '봇 추가' 모달<br>
                        <b>[왜]</b> 자동매매 봇 등록용<br>
                        <b>[어떻게]</b> 예산/목표수익률 설정 후 '시작' 클릭
                    </span>
                </span>
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
