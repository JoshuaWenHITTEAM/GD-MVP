document.addEventListener('DOMContentLoaded', () => {
    // 1. 获取视频源和各个画布上下文
    const video = document.getElementById('mockVideoSource');
    
    // 融合视图 Canvas（显示原始视频）
    const canvasFusion = document.getElementById('fusionCanvas');
    const ctxFusion = canvasFusion.getContext('2d');
    
    // 检测视图 Canvas（YOLO_PRO）
    const canvasDet = document.getElementById('detectionVizCanvas');
    const ctxDet = canvasDet.getContext('2d');
    
    // 跟踪视图 Canvas（DEEPSORT）
    const canvasTrack = document.getElementById('trackingVizCanvas');
    const ctxTrack = canvasTrack.getContext('2d');

    // 当视频的元数据（宽度和高度）加载完毕时，初始化画布
    video.addEventListener('loadedmetadata', () => {
        const w = video.videoWidth;
        const h = video.videoHeight;
        
        // 将三个画布的实际绘图分辨率设置为与视频原生分辨率一致，防止模糊
        [canvasFusion, canvasDet, canvasTrack].forEach(canvas => {
            canvas.width = w;
            canvas.height = h;
        });
        
        // 视频准备好后，启动模拟后端推流和前端渲染引擎
        startMockBackendAndRender();
    });

    // ==========================================
    // 模块 A: 假数据生成器 (漫游算法)
    // 作用：无需你手写 JSON，自动生成在画面里平滑移动的假目标
    // ==========================================
    class MockDataGenerator {
        constructor(videoW, videoH) {
            this.w = videoW;
            this.h = videoH;
            // 随机生成 4 个假目标
            this.targets = Array.from({ length: 4 }, (_, i) => ({
                id: i + 1,
                x: Math.random() * (videoW - 150) + 50, // 避免太靠边
                y: Math.random() * (videoH - 150) + 50,
                width: 80 + Math.random() * 60,
                height: 100 + Math.random() * 80,
                vx: (Math.random() - 0.5) * 6, // X轴平滑移动速度
                vy: (Math.random() - 0.5) * 6, // Y轴平滑移动速度
                class: ['Car', 'Person', 'Drone', 'Unknown'][Math.floor(Math.random() * 4)]
            }));
        }

        // 每一帧调用一次，更新目标的物理位置
        update() {
            this.targets.forEach(t => {
                t.x += t.vx;
                t.y += t.vy;
                
                // 边缘碰撞反弹处理
                if (t.x <= 0 || t.x + t.width >= this.w) t.vx *= -1;
                if (t.y <= 0 || t.y + t.height >= this.h) t.vy *= -1;
                
                // 偶尔发生微小的加速度变化，模拟真实物体的不规则运动
                if (Math.random() < 0.05) {
                    t.vx += (Math.random() - 0.5) * 2;
                    t.vy += (Math.random() - 0.5) * 2;
                }
            });
            // 返回深拷贝的数据，防止引用污染
            return JSON.parse(JSON.stringify(this.targets)); 
        }
    }

    // ==========================================
    // 模块 B: 模拟推流与前端渲染大循环
    // 作用：结合视频帧和生成的数据，并处理“频率差异”，最终画到 Canvas 上
    // ==========================================
    function startMockBackendAndRender() {
        const dataGenerator = new MockDataGenerator(video.videoWidth, video.videoHeight);
        
        let frameCount = 0;
        let lastDetectionData =[]; // 用于缓存低频的检测数据

        // 使用 requestAnimationFrame 保证渲染性能（与显示器刷新率同步）
        function renderLoop() {
            // 如果视频还没播放，或者暂停了，就继续等待下一帧
            if (video.paused || video.ended) {
                requestAnimationFrame(renderLoop);
                return;
            }

            frameCount++;

            // 1. 获取当前画面的“真实”目标物理位置
            const currentTargets = dataGenerator.update();

            // 2. 模拟 WebSocket 接收到的【跟踪数据】 (高频：每一帧都有)
            const trackingData = currentTargets; 

            // 3. 模拟 WebSocket 接收到的【检测数据】 (低频：比如每 15 帧才进行一次检测)
            if (frameCount % 15 === 0) {
                lastDetectionData = JSON.parse(JSON.stringify(currentTargets));
            }

            // 4. 开始向三个 Canvas 渲染数据
            // [融合视图]：你要求显示“原始的视频流”，我们就只画原视频
            renderCanvas(ctxFusion, video, null, null); 
            
            // [检测视图]：画视频 + 缓存的低频检测框 (青色)
            renderCanvas(ctxDet, video, lastDetectionData, null);
            
            // [跟踪视图]：画视频 + 实时的高频跟踪框 (紫色)
            renderCanvas(ctxTrack, video, null, trackingData);

            // 循环调用
            requestAnimationFrame(renderLoop);
        }

        // 启动循环
        requestAnimationFrame(renderLoop);
    }

    // ==========================================
    // 模块 C: 统一的 Canvas 渲染函数
    // 作用：把视频画面和框画到 Canvas 上
    // ==========================================
    function renderCanvas(ctx, videoElement, detectData, trackData) {
        // 第一步：把当前的视频帧画到底层（性能极高，覆盖上一帧的内容）
        ctx.drawImage(videoElement, 0, 0, ctx.canvas.width, ctx.canvas.height);

        // 第二步：如果要画检测框（YOLO_PRO 风格）
        if (detectData) {
            ctx.lineWidth = 3;
            ctx.strokeStyle = '#06b6d4'; // Cyan-500
            ctx.fillStyle = '#06b6d4';
            ctx.font = '18px monospace';

            detectData.forEach(box => {
                // 画检测框
                ctx.strokeRect(box.x, box.y, box.width, box.height);
                // 画标签背景
                ctx.fillRect(box.x, box.y - 25, 80, 25);
                // 画文字
                ctx.fillStyle = '#000';
                ctx.fillText(`DET:${box.class}`, box.x + 5, box.y - 8);
                ctx.fillStyle = '#06b6d4'; // 恢复画笔颜色
            });
        }

        // 第三步：如果要画跟踪框（DEEPSORT 风格）
        if (trackData) {
            ctx.lineWidth = 2;
            ctx.strokeStyle = '#a855f7'; // Purple-500
            ctx.fillStyle = '#a855f7';
            ctx.font = 'bold 16px monospace';

            trackData.forEach(box => {
                // 跟踪框用不同的样式，比如虚线或只画四个角，这里为了演示画个细实线+中心点
                ctx.strokeRect(box.x, box.y, box.width, box.height);
                
                // 画跟踪 ID
                ctx.fillText(`ID: ${box.id}`, box.x + 5, box.y + 20);

                // 画目标中心点（模拟运动轨迹锚点）
                ctx.beginPath();
                ctx.arc(box.x + box.width / 2, box.y + box.height / 2, 4, 0, Math.PI * 2);
                ctx.fill();
            });
        }
    }
});