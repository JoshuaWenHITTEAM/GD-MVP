package k8s

import (
	"algo-container-manager/internal/model"
	"context"
	"fmt"

	policyv1 "k8s.io/api/policy/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/util/intstr"
	"k8s.io/client-go/kubernetes"
)

func CreatePDB(clientset *kubernetes.Clientset, req model.StartAlgorithmRequest) error {
	if !req.EnablePDB {
		return nil
	}

	if req.DeploymentName == "" {
		return fmt.Errorf("deployment name is required")
	}

	minAvailable := req.MinAvailable
	pdb := &policyv1.PodDisruptionBudget{
		ObjectMeta: metav1.ObjectMeta{
			Name:      req.DeploymentName + "-pdb",
			Namespace: req.Namespace,
			Labels: map[string]string{
				"app": req.DeploymentName,
			},
		},
		Spec: policyv1.PodDisruptionBudgetSpec{
			MinAvailable: func() *intstr.IntOrString {
				v := intstr.FromInt32(minAvailable)
				return &v
			}(),
			Selector: &metav1.LabelSelector{
				MatchLabels: map[string]string{
					"app": req.DeploymentName,
				},
			},
		},
	}
	_, err := clientset.PolicyV1().
		PodDisruptionBudgets(req.Namespace).Create(context.Background(), pdb, metav1.CreateOptions{})
	if err != nil {
		return fmt.Errorf("create pdb failed: %v", err)
	}

	return nil
}
