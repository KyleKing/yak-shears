package internal

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

type MigrationFileInfo struct {
	Number        int
	Filename      string
	Path          string
	MigrationUp   string
	MigrationDown string
}

func ExtractSQL(content string) (string, string, error) {
	startMarker := "-- +geese up"
	endMarker := "-- +geese down"

	idxUp := strings.Index(content, startMarker)
	idxDown := strings.Index(content, endMarker)
	idxEnd := len(content)

	if idxUp == -1 || idxDown == -1 || idxUp >= idxDown {
		return "", "", fmt.Errorf("invalid markers ([%d, %d]) in %s", idxUp, idxDown, content)
	}

	sqlUp := strings.TrimSpace(content[idxUp+len(startMarker) : idxDown])
	sqlDown := strings.TrimSpace(content[idxDown+len(endMarker) : idxEnd])

	return sqlUp, sqlDown, nil
}

func parseMigrationFile(filename, migrationDir string) (MigrationFileInfo, error) {
	re := regexp.MustCompile(`^(\d{3})_[^.]+\.sql$`)

	matches := re.FindStringSubmatch(filename)
	if len(matches) != 2 { // Includes full string
		return MigrationFileInfo{}, fmt.Errorf(
			"file `%q` did match the required format (%s)",
			filename,
			matches,
		)
	}

	number, err := strconv.Atoi(matches[1])
	if err != nil {
		return MigrationFileInfo{}, fmt.Errorf("invalid number in filename: %w", err)
	}

	path := filepath.Join(migrationDir, filename)

	content, err := os.ReadFile(path)
	if err != nil {
		return MigrationFileInfo{}, fmt.Errorf("failed to read file %s: %w", filename, err)
	}

	sqlUp, sqlDown, err := ExtractSQL(string(content))
	if err != nil {
		return MigrationFileInfo{}, fmt.Errorf("failed to extract SQL from %s: %w", filename, err)
	}

	return MigrationFileInfo{
		Number: number, Filename: filename, Path: path, MigrationUp: sqlUp, MigrationDown: sqlDown,
	}, nil
}

func ReadMigrationDir(migrationDir string) ([]MigrationFileInfo, int, error) {
	if !filepath.IsAbs(migrationDir) {
		return nil, 0, fmt.Errorf("migrationDir is not an absolute path: %s", migrationDir)
	}

	files, err := os.ReadDir(migrationDir)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to read migration directory: %w", err)
	}

	var migrationFiles []MigrationFileInfo

	for _, file := range files {
		if !file.IsDir() {
			migrationFileInfo, err := parseMigrationFile(file.Name(), migrationDir)
			if err != nil {
				return nil, 0, fmt.Errorf("failed to parse migration file: %w", err)
			}

			migrationFiles = append(migrationFiles, migrationFileInfo)
		}
	}

	highestID := 0

	if len(migrationFiles) > 0 {
		sort.Slice(migrationFiles, func(i, j int) bool {
			return migrationFiles[i].Number < migrationFiles[j].Number
		})

		highestID = migrationFiles[len(migrationFiles)-1].Number
	}

	return migrationFiles, highestID, nil
}
