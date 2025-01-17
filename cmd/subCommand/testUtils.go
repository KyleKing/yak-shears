package subCommand

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/leaanthony/clir"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func initCli() *clir.Cli {
	return clir.NewCli("_", "test cli", "v0.0.1")
}

// Empty the subdirectory used for testing
func resetTmpTestDir(t *testing.T, subfolder string) string {
	tmpTestSubDir := filepath.Join("tmpTestData", subfolder)

	err := os.RemoveAll(tmpTestSubDir)
	require.NoError(t, err)

	err = os.Mkdir(tmpTestSubDir, os.ModePerm)
	require.NoError(t, err)

	fullpath, err := filepath.Abs(tmpTestSubDir)
	require.NoError(t, err)
	return fullpath
}

// Look for exactly one file that matches the prefix
func matchCreatedFile(testDir string, prefix string, t *testing.T) {
	matchedPaths := []string{}
	validateFiles := func(path string, fileInfo os.FileInfo, inpErr error) error {
		stat, err := os.Stat(path)
		if err != nil {
			return err
		}

		if strings.HasPrefix(filepath.Base(path), prefix) {
			matchedPaths = append(matchedPaths, path)
		} else if stat.Mode().IsRegular() {
			return fmt.Errorf("At least one unrecognized file when attempting to match (%s): %s (matchedPaths=%v)", prefix, path, matchedPaths)
		}

		return nil
	}

	err := filepath.Walk(testDir, validateFiles)
	require.NoError(t, err)
	assert.Equal(t, 1, len(matchedPaths), matchedPaths)
}
