package config

import (
	"log"
	"os"
	"path/filepath"
)

func GetSyncDir() string {
	home, err := os.UserHomeDir()
	if err != nil {
		log.Fatal(err)
	}
	return filepath.Join(home, "Sync")
}
