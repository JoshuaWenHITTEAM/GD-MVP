package k8s

import (
	"context"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
)

func DeleteAlgorithm(clientset *kubernetes.Clientset, namespace string, name string) error {
	_ = clientset.CoreV1().
		Services(namespace).
		Delete(context.Background(), name+"-svc", metav1.DeleteOptions{})

	return clientset.AppsV1().
		Deployments(namespace).
		Delete(context.Background(), name, metav1.DeleteOptions{})
}
