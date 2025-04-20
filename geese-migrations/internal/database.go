package internal

import (
	"database/sql"
	"fmt"
	"path/filepath"
	"time"

	_ "embed" // Required for compiler

	_ "github.com/marcboeker/go-duckdb" // DuckDB driver
	_ "github.com/mattn/go-sqlite3"     // SQLite driver
)

var (
	//go:embed sql/initGeeseStmt.sql
	initGeeseStmt string
	//go:embed sql/insertGeeseStmt.sql
	insertGeeseStmt string
	//go:embed sql/selectLastGeeseMigrationIDStmt.sql
	selectLastGeeseMigrationIDStmt string
)

func OpenDB(dbType, dsn string) (*sql.DB, error) {
	if !filepath.IsAbs(dsn) {
		return nil, fmt.Errorf("dsn is not an absolute path: %s", dsn)
	}

	db, err := sql.Open(dbType, dsn)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	return db, nil
}

func InitGeeseTable(db *sql.DB) error {
	_, err := db.Exec(initGeeseStmt)
	if err != nil {
		return fmt.Errorf("failed to create geese table: %w", err)
	}

	return nil
}

func SelectLastGeeseMigrationID(db *sql.DB, namespace string) (int, error) {
	var lastMigrationID int

	err := db.QueryRow(selectLastGeeseMigrationIDStmt, namespace).Scan(&lastMigrationID)
	if err != nil {
		if err != sql.ErrNoRows {
			return 0, fmt.Errorf("failed to identify last migration_id: %w", err)
		}

		return 0, nil
	}

	return lastMigrationID, nil
}

func execMigration(db *sql.DB, namespace string, fileInfo MigrationFileInfo, isUpgrade bool) error {
	tx, err := db.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}

	var execSQL string
	if isUpgrade {
		execSQL = fileInfo.MigrationUp
	} else {
		execSQL = fileInfo.MigrationDown
	}

	_, err = tx.Exec(execSQL)
	if err != nil {
		if rollbackErr := tx.Rollback(); rollbackErr != nil {
			return fmt.Errorf(
				"failed to rollback transaction: %w after executing migration: %w",
				rollbackErr,
				err,
			)
		}

		return fmt.Errorf("failed to execute migration SQL: %w", err)
	}

	if isUpgrade {
		_, err = tx.Exec(
			insertGeeseStmt,
			fileInfo.Number,
			namespace,
			fileInfo.Filename,
			fileInfo.MigrationUp,
			fileInfo.MigrationDown,
			time.Now(),
		)
	} else {
		_, err = tx.Exec(
			"DELETE FROM geese_migrations WHERE migration_id = ? AND namespace = ?",
			fileInfo.Number,
			namespace,
		)
	}

	if err != nil {
		if rollbackErr := tx.Rollback(); rollbackErr != nil {
			return fmt.Errorf(
				"failed to rollback transaction: %w after modifying metadata: %w",
				rollbackErr,
				err,
			)
		}

		return fmt.Errorf("failed to modify metadata: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	return nil
}

func ExecMigrationUp(db *sql.DB, namespace string, fileInfo MigrationFileInfo) error {
	return execMigration(db, namespace, fileInfo, true)
}

func ExecMigrationDown(db *sql.DB, namespace string, fileInfo MigrationFileInfo) error {
	return execMigration(db, namespace, fileInfo, false)
}
