package model

import "time"

// DeployRecord 映射共享表 deployments
type DeployRecord struct {
	// 共享表 deployments 主键是 uuid，不建议再用自增 id 当主键
	ID uint64 `gorm:"-" json:"id,omitempty"`

	UUID string `gorm:"column:uuid;type:varchar(64);primaryKey" json:"uuid"`

	VersionUUID string `gorm:"column:versionUuid;type:varchar(64);index;not null" json:"versionUuid"`

	Namespace         string `gorm:"column:namespace;type:varchar(64);not null" json:"namespace"`
	K8sDeploymentName string `gorm:"column:deploymentName;type:varchar(128);index;not null" json:"k8sDeploymentName"`
	K8sServiceName    string `gorm:"column:serviceName;type:varchar(128);not null" json:"k8sServiceName"`

	DeployStatus   string `gorm:"column:status;type:varchar(32);index;not null" json:"deployStatus"`
	AccessEndpoint string `gorm:"column:accessEndpoint;type:varchar(255)" json:"accessEndpoint,omitempty"`
	Image          string `gorm:"column:image;type:varchar(512);not null" json:"image"`

	Port          int32 `gorm:"column:port;not null" json:"port"`
	Replicas      int32 `gorm:"column:replicas;not null" json:"replicas"`
	ReadyReplicas int32 `gorm:"column:readyReplicas;not null" json:"readyReplicas"`

	ErrorMessage string `gorm:"column:errorMessage;type:text" json:"errorMessage"`
	Env          string `gorm:"column:env;type:text" json:"env"`
	Resources    string `gorm:"column:resources;type:text" json:"resources"`

	IsDeleted  int  `gorm:"column:is_deleted;type:tinyint(1);not null;default:0;index" json:"isDeleted"`
	ActiveFlag *int `gorm:"column:active_flag" json:"activeFlag,omitempty"`

	DeployedAt *time.Time `gorm:"column:deployedAt" json:"deployedAt"`
	UpdatedAt  *time.Time `gorm:"column:updatedAt" json:"updatedAt"`
}

func (DeployRecord) TableName() string {
	return "deployments"
}
