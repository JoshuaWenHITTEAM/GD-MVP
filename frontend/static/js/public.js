document.addEventListener('DOMContentLoaded', () => {
    // 获取当前页面的 URL 路径
    const currentPath = window.location.pathname;
    
    // 获取所有导航项
    const navLinks = document.querySelectorAll('.nav-link-item');
    
    // 1. 先清除所有 active 类 (保险起见)
    navLinks.forEach(link => link.classList.remove('active'));

    // 2. 根据当前路径匹配对应的 ID 并添加 active 类
    // 注意：这里的路径要和你 FastAPI 路由里定义的 get 路径一致
    if (currentPath === '/') {
        document.getElementById('nav-p1')?.classList.add('active');
    } else if (currentPath === '/train') {
        document.getElementById('nav-p2')?.classList.add('active');
    } else if (currentPath === '/reasoning') {
        document.getElementById('nav-p3')?.classList.add('active');
    }

    // --- 顺便实现的时间刷新逻辑 ---
    const timeDisplay = document.getElementById('current-time');
    function refreshClock() {
        const now = new Date();
        const timeString = now.toLocaleString('zh-CN', {
            year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit', second: '2-digit',
            hour12: false
        }).replace(/\//g, '/');
        if (timeDisplay) timeDisplay.textContent = timeString;
    }
    setInterval(refreshClock, 1000);
    refreshClock();
});