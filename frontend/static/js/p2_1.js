// 配置面板切换
function toggleConfig() {
    const content = document.getElementById('config-content');
    const icon = document.getElementById('config-toggle-icon');
    if (content.style.display === 'none') {
        content.style.display = 'grid';
        icon.style.transform = 'rotate(0deg)';
    } else {
        content.style.display = 'none';
        icon.style.transform = 'rotate(-90deg)';
    }
}

// 一键优化应用交互
function applyOptimization() {
    const btn = event.currentTarget;
    const presetValues = {
        'param-lr': 0.0001,
        'param-gamma': 0.99,
        'param-start-e': 0.9,
        'param-end-e': 0.05,
        'param-total-timesteps': 400,
        'param-learning-starts': 10,
        'param-train-frequency': 4,
        'param-target-network-frequency': 20,
        'param-batch-size': 32,
        'param-seed': 123,
    };
    Object.entries(presetValues).forEach(([id, value]) => {
        const el = document.getElementById(id);
        if (el) {
            el.value = value;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }
    });
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span class="iconify mr-1 animate-spin" data-icon="material-symbols:autorenew"></span> 正在部署优化方案...';
    btn.classList.add('bg-emerald-600');

    setTimeout(() => {
        btn.innerHTML = '<span class="iconify mr-1" data-icon="material-symbols:check-circle"></span> 优化方案已应用';
        btn.classList.remove('bg-emerald-600');
        btn.classList.add('bg-blue-600');

        const agentIcon = document.querySelector('.agent-glow');
        agentIcon.classList.add('scale-125', 'ring-8', 'ring-emerald-500');
        setTimeout(() => {
            agentIcon.classList.remove('scale-125', 'ring-8', 'ring-emerald-500');
            btn.innerHTML = originalText;
        }, 1500);
    }, 1000);
}

function buildLineChartOption(seriesName, lineColor, areaTopColor = null) {
    const series = {
        name: seriesName,
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: [],
        lineStyle: { width: 2, color: lineColor }
    };

    if (areaTopColor) {
        series.areaStyle = {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: areaTopColor },
                { offset: 1, color: 'rgba(0, 0, 0, 0)' }
            ])
        };
    }

    return {
        backgroundColor: 'transparent',
        animation: false,
        tooltip: { trigger: 'axis' },
        grid: { top: 10, bottom: 20, left: 30, right: 10 },
        xAxis: {
            type: 'category',
            boundaryGap: false,
            data: [],
            axisLine: { lineStyle: { color: '#334155' } },
            axisLabel: { show: false }
        },
        yAxis: {
            type: 'value',
            axisLine: { show: false },
            axisLabel: { color: '#475569', fontSize: 10 },
            splitLine: { lineStyle: { color: '#1e293b' } }
        },
        series: [series]
    };
}

const rewardChart = echarts.init(document.getElementById('rewardStats'));
const lossChart = echarts.init(document.getElementById('lossStats'));
const rewardChartState = { labels: [], values: [] };
const lossChartState = { labels: [], values: [] };
const MAX_CHART_POINTS = 60;

rewardChart.setOption(buildLineChartOption('Episode Reward', '#3b82f6', 'rgba(59, 130, 246, 0.3)'));
lossChart.setOption(buildLineChartOption('TD Loss', '#f59e0b', 'rgba(245, 158, 11, 0.22)'));

window.addEventListener('resize', () => {
    rewardChart.resize();
    lossChart.resize();
});

document.querySelector('.group').addEventListener('click', () => {
    const agentIcon = document.querySelector('.agent-glow');
    agentIcon.classList.add('scale-125', 'ring-4', 'ring-blue-400');
    setTimeout(() => {
        agentIcon.classList.remove('scale-125', 'ring-4', 'ring-blue-400');
    }, 500);
    console.log('手动触发链路重构分析...');
});

document.addEventListener('DOMContentLoaded', () => {
    const startBtn = document.getElementById('start-train-btn');
    const stopBtn = document.getElementById('stop-train-btn');
    const logContainer = document.getElementById('agent-log-container');
    const nodeStepText = document.getElementById('node-step-text');
    const nodeStepBar = document.getElementById('node-step-bar');
    const nodeCpuText = document.getElementById('node-cpu-text');
    const nodeCpuBar = document.getElementById('node-cpu-bar');
    const nodeGpuMemText = document.getElementById('node-gpu-mem-text');
    const nodeGpuMemBar = document.getElementById('node-gpu-mem-bar');
    const summaryEpsilon = document.getElementById('summary-epsilon');
    const summaryStep = document.getElementById('summary-step');
    const saveConfigBtn = document.getElementById('save-config-btn');
    const loadConfigBtn = document.getElementById('load-config-btn');
    const configStorageKey = 'p2_train_config';

    let selectedTaskType = null;
    let currentJobId = null;
    let eventSource = null;
    let isExpectedClose = false;
    let stopFallbackTimer = null;

    const moduleCards = {
        preprocess: { id: 'status-01', card: document.querySelector('.top-32.left-32 .module-card') },
        detect: { id: 'status-02', card: document.querySelector('.top-32.right-32 .module-card') },
        track: { id: 'status-03', card: document.querySelector('.bottom-32.left-32 .module-card') }
    };

    Object.keys(moduleCards).forEach((type) => {
        const cardElement = moduleCards[type].card;
        if (!cardElement) {
            return;
        }
        cardElement.style.cursor = 'pointer';
        cardElement.onclick = () => {
            selectedTaskType = type;
            Object.values(moduleCards).forEach((item) => item.card.classList.remove('selected-card', 'border-blue-500'));
            cardElement.classList.add('selected-card', 'border-blue-500');
            console.log('已选中模块:', type);
        };
    });

    function setUIState(running) {
        if (running) {
            startBtn.disabled = true;
            startBtn.classList.add('opacity-50', 'cursor-not-allowed');
            stopBtn.disabled = false;
            stopBtn.classList.remove('opacity-50', 'cursor-not-allowed');
            return;
        }
        startBtn.disabled = false;
        startBtn.classList.remove('opacity-50', 'cursor-not-allowed', 'bg-slate-700');
        stopBtn.disabled = true;
        stopBtn.classList.add('opacity-50', 'cursor-not-allowed');
        stopBtn.innerHTML = '<span class="iconify" data-icon="material-symbols:stop-circle-outline"></span><span>终止训练任务</span>';
    }

    function nowText() {
        return new Date().toLocaleTimeString();
    }

    function appendLog(message, ts) {
        const logHtml = `
            <div class="text-[11px] p-2 bg-blue-500/5 border-l-2 border-blue-500 text-slate-300 animate-fade-in">
                <span class="text-blue-400">[${ts || nowText()}]</span> ${message}
            </div>
        `;
        logContainer.insertAdjacentHTML('beforeend', logHtml);
        logContainer.scrollTop = logContainer.scrollHeight;
    }

    function updateStatusBadge(status) {
        if (!selectedTaskType) {
            return;
        }
        const map = { preprocess: '01', detect: '02', track: '03' };
        const statusEl = document.getElementById(`status-${map[selectedTaskType]}`);
        if (!statusEl) {
            return;
        }
        statusEl.textContent = status || '-';
        statusEl.className = 'text-xs py-0.5 px-2 bg-blue-500/20 text-blue-400 rounded animate-pulse';
    }

    function clampPercent(value) {
        const numeric = Number(value);
        if (Number.isNaN(numeric)) {
            return 0;
        }
        return Math.max(0, Math.min(100, numeric));
    }

    function setMetricDisplay(textEl, barEl, text, percent) {
        if (textEl) {
            textEl.textContent = text;
        }
        if (barEl) {
            barEl.style.width = `${clampPercent(percent)}%`;
        }
    }

    function bindRangeValue(inputId, valueId, formatter = (value) => value) {
        const input = document.getElementById(inputId);
        const valueEl = document.getElementById(valueId);
        if (!input || !valueEl) {
            return;
        }
        const render = () => {
            valueEl.textContent = formatter(input.value);
        };
        input.addEventListener('input', render);
        render();
    }

    function getNumberValue(id, fallback = null) {
        const el = document.getElementById(id);
        if (!el || el.value === '') {
            return fallback;
        }
        const value = Number(el.value);
        return Number.isNaN(value) ? fallback : value;
    }

    function getCheckboxValue(id, fallback = false) {
        const el = document.getElementById(id);
        if (!el) {
            return fallback;
        }
        return Boolean(el.checked);
    }

    function collectTrainingConfig() {
        return {
            learning_rate: getNumberValue('param-lr', 0.0001),
            gamma: getNumberValue('param-gamma', 0.99),
            start_e: getNumberValue('param-start-e', 0.9),
            end_e: getNumberValue('param-end-e', 0.05),
            total_timesteps: getNumberValue('param-total-timesteps', 400),
            learning_starts: getNumberValue('param-learning-starts', 10),
            train_frequency: getNumberValue('param-train-frequency', 4),
            target_network_frequency: getNumberValue('param-target-network-frequency', 20),
            batch_size: getNumberValue('param-batch-size', 32),
            seed: getNumberValue('param-seed', 123),
            cuda: getCheckboxValue('param-cuda', true),
            torch_deterministic: getCheckboxValue('param-torch-deterministic', true)
        };
    }

    function applyConfigToForm(config) {
        if (!config || typeof config !== 'object') {
            return;
        }
        const assignments = {
            'param-lr': config.learning_rate,
            'param-gamma': config.gamma,
            'param-start-e': config.start_e,
            'param-end-e': config.end_e,
            'param-total-timesteps': config.total_timesteps,
            'param-learning-starts': config.learning_starts,
            'param-train-frequency': config.train_frequency,
            'param-target-network-frequency': config.target_network_frequency,
            'param-batch-size': config.batch_size,
            'param-seed': config.seed,
        };
        Object.entries(assignments).forEach(([id, value]) => {
            if (value === undefined || value === null) {
                return;
            }
            const el = document.getElementById(id);
            if (el) {
                el.value = value;
                el.dispatchEvent(new Event('input', { bubbles: true }));
            }
        });
        const cudaEl = document.getElementById('param-cuda');
        if (cudaEl && config.cuda !== undefined) {
            cudaEl.checked = Boolean(config.cuda);
        }
        const torchEl = document.getElementById('param-torch-deterministic');
        if (torchEl && config.torch_deterministic !== undefined) {
            torchEl.checked = Boolean(config.torch_deterministic);
        }
    }

    function resetCharts() {
        rewardChartState.labels = [];
        rewardChartState.values = [];
        lossChartState.labels = [];
        lossChartState.values = [];
        rewardChart.setOption({
            xAxis: { data: [] },
            series: [{ data: [] }]
        });
        lossChart.setOption({
            xAxis: { data: [] },
            series: [{ data: [] }]
        });
    }

    function pushChartPoint(state, chart, label, value) {
        const numericValue = Number(value);
        if (value === null || value === undefined || Number.isNaN(numericValue)) {
            return;
        }
        state.labels.push(String(label));
        state.values.push(numericValue);
        if (state.labels.length > MAX_CHART_POINTS) {
            state.labels.shift();
            state.values.shift();
        }
        chart.setOption({
            xAxis: { data: state.labels },
            series: [{ data: state.values }]
        });
    }

    function updateNodeMetrics(payload) {
        if (!payload || typeof payload !== 'object') {
            return;
        }

        const totalSteps = Number(payload.total_steps || 0);
        const currentStep = Number(payload.current_step || 0);
        const progressPercent = payload.progress !== undefined
            ? Number(payload.progress) * 100
            : (totalSteps > 0 ? (currentStep / totalSteps) * 100 : 0);

        setMetricDisplay(
            nodeStepText,
            nodeStepBar,
            totalSteps > 0 ? `${currentStep}/${totalSteps}` : `${currentStep}`,
            progressPercent
        );

        if (summaryStep) {
            summaryStep.textContent = `${currentStep}`;
        }

        if (payload.cpu_util !== null && payload.cpu_util !== undefined) {
            const cpu = Number(payload.cpu_util);
            setMetricDisplay(nodeCpuText, nodeCpuBar, `${cpu.toFixed(1)}%`, cpu);
        }

        if (payload.gpu_mem !== null && payload.gpu_mem !== undefined) {
            const gpuMem = Number(payload.gpu_mem);
            const gpuMemPercent = Math.min(100, (gpuMem / 24000) * 100);
            setMetricDisplay(nodeGpuMemText, nodeGpuMemBar, `${gpuMem.toFixed(0)} MB`, gpuMemPercent);
        }

        if (payload.epsilon !== null && payload.epsilon !== undefined && summaryEpsilon) {
            summaryEpsilon.textContent = Number(payload.epsilon).toFixed(4);
        }
    }

    function handleLogEvent(data) {
        const payload = data.payload || {};
        const message = payload.message;
        if (!message) {
            return;
        }

        if (message.includes('[TRAIN_')) {
            return;
        }

        if (message.includes('global_step=') && message.includes('episodic_state=')) {
            return;
        }
        const prefix = payload.level ? `${payload.level}: ` : '';
        appendLog(`${prefix}${message}`, data.timestamp);
    }

    function handleStatusEvent(data) {
        const payload = data.payload || {};
        updateStatusBadge(payload.status);
        const extra = [];
        if (payload.status) {
            extra.push(`状态=${payload.status}`);
        }
        if (payload.run_dir) {
            extra.push(`run_dir=${payload.run_dir}`);
        }
        if (payload.pid) {
            extra.push(`pid=${payload.pid}`);
        }
        if (extra.length > 0) {
            appendLog(extra.join(' | '), data.timestamp);
        }
    }

    function handleProgressEvent(data) {
        const payload = data.payload || {};
        updateNodeMetrics(payload);
        const parts = [];
        if (payload.current_step !== undefined && payload.total_steps) {
            const percent = payload.progress !== undefined ? `${(Number(payload.progress) * 100).toFixed(1)}%` : '?';
            parts.push(`step=${payload.current_step}/${payload.total_steps}`);
            parts.push(`progress=${percent}`);
        }
        if (payload.cpu_util !== null && payload.cpu_util !== undefined) {
            parts.push(`cpu=${payload.cpu_util}%`);
        }
        if (payload.gpu_util !== null && payload.gpu_util !== undefined) {
            parts.push(`gpu=${payload.gpu_util}%`);
        }
        if (payload.gpu_mem !== null && payload.gpu_mem !== undefined) {
            parts.push(`gpu_mem=${payload.gpu_mem}MB`);
        }
        if (parts.length > 0) {
            appendLog(parts.join(' | '), data.timestamp);
        }
    }

    function handleMetricsEvent(data) {
        const payload = data.payload || {};
        updateNodeMetrics(payload);
        const metricSource = payload.metric_source;
        const parts = [];
        if (payload.step !== null && payload.step !== undefined) {
            parts.push(`step=${payload.step}`);
            if (summaryStep) {
                summaryStep.textContent = `${payload.step}`;
            }
        }
        if (metricSource === 'reward' && payload.reward !== null && payload.reward !== undefined) {
            parts.push(`reward=${payload.reward}`);
            pushChartPoint(rewardChartState, rewardChart, payload.step ?? rewardChartState.labels.length, payload.reward);
        }
        if (metricSource === 'monitor' && payload.td_loss !== null && payload.td_loss !== undefined) {
            parts.push(`td_loss=${payload.td_loss}`);
            pushChartPoint(lossChartState, lossChart, payload.step ?? lossChartState.labels.length, payload.td_loss);
        }
        if (payload.epsilon !== null && payload.epsilon !== undefined) {
            parts.push(`epsilon=${payload.epsilon}`);
            if (summaryEpsilon) {
                summaryEpsilon.textContent = Number(payload.epsilon).toFixed(4);
            }
        }
        if (payload.learning_rate !== null && payload.learning_rate !== undefined) {
            parts.push(`lr=${payload.learning_rate}`);
        }
        if (payload.sps !== null && payload.sps !== undefined) {
            parts.push(`sps=${payload.sps}`);
        }
        if (parts.length > 0) {
            appendLog(parts.join(' | '), data.timestamp);
        }
    }

    function handleCheckpointEvent(data) {
        const payload = data.payload || {};
        const parts = ['checkpoint'];
        if (payload.global_step !== null && payload.global_step !== undefined) {
            parts.push(`step=${payload.global_step}`);
        }
        if (payload.checkpoint_path) {
            parts.push(`path=${payload.checkpoint_path}`);
        }
        appendLog(parts.join(' | '), data.timestamp);
    }

    function closeConnection() {
        if (stopFallbackTimer) {
            clearTimeout(stopFallbackTimer);
            stopFallbackTimer = null;
        }
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
        currentJobId = null;
        setUIState(false);
    }

    bindRangeValue('param-lr', 'param-lr-value', (value) => Number(value).toFixed(4));
    bindRangeValue('param-gamma', 'param-gamma-value', (value) => Number(value).toFixed(2));
    bindRangeValue('param-start-e', 'param-start-e-value', (value) => Number(value).toFixed(2));
    bindRangeValue('param-end-e', 'param-end-e-value', (value) => Number(value).toFixed(2));

    if (saveConfigBtn) {
        saveConfigBtn.onclick = () => {
            localStorage.setItem(configStorageKey, JSON.stringify(collectTrainingConfig()));
            appendLog('配置已保存到本地浏览器', nowText());
        };
    }

    if (loadConfigBtn) {
        loadConfigBtn.onclick = () => {
            const raw = localStorage.getItem(configStorageKey);
            if (!raw) {
                appendLog('未找到已保存配置', nowText());
                return;
            }
            try {
                applyConfigToForm(JSON.parse(raw));
                appendLog('已加载本地配置', nowText());
            } catch (error) {
                appendLog(`配置加载失败: ${error.message}`, nowText());
            }
        };
    }

    startBtn.onclick = async () => {
        if (!selectedTaskType) {
            alert('请先点击选择一个算法模块卡片（预处理/检测/跟踪）！');
            return;
        }

        setUIState(true);
        isExpectedClose = false;
        logContainer.innerHTML = '<div class="text-[11px] text-slate-500 italic">正在向后端申请训练资源...</div>';
        resetCharts();

        try {
            const response = await fetch('/api/v1/train/jobs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    task_type: selectedTaskType,
                    config: collectTrainingConfig()
                })
            });

            if (!response.ok) {
                throw new Error(`后端服务响应异常: HTTP ${response.status}`);
            }

            const data = await response.json();
            currentJobId = data.job_id;
            appendLog(`任务已创建: ${currentJobId}`, nowText());
            updateStatusBadge(data.status || 'queued');
            subscribeToJob(currentJobId);
        } catch (error) {
            appendLog(`启动失败: ${error.message}`, nowText());
            setUIState(false);
        }
    };

    function subscribeToJob(jobId) {
        eventSource = new EventSource(`/api/v1/train/jobs/${jobId}/stream`);

        eventSource.addEventListener('log', (e) => {
            handleLogEvent(JSON.parse(e.data));
        });

        eventSource.addEventListener('status', (e) => {
            handleStatusEvent(JSON.parse(e.data));
        });

        eventSource.addEventListener('progress', (e) => {
            handleProgressEvent(JSON.parse(e.data));
        });

        eventSource.addEventListener('metrics', (e) => {
            handleMetricsEvent(JSON.parse(e.data));
        });

        eventSource.addEventListener('checkpoint', (e) => {
            handleCheckpointEvent(JSON.parse(e.data));
        });

        eventSource.addEventListener('completed', (e) => {
            const data = JSON.parse(e.data);
            isExpectedClose = true;
            updateStatusBadge('completed');
            appendLog('✅ 训练任务已成功完成', data.timestamp || nowText());
            setTimeout(closeConnection, 1000);
        });

        eventSource.addEventListener('stopped', (e) => {
            const data = JSON.parse(e.data);
            isExpectedClose = true;
            updateStatusBadge('stopped');
            appendLog('⏹️ 训练任务已停止', data.timestamp || nowText());
            setTimeout(closeConnection, 300);
        });

        eventSource.addEventListener('failed', (e) => {
            const data = JSON.parse(e.data);
            const payload = data.payload || {};
            isExpectedClose = true;
            updateStatusBadge('failed');
            appendLog(`❌ 任务运行失败${payload.error_message ? `: ${payload.error_message}` : ''}`, data.timestamp || nowText());
            setTimeout(closeConnection, 1000);
        });

        eventSource.onerror = (e) => {
            console.error('EventSource 发生错误:', e);
            if (!isExpectedClose) {
                appendLog('⚠️ 与后端的通信流异常中断', nowText());
                closeConnection();
            }
        };
    }

    stopBtn.onclick = async () => {
        if (!currentJobId) {
            return;
        }
        stopBtn.disabled = true;
        stopBtn.innerHTML = '<span class="iconify animate-spin" data-icon="material-symbols:sync"></span>停止中...';

        try {
            const response = await fetch(`/api/v1/train/jobs/${currentJobId}/stop`, { method: 'POST' });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            updateStatusBadge('stopping');
            appendLog('已发送停止请求', nowText());
            stopFallbackTimer = setTimeout(() => {
                appendLog('⏹️ 停止完成，连接已关闭', nowText());
                isExpectedClose = true;
                closeConnection();
            }, 1500);
        } catch (error) {
            alert(`停止请求失败: ${error.message}`);
            stopBtn.disabled = false;
            stopBtn.innerHTML = '<span class="iconify" data-icon="material-symbols:stop-circle-outline"></span><span>终止训练任务</span>';
        }
    };

    setUIState(false);
});
