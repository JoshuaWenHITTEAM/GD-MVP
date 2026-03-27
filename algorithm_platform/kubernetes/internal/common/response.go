package common

import (
	"net/http"

	"github.com/gin-gonic/gin"
)

func Success(c *gin.Context, data interface{}) {
	c.JSON(http.StatusOK, gin.H{
		"code":    0,
		"message": "success",
		"data":    data,
	})
}

func Fail(c *gin.Context, httpCode int, msg string) {
	c.JSON(http.StatusOK, gin.H{
		"code":    httpCode,
		"message": msg,
	})
}
