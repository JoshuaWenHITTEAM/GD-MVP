// Package k8s package k8s 提供 Kubernetes 客户端的初始化工具
// 本文件负责读取kubeconfig并创建Kubernetes Clientset
// 用于后续操作 Pod、Deployment、Service等资源
package k8s

import (
	"os"
	"path/filepath"

	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/tools/clientcmd"
)

func NewClientSet() (*kubernetes.Clientset, error) {
	kubeconfig := filepath.Join(
		getHomeDir(),
		".kube",
		"config")
	config, err := clientcmd.BuildConfigFromFlags("", kubeconfig)
	if err != nil {
		return nil, err
	}
	return kubernetes.NewForConfig(config)
}

func getHomeDir() string {
	if h := os.Getenv("HOME"); h != "" {
		return h
	}
	return os.Getenv("USERPROFILE")
}
