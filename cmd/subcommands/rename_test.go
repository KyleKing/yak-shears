package subcommands

import (
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/require"
)

func TestAttachRename(t *testing.T) {
	var err error

	tmpTestSubDir := resetTmpTestDir(t, "rename")

	baseCTime, _, _ := strings.Cut(toTimeName(time.Now()), "T")
	pathSrc := filepath.Join(tmpTestSubDir, "test-note.ext")
	err = createFile(pathSrc)
	require.NoError(t, err)

	cli := initCli()
	AttachRename(cli)
	err = cli.Run("rename", pathSrc)
	require.NoError(t, err)

	matchCreatedFile(tmpTestSubDir, baseCTime, t)
}
