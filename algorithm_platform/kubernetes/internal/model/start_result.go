package model

type StartResult struct {
	DeploymentName string `json:"deploymentName"`
	ServiceName    string `json:"serviceName"`
	Namespace      string `json:"namespace"`
}
