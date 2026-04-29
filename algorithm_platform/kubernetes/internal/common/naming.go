package common

import (
	"fmt"
	"regexp"
	"strings"
)

// 规范化K8s名称
func sanitizeName(name string) string {
	name = strings.ToLower(name)

	reg := regexp.MustCompile(`[^a-z0-9-]`)
	name = reg.ReplaceAllString(name, "-")

	name = strings.Trim(name, "-")

	return name
}

// BuildDeploymentName 构建Deployment名称
func BuildDeploymentName(name string, version string, uuid string) string {
	name = sanitizeName(name)
	version = sanitizeName(version)
	shortUID := uuid[:8]

	var result string
	if version == "" {
		result = fmt.Sprintf("algo-%s-%s", name, shortUID)
	} else {
		result = fmt.Sprintf("algo-%s-%s-%s", name, version, shortUID)
	}

	if len(result) > 63 {
		result = result[:63]
	}

	return result
}

// BuildServiceName 构建Service名称
func BuildServiceName(deploymentName string) string {
	name := deploymentName + "-svc"

	if len(name) > 63 {
		name = name[:63]
	}
	return name
}
