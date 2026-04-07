package common

import "algo-container-manager/internal/model"

func BuildDeploymentLabels(req model.StartAlgorithmRequest) map[string]string {
	labels := map[string]string{
		"app": req.DeploymentName,
	}

	if req.Name != "" {
		labels["algorithm-name"] = req.Name
	}
	if req.Version != "" {
		labels["algorithm-version"] = req.Version
	}
	if req.VersionUUID != "" {
		labels["version-uuid"] = req.VersionUUID
	}

	return labels
}
