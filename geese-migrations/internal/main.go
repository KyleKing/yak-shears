package internal

import (
	"fmt"
)

// FIXME: Implement downgrade migrations; shares read+open, but different for loop and doesn't need to init Geese table
func AutoUpgrade(namespace, dirPath, dbType, dsn string) error {
	migrationFiles, err := ReadMigrationDir(dirPath)
	if err != nil {
		return fmt.Errorf("failed to read directory: %w", err)
	}

	db, err := OpenDB(dbType, dsn)
	if err != nil {
		return fmt.Errorf("failed to open database: %w", err)
	}
	defer db.Close()

	if err = InitGeeseTable(db); err != nil {
		return fmt.Errorf("failed to initialize geese table: %w", err)
	}

	for _, fileInfo := range migrationFiles {
		err = ExecMigrationUp(db, namespace, fileInfo)
		if err != nil {
			return fmt.Errorf("failed to execute transaction for %s: %w", fileInfo.Path, err)
		}
	}

	return nil
}
