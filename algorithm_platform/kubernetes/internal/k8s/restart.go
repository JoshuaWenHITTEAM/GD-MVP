package k8s

import (
	"context"
	"time"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
)

func RestartDeployment(clientset *kubernetes.Clientset, namespace string, name string) error {
	deploy, err := clientset.AppsV1().Deployments(namespace).Get(context.Background(), name, metav1.GetOptions{})
	if err != nil {
		return err
	}

	if deploy.Spec.Template.ObjectMeta.Annotations == nil {
		deploy.Spec.Template.ObjectMeta.Annotations = map[string]string{}
	}

	deploy.Spec.Template.ObjectMeta.Annotations["kubectl.kubernetes.io/restartedAt"] = time.Now().Format(time.RFC3339)
	_, err = clientset.AppsV1().
		Deployments(namespace).
		Update(context.Background(), deploy, metav1.UpdateOptions{})

	return err
}
