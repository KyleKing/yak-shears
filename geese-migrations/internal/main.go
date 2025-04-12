package internal

import (
	"fmt"
	"io/ioutil"
	"regexp"
	"sort"
	"strconv"
)

type MigrationFileInfo struct {
	Number int
	Name   string
}

func parseMigrationFile(filename string) (MigrationFileInfo, error) {
	re := regexp.MustCompile(`^(\d{3})_([^.]+)\.sql$`)
	matches := re.FindStringSubmatch(filename)
	if len(matches) != 2 {
		err := fmt.Errorf("file '%q' did match the required format", filename)
		return MigrationFileInfo{}, err
	}

	number, err := strconv.Atoi(matches[1])
	if err != nil {
		return MigrationFileInfo{}, fmt.Errorf("invalid number in filename: %w", err)
	}

	return MigrationFileInfo{Number: number, Name: matches[2]}, nil
}

func ReadMigrationDir(migrationDir string) ([]string, error) {
	files, err := ioutil.ReadDir(migrationDir)
	if err != nil {
		return nil, fmt.Errorf("failed to read migration directory: %w", err)
	}
	var filenames []string
	for _, file := range files {
		if !file.IsDir() {
			filenames = append(filenames, file.Name())
		}
	}
	return filenames, nil
}

func sortMigrations(migrations []MigrationFileInfo) {
	// PLANNED: See if reverse can be applied after?
	// 	sort.Sort(sort.Reverse(
	sort.Slice(migrations, func(i, j int) bool { return migrations[i].Number < migrations[j].Number })
}
