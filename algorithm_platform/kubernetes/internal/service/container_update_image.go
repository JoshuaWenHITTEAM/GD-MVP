package service

import (
	"context"
	"fmt"

	"algo-container-manager/internal/db"
	"algo-container-manager/internal/k8s"
	"algo-container-manager/internal/model"
)

func (s *ContainerService) UpdateImage(
	name string,
	namespace string,
	newImage string,
) error {
	if namespace == "" {
		namespace = "default"
	}
	if name == "" {
		return fmt.Errorf("deployment name is required")
	}
	if newImage == "" {
		return fmt.Errorf("new image is required")
	}

	var record model.DeployRecord
	if err := db.DB.
		Where("k8s_deployment_name = ? AND namespace = ? AND is_deleted = ?", name, namespace, 0).
		First(&record).Error; err != nil {
		return fmt.Errorf("deploy record not found: %w", err)
	}

	oldImage := record.Image

	if _, err := k8s.UpdateDeploymentImage(
		context.Background(),
		s.clientset,
		namespace,
		name,
		newImage,
	); err != nil {
		return err
	}

	if err := db.DB.Model(&record).Updates(map[string]interface{}{
		"image":        newImage,
		"version_uuid": "",
	}).Error; err != nil {
		_, _ = k8s.UpdateDeploymentImage(
			context.Background(),
			s.clientset,
			namespace,
			name,
			oldImage,
		)
		return fmt.Errorf("update deploy record failed after k8s updated, rollback attempted: %w", err)
	}

	return nil
}
