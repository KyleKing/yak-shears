package subCommand

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

func createFile(path string) error {
	file, err := os.Create(path)
	defer file.Close()
	return err
}

func listSubfolders(home string) ([]string, error) {
	folderNames := []string{}

	files, err := os.ReadDir(home)
	if err != nil {
		return folderNames, err
	}

	for _, file := range files {
		if !(strings.HasPrefix(file.Name(), ".")) {
			folderNames = append(folderNames, file.Name())
		}
	}
	return folderNames, nil
}

func AttachNew(cli *clir.Cli) {
	rename := cli.NewSubCommand("new", "Create a new note")

	// PLANNED: `subfolder` should be a positional arg rather than flag. Consider other CLI libraries
	var subfolder string
	rename.StringFlag("subfolder", "Subfolder of `home`", &subfolder)

	home := config.GetSyncDir()
	rename.StringFlag("home", "Home", &home)

	visual := os.Getenv("VISUAL")
	rename.StringFlag("visual", "Specified application", &visual)

	rename.Action(func() error {
		folderNames, err := listSubfolders(home)
		if err != nil {
			return err
		}
		if !slices.Contains(folderNames, subfolder) {
			return fmt.Errorf("'%s' is not one of %v subfolders in '%s'. Create the folder if intended", subfolder, folderNames, home)
		}

		name := fmt.Sprintf("%s.dj", toTimeName(time.Now()))
		path := filepath.Join(home, subfolder, name)
		if err := createFile(path); err != nil {
			return err
		}
		if visual != "" {
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
