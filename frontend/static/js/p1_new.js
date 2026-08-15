// 算法平台后端 API。使用当前页面的主机名，避免远程浏览器访问到自己本机的 127.0.0.1:7000。
const API_BASE_URL = `${window.location.protocol}//${window.location.hostname || '127.0.0.1'}:7000`;

// ==================== 全局函数定义 ====================

// 页面切换逻辑
function switchPage(pageId) {
    document.querySelectorAll('.page-section').forEach(p => p.classList.add('hidden'));
    const targetPage = document.getElementById('page-' + pageId);
    if (!targetPage) {
        console.error('页面不存在: page-' + pageId);
        return;
    }
    targetPage.classList.remove('hidden');

    const titles = {
        'dashboard': '系统实时概览',
        'samples': '图像/视频样本管理',
        'training': '模型自学习训练舱',
        'vision': '视觉算法推理',
        'query': '算法资产库检索',
        'register': '生产算法入库注册',
        'editor': '代码热更新与在线调试',
        'recycle': '资产回收站'
    };
    const titleEl = document.getElementById('page-title');
    if (titleEl) titleEl.innerText = titles[pageId] || '光电感知算法库子系统';

    document.querySelectorAll('.nav-item').forEach(btn => btn.classList.remove('active-nav'));
    const navBtn = document.getElementById('nav-' + pageId);
    if (navBtn) navBtn.classList.add('active-nav');

    // 各页面特定初始化
    if (pageId === 'query') loadAlgorithmList();
    if (pageId === 'dashboard') initCharts();
    if (pageId === 'samples') loadSampleAssets();  // 确保样本库刷新
    if (pageId === 'vision') {
        if (!window._visionInitialized) {
            initVisionPage();
            window._visionInitialized = true;
        } else {
            loadVisionAssets();
            loadVisionAlgorithms();
        }
    }
}

// 辅助函数：转义HTML
function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/[&<>]/g, function(m) {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';
        return m;
    });
}

// ==================== 图表初始化 ====================
function initCharts() {
    if (typeof echarts === 'undefined') {
        console.warn('ECharts not loaded');
        return;
    }
    const mainChart = echarts.init(document.getElementById('chart-main'), 'dark');
    mainChart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis' },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: { type: 'category', data: ['09:00', '09:10', '09:20', '09:30', '09:40', '09:50'], axisLine: { lineStyle: { color: '#475569' } } },
        yAxis: { type: 'value', axisLine: { lineStyle: { color: '#475569' } }, splitLine: { lineStyle: { color: '#1e293b' } } },
        series: [
            { name: 'CPU 负载', type: 'line', smooth: true, areaStyle: { opacity: 0.1 }, data: [45, 52, 48, 61, 55, 62], itemStyle: { color: '#38bdf8' } },
            { name: 'GPU 占用', type: 'line', smooth: true, areaStyle: { opacity: 0.1 }, data: [70, 75, 72, 85, 80, 88], itemStyle: { color: '#818cf8' } }
        ]
    });
    const pieChart = echarts.init(document.getElementById('chart-pie'), 'dark');
    pieChart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'item' },
        series: [{
            type: 'pie', radius: ['40%', '70%'], avoidLabelOverlap: false,
            itemStyle: { borderRadius: 10, borderColor: '#020617', borderWidth: 2 }, label: { show: false },
            data: [
                { value: 64, name: '学习方法', itemStyle: { color: '#38bdf8' } },
                { value: 36, name: '传统方法', itemStyle: { color: '#c084fc' } }
            ]
        }]
    });
    window.addEventListener('resize', () => { mainChart.resize(); pieChart.resize(); });
}

// ==================== 新版算法管理（注册、检索、版本、热更新） ====================
let isImageValidated = false;

async function loadAlgorithms(preselectUuid = null) {
    const selectElem = document.getElementById('version-algo-select');
    if (!selectElem) return;
    selectElem.innerHTML = '<option value="">加载中...</option>';
    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/algorithms?pageNum=1&pageSize=100`);
        const resData = await response.json();
        if (response.ok && resData.data && resData.data.items) {
            selectElem.innerHTML = '<option value="">请选择算法...</option>';
            resData.data.items.forEach(algo => {
                const opt = document.createElement('option');
                opt.value = algo.uuid;
                opt.textContent = `${algo.algorithmName} [${algo.algorithmCode}]`;
                selectElem.appendChild(opt);
            });
            if (preselectUuid) selectElem.value = preselectUuid;
        } else {
            selectElem.innerHTML = '<option value="">加载失败或暂无数据</option>';
        }
    } catch (error) {
        console.error("加载算法列表失败:", error);
        selectElem.innerHTML = '<option value="">网络请求异常</option>';
    }
}

function switchTab(target) {
    const btnAlgo = document.getElementById('tab-btn-algo');
    const btnVersion = document.getElementById('tab-btn-version');
    const panelAlgo = document.getElementById('panel-algo');
    const panelVersion = document.getElementById('panel-version');
    if (target === 'algo') {
        btnAlgo.className = "px-8 py-3 rounded-xl font-bold transition-all bg-sky-500 text-white shadow-lg shadow-sky-500/30";
        btnVersion.className = "px-8 py-3 rounded-xl font-bold transition-all bg-transparent text-slate-400 hover:text-white hover:bg-slate-800";
        panelVersion.classList.add('hidden');
        panelAlgo.classList.remove('hidden');
    } else {
        btnVersion.className = "px-8 py-3 rounded-xl font-bold transition-all bg-indigo-500 text-white shadow-lg shadow-indigo-500/30";
        btnAlgo.className = "px-8 py-3 rounded-xl font-bold transition-all bg-transparent text-slate-400 hover:text-white hover:bg-slate-800";
        panelAlgo.classList.add('hidden');
        panelVersion.classList.remove('hidden');
        if (document.getElementById('version-algo-select').options.length <= 1) {
            loadAlgorithms();
        }
    }
}

function handleFileSelect(inputElem, targetInputId, mockPrefix) {
    if (inputElem.files && inputElem.files.length > 0) {
        const fileName = inputElem.files[0].name;
        document.getElementById(targetInputId).value = mockPrefix + fileName;
    }
}

function generateAlgorithmCode() {
    return 'ALG-' + Date.now() + '-' + Math.floor(1000 + Math.random() * 9000);
}

function normalizeAlgorithmType(value) {
    const algorithmTypeMap = {
        '检测': 'detection',
        '追踪': 'tracking',
        '跟踪': 'tracking',
        '预处理': 'preprocessing',
        'detect': 'detection',
        'detection': 'detection',
        'tracking': 'tracking',
        'preprocessing': 'preprocessing',
    };
    return algorithmTypeMap[value] || value;
}

function inferLanguageFromPath(codePath) {
    const lowerCodePath = (codePath || '').toLowerCase();
    if (lowerCodePath.endsWith('.py')) return 'Python';
    if (lowerCodePath.endsWith('.cpp') || lowerCodePath.endsWith('.cc') || lowerCodePath.endsWith('.cxx')) return 'C++';
    if (lowerCodePath.endsWith('.c')) return 'C';
    if (lowerCodePath.endsWith('.java')) return 'Java';
    return 'Python';
}

function buildAlgorithmMockPayload({ name, type, codePath, configPath }) {
    const normalizedType = normalizeAlgorithmType(type);
    const inferredLanguage = inferLanguageFromPath(codePath);
    return {
        algorithmCode: generateAlgorithmCode(),
        algorithmName: name,
        algorithmType: normalizedType,
        framework: inferredLanguage === 'Python' ? 'PyTorch' : 'Custom',
        runtimeType: inferredLanguage === 'Python' ? 'python3.10' : 'native',
        languageType: inferredLanguage,
        codePath,
        configPath,
        description: `${name} 算法，由前端 Demo 自动补全默认元数据`,
        status: 'REGISTERED',
    };
}

function buildVersionMockPayload({ version, versionName, localImageName }) {
    const imageNameParts = localImageName.split(':');
    const repositoryName = imageNameParts[0] || 'demo-algorithm';
    const imageTag = imageNameParts[1] || version;
    return {
        version,
        versionName,
        localImageName,
        entrypoint: 'python main.py',
        sourceRevision: 'mock-source-revision',
        configRevision: 'mock-config-revision',
        changelog: '从前端 Demo 自动补全默认版本元数据',
        sourceType: 'local',
        imagePullPolicy: 'IfNotPresent',
        registryUrl: '',
        repositoryName,
        imageTag,
        imageDigest: '',
        fullImageUri: localImageName,
        imageSize: 0,
        publishStatus: 'DRAFT',
    };
}

function formatApiError(resData, fallbackMessage) {
    if (!resData) return fallbackMessage;
    if (typeof resData.detail === 'string' && resData.detail.trim()) return resData.detail;
    if (Array.isArray(resData.detail) && resData.detail.length > 0) {
        return resData.detail.map(item => {
            const location = Array.isArray(item.loc) ? item.loc.join('.') : 'unknown';
            return `${location}: ${item.msg}`;
        }).join('\n');
    }
    if (typeof resData.message === 'string' && resData.message.trim()) return resData.message;
    return fallbackMessage;
}

async function submitAlgorithm() {
    const btn = document.getElementById('btn-submit-algo');
    const name = document.getElementById('algo-name').value.trim();
    const type = document.getElementById('algo-type').value;
    const codePath = document.getElementById('algo-codepath').value.trim();
    const configPath = document.getElementById('algo-configpath').value.trim();
    if (!name || !codePath || !configPath) {
        alert("请填写所有必填项！");
        return;
    }
    const payload = buildAlgorithmMockPayload({ name, type, codePath, configPath });
    try {
        btn.innerHTML = '注册中...';
        btn.disabled = true;
        const response = await fetch(`${API_BASE_URL}/api/v1/algorithms`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const resData = await response.json();
        if (response.ok && resData.data && resData.data.uuid) {
            const newUuid = resData.data.uuid;
            alert(`🎉 算法注册成功！\n系统生成的算法 UUID 是: ${newUuid}\n(已自动为您填入版本注册面板)`);
            await loadAlgorithms(newUuid);
            switchTab('version');
        } else {
            alert("注册失败：" + (resData.message || "未知错误"));
        }
    } catch (error) {
        console.error("API请求错误:", error);
        alert("网络请求失败，请检查后端服务是否启动。");
    } finally {
        btn.innerHTML = '确认注册算法';
        btn.disabled = false;
    }
}

function fakeValidateImage() {
    const imageName = document.getElementById('local-image-name').value.trim();
    const statusMsg = document.getElementById('image-status-msg');
    if (!imageName) {
        alert("请输入本地镜像名称！");
        return;
    }
    statusMsg.classList.remove('hidden', 'text-green-500', 'text-red-500');
    statusMsg.classList.add('text-indigo-400');
    statusMsg.innerText = "正在模拟连接 Docker Daemon 校验镜像...";
    setTimeout(() => {
        if (imageName.includes(':')) {
            statusMsg.classList.remove('text-indigo-400');
            statusMsg.classList.add('text-green-500');
            statusMsg.innerText = "✅ 校验通过：镜像合法且存在。";
            isImageValidated = true;
        } else {
            statusMsg.classList.remove('text-indigo-400');
            statusMsg.classList.add('text-red-500');
            statusMsg.innerText = "❌ 校验失败：缺少Tag标识 (例: algo:v1)。";
            isImageValidated = false;
        }
    }, 800);
}

async function submitVersion() {
    const selectElem = document.getElementById('version-algo-select');
    const targetUuid = selectElem.value;
    const version = document.getElementById('version-number').value.trim();
    const versionName = document.getElementById('version-name').value.trim();
    const localImageName = document.getElementById('local-image-name').value.trim();
    if (!targetUuid) {
        alert("请在下拉列表中选择一个所属算法！");
        return;
    }
    if (!version || !versionName || !localImageName) {
        alert("请填写所有必填项！");
        return;
    }
    if (!isImageValidated) {
        alert("请先点击【校验镜像】，确保校验通过后才能提交！");
        return;
    }
    const payload = buildVersionMockPayload({ version, versionName, localImageName });
    const btn = document.getElementById('btn-submit-version');
    try {
        btn.innerText = '提交中...';
        btn.disabled = true;
        const response = await fetch(`${API_BASE_URL}/api/v1/algorithms/${targetUuid}/versions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const resData = await response.json();
        if (response.ok) {
            alert("🚀 算法版本注册成功！");
            resetVersionForm();
        } else {
            alert("版本注册失败：" + formatApiError(resData, "后端返回错误"));
        }
    } catch (error) {
        console.error("API请求错误:", error);
        alert("网络请求失败，请检查后端。");
    } finally {
        btn.innerText = '提交并注册版本';
        btn.disabled = false;
    }
}

function resetAlgoForm() {
    document.getElementById('algo-name').value = '';
    document.getElementById('algo-codepath').value = '';
    document.getElementById('algo-configpath').value = '';
}

function resetVersionForm() {
    document.getElementById('version-number').value = '';
    document.getElementById('version-name').value = '';
    document.getElementById('local-image-name').value = '';
    document.getElementById('image-status-msg').classList.add('hidden');
    isImageValidated = false;
}

function resetForm() {
    document.getElementById('algo-name').value = '';
    document.getElementById('algo-version').value = '';
    document.getElementById('algo-type').selectedIndex = 0;
    document.getElementById('algo-tags').value = '';
    document.getElementById('algo-description').value = '';
    document.querySelector('input[name="auth"][value="公开"]').checked = true;
}

async function loadAlgorithmList() {
    const container = document.querySelector('#page-query .grid.grid-cols-1');
    if (!container) return;
    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/algorithms?pageNum=1&pageSize=100`);
        if (!response.ok) throw new Error('加载失败');
        const resData = await response.json();
        const algorithms = (resData.data && resData.data.items) ? resData.data.items : [];
        renderAlgorithmList(algorithms);
    } catch (error) {
        console.error("加载列表报错:", error);
        container.innerHTML = '<div class="glass-panel rounded-xl p-10 text-center text-red-400">加载算法列表失败，请检查后端服务。</div>';
    }
}

function renderAlgorithmList(algorithms) {
    const container = document.querySelector('#page-query .grid.grid-cols-1');
    if (!container) return;
    if (!algorithms || algorithms.length === 0) {
        container.innerHTML = '<div class="glass-panel rounded-xl p-10 text-center text-slate-500">暂无算法，请先去“资产注册”页面添加。</div>';
        return;
    }
    container.innerHTML = algorithms.map(alg => `
        <div class="glass-panel rounded-xl p-5 group hover:border-sky-500/50 transition-all" data-uuid="${alg.uuid}">
            <div class="flex justify-between items-start">
                <div class="flex gap-4">
                    <div class="w-16 h-16 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-sky-400 group-hover:scale-110 transition-transform">
                        <svg class="iconify text-3xl" data-icon="material-symbols:model-training" width="1em" height="1em" viewBox="0 0 24 24">
                            <path d="M5.15 18.85q-1.025-1.2-1.588-2.687T3 13q0-3.75 2.625-6.375T12 4h.2l-1.6-1.6L12 1l4 4l-4 4l-1.425-1.425L12.15 6H12Q9.1 6 7.05 8.05T5 13q0 1.275.412 2.4t1.163 2.025zM11 18.5q0-.575-.387-1.137t-.863-1.175t-.862-1.275T8.5 13.5q0-1.45 1.025-2.475T12 10t2.475 1.025T15.5 13.5q0 .75-.387 1.413t-.863 1.274t-.862 1.175T13 18.5zm0 2.5v-1.5h2V21zm7.85-2.15l-1.425-1.425q.75-.9 1.163-2.025T19 13q0-1.65-.687-3.062t-1.888-2.363L17.85 6.15q1.45 1.25 2.3 3.013T21 13q0 1.675-.562 3.163T18.85 18.85" fill="currentColor"/>
                        </svg>
                    </div>
                    <div>
                        <div class="flex items-center gap-3">
                            <h5 class="text-lg font-bold">${escapeHtml(alg.algorithmName)}</h5>
                            <span class="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300">编码: ${escapeHtml(alg.algorithmCode)}</span>
                            <span class="px-2 py-0.5 rounded text-[10px] bg-sky-500/10 text-sky-400 border border-sky-500/20">${escapeHtml(alg.algorithmType || '未知类型')}</span>
                            <span class="px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">${alg.status === 'ENABLED' ? '已启用' : '已注册'}</span>
                        </div>
                        <p class="text-sm text-slate-500 mt-1 max-w-2xl">${escapeHtml(alg.description) || '暂无描述'}</p>
                        <div class="flex items-center gap-4 mt-3 text-[11px] text-slate-500 italic">
                            <span class="flex items-center gap-1">📋 UUID: ${alg.uuid}</span>
                            <span class="flex items-center gap-1">🕒 更新于: ${alg.updatedAt ? new Date(alg.updatedAt).toLocaleDateString() : '未知'}</span>
                        </div>
                    </div>
                </div>
                <div class="flex flex-col gap-2">
                    <button class="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs transition-colors" onclick="showAlgorithmDetail('${alg.uuid}')">查看详情</button>
                    <button class="px-4 py-1.5 rounded-lg bg-sky-900/30 text-sky-400 hover:bg-sky-900/50 border border-sky-700/50 text-xs transition-colors" onclick="editAlgorithm('${alg.uuid}')">在线修改</button>
                    <button class="px-4 py-1.5 rounded-lg text-rose-400/70 hover:text-rose-400 text-xs transition-colors" onclick="deleteAlgorithm('${alg.uuid}', '${escapeHtml(alg.algorithmName)}')">删除</button>
                </div>
            </div>
        </div>
    `).join('');
}

async function showAlgorithmDetail(uuid) {
    try {
        const algoResponse = await fetch(`${API_BASE_URL}/api/v1/algorithms/${uuid}`);
        if (!algoResponse.ok) throw new Error('获取算法详情失败');
        const algoResData = await algoResponse.json();
        const alg = algoResData.data || algoResData;
        let versions = [];
        try {
            const versionsResponse = await fetch(`${API_BASE_URL}/api/v1/algorithms/${uuid}/versions`);
            if (versionsResponse.ok) {
                const versionsResData = await versionsResponse.json();
                versions = (versionsResData.data && versionsResData.data.items) ? versionsResData.data.items : [];
            }
        } catch (vErr) { console.error("获取版本列表报错:", vErr); }
        let versionsHtml = '';
        if (versions.length === 0) {
            versionsHtml = `<div class="text-slate-500 text-xs italic text-center p-4 bg-slate-900/30 rounded border border-slate-800">暂无关联的版本</div>`;
        } else {
            versionsHtml = versions.map(v => `
                <div class="bg-slate-900/50 rounded-lg p-3 flex justify-between items-center text-sm border border-slate-800 hover:border-indigo-500/50 transition-colors">
                    <div class="flex flex-col">
                        <div><span class="text-sky-400 font-bold">${escapeHtml(v.version)}</span><span class="text-slate-400 text-xs ml-2">${escapeHtml(v.versionName || '')}</span></div>
                        <span class="text-slate-500 text-[10px] mt-1">镜像: ${escapeHtml(v.localImageName || '--')}</span>
                    </div>
                    <div class="flex items-center gap-3">
                        <span class="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400 border border-slate-700">${v.publishStatus || 'DRAFT'}</span>
                        <button onclick="showVersionDetail('${v.uuid}')" class="px-3 py-1.5 bg-indigo-900/30 border border-indigo-700/50 rounded text-xs text-indigo-300 hover:text-white hover:bg-indigo-600 transition-all">版本详情</button>
                    </div>
                </div>
            `).join('');
        }
        const modal = document.getElementById('modal-detail');
        if (!modal) { alert("找不到详情弹窗DOM(id='modal-detail')"); return; }
        modal.querySelector('.font-mono').innerText = `UUID: ${alg.uuid}`;
        const detailBody = modal.querySelector('.flex-1.overflow-y-auto');
        detailBody.innerHTML = `
            <div class="grid grid-cols-2 gap-8">
                <div class="space-y-4">
                    <h6 class="text-xs font-bold text-sky-400 uppercase tracking-widest border-b border-sky-500/20 pb-2 italic">基础元数据</h6>
                    <div class="space-y-2 text-sm">
                        <p><span class="text-slate-400 inline-block w-20">名称：</span> ${escapeHtml(alg.algorithmName)}</p>
                        <p><span class="text-slate-400 inline-block w-20">唯一编码：</span> ${escapeHtml(alg.algorithmCode)}</p>
                        <p><span class="text-slate-400 inline-block w-20">算法类型：</span> ${escapeHtml(alg.algorithmType)}</p>
                        <p><span class="text-slate-400 inline-block w-20">当前状态：</span> ${alg.status === 'ENABLED' ? '✅ 已启用' : alg.status}</p>
                        <p><span class="text-slate-400 inline-block w-20">运行环境：</span> ${escapeHtml(alg.runtimeType) || '未指定'}</p>
                        <p><span class="text-slate-400 inline-block w-20">开发语言：</span> ${escapeHtml(alg.languageType) || '未指定'}</p>
                    </div>
                </div>
                <div class="space-y-4">
                    <h6 class="text-xs font-bold text-indigo-400 uppercase tracking-widest border-b border-indigo-500/20 pb-2 italic">路径与配置</h6>
                    <div class="space-y-2 text-sm">
                        <div class="bg-slate-900/50 p-2 rounded border border-slate-800">
                            <span class="text-slate-500 text-xs block mb-1">外置代码路径 (codePath)</span>
                            <span class="text-sky-300 font-mono text-xs break-all">${escapeHtml(alg.codePath) || '--'}</span>
                        </div>
                        <div class="bg-slate-900/50 p-2 rounded border border-slate-800">
                            <span class="text-slate-500 text-xs block mb-1">外置配置路径 (configPath)</span>
                            <span class="text-indigo-300 font-mono text-xs break-all">${escapeHtml(alg.configPath) || '--'}</span>
                        </div>
                        <p class="mt-2 text-xs text-slate-400"><span class="text-slate-500">创建时间：</span> ${alg.createdAt ? new Date(alg.createdAt).toLocaleString() : '--'}</p>
                    </div>
                </div>
            </div>
            <div class="mt-6 space-y-4">
                <div class="flex items-center justify-between border-b border-purple-500/20 pb-2">
                    <h6 class="text-xs font-bold text-purple-400 uppercase tracking-widest italic">关联版本历史 (${versions.length})</h6>
                </div>
                <div class="space-y-2 max-h-48 overflow-y-auto pr-2 custom-scrollbar">
                    ${versionsHtml}
                </div>
            </div>
            <div class="mt-6 space-y-4">
                <h6 class="text-xs font-bold text-emerald-400 uppercase tracking-widest border-b border-emerald-500/20 pb-2 italic">API 调用示例代码</h6>
                <div class="bg-black/40 rounded-xl p-4 font-mono text-xs text-emerald-400/90 border border-emerald-500/10">
                    <pre>import requests\n\n# 获取算法及版本列表\nurl = "${API_BASE_URL}/api/v1/algorithms/${alg.uuid}/versions"\nresponse = requests.get(url)\nprint(response.json())</pre>
                </div>
            </div>
        `;
        modal.classList.remove('hidden');
        modal.classList.add('flex');
    } catch (error) {
        console.error(error);
        alert('无法获取算法详情，请检查网络或后端服务。');
    }
}

async function showVersionDetail(versionUuid) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/versions/${versionUuid}`);
        if (!response.ok) throw new Error("获取版本详情失败");
        const resData = await response.json();
        const version = resData.data || resData;
        const info = `【版本详细信息】\n
版本号 (version): ${version.version || '--'}
版本名称 (versionName): ${version.versionName || '--'}
所属算法UUID: ${version.algorithmUuid || '--'}
--------------------------------------
本地镜像 (localImageName): ${version.localImageName || '--'}
运行入口 (entrypoint): ${version.entrypoint || '未配置'}
拉取策略 (imagePullPolicy): ${version.imagePullPolicy || '--'}
镜像大小 (imageSize): ${version.imageSize ? (version.imageSize / 1024 / 1024).toFixed(2) + ' MB' : '未知'}
--------------------------------------
变更说明 (changelog):
${version.changelog || '无'}
--------------------------------------
创建时间: ${version.createdAt ? new Date(version.createdAt).toLocaleString() : '--'}`;
        alert(info);
    } catch (error) {
        console.error(error);
        alert("获取版本详情失败，请检查网络或确认 UUID 是否正确！");
    }
}

async function deleteAlgorithm(uuid, name) {
    if (confirm(`确定要删除算法“${name}”吗？此操作不可恢复。`)) {
        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/algorithms/${uuid}`, { method: 'DELETE' });
            if (response.ok) {
                alert('删除成功');
                loadAlgorithmList();
            } else {
                const err = await response.json();
                alert(`删除失败：${err.message || err.detail || '未知错误'}`);
            }
        } catch (error) {
            alert('网络错误，请确认删除接口是否存在。');
        }
    }
}

async function uploadAlgorithmFile() {
    const fileInput = document.getElementById('algo-file');
    const ruleSelect = document.getElementById('validation-rule');
    const versionInput = document.getElementById('version-number');
    const file = fileInput.files[0];
    if (!file) { alert('请选择一个文件'); return; }
    if (!currentAlgorithmId) { alert('请先完成第一步算法注册'); return; }
    const formData = new FormData();
    formData.append('file', file);
    formData.append('rule', ruleSelect.value);
    if (versionInput.value.trim()) formData.append('version_number', versionInput.value.trim());
    try {
        const response = await fetch(`/api/algorithm/upload-file/${currentAlgorithmId}`, { method: 'POST', body: formData });
        const result = await response.json();
        if (response.ok) {
            alert(`文件上传成功！\n版本号：${result.version}\n路径：${result.file_path}`);
            fileInput.value = '';
            versionInput.value = '';
            switchPage('query');
        } else {
            alert(`上传失败：${result.detail}`);
        }
    } catch (error) {
        console.error(error);
        alert('网络错误，请稍后重试');
    }
}

function editAlgorithm(uuid) {
    switchPage('editor');
    loadAlgorithmToEditor(uuid);
}

async function searchAlgorithms() {
    const keyword = document.getElementById('search-keyword').value.trim();
    const algorithmType = document.getElementById('search-type').value;
    let url = `${API_BASE_URL}/api/v1/algorithms?pageNum=1&pageSize=100`;
    if (keyword) url += `&keyword=${encodeURIComponent(keyword)}`;
    if (algorithmType) {
        const normalizedAlgorithmType = normalizeAlgorithmType(algorithmType);
        url += `&algorithmType=${encodeURIComponent(normalizedAlgorithmType)}`;
    }
    const container = document.querySelector('#page-query .grid.grid-cols-1');
    container.innerHTML = `<div class="glass-panel rounded-xl p-16 flex flex-col items-center justify-center text-slate-400 space-y-4">
        <svg class="animate-spin h-10 w-10 text-sky-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
        <span class="text-sm">正在检索中...</span>
    </div>`;
    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error('搜索请求失败');
        const resData = await response.json();
        const algorithms = (resData.data && resData.data.items) ? resData.data.items : [];
        renderAlgorithmList(algorithms);
    } catch (error) {
        console.error(error);
        container.innerHTML = '<div class="glass-panel rounded-xl p-10 text-center text-red-400">搜索失败，请检查后端服务是否正常。</div>';
    }
}

async function loadAlgorithmToEditor(uuid) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/algorithms/${uuid}/hot-update`);
        const resData = await response.json();
        if (!response.ok || resData.code !== 0) {
            alert(`无法加载热更新文件：${resData.message || resData.detail || '未知错误'}`);
            return;
        }
        const hotUpdate = resData.data || resData;
        const editor = document.getElementById('code-editor');
        if (editor) editor.value = hotUpdate.content || '';
        const fileName = hotUpdate.editorPath || '/app/inference/backends/inference.py';
        const filenameElem = document.getElementById('editor-filename');
        if (filenameElem) filenameElem.innerText = fileName;
        const algonameElem = document.getElementById('editor-algo-name');
        if (algonameElem) algonameElem.innerText = `${hotUpdate.algorithmName}[${hotUpdate.algorithmCode}]`;
        window.currentEditAlgorithmId = uuid;
        window.currentEditHotUpdateTarget = hotUpdate;
    } catch (error) {
        console.error(error);
        alert('加载算法到编辑器失败，请检查网络');
    }
}

async function saveHotUpdate() {
    const algorithmId = window.currentEditAlgorithmId;
    if (!algorithmId) { alert('未选中任何算法'); return; }
    const codeContent = document.getElementById('code-editor').value;
    if (!codeContent.trim()) { alert('文件内容不能为空'); return; }
    let versionNumber = prompt("请输入新版本号（例如 v1.0.1），留空则自动生成：");
    versionNumber = versionNumber && versionNumber.trim() ? versionNumber.trim() : null;
    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/algorithms/${algorithmId}/hot-update`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                content: codeContent,
                version: versionNumber,
                changelog: ''
            })
        });
        const result = await response.json();
        if (response.ok && result.code === 0) {
            const data = result.data || {};
            const version = data.version || {};
            alert(`热更新成功！\n生效文件：${data.editorPath || document.getElementById('editor-filename').innerText}\n新版本：${version.version || '-'}\n自动生效：${(data.autoReload && data.autoReload.message) || '容器将自动热重载'}`);
            switchPage('query');
            loadAlgorithmList();
        } else {
            alert(`保存失败：${result.message || result.detail || '未知错误'}`);
        }
    } catch (error) {
        console.error(error);
        alert('网络错误，请稍后重试');
    }
}

function showRollbackDialog() {
    const algorithmId = window.currentEditAlgorithmId;
    if (!algorithmId) {
        alert('请先从算法检索页选择一个算法进入编辑，再执行版本回滚。');
        return;
    }
    alert('版本回滚功能尚未接入当前页面。');
}

// ==================== 样本库管理模块（完整保留自旧版，确保显示） ====================
let sampleCurrentPage = 1;
const samplePageSize = 10;
let sampleTotalAssets = 0;
const samplePreviewConcurrency = 2;
let sampleRenderToken = 0;
let sampleListAbortController = null;
let samplePreviewQueue = [];
let sampleActivePreviewLoads = 0;

async function uploadSample() {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = 'image/*,video/*,application/json,.json,.txt';
    fileInput.onchange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        let mediaType = 'metadata';
        if (file.type.startsWith('image/')) mediaType = 'image';
        else if (file.type.startsWith('video/')) mediaType = 'video';
        let datasetName = prompt('请输入数据集名称（用于分类）:', 'default_dataset');
        if (!datasetName) { alert('数据集名称不能为空，上传已取消'); return; }
        let split = prompt('请输入数据集拆分类型（train/val/test，可选）:', '');
        let sequenceName = prompt('请输入序列名称（可选）:', '');
        let modality = prompt('请输入模态（RGB/IR/DEPTH，可选）:', '');
        const formData = new FormData();
        formData.append('file', file);
        formData.append('media_type', mediaType);
        formData.append('dataset_name', datasetName);
        if (split) formData.append('split', split);
        if (sequenceName) formData.append('sequence_name', sequenceName);
        if (modality) formData.append('modality', modality);
        const uploadBtn = document.querySelector('#upload-sample-btn');
        const originalText = uploadBtn.innerHTML;
        uploadBtn.innerHTML = '<span class="iconify animate-spin" data-icon="material-symbols:sync"></span> 上传中...';
        uploadBtn.disabled = true;
        try {
            const response = await fetch('/api/assets/upload', { method: 'POST', body: formData });
            const result = await response.json();
            if (response.ok) {
                alert(`✅ 上传成功！\n文件名：${result.original_name}\nUUID：${result.uuid}\n大小：${Math.round(result.file_size / 1024)} KB`);
                sampleCurrentPage = 1;
                loadSampleAssets();
            } else {
                alert(`❌ 上传失败：${result.detail || '未知错误'}`);
            }
        } catch (error) {
            console.error(error);
            alert('❌ 网络错误，请检查后端服务是否正常运行');
        } finally {
            uploadBtn.innerHTML = originalText;
            uploadBtn.disabled = false;
        }
    };
    fileInput.click();
}

async function loadSampleAssets() {
    const mediaType = document.getElementById('sample-media-type')?.value || '';
    const datasetName = document.getElementById('sample-dataset-name')?.value || '';
    let url = `/api/assets?pageNum=${sampleCurrentPage}&pageSize=${samplePageSize}`;
    if (mediaType) url += `&media_type=${encodeURIComponent(mediaType)}`;
    if (datasetName) url += `&dataset_name=${encodeURIComponent(datasetName)}`;
    sampleRenderToken += 1;
    const renderToken = sampleRenderToken;
    resetSamplePreviewLoader();
    if (sampleListAbortController) sampleListAbortController.abort();
    sampleListAbortController = new AbortController();
    try {
        const resp = await fetch(url, { signal: sampleListAbortController.signal });
        if (!resp.ok) throw new Error('加载失败');
        const data = await resp.json();
        if (renderToken !== sampleRenderToken) return;
        sampleTotalAssets = data.total;
        renderSampleAssets(data.items, renderToken);
        renderSamplePagination();
        document.getElementById('sample-stats').innerText = `共 ${sampleTotalAssets} 个资产 | 第 ${sampleCurrentPage} 页`;
    } catch (err) {
        if (err.name === 'AbortError') return;
        console.error(err);
        document.getElementById('sample-asset-grid').innerHTML = '<div class="col-span-full text-center text-red-400 py-10">加载资产失败，请检查后端服务</div>';
    }
}

function resetSamplePreviewLoader() {
    samplePreviewQueue = [];
    sampleActivePreviewLoads = 0;
}

function enqueueSamplePreview(img, renderToken) {
    if (!img || renderToken !== sampleRenderToken) return;
    if (img.dataset.previewState === 'queued' || img.dataset.previewState === 'loading' || img.dataset.previewState === 'loaded') {
        return;
    }
    img.dataset.previewState = 'queued';
    samplePreviewQueue.push({ img, renderToken });
    drainSamplePreviewQueue();
}

function drainSamplePreviewQueue() {
    while (sampleActivePreviewLoads < samplePreviewConcurrency && samplePreviewQueue.length > 0) {
        const nextItem = samplePreviewQueue.shift();
        if (!nextItem) return;
        const { img, renderToken } = nextItem;
        if (!img.isConnected || renderToken !== sampleRenderToken) continue;
        const uuid = img.getAttribute('data-uuid');
        const containerDiv = img.closest('.preview-container');
        const loadingDiv = containerDiv?.querySelector('.loading-placeholder');
        if (!uuid || !containerDiv || !loadingDiv) continue;

        img.dataset.previewState = 'loading';
        sampleActivePreviewLoads += 1;

        fetch(`/api/assets/${uuid}/preview-url`)
            .then(res => res.json())
            .then(data => {
                if (renderToken !== sampleRenderToken || !data.url) {
                    throw new Error('无效的预览URL');
                }
                return new Promise((resolve, reject) => {
                    const handleLoad = () => {
                        img.dataset.previewState = 'loaded';
                        img.classList.remove('hidden');
                        loadingDiv.classList.add('hidden');
                        resolve();
                    };
                    const handleError = () => reject(new Error('图片加载失败'));
                    img.addEventListener('load', handleLoad, { once: true });
                    img.addEventListener('error', handleError, { once: true });
                    img.src = data.url;
                });
            })
            .catch(err => {
                console.error(`加载图片 ${uuid} 失败:`, err);
                img.dataset.previewState = 'error';
                if (loadingDiv) {
                    loadingDiv.innerHTML = '<span class="text-xs text-red-400">加载失败</span>';
                }
            })
            .finally(() => {
                sampleActivePreviewLoads = Math.max(0, sampleActivePreviewLoads - 1);
                if (renderToken === sampleRenderToken) {
                    drainSamplePreviewQueue();
                }
            });
    }
}

function renderSampleAssets(assets, renderToken) {
    const container = document.getElementById('sample-asset-grid');
    if (!container) return;
    if (!assets || assets.length === 0) {
        container.innerHTML = '<div class="col-span-full text-center text-slate-500 py-10">暂无资产，请点击“上传新样本”按钮添加</div>';
        return;
    }
    container.innerHTML = assets.map(asset => `
        <div class="group relative aspect-square bg-slate-800 rounded-lg overflow-hidden border border-slate-700 hover:border-sky-500/50 transition-all" data-uuid="${asset.uuid}">
            <div class="preview-container w-full h-full relative bg-slate-900 flex items-center justify-center">
                ${asset.media_type === 'image' ? `
                    <div class="loading-placeholder absolute inset-0 flex items-center justify-center text-slate-500">
                        <span class="iconify animate-spin text-2xl" data-icon="material-symbols:sync"></span>
                    </div>
                    <img class="preview-img hidden w-full h-full object-cover opacity-60 group-hover:opacity-100 transition-opacity"
                         data-uuid="${asset.uuid}"
                         decoding="async"
                         onerror="this.onerror=null; this.classList.add('hidden'); this.parentElement.querySelector('.loading-placeholder').innerHTML = '<span class=\\'text-xs text-red-400\\'>加载失败</span>';">
                ` : `
                    <div class="w-full h-full flex items-center justify-center bg-slate-900">
                        <span class="iconify text-5xl text-slate-600" data-icon="material-symbols:${asset.media_type === 'video' ? 'play-circle' : 'description'}"></span>
                    </div>
                `}
            </div>
            <div class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/90 to-transparent p-3 translate-y-2 group-hover:translate-y-0 transition-transform">
                <p class="text-[10px] font-bold text-white truncate">${escapeHtml(asset.original_name)}</p>
                <div class="flex justify-between mt-1">
                    <span class="text-[8px] text-sky-400">${asset.media_type} | ${Math.round(asset.file_size / 1024)}KB</span>
                    <span class="text-[8px] text-slate-400">${asset.dataset_name || '未分类'}</span>
                </div>
            </div>
            <div class="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button onclick="previewSample('${asset.uuid}')" class="p-1.5 bg-slate-900/80 rounded hover:bg-sky-500 text-white">
                    <span class="iconify text-xs" data-icon="material-symbols:visibility"></span>
                </button>
                <button onclick="downloadSample('${asset.uuid}')" class="p-1.5 bg-slate-900/80 rounded hover:bg-indigo-500 text-white">
                    <span class="iconify text-xs" data-icon="material-symbols:download"></span>
                </button>
                <button onclick="deleteSample('${asset.uuid}')" class="p-1.5 bg-slate-900/80 rounded hover:bg-rose-500 text-white">
                    <span class="iconify text-xs" data-icon="material-symbols:delete"></span>
                </button>
            </div>
            ${asset.split ? `<span class="absolute top-2 left-2 px-2 py-0.5 rounded text-[8px] bg-sky-500/80 text-white">${escapeHtml(asset.split)}</span>` : ''}
        </div>
    `).join('');

    const previewImages = Array.from(container.querySelectorAll('.preview-img'));
    previewImages.forEach(img => {
        img.dataset.previewState = 'idle';
        enqueueSamplePreview(img, renderToken);
    });
}

async function previewSample(uuid) {
    try {
        const resp = await fetch(`/api/assets/${uuid}/preview-url`);
        if (!resp.ok) throw new Error('获取预览URL失败');
        const data = await resp.json();
        window.open(data.url, '_blank');
    } catch (err) { alert('预览失败：' + err.message); }
}

async function downloadSample(uuid) {
    try {
        const resp = await fetch(`/api/assets/${uuid}/download-url`);
        if (!resp.ok) throw new Error('获取下载URL失败');
        const data = await resp.json();
        window.open(data.url, '_blank');
    } catch (err) { alert('下载失败：' + err.message); }
}

async function deleteSample(uuid) {
    if (!confirm('确定将该资产移至回收站吗？')) return;
    try {
        const resp = await fetch(`/api/assets/${uuid}`, { method: 'DELETE' });
        if (resp.ok) {
            alert('删除成功（已移至回收站）');
            loadSampleAssets();
        } else {
            const err = await resp.json();
            alert(`删除失败：${err.detail}`);
        }
    } catch (err) { alert('网络错误，删除失败'); }
}

function renderSamplePagination() {
    const totalPages = Math.ceil(sampleTotalAssets / samplePageSize);
    const container = document.getElementById('sample-pagination');
    if (!container) return;
    if (totalPages <= 1) { container.innerHTML = ''; return; }
    const startPage = Math.max(1, sampleCurrentPage - 2);
    const endPage = Math.min(totalPages, sampleCurrentPage + 2);
    let html = `<button class="px-3 py-1 rounded text-xs ${sampleCurrentPage === 1 ? 'bg-slate-800 text-slate-500 cursor-not-allowed' : 'bg-slate-700 hover:bg-slate-600'}" ${sampleCurrentPage === 1 ? 'disabled' : `onclick="goToSamplePage(${sampleCurrentPage - 1})"`}>上一页</button>`;
    if (startPage > 1) {
        html += `<button class="px-3 py-1 rounded text-xs bg-slate-700 hover:bg-slate-600" onclick="goToSamplePage(1)">1</button>`;
        if (startPage > 2) html += `<span class="px-2 text-xs text-slate-500">...</span>`;
    }
    for (let i = startPage; i <= endPage; i++) {
        html += `<button class="px-3 py-1 rounded text-xs ${i === sampleCurrentPage ? 'bg-sky-600' : 'bg-slate-700 hover:bg-slate-600'}" onclick="goToSamplePage(${i})">${i}</button>`;
    }
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) html += `<span class="px-2 text-xs text-slate-500">...</span>`;
        html += `<button class="px-3 py-1 rounded text-xs bg-slate-700 hover:bg-slate-600" onclick="goToSamplePage(${totalPages})">${totalPages}</button>`;
    }
    html += `<button class="px-3 py-1 rounded text-xs ${sampleCurrentPage === totalPages ? 'bg-slate-800 text-slate-500 cursor-not-allowed' : 'bg-slate-700 hover:bg-slate-600'}" ${sampleCurrentPage === totalPages ? 'disabled' : `onclick="goToSamplePage(${sampleCurrentPage + 1})"`}>下一页</button>`;
    container.innerHTML = html;
}

function goToSamplePage(page) {
    sampleCurrentPage = page;
    loadSampleAssets();
}

function initSampleFilters() {
    const filterBtn = document.getElementById('sample-filter-btn');
    if (filterBtn) filterBtn.addEventListener('click', () => { sampleCurrentPage = 1; loadSampleAssets(); });
    const datasetInput = document.getElementById('sample-dataset-name');
    if (datasetInput) datasetInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') { sampleCurrentPage = 1; loadSampleAssets(); } });
}

// ==================== UUID 查询模式 ====================
let isUuidSearchMode = false;

async function searchAssetByUuid() {
    const uuidInput = document.getElementById('sample-uuid-search');
    const uuid = uuidInput.value.trim();
    if (!uuid) { alert('请输入有效的 UUID'); return; }
    const gridContainer = document.getElementById('sample-asset-grid');
    gridContainer.innerHTML = '<div class="col-span-full text-center text-slate-400 py-10">正在查询...</div>';
    try {
        const response = await fetch(`/api/assets/${uuid}`);
        if (!response.ok) {
            if (response.status === 404) gridContainer.innerHTML = `<div class="col-span-full text-center text-amber-400 py-10">未找到 UUID 为 ${uuid} 的资产，请检查后重试。</div>`;
            else throw new Error('查询失败');
            document.getElementById('sample-pagination').innerHTML = '';
            document.getElementById('sample-show-all-btn').classList.remove('hidden');
            isUuidSearchMode = true;
            document.getElementById('sample-stats').innerText = `UUID 查询模式：${uuid}`;
            return;
        }
        const asset = await response.json();
        renderSampleAssets([asset]);
        document.getElementById('sample-pagination').innerHTML = '';
        document.getElementById('sample-show-all-btn').classList.remove('hidden');
        isUuidSearchMode = true;
        document.getElementById('sample-stats').innerText = `UUID 查询结果：${asset.original_name} (${asset.uuid})`;
    } catch (error) {
        console.error(error);
        gridContainer.innerHTML = '<div class="col-span-full text-center text-red-400 py-10">网络错误，请检查后端服务</div>';
        document.getElementById('sample-show-all-btn').classList.remove('hidden');
        isUuidSearchMode = true;
    }
}

function resetToNormalList() {
    isUuidSearchMode = false;
    document.getElementById('sample-uuid-search').value = '';
    document.getElementById('sample-show-all-btn').classList.add('hidden');
    sampleCurrentPage = 1;
    loadSampleAssets();
}

function initUuidSearch() {
    const uuidSearchBtn = document.getElementById('sample-uuid-search-btn');
    if (uuidSearchBtn) uuidSearchBtn.addEventListener('click', searchAssetByUuid);
    const showAllBtn = document.getElementById('sample-show-all-btn');
    if (showAllBtn) showAllBtn.addEventListener('click', resetToNormalList);
    const uuidInput = document.getElementById('sample-uuid-search');
    if (uuidInput) uuidInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') searchAssetByUuid(); });
}

// ==================== 视觉算法推理模块（完整保留） ====================
let visionAlgorithms = [];
let selectedAssetUuids = [];
let allVisionAssets = [];
const VISION_ASSET_BUCKET = 'raw-images';
const VISION_SEQUENCE_ROOT_PREFIX = 'DUT-Anti-UAV';
let visionSequenceOptions = [];
let currentVisionSequencePrefix = '';
let visionTrackingPlaybackData = {};
let visionTrackingPlaybackState = {};

async function uploadVisionAsset() {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = 'image/*';
    fileInput.onchange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        if (!file.type.startsWith('image/')) { alert('请选择图片文件（jpg/png等）'); return; }
        let datasetName = prompt('请输入数据集名称（用于分类）:', 'DUT-Anti-UAV');
        if (!datasetName) { alert('数据集名称不能为空'); return; }
        const formData = new FormData();
        formData.append('file', file);
        formData.append('media_type', 'image');
        formData.append('dataset_name', datasetName);
        const uploadBtn = document.getElementById('vision-upload-btn');
        const originalText = uploadBtn.innerHTML;
        uploadBtn.innerHTML = '<span class="iconify animate-spin" data-icon="material-symbols:sync"></span> 上传中...';
        uploadBtn.disabled = true;
        try {
            const response = await fetch('/api/assets/upload', { method: 'POST', body: formData });
            const result = await response.json();
            if (response.ok) {
                alert(`✅ 上传成功！\n文件: ${result.original_name}\nUUID: ${result.uuid}`);
                loadVisionAssets();
            } else {
                alert(`❌ 上传失败：${result.detail || '未知错误'}`);
            }
        } catch (err) {
            console.error(err);
            alert('网络错误，上传失败');
        } finally {
            uploadBtn.innerHTML = originalText;
            uploadBtn.disabled = false;
        }
    };
    fileInput.click();
}

async function loadVisionSequences() {
    const select = document.getElementById('vision-sequence-select');
    if (!select) return;
    select.innerHTML = '<option value="">-- 加载序列中 --</option>';
    try {
        const params = new URLSearchParams({
            bucket_name: VISION_ASSET_BUCKET,
            object_prefix: VISION_SEQUENCE_ROOT_PREFIX,
        });
        const resp = await fetch(`/api/assets/minio-sequences?${params.toString()}`);
        if (!resp.ok) throw new Error('加载序列失败');
        const data = await resp.json();
        visionSequenceOptions = data.items || [];
        if (visionSequenceOptions.length === 0) {
            select.innerHTML = '<option value="">暂无序列</option>';
            currentVisionSequencePrefix = '';
            return;
        }
        select.innerHTML = visionSequenceOptions.map(item => `
            <option value="${escapeHtml(item.object_prefix)}">${escapeHtml(item.sequence_name)}</option>
        `).join('');
        currentVisionSequencePrefix = visionSequenceOptions[0].object_prefix;
        select.value = currentVisionSequencePrefix;
    } catch (err) {
        console.error(err);
        select.innerHTML = '<option value="">序列加载失败</option>';
        currentVisionSequencePrefix = '';
    }
}

async function loadVisionAssets() {
    const container = document.getElementById('vision-asset-carousel');
    if (!container) return;
    container.innerHTML = '<div class="text-center text-slate-500 w-full py-8">加载资产中...</div>';
    if (!currentVisionSequencePrefix) {
        container.innerHTML = '<div class="text-center text-slate-500 w-full py-8">请先选择图像序列。</div>';
        allVisionAssets = [];
        selectedAssetUuids = [];
        updateSelectedAssetsPreview();
        updateVisionSequenceHint();
        return;
    }
    try {
        const params = new URLSearchParams({
            bucket_name: VISION_ASSET_BUCKET,
            object_prefix: currentVisionSequencePrefix,
            media_type: 'image',
            pageSize: '500'
        });
        const resp = await fetch(`/api/assets/minio-prefix?${params.toString()}`);
        if (!resp.ok) throw new Error('加载资产失败');
        const data = await resp.json();
        const assets = data.items || [];
        allVisionAssets = assets;
        updateVisionSequenceHint();
        const visibleUuids = new Set(assets.map(asset => asset.uuid));
        selectedAssetUuids = selectedAssetUuids.filter(uuid => visibleUuids.has(uuid));
        if (assets.length === 0) {
            container.innerHTML = `<div class="text-center text-slate-500 w-full py-8">暂无 ${escapeHtml(`${VISION_ASSET_BUCKET}/${currentVisionSequencePrefix}`)} 图像资产。</div>`;
            updateSelectedAssetsPreview();
            return;
        }
        container.innerHTML = assets.map(asset => `
            <div class="vision-asset-card flex-shrink-0 w-40 bg-slate-800/60 rounded-lg overflow-hidden border-2 cursor-pointer transition-all"
                 data-uuid="${asset.uuid}" data-name="${escapeHtml(asset.original_name)}">
                <div class="aspect-square bg-slate-900 relative">
                    <div class="loading-placeholder absolute inset-0 flex items-center justify-center text-slate-500">
                        <span class="iconify animate-spin text-2xl" data-icon="material-symbols:sync"></span>
                    </div>
                    <img class="preview-img hidden w-full h-full object-cover" data-uuid="${asset.uuid}"
                         onerror="this.onerror=null; this.classList.add('hidden'); this.parentElement.querySelector('.loading-placeholder').innerHTML = '<span class=\\'text-xs text-red-400\\'>加载失败</span>';">
                    <div class="selected-mark absolute top-1 right-1 hidden">
                        <span class="iconify text-sky-400 text-xl" data-icon="material-symbols:check-circle"></span>
                    </div>
                </div>
                <div class="p-2 truncate text-center">
                    <p class="text-xs font-medium truncate" title="${escapeHtml(asset.original_name)}">${escapeHtml(asset.original_name)}</p>
                    <p class="text-[10px] text-slate-400">${Math.round(asset.file_size/1024)}KB</p>
                </div>
            </div>
        `).join('');
        const previewImages = container.querySelectorAll('.preview-img');
        previewImages.forEach(img => {
            const uuid = img.getAttribute('data-uuid');
            const card = img.closest('.vision-asset-card');
            const loadingDiv = card?.querySelector('.loading-placeholder');
            if (!card || !loadingDiv) return;
            fetch(`/api/assets/${uuid}/preview-url`)
                .then(res => res.json())
                .then(data => {
                    if (data.url) {
                        img.src = data.url;
                        img.classList.remove('hidden');
                        loadingDiv.classList.add('hidden');
                    } else throw new Error('无效的预览URL');
                })
                .catch(err => {
                    console.error(`加载图片 ${uuid} 失败:`, err);
                    if (loadingDiv) loadingDiv.innerHTML = '<span class="text-xs text-red-400">加载失败</span>';
                });
        });
        document.querySelectorAll('.vision-asset-card').forEach(card => {
            card.addEventListener('click', (e) => {
                e.stopPropagation();
                if (currentVisionAlgorithmType() === 'tracking') {
                    return;
                }
                const uuid = card.getAttribute('data-uuid');
                if (!uuid) return;
                const idx = selectedAssetUuids.indexOf(uuid);
                if (idx === -1) selectedAssetUuids.push(uuid);
                else selectedAssetUuids.splice(idx, 1);
                updateCardHighlight(card, uuid);
                updateSelectedAssetsPreview();
            });
        });
        document.querySelectorAll('.vision-asset-card').forEach(card => {
            const uuid = card.getAttribute('data-uuid');
            updateCardHighlight(card, uuid);
        });
        syncTrackingSelectionWithSequence();
        updateSelectedAssetsPreview();
    } catch (err) {
        console.error(err);
        container.innerHTML = '<div class="text-center text-red-400 w-full py-8">加载资产失败，请检查后端服务</div>';
    }
}

function updateCardHighlight(card, uuid) {
    if (currentVisionAlgorithmType() === 'tracking') {
        card.classList.remove('border-sky-500', 'shadow-lg', 'shadow-sky-500/20');
        const mark = card.querySelector('.selected-mark');
        if (mark) mark.classList.add('hidden');
        return;
    }
    if (selectedAssetUuids.includes(uuid)) {
        card.classList.add('border-sky-500', 'shadow-lg', 'shadow-sky-500/20');
        const mark = card.querySelector('.selected-mark');
        if (mark) mark.classList.remove('hidden');
    } else {
        card.classList.remove('border-sky-500', 'shadow-lg', 'shadow-sky-500/20');
        const mark = card.querySelector('.selected-mark');
        if (mark) mark.classList.add('hidden');
    }
}

async function updateSelectedAssetsPreview() {
    const container = document.getElementById('selected-assets-container');
    if (!container) return;
    if (currentVisionAlgorithmType() === 'tracking') {
        container.innerHTML = `
            <div class="w-full text-xs text-slate-400 leading-6">
                当前为跟踪模式，将直接使用所选序列的全部 <span class="text-cyan-300 font-semibold">${escapeHtml(String(allVisionAssets.length))}</span> 帧按顺序推理。
            </div>
        `;
        return;
    }
    if (selectedAssetUuids.length === 0) {
        container.innerHTML = '<div class="text-xs text-slate-500 w-full text-center">暂无选中资产，请点击上方图片选择</div>';
        return;
    }
    const selectedAssets = allVisionAssets.filter(asset => selectedAssetUuids.includes(asset.uuid));
    container.innerHTML = selectedAssets.map(asset => `
        <div class="selected-asset-item relative w-20 h-20 bg-slate-800 rounded overflow-hidden border border-slate-600 group" data-uuid="${asset.uuid}">
            <div class="loading-placeholder-small absolute inset-0 flex items-center justify-center text-slate-500">
                <span class="iconify animate-spin text-sm" data-icon="material-symbols:sync"></span>
            </div>
            <img class="preview-img-small hidden w-full h-full object-cover" data-uuid="${asset.uuid}"
                 onerror="this.onerror=null; this.classList.add('hidden'); this.parentElement.querySelector('.loading-placeholder-small').innerHTML = '<span class=\\'text-red-400 text-[8px]\\'>错误</span>';">
            <button class="remove-selected absolute -top-1 -right-1 w-5 h-5 rounded-full bg-rose-500 text-white flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity" data-uuid="${asset.uuid}">×</button>
        </div>
    `).join('');
    const smallImgs = container.querySelectorAll('.preview-img-small');
    smallImgs.forEach(img => {
        const uuid = img.getAttribute('data-uuid');
        const parent = img.closest('.selected-asset-item');
        const loadingDiv = parent?.querySelector('.loading-placeholder-small');
        if (!parent || !loadingDiv) return;
        fetch(`/api/assets/${uuid}/preview-url`)
            .then(res => res.json())
            .then(data => {
                if (data.url) {
                    img.src = data.url;
                    img.classList.remove('hidden');
                    loadingDiv.classList.add('hidden');
                } else throw new Error('无效URL');
            })
            .catch(err => {
                console.error(`加载预览小图 ${uuid} 失败`, err);
                if (loadingDiv) loadingDiv.innerHTML = '<span class="text-red-400 text-[8px]">失败</span>';
            });
    });
    container.querySelectorAll('.remove-selected').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const uuid = btn.getAttribute('data-uuid');
            if (uuid) {
                const idx = selectedAssetUuids.indexOf(uuid);
                if (idx !== -1) selectedAssetUuids.splice(idx, 1);
                const originalCard = document.querySelector(`.vision-asset-card[data-uuid="${uuid}"]`);
                if (originalCard) updateCardHighlight(originalCard, uuid);
                updateSelectedAssetsPreview();
            }
        });
    });
}

async function loadVisionAlgorithms() {
    try {
        const resp = await fetch('/api/v1/vision/algorithms');
        if (!resp.ok) throw new Error('加载算法失败');
        const payload = await resp.json();
        const algorithms = payload.items || [];
        visionAlgorithms = algorithms;
        const select = document.getElementById('vision-algorithm-select');
        if (!select) return;
        select.innerHTML = '<option value="">-- 请选择算法 --</option>' +
            algorithms.map(alg => `
                <option
                    value="${alg.versionUuid}"
                    data-algorithm-type="${escapeHtml(alg.algorithmType || '')}"
                >
                    ${escapeHtml(alg.algorithmName)} / ${escapeHtml(alg.versionName || alg.version)} / ${escapeHtml(alg.publishStatus || 'UNKNOWN')}
                </option>
            `).join('');
        updateVisionSequenceHint();
    } catch (err) {
        console.error(err);
        const select = document.getElementById('vision-algorithm-select');
        if (select) select.innerHTML = '<option value="">加载算法失败</option>';
    }
}

function currentVisionAlgorithmType() {
    const select = document.getElementById('vision-algorithm-select');
    if (!select) return '';
    const selectedOption = select.options[select.selectedIndex];
    return selectedOption?.dataset.algorithmType || '';
}

function syncTrackingSelectionWithSequence() {
    if (currentVisionAlgorithmType() !== 'tracking') return;
    selectedAssetUuids = [];
}

function updateVisionSequenceHint() {
    const hint = document.getElementById('vision-sequence-hint');
    if (!hint) return;
    const algorithmType = currentVisionAlgorithmType();
    const frameCount = allVisionAssets.length;
    const sequenceLabel = currentVisionSequencePrefix || '未选择';
    if (algorithmType === 'tracking') {
        hint.textContent = `当前序列：${sequenceLabel}，跟踪模式将按顺序使用全部 ${frameCount} 帧，并从 raw-annotations 自动匹配首帧初始化框。`;
        return;
    }
    hint.textContent = `当前序列：${sequenceLabel}，可从中选择单帧进行检测/预处理。`;
}

async function runVisionInference() {
    const select = document.getElementById('vision-algorithm-select');
    const versionUuid = select.value;
    const selectedOption = select.options[select.selectedIndex];
    const algorithmType = selectedOption?.dataset.algorithmType || '';
    if (!versionUuid) { alert('请先选择算法'); return; }
    const resultArea = document.getElementById('vision-result-area');
    const runBtn = document.getElementById('vision-run-btn');
    resultArea.innerHTML = '<div class="text-sky-400 flex items-center gap-2"><span class="iconify animate-spin" data-icon="material-symbols:sync"></span> 推理中，请稍候...</div>';
    runBtn.disabled = true;
    runBtn.classList.add('opacity-50');
    let allResults = [];
    let hasError = false;

    if (algorithmType === 'tracking') {
        const trackingAssetUuids = allVisionAssets.map(asset => asset.uuid);
        if (trackingAssetUuids.length < 2) { alert('当前序列至少需要 2 帧才能执行跟踪推理'); runBtn.disabled = false; runBtn.classList.remove('opacity-50'); return; }
        const liveTrackingItem = {
            asset_uuids: trackingAssetUuids,
            success: true,
            sequence_prefix: currentVisionSequencePrefix,
            result: {
                mode: 'tracking',
                template_asset_uuid: null,
                template_bbox: null,
                init_result: null,
                track_results: [],
            },
        };
        try {
            const response = await fetch('/api/v1/vision/tracking-stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    version_uuid: versionUuid,
                    asset_uuids: trackingAssetUuids,
                })
            });
            if (!response.ok || !response.body) {
                const payload = await response.json().catch(() => null);
                allResults.push({ asset_uuids: trackingAssetUuids, error: formatInferenceError(payload), success: false, sequence_prefix: currentVisionSequencePrefix });
                hasError = true;
            } else {
                renderVisionTrackingStreamingState(resultArea, liveTrackingItem, '初始化中...');
                let streamFailed = false;
                await consumeNdjsonStream(response, (event) => {
                    if (!event || typeof event !== 'object') return;
                    if (event.event === 'init') {
                        liveTrackingItem.result.init_result = event.init_result || null;
                        liveTrackingItem.result.template_asset_uuid = event.template_asset_uuid || null;
                        liveTrackingItem.result.template_bbox = event.template_bbox || null;
                        renderVisionTrackingStreamingState(resultArea, liveTrackingItem, '已完成初始化，开始跟踪...');
                        return;
                    }
                    if (event.event === 'frame') {
                        liveTrackingItem.result.track_results.push({
                            asset_uuid: event.asset_uuid,
                            frame_index: event.frame_index,
                            runtime_result: event.runtime_result,
                        });
                        renderVisionTrackingStreamingState(
                            resultArea,
                            liveTrackingItem,
                            `跟踪中... ${liveTrackingItem.result.track_results.length + 1}/${trackingAssetUuids.length}`
                        );
                        return;
                    }
                    if (event.event === 'error') {
                        streamFailed = true;
                        allResults = [{
                            asset_uuids: trackingAssetUuids,
                            error: typeof event.detail === 'string' ? event.detail : JSON.stringify(event.detail || event),
                            success: false,
                            sequence_prefix: currentVisionSequencePrefix,
                        }];
                        hasError = true;
                    }
                });
                if (!streamFailed) {
                    allResults.push(liveTrackingItem);
                }
            }
        } catch (err) {
            console.error(err);
            allResults.push({ asset_uuids: trackingAssetUuids, error: '网络错误', success: false, sequence_prefix: currentVisionSequencePrefix });
            hasError = true;
        }
    } else {
        if (selectedAssetUuids.length === 0) { alert('请至少选择一个资产'); runBtn.disabled = false; runBtn.classList.remove('opacity-50'); return; }
        for (let i = 0; i < selectedAssetUuids.length; i++) {
            const assetUuid = selectedAssetUuids[i];
            try {
                const response = await fetch('/api/v1/vision/inference', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ asset_uuid: assetUuid, version_uuid: versionUuid })
                });
                const data = await response.json();
                if (response.ok && data.success) {
                    allResults.push({ asset_uuid: assetUuid, result: data.result, success: true });
                } else {
                    allResults.push({ asset_uuid: assetUuid, error: formatInferenceError(data), success: false });
                    hasError = true;
                }
            } catch (err) {
                console.error(err);
                allResults.push({ asset_uuid: assetUuid, error: '网络错误', success: false });
                hasError = true;
            }
            resultArea.innerHTML = `<pre class="text-emerald-300 text-sm">已完成 ${i+1}/${selectedAssetUuids.length}...\n${JSON.stringify(allResults, null, 2)}</pre>`;
        }
    }
    renderVisionInferenceResults(resultArea, allResults, hasError);
    runBtn.disabled = false;
    runBtn.classList.remove('opacity-50');
}

async function consumeNdjsonStream(response, onEvent) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const rawLine of lines) {
            const line = rawLine.trim();
            if (!line) continue;
            try {
                onEvent(JSON.parse(line));
            } catch (err) {
                console.error('解析 tracking stream 失败', err, line);
            }
        }
        if (done) break;
    }
    const tail = buffer.trim();
    if (tail) {
        try {
            onEvent(JSON.parse(tail));
        } catch (err) {
            console.error('解析 tracking stream 尾包失败', err, tail);
        }
    }
}

function formatInferenceError(payload) {
    if (!payload) return '推理失败';
    if (typeof payload.detail === 'string' && payload.detail) return payload.detail;
    if (typeof payload.message === 'string' && payload.message) return payload.message;
    if (payload.detail && typeof payload.detail === 'object') return JSON.stringify(payload.detail);
    return '推理失败';
}

function renderVisionInferenceResults(container, allResults, hasError) {
    if (!container) return;
    stopAllTrackingPlayers();
    const title = hasError ? '部分推理失败' : '推理完成';
    container.innerHTML = `
        <div class="space-y-4">
            <div class="${hasError ? 'text-yellow-300' : 'text-emerald-300'} text-sm font-semibold">${title}</div>
            <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
                ${allResults.map(renderVisionInferenceCard).join('')}
            </div>
        </div>
    `;
    initTrackingPlayers(container);
}

function renderVisionInferenceCard(item) {
    if (!item || !item.success) {
        return `
            <div class="rounded-2xl border border-yellow-500/30 bg-slate-900/80 p-4">
                <div class="text-yellow-300 font-semibold text-sm">推理失败</div>
                <div class="text-slate-300 text-xs mt-2 break-all">${escapeHtml(item?.asset_uuid || (item?.asset_uuids || []).join(', '))}</div>
                <pre class="mt-3 text-xs text-rose-300 whitespace-pre-wrap break-words">${escapeHtml(item?.error || '未知错误')}</pre>
            </div>
        `;
    }

    if (item.result?.mode === 'preprocessing') {
        return renderVisionPreprocessCard(item);
    }
    if (item.result?.mode === 'tracking') {
        return renderVisionTrackingCard(item);
    }

    const runtimeResult = item.result?.runtime_result || {};
    const annotatedImageBase64 = runtimeResult.annotated_image_base64 || '';
    const annotatedMediaType = runtimeResult.annotated_media_type || 'image/jpeg';
    const detections = Array.isArray(runtimeResult.detections) ? runtimeResult.detections : [];
    const detectionCount = runtimeResult.num_detections ?? detections.length ?? 0;
    const summary = {
        asset_uuid: item.asset_uuid || null,
        mode: item.result?.mode || null,
        model_name: runtimeResult.model_name || null,
        num_detections: detectionCount,
        detections: detections,
        yolo_txt: runtimeResult.yolo_txt || '',
    };

    return `
        <div class="rounded-2xl border border-emerald-500/20 bg-slate-900/80 p-4 space-y-3">
            <div class="flex items-center justify-between gap-3">
                <div>
                    <div class="text-emerald-300 font-semibold text-sm">检测成功</div>
                    <div class="text-slate-400 text-xs break-all">${escapeHtml(item.asset_uuid || '')}</div>
                </div>
                <div class="text-right">
                    <div class="text-slate-300 text-xs">目标数</div>
                    <div class="text-xl font-bold text-white">${escapeHtml(String(detectionCount))}</div>
                </div>
            </div>
            ${annotatedImageBase64 ? `
                <div class="overflow-hidden rounded-xl border border-slate-700 bg-slate-950/60">
                    <img
                        src="data:${escapeHtml(annotatedMediaType)};base64,${annotatedImageBase64}"
                        alt="检测结果图"
                        class="w-full h-auto object-contain"
                    >
                </div>
            ` : `
                <div class="rounded-xl border border-dashed border-slate-700 bg-slate-950/40 px-4 py-6 text-center text-xs text-slate-400">
                    当前结果未返回标注图像
                </div>
            `}
            <details class="rounded-xl border border-slate-700 bg-slate-950/50 p-3">
                <summary class="cursor-pointer text-xs text-sky-300">查看结构化结果</summary>
                <pre class="mt-3 text-xs text-slate-200 whitespace-pre-wrap break-words">${escapeHtml(JSON.stringify(summary, null, 2))}</pre>
            </details>
        </div>
    `;
}

function renderVisionTrackingCard(item) {
    const result = item.result || {};
    const initResult = result.init_result || {};
    const trackResults = Array.isArray(result.track_results) ? result.track_results : [];
    const playbackFrames = trackResults
        .map((entry, idx) => {
            const runtime = entry.runtime_result || {};
            const imageBase64 = runtime.tracked_image_base64 || '';
            if (!imageBase64) return null;
            return {
                asset_uuid: entry.asset_uuid || null,
                frame_index: entry.frame_index ?? idx + 1,
                image_base64: imageBase64,
                image_media_type: runtime.tracked_media_type || 'image/jpeg',
                bbox_xyxy: runtime.bbox_xyxy || null,
                score: runtime.score ?? null,
            };
        })
        .filter(Boolean);
    const fallbackPreview = initResult.cached_template_base64 || '';
    const fallbackMediaType = initResult.cached_template_media_type || 'image/jpeg';
    const cardId = `tracking-player-${Object.keys(visionTrackingPlaybackData).length + 1}`;
    visionTrackingPlaybackData[cardId] = {
        frames: playbackFrames,
        fallbackPreview,
        fallbackMediaType,
    };
    const initialFrame = playbackFrames[0] || null;
    const summary = {
        mode: result.mode || null,
        sequence_prefix: item.sequence_prefix || null,
        template_asset_uuid: result.template_asset_uuid || null,
        template_bbox: result.template_bbox || null,
        frame_count: trackResults.length + 1,
        playback_frame_count: playbackFrames.length,
        last_bbox_xyxy: trackResults.length > 0 ? (trackResults[trackResults.length - 1].runtime_result || {}).bbox_xyxy || null : null,
        last_score: trackResults.length > 0 ? (trackResults[trackResults.length - 1].runtime_result || {}).score ?? null : null,
    };

    return `
        <div class="rounded-2xl border border-cyan-500/20 bg-slate-900/80 p-4 space-y-3">
            <div class="flex items-center justify-between gap-3">
                <div>
                    <div class="text-cyan-300 font-semibold text-sm">跟踪成功</div>
                    <div class="text-slate-400 text-xs break-all">${escapeHtml(item.sequence_prefix || '')}</div>
                </div>
                <div class="text-right">
                    <div class="text-slate-300 text-xs">帧数</div>
                    <div class="text-xl font-bold text-white">${escapeHtml(String(trackResults.length + 1))}</div>
                </div>
            </div>
            ${initialFrame || fallbackPreview ? `
                <div class="vision-tracking-player space-y-3" data-player-id="${escapeHtml(cardId)}">
                    <div class="overflow-hidden rounded-xl border border-slate-700 bg-slate-950/60">
                        <img
                            id="${escapeHtml(cardId)}-image"
                            src="${initialFrame ? `data:${escapeHtml(initialFrame.image_media_type)};base64,${initialFrame.image_base64}` : `data:${escapeHtml(fallbackMediaType)};base64,${fallbackPreview}`}"
                            alt="跟踪结果图"
                            class="w-full h-auto object-contain"
                        >
                    </div>
                    <div class="flex items-center justify-between gap-3 text-xs">
                        <div class="text-slate-300">
                            <span id="${escapeHtml(cardId)}-frame-label">帧 ${escapeHtml(String(initialFrame ? initialFrame.frame_index : 0))}/${escapeHtml(String(playbackFrames.length || 0))}</span>
                            <span class="mx-2 text-slate-600">|</span>
                            <span id="${escapeHtml(cardId)}-score-label">score: ${escapeHtml(String(initialFrame?.score ?? '-'))}</span>
                        </div>
                        <div class="flex items-center gap-2">
                            <button type="button" class="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 transition-colors" data-action="prev">上一帧</button>
                            <button type="button" class="px-2 py-1 rounded bg-cyan-700 hover:bg-cyan-600 text-white transition-colors" data-action="play">播放</button>
                            <button type="button" class="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 transition-colors" data-action="next">下一帧</button>
                        </div>
                    </div>
                    <div id="${escapeHtml(cardId)}-bbox-label" class="text-[11px] text-slate-400 break-all">
                        bbox: ${escapeHtml(JSON.stringify(initialFrame?.bbox_xyxy || null))}
                    </div>
                </div>
            ` : `
                <div class="rounded-xl border border-dashed border-slate-700 bg-slate-950/40 px-4 py-6 text-center text-xs text-slate-400">
                    当前结果未返回跟踪图像
                </div>
            `}
            <details class="rounded-xl border border-slate-700 bg-slate-950/50 p-3">
                <summary class="cursor-pointer text-xs text-sky-300">查看结构化结果</summary>
                <pre class="mt-3 text-xs text-slate-200 whitespace-pre-wrap break-words">${escapeHtml(JSON.stringify(summary, null, 2))}</pre>
            </details>
        </div>
    `;
}

function renderVisionTrackingStreamingState(container, item, statusText) {
    if (!container) return;
    const result = item.result || {};
    const initResult = result.init_result || {};
    const trackResults = Array.isArray(result.track_results) ? result.track_results : [];
    const lastTrack = trackResults.length ? (trackResults[trackResults.length - 1].runtime_result || {}) : null;
    const currentImageBase64 = lastTrack?.tracked_image_base64 || initResult.cached_template_base64 || '';
    const currentMediaType = lastTrack?.tracked_media_type || initResult.cached_template_media_type || 'image/jpeg';
    const currentScore = lastTrack?.score ?? null;
    const currentBBox = lastTrack?.bbox_xyxy || result.template_bbox || null;
    container.innerHTML = `
        <div class="space-y-4">
            <div class="text-cyan-300 text-sm font-semibold">${escapeHtml(statusText || '跟踪中...')}</div>
            <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
                <div class="rounded-2xl border border-cyan-500/20 bg-slate-900/80 p-4 space-y-3">
                    <div class="flex items-center justify-between gap-3">
                        <div>
                            <div class="text-cyan-300 font-semibold text-sm">实时跟踪输出</div>
                            <div class="text-slate-400 text-xs break-all">${escapeHtml(item.sequence_prefix || '')}</div>
                        </div>
                        <div class="text-right">
                            <div class="text-slate-300 text-xs">已处理帧</div>
                            <div class="text-xl font-bold text-white">${escapeHtml(String(trackResults.length + (initResult ? 1 : 0)))}</div>
                        </div>
                    </div>
                    ${currentImageBase64 ? `
                        <div class="overflow-hidden rounded-xl border border-slate-700 bg-slate-950/60">
                            <img
                                src="data:${escapeHtml(currentMediaType)};base64,${currentImageBase64}"
                                alt="实时跟踪结果图"
                                class="w-full h-auto object-contain"
                            >
                        </div>
                    ` : `
                        <div class="rounded-xl border border-dashed border-slate-700 bg-slate-950/40 px-4 py-6 text-center text-xs text-slate-400">
                            正在等待跟踪结果图像...
                        </div>
                    `}
                    <div class="rounded-xl border border-slate-700 bg-slate-950/50 p-3 text-xs text-slate-200 space-y-1">
                        <div>score: <span class="text-cyan-300">${escapeHtml(String(currentScore ?? '-'))}</span></div>
                        <div>bbox: <span class="break-all">${escapeHtml(JSON.stringify(currentBBox))}</span></div>
                        <div>template_asset_uuid: <span class="break-all">${escapeHtml(result.template_asset_uuid || '-')}</span></div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function initTrackingPlayers(container) {
    const cards = container.querySelectorAll('.vision-tracking-player');
    cards.forEach(card => {
        const playerId = card.getAttribute('data-player-id');
        const payload = visionTrackingPlaybackData[playerId];
        if (!playerId || !payload) return;
        visionTrackingPlaybackState[playerId] = {
            currentIndex: 0,
            timer: null,
        };
        card.querySelectorAll('button[data-action]').forEach(btn => {
            btn.addEventListener('click', () => {
                const action = btn.getAttribute('data-action');
                if (action === 'prev') {
                    stepTrackingPlayer(playerId, -1);
                } else if (action === 'next') {
                    stepTrackingPlayer(playerId, 1);
                } else if (action === 'play') {
                    toggleTrackingPlayer(playerId, btn);
                }
            });
        });
        renderTrackingPlayerFrame(playerId);
    });
}

function stopAllTrackingPlayers() {
    Object.values(visionTrackingPlaybackState).forEach(state => {
        if (state && state.timer) {
            clearInterval(state.timer);
        }
    });
    visionTrackingPlaybackData = {};
    visionTrackingPlaybackState = {};
}

function stepTrackingPlayer(playerId, delta) {
    const state = visionTrackingPlaybackState[playerId];
    const payload = visionTrackingPlaybackData[playerId];
    if (!state || !payload || !payload.frames.length) return;
    state.currentIndex = (state.currentIndex + delta + payload.frames.length) % payload.frames.length;
    renderTrackingPlayerFrame(playerId);
}

function toggleTrackingPlayer(playerId, button) {
    const state = visionTrackingPlaybackState[playerId];
    const payload = visionTrackingPlaybackData[playerId];
    if (!state || !payload || payload.frames.length <= 1) return;
    if (state.timer) {
        clearInterval(state.timer);
        state.timer = null;
        button.textContent = '播放';
        return;
    }
    state.timer = setInterval(() => {
        stepTrackingPlayer(playerId, 1);
    }, 450);
    button.textContent = '暂停';
}

function renderTrackingPlayerFrame(playerId) {
    const state = visionTrackingPlaybackState[playerId];
    const payload = visionTrackingPlaybackData[playerId];
    if (!state || !payload) return;
    const imageEl = document.getElementById(`${playerId}-image`);
    const frameLabelEl = document.getElementById(`${playerId}-frame-label`);
    const scoreLabelEl = document.getElementById(`${playerId}-score-label`);
    const bboxLabelEl = document.getElementById(`${playerId}-bbox-label`);
    if (!imageEl || !frameLabelEl || !scoreLabelEl || !bboxLabelEl) return;

    const frame = payload.frames[state.currentIndex];
    if (!frame) {
        frameLabelEl.textContent = '帧 0/0';
        scoreLabelEl.textContent = 'score: -';
        bboxLabelEl.textContent = 'bbox: null';
        return;
    }
    imageEl.src = `data:${frame.image_media_type};base64,${frame.image_base64}`;
    frameLabelEl.textContent = `帧 ${frame.frame_index}/${payload.frames.length}`;
    scoreLabelEl.textContent = `score: ${frame.score ?? '-'}`;
    bboxLabelEl.textContent = `bbox: ${JSON.stringify(frame.bbox_xyxy || null)}`;
}

function renderVisionPreprocessCard(item) {
    const runtimeResult = item.result?.runtime_result || {};
    const processedImageBase64 = runtimeResult.processed_image_base64 || '';
    const processedMediaType = runtimeResult.processed_media_type || 'image/jpeg';
    const summary = {
        asset_uuid: item.asset_uuid || null,
        mode: item.result?.mode || null,
        model_name: runtimeResult.model_name || null,
        operation: runtimeResult.operation || null,
        metadata: runtimeResult.metadata || {},
    };

    return `
        <div class="rounded-2xl border border-indigo-500/20 bg-slate-900/80 p-4 space-y-3">
            <div class="flex items-center justify-between gap-3">
                <div>
                    <div class="text-indigo-300 font-semibold text-sm">预处理成功</div>
                    <div class="text-slate-400 text-xs break-all">${escapeHtml(item.asset_uuid || '')}</div>
                </div>
                <div class="text-right">
                    <div class="text-slate-300 text-xs">操作</div>
                    <div class="text-sm font-bold text-white">${escapeHtml(String(runtimeResult.operation || 'unknown'))}</div>
                </div>
            </div>
            ${processedImageBase64 ? `
                <div class="overflow-hidden rounded-xl border border-slate-700 bg-slate-950/60">
                    <img
                        src="data:${escapeHtml(processedMediaType)};base64,${processedImageBase64}"
                        alt="预处理结果图"
                        class="w-full h-auto object-contain"
                    >
                </div>
            ` : `
                <div class="rounded-xl border border-dashed border-slate-700 bg-slate-950/40 px-4 py-6 text-center text-xs text-slate-400">
                    当前结果未返回处理图像
                </div>
            `}
            <details class="rounded-xl border border-slate-700 bg-slate-950/50 p-3">
                <summary class="cursor-pointer text-xs text-sky-300">查看结构化结果</summary>
                <pre class="mt-3 text-xs text-slate-200 whitespace-pre-wrap break-words">${escapeHtml(JSON.stringify(summary, null, 2))}</pre>
            </details>
        </div>
    `;
}

function initVisionPage() {
    loadVisionSequences().then(() => loadVisionAssets());
    loadVisionAlgorithms();
    const sequenceSelect = document.getElementById('vision-sequence-select');
    if (sequenceSelect) {
        sequenceSelect.removeEventListener('change', handleVisionSequenceChange);
        sequenceSelect.addEventListener('change', handleVisionSequenceChange);
    }
    const algorithmSelect = document.getElementById('vision-algorithm-select');
    if (algorithmSelect) {
        algorithmSelect.removeEventListener('change', handleVisionAlgorithmChange);
        algorithmSelect.addEventListener('change', handleVisionAlgorithmChange);
    }
    const runBtn = document.getElementById('vision-run-btn');
    if (runBtn) {
        runBtn.removeEventListener('click', runVisionInference);
        runBtn.addEventListener('click', runVisionInference);
    }
    const uploadBtn = document.getElementById('vision-upload-btn');
    if (uploadBtn) {
        uploadBtn.removeEventListener('click', uploadVisionAsset);
        uploadBtn.addEventListener('click', uploadVisionAsset);
    }
}

function handleVisionSequenceChange(event) {
    currentVisionSequencePrefix = event.target.value || '';
    selectedAssetUuids = [];
    loadVisionAssets();
}

function handleVisionAlgorithmChange() {
    syncTrackingSelectionWithSequence();
    updateSelectedAssetsPreview();
    updateVisionSequenceHint();
}

// ==================== 其他辅助函数 ====================
function startTraining() {
    const btn = event.target;
    btn.innerHTML = '<span class="iconify animate-spin" data-icon="material-symbols:sync"></span> 训练初始化...';
    btn.classList.add('opacity-50');
    setTimeout(() => {
        alert('训练任务下发成功！已在 K8s 集群分配 A100 GPU 资源。');
        btn.innerHTML = '<span class="iconify" data-icon="material-symbols:play-arrow"></span> 重新开始训练';
        btn.classList.remove('opacity-50');
    }, 1500);
}

function toggleVectorSearch() { alert('向量检索模式切换：已加载 pgvector 特征索引。'); }
function showDeleteConfirm(name) { document.getElementById('del-name').innerText = name; document.getElementById('modal-delete').classList.remove('hidden'); }
function showDetail() { document.getElementById('modal-detail').classList.remove('hidden'); }
function openCompare() { document.getElementById('modal-compare').classList.remove('hidden'); }
function closeModal(id) { document.getElementById(id).classList.add('hidden'); }
function saveCode() { alert('代码保存中...\n系统正在同步镜像到服务器端 v2.4.2 [热更新模式]...'); }
function restoreRecord() { alert('已成功将算法记录从 [回收站] 恢复至 [正式库]！'); }

setInterval(() => {
    const now = new Date();
    const timeEl = document.getElementById('current-time');
    if (timeEl) timeEl.innerText = now.toLocaleString();
}, 1000);

// ==================== DOM 加载完成后初始化 ====================
function initP1Page() {
    initCharts();
    // 算法注册相关
    const submitBtn = document.getElementById('submit-upload');
    if (submitBtn) submitBtn.addEventListener('click', uploadAlgorithmFile);
    const cancelBtn = document.getElementById('cancel-upload');
    if (cancelBtn) cancelBtn.addEventListener('click', () => { resetForm(); currentAlgorithmId = null; document.getElementById('algo-file').value = ''; alert('已取消注册'); });
    const fileInput = document.getElementById('algo-file');
    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            const statusSpan = document.getElementById('file-status');
            if (e.target.files.length > 0) {
                statusSpan.textContent = `已选择：${e.target.files[0].name}`;
                statusSpan.classList.remove('text-slate-400');
                statusSpan.classList.add('text-sky-400');
            } else {
                statusSpan.textContent = '未选择文件';
                statusSpan.classList.add('text-slate-400');
                statusSpan.classList.remove('text-sky-400');
            }
        });
    }
    const saveBtn = document.getElementById('save-hot-update');
    if (saveBtn) saveBtn.addEventListener('click', saveHotUpdate);
    const rollbackBtn = document.getElementById('rollback-version');
    if (rollbackBtn && typeof showRollbackDialog === 'function') {
        rollbackBtn.addEventListener('click', showRollbackDialog);
    }

    // 样本库
    const sampleUploadBtn = document.getElementById('upload-sample-btn');
    if (sampleUploadBtn) {
        sampleUploadBtn.removeEventListener('click', uploadSample);
        sampleUploadBtn.addEventListener('click', uploadSample);
    }
    initSampleFilters();
    initUuidSearch();
    // 如果样本库页面当前可见，则加载数据
    if (document.getElementById('page-samples') && !document.getElementById('page-samples').classList.contains('hidden')) {
        loadSampleAssets();
    }

    // 视觉推理
    const visionNav = document.getElementById('nav-vision');
    if (visionNav && !visionNav.onclick) visionNav.onclick = () => switchPage('vision');
    if (document.getElementById('page-vision') && !document.getElementById('page-vision').classList.contains('hidden')) {
        initVisionPage();
        window._visionInitialized = true;
    }

    // 算法查询列表（若页面可见）
    if (document.getElementById('page-query') && !document.getElementById('page-query').classList.contains('hidden')) {
        loadAlgorithmList();
    }

    const activeNav = document.querySelector('.nav-item.active-nav');
    const initialPage = activeNav?.id?.replace(/^nav-/, '') || 'samples';
    switchPage(initialPage);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initP1Page);
} else {
    initP1Page();
}
