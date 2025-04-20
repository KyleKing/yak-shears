package library

import (
	"errors"

	"github.com/KyleKing/yak-shears/geese-migrations/internal"
)

// Automatically run whenever the local migrations are ahead of the database
func AutoUpgrade(namespace, dirPath, dbType, dsn string) error {
	//nolint:wrapcheck
	return internal.AutoUpgrade(namespace, dirPath, dbType, dsn)
}

// For data integrity, only allow destructive downgrades to be run on demand
// Setting newLatestMigrationID to 0 will completely roll back the database
func MigrateToRevision(namespace, dirPath, dbType, dsn string, newLatestMigrationID int) error {
	return errors.New("not yet implemented")
}
