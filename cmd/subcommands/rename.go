package subcommands

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/djherbis/times"
	"github.com/leaanthony/clir"
)

func readCreationTime(path string) (string, error) {
	t, err := times.Stat(path)
	if err != nil {
		return "", fmt.Errorf("Error with specified file (`%s`): %w", path, err)
	}
	return toTimeName(t.BirthTime()), nil
}

func renameFile(path, cTime string) error {
	basename, _, _ := strings.Cut(filepath.Base(path), ".")
	newPath := strings.ReplaceAll(path, basename, cTime)
	return os.Rename(path, newPath)
}

func AttachRename(cli *clir.Cli) {
	renameCmd := cli.NewSubCommand("rename", "Rename specified file based on creation date")
	// PLANNED: `path` should be a positional arg rather than flag
	var path string
	renameCmd.StringFlag("path", "Path to file", &path)
	renameCmd.Action(func() error {
		cTime, err := readCreationTime(path)
		if err == nil {
			renameFile(path, cTime)
			fmt.Printf("Renamed %s with time %v\n", path, cTime)
		}
		return err
	})
}
