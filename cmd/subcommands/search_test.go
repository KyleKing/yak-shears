package subcommands

import (
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/require"
)

func TestAttachSearch(t *testing.T) {
	var err error

	tmpTestSubDir := resetTmpTestDir(t, "search")

	cli := initCli()
	AttachSearch(cli)
	err = cli.Run("search", "Are there matches to this?", "-sync-dir", filepath.Dir(tmpTestSubDir))
	require.NoError(t, err)
}
