package k8s

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"mime/multipart"
	"sort"
	"strings"
	"time"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
)

func ProxyMultipartToService(clientset *kubernetes.Clientset, namespace, serviceName, path, filename string, content []byte, fields map[string]string) ([]byte, error) {
	svc, err := clientset.CoreV1().Services(namespace).Get(context.Background(), serviceName, metav1.GetOptions{})
	if err != nil {
		return nil, fmt.Errorf("failed to fetch service %q: %v", serviceName, err)
	}
	if len(svc.Spec.Ports) == 0 {
		return nil, fmt.Errorf("service %q has no ports", serviceName)
	}

	body, contentType, err := buildMultipartBody(filename, content, strings.Fields)
	if err != nil {
		return nil, err
	}

	proxyPath := strings.Trim(path, "/")
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()

	raw, err := clientset.CoreV1().RESTClient().Post().
		Namespace(namespace).
		Resource("services").
		Name(serviceName).
		SubResource("proxy").
		Suffix(proxyPath).
		SetHeader("Content-Type", contentType).
		Body(body).
		DoRaw(ctx)
	if err == nil {
		return raw, nil
	}

	raw, err = clientset.CoreV1().RESTClient().Post().
		Namespace(namespace).
		Resource("services").
		Name(fmt.Sprintf("%s:%d", serviceName, svc.Spec.Ports[0].Port)).
		SubResource("proxy").
		Suffix(proxyPath).
		SetHeader("Content-Type", contentType).
		Body(body).
		DoRaw(ctx)
	if err != nil {
		return nil, fmt.Errorf("proxy infer request failed: %w", err)
	}

	return raw, nil
}

func buildMultipartBody(filename string, content []byte, fields map[string]string) ([]byte, string, error) {
	var buf bytes.Buffer
	writer := multipart.NewWriter(&buf)

	part, err := writer.CreateFormFile("file", filename)
	if err != nil {
		return nil, "", fmt.Errorf("failed to create form file: %w", err)
	}
	if _, err := part.Write(content); err != nil {
		return nil, "", fmt.Errorf("failed to write content: %w", err)
	}

	keys := make([]string, 0, len(fields))
	for k := range fields {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		if err := writer.WriteField(k, fields[k]); err != nil {
			return nil, "", fmt.Errorf("failed to write field: %w", err)
		}
	}

	if err := writer.Close(); err != nil {
		return nil, "", fmt.Errorf(" failed to close multipart writer: %w", err)
	}

	return buf.Bytes(), writer.FormDataContentType(), nil
}
