package k8s

import (
	"context"
	"fmt"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
)

func DeleteService(clientset *kubernetes.Clientset, namespace, serviceName string) error {
	if namespace == "" {
		return fmt.Errorf("namespace is required")
	}
	if serviceName == "" {
		return fmt.Errorf("service name is required")
	}

	err := clientset.CoreV1().
		Services(namespace).
		Delete(context.Background(), serviceName, metav1.DeleteOptions{})
	if err != nil {
		return fmt.Errorf("delete service failed: %w", err)
	}
	return nil
}
