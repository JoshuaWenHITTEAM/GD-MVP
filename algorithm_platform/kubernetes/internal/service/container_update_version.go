package service

import (
	"context"
	"fmt"

	"algo-container-manager/internal/db"
	"algo-container-manager/internal/k8s"
	"algo-container-manager/internal/model"
)

func (s *ContainerService) UpdateVersion(name, namespace, versionUUID string) error {
	if namespace == "" {
		namespace = "default"
	}
	if name == "" {
		return fmt.Errorf("deployment name is required")
	}
	if versionUUID == "" {
		return fmt.Errorf("versionUuid is required")
	}

	var ver model.AlgorithmVersion
	if err := db.DB.Where("uuid = ?", versionUUID).First(&ver).Error; err != nil {
		return fmt.Errorf("find algorithm version failed: %w", err)
	}

	if ver.PublishStatus != "PUBLISHED" {
		return fmt.Errorf("algorithm version %s is not published", versionUUID)
	}

	image := ""
	if ver.FullImageURI != "" {
		image = ver.FullImageURI
	} else if ver.LocalImageName != "" {
		image = ver.LocalImageName
	}

	if image == "" {
		return fmt.Errorf("algorithm version %s has no deployable image", versionUUID)
	}

	if _, err := k8s.UpdateDeploymentImage(
		context.Background(),
		s.clientset,
		namespace,
		name,
		image,
	); err != nil {
		return err
	}

	if err := db.DB.Model(&model.DeployRecord{}).
		Where("k8s_deployment_name = ? AND namespace = ? AND is_deleted = ?", name, namespace, 0).
		Updates(map[string]interface{}{
			"version_uuid": versionUUID,
			"image":        image,
		}).Error; err != nil {
		return fmt.Errorf("update deploy record failed: %w", err)
	}

	return nil
}
