package model

type ContainerInstance struct {
	AlgorithmVersionID uint64 `json:"algorithmVersionId,omitempty"`

	Name       string `json:"name"`
	Namespace  string `json:"namespace"`
	Deployment string `json:"deployment"`
	Service    string `json:"service"`

	Status            string `json:"status"`
	Image             string `json:"image"`
	Replicas          int32  `json:"replicas"`
	ReadyReplicas     int32  `json:"readyReplicas"`
	AvailableReplicas int32  `json:"availableReplicas,omitempty"`

	AccessEndpoint string `json:"accessEndpoint,omitempty"`
}
