package k8s

import (
	"context"
	"fmt"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
)

func DeletePDB(clientset *kubernetes.Clientset, namespace, pdbName string) error {
	if namespace == "" {
		return fmt.Errorf("namespace is required")
	}
	if pdbName == "" {
		return fmt.Errorf("pdb name is required")
	}

	err := clientset.PolicyV1().
		PodDisruptionBudgets(namespace).
		Delete(context.Background(), pdbName, metav1.DeleteOptions{})
	if err != nil {
		return fmt.Errorf("delete pdb failed: %w", err)
	}
	return nil
}
