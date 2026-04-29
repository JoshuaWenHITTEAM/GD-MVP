package service

import (
	"algo-container-manager/internal/db"
	"algo-container-manager/internal/k8s"
	"algo-container-manager/internal/model"
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"
	"gorm.io/gorm"
)

func parseImageTag(image string) string {
	lastSlash := strings.LastIndex(image, "/")
	lastColon := strings.LastIndex(image, ":")
	if lastColon > lastSlash {
		return image[lastColon+1:]
	}
	return ""
}

func parseRepositoryName(image string) string {
	lastSlash := strings.LastIndex(image, "/")
	lastColon := strings.LastIndex(image, ":")

	end := len(image)
	if lastColon > lastSlash {
		end = lastColon
	}
	if lastSlash >= 0 {
		return image[lastSlash+1 : end]
	}
	return image[:end]
}

func (s *ContainerService) UpdateImage(
	name string,
	namespace string,
	newImage string,
) (string, error) {
	if namespace == "" {
		namespace = "default"
	}
	if name == "" {
		return "", fmt.Errorf("deployment name is required")
	}
	if newImage == "" {
		return "", fmt.Errorf("new image is required")
	}

	// 1. 查当前部署记录
	var record model.DeployRecord
	if err := db.DB.
		Where("deploymentName = ? AND namespace = ? AND is_deleted = ?", name, namespace, 0).
		First(&record).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return "", fmt.Errorf("deploy record not found")
		}
		return "", fmt.Errorf("query deploy record failed: %w", err)
	}

	// 2. 查当前绑定的旧版本
	var oldVer model.AlgorithmVersion
	if err := db.DB.
		Where("uuid = ? AND is_deleted = ?", record.VersionUUID, 0).
		First(&oldVer).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return "", fmt.Errorf("current algorithm version not found: %s", record.VersionUUID)
		}
		return "", fmt.Errorf("query current algorithm version failed: %w", err)
	}

	oldImage := record.Image
	oldVersionUUID := record.VersionUUID

	now := time.Now()
	newVersionUUID := "ver-" + uuid.NewString()
	autoVersion := "auto-" + now.Format("20060102150405")

	// 3. 显式构造新版本，不要整对象复制
	newVer := model.AlgorithmVersion{
		UUID:            newVersionUUID,
		AlgorithmUUID:   oldVer.AlgorithmUUID,
		Version:         autoVersion,
		VersionName:     autoVersion,
		Entrypoint:      oldVer.Entrypoint,
		Changelog:       "auto created by image update",
		SourceType:      oldVer.SourceType,
		LocalImageName:  newImage,
		ImagePullPolicy: oldVer.ImagePullPolicy,
		RegistryURL:     oldVer.RegistryURL,
		RepositoryName:  parseRepositoryName(newImage),
		ImageTag:        parseImageTag(newImage),
		ImageDigest:     "",
		FullImageURI:    newImage,
		ImageSize:       oldVer.ImageSize,
		PublishStatus:   oldVer.PublishStatus,
		IsDeleted:       0,
		CreatedAt:       &now,
		UpdatedAt:       &now,
	}

	// 4. 先写版本表
	if err := db.DB.Create(&newVer).Error; err != nil {
		return "", fmt.Errorf("create new algorithm version failed: %w", err)
	}

	// 5. 更新 K8s deployment 镜像
	if _, err := k8s.UpdateDeploymentImage(
		context.Background(),
		s.clientset,
		namespace,
		name,
		newImage,
	); err != nil {
		_ = db.DB.Where("uuid = ?", newVersionUUID).Delete(&model.AlgorithmVersion{}).Error
		return "", fmt.Errorf("update k8s deployment image failed: %w", err)
	}

	// 6. 回写部署记录
	if err := db.DB.Model(&record).Updates(map[string]interface{}{
		"versionUuid": newVersionUUID,
		"image":       newImage,
		"updatedAt":   now,
	}).Error; err != nil {
		_, _ = k8s.UpdateDeploymentImage(
			context.Background(),
			s.clientset,
			namespace,
			name,
			oldImage,
		)

		_ = db.DB.Model(&record).Updates(map[string]interface{}{
			"versionUuid": oldVersionUUID,
			"image":       oldImage,
			"updatedAt":   now,
		}).Error

		return "", fmt.Errorf("update deploy record failed after k8s updated, rollback attempted: %w", err)
	}

	return newVersionUUID, nil
}