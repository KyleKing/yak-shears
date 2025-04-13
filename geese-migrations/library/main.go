package library

import (
	"github.com/KyleKing/yak-shears/geese-migrations/internal"
)

// Automatically run whenever the local migrations are ahead of the database
func AutoUpgrade(namespace, dirPath, dbType, dsn string) error {
	//nolint:wrapcheck
	return internal.AutoUpgrade(namespace, dirPath, dbType, dsn)
}

// // For data integrity, only run on demand
// func Downgrade(newLatestMigrationID int) error {
// TODO: Needs to be implemetned
// }
