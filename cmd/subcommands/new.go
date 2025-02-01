package subcommands

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"slices"
	"strings"
	"time"

	"github.com/leaanthony/clir"

	"github.com/KyleKing/yak-shears/cmd/config"
)

func toTimeName(t time.Time) string {
	// Adapted from: https://stackoverflow.com/a/65221179/3219667
	//  and https://pkg.go.dev/time
	return strings.Replace(t.UTC().Format(time.RFC3339), ":", "_", 2) // or RFC9557?
}

func fromTimeName(name string) (time.Time, error) {
	return time.Parse(time.RFC3339, strings.Replace(name, "_", ":", 2))
}

func createFile(path string) (err error) {
	file, err := os.Create(path)
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
			return fmt.Errorf("'%s' is not one of %v subDirs in '%s'. Create the folder if intended", subDir, folderNames, syncDir)
		}

		name := fmt.Sprintf("%s.dj", toTimeName(time.Now()))
		path := filepath.Join(syncDir, subDir, name)
		if err := createFile(path); err != nil {
			return err
		}
		if open {
			visual := os.Getenv("VISUAL")
			if visual == "" {
				return fmt.Errorf("No value is set for Visual")
			}
			cmd := exec.Command("open", "-a", visual, path)
			out, err := cmd.Output()
			if err != nil {
				return fmt.Errorf("Failed to run '%v' with error '%s' and output '%v'", cmd, err, out)
			}
		}
		fmt.Println(path)
		return nil
	})
}
