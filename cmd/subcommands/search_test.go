package subcommands

import (
	"testing"

	"github.com/stretchr/testify/require"
)

func TestAttachSearch(t *testing.T) {
	var err error

	// tmpTestSubDir := resetTmpTestDir(t, "search")

	cli := initCli()
	AttachSearch(cli)
	err = cli.Run("search", "Are there matches to this?")
	require.NoError(t, err)
}
