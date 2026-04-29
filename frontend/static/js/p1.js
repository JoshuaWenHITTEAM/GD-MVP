// 后端 数据库api端口 根据真实情况进行修改
const API_BASE_URL = 'http://127.0.0.1:8000';

// 页面切换逻辑
function switchPage(pageId) {
    // 隐藏所有页面
    document.querySelectorAll('.page-section').forEach(p => p.classList.add('hidden'));
    // 显示选中页
    document.getElementById('page-' + pageId).classList.remove('hidden');

    // 更新标题
    const titles = {
        'dashboard': '系统实时概览',
        'samples': '图像/视频样本管理',
        'training': '模型自学习训练舱',
        'query': '算法资产库检索',
        'register': '生产算法入库注册',
        'editor': '代码热更新与在线调试',
        'recycle': '资产回收站'
    };
    document.getElementById('page-title').innerText = titles[pageId];

    // 更新导航高亮
    document.querySelectorAll('.nav-item').forEach(btn => btn.classList.remove('active-nav'));
    document.getElementById('nav-' + pageId).classList.add('active-nav');

    // 新增：如果切换到算法检索页，则加载列表
    if (pageId === 'query') {
        loadAlgorithmList();
    }

    if (pageId === 'dashboard') initCharts();
}

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

function toggleVectorSearch() {
    alert('向量检索模式切换：已加载 pgvector 特征索引。');
}

function uploadSample() {
    alert('调起 MinIO 上传接口... 正在进行 MD5 哈希校验以去重。');
}

// 弹窗控制
function showDeleteConfirm(name) {
    document.getElementById('del-name').innerText = name;
    document.getElementById('modal-delete').classList.remove('hidden');
}

function showDetail() {
    document.getElementById('modal-detail').classList.remove('hidden');
}

function openCompare() {
    document.getElementById('modal-compare').classList.remove('hidden');
}

function closeModal(id) {
    document.getElementById(id).classList.add('hidden');
}

function saveCode() {
    alert('代码保存中...\n系统正在同步镜像到服务器端 v2.4.2 [热更新模式]...');
}

function restoreRecord() {
    alert('已成功将算法记录从 [回收站] 恢复至 [正式库]！');
}

// 时间刷新
setInterval(() => {
    const now = new Date();
    document.getElementById('current-time').innerText = now.toLocaleString();
}, 1000);

// 初始化图表
function initCharts() {
    // 主负载图
    const mainChart = echarts.init(document.getElementById('chart-main'), 'dark');
    mainChart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis' },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: {
            type: 'category',
            data: ['09:00', '09:10', '09:20', '09:30', '09:40', '09:50'],
            axisLine: { lineStyle: { color: '#475569' } }
        },
        yAxis: { type: 'value', axisLine: { lineStyle: { color: '#475569' } }, splitLine: { lineStyle: { color: '#1e293b' } } },
        series: [
            {
                name: 'CPU 负载',
                type: 'line',
                smooth: true,
                areaStyle: { opacity: 0.1 },
                data: [45, 52, 48, 61, 55, 62],
                itemStyle: { color: '#38bdf8' }
            },
            {
                name: 'GPU 占用',
                type: 'line',
                smooth: true,
                areaStyle: { opacity: 0.1 },
                data: [70, 75, 72, 85, 80, 88],
                itemStyle: { color: '#818cf8' }
            }
        ]
    });

    // 饼图
    const pieChart = echarts.init(document.getElementById('chart-pie'), 'dark');
    pieChart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'item' },
        series: [{
            type: 'pie',
            radius: ['40%', '70%'],
            avoidLabelOverlap: false,
            itemStyle: { borderRadius: 10, borderColor: '#020617', borderWidth: 2 },
            label: { show: false },
            data: [
                { value: 64, name: '学习方法', itemStyle: { color: '#38bdf8' } },
                { value: 36, name: '传统方法', itemStyle: { color: '#c084fc' } },
            ]
        }]
    });

    window.addEventListener('resize', () => {
        mainChart.resize();
        pieChart.resize();
    });
}
/*
// 提交算法注册
let currentAlgorithmId = null;  // 存储第一步注册成功的算法ID
async function submitAlgorithm() {
    // 获取表单数据
    const formData = {
        name: document.getElementById('algo-name').value.trim(),
        version: document.getElementById('algo-version').value.trim(),
        algorithm_type: document.getElementById('algo-type').value,
        tags: document.getElementById('algo-tags').value.trim(),
        description: document.getElementById('algo-description').value.trim(),
        auth: document.querySelector('input[name="auth"]:checked').value
    };

    // 验证必填字段
    if (!formData.name || !formData.version || !formData.algorithm_type || !formData.tags) {
        alert('请填写所有必填项！');
        return;
    }

    if (formData.name.length > 32) {
        alert('算法名称不能超过 32 个字符！');
        return;
    }

    try {
        const response = await fetch('/api/algorithm/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });

        const result = await response.json();

        if (response.ok) {
            alert(`算法注册成功！\nID: ${result.id}\n名称：${result.name}`);
            currentAlgorithmId = result.id;
            // 可以在这里跳转到下一步或清空表单
            console.log('注册成功，算法ID及信息：', currentAlgorithmId,result);
            // 注册成功后刷新算法列表（如果列表页正在显示）
            loadAlgorithmList();
        } else {
            alert(`注册失败：${result.detail || '未知错误'}`);
        }
    } catch (error) {
        console.error('提交失败:', error);
        alert('网络错误，请稍后重试');
    }
}
*/

let isImageValidated = false; // 镜像校验状态

/**
 * 新增功能：从后端 API 拉取算法列表，并渲染为下拉菜单
 * @param {string} preselectUuid - (可选) 加载完后自动选中的算法 UUID
 */
async function loadAlgorithms(preselectUuid = null) {
    const selectElem = document.getElementById('version-algo-select');
    selectElem.innerHTML = '<option value="">加载中...</option>';

    try {
        // 请求你提供的 GET API。Demo 演示中为了拿到足够多的数据，pageSize 设为 100
        const response = await fetch(`${API_BASE_URL}/api/v1/algorithms?pageNum=1&pageSize=100`);
        const resData = await response.json();

        // 假设分页返回的格式为 { code: 200, data: { items: [...] } }
        // 注意：需根据你实际后端的 paginate() 包装器结构微调 resData.data.items 
        if (response.ok && resData.data && resData.data.items) {
            selectElem.innerHTML = '<option value="">请选择算法...</option>';
            
            resData.data.items.forEach(algo => {
                const opt = document.createElement('option');
                // value 绑定 uuid 给后续 API 请求使用
                opt.value = algo.uuid; 
                // 页面展示：算法名称 (包含一个 Code 作为补充区分)
                opt.textContent = `${algo.algorithmName} [${algo.algorithmCode}]`; 
                selectElem.appendChild(opt);
            });

            // 如果有刚注册完传过来的 uuid，则自动选中
            if (preselectUuid) {
                selectElem.value = preselectUuid;
            }
        } else {
            selectElem.innerHTML = '<option value="">加载失败或暂无数据</option>';
        }
    } catch (error) {
        console.error("加载算法列表失败:", error);
        selectElem.innerHTML = '<option value="">网络请求异常</option>';
    }
}

/**
 * Tab 切换效果控制
 * 优化：在 Tab 切换时，如果是切换到“版本注册”，自动刷新一次算法列表
 */
function switchTab(target) {
    const btnAlgo = document.getElementById('tab-btn-algo');
    const btnVersion = document.getElementById('tab-btn-version');
    const panelAlgo = document.getElementById('panel-algo');
    const panelVersion = document.getElementById('panel-version');

    if (target === 'algo') {
        btnAlgo.className = "px-8 py-3 rounded-xl font-bold transition-all duration-300 bg-sky-500 text-white shadow-lg shadow-sky-500/30";
        btnVersion.className = "px-8 py-3 rounded-xl font-bold transition-all duration-300 bg-transparent text-slate-400 hover:text-white hover:bg-slate-800";
        panelVersion.classList.add('hidden');
        panelAlgo.classList.remove('hidden');
    } else {
        btnVersion.className = "px-8 py-3 rounded-xl font-bold transition-all duration-300 bg-indigo-500 text-white shadow-lg shadow-indigo-500/30";
        btnAlgo.className = "px-8 py-3 rounded-xl font-bold transition-all duration-300 bg-transparent text-slate-400 hover:text-white hover:bg-slate-800";
        panelAlgo.classList.add('hidden');
        panelVersion.classList.remove('hidden');
        
        // 【新增】：每次切入版本面板时，静默加载最新列表
        if (document.getElementById('version-algo-select').options.length <= 1) {
            loadAlgorithms();
        }
    }
}

/**
 * 模拟文件选择并提取路径
 * inputElem: 文件选择器元素
 * targetInputId: 目标填入的文本框ID
 * mockPrefix: 假装的服务器前缀路径 (Demo用)
 */
function handleFileSelect(inputElem, targetInputId, mockPrefix) {
    if (inputElem.files && inputElem.files.length > 0) {
        const fileName = inputElem.files[0].name;
        // 拼接成类似真实的后端路径：/opt/algorithms/code/xxxx.py
        // 等待后端给出具体存放代码路径后修改为真正的前缀
        document.getElementById(targetInputId).value = mockPrefix + fileName;
    }
}

/**
 * 辅助函数：生成前端唯一算法编码
 */
function generateAlgorithmCode() {
    return 'ALG-' + Date.now() + '-' + Math.floor(1000 + Math.random() * 9000);
}

/**
 * 提交算法基础信息
 */
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

    const payload = {
        algorithmCode: generateAlgorithmCode(),
        algorithmName: name,
        algorithmType: type,
        codePath: codePath,
        configPath: configPath
    };

    try {
        btn.innerHTML = '注册中...';
        btn.disabled = true;

        const response = await fetch(`${API_BASE_URL}/api/v1/algorithms`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        const resData = await response.json();

        // 假定正常返回数据在 data 层
        if (response.ok && resData.data && resData.data.uuid) {
            const newUuid = resData.data.uuid;
            alert(`🎉 算法注册成功！\n系统生成的算法 UUID 是: ${newUuid}\n(已自动为您填入版本注册面板)`);
            
            // 【修改】：不填输入框了，而是先触发加载列表，把新生成的 uuid 传进去要求它自动选中
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

/**
 * 假装校验本地镜像名
 */
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

/**
 * 提交版本信息
 */
/**
 * 修改：版本注册提取下拉框的 value
 */
async function submitVersion() {
    // 【修改】：从原来的 text input 改成了取 select 下拉框的值
    const targetUuid = document.getElementById('version-algo-select').value;
    
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

    const payload = {
        version: version,
        versionName: versionName,
        localImageName: localImageName,
        entrypoint: "", 
        sourceRevision: "",
        configRevision: "",
        changelog: "从前端Demo注册",
        sourceType: "LOCAL", 
        imagePullPolicy: "IF_NOT_PRESENT",
        registryUrl: "",
        repositoryName: "",
        imageTag: version,
        imageDigest: "",
        fullImageUri: localImageName,
        imageSize: 0
    };

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
            alert("版本注册失败：" + (resData.message || "后端返回错误"));
        }
    } catch (error) {
        console.error("API请求错误:", error);
        alert("网络请求失败，请检查后端。");
    } finally {
        btn.innerText = '提交并注册版本';
        btn.disabled = false;
    }
}

/**
 * 重置表单工具函数
 */
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

// 重置表单
function resetForm() {
    document.getElementById('algo-name').value = '';
    document.getElementById('algo-version').value = '';
    document.getElementById('algo-type').selectedIndex = 0;
    document.getElementById('algo-tags').value = '';
    document.getElementById('algo-description').value = '';
    document.querySelector('input[name="auth"][value="公开"]').checked = true;
}

// 初始加载
window.onload = () => {
    initCharts();
};

// 加载并渲染算法列表
async function loadAlgorithmList() {
    const container = document.querySelector('#page-query .grid.grid-cols-1');
    if (!container) return;

    try {
        // 【修改1】修改请求API，并适配分页查询的格式
        const response = await fetch(`${API_BASE_URL}/api/v1/algorithms?pageNum=1&pageSize=100`);
        if (!response.ok) throw new Error('加载失败');
        
        const resData = await response.json();
        // 根据之前你提供的后端代码，这里通常包裹在 data.items 里
        const algorithms = (resData.data && resData.data.items) ? resData.data.items :[];
        
        // 调用专门的渲染函数（去除了原来在这里重复写的一大段 HTML）
        renderAlgorithmList(algorithms);

    } catch (error) {
        console.error("加载列表报错:", error);
        if (container) {
            container.innerHTML = '<div class="glass-panel rounded-xl p-10 text-center text-red-400">加载算法列表失败，请检查后端服务。</div>';
        }
    }
}

// 辅助函数：防止 XSS
function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/[&<>]/g, function(m) {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';
        return m;
    });
}

// 渲染算法列表（接收算法数组）
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
                            <!-- 【修改2】数据库字段映射：name 变 algorithmName -->
                            <h5 class="text-lg font-bold">${escapeHtml(alg.algorithmName)}</h5>
                            <!-- 【修改3】由于目前只有算法，且算法没有直接版本号（版本在另一张表），此处使用 algorithmCode 展示标识 -->
                            <span class="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300">编码: ${escapeHtml(alg.algorithmCode)}</span>
                            <!-- 【修改4】数据库字段映射：algorithm_type 变 algorithmType -->
                            <span class="px-2 py-0.5 rounded text-[10px] bg-sky-500/10 text-sky-400 border border-sky-500/20">${escapeHtml(alg.algorithmType || '未知类型')}</span>
                            <!-- 【修改5】映射 status 字段 -->
                            <span class="px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">${alg.status === 'ENABLED' ? '已启用' : '已注册'}</span>
                        </div>
                        <p class="text-sm text-slate-500 mt-1 max-w-2xl">${escapeHtml(alg.description) || '暂无描述'}</p>
                        <div class="flex items-center gap-4 mt-3 text-[11px] text-slate-500 italic">
                            <!-- 【修改6】ID 换为 UUID -->
                            <span class="flex items-center gap-1">📋 UUID: ${alg.uuid}</span>
                            <span class="flex items-center gap-1">🕒 更新于: ${alg.updatedAt ? new Date(alg.updatedAt).toLocaleDateString() : '未知'}</span>
                        </div>
                    </div>
                </div>
                <div class="flex flex-col gap-2">
                    <!-- 【修改7】核心修正：因为 UUID 是字符串类型，传参时必须加上单引号 '${alg.uuid}'，否则JS会报错！ -->
                    <button class="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs transition-colors" onclick="showAlgorithmDetail('${alg.uuid}')">查看详情</button>
                    <button class="px-4 py-1.5 rounded-lg bg-sky-900/30 text-sky-400 hover:bg-sky-900/50 border border-sky-700/50 text-xs transition-colors" onclick="editAlgorithm('${alg.uuid}')">在线修改</button>
                    <button class="px-4 py-1.5 rounded-lg text-rose-400/70 hover:text-rose-400 text-xs transition-colors" onclick="deleteAlgorithm('${alg.uuid}', '${escapeHtml(alg.algorithmName)}')">删除</button>
                </div>
            </div>
        </div>
    `).join('');
}

// 显示算法详情
async function showAlgorithmDetail(uuid) {
    try {
        // 1. 发起请求获取算法详情
        const algoResponse = await fetch(`${API_BASE_URL}/api/v1/algorithms/${uuid}`);
        if (!algoResponse.ok) throw new Error('获取算法详情失败');
        
        const algoResData = await algoResponse.json();
        const alg = algoResData.data || algoResData; 

        // 2. 发起请求获取该算法的版本列表 (新增逻辑)
        let versions =[];
        try {
            const versionsResponse = await fetch(`${API_BASE_URL}/api/v1/algorithms/${uuid}/versions`);
            if (versionsResponse.ok) {
                const versionsResData = await versionsResponse.json();
                // 适配你的返回结构 ok({"items": items, "total": len(items)})
                versions = (versionsResData.data && versionsResData.data.items) ? versionsResData.data.items :[];
            }
        } catch (vErr) {
            console.error("获取版本列表报错, 但不影响详情展示:", vErr);
        }

        // 3. 动态生成版本列表的 HTML
        let versionsHtml = '';
        if (versions.length === 0) {
            versionsHtml = `<div class="text-slate-500 text-xs italic text-center p-4 bg-slate-900/30 rounded border border-slate-800">暂无关联的版本</div>`;
        } else {
            versionsHtml = versions.map(v => `
                <div class="bg-slate-900/50 rounded-lg p-3 flex justify-between items-center text-sm border border-slate-800 hover:border-indigo-500/50 transition-colors">
                    <div class="flex flex-col">
                        <div>
                            <span class="text-sky-400 font-bold">${escapeHtml(v.version)}</span>
                            <span class="text-slate-400 text-xs ml-2">${escapeHtml(v.versionName || '')}</span>
                        </div>
                        <span class="text-slate-500 text-[10px] mt-1">镜像: ${escapeHtml(v.localImageName || '--')}</span>
                    </div>
                    <div class="flex items-center gap-3">
                        <span class="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400 border border-slate-700">${v.publishStatus || 'DRAFT'}</span>
                        <button onclick="showVersionDetail('${v.uuid}')" class="px-3 py-1.5 bg-indigo-900/30 border border-indigo-700/50 rounded text-xs text-indigo-300 hover:text-white hover:bg-indigo-600 transition-all">版本详情</button>
                    </div>
                </div>
            `).join('');
        }

        // 4. 渲染弹窗内容
        const modal = document.getElementById('modal-detail');
        if (!modal) {
            alert("找不到详情弹窗DOM(id='modal-detail')");
            return;
        }

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
            
            <!-- 【替换】这里换成了真实拉取渲染的版本列表 -->
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

// 【新增】获取单个版本详细信息的函数
async function showVersionDetail(versionUuid) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/versions/${versionUuid}`);
        if (!response.ok) throw new Error("获取版本详情失败");
        
        const resData = await response.json();
        const version = resData.data || resData;

        // 为了 Demo 方便展示，我们将获取到的版本详细字段拼接成字符串，用系统自带弹窗显示。
        // 如果后续你有设计“版本详情弹窗”的 HTML，可以把这里替换为渲染 HTML 的逻辑。
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

// 删除算法
async function deleteAlgorithm(uuid, name) {
    if (confirm(`确定要删除算法“${name}”吗？此操作不可恢复。`)) {
        try {
            // 【修改10】修改删除 API 路径
            const response = await fetch(`${API_BASE_URL}/api/v1/algorithms/${uuid}`, { method: 'DELETE' });
            
            if (response.ok) {
                alert('删除成功');
                loadAlgorithmList();  // 刷新列表
            } else {
                const err = await response.json();
                alert(`删除失败：${err.message || err.detail || '未知错误'}`);
            }
        } catch (error) {
            alert('网络错误，请确认删除接口是否存在。');
        }
    }
}

//镜像文件上传函数
async function uploadAlgorithmFile() {
    const fileInput = document.getElementById('algo-file');
    const ruleSelect = document.getElementById('validation-rule');
    const versionInput = document.getElementById('version-number');
    const file = fileInput.files[0];
    if (!file) {
        alert('请选择一个文件');
        return;
    }
    if (!currentAlgorithmId) {
        alert('请先完成第一步算法注册');
        return;
    }
    const formData = new FormData();
    formData.append('file', file);
    formData.append('rule', ruleSelect.value);
    if (versionInput.value.trim()) {
        formData.append('version_number', versionInput.value.trim());
    }

    try {
        const response = await fetch(`/api/algorithm/upload-file/${currentAlgorithmId}`, {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        if (response.ok) {
            alert(`文件上传成功！\n版本号：${result.version}\n路径：${result.file_path}`);
            // 可选：清空文件选择
            fileInput.value = '';
            versionInput.value = '';
            // 跳转到算法检索页查看更新
            switchPage('query');
        } else {
            alert(`上传失败：${result.detail}`);
        }
    } catch (error) {
        console.error(error);
        alert('网络错误，请稍后重试');
    }
}

window.onload = () => {
    initCharts();
    // 绑定文件上传按钮
    const submitBtn = document.getElementById('submit-upload');
    if (submitBtn) {
        submitBtn.addEventListener('click', uploadAlgorithmFile);
    }
    const cancelBtn = document.getElementById('cancel-upload');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', () => {
            // 取消注册逻辑：清空第一步表单和当前ID
            resetForm();
            currentAlgorithmId = null;
            document.getElementById('algo-file').value = '';
            alert('已取消注册');
        });
    }
     //文件选择监听：
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

    //热更新保存
    const saveBtn = document.getElementById('save-hot-update');
    if (saveBtn) {
        saveBtn.addEventListener('click', saveHotUpdate);
    }
};

function editAlgorithm(id) {
    // 跳转到编辑器页面，并传递算法ID
    // 你的编辑器页面是 page-editor，可以预先加载算法数据
    switchPage('editor');
    // 然后调用一个函数加载算法详情到编辑器（需要额外实现）
    loadAlgorithmToEditor(id);
}

/**
 * 搜索算法列表
 */
async function searchAlgorithms() {
    const keyword = document.getElementById('search-keyword').value.trim();
    const algorithmType = document.getElementById('search-type').value;

    // 【修改1】复用后端的 GET /api/v1/algorithms 接口，同时附带分页参数
    let url = `${API_BASE_URL}/api/v1/algorithms?pageNum=1&pageSize=100`;
    
    // 【修改2】注意后端的字段名是 algorithmType（驼峰）
    if (keyword) url += `&keyword=${encodeURIComponent(keyword)}`;
    if (algorithmType) url += `&algorithmType=${encodeURIComponent(algorithmType)}`;

    const container = document.querySelector('#page-query .grid.grid-cols-1');
    
    // 搜索时展示加载动画
    container.innerHTML = `
        <div class="glass-panel rounded-xl p-16 flex flex-col items-center justify-center text-slate-400 space-y-4">
            <svg class="animate-spin h-10 w-10 text-sky-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
            <span class="text-sm">正在检索中...</span>
        </div>
    `;

    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error('搜索请求失败');
        
        const resData = await response.json();
        const algorithms = (resData.data && resData.data.items) ? resData.data.items :[];
        
        // 调用之前写好的渲染函数
        renderAlgorithmList(algorithms);
    } catch (error) {
        console.error(error);
        container.innerHTML = '<div class="glass-panel rounded-xl p-10 text-center text-red-400">搜索失败，请检查后端服务是否正常。</div>';
    }
}

/**
 * 加载算法内容到编辑器 (Demo Mock 版)
 */
async function loadAlgorithmToEditor(uuid) {
    try {
        // 【修改3】由于后端没有读取文件的接口，我们请求算法详情接口获取 metadata
        const response = await fetch(`${API_BASE_URL}/api/v1/algorithms/${uuid}`);
        if (!response.ok) {
            const err = await response.json();
            alert(`无法加载算法详情：${err.detail || err.message}`);
            return;
        }
        
        const resData = await response.json();
        const alg = resData.data || resData;

        // 【修改4】使用算法数据，动态生成一段逼真的 Demo Python 代码
        const mockCode = `"""
@Algorithm : ${alg.algorithmName}
@Code      : ${alg.algorithmCode}
@Type      : ${alg.algorithmType}
@Path      : ${alg.codePath || '/app/main.py'}
"""

import json
import logging

logging.basicConfig(level=logging.INFO)

def init_model():
    logging.info(f"Initializing {alg.algorithmType} model: ${alg.algorithmName}...")
    # 加载配置: ${alg.configPath || '未配置'}
    return True

def process_data(input_payload):
    """
    核心执行逻辑
    """
    logging.info("Start processing...")
    # TODO: 实现具体的业务逻辑
    
    return {
        "status": "success",
        "algorithm_uuid": "${alg.uuid}",
        "result": "Demo output"
    }

if __name__ == "__main__":
    init_model()
    print(process_data({"test": "data"}))
`;

        // 填充代码编辑器
        const editor = document.getElementById('code-editor');
        if (editor) editor.value = mockCode;
        
        // 提取文件名 (例如从 /opt/algo/main.py 提取出 main.py)
        const fileName = alg.codePath ? alg.codePath.split('/').pop() : 'main.py';
        
        const filenameElem = document.getElementById('editor-filename');
        if (filenameElem) filenameElem.innerText = fileName;
        
        const algonameElem = document.getElementById('editor-algo-name');
        if (algonameElem) algonameElem.innerText = `${alg.algorithmName}[${alg.algorithmCode}]`;

        // 保存当前编辑的算法UUID到全局变量，用于保存
        window.currentEditAlgorithmId = uuid;
        
        // 如果页面有跳转到编辑器 Tab 的方法，可以在这里调用，例如：
        // switchPage('editor'); 

    } catch (error) {
        console.error(error);
        alert('加载算法到编辑器失败，请检查网络');
    }
}

//算法代码热更新并保存
async function saveHotUpdate() {
    const algorithmId = window.currentEditAlgorithmId;
    if (!algorithmId) {
        alert('未选中任何算法');
        return;
    }
    const codeContent = document.getElementById('code-editor').value;
    if (!codeContent.trim()) {
        alert('文件内容不能为空');
        return;
    }

    // 询问用户是否指定版本号（可选）
    let versionNumber = prompt("请输入新版本号（例如 v1.0.1），留空则自动生成：");
    // 将代码内容转为 File 对象
    const blob = new Blob([codeContent], { type: 'text/plain' });
    const file = new File([blob], document.getElementById('editor-filename').innerText, { type: 'text/plain' });

    const formData = new FormData();
    formData.append('file', file);
    formData.append('rule', 'none');   // 热更新时跳过内容校验，或根据需要选择规则
    if (versionNumber && versionNumber.trim()) {
        formData.append('version_number', versionNumber.trim());
    }
    try {
        const response = await fetch(`/api/algorithm/upload-file/${algorithmId}`, {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        if (response.ok) {
            alert(`热更新成功！新版本号：${result.version}\n文件路径：${result.file_path}`);
            // 可选：跳转到算法检索页
            switchPage('query');
            // 刷新列表
            loadAlgorithmList();
        } else {
            alert(`保存失败：${result.detail}`);
        }
    } catch (error) {
        console.error(error);
        alert('网络错误，请稍后重试');
    }
}