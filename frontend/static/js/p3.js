// 模态框控制
function openModal(id) {
    document.getElementById(id).classList.remove('hidden');
}
function closeModal(id) {
    document.getElementById(id).classList.add('hidden');
}
function confirmDelete() {
    document.getElementById('deleteConfirm').classList.remove('hidden');
}
function hideConfirm() {
    document.getElementById('deleteConfirm').classList.add('hidden');
}

// 资源画像曲线图
const resChart = echarts.init(document.getElementById('resourceChart'));
const option = {
    backgroundColor: 'transparent',
    grid: { top: 10, bottom: 20, left: 30, right: 10 },
    xAxis: {
        type: 'category',
        boundaryGap: false,
        data: Array.from({ length: 20 }, (_, i) => i),
        axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
        axisLabel: { show: false }
    },
    yAxis: {
        type: 'value',
        max: 100,
        axisLine: { show: false },
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
        axisLabel: { color: '#666', fontSize: 10 }
    },
    series: [
        {
            name: 'GPU Util',
            type: 'line',
            smooth: true,
            symbol: 'none',
            lineStyle: { color: '#00FBFF', width: 2 },
            areaStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: 'rgba(0,251,255,0.3)' },
                    { offset: 1, color: 'rgba(0,251,255,0)' }
                ])
            },
            data: [42, 45, 43, 44, 46, 45, 48, 47, 45, 46, 42, 43, 45, 47, 48, 45, 44, 46, 45, 45]
        },
        {
            name: 'CPU Util',
            type: 'line',
            smooth: true,
            symbol: 'none',
            lineStyle: { color: '#8B5CFF', width: 1, type: 'dashed' },
            data: [30, 32, 35, 33, 31, 28, 30, 32, 35, 34, 30, 32, 31, 29, 32, 30, 33, 31, 30, 32]
        }
    ]
};
resChart.setOption(option);

// 雷达评估图
const radarChart = echarts.init(document.getElementById('radarChart'));
const radarOption = {
    radar: {
        indicator: [
            { name: '准确率', max: 100 },
            { name: '召回率', max: 100 },
            { name: '推理耗时', max: 100 },
            { name: '带宽利用', max: 100 },
            { name: '稳定性', max: 100 }
        ],
        shape: 'circle',
        splitNumber: 3,
        axisName: { color: '#888', fontSize: 10 },
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
        splitArea: { areaStyle: { color: 'transparent' } },
        axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }
    },
    series: [{
        type: 'radar',
        data: [
            {
                value: [98, 92, 85, 40, 95],
                name: '重构后链路',
                itemStyle: { color: '#00FBFF' },
                areaStyle: { color: 'rgba(0,251,255,0.2)' }
            },
            {
                value: [85, 80, 70, 60, 75],
                name: '历史基准',
                itemStyle: { color: '#8B5CFF' },
                areaStyle: { color: 'rgba(139,92,255,0.1)' }
            }
        ]
    }]
};
radarChart.setOption(radarOption);

// --- 多模态传感器交互与可视化修复 ---
function toggleView(mode) {
    const btnFusion = document.getElementById('btn-fusion');
    const btnSplit = document.getElementById('btn-split');
    const viewFusion = document.getElementById('view-fusion');
    const viewSplit = document.getElementById('view-split');

    if (mode === 'fusion') {
        btnFusion.classList.add('active');
        btnSplit.classList.remove('active');
        viewFusion.classList.remove('hidden-panel');
        viewSplit.classList.add('hidden-panel');
    } else {
        btnFusion.classList.remove('active');
        btnSplit.classList.add('active');
        viewFusion.classList.add('hidden-panel');
        viewSplit.classList.remove('hidden-panel');

        // 确保分屏内容在显示后能够正确渲染
        setTimeout(() => {
            initSplitCharts();
        }, 50);
    }
}

function initSplitCharts() {
    resizeCanvases();
    // 刷新雷达
    const radarChart = echarts.getInstanceByDom(document.getElementById('radarPanel'));
    if (radarChart) {
        radarChart.resize();
    } else {
        initRadarInSplit();
    }
    // 刷新特征图
    const miniSync = echarts.getInstanceByDom(document.getElementById('miniSyncGraph'));
    if (miniSync) miniSync.resize();
}

let fusionCtx, fusionCanvas, acousticCtx, acousticCanvas;
let trackingCtx, trackingCanvas;
let trackingTargets = [];
let animationFrame;

function initMultimodal() {
    fusionCanvas = document.getElementById('fusionCanvas');
    fusionCtx = fusionCanvas.getContext('2d');
    acousticCanvas = document.getElementById('acousticCanvas');
    acousticCtx = acousticCanvas.getContext('2d');
    trackingCanvas = document.getElementById('trackingCanvas');
    if (trackingCanvas) trackingCtx = trackingCanvas.getContext('2d');

    resizeCanvases();
    animateMultimodal();
    initRadarInSplit();
    initMiniSyncGraph();
    initTrackingVisualizer();
}

function resizeCanvases() {
    if (fusionCanvas) {
        fusionCanvas.width = fusionCanvas.offsetWidth;
        fusionCanvas.height = fusionCanvas.offsetHeight;
    }
    if (acousticCanvas) {
        acousticCanvas.width = acousticCanvas.offsetWidth;
        acousticCanvas.height = acousticCanvas.offsetHeight;
    }
    if (trackingCanvas) {
        trackingCanvas.width = trackingCanvas.offsetWidth;
        trackingCanvas.height = trackingCanvas.offsetHeight;
    }
}

function animateMultimodal() {
    // 1. 模拟融合视图 (雷达 + 视觉 叠加)
    fusionCtx.clearRect(0, 0, fusionCanvas.width, fusionCanvas.height);

    // 背景雷达线
    fusionCtx.strokeStyle = 'rgba(0, 251, 255, 0.1)';
    fusionCtx.lineWidth = 1;
    const time = Date.now() * 0.001;
    for (let i = 0; i < 3; i++) {
        fusionCtx.beginPath();
        fusionCtx.arc(fusionCanvas.width / 2, fusionCanvas.height / 2, (50 + i * 40 + (time * 20) % 40), 0, Math.PI * 2);
        fusionCtx.stroke();
    }

    // 目标十字准星
    const targetX = fusionCanvas.width / 2 + Math.sin(time) * 30;
    const targetY = fusionCanvas.height / 2 + Math.cos(time * 0.8) * 20;
    fusionCtx.strokeStyle = '#00FBFF';
    fusionCtx.lineWidth = 2;
    fusionCtx.beginPath();
    fusionCtx.moveTo(targetX - 10, targetY); fusionCtx.lineTo(targetX + 10, targetY);
    fusionCtx.moveTo(targetX, targetY - 10); fusionCtx.lineTo(targetX, targetY + 10);
    fusionCtx.stroke();
    fusionCtx.fillStyle = 'rgba(0, 251, 255, 0.2)';
    fusionCtx.fillRect(targetX - 15, targetY - 15, 30, 30);

    // 2. 模拟声学频谱
    if (!document.getElementById('view-split').classList.contains('hidden-panel')) {
        acousticCtx.clearRect(0, 0, acousticCanvas.width, acousticCanvas.height);
        acousticCtx.fillStyle = '#8B5CFF';
        for (let i = 0; i < 40; i++) {
            const h = Math.random() * acousticCanvas.height * 0.8;
            acousticCtx.fillRect(i * (acousticCanvas.width / 40), acousticCanvas.height - h, (acousticCanvas.width / 40) - 1, h);
        }
    }

    requestAnimationFrame(animateMultimodal);
}

function initRadarInSplit() {
    const chart = echarts.init(document.getElementById('radarPanel'));
    const option = {
        backgroundColor: 'transparent',
        polar: { radius: '80%' },
        angleAxis: { type: 'value', startAngle: 0, axisLine: { show: false }, splitLine: { lineStyle: { color: 'rgba(0,251,255,0.1)' } }, axisLabel: { show: false } },
        radiusAxis: { min: 0, max: 100, axisLine: { show: false }, splitLine: { lineStyle: { color: 'rgba(0,251,255,0.1)' } }, axisLabel: { show: false } },
        series: [{
            type: 'scatter',
            coordinateSystem: 'polar',
            symbolSize: 4,
            itemStyle: { color: '#00FBFF' },
            data: Array.from({ length: 20 }, () => [Math.random() * 100, Math.random() * 360])
        }]
    };
    chart.setOption(option);
    setInterval(() => {
        const data = Array.from({ length: 20 }, () => [Math.random() * 100, Math.random() * 360]);
        chart.setOption({ series: [{ data }] });
    }, 300);
}

function initMiniSyncGraph() {
    const chart = echarts.init(document.getElementById('miniSyncGraph'));
    const data = Array.from({ length: 20 }, () => Math.random() * 10);
    const option = {
        grid: { top: 5, bottom: 5, left: 5, right: 5 },
        xAxis: { type: 'category', show: false },
        yAxis: { type: 'value', show: false },
        series: [{
            type: 'line',
            smooth: true,
            symbol: 'none',
            lineStyle: { width: 1, color: '#00FBFF' },
            areaStyle: { color: 'rgba(0,251,255,0.1)' },
            data: data
        }]
    };
    chart.setOption(option);
    setInterval(() => {
        data.shift();
        data.push(Math.random() * 10);
        chart.setOption({ series: [{ data }] });
    }, 500);
}

function initTrackingVisualizer() {
    if (!trackingCanvas) return;
    const targetTypes = ['CAR', 'DRONE', 'TRUCK'];
    trackingTargets = Array.from({ length: 6 }, (_, i) => ({
        id: i === 0 ? 'T-100' : `A-${100 + i}`,
        type: targetTypes[i % 3],
        x: Math.random() * 800,
        y: Math.random() * 400,
        vx: (Math.random() - 0.5) * 1.5,
        vy: (Math.random() - 0.5) * 1.5,
        confidence: 0.85 + Math.random() * 0.14,
        history: [],
        status: Math.random() > 0.3 ? 'LOCKING' : 'ANALYZING'
    }));

    const uuidEl = document.getElementById('tracking-uuid');
    if (uuidEl) uuidEl.innerText = `UID: TRK-20260226-${Math.floor(Math.random() * 1000)}`;

    function animateTracking() {
        if (!trackingCtx) return;
        trackingCtx.clearRect(0, 0, trackingCanvas.width, trackingCanvas.height);

        // 绘制背景网格
        trackingCtx.strokeStyle = 'rgba(139, 92, 255, 0.08)';
        trackingCtx.lineWidth = 0.5;
        const step = 40;
        for (let i = 0; i < trackingCanvas.width; i += step) {
            trackingCtx.beginPath(); trackingCtx.moveTo(i, 0); trackingCtx.lineTo(i, trackingCanvas.height); trackingCtx.stroke();
        }
        for (let i = 0; i < trackingCanvas.height; i += step) {
            trackingCtx.beginPath(); trackingCtx.moveTo(0, i); trackingCtx.lineTo(trackingCanvas.width, i); trackingCtx.stroke();
        }

        const tbody = document.getElementById('tracking-tbody');
        let html = '';

        trackingTargets.forEach(t => {
            t.x += t.vx;
            t.y += t.vy;
            if (t.x < 0 || t.x > trackingCanvas.width) t.vx *= -1;
            if (t.y < 0 || t.y > trackingCanvas.height) t.vy *= -1;

            t.history.push({ x: t.x, y: t.y });
            if (t.history.length > 40) t.history.shift();

            trackingCtx.beginPath();
            trackingCtx.strokeStyle = t.id === 'T-100' ? 'rgba(0, 251, 255, 0.4)' : 'rgba(139, 92, 255, 0.3)';
            trackingCtx.setLineDash([4, 4]);
            t.history.forEach((p, idx) => {
                if (idx === 0) trackingCtx.moveTo(p.x, p.y);
                else trackingCtx.lineTo(p.x, p.y);
            });
            trackingCtx.stroke();
            trackingCtx.setLineDash([]);

            const size = 24;
            trackingCtx.strokeStyle = t.id === 'T-100' ? '#00FBFF' : '#8B5CFF';
            trackingCtx.lineWidth = 2;
            trackingCtx.strokeRect(t.x - size / 2, t.y - size / 2, size, size);

            trackingCtx.fillStyle = trackingCtx.strokeStyle;
            trackingCtx.font = '10px Orbitron';
            trackingCtx.fillText(`${t.id}`, t.x + 15, t.y - 8);

            if (t.id === 'T-100') {
                trackingCtx.beginPath();
                trackingCtx.arc(t.x, t.y, size * 1.5, 0, Math.PI * 2);
                trackingCtx.strokeStyle = 'rgba(0, 251, 255, 0.2)';
                trackingCtx.stroke();
            }

            const statusColor = t.confidence > 0.9 ? 'text-green-400' : 'text-yellow-400';
            html += `
                        <tr class="border-b border-white/5">
                            <td class="py-0.5 font-mono text-cyan-400 uppercase">${t.id}</td>
                            <td class="py-0.5 font-mono text-gray-300 text-center">${(t.confidence * 100).toFixed(0)}%</td>
                            <td class="py-0.5 text-right ${statusColor}">${t.status}</td>
                        </tr>
                    `;
        });

        if (tbody) tbody.innerHTML = html;

        const nodeDetect = document.getElementById('node2-stats');
        const nodeTrack = document.getElementById('node3-stats');
        if (nodeDetect) nodeDetect.innerText = `DETECT: ${trackingTargets.length} OBJS`;
        if (nodeTrack) nodeTrack.innerText = `TRACK: ${trackingTargets.length} ACTIVE`;

        requestAnimationFrame(animateTracking);
    }
    animateTracking();
}

// 修改窗口大小适配
window.addEventListener('resize', () => {
    if (typeof resChart !== 'undefined') resChart.resize();
    if (typeof radarChart !== 'undefined') radarChart.resize();
    resizeCanvases();
    const rp = echarts.getInstanceByDom(document.getElementById('radarPanel'));
    if (rp) rp.resize();
    const msg = echarts.getInstanceByDom(document.getElementById('miniSyncGraph'));
    if (msg) msg.resize();
});

// 在页面加载后初始化
window.addEventListener('load', () => {
    initRadarViz();
    initVisualization();
    initMultimodal();
});

// 定时器模拟
setInterval(() => {
    const timer = document.getElementById('timer');
    if (!timer) return;
    let parts = timer.innerText.split(':');
    let secParts = parts[2].split('.');
    let ms = parseInt(secParts[1]) + Math.floor(Math.random() * 5);
    if (ms > 99) ms = 0;
    secParts[1] = ms.toString().padStart(2, '0');
    parts[2] = secParts.join('.');
    timer.innerText = parts.join(':');
}, 100);
