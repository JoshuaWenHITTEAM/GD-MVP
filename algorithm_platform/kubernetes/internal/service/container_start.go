package service

import (
	"fmt"

	"algo-container-manager/internal/common"
	"algo-container-manager/internal/db"
	"algo-container-manager/internal/k8s"
	"algo-container-manager/internal/model"

	"github.com/google/uuid"
)

func (s *ContainerService) Start(req model.StartAlgorithmRequest) (*model.StartResult, error) {
	uid := uuid.New().String()

	s.prepareStartRequest(&req, uid)

	if err := k8s.CreateDeployment(s.clientset, req); err != nil {
		return nil, fmt.Errorf("create deployment failed: %w", err)
	}

	if err := k8s.CreateService(s.clientset, req); err != nil {
		_ = k8s.DeleteAlgorithm(s.clientset, req.Namespace, req.DeploymentName)
		return nil, fmt.Errorf("create service failed: %w", err)
	}
	if err := k8s.CreatePDB(s.clientset, req); err != nil {
		_ = k8s.DeleteAlgorithm(s.clientset, req.Namespace, req.DeploymentName)
		_ = k8s.DeleteService(s.clientset, req.Namespace, req.ServiceName)
		return nil, fmt.Errorf("create pdb failed: %w", err)
	}

	record := s.buildDeployRecord(req, uid)

	if err := s.saveDeployRecord(record); err != nil {
		_ = k8s.DeletePDB(s.clientset, req.Namespace, req.DeploymentName+"-pdb")
		_ = k8s.DeleteAlgorithm(s.clientset, req.Namespace, req.DeploymentName)
		_ = k8s.DeleteService(s.clientset, req.Namespace, req.ServiceName)
		return nil, fmt.Errorf("save deploy record failed: %w", err)
	}

	return &model.StartResult{
		DeploymentName: req.DeploymentName,
		ServiceName:    req.ServiceName,
		Namespace:      req.Namespace,
	}, nil
}

func (s *ContainerService) prepareStartRequest(req *model.StartAlgorithmRequest, uid string) {
	if req.Namespace == "" {
		req.Namespace = "default"
	}
	if req.DeploymentName == "" {
		req.DeploymentName = common.BuildDeploymentName(req.Name, req.Version, uid)
	}
	if req.ServiceName == "" {
		req.ServiceName = common.BuildServiceName(req.DeploymentName)
	}
	if req.Port == 0 {
		req.Port = 80
	}
	if req.CPU == "" {
		req.CPU = "500m"
	}
	if req.Memory == "" {
		req.Memory = "512Mi"
	}
	if req.Replicas <= 0 {
		req.Replicas = 1
	}

	if req.EnablePDB && req.MinAvailable <= 0 {
		req.MinAvailable = 1
	}
	if req.EnablePDB && req.Replicas < 2 {
		req.Replicas = 2
	}
	if req.ReadyPath == "" {
		req.ReadyPath = "/ready"
	}
	if req.HealthPath == "" {
		req.HealthPath = "/healthz"
	}

}

func (s *ContainerService) buildDeployRecord(req model.StartAlgorithmRequest, uid string) model.DeployRecord {
	return model.DeployRecord{
		UUID:               uid,
		AlgorithmVersionID: req.AlgorithmVersionID,
		ImageID:            req.ImageID,
		Namespace:          req.Namespace,
		K8sDeploymentName:  req.DeploymentName,
		K8sServiceName:     req.ServiceName,
		DeployStatus:       "deploying",
		AccessEndpoint:     "",
		IsDeleted:          0,
	}
}

func (s *ContainerService) saveDeployRecord(record model.DeployRecord) error {
	return db.DB.Create(&record).Error
}
