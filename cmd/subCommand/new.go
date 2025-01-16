package subCommand

import (
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/leaanthony/clir"

	"github.com/KyleKing/yak-shears/cmd/config"
)

func toTimeName(t time.Time) string {
	// Adapted from: https://stackoverflow.com/a/65221179/3219667
	//  and https://pkg.go.dev/time
	return t.UTC().Format(time.RFC3339) // or RFC9557?
}

func createFile(path string) error {
	file, err := os.Create(path)
	defer file.Close()
	return err
}

func AttachNew(cli *clir.Cli) {
	rename := cli.NewSubCommand("new", "Create a new note")
	// PLANNED: `subfolder` should be a positional arg rather than flag. Consider other CLI libraries
	var subfolder string
	rename.StringFlag("n", "Subfolder", &subfolder)
	// PLANNED: Assumes the subfolder exists
	rename.Action(func() error {
		name := fmt.Sprintf("%s.dj", toTimeName(time.Now()))
		path := filepath.Join(config.GetSyncDir(), subfolder, name)
		fmt.Println("Created:", path)
		return createFile(path)
	})
}
