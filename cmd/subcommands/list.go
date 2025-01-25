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

// Sort Helpers

type ExtDirEntry struct {
	file fs.DirEntry
	stat string
}

type SortDirection func(string, string) bool

func asc(left, right string) bool {
	return left < right
}

func dsc(left, right string) bool {
	return left > right
}

type SortMethod func([]ExtDirEntry, SortDirection)

func sortFileName(files []ExtDirEntry, fun SortDirection) {
	sort.Slice(files, func(i, j int) bool {
		return fun(files[i].file.Name(), files[j].file.Name())
	})
}

func sortFileStat(files []ExtDirEntry, fun SortDirection) {
	sort.Slice(files, func(i, j int) bool {
		return fun(files[i].stat, files[j].stat)
	})
}

// Output

type OutputMethod func(ExtDirEntry) (string, error)

func summarize(file ExtDirEntry) (string, error) {
	fileInfo, err := file.file.Info()
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("%s %s %v %v", file.stat, file.file.Name(), fileInfo.Size(), fileInfo.ModTime()), nil
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
	listCmd.StringFlag("sort", "Sort Method. One of name or stat", &sortMethodStr)

	sortDirectionStr := "asc"
	listCmd.StringFlag("direction", "Sort Direction. One of asc or dsc", &sortDirectionStr)

	outputFormat := "text"
	listCmd.StringFlag("output", "Output format", &outputFormat)

	sortMethod := map[string]SortMethod{"name": sortFileName, "stat": sortFileStat}[sortMethodStr]
	sortDirection := map[string]SortDirection{"asc": asc, "dsc": dsc}[sortDirectionStr]
	output := map[string]OutputMethod{"text": summarize}[outputFormat]

	listCmd.Action(func() error {
		stats, err := getStats(syncDir)
		if err != nil {
			return err
		}
		sortMethod(stats, sortDirection)
		for _, s := range stats {
			out, err := output(s)
			if err != nil {
				return err
			}
			fmt.Println(out)
		}
		return nil
	})
}
