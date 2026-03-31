
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