package model

import "time"

// AlgorithmVersion 映射共享表 versions
type AlgorithmVersion struct {
	UUID string `gorm:"column:uuid;type:varchar(64);primaryKey" json:"uuid"`

	AlgorithmUUID string `gorm:"column:algorithmUuid;type:varchar(64);not null;index" json:"algorithmUuid"`

	// 暂时保留，避免别的代码大面积报错，但不映射数据库
	AlgorithmCode string `gorm:"-" json:"algorithmCode"`
	AlgorithmName string `gorm:"-" json:"algorithmName"`
	RuntimeType   string `gorm:"-" json:"runtimeType"`

	Version     string `gorm:"column:version;type:varchar(64);not null" json:"version"`
	VersionName string `gorm:"column:versionName;type:varchar(128);not null" json:"versionName"`

	Entrypoint string `gorm:"column:entrypoint;type:varchar(255);not null" json:"entrypoint"`
	Changelog  string `gorm:"column:changelog;type:text;not null" json:"changelog"`

	SourceType      string `gorm:"column:sourceType;type:varchar(32);not null" json:"sourceType"`
	LocalImageName  string `gorm:"column:localImageName;type:varchar(255);not null" json:"localImageName"`
	ImagePullPolicy string `gorm:"column:imagePullPolicy;type:varchar(32);not null" json:"imagePullPolicy"`
	RegistryURL     string `gorm:"column:registryUrl;type:varchar(255);not null" json:"registryUrl"`
	RepositoryName  string `gorm:"column:repositoryName;type:varchar(255);not null" json:"repositoryName"`
	ImageTag        string `gorm:"column:imageTag;type:varchar(128);not null" json:"imageTag"`
	ImageDigest     string `gorm:"column:imageDigest;type:varchar(255)" json:"imageDigest"`
	FullImageURI    string `gorm:"column:fullImageUri;type:varchar(512);not null" json:"fullImageUri"`
	ImageSize       int64  `gorm:"column:imageSize" json:"imageSize"`

	PublishStatus string `gorm:"column:publishStatus;type:varchar(32);not null;index" json:"publishStatus"`

	IsDeleted int `gorm:"column:is_deleted;type:tinyint(1);not null;default:0;index" json:"isDeleted"`

	CreatedAt *time.Time `gorm:"column:createdAt" json:"createdAt"`
	UpdatedAt *time.Time `gorm:"column:updatedAt" json:"updatedAt"`
}

func (AlgorithmVersion) TableName() string {
	return "versions"
}
