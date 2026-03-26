package k8s

import (
	"context"
	"fmt"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
)

func ScaleDeployment(clientset *kubernetes.Clientset, namespace string, deploymentName string, replicas int32) error {
	deploy, err := clientset.AppsV1().Deployments(namespace).Get(context.Background(), deploymentName, metav1.GetOptions{})

	if err != nil {
		return fmt.Errorf("deployment %s/%s not found", namespace, deploymentName)
	}

	deploy.Spec.Replicas = &replicas
	_, err = clientset.AppsV1().Deployments(namespace).Update(context.Background(), deploy, metav1.UpdateOptions{})
	if err != nil {
		return fmt.Errorf("deployment %s/%s update failed: %v", namespace, deploymentName, err)
	}
	return nil
}
