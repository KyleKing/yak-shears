package subcommands

import (
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestTimeName(t *testing.T) {
	now := time.Now()
	name := toTimeName(now)

	restored, err := fromTimeName(name)

	require.NoError(t, err)
	assert.Equal(t, now.UTC().Format(time.RFC3339), restored.Format(time.RFC3339), name)
}

func TestAttachNew(t *testing.T) {
	var err error

	tmpTestSubDir := resetTmpTestDir(t, "new")

	baseCTime, _, _ := strings.Cut(toTimeName(time.Now()), "T")

	cli := initCli()
	AttachNew(cli)
	err = cli.Run("new", "-subfolder", "new", "-home", filepath.Dir(tmpTestSubDir))
	require.NoError(t, err)

	matchCreatedFile(tmpTestSubDir, baseCTime, t)
}
