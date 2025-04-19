package subcommands

import (
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"slices"
	"strings"
	"time"

	"github.com/leaanthony/clir"

	"github.com/KyleKing/yak-shears/yak-notes-cli/cmd/config"
)

func ToTimeName(t time.Time) string {
	// Adapted from: https://stackoverflow.com/a/65221179/3219667
	//  and https://pkg.go.dev/time
	return strings.Replace(t.UTC().Format(time.RFC3339), ":", "_", 2) // or RFC9557?
}

func FromTimeName(name string) (time.Time, error) {
	parsedName := strings.Replace(name, "_", ":", 2)
	time, err := time.Parse(time.RFC3339, parsedName)

	if err != nil {
		return time, fmt.Errorf("failed to parse time %s (%s): %w", name, parsedName, err)
	}

	return time, nil
}

func CreateFile(path string) (err error) {
	file, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("failed to create file: %w", err)
	}

	defer file.Close()

	return
}

func AttachNew(cli *clir.Cli) {
	newCmd := cli.NewSubCommand("new", "Create a new note")

	syncDir := config.GetSyncDir()
	newCmd.StringFlag("sync-dir", "Sync Directory", &syncDir)

	subDir := config.GetSubDir()
	newCmd.StringFlag("sub-dir", "SubDir of Shears Sync directory", &subDir)

	open := false
	newCmd.BoolFlag("o", "If set, opens the file in `$VISUAL`", &open)

	newCmd.Action(func() error {
		folderNames, err := ListsubDirs(syncDir)
		if err != nil {
			return err
		}

		if !slices.Contains(folderNames, subDir) {
			return fmt.Errorf(
				"'%s' is not one of %v subDirs in '%s'. Create the folder if intended",
				subDir,
				folderNames,
				syncDir,
			)
		}

		name := ToTimeName(time.Now()) + ".dj"

		path := filepath.Join(syncDir, subDir, name)
		if err := CreateFile(path); err != nil {
			return err
		}

		if open {
			visual := os.Getenv("VISUAL")
			if visual == "" {
				return errors.New("no value is set for shell environment 'VISUAL'")
			}

			cmd := exec.Command("open", "-a", visual, path)
			out, err := cmd.Output()

			if err != nil {
				return fmt.Errorf(
					"failed to run '%v' with error '%w' and output '%v'",
					cmd,
					err,
					out,
				)
			}
		}

		fmt.Println(path)

		return nil
	})
}
