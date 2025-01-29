package config

import (
	"log"
	"os"
	"path/filepath"
)

func GetSyncDir() string {
	if syncDir := os.Getenv("SHEARS_SYNC_DIR"); syncDir != "" {
		return syncDir
	}

	home, err := os.UserHomeDir()
	if err != nil {
		log.Fatal(err)
	}
	return filepath.Join(home, "Sync", "yak-shears")
}

func GetSubfolder() string {
	return os.Getenv("SHEARS_SUBFOLDER")
}
