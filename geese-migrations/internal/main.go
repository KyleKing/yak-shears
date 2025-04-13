package internal

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
)

type MigrationFileInfo struct {
	Number   int
	Filename string
}

func parseMigrationFile(filename string) (MigrationFileInfo, error) {
	re := regexp.MustCompile(`^(\d{3})_[^.]+\.sql$`)
	matches := re.FindStringSubmatch(filename)
	if len(matches) != 2 { // Includes full string
		err := fmt.Errorf("file `%q` did match the required format (%s)", filename, matches)
		return MigrationFileInfo{}, err
	}

	number, err := strconv.Atoi(matches[1])
	if err != nil {
		return MigrationFileInfo{}, fmt.Errorf("invalid number in filename: %w", err)
	}

	return MigrationFileInfo{Number: number, Filename: filename}, nil
}

func ReadMigrationDir(migrationDir string) ([]MigrationFileInfo, error) {
	if !filepath.IsAbs(migrationDir) {
		return nil, fmt.Errorf("migrationDir is not an absolute path: %s", migrationDir)
	}

	files, err := os.ReadDir(migrationDir)
	if err != nil {
		return nil, fmt.Errorf("failed to read migration directory: %w", err)
	}
	var MigrationFiles []MigrationFileInfo
	for _, file := range files {
		if !file.IsDir() {
			migrationFileInfo, err := parseMigrationFile(file.Name())
			if err != nil {
				return nil, fmt.Errorf("failed to parse migration file: %w", err)
			}
			MigrationFiles = append(MigrationFiles, migrationFileInfo)
		}
	}
	return MigrationFiles, nil
}

// func sortMigrations(migrations []MigrationFileInfo) {
// 	// PLANNED: See if reverse can be applied after?
// 	// 	sort.Sort(sort.Reverse(
// 	sort.Slice(migrations, func(i, j int) bool { return migrations[i].Number < migrations[j].Number })
// }
