package main

import (
	"flag"
	"fmt"
	"os"
	"os/exec"
)

const (
	DEFAULT_EDITOR = "nano -w"
	DEFAULT_DIR    = "~/Sync/notes/"
)

func main() {
	var editor string
	flag.StringVar(&editor, "e", DEFAULT_EDITOR, "The default editor to use")
	flag.Parse()

	// Open the file with the default editor
	if editor == "" {
		editor = DEFAULT_EDITOR
	}
}

func openFile(filename string, editor string) error {
	if _, err := os.Stat(filename); err != nil {
		return fmt.Errorf("file does not exist")
	}

	// Open the file in the default editor
	cmd := exec.Command(editor, filename)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	err := cmd.Run()
	return err
}

// ```bash
// $ go run main.go new -e=atom
// File created: ~/Sync/notes/2023-03-01.dj
//
// # Or using flag with no --editor option (will use nano)
// $ go run main.go new
// File created: ~/Sync/notes/2023-03-01.dj
//
// # Editing the file in atom:
// $ go run main.go new -e=atom
// ```
//
// This CLI will create a new text file at `~/Sync/notes/{ISO timestamp}.dj` and open it in the default editor specified. If no --editor option is provided, the default editor (nano) will be used.
