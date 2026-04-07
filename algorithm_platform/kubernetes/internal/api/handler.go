package api

import (
	"io"
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

func (h *Handler) InferContainer(context *gin.Context) {
	name := context.Param("name")
	namespace := context.DefaultQuery("namespace", "default")

	fileHeader, err := context.FormFile("file")
	if err != nil {
		common.Fail(context, http.StatusBadRequest, "file is required")
		return
	}

	file, err := fileHeader.Open()
	if err != nil {
		common.Fail(context, http.StatusBadRequest, "open uploaded file failed")
		return
	}
	defer file.Close()

	content, err := io.ReadAll(file)
	if err != nil {
		common.Fail(context, http.StatusBadRequest, "read upload file failed")
		return
	}

	fields := map[string]string{}
	form, _ := context.MultipartForm()
	if form != nil {
		for key, vals := range form.Value {
			if len(vals) > 0 {
				fields[key] = vals[0]
			}
		}
	}

	raw, err := h.containerSvc.Infer(name, namespace, fileHeader.Filename, content, fields)
	if err != nil {
		common.Fail(context, http.StatusInternalServerError, err.Error())
		return
	}

	context.Data(http.StatusOK, "application/json; charset = utf-8", raw)
}

func (h *Handler) UpdateContainerImage(context *gin.Context) {
	name := context.Param("name")
	namespace := context.DefaultQuery("namespace", "default")

	var req model.UpdateImageRequest
	if err := context.ShouldBindJSON(&req); err != nil {
		common.Fail(context, http.StatusBadRequest, err.Error())
		return
	}

	if req.Image == "" {
		common.Fail(context, http.StatusBadRequest, "image is required")
		return
	}

	if err := h.containerSvc.UpdateImage(name, namespace, req.Image); err != nil {
		common.Fail(context, http.StatusInternalServerError, err.Error())
		return
	}

	common.Success(context, gin.H{
		"deploymentName": name,
		"namespace":      namespace,
		"image":          req.Image,
	})
}

func (h *Handler) UpdateContainerVersion(context *gin.Context) {
	name := context.Param("name")
	namespace := context.DefaultQuery("namespace", "default")

	var req model.UpdateVersionRequest
	if err := context.ShouldBindJSON(&req); err != nil {
		common.Fail(context, http.StatusBadRequest, err.Error())
		return
	}

	if req.VersionUUID == "" {
		common.Fail(context, http.StatusBadRequest, "versionUuid is required")
		return
	}

	if err := h.containerSvc.UpdateVersion(name, namespace, req.VersionUUID); err != nil {
		common.Fail(context, http.StatusInternalServerError, err.Error())
		return
	}

	common.Success(context, gin.H{
		"deploymentName": name,
		"namespace":      namespace,
		"versionUuid":    req.VersionUUID,
	})
}
