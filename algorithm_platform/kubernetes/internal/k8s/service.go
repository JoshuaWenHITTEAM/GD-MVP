package k8s

import (
	"context"
	"fmt"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/util/intstr"
	"k8s.io/client-go/kubernetes"

	"algo-container-manager/internal/model"
)

func CreateService(clientset *kubernetes.Clientset, req model.StartAlgorithmRequest) error {
	serviceName := req.ServiceName
	if req.ServiceName == "" {
		return fmt.Errorf("service name is required")
	}

	selector := map[string]string{
		"app": req.DeploymentName,
	}

	service := &corev1.Service{
		ObjectMeta: metav1.ObjectMeta{
			Name:      serviceName,
			Namespace: req.Namespace,
			Labels:    selector,
		},
		Spec: corev1.ServiceSpec{
			Selector: selector,
			Type:     corev1.ServiceTypeClusterIP,
			Ports: []corev1.ServicePort{
				{
					Port:       req.Port,
					TargetPort: intstr.FromInt32(req.Port),
					Protocol:   corev1.ProtocolTCP,
				},
			},
		},
	}

	_, err := clientset.CoreV1().
		Services(req.Namespace).
		Create(context.Background(), service, metav1.CreateOptions{})

	if err != nil {
		return fmt.Errorf("create service failed: %w", err)
	}
	return nil
}
