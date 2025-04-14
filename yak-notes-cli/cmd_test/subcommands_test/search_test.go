package subcommands_test

import (
	"path/filepath"
	"testing"

	"github.com/KyleKing/yak-shears/yak-notes-cli/cmd/subcommands"
	"github.com/stretchr/testify/require"
)

func TestAttachSearch(t *testing.T) {
	var err error

	tmpTestSubDir := resetTmpTestDir(t, "search")
	setYakShearsDir(t)

	cli := initTestCli()
	subcommands.AttachSearch(cli)
	err = cli.Run("search", "Are there matches to this?", "-sync-dir", filepath.Dir(tmpTestSubDir))
	require.NoError(t, err)
}
