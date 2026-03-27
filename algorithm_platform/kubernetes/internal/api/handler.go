package api

import (
	"net/http"

	"algo-container-manager/internal/common"
	"algo-container-manager/internal/model"
	"algo-container-manager/internal/service"

	"github.com/gin-gonic/gin"
)

type Handler struct {
	containerSvc *service.ContainerService
}

func NewHandler(svc *service.ContainerService) *Handler {
	return &Handler{containerSvc: svc}
}

func (h *Handler) StartAlgorithm(context *gin.Context) {
	var req model.StartAlgorithmRequest
	if err := context.ShouldBindJSON(&req); err != nil {
		common.Fail(context, http.StatusBadRequest, err.Error())
		return
	}
	result, err := h.containerSvc.Start(req)
	if err != nil {
		common.Fail(context, http.StatusInternalServerError, err.Error())
		return
	}

	common.Success(context, result)
}

func (h *Handler) ListRuntimeContainers(context *gin.Context) {
	namespace := context.DefaultQuery("namespace", "default")
	data, err := h.containerSvc.List(namespace)
	if err != nil {
		common.Fail(context, http.StatusInternalServerError, err.Error())
		return
	}
	common.Success(context, gin.H{
		"items": data,
		"total": len(data),
	})
}

func (h *Handler) DeleteContainer(context *gin.Context) {
	name := context.Param("name")
	namespace := context.DefaultQuery("namespace", "default")

	err := h.containerSvc.Delete(name, namespace)
	if err != nil {
		common.Fail(context, http.StatusInternalServerError, err.Error())
		return
	}
	common.Success(context, gin.H{
		"deploymentName": name,
		"namespace":      namespace,
	})
}

func (h *Handler) RestartContainer(context *gin.Context) {
	name := context.Param("name")
	namespace := context.DefaultQuery("namespace", "default")

	err := h.containerSvc.Restart(name, namespace)
	if err != nil {
		common.Fail(context, http.StatusInternalServerError, err.Error())
		return
	}
	common.Success(context, gin.H{
		"deploymentName": name,
		"namespace":      namespace,
	})
}

func (h *Handler) ScaleContainer(context *gin.Context) {
	name := context.Param("name")
	namespace := context.DefaultQuery("namespace", "default")

	var req model.ScaleContainerRequest
	if err := context.ShouldBindJSON(&req); err != nil {
		common.Fail(context, http.StatusBadRequest, err.Error())
		return
	}

	if req.Replicas <= 0 {
		common.Fail(context, http.StatusBadRequest, "replicas must be greater than 0")
		return
	}

	if err := h.containerSvc.Scale(name, namespace, req.Replicas); err != nil {
		common.Fail(context, http.StatusInternalServerError, err.Error())
		return
	}
	common.Success(context, gin.H{
		"name":      name,
		"namespace": namespace,
		"replicas":  req.Replicas,
	})
}

func (h *Handler) ListContainers(c *gin.Context) {
	records, err := h.containerSvc.ListDeployRecords()
	if err != nil {
		common.Fail(c, http.StatusInternalServerError, err.Error())
		return
	}

	common.Success(c, gin.H{
		"items": records,
		"total": len(records),
	})
}

func (h *Handler) GetContainerStatus(c *gin.Context) {
	name := c.Param("name")
	namespace := c.DefaultQuery("namespace", "default")

	status, err := h.containerSvc.GetStatus(name, namespace)
	if err != nil {
		common.Fail(c, http.StatusInternalServerError, err.Error())
		return
	}

	common.Success(c, status)
}
