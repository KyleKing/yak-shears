package cmd

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"github.com/leaanthony/clir"
)

func currentCreationTime() string {
	// Adapted from: https://stackoverflow.com/a/65221179/3219667
	//  and https://pkg.go.dev/time
	return time.Now().UTC().Format(time.RFC3339) // or RFC9557?
}

func readCreationTime(path string) (string, error) {
	// Utilities adapted from: https://github.com/djherbis/times/blob/d1af0aa12128959e70b9e802c912f302c743c35b/times_darwin.go

	timespecToTime := func(ts syscall.Timespec) string {
		return time.Unix(int64(ts.Sec), int64(ts.Nsec)).UTC().Format(time.RFC3339)
	}
	getTimespec := func(fi os.FileInfo) string {
		stat := fi.Sys().(*syscall.Stat_t)
		return timespecToTime(stat.Ctimespec) // stat.Birthtimespec
	}

	fileInfo, err := os.Stat(path)
	if err != nil {
		return "", fmt.Errorf("Error with specified file (`%s`): %w", path, err)
	}

	return getTimespec(fileInfo), nil
}

func renameFile(path, cTime string) error {
	basename, _, _ := strings.Cut(filepath.Base(path), ".")
	newPath := strings.ReplaceAll(path, basename, cTime)
	return os.Rename(path, newPath)
}

func attachRename(cli *clir.Cli) {
	rename := cli.NewSubCommand("rename", "Rename specified file based on creation date")
	// PLANNED: `path` should be a positional arg rather than flag. Consider other CLI libraries
	var path string
	rename.StringFlag("path", "Path to file", &path)
	rename.Action(func() error {
		cTime, err := readCreationTime(path)
		if err == nil {
			renameFile(path, cTime)
			fmt.Printf("Renamed %s with time %v\n", path, cTime)
		}
		return err
	})
}
