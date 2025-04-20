package internal

import (
	"database/sql"
	"fmt"
)

func applyMigrationsUp(
	db *sql.DB,
	namespace string,
	migrationFiles []MigrationFileInfo,
	lastMigrationID, targetRevision int,
) error {
	for _, fileInfo := range migrationFiles {
		if fileInfo.Number > lastMigrationID && fileInfo.Number <= targetRevision {
			err := ExecMigrationUp(db, namespace, fileInfo)
			if err != nil {
				return fmt.Errorf("failed to execute transaction for %s: %w", fileInfo.Path, err)
			}
		}
	}

	return nil
}

func applyMigrationsDown(
	db *sql.DB,
	namespace string,
	migrationFiles []MigrationFileInfo,
	lastMigrationID, targetRevision int,
) error {
	for i := len(migrationFiles) - 1; i >= 0; i-- {
		fileInfo := migrationFiles[i]
		if fileInfo.Number <= lastMigrationID && fileInfo.Number > targetRevision {
			err := ExecMigrationDown(db, namespace, fileInfo)
			if err != nil {
				return fmt.Errorf("failed to execute transaction for %s: %w", fileInfo.Path, err)
			}
		}
	}

	return nil
}

func MigrateToRevision(namespace, dirPath, dbType, dsn string, targetRevision int) error {
	migrationFiles, _, err := ReadMigrationDir(dirPath)
	if err != nil {
		return fmt.Errorf("failed to read directory: %w", err)
	}

	db, err := OpenDB(dbType, dsn)
	if err != nil {
		return err
	}
	defer db.Close()

	if err = InitGeeseTable(db); err != nil {
		return err
	}

	lastMigrationID, err := SelectLastGeeseMigrationID(db, namespace)
	if err != nil {
		return err
	}

	if targetRevision > lastMigrationID {
		if err = applyMigrationsUp(db, namespace, migrationFiles, lastMigrationID, targetRevision); err != nil {
			return err
		}
	} else if targetRevision < lastMigrationID {
		if err = applyMigrationsDown(db, namespace, migrationFiles, lastMigrationID, targetRevision); err != nil {
			return err
		}
	}

	return nil
}

func AutoUpgrade(namespace, dirPath, dbType, dsn string) error {
	_, highestID, err := ReadMigrationDir(dirPath)
	if err != nil {
		return fmt.Errorf("failed to read directory: %w", err)
	}

	return MigrateToRevision(namespace, dirPath, dbType, dsn, highestID)
}

func AutoDowngrade(namespace, dirPath, dbType, dsn string) error {
	return MigrateToRevision(namespace, dirPath, dbType, dsn, 0)
}
