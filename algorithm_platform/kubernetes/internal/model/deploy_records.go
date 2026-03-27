package model

import "time"

type DeployRecord struct {
	ID uint64 `gorm:"primaryKey;autoIncrement" json:"id"`

	UUID string `gorm:"type:varchar(36);uniqueIndex" json:"uuid"`

	AlgorithmVersionID uint64 `gorm:"index" json:"algorithmVersionId"`
	ImageID            uint64 `gorm:"index" json:"imageId"`

	Namespace         string `gorm:"type:varchar(64)" json:"namespace"`
	K8sDeploymentName string `gorm:"type:varchar(128)" json:"k8sDeploymentName"`
	K8sServiceName    string `gorm:"type:varchar(128)" json:"k8sServiceName"`

	DeployStatus   string `gorm:"type:varchar(16);index" json:"deployStatus"`
	AccessEndpoint string `gorm:"type:varchar(255)" json:"accessEndpoint,omitempty"`

	IsDeleted int `grom:"type:tinyint(1);not null; default:0; index" json:"isDeleted"`

	DeployedAt time.Time `gorm:"autoCreateTime" json:"deployedAt"`
	UpdatedAt  time.Time `gorm:"autoUpdateTime" json:"updatedAt"`
}
