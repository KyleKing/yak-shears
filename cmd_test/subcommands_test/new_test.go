package subcommands_test

import (
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/KyleKing/yak-shears/cmd/subcommands"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestTimeName(t *testing.T) {
	now := time.Now()
	name := subcommands.ToTimeName(now)

	restored, err := subcommands.FromTimeName(name)

	require.NoError(t, err)
	assert.Equal(t, now.UTC().Format(time.RFC3339), restored.Format(time.RFC3339), name)
}

func TestAttachNew(t *testing.T) {
	var err error

	tmpTestSubDir := resetTmpTestDir(t, "new")

	baseCTime, _, _ := strings.Cut(subcommands.ToTimeName(time.Now()), "T")

	cli := initTestCli()
	subcommands.AttachNew(cli)
	err = cli.Run("new", "-sync-dir", filepath.Dir(tmpTestSubDir), "-sub-dir", "new")
	require.NoError(t, err)

	matchCreatedFile(tmpTestSubDir, baseCTime, t)
}
