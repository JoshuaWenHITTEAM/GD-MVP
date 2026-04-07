package model

import "time"

// AlgorithmVersion 表示一个可部署的算法版本。
// 这张表只保留部署侧真正需要的字段：版本标识、镜像信息、启动信息、发布状态。
type AlgorithmVersion struct {
	UUID string `gorm:"type:varchar(64);primaryKey" json:"uuid"`

	AlgorithmCode string `gorm:"type:varchar(64);index;not null" json:"algorithmCode"`
	AlgorithmName string `gorm:"type:varchar(128);not null" json:"algorithmName"`
	Version       string `gorm:"type:varchar(64);not null" json:"version"`
	VersionName   string `gorm:"type:varchar(128)" json:"versionName"`

	Entrypoint string `gorm:"type:varchar(255)" json:"entrypoint"`

	RuntimeType string `gorm:"type:varchar(32)" json:"runtimeType"`
	ConfigPath  string `gorm:"type:varchar(255)" json:"configPath"`
	SourceType  string `gorm:"type:varchar(32)" json:"sourceType"`

	LocalImageName  string `gorm:"type:varchar(255)" json:"localImageName"`
	ImagePullPolicy string `gorm:"type:varchar(32)" json:"imagePullPolicy"`
	FullImageURI    string `gorm:"type:varchar(512)" json:"fullImageUri"`
	ImageSize       string `gorm:"type:varchar(64)" json:"imageSize"`

	// PublishStatus：发布状态，例如 DRAFT / PUBLISHED / OFFLINE。
	// DRAFT：草稿，未发布
	// PUBLISHED：已发布，可部署
	// OFFLINE：已下线，不建议继续部署
	PublishStatus string `gorm:"type:varchar(32);index" json:"publishStatus"`

	CreatedAt time.Time `json:"createdAt"`
	UpdatedAt time.Time `json:"updatedAt"`
}
