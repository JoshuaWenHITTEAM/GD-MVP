package model

type UpdateVersionRequest struct {
	VersionUUID string `json:"versionUuid" binding:"required"`
}
