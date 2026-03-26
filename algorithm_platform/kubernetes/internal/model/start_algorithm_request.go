package model

type StartAlgorithmRequest struct {
	AlgorithmVersionID uint64 `json:"algorithmVersionId"`
	ImageID            uint64 `json:"imageId"`

	Name           string `json:"name"`
	Version        string `json:"version"`
	Image          string `json:"image"`
	Namespace      string `json:"namespace"`
	DeploymentName string `json:"deploymentName"`
	ServiceName    string `json:"serviceName"`

	Port     int32             `json:"port"`
	Replicas int32             `json:"replicas"`
	Env      map[string]string `json:"env"`
	CPU      string            `json:"cpu"`
	Memory   string            `json:"memory"`

	HealthPath string `json:"healthPath"`
	ReadyPath  string `json:"readyPath"`

	EnablePDB    bool  `json:"enablePDB"`
	MinAvailable int32 `json:"minAvailable"`
}
