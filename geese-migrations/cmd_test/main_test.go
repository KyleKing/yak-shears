package cmd_test

import (
	"database/sql"
	"os"
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

	// Create migrations directory and test file
	dirPath := "./test_migrations"
	os.Mkdir(dirPath, 0755)
	defer os.RemoveAll(dirPath)

	migrationFile := dirPath + "/001_init.sql"
	content := `-- +geese up
CREATE TABLE note (
    sub_dir VARCHAR NOT NULL,
    filename VARCHAR NOT NULL UNIQUE PRIMARY KEY,
    content VARCHAR NOT NULL,
    modified_at DATE NOT NULL
);
-- +geese down
DROP TABLE IF EXISTS note;`
	os.WriteFile(migrationFile, []byte(content), 0644)

	// Run processMigrations
	err = cmd.ProcessMigrations(dirPath, "sqlite3", dbFile)
	if err != nil {
		t.Fatalf("processMigrations failed: %v", err)
	}

	// Verify the table and data
	row := db.QueryRow("SELECT filename, content FROM note WHERE filename = ?", "001_init.sql")
	var filename, fileContent string
	err = row.Scan(&filename, &fileContent)
	if err != nil {
		t.Fatalf("Failed to query note table: %v", err)
	}

	if filename != "001_init.sql" || fileContent != content {
		t.Errorf("Unexpected data in note table: got (%s, %s), want (%s, %s)", filename, fileContent, "001_init.sql", content)
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
		t.Errorf("extractUpmain.gradeSQL returned unexpected result: got %s, want %s", result, expected)
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

	// Create migrations directory and test file
	dirPath := "./test_migrations_downgrade"
	os.Mkdir(dirPath, 0755)
	defer os.RemoveAll(dirPath)

	migrationFile := dirPath + "/001_init.sql"
	content := `-- +geese up
CREATE TABLE note (
    sub_dir VARCHAR NOT NULL,
    filename VARCHAR NOT NULL UNIQUE PRIMARY KEY,
    content VARCHAR NOT NULL,
    modified_at DATE NOT NULL
);
-- +geese down
DROP TABLE IF EXISTS note;`
	os.WriteFile(migrationFile, []byte(content), 0644)

	// Run processMigrations
	err = cmd.ProcessMigrations(dirPath, "sqlite3", dbFile)
	if err != nil {
		t.Fatalf("processMigrations failed: %v", err)
	}

	// Verify the table exists
	_, err = db.Exec("INSERT INTO note (sub_dir, filename, content, modified_at) VALUES (?, ?, ?, ?)", "migrations", "001_init.sql", content, "2025-04-09")
	if err != nil {
		t.Fatalf("Failed to insert into note table: %v", err)
	}

	// Run processDowngrades
	err = cmd.ProcessDowngrades(dirPath, "sqlite3", dbFile)
	if err != nil {
		t.Fatalf("processDowngrades failed: %v", err)
	}

	// Verify the table is dropped
	_, err = db.Exec("SELECT * FROM note")
	if err == nil {
		t.Fatalf("Expected error querying dropped table, but got none")
	}
}
