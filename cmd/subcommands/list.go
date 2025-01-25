package subcommands

import (
	"fmt"
	"io/fs"
	"os"
	"sort"
	"strings"

	"github.com/KyleKing/yak-shears/cmd/config"
	"github.com/djherbis/times"
	"github.com/leaanthony/clir"
)

type ExtDirEntry struct {
	file fs.DirEntry
	stat string
}

// Sort Helpers

func strAsc(left, right string) bool {
	return left < right
}
func strDsc(left, right string) bool {
	return left > right
}

func SortFileName(files []ExtDirEntry, fun func(string, string) bool) {
	sort.Slice(files, func(i, j int) bool {
		return fun(files[i].file.Name(), files[j].file.Name())
	})
}

func SortFileMod(files []ExtDirEntry, fun func(string, string) bool) {
	sort.Slice(files, func(i, j int) bool {
		return fun(files[i].stat, files[j].stat)
	})
}

type FileSummary struct {
	mod  string
	name string
}

func summarize(file ExtDirEntry) FileSummary {
	return FileSummary{name: file.file.Name(), mod: file.stat}
}

// Main Operations

func getStats(dir string) (stats []ExtDirEntry, err error) {
	// // TIL: you can define variables above ^^
	// stats := []ExtDirEntry{}

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
			t := times.Get(fi)
			stat := ExtDirEntry{stat: fmt.Sprintf("%v", t.ModTime()), file: file}
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
	listCmd.StringFlag("sort", "Sort Method", &sortMethodStr)

	sortDirectionStr := "asc"
	listCmd.StringFlag("direction", "Sort Direction", &sortDirectionStr)

	outputFormat := "table"
	listCmd.StringFlag("output", "Output format", &outputFormat)

	// TODO: make these dynamic
	sortMethod := SortFileName
	sortDirection := strAsc
	output := summarize

	listCmd.Action(func() error {
		stats, err := getStats(syncDir)
		if err != nil {
			return err
		}
		sortMethod(stats, sortDirection)
		for _, s := range stats {
			fmt.Println(output(s))
		}
		return nil
	})
}
