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

// 初始加载
window.onload = () => {
    initCharts();
};