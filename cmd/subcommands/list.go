package subcommands

import (
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"slices"
	"sort"
	"strings"

	"github.com/KyleKing/yak-shears/cmd/config"
	"github.com/leaanthony/clir"
)

// Shared Utilities

func ListSubfolders(dir string) (folderNames []string, err error) {
	files, err := os.ReadDir(dir)
	if err != nil {
		return
	}
	for _, file := range files {
		if file.IsDir() && !(strings.HasPrefix(file.Name(), ".")) {
			folderNames = append(folderNames, file.Name())
		}
	}
	return
}

// Sort Helpers

type ExtDirEntry struct {
	file     fs.DirEntry
	fileInfo fs.FileInfo
}

type SortMethod func([]ExtDirEntry)

func sortFileName(files []ExtDirEntry) {
	sort.Slice(files, func(i, j int) bool {
		return files[i].file.Name() > files[j].file.Name()
	})
}

func sortFileModTime(files []ExtDirEntry) {
	sort.Slice(files, func(i, j int) bool {
		return files[i].fileInfo.ModTime().After(files[j].fileInfo.ModTime())
	})
}

// Output

type OutputFormat func(ExtDirEntry) string

func summarize(file ExtDirEntry) string {
	fi := file.fileInfo
	return fmt.Sprintf("%v | %v | %v", fi.ModTime(), file.file.Name(), fi.Size())
}

// Main Operations

func calculateStats(dir string) (stats []ExtDirEntry, err error) {
	files, err := os.ReadDir(dir)
	if err != nil {
		return
	}

	for _, file := range files {
		if !file.IsDir() && strings.HasSuffix(file.Name(), ".dj") {
			fi, err := file.Info()
			if err != nil {
				return stats, fmt.Errorf("Error with specified file (`%v`): %w", file, err)
			}
			stat := ExtDirEntry{file: file, fileInfo: fi}
			stats = append(stats, stat)
		}
	}
	return
}

func getStats(syncDir string) (stats []ExtDirEntry, err error) {
	folderNames, err := ListSubfolders(syncDir)
	if err != nil {
		return
	}
	for _, name := range folderNames {
		subStats, err := calculateStats(filepath.Join(syncDir, name))
		if err != nil {
			return stats, err
		}
		stats = append(stats, subStats...)
	}
	return
}

func AttachList(cli *clir.Cli) {
	listCmd := cli.NewSubCommand("list", "List notes")

	syncDir := config.GetSyncDir()
	listCmd.StringFlag("sync-dir", "Sync Directory", &syncDir)

	sortMethodStr := "name"
	listCmd.StringFlag("sort", "Sort Method. One of name or mod", &sortMethodStr)

	sortAsc := false
	listCmd.BoolFlag("sort-asc", "If set, sort ascending", &sortAsc)

	outputFormat := "text"
	listCmd.StringFlag("output", "Output format", &outputFormat)

	listCmd.Action(func() (err error) {
		sortMethod := map[string]SortMethod{"name": sortFileName, "mod": sortFileModTime}[sortMethodStr]
		output := map[string]OutputFormat{"text": summarize}[outputFormat]

		stats, err := getStats(syncDir)
		if err != nil {
			return
		}
		sortMethod(stats)
		if sortAsc {
			slices.Reverse(stats)
		}
		for _, s := range stats {
			fmt.Println(output(s))
		}
		return
	})
}
