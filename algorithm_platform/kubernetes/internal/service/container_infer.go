package service

import (
	"algo-container-manager/internal/common"
	"algo-container-manager/internal/db"
	"algo-container-manager/internal/k8s"
	"algo-container-manager/internal/model"
	"fmt"

	"gorm.io/gorm"
)

func (s *ContainerService) Infer(name, namespace, filename string, content []byte, fields map[string]string) ([]byte, error) {
	if len(content) == 0 {
		return nil, fmt.Errorf("file is empty")
	}

	serviceName, err := s.resolveServiceName(name, namespace)
	if err != nil {
		return nil, err
	}

	return k8s.ProxyMultipartToService(s.clientset, namespace, serviceName, "/infer", filename, content, fields)

}

func (s *ContainerService) resolveServiceName(name, namespace string) (string, error) {
	var record model.DeployRecord
	err := db.DB.
		Where("deploymentName = ? AND namespace = ? AND is_deleted = ?", name, namespace, 0).
		First(&record).Error
	if err == nil && record.K8sServiceName != "" {
		return record.K8sServiceName, nil
	}
	if err != nil && err != gorm.ErrRecordNotFound {
		return "", err
	}

	return common.BuildServiceName(name), nil
}
