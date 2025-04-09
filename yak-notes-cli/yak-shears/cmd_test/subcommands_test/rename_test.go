package subcommands_test

import (
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/KyleKing/yak-shears/cmd/subcommands"
	"github.com/stretchr/testify/require"
)

func TestAttachRename(t *testing.T) {
	var err error

	tmpTestSubDir := resetTmpTestDir(t, "rename")

	baseCTime, _, _ := strings.Cut(subcommands.ToTimeName(time.Now()), "T")
	pathSrc := filepath.Join(tmpTestSubDir, "test-note.ext")
	err = subcommands.CreateFile(pathSrc)
	require.NoError(t, err)

	cli := initTestCli()
	subcommands.AttachRename(cli)
	err = cli.Run("rename", pathSrc)
	require.NoError(t, err)

	matchCreatedFile(tmpTestSubDir, baseCTime, t)
}
