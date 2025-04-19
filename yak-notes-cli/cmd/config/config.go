package config

import (
	"os"
	"path/filepath"
)

func GetSyncDir() string {
	if syncDir := os.Getenv("SHEARS_SYNC_DIR"); syncDir != "" {
		return syncDir
	}

	home, err := os.UserHomeDir()
	if err != nil {
		panic(err)
	}

	return filepath.Join(home, "Sync", "yak-shears")
}

func GetSubDir() string {
	return os.Getenv("SHEARS_SUBDIR")
}
