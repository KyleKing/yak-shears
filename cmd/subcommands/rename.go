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

type RenameFlags struct {
	Path string `description:"Path to the file" pos:"1"`
}

func renameAction(flags *RenameFlags) error {
	cTime, err := readCreationTime(flags.Path)
	if err != nil {
		return err
	}
	renameFile(flags.Path, cTime)
	fmt.Printf("Renamed %s with time %v\n", flags.Path, cTime)
	return nil
}

func AttachRename(cli *clir.Cli) {
	cli.NewSubCommandFunction("rename", "Rename specified file based on creation date", renameAction)
}
