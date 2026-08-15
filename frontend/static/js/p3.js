function openModal(id) { document.getElementById(id)?.classList.remove('hidden'); }
function closeModal(id) { document.getElementById(id)?.classList.add('hidden'); }
function confirmDelete() { document.getElementById('deleteConfirm')?.classList.remove('hidden'); }
function hideConfirm() { document.getElementById('deleteConfirm')?.classList.add('hidden'); }

const echartsReady = typeof echarts !== 'undefined';
const noopChart = { setOption() {}, resize() {} };
let resChart = noopChart;
let radarChart = noopChart;
let reasoningAbortController = null;
let reasoningStopping = false;
let reasoningStopRequested = false;
let reasoningManualStopLogged = false;

function markReasoningManuallyStopped() {
    if (reasoningManualStopLogged) return;
    reasoningManualStopLogged = true;
    appendCommandLog('[STOP] 链路已手动停止', 'text-yellow-400');
    setPhase('stopped');
    setSystemLog('链路已停止');
}

async function requestReasoningStop() {
    if (reasoningStopping) return;
    reasoningStopping = true;
    reasoningStopRequested = true;

    setSystemLog('正在停止链路...');
    appendCommandLog('[STOP] 正在停止链路...', 'text-yellow-400');

    const stopRequest = fetch('/api/v1/reasoning/stop', {
        method: 'POST',
        keepalive: true,
    });

    try {
        if (navigator.sendBeacon) {
            navigator.sendBeacon('/api/v1/reasoning/stop', new Blob([], { type: 'application/json' }));
        }
        if (reasoningAbortController) reasoningAbortController.abort();
        await stopRequest;
    } catch (error) {
        appendCommandLog(`[WARN] 停止请求失败：${String(error)}`, 'text-yellow-400');
    } finally {
        if (reasoningAbortController) reasoningAbortController.abort();
        markReasoningManuallyStopped();
    }
}

window.requestReasoningStop = requestReasoningStop;
window.stopStream = requestReasoningStop;

if (echartsReady) {
    const resourceChartEl = document.getElementById('resourceChart');
    if (resourceChartEl) {
        resChart = echarts.init(resourceChartEl);
        resChart.setOption({
            backgroundColor: 'transparent',
            grid: { top: 10, bottom: 20, left: 30, right: 10 },
            xAxis: { type: 'category', boundaryGap: false, data: [], axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }, axisLabel: { show: false } },
            yAxis: { type: 'value', max: 100, axisLine: { show: false }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }, axisLabel: { color: '#666', fontSize: 10 } },
            series: [
                { name: 'Detect', type: 'line', smooth: true, symbol: 'none', lineStyle: { color: '#00FBFF', width: 2 }, data: [] },
                { name: 'Track', type: 'line', smooth: true, symbol: 'none', lineStyle: { color: '#8B5CFF', width: 2 }, data: [] }
            ]
        });
    }

    const radarChartEl = document.getElementById('radarChart');
    if (radarChartEl) {
        radarChart = echarts.init(radarChartEl);
        radarChart.setOption({
            radar: {
                indicator: [
                    { name: '检测延迟', max: 1000 },
                    { name: '跟踪延迟', max: 1000 },
                    { name: '检测置信度', max: 100 },
                    { name: '跟踪置信度', max: 100 },
                    { name: '链路稳定性', max: 100 }
                ],
                shape: 'circle',
                splitNumber: 3,
                axisName: { color: '#888', fontSize: 10 },
                splitLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
                splitArea: { areaStyle: { color: 'transparent' } },
                axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }
            },
            series: [{ type: 'radar', data: [{ value: [0, 0, 0, 0, 0], name: '链路实时状态', itemStyle: { color: '#00FBFF' }, areaStyle: { color: 'rgba(0,251,255,0.2)' } }] }]
        });
    }
}

function toggleView(mode) {
    const btnFusion = document.getElementById('btn-fusion');
    const btnSplit = document.getElementById('btn-split');
    const viewFusion = document.getElementById('view-fusion');
    const viewSplit = document.getElementById('view-split');

    if (mode === 'fusion') {
        btnFusion?.classList.add('active');
        btnSplit?.classList.remove('active');
        viewFusion?.classList.remove('hidden-panel');
        viewSplit?.classList.add('hidden-panel');
    } else {
        btnFusion?.classList.remove('active');
        btnSplit?.classList.add('active');
        viewFusion?.classList.add('hidden-panel');
        viewSplit?.classList.remove('hidden-panel');
    }
}

function appendCommandLog(text, cssClass = 'text-gray-500') {
    const container = document.getElementById('command-log');
    if (!container) return;
    const line = document.createElement('p');
    line.className = cssClass;
    line.textContent = text;
    container.prepend(line);
    while (container.children.length > 80) {
        container.lastElementChild?.remove();
    }
}

function setPhase(text) {
    const el = document.getElementById('reasoning-phase');
    if (el) el.textContent = text;
}

function setSystemLog(text) {
    const el = document.getElementById('system-log-marquee');
    if (el) el.textContent = text;
}

function updateTrackingTable(result, sequence, frameIndex) {
    const tbody = document.getElementById('tracking-tbody');
    const uuidEl = document.getElementById('tracking-uuid');
    if (!tbody || !uuidEl) return;
    if (!result) {
        tbody.innerHTML = '';
        uuidEl.textContent = 'UID: --';
        return;
    }
    uuidEl.textContent = `UID: ${sequence}-${frameIndex}`;
    const score = result.score ?? 0;
    const statusColor = score >= 0.5 ? 'text-green-400' : 'text-yellow-400';
    const statusText = score >= 0.5 ? 'LOCKING' : 'RECOVER';
    tbody.innerHTML = `
        <tr class="border-b border-white/5">
            <td class="py-0.5 font-mono text-cyan-400 uppercase">${result.tracker || result.detector || 'CHAIN'}</td>
            <td class="py-0.5 font-mono text-gray-300 text-center">${(score * 100).toFixed(0)}%</td>
            <td class="py-0.5 text-right ${statusColor}">${statusText}</td>
        </tr>
    `;
}

function updateAnglesFromBbox(bbox) {
    const azEl = document.getElementById('azimuth-value');
    const elEl = document.getElementById('elevation-value');
    if (!azEl || !elEl || !Array.isArray(bbox) || bbox.length !== 4) return;
    const [x1, y1, x2, y2] = bbox.map(Number);
    const cx = (x1 + x2) / 2;
    const cy = (y1 + y2) / 2;
    azEl.textContent = `${(cx / 10).toFixed(2)}°`;
    elEl.textContent = `${(cy / 10).toFixed(2)}°`;
}

function updateNodeStats(stage, result) {
    const preEl = document.getElementById('node1-stats');
    const detEl = document.getElementById('node2-stats');
    const trackEl = document.getElementById('node3-stats');
    if (preEl) {
        preEl.textContent = 'ACTIVE';
    }
    if (stage === 'detect' && detEl && result) {
        detEl.textContent = `LATENCY: ${(result.latency_ms ?? 0).toFixed(1)}ms | SCORE: ${((result.score ?? 0) * 100).toFixed(0)}%`;
    }
    if (stage === 'track' && trackEl && result) {
        trackEl.textContent = `LATENCY: ${(result.latency_ms ?? 0).toFixed(1)}ms | SCORE: ${((result.score ?? 0) * 100).toFixed(0)}%`;
    }
}

function setActiveNode(nodeKey) {
    const nodes = {
        preprocess: document.getElementById('node-preprocess'),
        detect: document.getElementById('node-detect'),
        track: document.getElementById('node-track'),
    };
    Object.entries(nodes).forEach(([key, el]) => {
        if (!el) return;
        const active = key === nodeKey;
        el.classList.toggle('node-active', active);
        el.classList.toggle('node-idle', !active);
        if (key === 'detect') {
            el.classList.toggle('bg-cyan-400/5', active);
        }
        if (key === 'track') {
            el.classList.toggle('bg-purple-400/5', active);
        }
        if (key === 'preprocess') {
            el.classList.toggle('bg-cyan-400/5', active);
        }
    });
}

function highlightPipeline(stage) {
    setActiveNode(stage === 'detect' ? 'detect' : 'track');
}

function clearCanvas(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const width = Math.max(canvas.clientWidth, 1);
    const height = Math.max(canvas.clientHeight, 1);
    canvas.width = width;
    canvas.height = height;
    ctx.clearRect(0, 0, width, height);
}

const canvasDrawTickets = new Map();
const latestCanvasImages = new Map();
const TRACK_DISPLAY_INTERVAL_MS = 33;
const trackDisplayState = {
    pendingPayload: null,
    scheduled: false,
    loading: false,
    lastRenderAt: 0,
};

function drawBbox(ctx, bbox, imageWidth, imageHeight, offsetX, offsetY, drawWidth, drawHeight, color) {
    if (!Array.isArray(bbox) || bbox.length !== 4 || !imageWidth || !imageHeight) return;
    const [x1, y1, x2, y2] = bbox.map(Number);
    if (![x1, y1, x2, y2].every(Number.isFinite)) return;
    const scaleX = drawWidth / imageWidth;
    const scaleY = drawHeight / imageHeight;
    const boxX = offsetX + x1 * scaleX;
    const boxY = offsetY + y1 * scaleY;
    const boxW = Math.max((x2 - x1) * scaleX, 1);
    const boxH = Math.max((y2 - y1) * scaleY, 1);

    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.strokeRect(boxX, boxY, boxW, boxH);
    ctx.restore();
}

function drawImageToCanvas(canvasId, imageBase64, mediaType = 'image/jpeg', bbox = null, bboxColor = '#FF0000') {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !imageBase64) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const ticket = (canvasDrawTickets.get(canvasId) || 0) + 1;
    canvasDrawTickets.set(canvasId, ticket);

    requestAnimationFrame(() => {
        if (canvasDrawTickets.get(canvasId) !== ticket) return;
        const image = new Image();
        image.onload = () => {
            if (canvasDrawTickets.get(canvasId) !== ticket) return;
            const targetWidth = Math.max(canvas.clientWidth, 1);
            const targetHeight = Math.max(canvas.clientHeight, 1);
            canvas.width = targetWidth;
            canvas.height = targetHeight;
            ctx.clearRect(0, 0, targetWidth, targetHeight);

            const scale = Math.min(targetWidth / image.width, targetHeight / image.height);
            const drawWidth = image.width * scale;
            const drawHeight = image.height * scale;
            const offsetX = (targetWidth - drawWidth) / 2;
            const offsetY = (targetHeight - drawHeight) / 2;

            ctx.drawImage(image, offsetX, offsetY, drawWidth, drawHeight);
            drawBbox(ctx, bbox, image.width, image.height, offsetX, offsetY, drawWidth, drawHeight, bboxColor);
            latestCanvasImages.set(canvasId, image);
        };
        image.src = `data:${mediaType};base64,${imageBase64}`;
    });
}

function redrawCanvasBbox(canvasId, bbox, bboxColor = '#FF0000') {
    const image = latestCanvasImages.get(canvasId);
    const canvas = document.getElementById(canvasId);
    if (!image || !canvas || !bbox) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const targetWidth = Math.max(canvas.clientWidth, 1);
    const targetHeight = Math.max(canvas.clientHeight, 1);
    canvas.width = targetWidth;
    canvas.height = targetHeight;
    ctx.clearRect(0, 0, targetWidth, targetHeight);

    const scale = Math.min(targetWidth / image.width, targetHeight / image.height);
    const drawWidth = image.width * scale;
    const drawHeight = image.height * scale;
    const offsetX = (targetWidth - drawWidth) / 2;
    const offsetY = (targetHeight - drawHeight) / 2;

    ctx.drawImage(image, offsetX, offsetY, drawWidth, drawHeight);
    drawBbox(ctx, bbox, image.width, image.height, offsetX, offsetY, drawWidth, drawHeight, bboxColor);
}

function drawImageUrlToCanvas(canvasId, imageUrl, bbox = null, bboxColor = '#FF0000') {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !imageUrl) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const ticket = (canvasDrawTickets.get(canvasId) || 0) + 1;
    canvasDrawTickets.set(canvasId, ticket);

    requestAnimationFrame(() => {
        if (canvasDrawTickets.get(canvasId) !== ticket) return;
        const image = new Image();
        image.onload = () => {
            if (canvasDrawTickets.get(canvasId) !== ticket) return;
            const targetWidth = Math.max(canvas.clientWidth, 1);
            const targetHeight = Math.max(canvas.clientHeight, 1);
            canvas.width = targetWidth;
            canvas.height = targetHeight;
            ctx.clearRect(0, 0, targetWidth, targetHeight);

            const scale = Math.min(targetWidth / image.width, targetHeight / image.height);
            const drawWidth = image.width * scale;
            const drawHeight = image.height * scale;
            const offsetX = (targetWidth - drawWidth) / 2;
            const offsetY = (targetHeight - drawHeight) / 2;

            ctx.drawImage(image, offsetX, offsetY, drawWidth, drawHeight);
            drawBbox(ctx, bbox, image.width, image.height, offsetX, offsetY, drawWidth, drawHeight, bboxColor);
            latestCanvasImages.set(canvasId, image);
        };
        image.onerror = () => {
            redrawCanvasBbox(canvasId, bbox, bboxColor);
        };
        image.src = imageUrl;
    });
}

function drawLoadedImageToCanvas(canvasId, image, bbox = null, bboxColor = '#FF0000') {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !image) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const targetWidth = Math.max(canvas.clientWidth, 1);
    const targetHeight = Math.max(canvas.clientHeight, 1);
    canvas.width = targetWidth;
    canvas.height = targetHeight;
    ctx.clearRect(0, 0, targetWidth, targetHeight);

    const scale = Math.min(targetWidth / image.width, targetHeight / image.height);
    const drawWidth = image.width * scale;
    const drawHeight = image.height * scale;
    const offsetX = (targetWidth - drawWidth) / 2;
    const offsetY = (targetHeight - drawHeight) / 2;

    ctx.drawImage(image, offsetX, offsetY, drawWidth, drawHeight);
    drawBbox(ctx, bbox, image.width, image.height, offsetX, offsetY, drawWidth, drawHeight, bboxColor);
    latestCanvasImages.set(canvasId, image);
}

function drawImageUrlToCanvases(canvasConfigs, imageUrl, onDone = null) {
    const configs = Array.isArray(canvasConfigs)
        ? canvasConfigs
            .map((item) => (typeof item === 'string' ? { canvasId: item } : item))
            .filter((item) => item?.canvasId)
        : [];
    if (!configs.length || !imageUrl) {
        if (onDone) onDone();
        return;
    }
    const tickets = configs.map((config) => {
        const canvasId = config.canvasId;
        const ticket = (canvasDrawTickets.get(canvasId) || 0) + 1;
        canvasDrawTickets.set(canvasId, ticket);
        return [config, ticket];
    });

    requestAnimationFrame(() => {
        const image = new Image();
        image.onload = () => {
            for (const [config, ticket] of tickets) {
                const canvasId = config.canvasId;
                if (canvasDrawTickets.get(canvasId) !== ticket) continue;
                drawLoadedImageToCanvas(canvasId, image, config.bbox || null, config.bboxColor || '#FF0000');
            }
            if (onDone) onDone();
        };
        image.onerror = () => {
            for (const [config] of tickets) {
                redrawCanvasBbox(config.canvasId, config.bbox || null, config.bboxColor || '#FF0000');
            }
            if (onDone) onDone();
        };
        image.src = imageUrl;
    });
}

function scheduleTrackDisplay(payload, result) {
    if (!payload?.task_id || !result?.bbox_xyxy) return;
    redrawCanvasBbox('trackingVizCanvas', result.bbox_xyxy, '#FF0000');
    trackDisplayState.pendingPayload = {
        taskId: payload.task_id,
        frameIndex: payload.frame_index,
        bbox: result.bbox_xyxy,
    };
    if (trackDisplayState.scheduled || trackDisplayState.loading) return;

    const now = performance.now();
    const delay = Math.max(TRACK_DISPLAY_INTERVAL_MS - (now - trackDisplayState.lastRenderAt), 0);
    trackDisplayState.scheduled = true;
    setTimeout(flushTrackDisplay, delay);
}

function flushTrackDisplay() {
    trackDisplayState.scheduled = false;
    if (trackDisplayState.loading || !trackDisplayState.pendingPayload) return;

    const item = trackDisplayState.pendingPayload;
    trackDisplayState.pendingPayload = null;
    trackDisplayState.loading = true;
    const frameUrl = `/api/v1/reasoning/frame/${item.taskId}/latest?frame=${item.frameIndex}&t=${Date.now()}`;
    drawImageUrlToCanvases([
        { canvasId: 'fusionCanvas' },
        { canvasId: 'trackingVizCanvas', bbox: item.bbox, bboxColor: '#FF0000' },
    ], frameUrl, () => {
        trackDisplayState.loading = false;
        trackDisplayState.lastRenderAt = performance.now();
        if (trackDisplayState.pendingPayload && !trackDisplayState.scheduled) {
            trackDisplayState.scheduled = true;
            setTimeout(flushTrackDisplay, TRACK_DISPLAY_INTERVAL_MS);
        }
    });
}

const metricsState = {
    labels: [],
    detectLatency: [],
    trackLatency: [],
    latestDetectLatency: 0,
    latestTrackLatency: 0,
    latestDetectScore: 0,
    latestTrackScore: 0,
    stability: 0,
};
let lastMetricsRenderAt = 0;

const fpsState = {
    detect: [],
    track: [],
    windowMs: 2000,
};

function resetOutputFps() {
    fpsState.detect = [];
    fpsState.track = [];
    const detectEl = document.getElementById('detect-fps-value');
    const trackEl = document.getElementById('track-fps-value');
    if (detectEl) detectEl.textContent = '--';
    if (trackEl) trackEl.textContent = '--';
}

function recordOutputFps(stage) {
    if (stage !== 'detect' && stage !== 'track') return;
    const now = performance.now();
    const samples = fpsState[stage];
    samples.push(now);
    const cutoff = now - fpsState.windowMs;
    while (samples.length && samples[0] < cutoff) {
        samples.shift();
    }

    const fps = samples.length > 1
        ? (samples.length - 1) * 1000 / Math.max(samples[samples.length - 1] - samples[0], 1)
        : samples.length * 1000 / fpsState.windowMs;
    const el = document.getElementById(stage === 'detect' ? 'detect-fps-value' : 'track-fps-value');
    if (el) el.textContent = fps.toFixed(1);
}

function pushMetrics(stage, result, frameIndex) {
    if (!result) return;
    const latency = Number(result.latency_ms || 0);
    const score = Number(result.score || 0) * 100;
    if (stage === 'detect') {
        metricsState.latestDetectLatency = latency;
        metricsState.latestDetectScore = score;
    }
    if (stage === 'track') {
        metricsState.latestTrackLatency = latency;
        metricsState.latestTrackScore = score;
        metricsState.stability = score;
    }
    metricsState.labels.push(String(frameIndex));
    metricsState.detectLatency.push(metricsState.latestDetectLatency);
    metricsState.trackLatency.push(metricsState.latestTrackLatency);
    if (metricsState.labels.length > 30) {
        metricsState.labels.shift();
        metricsState.detectLatency.shift();
        metricsState.trackLatency.shift();
    }
    const now = performance.now();
    if (now - lastMetricsRenderAt < 120) return;
    lastMetricsRenderAt = now;
    resChart.setOption({
        xAxis: { data: metricsState.labels },
        series: [
            { data: metricsState.detectLatency },
            { data: metricsState.trackLatency },
        ],
    });
    radarChart.setOption({
        series: [{
            data: [{
                value: [
                    Math.min(metricsState.latestDetectLatency, 1000),
                    Math.min(metricsState.latestTrackLatency, 1000),
                    Math.min(metricsState.latestDetectScore, 100),
                    Math.min(metricsState.latestTrackScore, 100),
                    Math.min(metricsState.stability, 100),
                ]
            }]
        }]
    });
}

function resetReasoningView() {
    setPhase('idle');
    setSystemLog('等待算法链路实时数据接入...');
    document.getElementById('tracking-tbody').innerHTML = '';
    document.getElementById('tracking-uuid').textContent = 'UID: --';
    document.getElementById('command-log').innerHTML = '<p class="text-gray-500">等待链路启动...</p>';
    document.getElementById('azimuth-value').textContent = '--';
    document.getElementById('elevation-value').textContent = '--';
    resetOutputFps();
    setActiveNode(null);
    clearCanvas('detectionVizCanvas');
    clearCanvas('trackingVizCanvas');
    clearCanvas('fusionCanvas');
    clearCanvas('trackingCanvas');
    latestCanvasImages.clear();
    canvasDrawTickets.clear();
    trackDisplayState.pendingPayload = null;
    trackDisplayState.scheduled = false;
    trackDisplayState.loading = false;
    trackDisplayState.lastRenderAt = 0;
}

document.addEventListener('DOMContentLoaded', () => {
    const startBtn = document.getElementById('reasoning-start-btn');
    const stopBtn = document.getElementById('reasoning-stop-btn');
    const eventTypeEl = document.getElementById('reasoning-event-type');

    function yieldToBrowser() {
        return new Promise((resolve) => setTimeout(resolve, 0));
    }

    async function startStream() {
        if (reasoningAbortController) reasoningAbortController.abort();
        reasoningAbortController = new AbortController();
        reasoningStopRequested = false;
        reasoningStopping = false;
        reasoningManualStopLogged = false;
        resetReasoningView();
        setPhase('starting');
        startBtn.disabled = true;
        stopBtn.disabled = false;

        try {
            const response = await fetch('/api/v1/reasoning/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ event_type: eventTypeEl.value }),
                signal: reasoningAbortController.signal,
            });
            if (!response.ok || !response.body) {
                throw new Error(`HTTP ${response.status}`);
            }
            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let buffer = '';

            while (!reasoningStopRequested) {
                const { value, done } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const chunks = buffer.split('\n\n');
                buffer = chunks.pop() || '';

                for (const chunk of chunks) {
                    if (reasoningStopRequested) break;
                    const line = chunk.split('\n').find((item) => item.startsWith('data: '));
                    if (!line) continue;
                    const payload = JSON.parse(line.slice(6));

                    if (payload.stage === 'start') {
                        setPhase('running');
                        appendCommandLog(`[START] ${payload.task_id} ${payload.event_type}`);
                        continue;
                    }
                    if (payload.stage === 'done') {
                        setPhase('done');
                        appendCommandLog('[DONE] 链路执行完成', 'text-green-400');
                        setSystemLog('链路执行完成');
                        continue;
                    }
                    if (payload.stage === 'stopped') {
                        setPhase('stopped');
                        if (!reasoningManualStopLogged) {
                            appendCommandLog('[STOP] 链路已停止', 'text-yellow-400');
                        }
                        setSystemLog('链路已停止');
                        continue;
                    }
                    if (payload.stage === 'error') {
                        setPhase('error');
                        appendCommandLog(`[ERROR] ${payload.error}`, 'text-red-400');
                        setSystemLog(payload.error);
                        continue;
                    }

                    const result = payload.result || null;
                    if (payload.stage === 'detect' || payload.stage === 'track') {
                        recordOutputFps(payload.stage);
                        highlightPipeline(payload.stage);
                    }
                    setPhase(payload.stage);
                    setSystemLog(`${payload.sequence} / ${payload.frame_name} / ${payload.reason || '-'}`);
                    appendCommandLog(`[${payload.stage.toUpperCase()}] ${payload.sequence} frame=${payload.frame_index} reason=${payload.reason || '-'}`);

                    if (payload.stage === 'detect') {
                        if (payload.image_base64) {
                            drawImageToCanvas('fusionCanvas', payload.image_base64, payload.image_media_type);
                            drawImageToCanvas('detectionVizCanvas', payload.image_base64, payload.image_media_type, result?.bbox_xyxy, '#FF0000');
                        } else {
                            const frameUrl = `/api/v1/reasoning/frame/${payload.task_id}/latest?frame=${payload.frame_index}&t=${Date.now()}`;
                            drawImageUrlToCanvases([
                                { canvasId: 'fusionCanvas' },
                                { canvasId: 'detectionVizCanvas', bbox: result?.bbox_xyxy, bboxColor: '#FF0000' },
                            ], frameUrl);
                        }
                    } else if (payload.stage === 'track') {
                        if (payload.image_base64) {
                            drawImageToCanvas('fusionCanvas', payload.image_base64, payload.image_media_type);
                            drawImageToCanvas('trackingVizCanvas', payload.image_base64, payload.image_media_type, result?.bbox_xyxy, '#FF0000');
                        } else {
                            scheduleTrackDisplay(payload, result);
                        }
                    }

                    if (result?.bbox_xyxy) {
                        updateAnglesFromBbox(result.bbox_xyxy);
                    }
                    updateTrackingTable(result, payload.sequence, payload.frame_index);
                    updateNodeStats(payload.stage, result);
                    pushMetrics(payload.stage, result, payload.frame_index);
                    await yieldToBrowser();
                }
                await yieldToBrowser();
            }
        } catch (error) {
            if (error.name === 'AbortError' || reasoningStopping) {
                markReasoningManuallyStopped();
            } else {
                appendCommandLog(`[ERROR] ${String(error)}`, 'text-red-400');
                setPhase('error');
                setSystemLog(String(error));
            }
        } finally {
            reasoningAbortController = null;
            reasoningStopping = false;
            reasoningStopRequested = false;
            startBtn.disabled = false;
            stopBtn.disabled = false;
        }
    }

    async function stopStream() {
        await requestReasoningStop();
    }

    startBtn?.addEventListener('click', startStream);
    stopBtn?.addEventListener('click', stopStream);
    resetReasoningView();
    toggleView('fusion');
});

window.addEventListener('resize', () => {
    resChart.resize();
    radarChart.resize();
    clearCanvas('detectionVizCanvas');
    clearCanvas('trackingVizCanvas');
    clearCanvas('fusionCanvas');
    clearCanvas('trackingCanvas');
});
