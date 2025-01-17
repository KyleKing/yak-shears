package subCommand

import (
	"fmt"
	"os"
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
func listSubfoldersOld(home string) ([]string, error) {
	file, err := os.Open(filepath.Join(home, "PLACEHOLDER?"))
	if err != nil {
		return []string{}, err
	}
	names, err := file.Readdirnames(0)
	if err != nil {
		return []string{}, err
	}
	return names, err
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
	 rename := cli.NewSubCommand("new", "Create a new note and write the path to STDOUT. Example usage: `path=$(go run . new -subfolder test) && nvim \"$path\" || echo $path`")
	// PLANNED: `subfolder` should be a positional arg rather than flag. Consider other CLI libraries
	var subfolder string
	rename.StringFlag("subfolder", "Subfolder of `home`", &subfolder)
	home := config.GetSyncDir()
	rename.StringFlag("home", "Home", &home)
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
		fmt.Println(path)
		return createFile(path)
	})
}
