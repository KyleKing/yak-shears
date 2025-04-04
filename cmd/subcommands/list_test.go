package subcommands

import (
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/require"
)

func TestAttachList(t *testing.T) {
	var err error

	tmpTestSubDir := resetTmpTestDir(t, "list")

	cli := initTestCli()
	AttachList(cli)
	err = cli.Run("list", "-sync-dir", filepath.Dir(tmpTestSubDir))
	require.NoError(t, err)
}
