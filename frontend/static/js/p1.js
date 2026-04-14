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

// 加载并渲染算法列表（用于 page-query）
async function loadAlgorithmList() {
    const container = document.querySelector('#page-query .grid.grid-cols-1');
    if (!container) return;

    try {
        const response = await fetch('/api/algorithms');
        if (!response.ok) throw new Error('加载失败');
        const algorithms = await response.json();
        renderAlgorithmList(algorithms);

        if (algorithms.length === 0) {
            container.innerHTML = '<div class="glass-panel rounded-xl p-10 text-center text-slate-500">暂无算法，请先去“资产注册”页面添加。</div>';
            return;
        }

        // 生成列表 HTML
        container.innerHTML = algorithms.map(alg => `
            <div class="glass-panel rounded-xl p-5 group hover:border-sky-500/50 transition-all" data-id="${alg.id}">
                <div class="flex justify-between items-start">
                    <div class="flex gap-4">
                        <div class="w-16 h-16 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-sky-400 group-hover:scale-110 transition-transform">
                            <svg class="iconify text-3xl" data-icon="material-symbols:model-training" width="1em" height="1em" viewBox="0 0 24 24">
                                <path d="M5.15 18.85q-1.025-1.2-1.588-2.687T3 13q0-3.75 2.625-6.375T12 4h.2l-1.6-1.6L12 1l4 4l-4 4l-1.425-1.425L12.15 6H12Q9.1 6 7.05 8.05T5 13q0 1.275.412 2.4t1.163 2.025zM11 18.5q0-.575-.387-1.137t-.863-1.175t-.862-1.275T8.5 13.5q0-1.45 1.025-2.475T12 10t2.475 1.025T15.5 13.5q0 .75-.387 1.413t-.863 1.274t-.862 1.175T13 18.5zm0 2.5v-1.5h2V21zm7.85-2.15l-1.425-1.425q.75-.9 1.163-2.025T19 13q0-1.65-.687-3.062t-1.888-2.363L17.85 6.15q1.45 1.25 2.3 3.013T21 13q0 1.675-.562 3.163T18.85 18.85" fill="currentColor"/>
                            </svg>
                        </div>
                        <div>
                            <div class="flex items-center gap-3">
                                <h5 class="text-lg font-bold">${escapeHtml(alg.name)}</h5>
                                <span class="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300">${escapeHtml(alg.version)}</span>
                                <span class="px-2 py-0.5 rounded text-[10px] ${alg.algorithm_type === 'deep_learning' ? 'bg-sky-500/10 text-sky-400' : 'bg-indigo-500/10 text-indigo-400'} border">${alg.algorithm_type === 'deep_learning' ? '学习方法' : '传统方法'}</span>
                                <span class="px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border">已注册</span>
                            </div>
                            <p class="text-sm text-slate-500 mt-1 max-w-2xl">${escapeHtml(alg.description) || '暂无描述'}</p>
                            <div class="flex items-center gap-4 mt-3 text-[11px] text-slate-500 italic">
                                <span class="flex items-center gap-1">📋 UUID: ${alg.id}</span>
                                <span class="flex items-center gap-1">🕒 更新于: ${new Date(alg.updated_at).toLocaleDateString()}</span>
                                <span class="flex items-center gap-1 text-sky-400">⭐ 收藏(0)</span>
                            </div>
                        </div>
                    </div>
                    <div class="flex flex-col gap-2">
                        <button class="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs transition-colors" onclick="showAlgorithmDetail(${alg.id})">查看详情</button>
                        <button class="px-4 py-1.5 rounded-lg bg-sky-900/30 text-sky-400 hover:bg-sky-900/50 border border-sky-700/50 text-xs transition-colors" onclick="editAlgorithm(${alg.id})">在线修改</button>
                        <button class="px-4 py-1.5 rounded-lg text-rose-400/70 hover:text-rose-400 text-xs transition-colors" onclick="deleteAlgorithm(${alg.id}, '${escapeHtml(alg.name)}')">删除</button>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error(error);
        const container = document.querySelector('#page-query .grid.grid-cols-1');
        if (container) {
            container.innerHTML = '<div class="glass-panel rounded-xl p-10 text-center text-red-400">加载算法列表失败，请检查后端服务。</div>';
        }

    }
}

// 辅助函数：防止 XSS
function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>]/g, function(m) {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';
        return m;
    });
}

async function showAlgorithmDetail(id) {
    try {
        const response = await fetch(`/api/algorithm/${id}`);
        if (!response.ok) throw new Error('获取详情失败');
        const alg = await response.json();

        // 填充弹窗内容
        const modal = document.getElementById('modal-detail');
        // 更新 UUID
        modal.querySelector('.font-mono').innerText = `UUID: ${alg.id}`;
        // 更新主体内容（你需要根据实际弹窗结构修改）
        const detailBody = modal.querySelector('.flex-1.overflow-y-auto');
        // 简单示例：你也可以完全重写内部 HTML
        detailBody.innerHTML = `
            <div class="grid grid-cols-2 gap-8">
                <div class="space-y-4">
                    <h6 class="text-xs font-bold text-sky-400 uppercase tracking-widest border-b border-sky-500/20 pb-2 italic">基本信息</h6>
                    <div class="space-y-2">
                        <p><span class="text-slate-400">名称：</span> ${escapeHtml(alg.name)}</p>
                        <p><span class="text-slate-400">版本：</span> ${escapeHtml(alg.version)}</p>
                        <p><span class="text-slate-400">类型：</span> ${alg.algorithm_type === 'deep_learning' ? '深度学习' : '机器学习'}</p>
                        <p><span class="text-slate-400">标签：</span> ${escapeHtml(alg.tags)}</p>
                        <p><span class="text-slate-400">描述：</span> ${escapeHtml(alg.description) || '无'}</p>
                        <p><span class="text-slate-400">权限：</span> ${alg.auth}</p>
                        <p><span class="text-slate-400">创建时间：</span> ${new Date(alg.created_at).toLocaleString()}</p>
                    </div>
                </div>
                <div class="space-y-4">
                    <h6 class="text-xs font-bold text-indigo-400 uppercase tracking-widest border-b border-indigo-500/20 pb-2 italic">历史版本</h6>
                    <div class="space-y-2">
                        <div class="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg">
                            <div><span class="text-sky-400">${escapeHtml(alg.version)}</span><span class="text-slate-500 text-[10px] ml-2">当前版本</span></div>
                            <svg class="iconify text-emerald-400" data-icon="material-symbols:check-circle" width="1em" height="1em"></svg>
                        </div>
                        <!-- 如果有历史版本列表可以后续扩展 -->
                    </div>
                </div>
            </div>
            <div class="mt-8 space-y-4">
                <h6 class="text-xs font-bold text-emerald-400 uppercase tracking-widest border-b border-emerald-500/20 pb-2 italic">示例代码</h6>
                <div class="bg-black/40 rounded-xl p-4 font-mono text-xs text-emerald-400/90 border border-emerald-500/10">
                    <pre>import requests<br/>response = requests.get("http://your-api/algorithm/${alg.id}")<br/>print(response.json())</pre>
                </div>
            </div>
        `;
        modal.classList.remove('hidden');
        modal.classList.add('flex');
    } catch (error) {
        console.error(error);
        alert('无法获取算法详情');
    }
}

async function deleteAlgorithm(id, name) {
    if (confirm(`确定要删除算法“${name}”吗？此操作不可恢复。`)) {
        try {
            const response = await fetch(`/api/algorithm/${id}`, { method: 'DELETE' });
            if (response.ok) {
                alert('删除成功');
                loadAlgorithmList();  // 刷新列表
            } else {
                const err = await response.json();
                alert(`删除失败：${err.detail || '未知错误'}`);
            }
        } catch (error) {
            alert('网络错误');
        }
    }
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
        <div class="glass-panel rounded-xl p-5 group hover:border-sky-500/50 transition-all" data-id="${alg.id}">
            <div class="flex justify-between items-start">
                <div class="flex gap-4">
                    <div class="w-16 h-16 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-sky-400 group-hover:scale-110 transition-transform">
                        <svg class="iconify text-3xl" data-icon="material-symbols:model-training" width="1em" height="1em" viewBox="0 0 24 24">
                            <path d="M5.15 18.85q-1.025-1.2-1.588-2.687T3 13q0-3.75 2.625-6.375T12 4h.2l-1.6-1.6L12 1l4 4l-4 4l-1.425-1.425L12.15 6H12Q9.1 6 7.05 8.05T5 13q0 1.275.412 2.4t1.163 2.025zM11 18.5q0-.575-.387-1.137t-.863-1.175t-.862-1.275T8.5 13.5q0-1.45 1.025-2.475T12 10t2.475 1.025T15.5 13.5q0 .75-.387 1.413t-.863 1.274t-.862 1.175T13 18.5zm0 2.5v-1.5h2V21zm7.85-2.15l-1.425-1.425q.75-.9 1.163-2.025T19 13q0-1.65-.687-3.062t-1.888-2.363L17.85 6.15q1.45 1.25 2.3 3.013T21 13q0 1.675-.562 3.163T18.85 18.85" fill="currentColor"/>
                        </svg>
                    </div>
                    <div>
                        <div class="flex items-center gap-3">
                            <h5 class="text-lg font-bold">${escapeHtml(alg.name)}</h5>
                            <span class="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300">${escapeHtml(alg.version)}</span>
                            <span class="px-2 py-0.5 rounded text-[10px] ${alg.algorithm_type === 'Deep Learning' ? 'bg-sky-500/10 text-sky-400' : 'bg-indigo-500/10 text-indigo-400'} border">
                                ${alg.algorithm_type === 'Deep Learning' ? '学习方法' : '传统方法'}
                            </span>
                            <span class="px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border">已注册</span>
                            <span class="px-2 py-0.5 rounded text-[10px] bg-purple-500/10 text-purple-400 border">版本数：${alg.versions.length}</span>
                        </div>
                        <p class="text-sm text-slate-500 mt-1 max-w-2xl">${escapeHtml(alg.description) || '暂无描述'}</p>
                        <div class="flex items-center gap-4 mt-3 text-[11px] text-slate-500 italic">
                            <span class="flex items-center gap-1">📋 ID: ${alg.id}</span>
                            <span class="flex items-center gap-1">🕒 更新于: ${new Date(alg.updated_at).toLocaleDateString()}</span>
                            <span class="flex items-center gap-1 text-sky-400">⭐ 收藏(0)</span>
                        </div>
                    </div>
                </div>
                <div class="flex flex-col gap-2">
                    <button class="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs transition-colors" onclick="showAlgorithmDetail(${alg.id})">查看详情</button>
                    <button class="px-4 py-1.5 rounded-lg bg-sky-900/30 text-sky-400 hover:bg-sky-900/50 border border-sky-700/50 text-xs transition-colors" onclick="editAlgorithm(${alg.id})">在线修改</button>
                    <button class="px-4 py-1.5 rounded-lg text-rose-400/70 hover:text-rose-400 text-xs transition-colors" onclick="deleteAlgorithm(${alg.id}, '${escapeHtml(alg.name)}')">删除</button>
                </div>
            </div>
        </div>
    `).join('');
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

async function searchAlgorithms() {
    const keyword = document.getElementById('search-keyword').value.trim();
    const algorithmType = document.getElementById('search-type').value; // 可能为 "Deep Learning", "Machine Learning" 或 ""

    // 构建 URL 参数
    let url = '/api/algorithms/search?';
    const params = [];
    if (keyword) params.push(`keyword=${encodeURIComponent(keyword)}`);
    if (algorithmType) params.push(`algorithm_type=${encodeURIComponent(algorithmType)}`);
    url += params.join('&');

    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error('搜索失败');
        const algorithms = await response.json();
        renderAlgorithmList(algorithms);
    } catch (error) {
        console.error(error);
        alert('搜索失败，请稍后重试');
    }
}

//加载算法文件内容到编辑器
async function loadAlgorithmToEditor(id) {
    try {
        const response = await fetch(`/api/algorithm/${id}/file-content`);
        if (!response.ok) {
            const err = await response.json();
            alert(`无法加载文件内容：${err.detail}`);
            return;
        }
        const data = await response.json();
        // 填充编辑器
        document.getElementById('code-editor').value = data.content;
        document.getElementById('editor-filename').innerText = data.filename;
        document.getElementById('editor-algo-name').innerText = `${data.algorithm_name} (v${data.algorithm_version})`;
        // 保存当前编辑的算法ID到全局变量，用于保存
        window.currentEditAlgorithmId = id;
    } catch (error) {
        console.error(error);
        alert('加载文件内容失败');
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