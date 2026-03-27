package service

import (
	"context"

	"algo-container-manager/internal/db"
	"algo-container-manager/internal/k8s"
	"algo-container-manager/internal/model"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

func (s *ContainerService) List(namespace string) ([]model.ContainerInstance, error) {
	return k8s.ListContainers(s.clientset, namespace)
}

func (s *ContainerService) ListDeployRecords() ([]model.DeployRecord, error) {
	var records []model.DeployRecord
	if err := db.DB.
		Where("is_deleted = ?", 0).
		Order("is desc").
		Find(&records).Error; err != nil {
		return nil, err
	}
	for _, record := range records {
		_, _ = s.GetStatus(record.K8sDeploymentName, record.Namespace)
	}

	if err := db.DB.
		Where("is_deleted = ?", 0).
		Order("is desc").
		Find(&records).Error; err != nil {
		return nil, err
	}

	return records, nil
}

func (s *ContainerService) GetStatus(name, namespace string) (map[string]interface{}, error) {
	deploy, err := s.clientset.AppsV1().
		Deployments(namespace).
		Get(context.TODO(), name, metav1.GetOptions{})
	if err != nil {
		s.updateDeployStatus(name, namespace, "failed")
		return nil, err
	}

	var replicas int32 = 0
	if deploy.Spec.Replicas != nil {
		replicas = *deploy.Spec.Replicas
	}

	deployStatus := k8s.DeploymentStatus(deploy.Status.ReadyReplicas, replicas)
	s.updateDeployStatus(name, namespace, deployStatus)

	result := map[string]interface{}{
		"name":              deploy.Name,
		"namespace":         deploy.Namespace,
		"replicas":          replicas,
		"readyReplicas":     deploy.Status.ReadyReplicas,
		"availableReplicas": deploy.Status.AvailableReplicas,
		"deployStatus":      deployStatus,
	}

	return result, nil
}

func (s *ContainerService) updateDeployStatus(name, namespace, status string) {
	_ = db.DB.Model(&model.DeployRecord{}).
		Where("k8s_deployment_name = ? AND namespace = ? AND is_delete = ?", name, namespace, 0).
		Update("deploy_status", status).Error
}

func (s *ContainerService) deleteDeployRecord(name, namespace string) error {
	return db.DB.Where("k8s_deployment_name = ? AND namespace = ? AND is_delete = ?", name, namespace, 0).
		Updates(map[string]interface{}{
			"is_deleted":    1,
			"deploy_status": "deleted",
		}).Error
}

func (s *ContainerService) Delete(name, namespace string) error {
	_ = k8s.DeletePDB(s.clientset, namespace, name+"-pdb")

	if err := k8s.DeleteAlgorithm(s.clientset, namespace, name); err != nil {
		return err
	}
	return s.deleteDeployRecord(name, namespace)
}

func (s *ContainerService) Restart(name, namespace string) error {
	return k8s.RestartDeployment(s.clientset, namespace, name)
}

func (s *ContainerService) Scale(name, namespace string, replicas int32) error {
	return k8s.ScaleDeployment(s.clientset, namespace, name, replicas)
}
