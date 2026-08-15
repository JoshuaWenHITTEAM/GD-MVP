package main

import (
	"algo-container-manager/internal/api"
	"algo-container-manager/internal/db"
	"algo-container-manager/internal/k8s"
	"algo-container-manager/internal/service"
	"log"
	"os"
)

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func main() {

	//初始化MySQL
	err := db.InitMySQL(db.Config{
		Host:     envOr("MYSQL_HOST", "127.0.0.1"),
		Port:     3306,
		User:     envOr("MYSQL_USER", "appuser"),
		Password: os.Getenv("MYSQL_PASSWORD"),
		DBName:   envOr("MYSQL_DB", "algo_manager"),
	})
	if err != nil {
		log.Fatalf("database init err: %v", err)
	}
	clientset, err := k8s.NewClientSet()
	if err != nil {
		log.Fatalf("init k8s client failed: %v", err)
	}

	containerSvc := service.NewContainerService(clientset)
	handler := api.NewHandler(containerSvc)
	router := api.NewRouter(handler)

	if err := router.Run(":8080"); err != nil {
		log.Fatalf("start http server failed: %v", err)
	}
}
