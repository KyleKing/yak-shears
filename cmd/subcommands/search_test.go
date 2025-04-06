package subcommands

import (
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/require"
)

func TestAttachSearch(t *testing.T) {
	var err error

	tmpTestSubDir := resetTmpTestDir(t, "search")

	// PLANNED: Consider testing against a seeded database
	// db, err := connectDB(filepath.Dir(tmpTestSubDir))
	// require.NoError(t, err)
	// defer db.Close()
	//
	// notes := []Note{
	// 	{sub_dir: "search", filename: "test1.dj", content: "Test content 1", modified_at: time.Now()},
	// 	{sub_dir: "search", filename: "test2.dj", content: "Test content 2", modified_at: time.Now()},
	// }
	// err = storeNotes(db, notes)
	// require.NoError(t, err)

	cli := initTestCli()
	AttachSearch(cli)
	err = cli.Run("search", "Are there matches to this?", "-sync-dir", filepath.Dir(tmpTestSubDir))
	require.NoError(t, err)
}
