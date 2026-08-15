package k8s

import (
	"algo-container-manager/internal/common"
	"algo-container-manager/internal/model"
	"context"
	"fmt"

	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/resource"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/util/intstr"
	"k8s.io/client-go/kubernetes"
)

func CreateDeployment(clientset *kubernetes.Clientset, req model.StartAlgorithmRequest) error {
	deploymentName := req.DeploymentName
	if deploymentName == "" {
		return fmt.Errorf("deployment name is required")
	}

	labels := common.BuildDeploymentLabels(req)
	envVars := common.BuildEnvVars(req.Env)

	replicas := req.Replicas
	containerPort := req.Port
	readyPath := req.ReadyPath
	healthPath := req.HealthPath
	workingDir := "/workspace"

	// 默认滚动更新策略：更新镜像时平滑 rollout
	maxUnavailable := intstr.FromInt(0)
	maxSurge := intstr.FromInt(1)

	container := corev1.Container{
		Name:            deploymentName,
		Image:           req.Image,
		ImagePullPolicy: corev1.PullIfNotPresent,
		WorkingDir:      workingDir,
		Command:         []string{"uvicorn"}, // 新增
        Args:            []string{"app.server:app", "--host", "0.0.0.0", "--port", fmt.Sprintf("%d", containerPort), "--log-level", "info"}, // 新增
		Ports: []corev1.ContainerPort{
			{ContainerPort: containerPort},
		},
		Env: envVars,
		Resources: corev1.ResourceRequirements{
			Requests: corev1.ResourceList{
				corev1.ResourceCPU:    resource.MustParse(req.CPU),
				corev1.ResourceMemory: resource.MustParse(req.Memory),
			},
			Limits: corev1.ResourceList{
				corev1.ResourceCPU:    resource.MustParse(req.CPU),
				corev1.ResourceMemory: resource.MustParse(req.Memory),
			},
		},
		LivenessProbe: &corev1.Probe{
			ProbeHandler: corev1.ProbeHandler{
				HTTPGet: &corev1.HTTPGetAction{
					Path: healthPath,
					Port: intstr.FromInt32(containerPort),
				},
			},
			InitialDelaySeconds: 10,
			PeriodSeconds:       10,
			TimeoutSeconds:      2,
			FailureThreshold:    3,
			SuccessThreshold:    1,
		},
		ReadinessProbe: &corev1.Probe{
			ProbeHandler: corev1.ProbeHandler{
				HTTPGet: &corev1.HTTPGetAction{
					Path: readyPath,
					Port: intstr.FromInt32(containerPort),
				},
			},
			InitialDelaySeconds: 5,
			PeriodSeconds:       5,
			TimeoutSeconds:      2,
			FailureThreshold:    3,
			SuccessThreshold:    1,
		},
	}

	var volumes []corev1.Volume
	var volumeMounts []corev1.VolumeMount

	// 只挂模型，不挂代码
	if req.ModelHostPath != "" {
		dirType := corev1.HostPathDirectoryOrCreate

		volumes = append(volumes, corev1.Volume{
			Name: "model-volume",
			VolumeSource: corev1.VolumeSource{
				HostPath: &corev1.HostPathVolumeSource{
					Path: req.ModelHostPath,
					Type: &dirType,
				},
			},
		})

		volumeMounts = append(volumeMounts, corev1.VolumeMount{
			Name:      "model-volume",
			MountPath: "/models",
			ReadOnly:  true,
		})
	}

	if len(volumeMounts) > 0 {
		container.VolumeMounts = volumeMounts
	}

	deployment := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:      deploymentName,
			Namespace: req.Namespace,
			Labels:    labels,
		},
		Spec: appsv1.DeploymentSpec{
			Replicas: &replicas,
			Strategy: appsv1.DeploymentStrategy{
				Type: appsv1.RollingUpdateDeploymentStrategyType,
				RollingUpdate: &appsv1.RollingUpdateDeployment{
					MaxUnavailable: &maxUnavailable,
					MaxSurge:       &maxSurge,
				},
			},
			Selector: &metav1.LabelSelector{
				MatchLabels: map[string]string{
					"app": deploymentName,
				},
			},
			Template: corev1.PodTemplateSpec{
				ObjectMeta: metav1.ObjectMeta{
					Labels: labels,
				},
				Spec: corev1.PodSpec{
					RestartPolicy: corev1.RestartPolicyAlways,
					Containers:    []corev1.Container{container},
					Volumes:       volumes,
				},
			},
		},
	}

	_, err := clientset.AppsV1().
		Deployments(req.Namespace).
		Create(context.Background(), deployment, metav1.CreateOptions{})
	if err != nil {
		return fmt.Errorf("create deployment failed: %w", err)
	}

	return nil
}
