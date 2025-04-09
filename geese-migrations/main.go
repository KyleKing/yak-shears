package main

import (
	"database/sql"
	"fmt"
	"io/ioutil"
	"log"
	"sort"
	"strings"

	_ "github.com/marcboeker/go-duckdb" // DuckDB driver
	_ "github.com/mattn/go-sqlite3"     // SQLite driver
)

func main() {
	// Example usage
	dirPath := "./migrations"
	dbType := "sqlite" // or "duckdb"
	dsn := "example.db"

	err := processMigrations(dirPath, dbType, dsn)
	if err != nil {
		log.Fatalf("Error processing migrations: %v", err)
	}

	err = processDowngrades(dirPath, dbType, dsn)
	if err != nil {
		log.Fatalf("Error processing downgrades: %v", err)
	}
}

func processSQL(dirPath, dbType, dsn string, extractSQL func(string) (string, error), reverseOrder bool) error {
	// Open database connection
	db, err := sql.Open(dbType, dsn)
	if err != nil {
		return fmt.Errorf("failed to open database: %w", err)
	}
	defer db.Close()

	// Read and sort filenames
	files, err := ioutil.ReadDir(dirPath)
	if err != nil {
		return fmt.Errorf("failed to read directory: %w", err)
	}

	var filenames []string
	for _, file := range files {
		if !file.IsDir() {
			filenames = append(filenames, file.Name())
		}
	}

	if reverseOrder {
		sort.Sort(sort.Reverse(sort.StringSlice(filenames)))
	} else {
		sort.Strings(filenames)
	}

	// Process each file
	for _, filename := range filenames {
		filePath := fmt.Sprintf("%s/%s", dirPath, filename)
		content, err := ioutil.ReadFile(filePath)
		if err != nil {
			return fmt.Errorf("failed to read file %s: %w", filename, err)
		}

		sqlContent, err := extractSQL(string(content))
		if err != nil {
			return fmt.Errorf("failed to extract SQL from %s: %w", filename, err)
		}

		err = executeTransaction(db, sqlContent, filename, string(content))
		if err != nil {
			return fmt.Errorf("failed to execute transaction for %s: %w", filename, err)
		}
	}

	return nil
}

func processMigrations(dirPath, dbType, dsn string) error {
	return processSQL(dirPath, dbType, dsn, extractUpgradeSQL, false)
}

func processDowngrades(dirPath, dbType, dsn string) error {
	return processSQL(dirPath, dbType, dsn, extractDowngradeSQL, true)
}

func extractUpgradeSQL(content string) (string, error) {
	startMarker := "-- +geese up"
	endMarker := "-- +geese down"

	startIdx := strings.Index(content, startMarker)
	endIdx := strings.Index(content, endMarker)

	if startIdx == -1 || endIdx == -1 || startIdx >= endIdx {
		return "", fmt.Errorf("invalid markers")
	}

	return strings.TrimSpace(content[startIdx+len(startMarker) : endIdx]), nil
}

func extractDowngradeSQL(content string) (string, error) {
	startMarker := "-- +geese down"
	endMarker := "-- +geese up"

	startIdx := strings.Index(content, startMarker)
	if startIdx == -1 {
		return "", fmt.Errorf("missing downgrade marker")
	}

	endIdx := len(content)
	if nextUpIdx := strings.Index(content[startIdx:], endMarker); nextUpIdx != -1 {
		endIdx = startIdx + nextUpIdx
	}

	return strings.TrimSpace(content[startIdx+len(startMarker) : endIdx]), nil
}

func executeTransaction(db *sql.DB, upgradeSQL, filename, content string) error {
	tx, err := db.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}

	_, err = tx.Exec(upgradeSQL)
	if err != nil {
		tx.Rollback()
		return fmt.Errorf("failed to execute upgrade SQL: %w", err)
	}

	// Create geese table if it doesn't exist
	createTableSQL := `CREATE TABLE IF NOT EXISTS geese (
		migration_id INTEGER PRIMARY KEY,
		filename TEXT NOT NULL,
		content TEXT NOT NULL,
		modified_at TEXT NOT NULL
	)`
	_, err = tx.Exec(createTableSQL)
	if err != nil {
		tx.Rollback()
		return fmt.Errorf("failed to create geese table: %w", err)
	}
	// Insert metadata into the geese table
	insertSQL := `INSERT INTO geese (filename, content, modified_at) VALUES (?, ?, ?, ?)`
	_, err = tx.Exec(insertSQL, migrationId, filename, content, "2025-04-09")
	if err != nil {
		tx.Rollback()
		return fmt.Errorf("failed to insert metadata: %w", err)
	}

	return tx.Commit()
}
