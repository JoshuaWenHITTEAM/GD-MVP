
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
             */
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
});

