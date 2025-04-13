package cmd_test

import (
	"database/sql"
	"os"
	"path/filepath"
	"testing"

	"github.com/KyleKing/yak-shears/geese-migrations/cmd"

	_ "github.com/mattn/go-sqlite3" // SQLite driver
)

func TestProcessMigrations(t *testing.T) {
	// Setup temporary database file
	dbFile := "test.db"
	defer os.Remove(dbFile)

	db, err := sql.Open("sqlite3", dbFile)
	if err != nil {
		t.Fatalf("Failed to open test database: %v", err)
	}
	defer db.Close()

	cwd, err := os.Getwd()
	if err != nil {
		t.Fatalf("could not get cwd: %v", err)
	}
	dirPath := filepath.Join(cwd, "test_migrations")

	// Run processMigrations
	err = cmd.ProcessMigrations(dirPath, "sqlite3", dbFile)
	if err != nil {
		t.Fatalf("processMigrations failed: %v", err)
	}

	// Verify the table exists
	insertedFilename := "test.md"
	_, err = db.Exec("INSERT INTO note (sub_dir, filename, content, modified_at) VALUES (?, ?, ?, ?)", "migrations", insertedFilename, "...content...", "2025-04-09")
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

func TestExtractUpgradeSQL(t *testing.T) {
	content := `-- +geese up
CREATE TABLE test (id INT);
-- +geese down
DROP TABLE test;`

	expected := "CREATE TABLE test (id INT);"
	result, err := cmd.ExtractUpgradeSQL(content)
	if err != nil {
		t.Fatalf("extractUpgradeSQL failed: %v", err)
	}

	if result != expected {
		t.Errorf("extractUpgradeSQL returned unexpected result: got %s, want %s", result, expected)
	}
}

func TestProcessDowngrades(t *testing.T) {
	// Setup temporary database file
	dbFile := "test_downgrade.db"
	defer os.Remove(dbFile)

	db, err := sql.Open("sqlite3", dbFile)
	if err != nil {
		t.Fatalf("Failed to open test database: %v", err)
	}
	defer db.Close()

	cwd, err := os.Getwd()
	if err != nil {
		t.Fatalf("could not get cwd: %v", err)
	}
	dirPath := filepath.Join(cwd, "test_migrations_downgrade")

	err = cmd.ProcessMigrations(dirPath, "sqlite3", dbFile)
	if err != nil {
		t.Fatalf("processMigrations failed: %v", err)
	}
	// Verify that the table exists
	_, err = db.Exec("SELECT * FROM note")
	if err != nil {
		t.Fatalf("unexpected error querying new table: %v", err)
	}

	err = cmd.ProcessDowngrades(dirPath, "sqlite3", dbFile)
	if err != nil {
		t.Fatalf("processDowngrades failed: %v", err)
	}
	// Verify the table is dropped by downgrade
	_, err = db.Exec("SELECT * FROM note")
	if err == nil {
		t.Fatalf("expected error querying dropped table, but got none")
	}
}
