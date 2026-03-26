package db

import (
	"fmt"

	"gorm.io/driver/mysql"
	"gorm.io/gorm"

	"algo-container-manager/internal/model"
)

var DB *gorm.DB

type Config struct {
	Host     string
	Port     int
	User     string
	Password string
	DBName   string
}

func InitMySQL(cfg Config) error {
	dsn := fmt.Sprintf(
		"%s:%s@tcp(%s:%d)/%s?charset=utf8mb4&parseTime=True&loc=Local",
		cfg.User,
		cfg.Password,
		cfg.Host,
		cfg.Port,
		cfg.DBName,
	)

	db, err := gorm.Open(mysql.Open(dsn), &gorm.Config{})
	if err != nil {
		return fmt.Errorf("mysql connect err: %v", err)
	}
	if err := db.AutoMigrate(&model.DeployRecord{}); err != nil {
		return fmt.Errorf("mysql migrate err: %v", err)
	}

	DB = db
	return nil
}
