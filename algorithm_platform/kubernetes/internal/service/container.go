package service

import "k8s.io/client-go/kubernetes"

type ContainerService struct {
	clientset *kubernetes.Clientset
}

func NewContainerService(clientset *kubernetes.Clientset) *ContainerService {
	return &ContainerService{clientset: clientset}
}
