package internal

import (
	_ "embed" // Required for compiler

	"database/sql"
	"fmt"
	"path/filepath"
	"time"

	_ "github.com/marcboeker/go-duckdb" // DuckDB driver
	_ "github.com/mattn/go-sqlite3"     // SQLite driver
)

var (
	//go:embed sql/initGeeseStmt.sql
	initGeeseStmt string
	//go:embed sql/insertGeeseStmt.sql
	insertGeeseStmt string
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

func ExecMigrationUp(db *sql.DB, namespace string, fileInfo MigrationFileInfo) error {
	tx, err := db.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}

	_, err = tx.Exec(fileInfo.MigrationUp)
	if err != nil {
		if rollbackErr := tx.Rollback(); rollbackErr != nil {
			return fmt.Errorf(
				"failed to rollback transaction: %w after upgrade: %w",
				rollbackErr,
				err,
			)
		}

		return fmt.Errorf("failed to execute upgrade SQL: %w", err)
	}

	_, err = tx.Exec(
		insertGeeseStmt,
		fileInfo.Number,
		namespace,
		fileInfo.Filename,
		fileInfo.MigrationUp,
		fileInfo.MigrationDown,
		time.Now(),
	)
	if err != nil {
		if rollbackErr := tx.Rollback(); rollbackErr != nil {
			return fmt.Errorf(
				"failed to rollback transaction: %w after inserting metadata: %w",
				rollbackErr,
				err,
			)
		}

		return fmt.Errorf("failed to insert metadata: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	return nil
}
