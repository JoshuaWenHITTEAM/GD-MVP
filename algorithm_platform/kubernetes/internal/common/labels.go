package common

import (
	"algo-container-manager/internal/model"
	"fmt"
)

// BuildDeploymentLabels 为 Deployment 创建标签
func BuildDeploymentLabels(req model.StartAlgorithmRequest) map[string]string {
	labels := map[string]string{
		"app": req.DeploymentName,
	}

	if req.AlgorithmVersionID > 0 {
		labels["algorithm-version-id"] = fmt.Sprintf("%d", req.AlgorithmVersionID)
	}
	if req.ImageID > 0 {
		labels["image-id"] = fmt.Sprintf("%d", req.ImageID)
	}
	if req.Name != "" {
		labels["algorithm-name"] = req.Name
	}
	if req.Version != "" {
		labels["algorithm-version"] = req.Version
	}

	return labels
}
