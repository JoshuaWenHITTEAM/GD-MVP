// ==========================================
// 1. 模态框与通用 UI 控制 (保留原样)
// ==========================================
function openModal(id) { document.getElementById(id).classList.remove('hidden'); }
function closeModal(id) { document.getElementById(id).classList.add('hidden'); }
function confirmDelete() { document.getElementById('deleteConfirm').classList.remove('hidden'); }
function hideConfirm() { document.getElementById('deleteConfirm').classList.add('hidden'); }

// ==========================================
// 2. 资源画像曲线图 & 雷达评估图 (保留原样)
// ==========================================
const resChart = echarts.init(document.getElementById('resourceChart'));
const resOption = {
    backgroundColor: 'transparent',
    grid: { top: 10, bottom: 20, left: 30, right: 10 },
    xAxis: { type: 'category', boundaryGap: false, data: Array.from({ length: 20 }, (_, i) => i), axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }, axisLabel: { show: false } },
    yAxis: { type: 'value', max: 100, axisLine: { show: false }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }, axisLabel: { color: '#666', fontSize: 10 } },
    series:[
        { name: 'GPU Util', type: 'line', smooth: true, symbol: 'none', lineStyle: { color: '#00FBFF', width: 2 }, areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1,[{ offset: 0, color: 'rgba(0,251,255,0.3)' }, { offset: 1, color: 'rgba(0,251,255,0)' }]) }, data:[42, 45, 43, 44, 46, 45, 48, 47, 45, 46, 42, 43, 45, 47, 48, 45, 44, 46, 45, 45] },
        { name: 'CPU Util', type: 'line', smooth: true, symbol: 'none', lineStyle: { color: '#8B5CFF', width: 1, type: 'dashed' }, data:[30, 32, 35, 33, 31, 28, 30, 32, 35, 34, 30, 32, 31, 29, 32, 30, 33, 31, 30, 32] }
    ]
};
resChart.setOption(resOption);

const radarChart = echarts.init(document.getElementById('radarChart'));
const radarOption = {
    radar: { indicator:[{ name: '准确率', max: 100 }, { name: '召回率', max: 100 }, { name: '推理耗时', max: 100 }, { name: '带宽利用', max: 100 }, { name: '稳定性', max: 100 }], shape: 'circle', splitNumber: 3, axisName: { color: '#888', fontSize: 10 }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }, splitArea: { areaStyle: { color: 'transparent' } }, axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } } },
    series: [{ type: 'radar', data: [{ value:[98, 92, 85, 40, 95], name: '重构后链路', itemStyle: { color: '#00FBFF' }, areaStyle: { color: 'rgba(0,251,255,0.2)' } }, { value:[85, 80, 70, 60, 75], name: '历史基准', itemStyle: { color: '#8B5CFF' }, areaStyle: { color: 'rgba(139,92,255,0.1)' } }] }]
};
radarChart.setOption(radarOption);

// ==========================================
// 3. 视图切换与图表初始化 (清理了干扰视频的部分)
// ==========================================
function toggleView(mode) {
    const btnFusion = document.getElementById('btn-fusion');
    const btnSplit = document.getElementById('btn-split');
    const viewFusion = document.getElementById('view-fusion');
    const viewSplit = document.getElementById('view-split');

    if (mode === 'fusion') {
        btnFusion.classList.add('active'); btnSplit.classList.remove('active');
        viewFusion.classList.remove('hidden-panel'); viewSplit.classList.add('hidden-panel');
    } else {
        btnFusion.classList.remove('active'); btnSplit.classList.add('active');
        viewFusion.classList.add('hidden-panel'); viewSplit.classList.remove('hidden-panel');
        setTimeout(() => { initSplitCharts(); }, 50);
    }
}

function initSplitCharts() {
    // 刷新雷达
    const radarPanel = document.getElementById('radarPanel');
    if(radarPanel){
        const rpChart = echarts.getInstanceByDom(radarPanel);
        if (rpChart) rpChart.resize(); else initRadarInSplit();
    }
    // 刷新特征图
    const miniSync = echarts.getInstanceByDom(document.getElementById('miniSyncGraph'));
    if (miniSync) miniSync.resize();
}

function initRadarInSplit() {
    const panel = document.getElementById('radarPanel');
    if(!panel) return;
    const chart = echarts.init(panel);
    const option = { backgroundColor: 'transparent', polar: { radius: '80%' }, angleAxis: { type: 'value', startAngle: 0, axisLine: { show: false }, splitLine: { lineStyle: { color: 'rgba(0,251,255,0.1)' } }, axisLabel: { show: false } }, radiusAxis: { min: 0, max: 100, axisLine: { show: false }, splitLine: { lineStyle: { color: 'rgba(0,251,255,0.1)' } }, axisLabel: { show: false } }, series:[{ type: 'scatter', coordinateSystem: 'polar', symbolSize: 4, itemStyle: { color: '#00FBFF' }, data: Array.from({ length: 20 }, () =>[Math.random() * 100, Math.random() * 360]) }] };
    chart.setOption(option);
    setInterval(() => { chart.setOption({ series: [{ data: Array.from({ length: 20 }, () =>[Math.random() * 100, Math.random() * 360]) }] }); }, 300);
}

function initMiniSyncGraph() {
    const miniGraph = document.getElementById('miniSyncGraph');
    if(!miniGraph) return;
    const chart = echarts.init(miniGraph);
    const data = Array.from({ length: 20 }, () => Math.random() * 10);
    const option = { grid: { top: 5, bottom: 5, left: 5, right: 5 }, xAxis: { type: 'category', show: false }, yAxis: { type: 'value', show: false }, series:[{ type: 'line', smooth: true, symbol: 'none', lineStyle: { width: 1, color: '#00FBFF' }, areaStyle: { color: 'rgba(0,251,255,0.1)' }, data: data }] };
    chart.setOption(option);
    setInterval(() => { data.shift(); data.push(Math.random() * 10); chart.setOption({ series: [{ data }] }); }, 500);
}

// 独立的声学频谱动画 (不干扰视频)
function startAcousticAnimation() {
    const acousticCanvas = document.getElementById('acousticCanvas');
    if(!acousticCanvas) return;
    const acousticCtx = acousticCanvas.getContext('2d');
    
    function animateAcoustic() {
        const viewSplit = document.getElementById('view-split');
        if (viewSplit && !viewSplit.classList.contains('hidden-panel')) {
            // 只重置声学画布的尺寸，不碰视频画布
            acousticCanvas.width = acousticCanvas.offsetWidth;
            acousticCanvas.height = acousticCanvas.offsetHeight;
            
            acousticCtx.clearRect(0, 0, acousticCanvas.width, acousticCanvas.height);
            acousticCtx.fillStyle = '#8B5CFF';
            for (let i = 0; i < 40; i++) {
                const h = Math.random() * acousticCanvas.height * 0.8;
                acousticCtx.fillRect(i * (acousticCanvas.width / 40), acousticCanvas.height - h, (acousticCanvas.width / 40) - 1, h);
            }
        }
        requestAnimationFrame(animateAcoustic);
    }
    animateAcoustic();
}


// ==========================================
// 4. 【核心重构】：基于真实视频流的模拟数据与渲染引擎
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    const video = document.getElementById('mockVideoSource');
    if(!video) return;

    // 获取三个关键的视频 Canvas
    const canvasFusion = document.getElementById('fusionCanvas');
    const ctxFusion = canvasFusion ? canvasFusion.getContext('2d') : null;
    
    // 注意：用你前面给的 HTML 里的 ID：detectionVizCanvas 和 trackingVizCanvas
    const canvasDet = document.getElementById('detectionVizCanvas');
    const ctxDet = canvasDet ? canvasDet.getContext('2d') : null;
    
    const canvasTrack = document.getElementById('trackingVizCanvas');
    const ctxTrack = canvasTrack ? canvasTrack.getContext('2d') : null;

    video.addEventListener('loadedmetadata', () => {
        const w = video.videoWidth;
        const h = video.videoHeight;
        
        // 使用视频原分辨率，保证绝对清晰且不被外部变形
        if(canvasFusion) { canvasFusion.width = w; canvasFusion.height = h; }
        if(canvasDet) { canvasDet.width = w; canvasDet.height = h; }
        if(canvasTrack) { canvasTrack.width = w; canvasTrack.height = h; }
        
        startMockBackendAndRender();
        startAcousticAnimation();
    });

    // 漫游算法生成器
    class MockDataGenerator {
        constructor(videoW, videoH) {
            this.w = videoW; this.h = videoH;
            this.targets = Array.from({ length: 4 }, (_, i) => ({
                id: `OBJ-${100 + i}`,
                class: ['CAR', 'PERSON', 'DRONE', 'TRUCK'][Math.floor(Math.random() * 4)],
                x: Math.random() * (videoW - 150) + 50,
                y: Math.random() * (videoH - 150) + 50,
                width: 80 + Math.random() * 60,
                height: 100 + Math.random() * 80,
                vx: (Math.random() - 0.5) * 6,
                vy: (Math.random() - 0.5) * 6,
                confidence: 0.85 + Math.random() * 0.14
            }));
        }

        update() {
            this.targets.forEach(t => {
                t.x += t.vx; t.y += t.vy;
                if (t.x <= 0 || t.x + t.width >= this.w) t.vx *= -1;
                if (t.y <= 0 || t.y + t.height >= this.h) t.vy *= -1;
                if (Math.random() < 0.05) { t.vx += (Math.random() - 0.5) * 2; t.vy += (Math.random() - 0.5) * 2; }
                t.confidence = Math.min(0.99, Math.max(0.70, t.confidence + (Math.random() - 0.5) * 0.05));
            });
            return JSON.parse(JSON.stringify(this.targets)); 
        }
    }

    function startMockBackendAndRender() {
        const dataGenerator = new MockDataGenerator(video.videoWidth, video.videoHeight);
        let frameCount = 0;
        let lastDetectionData =[];

        function renderLoop() {
            if (video.paused || video.ended) { requestAnimationFrame(renderLoop); return; }
            frameCount++;
            
            const currentTargets = dataGenerator.update();
            const trackingData = currentTargets; // 追踪高频
            
            if (frameCount % 15 === 0) { // 检测低频 (每15帧更新)
                lastDetectionData = JSON.parse(JSON.stringify(currentTargets));
            }

            // 【画原视频】
            if(ctxFusion) ctxFusion.drawImage(video, 0, 0, canvasFusion.width, canvasFusion.height);

            // 【画检测】
            if(ctxDet) {
                ctxDet.drawImage(video, 0, 0, canvasDet.width, canvasDet.height);
                ctxDet.lineWidth = 3; ctxDet.font = '18px monospace';
                lastDetectionData.forEach(box => {
                    ctxDet.strokeStyle = '#06b6d4';
                    ctxDet.strokeRect(box.x, box.y, box.width, box.height);
                    ctxDet.fillStyle = 'rgba(6, 182, 212, 0.5)';
                    ctxDet.fillRect(box.x, box.y - 25, 100, 25);
                    ctxDet.fillStyle = '#FFF';
                    ctxDet.fillText(`${box.class} ${(box.confidence*100).toFixed(0)}%`, box.x + 5, box.y - 8);
                });
            }

            // 【画追踪】
            if(ctxTrack) {
                ctxTrack.drawImage(video, 0, 0, canvasTrack.width, canvasTrack.height);
                ctxTrack.lineWidth = 2; ctxTrack.font = 'bold 16px monospace';
                trackingData.forEach(box => {
                    ctxTrack.strokeStyle = '#a855f7';
                    ctxTrack.strokeRect(box.x, box.y, box.width, box.height);
                    ctxTrack.fillStyle = '#a855f7';
                    ctxTrack.fillText(`ID: ${box.id}`, box.x + 5, box.y + 20);
                    ctxTrack.beginPath(); ctxTrack.arc(box.x + box.width / 2, box.y + box.height / 2, 4, 0, Math.PI * 2); ctxTrack.fill();
                });
            }

            // 【同步更新侧边栏 DOM 统计数据（接管同事功能）】
            updateSidebarDOM(trackingData);

            requestAnimationFrame(renderLoop);
        }
        requestAnimationFrame(renderLoop);
    }

    // 更新原有的 DOM 表格和统计节点
    function updateSidebarDOM(targets) {
        const tbody = document.getElementById('tracking-tbody');
        if (tbody) {
            let html = '';
            targets.forEach(t => {
                const statusColor = t.confidence > 0.9 ? 'text-green-400' : 'text-yellow-400';
                const statusText = t.confidence > 0.9 ? 'LOCKING' : 'ANALYZING';
                html += `
                    <tr class="border-b border-white/5">
                        <td class="py-0.5 font-mono text-cyan-400 uppercase">${t.id}</td>
                        <td class="py-0.5 font-mono text-gray-300 text-center">${(t.confidence * 100).toFixed(0)}%</td>
                        <td class="py-0.5 text-right ${statusColor}">${statusText}</td>
                    </tr>
                `;
            });
            tbody.innerHTML = html;
        }

        const nodeDetect = document.getElementById('node2-stats');
        const nodeTrack = document.getElementById('node3-stats');
        if (nodeDetect) nodeDetect.innerText = `DETECT: ${targets.length} OBJS`;
        if (nodeTrack) nodeTrack.innerText = `TRACK: ${targets.length} ACTIVE`;
    }
});


// ==========================================
// 5. 窗口变化事件与定时器 (修改版，不破坏视频)
// ==========================================
window.addEventListener('resize', () => {
    // 仅调整图表大小，绝对不能在这里重置视频画布的大小！
    if (typeof resChart !== 'undefined') resChart.resize();
    if (typeof radarChart !== 'undefined') radarChart.resize();
    const rp = echarts.getInstanceByDom(document.getElementById('radarPanel'));
    if (rp) rp.resize();
    const msg = echarts.getInstanceByDom(document.getElementById('miniSyncGraph'));
    if (msg) msg.resize();
});

// 定时器模拟 (保留原样)
setInterval(() => {
    const timer = document.getElementById('timer');
    if (!timer) return;
    let parts = timer.innerText.split(':');
    if(parts.length < 3) return;
    let secParts = parts[2].split('.');
    if(secParts.length < 2) return;
    let ms = parseInt(secParts[1]) + Math.floor(Math.random() * 5);
    if (ms > 99) ms = 0;
    secParts[1] = ms.toString().padStart(2, '0');
    parts[2] = secParts.join('.');
    timer.innerText = parts.join(':');
}, 100);

// 全局初始化入口
window.addEventListener('load', () => {
    // 那些没有定义的未知初始化函数已经剥离，避免报错中断执行
    if(typeof initRadarInSplit === 'function') initRadarInSplit();
    if(typeof initMiniSyncGraph === 'function') initMiniSyncGraph();
});