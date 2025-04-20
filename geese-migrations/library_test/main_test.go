package library_test

import (
	"database/sql"
	"os"
	"path/filepath"
	"testing"

	"github.com/KyleKing/yak-shears/geese-migrations/library"

	_ "github.com/mattn/go-sqlite3" // SQLite driver
)

func TestAutoUpgrade(t *testing.T) {
	cwd, err := os.Getwd()
	if err != nil {
		t.Fatalf("could not get cwd: %v", err)
	}

	dbFile := filepath.Join(cwd, "test.db")
	defer os.Remove(dbFile)

	db, err := sql.Open("sqlite3", dbFile)
	if err != nil {
		t.Fatalf("Failed to open test database: %v", err)
	}
	defer db.Close()

	dirPath := filepath.Join(cwd, "test_migrations")

	// Run processMigrations
	err = library.AutoUpgrade("test", dirPath, "sqlite3", dbFile)
	if err != nil {
		t.Fatalf("processMigrations failed: %v", err)
	}

	// Verify the table exists
	insertedFilename := "test.md"

	_, err = db.Exec(
		"INSERT INTO note (sub_dir, filename, content, modified_at) VALUES (?, ?, ?, ?)",
		"migrations",
		insertedFilename,
		"...content...",
		"2025-04-09",
	)
	if err != nil {
		t.Fatalf("Failed to insert into note table: %v", err)
	}

	// Verify the table and data
	row := db.QueryRow("SELECT filename FROM note WHERE filename = ?", insertedFilename)

	var filename string

	err = row.Scan(&filename)
	if err != nil {
		t.Fatalf("Failed to query note table: %v", err)
	}

	if filename != insertedFilename {
		t.Errorf("Unexpected data in note table: got (%s) want (%s)", filename, insertedFilename)
	}
}

func TestProcessDowngrades(t *testing.T) {
	cwd, err := os.Getwd()
	if err != nil {
		t.Fatalf("could not get cwd: %v", err)
	}

	dbFile := filepath.Join(cwd, "test_downgrade.db")
	defer os.Remove(dbFile)

	db, err := sql.Open("sqlite3", dbFile)
	if err != nil {
		t.Fatalf("Failed to open test database: %v", err)
	}
	defer db.Close()

	dirPath := filepath.Join(cwd, "test_migrations_downgrade")

	err = library.AutoUpgrade("test", dirPath, "sqlite3", dbFile)
	if err != nil {
		t.Fatalf("processMigrations failed: %v", err)
	}
	// Verify that the table exists
	_, err = db.Exec("SELECT * FROM note")
	if err != nil {
		t.Fatalf("unexpected error querying new table: %v", err)
	}

	err = library.MigrateToRevision("test", dirPath, "sqlite3", dbFile, 0)
	if err != nil {
		t.Fatalf("Downgrade failed: %v", err)
	}

	// Verify the table is dropped by downgrade
	_, err = db.Exec("SELECT * FROM note")
	if err == nil {
		t.Fatalf("expected error querying dropped table, but got none")
	}
}
