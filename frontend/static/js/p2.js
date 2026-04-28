
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
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span class="iconify mr-1 animate-spin" data-icon="material-symbols:autorenew"></span> 正在部署优化方案...';
    btn.classList.add('bg-emerald-600');

    setTimeout(() => {
        btn.innerHTML = '<span class="iconify mr-1" data-icon="material-symbols:check-circle"></span> 优化方案已应用';
        btn.classList.remove('bg-emerald-600');
        btn.classList.add('bg-blue-600');

        // 模拟 Agent 脉冲反馈
        const agentIcon = document.querySelector('.agent-glow');
        agentIcon.classList.add('scale-125', 'ring-8', 'ring-emerald-500');
        setTimeout(() => {
            agentIcon.classList.remove('scale-125', 'ring-8', 'ring-emerald-500');
            btn.innerHTML = originalText;
        }, 1500);
    }, 1000);
}

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

// 简单的交互：点击 Agent 模拟一次重构动作
document.querySelector('.group').addEventListener('click', () => {
    const agentIcon = document.querySelector('.agent-glow');
    agentIcon.classList.add('scale-125', 'ring-4', 'ring-blue-400');
    setTimeout(() => {
        agentIcon.classList.remove('scale-125', 'ring-4', 'ring-blue-400');
    }, 500);

    // 可以在这里模拟数据刷新
    console.log("手动触发链路重构分析...");
});

// 控制台日志部分：使用 SSE 实时接收后端日志并渲染
document.addEventListener('DOMContentLoaded', () => {
    // --- 1. 变量定义 ---
    const startBtn = document.getElementById('start-train-btn');
    const stopBtn = document.getElementById('stop-train-btn');
    const logContainer = document.getElementById('agent-log-container');
    
    let selectedTaskType = null; // 选中的模块类型: preprocess, detect, track
    let currentJobId = null;
    let eventSource = null;
    let isExpectedClose = false;

    // --- 2. 核心：卡片选中逻辑 ---
    // 为三个卡片绑定点击事件
    const moduleCards = {
        'preprocess': { id: 'status-01', card: document.querySelector('.top-32.left-32 .module-card') },
        'detect': { id: 'status-02', card: document.querySelector('.top-32.right-32 .module-card') },
        'track': { id: 'status-03', card: document.querySelector('.bottom-32.left-32 .module-card') }
    };

    // 自动寻找并绑定点击事件（根据你的 HTML 结构）
    Object.keys(moduleCards).forEach(type => {
        const cardElement = moduleCards[type].card;
        if (cardElement) {
            cardElement.style.cursor = 'pointer';
            cardElement.onclick = () => {
                selectedTaskType = type;
                // 清除所有选中效果
                Object.values(moduleCards).forEach(m => m.card.classList.remove('selected-card', 'border-blue-500'));
                // 给当前点击的加个高亮（利用 Tailwind 类或自定义类）
                cardElement.classList.add('selected-card', 'border-blue-500');
                console.log("已选中模块:", type);
            };
        }
    });

    // --- 3. UI 状态管理 ---
    function setUIState(running) {
        if (running) {
            startBtn.disabled = true;
            startBtn.classList.add('opacity-50', 'cursor-not-allowed');
            stopBtn.disabled = false;
            stopBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        } else {
            startBtn.disabled = false;
            startBtn.classList.remove('opacity-50', 'cursor-not-allowed', 'bg-slate-700');
            stopBtn.disabled = true;
            stopBtn.classList.add('opacity-50', 'cursor-not-allowed');
            stopBtn.innerHTML = '<span class="iconify" data-icon="material-symbols:stop-circle-outline"></span><span>终止训练任务</span>';
        }
    }

    function appendLog(logData) {
        // 适配新后端的字段: logData.ts, logData.message
        const logHtml = `
            <div class="text-[11px] p-2 bg-blue-500/5 border-l-2 border-blue-500 text-slate-300 animate-fade-in">
                <span class="text-blue-400">[${logData.ts || new Date().toLocaleTimeString()}]</span> ${logData.message}
            </div>
        `;
        logContainer.insertAdjacentHTML('beforeend', logHtml);
        logContainer.scrollTop = logContainer.scrollHeight;
    }

    // --- 4. 启动任务 ---
    startBtn.onclick = async () => {
        if (!selectedTaskType) {
            alert("请先点击选择一个算法模块卡片（预处理/检测/跟踪）！");
            return;
        }

        setUIState(true);
        isExpectedClose = false;
        logContainer.innerHTML = '<div class="text-[11px] text-slate-500 italic">正在向后端申请训练资源...</div>';

        try {
            // 注意：这里调的是你自己的 BFF 接口
            const response = await fetch('/api/v1/train/jobs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    task_type: selectedTaskType,
                    config: {
                        learning_rate: document.getElementById('param-lr')?.value || 0.001,
                        epsilon: document.getElementById('param-epsilon')?.value || 0.9
                    }
                })
            });
            
            if (!response.ok) throw new Error("后端服务响应异常");

            const data = await response.json();
            currentJobId = data.job_id; 

            // 建立监听：注意后端现在使用命名事件
            subscribeToJob(currentJobId);

        } catch (error) {
            appendLog({ message: `启动失败: ${error.message}`, status: 'failed' });
            setUIState(false);
        }
    };

    // --- 5. 核心：监听命名事件 (SSE) ---
    function subscribeToJob(jobId) {
        eventSource = new EventSource(`/api/v1/train/jobs/${jobId}/stream`);

        // 监听 [log] 事件 -> 打印到控制台
        eventSource.addEventListener('log', (e) => {
            const data = JSON.parse(e.data);
            appendLog(data);
        });

        // 监听 [status] 事件 -> 更新卡片
        eventSource.addEventListener('status', (e) => {
            const data = JSON.parse(e.data);
            const map = { 'preprocess': '01', 'detect': '02', 'track': '03' };
            const statusEl = document.getElementById(`status-${map[selectedTaskType]}`);
            if (statusEl) {
                statusEl.textContent = data.status;
                statusEl.className = "text-xs py-0.5 px-2 bg-blue-500/20 text-blue-400 rounded animate-pulse";
            }
        });

        // 监听 [completed] 事件
        eventSource.addEventListener('completed', (e) => {
            isExpectedClose = true;
            appendLog({ message: "✅ 训练任务已成功完成", ts: new Date().toLocaleTimeString() });
            setTimeout(closeConnection, 1000);
        });

        // 监听 [failed] 事件
        eventSource.addEventListener('failed', (e) => {
            isExpectedClose = true;
            appendLog({ message: "❌ 任务运行失败", ts: new Date().toLocaleTimeString() });
            setTimeout(closeConnection, 1000);
        });

        eventSource.onerror = () => {
            if (!isExpectedClose) {
                appendLog({ message: "⚠️ 与后端的通信流异常中断", ts: new Date().toLocaleTimeString() });
                closeConnection();
            }
        };
    }

    // --- 6. 终止任务 ---
    stopBtn.onclick = async () => {
        if (!currentJobId) return;
        stopBtn.disabled = true;
        stopBtn.innerHTML = '<span class="iconify animate-spin" data-icon="material-symbols:sync"></span>停止中...';

        try {
            await fetch(`/api/v1/train/jobs/${currentJobId}/stop`, { method: 'POST' });
        } catch (error) {
            alert("停止请求失败");
            stopBtn.disabled = false;
        }
    };

    function closeConnection() {
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
        currentJobId = null;
        setUIState(false);
    }
});
/*
        // --- 【旧版终止任务核心逻辑】 ---
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
*/

