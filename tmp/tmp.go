package main

import (
	"flag"
	"fmt"
	"log"
	"os"
	"os/exec"
	"time"
	// "github.com/spf13/cobra"
)

const (
	DEFAULT_EDITOR = "nano -w"
	DEFAULT_DIR    = "~/Sync/notes/"
)

func main() {
	var editor string
	flag.StringVar(&editor, "e", DEFAULT_EDITOR, "The default editor to use")
	flag.Parse()

	if flag.NArg() == 0 {
		log.Fatal("No file name provided. Please run with a filename")
	}

	// FYI: see https://stackoverflow.com/a/65221179/3219667 (and https://pkg.go.dev/time)
	timestamp := time.Now().UTC().Format(time.RFC3339) // or RFC9557?
	filename := fmt.Sprintf("%s%s.%s", DEFAULT_DIR, timestamp, "dj")

	file, err := os.Create(filename)
	if err != nil {
		log.Fatal(err)
	}
	defer file.Close()

	fmt.Printf("File created: %s\n", filename)

	// Open the file with the default editor
	if editor == "" {
		editor = DEFAULT_EDITOR
	}

	// cmd := &cobra.Command{
	//         Use:   "new",
	//         Short: "Create a new text file and open it in $EDITOR",
	//         RunE: func(cmd *cobra.Command, args []string) error {
	//                 return openFile(file.Name(), editor)
	//         },
	// }
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
