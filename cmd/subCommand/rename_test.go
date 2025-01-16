package subCommand

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/leaanthony/clir"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestAttachRename(t *testing.T) {
	var err error

	tempTestSubDir := filepath.Join("tmpTestData", "rename")
	err = os.RemoveAll(tempTestSubDir)
	require.NoError(t, err)
	err = os.Mkdir(tempTestSubDir, os.ModePerm)
	require.NoError(t, err)

	baseCTime, _, _ := strings.Cut(toTimeName(time.Now()), ":")
	baseCTime = baseCTime + ":"
	pathSrc := filepath.Join(tempTestSubDir, "test note.ext")
	err = createFile(pathSrc)
	require.NoError(t, err)

	cli := clir.NewCli("_", "test cli", "v0.0.1")
	AttachRename(cli)
	err = cli.Run("rename", "-path", pathSrc)
	require.NoError(t, err)

	matchedPaths := []string{}
	validateFiles := func(path string, fileInfo os.FileInfo, inpErr error) error {
		if strings.HasPrefix(filepath.Base(path), baseCTime) {
			matchedPaths = append(matchedPaths, path)
		} else if strings.HasSuffix(path, ".ext") {
			return fmt.Errorf("At least one unrecognized file when attempting to match (%s): %s (matchedPaths=%v)", baseCTime, path, matchedPaths)
		}
		return nil
	}
	err = filepath.Walk(tempTestSubDir, validateFiles)
	require.NoError(t, err)
	assert.Equal(t, 1, len(matchedPaths), matchedPaths)
}
