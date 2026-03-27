package k8s

import (
	"context"
	"io"

	corev1 "k8s.io/api/core/v1"
	"k8s.io/client-go/kubernetes"
)

func GetPodLogs(clientset *kubernetes.Clientset, namespace string, podName string, tailLines int64) (string, error) {
	req := clientset.CoreV1().Pods(namespace).GetLogs(podName, &corev1.PodLogOptions{
		TailLines: &tailLines,
	})

	stream, err := req.Stream(context.Background())
	if err != nil {
		return "", err
	}
	defer stream.Close()

	buf, err := io.ReadAll(stream)
	if err != nil {
		return "", err
	}
	return string(buf), nil
}
