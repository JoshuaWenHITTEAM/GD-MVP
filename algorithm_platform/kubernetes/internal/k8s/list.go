package k8s

import (
	"context"
	"fmt"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"

	"algo-container-manager/internal/model"
)

func ListContainers(clientSet *kubernetes.Clientset, namespace string) ([]model.ContainerInstance, error) {
	list, err := clientSet.AppsV1().Deployments(namespace).List(context.Background(), metav1.ListOptions{})
	if err != nil {
		return nil, fmt.Errorf("list deployments failed: %w", err)
	}

	result := make([]model.ContainerInstance, 0, len(list.Items))

	for _, item := range list.Items {
		image := ""
		if len(item.Spec.Template.Spec.Containers) > 0 {
			image = item.Spec.Template.Spec.Containers[0].Image
		}

		instance := model.ContainerInstance{
			Name:          item.Name,
			Namespace:     item.Namespace,
			Deployment:    item.Name,
			Service:       item.Name + "-svc",
			Status:        DeploymentStatus(item.Status.ReadyReplicas, item.Status.Replicas),
			Image:         image,
			Replicas:      item.Status.Replicas,
			ReadyReplicas: item.Status.ReadyReplicas,
		}

		result = append(result, instance)
	}
	return result, nil

}

func DeploymentStatus(ready, total int32) string {
	if total == 0 {
		return "Stopped"
	}
	if ready == total {
		return "Running"
	}
	if ready == 0 {
		return "Pending"
	}

	return fmt.Sprintf("%d/%d", ready, total)

}
