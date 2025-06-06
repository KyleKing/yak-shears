package subcommands_test

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

func initTestCli() *clir.Cli {
	return clir.NewCli("_", "test cli", "v0.0.1")
}

// Sets environment variable for migrations
func setYakShearsDir(t *testing.T) {
	cwd, err := os.Getwd()
	if err != nil {
		t.Fatalf("could not get cwd: %v", err)
	}
	// Calculate parent directory of applet (e.g. ../../../<cwd>)
	os.Setenv("YAK_SHEARS_DIR", filepath.Dir(filepath.Dir(filepath.Dir(cwd))))
}

// Empty the subDir used for testing
func resetTmpTestDir(t *testing.T, subDir string) string {
	tmpTestSubDir := filepath.Join("tmpTestData", subDir)

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
	validateFiles := func(path string, _ os.FileInfo, _ error) error {
		stat, err := os.Stat(path)
		if err != nil {
			return fmt.Errorf("failed to get file info for %s: %w", path, err)
		}

		if strings.HasPrefix(filepath.Base(path), prefix) {
			matchedPaths = append(matchedPaths, path)
		} else if stat.Mode().IsRegular() {
			return fmt.Errorf("at least one unrecognized file when attempting to match (%s): %s (matchedPaths=%v)", prefix, path, matchedPaths)
		}

		return nil
	}

	err := filepath.Walk(testDir, validateFiles)
	require.NoError(t, err)
	assert.Len(t, matchedPaths, 1, "%+v", matchedPaths)
}
