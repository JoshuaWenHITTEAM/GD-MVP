package common

import (
	"sort"

	corev1 "k8s.io/api/core/v1"
)

// BuildEnvVars 为 Deployment 创建环境变量
func BuildEnvVars(envMap map[string]string) []corev1.EnvVar {
	if len(envMap) == 0 {
		return nil
	}

	keys := make([]string, 0, len(envMap))
	for k := range envMap {
		keys = append(keys, k)
	}
	sort.Strings(keys)

	envVars := make([]corev1.EnvVar, 0, len(keys))
	for _, k := range keys {
		envVars = append(envVars, corev1.EnvVar{
			Name:  k,
			Value: envMap[k],
		})
	}

	return envVars
}
