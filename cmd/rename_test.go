package cmd

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestAttachRename(t *testing.T) {
	baseCTime, _, _ := strings.Cut(currentCreationTime(), ":")
	baseCTime = baseCTime + ":"
	tempTestSubDir := filepath.Join("tmpTestData", "rename")
	os.RemoveAll(tempTestSubDir)
	os.Mkdir(tempTestSubDir, os.ModePerm)
	pathSrc := filepath.Join(tempTestSubDir, "test note.ext")

	file, err := os.Create(pathSrc)
	defer file.Close()
	require.NoError(t, err)

	err = Main().Run("rename", "-path", pathSrc)
	require.NoError(t, err)

	matchedPaths := []string{}
	validateFiles := func(path string, fileInfo os.FileInfo, inpErr error) error {
		if strings.HasPrefix(filepath.Base(path), baseCTime) {
			matchedPaths = append(matchedPaths, path)
			os.Remove(path)
		} else if strings.HasSuffix(path, ".ext") {
			return fmt.Errorf("At least one unrecognized file when attempting to match (%s): %s (matchedPaths=%v)", baseCTime, path, matchedPaths)
		}
		return nil
	}
	err = filepath.Walk(tempTestSubDir, validateFiles)
	require.NoError(t, err)
	assert.Equal(t, 1, len(matchedPaths), matchedPaths)
}
