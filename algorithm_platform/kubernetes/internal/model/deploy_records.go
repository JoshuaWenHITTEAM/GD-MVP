package model

import "time"

type DeployRecord struct {
	ID   uint64 `gorm:"primaryKey;autoIncrement" json:"id"`
	UUID string `gorm:"type:varchar(36);uniqueIndex" json:"uuid"`

	VersionUUID string `gorm:"type:varchar(64);index" json:"versionUuid"`

	Namespace         string `gorm:"type:varchar(64)" json:"namespace"`
	K8sDeploymentName string `gorm:"type:varchar(128);index" json:"k8sDeploymentName"`
	K8sServiceName    string `gorm:"type:varchar(128)" json:"k8sServiceName"`

	DeployStatus   string `gorm:"type:varchar(32);index" json:"deployStatus"`
	AccessEndpoint string `gorm:"type:varchar(255)" json:"accessEndpoint,omitempty"`
	Image          string `gorm:"type:varchar(512)" json:"image"`

	Port          int32 `json:"port"`
	Replicas      int32 `json:"replicas"`
	ReadyReplicas int32 `json:"readyReplicas"`

	ErrorMessage string `gorm:"type:text" json:"errorMessage"`
	Env          string `gorm:"type:text" json:"env"`
	Resources    string `gorm:"type:text" json:"resources"`

	IsDeleted int `gorm:"type:tinyint(1);not null;default:0;index" json:"isDeleted"`

	DeployedAt time.Time `gorm:"autoCreateTime" json:"deployedAt"`
	UpdatedAt  time.Time `gorm:"autoUpdateTime" json:"updatedAt"`
}
