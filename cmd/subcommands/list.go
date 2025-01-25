package subcommands

import (
	"fmt"
	"io/fs"
	"os"
	"slices"
	"sort"
	"strings"

	"github.com/KyleKing/yak-shears/cmd/config"
	"github.com/leaanthony/clir"
)

// Sort Helpers

type ExtDirEntry struct {
	file     fs.DirEntry
	fileInfo fs.FileInfo
}

type SortMethod func([]ExtDirEntry)

func sortFileName(files []ExtDirEntry) {
	sort.Slice(files, func(i, j int) bool {
		return files[i].file.Name() < files[j].file.Name()
	})
}

func sortFileModTime(files []ExtDirEntry) {
	sort.Slice(files, func(i, j int) bool {
		return files[i].fileInfo.ModTime().Before(files[j].fileInfo.ModTime())
	})
}

// Output

type OutputFormat func(ExtDirEntry) string

func summarize(file ExtDirEntry) string {
	fi := file.fileInfo
	return fmt.Sprintf("%v %v %v", fi.ModTime(), file.file.Name(), fi.Size())
}

// Main Operations

func getStats(dir string) (stats []ExtDirEntry, err error) {
	files, err := os.ReadDir(dir)
	if err != nil {
		return stats, err
	}

	for _, file := range files {
		if !file.IsDir() && !strings.HasSuffix(file.Name(), ".dj") {
			fi, err := file.Info()
			if err != nil {
				return stats, fmt.Errorf("Error with specified file (`%v`): %w", file, err)
			}
			stat := ExtDirEntry{file: file, fileInfo: fi}
			stats = append(stats, stat)
		}
	}
	return stats, nil
}

func AttachList(cli *clir.Cli) {
	listCmd := cli.NewSubCommand("list", "List notes")

	syncDir := config.GetSyncDir()
	listCmd.StringFlag("sync-dir", "Sync Directory", &syncDir)

	sortMethodStr := "name"
	listCmd.StringFlag("sort", "Sort Method. One of name or stat", &sortMethodStr)

	sortDesc := false
	listCmd.BoolFlag("sort-desc", "If set, sort descending", &sortDesc)

	outputFormat := "text"
	listCmd.StringFlag("output", "Output format", &outputFormat)

	sortMethod := map[string]SortMethod{"name": sortFileName, "stat": sortFileModTime}[sortMethodStr]
	output := map[string]OutputFormat{"text": summarize}[outputFormat]

	listCmd.Action(func() error {
		stats, err := getStats(syncDir)
		if err != nil {
			return err
		}
		sortMethod(stats)
		if sortDesc {
			slices.Reverse(stats)
		}
		for _, s := range stats {
			fmt.Println(output(s))
		}
		return nil
	})
}
