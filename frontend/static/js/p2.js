
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
    const startBtn = document.getElementById('start-train-btn');
    const stopBtn = document.getElementById('stop-train-btn');
    const logContainer = document.getElementById('agent-log-container');

    let currentSessionId = null;
    let eventSource = null;

    // 辅助函数：切换按钮状态
    function setUIState(running) {
        if (running) {
            startBtn.disabled = true;
            startBtn.classList.add('opacity-50', 'cursor-not-allowed');
            stopBtn.disabled = false;
            stopBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        } else {
            startBtn.disabled = false;
            startBtn.classList.remove('opacity-50', 'cursor-not-allowed');
            stopBtn.disabled = true;
            stopBtn.classList.add('opacity-50', 'cursor-not-allowed');
        }
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
        startBtn.disabled = true;
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
                // console.log("收到的原始数据:", event.data); // DEBUG用
                // const logData = JSON.parse(event.data);
                 // 如果数据已经是对象（由于某些库的自动处理），就不解析
                const logData = typeof event.data === 'object' ? event.data : JSON.parse(event.data);
                appendLog(logData);
                if (['success', 'failed', 'terminated'].includes(logData.status)) {
                    closeConnection(); 
                }
            };

            eventSource.onerror = (err) => {
                appendLog({ ts: 'Error', message: '日志流连接中断', status: 'failed' });
                closeConnection();
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
            eventSource.close();
            eventSource = null;
        }
        currentSessionId = null;
        setUIState(false);
    }
});

