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
		return "", fmt.Errorf("error with specified file (`%s`): %w", path, err)
	}

	return ToTimeName(t.BirthTime()), nil
}

func renameFile(path, cTime string) error {
	basename, _, _ := strings.Cut(filepath.Base(path), ".")

	newPath := strings.ReplaceAll(path, basename, cTime)
	if err := os.Rename(path, newPath); err != nil {
		return fmt.Errorf("failed to rename file from %s to %s: %w", path, newPath, err)
	}

	return nil
}

type RenameFlags struct {
	Path string `description:"Path to the file" pos:"1"`
}

func renameAction(flags *RenameFlags) (err error) {
	cTime, err := readCreationTime(flags.Path)
	if err != nil {
		return
	}

	err = renameFile(flags.Path, cTime)
	if err != nil {
		return fmt.Errorf("failed to rename file: %w", err)
	}

	fmt.Printf("Renamed %s with time %v\n", flags.Path, cTime)

	return
}

func AttachRename(cli *clir.Cli) {
	cli.NewSubCommandFunction(
		"rename",
		"Rename specified file based on creation date",
		renameAction,
	)
}
