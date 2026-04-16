




// 初始化奖励变化图表
const rewardChart = echarts.init(document.getElementById('rewardStats'));
const option = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    grid: { top: 10, bottom: 20, left: 30, right: 10 },
    xAxis: {
        type: 'category',
        boundaryGap: false,
        data: Array.from({ length: 20 }, (_, i) => i),
        axisLine: { lineStyle: { color: '#334155' } },
        axisLabel: { show: false }
    },
    yAxis: {
        type: 'value',
        axisLine: { show: false },
        axisLabel: { color: '#475569', fontSize: 10 },
        splitLine: { lineStyle: { color: '#1e293b' } }
    },
    series: [{
        name: 'Episode Reward',
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: [12, 15, 13, 18, 22, 25, 20, 28, 32, 35, 40, 38, 45, 48, 42, 55, 60, 65, 62, 70],
        lineStyle: { width: 2, color: '#3b82f6' },
        areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
                { offset: 1, color: 'rgba(59, 130, 246, 0)' }
            ])
        }
    }]
};
rewardChart.setOption(option);

// 窗口缩放适配
window.addEventListener('resize', () => {
    rewardChart.resize();
});

let currentModule = 'processing'; // 当前选中的标签: processing, det, track
let activeSessions = {}; // 记录状态: { 'processing': { sessionId: '...', isRunning: false, logs: [] } }
let eventSource = null;
let isExpectedClose = false;
// let rewardChart = null;

document.addEventListener('DOMContentLoaded', () => {
    initChart();
    switchTab('processing'); // 初始进入预处理页
    
    // 监听窗口缩放，防止图表变形
    window.addEventListener('resize', () => {
        if (rewardChart) rewardChart.resize();
    });
});

// --- 1. UI 逻辑：标签切换 ---
function switchTab(moduleName) {
    currentModule = moduleName;
    isExpectedClose = false;

    // 切换标签样式
    document.querySelectorAll('.tab-item').forEach(el => el.classList.remove('active'));
    document.getElementById(`tab-${moduleName}`).classList.add('active');

    // 更新左侧卡片静态内容与视觉风格
    const moduleConfigs = {
        'processing': { name: '图像预处理模块', icon: 'filter-vintage-outline', color: '#3b82f6', desc: '负责多维信号对齐、非线性噪声抑制及局部对比度动态增强。', tag: 'MODULE: PROCESSING' },
        'det': { name: '目标检测重构项', icon: 'target', color: '#f59e0b', desc: '动态载入检测头，在精度与速度之间基于实时算力进行平衡决策。', tag: 'MODULE: DETECTION' },
        'track': { name: '多目标链路跟踪', icon: 'share-location-outline', color: '#10b981', desc: '自适应卡尔曼滤波参数调整，减少复杂背景下遮挡导致的目标丢失率。', tag: 'MODULE: TRACKING' }
    };

    const config = moduleConfigs[moduleName];
    document.getElementById('module-display-name').textContent = config.name;
    document.getElementById('module-desc').textContent = config.desc;
    document.getElementById('active-tag').textContent = config.tag;
    
    const iconEl = document.getElementById('module-icon');
    iconEl.dataset.icon = `material-symbols:${config.icon}`;
    iconEl.style.color = config.color;
    document.getElementById('module-icon-bg').style.boxShadow = `0 0 20px ${config.color}33`;

    // 刷新按钮状态：如果该模块正在运行，则保持“终止”可用
    updateButtonsByStatus();
    
    // 切换卡片时的扫描特效（可选）
    const card = document.getElementById('active-module-card');
    card.classList.add('scan-effect');
    setTimeout(() => card.classList.remove('scan-effect'), 1500);
}

// --- 2. 核心功能：启动与停止 ---
async function handleStart() {
    const lr = document.getElementById('param-lr').value;
    const eps = document.getElementById('param-epsilon').value;

    setUIState(true);
    resetMetrics(); // 开始前重置进度条

    try {
        const response = await fetch('/api/v1/agent-training/sessions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                module: currentModule, // 必传
                learning_rate: lr, 
                epsilon: eps 
            })
        });
        const data = await response.json();
        const sid = data.session_id;

        activeSessions[currentModule] = { sessionId: sid, isRunning: true };
        startSSE(sid);
    } catch (e) {
        appendLog({ message: "启动失败: 连接后端超时", status: "failed" });
        setUIState(false);
    }
}

async function handleStop() {
    const session = activeSessions[currentModule];
    if (!session || !session.sessionId) return;

    const stopBtn = document.getElementById('stop-btn');
    stopBtn.innerHTML = '<span class="iconify animate-spin" data-icon="material-symbols:sync"></span>停止中...';
    
    await fetch(`/api/v1/agent-training/sessions/${session.sessionId}/stop`, { method: 'POST' });
}

// --- 3. SSE 数据处理 ---
function startSSE(sid) {
    if (eventSource) eventSource.close();
    isExpectedClose = false;
    eventSource = new EventSource(`/api/v1/agent-training/sessions/${sid}/events`);

    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        appendLog(data);

        // 只有当前正在查看的 Tab 才更新实时卡片和指标
        if (data.status) {
            updateLiveUI(data);
        }

        if (['success', 'failed', 'terminated'].includes(data.status)) {
            isExpectedClose = true;
            setTimeout(() => closeConnection(), 500);
        }
    };

    eventSource.onerror = () => {
        if (!isExpectedClose) {
            appendLog({ message: "日志流异常中断", status: "failed" });
            closeConnection();
        }
    };
}

// 更新界面上的进度条、图表、卡片状态
function updateLiveUI(data) {
    // 1. 更新卡片状态标签和算法名
    const statusTag = document.getElementById('module-status-tag');
    statusTag.textContent = data.status === 'running' ? '运行中' : '已完成';
    statusTag.className = `text-[10px] px-2 py-1 rounded-full border ${data.status === 'running' ? 'bg-blue-500/10 text-blue-400 border-blue-500/30 animate-pulse' : 'bg-slate-800 text-slate-400 border-slate-700'}`;
    
    if (data.algo_name) document.getElementById('module-algo').textContent = data.algo_name;
    if (data.version) document.getElementById('module-ver').textContent = data.version;

    // 2. 更新性能指标进度条 (模拟逻辑，实际可由后端传具体数值)
    if (data.seq) {
        updateProgressBar('step', data.seq, 10); // 假设总共10步
        updateProgressBar('ram', Math.floor(Math.random() * 20 + 60), 100); // 模拟
        updateProgressBar('vram', Math.floor(Math.random() * 15 + 70), 100); // 模拟
    }

    // 3. 更新 ECharts (Reward 曲线)
    if (data.seq) {
        updateChart(data.seq, Math.random() * 10); // 模拟 Reward
    }
}

// --- 辅助工具函数 ---
function updateProgressBar(id, val, max) {
    const percent = Math.min((val / max) * 100, 100);
    document.getElementById(`label-${id}`).textContent = id === 'step' ? val.toString().padStart(4, '0') : `${val}%`;
    document.getElementById(`bar-${id}`).style.width = `${percent}%`;
}

function setUIState(running) {
    activeSessions[currentModule] = activeSessions[currentModule] || {};
    activeSessions[currentModule].isRunning = running;
    updateButtonsByStatus();
}

function updateButtonsByStatus() {
    const isRunning = activeSessions[currentModule]?.isRunning || false;
    const sBtn = document.getElementById('start-btn');
    const tBtn = document.getElementById('stop-btn');

    sBtn.disabled = isRunning;
    tBtn.disabled = !isRunning;
    
    if (isRunning) {
        sBtn.classList.add('opacity-50', 'cursor-not-allowed');
        tBtn.classList.remove('text-slate-500', 'cursor-not-allowed');
        tBtn.classList.add('bg-red-600/20', 'text-red-400', 'border-red-500/50', 'hover:bg-red-600/30');
    } else {
        sBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        tBtn.classList.add('text-slate-500', 'cursor-not-allowed');
        tBtn.classList.remove('bg-red-600/20', 'text-red-400', 'border-red-500/50', 'hover:bg-red-600/30');
        tBtn.innerHTML = '<span class="iconify" data-icon="material-symbols:stop-circle-outline"></span>终止';
    }
}

/*
function initChart() {
    rewardChart = echarts.init(document.getElementById('rewardStats'), 'dark');
    const option = {
        backgroundColor: 'transparent',
        grid: { top: 10, bottom: 20, left: 30, right: 10 },
        xAxis: { type: 'category', boundaryGap: false, axisLine: { show: false } },
        yAxis: { type: 'value', splitLine: { lineStyle: { color: '#1e293b' } } },
        series: [{
            type: 'line', smooth: true,
            areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{offset: 0, color: '#3b82f644'}, {offset: 1, color: '#3b82f600'}]) },
            data: []
        }]
    };
    rewardChart.setOption(option);
}
    

function updateChart(step, value) {
    const option = rewardChart.getOption();
    option.series[0].data.push([step, value]);
    rewardChart.setOption(option);
}
*/

function resetMetrics() {
    ['step', 'ram', 'vram'].forEach(id => updateProgressBar(id, 0, 100));
    if (rewardChart) rewardChart.setOption({ series: [{ data: [] }] });
}

function closeConnection() {
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
    setUIState(false);
}

/*
// 控制台日志部分：使用 SSE 实时接收后端日志并渲染

document.addEventListener('DOMContentLoaded', () => {
    const startBtn = document.getElementById('start-train-btn');
    const stopBtn = document.getElementById('stop-train-btn');
    const logContainer = document.getElementById('agent-log-container');

    let currentSessionId = null;
    let eventSource = null;
    let isExpectedClose = false;

    // 辅助函数：切换按钮状态
    function setUIState(running) {
        const sBtn = document.getElementById('start-train-btn');
        const tBtn = document.getElementById('stop-train-btn');
        if (running) {
            sBtn.disabled = true;
            sBtn.classList.add('opacity-50', 'cursor-not-allowed');
            tBtn.disabled = false;
            tBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        } else {
            sBtn.disabled = false;
            sBtn.classList.remove('opacity-50', 'cursor-not-allowed', 'bg-slate-700'); // 顺便移除背景色
            tBtn.disabled = true;
            tBtn.classList.add('opacity-50', 'cursor-not-allowed');
        }
    }

    function resetCards() {
        const ids = ['01', '02', '03'];
        ids.forEach(id => {
            // 1. 恢复状态标签样式和文字
            const statusEl = document.getElementById(`status-${id}`);
            if (statusEl) {
                statusEl.className = "text-[10px] py-0.5 px-2 bg-slate-500/20 text-slate-400 rounded";
                statusEl.textContent = "等待中";
            }

            // 2. 恢复算法名称文字和样式
            const algoEl = document.getElementById(`algo-${id}`);
            if (algoEl) {
                algoEl.textContent = "待载入";
                algoEl.className = "text-slate-500";
            }

            // 3. 隐藏版本信息
            const verEl = document.getElementById(`ver-${id}`);
            if (verEl) {
                verEl.classList.add('opacity-0');
            }
        });
    }

    // 辅助函数：根据 status 和 event 返回对应的 Tailwind 颜色类
    // 未完成
    // 等待后端对接status
    function getLogStyle(logData) {
        if (logData.event === 'heartbeat') {
            return {
                bg: 'bg-slate-800/40',
                border: 'border-slate-600',
                text: 'text-slate-400',
                time: 'text-slate-500'
            };
        }
        if (logData.status === 'success') {
            return {
                bg: 'bg-emerald-500/5',
                border: 'border-emerald-500',
                text: 'text-slate-300',
                time: 'text-emerald-400'
            };
        }
        if (logData.status === 'failed') {
            return {
                bg: 'bg-red-500/5',
                border: 'border-red-500',
                text: 'text-slate-300',
                time: 'text-red-400'
            };
        }
        // 默认蓝色 (running)
        return {
            bg: 'bg-blue-500/5',
            border: 'border-blue-500',
            text: 'text-slate-300',
            time: 'text-blue-400'
        };
    }

    // 渲染单行日志
    function appendLog(logData) {
        const style = getLogStyle(logData);
        const logHtml = `
            <div class="text-[11px] p-2 ${style.bg} border-l-2 ${style.border} ${style.text} animate-fade-in">
                <span class="${style.time}">[${logData.ts}]</span> ${logData.message}
            </div>
        `;
        logContainer.insertAdjacentHTML('beforeend', logHtml);
        
        // 自动滚动到底部
        logContainer.scrollTop = logContainer.scrollHeight;
    }

    // 点击“开始”按钮
    startBtn.onclick = async () => {
        // 1. 禁用按钮防止重复点击
        resetCards(); // 重置所有卡片 UI
        setUIState(true);
        startBtn.classList.add('bg-slate-700');

        
        // 2. 清空之前的日志
        logContainer.innerHTML = '<div class="text-[11px] text-slate-500 italic">正在建立与 Agent 的连接...</div>';

        try {
            const response = await fetch('/api/v1/agent-training/sessions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ config: "p1_selected_uuids" }) 
            });
            
            if (!response.ok) throw new Error("后端服务响应异常");

            const data = await response.json();
            currentSessionId = data.session_id; 

            eventSource = new EventSource(`/api/v1/agent-training/sessions/${currentSessionId}/events`);

            eventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    appendLog(data);

                    // 识别指令
                    if (data.event === 'switch_module01') updateCardUI('01', data);
                    if (data.event === 'switch_module02') updateCardUI('02', data);
                    if (data.event === 'switch_module03') updateCardUI('03', data);

                    if (['success', 'failed', 'terminated'].includes(data.status)) {
                        isExpectedClose = true;
                        setTimeout(() => {
                            closeConnection(); // 关闭连接，恢复按钮状态
                        }, 500);
                    }
                } catch (e) {
                    console.error("解析错误", e);
                }
            };

            /**
             * 通用的卡片更新函数
             * @param {string} index - '01', '02', 或 '03'
             * @param {object} data - 后端传来的 JSON 对象
             *//*
            function updateCardUI(index, data) {
                const statusEl = document.getElementById(`status-${index}`);
                const algoEl = document.getElementById(`algo-${index}`);
                const verEl = document.getElementById(`ver-${index}`);

                if (!statusEl) return;

                // 更新文字内容（如果有传的话）
                if (data.algo_name) algoEl.textContent = data.algo_name;
                if (data.version) {
                    verEl.textContent = data.version;
                    verEl.classList.remove('opacity-0');
                }

                // 根据 status 切换样式
                if (data.status === 'running') {
                    // 运行中：蓝色 + 呼吸灯动画
                    statusEl.className = "text-[10px] py-0.5 px-2 bg-blue-500/20 text-blue-400 rounded animate-pulse";
                    statusEl.textContent = "运行中";
                    algoEl.className = "text-blue-400 font-bold";
                } else if (data.status === 'completed') {
                    // 已完成：绿色
                    statusEl.className = "text-[10px] py-0.5 px-2 bg-emerald-500/20 text-emerald-400 rounded";
                    statusEl.textContent = "已完成";
                    algoEl.className = "text-emerald-400 font-bold";
                } else {
                    // 其他情况（如等待中）
                    statusEl.className = "text-[10px] py-0.5 px-2 bg-slate-500/20 text-slate-400 rounded";
                    statusEl.textContent = "等待中";
                }
            }

            eventSource.onerror = (err) => {
                if (!isExpectedClose) {
                    console.error("SSE 异常中断");
                    appendLog({ 
                        ts: new Date().toLocaleTimeString(), 
                        message: '与服务器的日志连接异常中断', 
                        status: 'failed' 
                    });
                }
                
                if (!isExpectedClose) {
                    closeConnection();
                }
            };

        } catch (error) {
            logContainer.innerHTML = `<div class="text-[11px] text-red-400">启动失败: ${error.message}</div>`;
            setUIState(false);
        }
    };

        // --- 【终止任务核心逻辑】 ---
    stopBtn.onclick = async () => {
        if (!currentSessionId) return;

        // 界面反馈：把停止按钮设为加载中
        stopBtn.innerHTML = '<span class="iconify animate-spin" data-icon="material-symbols:sync"></span><span>正在停止...</span>';
        stopBtn.disabled = true;

        try {
            const response = await fetch(`/api/v1/agent-training/sessions/${currentSessionId}/stop`, {
                method: 'POST'
            });
            const result = await response.json();
            console.log("停止请求已发送:", result.message);
            // 注意：这里不需要立刻调用 closeConnection()
            // 因为我们要等待后端发回最后一条 "status: terminated" 的日志
        } catch (error) {
            console.error("停止请求失败:", error);
            alert("无法停止任务，请检查网络");
            stopBtn.disabled = false;
        } finally {
            // 恢复停止按钮文字（图标也恢复）
            stopBtn.innerHTML = '<span class="iconify" data-icon="material-symbols:stop-circle-outline"></span><span>终止训练任务</span>';
        }
    };

    function closeConnection() {
        if (eventSource) {
            isExpectedClose = true;
            eventSource.close();
            eventSource = null;
        }
        currentSessionId = null;
        setUIState(false);
    }
});*/

