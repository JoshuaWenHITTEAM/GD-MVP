package api

import "github.com/gin-gonic/gin"

func NewRouter(handler *Handler) *gin.Engine {
	r := gin.Default()
	apiV1 := r.Group("/api/v1")
	// 1. 创建
	apiV1.POST("/containers/start", handler.StartAlgorithm)

	// 2. 查询（管理视角：数据库）
	apiV1.GET("/containers", handler.ListContainers)

	// 3. 查询（运行视角：K8s）
	apiV1.GET("/containers/runtime", handler.ListRuntimeContainers)
	apiV1.GET("/containers/:name/status", handler.GetContainerStatus)

	// 4. 操作（生命周期管理）
	apiV1.DELETE("/containers/:name", handler.DeleteContainer)
	apiV1.POST("/containers/:name/restart", handler.RestartContainer)
	apiV1.POST("/containers/:name/scale", handler.ScaleContainer)

	return r
}
