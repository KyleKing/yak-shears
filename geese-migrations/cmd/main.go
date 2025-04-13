package cmd

import (
	"database/sql"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/KyleKing/yak-shears/geese-migrations/internal"

	_ "github.com/marcboeker/go-duckdb" // DuckDB driver
	_ "github.com/mattn/go-sqlite3"     // SQLite driver
)

func processSQL(dirPath, dbType, dsn string, extractSQL func(string) (string, error), _ bool) error { // Renamed reverseOrder to _
	// Open database connection
	db, err := sql.Open(dbType, dsn)
	if err != nil {
		return fmt.Errorf("failed to open database: %w", err)
	}
	defer db.Close()

	migrationFiles, err := internal.ReadMigrationDir(dirPath)
	if err != nil {
		return fmt.Errorf("failed to read directory: %w", err)
	}

	// Process each file
	for _, fileInfo := range migrationFiles {
		filename := fileInfo.Filename
		filePath := filepath.Join(dirPath, filename)
		content, err := os.ReadFile(filePath)
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

func ProcessMigrations(dirPath, dbType, dsn string) error {
	return processSQL(dirPath, dbType, dsn, ExtractUpgradeSQL, false)
}

func ProcessDowngrades(dirPath, dbType, dsn string) error {
	return processSQL(dirPath, dbType, dsn, ExtractDowngradeSQL, true)
}

func ExtractUpgradeSQL(content string) (string, error) {
	startMarker := "-- +geese up"
	endMarker := "-- +geese down"

	startIdx := strings.Index(content, startMarker)
	endIdx := strings.Index(content, endMarker)

	if startIdx == -1 || endIdx == -1 || startIdx >= endIdx {
		return "", errors.New("invalid markers")
	}

	return strings.TrimSpace(content[startIdx+len(startMarker) : endIdx]), nil
}

func ExtractDowngradeSQL(content string) (string, error) {
	startMarker := "-- +geese down"
	endMarker := "-- +geese up"

	startIdx := strings.Index(content, startMarker)
	if startIdx == -1 {
		return "", errors.New("missing downgrade marker")
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
		if rollbackErr := tx.Rollback(); rollbackErr != nil {
			return fmt.Errorf("failed to rollback transaction: %w after upgrade: %w", rollbackErr, err)
		}
		return fmt.Errorf("failed to execute upgrade SQL: %w", err)
	}

	// Create geese table if it doesn't exist
	// FIXME: PRIMARY KEY, <- Need to remove on rollback!
	createTableSQL := `CREATE TABLE IF NOT EXISTS geese (
		migration_id INTEGER,
		filename TEXT NOT NULL,
		content TEXT NOT NULL,
		modified_at TEXT NOT NULL
	)`
	_, err = tx.Exec(createTableSQL)
	if err != nil {
		if rollbackErr := tx.Rollback(); rollbackErr != nil {
			return fmt.Errorf("failed to rollback transaction: %w after creating geese table: %w", rollbackErr, err)
		}
		return fmt.Errorf("failed to create geese table: %w", err)
	}
	// Insert metadata into the geese table
	insertSQL := `INSERT INTO geese (migration_id, filename, content, modified_at) VALUES (?, ?, ?, ?)`
	migrationID := 1 // FIXME: replace with real id
	_, err = tx.Exec(insertSQL, migrationID, filename, content, "2025-04-09")
	if err != nil {
		if rollbackErr := tx.Rollback(); rollbackErr != nil {
			return fmt.Errorf("failed to rollback transaction: %w after inserting metadata: %w", rollbackErr, err)
		}
		return fmt.Errorf("failed to insert metadata: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}
	return nil
}

// func main() {
// 	// Example usage
// 	dirPath := "./migrations"
// 	dbType := "sqlite" // or "duckdb"
// 	dsn := "example.db"

// 	err := ProcessMigrations(dirPath, dbType, dsn)
// 	if err != nil {
// 		log.Fatalf("Error processing migrations: %v", err)
// 	}

// 	err = ProcessDowngrades(dirPath, dbType, dsn)
// 	if err != nil {
// 		log.Fatalf("Error processing downgrades: %v", err)
// 	}
// }
