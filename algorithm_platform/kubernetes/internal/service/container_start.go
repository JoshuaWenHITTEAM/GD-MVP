package service

import (
	"encoding/json"
	"fmt"

	"algo-container-manager/internal/common"
	"algo-container-manager/internal/db"
	"algo-container-manager/internal/k8s"
	"algo-container-manager/internal/model"

	"github.com/google/uuid"
)

func (s *ContainerService) Start(req model.StartAlgorithmRequest) (*model.StartResult, error) {
	uid := uuid.New().String()

	// 先根据 versionUuid 补齐镜像和基础信息
	if err := s.resolveVersionForStart(&req); err != nil {
		return nil, err
	}

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

func (s *ContainerService) resolveVersionForStart(req *model.StartAlgorithmRequest) error {
	// 新逻辑：传了 versionUuid，就查版本表
	if req.VersionUUID != "" {
		var ver model.AlgorithmVersion
		if err := db.DB.Where("uuid = ?", req.VersionUUID).First(&ver).Error; err != nil {
			return fmt.Errorf("algorithm version not found: %w", err)
		}

		if ver.PublishStatus != "PUBLISHED" {
			return fmt.Errorf("algorithm version %s is not published", ver.UUID)
		}

		// 如果请求里没传 name/version，就从版本表补
		if req.Name == "" {
			req.Name = ver.AlgorithmCode
		}
		if req.Version == "" {
			req.Version = ver.Version
		}

		// 优先完整镜像地址，其次本地镜像名
		if req.Image == "" {
			if ver.FullImageURI != "" {
				req.Image = ver.FullImageURI
			} else if ver.LocalImageName != "" {
				req.Image = ver.LocalImageName
			} else {
				return fmt.Errorf("algorithm version %s has no deployable image", ver.UUID)
			}
		}
	}

	// 旧逻辑兜底：没传 versionUuid，就必须直接传 image
	if req.Image == "" {
		return fmt.Errorf("image is required")
	}

	return nil
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
		req.Port = 8080
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
	envJSON, _ := json.Marshal(req.Env)

	resourcesJSON, _ := json.Marshal(map[string]string{
		"cpu":    req.CPU,
		"memory": req.Memory,
	})

	return model.DeployRecord{
		UUID:              uid,
		VersionUUID:       req.VersionUUID,
		Namespace:         req.Namespace,
		K8sDeploymentName: req.DeploymentName,
		K8sServiceName:    req.ServiceName,
		DeployStatus:      "deploying",
		AccessEndpoint:    "",
		Image:             req.Image,
		Port:              req.Port,
		Replicas:          req.Replicas,
		ReadyReplicas:     0,
		ErrorMessage:      "",
		Env:               string(envJSON),
		Resources:         string(resourcesJSON),
		IsDeleted:         0,
	}
}

func (s *ContainerService) saveDeployRecord(record model.DeployRecord) error {
	return db.DB.Create(&record).Error
}
