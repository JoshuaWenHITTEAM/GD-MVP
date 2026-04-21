package k8s

import (
	"context"
	"fmt"
	"time"

	appsv1 "k8s.io/api/apps/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
)

func UpdateDeploymentImage(
	ctx context.Context,
	clientset *kubernetes.Clientset,
	namespace string,
	deploymentName string,
	newImage string,
) (*appsv1.Deployment, error) {
	deploy, err := clientset.AppsV1().
		Deployments(namespace).
		Get(ctx, deploymentName, metav1.GetOptions{})
	if err != nil {
		return nil, fmt.Errorf("get deployment failed: %w", err)
	}

	if len(deploy.Spec.Template.Spec.Containers) == 0 {
		return nil, fmt.Errorf("deployment %s has no containers", deploymentName)
	}

	deploy.Spec.Template.Spec.Containers[0].Image = newImage

	if deploy.Spec.Template.Annotations == nil {
		deploy.Spec.Template.Annotations = map[string]string{}
	}
	deploy.Spec.Template.Annotations["algo-platform/updated-at"] = time.Now().Format(time.RFC3339)

	updated, err := clientset.AppsV1().
		Deployments(namespace).
		Update(ctx, deploy, metav1.UpdateOptions{})
	if err != nil {
		return nil, fmt.Errorf("update deployment image failed: %w", err)
	}

	return updated, nil
}
