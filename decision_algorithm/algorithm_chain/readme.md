后端启动：uvicorn decision_algorithm.algorithm_chain.backend_service:app --host 0.0.0.0 --port 8010
前端启动：python3 -m http.server 8080

依赖的算法服务宿主端口参考 `decision_algorithm/images_build/compose.yaml`：
- `det_yolo`: `8004`
- `det_redetr`: `8001`
- `track_advi`: `8002`
- `track_siamrpnpp`: `8003`
