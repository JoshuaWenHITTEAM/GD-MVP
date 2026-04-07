package model

type UpdateImageRequest struct {
	Image string `json:"image" binding:"required"`
}
