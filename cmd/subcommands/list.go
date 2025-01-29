package subcommands

import (
	"bufio"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"slices"
	"sort"
	"strings"
	"time"

	"github.com/KyleKing/yak-shears/cmd/config"
	"github.com/jedib0t/go-pretty/v6/table"
	"github.com/jedib0t/go-pretty/v6/text"
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

type FileStat struct {
	file     fs.DirEntry
	fileInfo fs.FileInfo
	path     string
}

type SortMethod func([]FileStat)

func sortFileName(stats []FileStat) {
	sort.Slice(stats, func(i, j int) bool {
		return stats[i].file.Name() > stats[j].file.Name()
	})
}

func sortFileModTime(stats []FileStat) {
	sort.Slice(stats, func(i, j int) bool {
		return stats[i].fileInfo.ModTime().After(stats[j].fileInfo.ModTime())
	})
}

// Output

type FileSummary struct {
	stat   FileStat
	header string
}

type OutputFormat func([]FileSummary) string

func summarize(summaries []FileSummary) string {
	mod_time_col := "Modified"

	t := table.NewWriter()
	t.AppendHeader(table.Row{"File Name", mod_time_col, "Header"})
	for _, summary := range summaries {
		fi := summary.stat.fileInfo
		t.AppendRow([]interface{}{
			summary.stat.file.Name(), fi.ModTime(), summary.header,
		})
	}
	t.SetColumnConfigs([]table.ColumnConfig{{
		Name:        mod_time_col,
		Transformer: text.NewTimeTransformer(time.RFC822, nil), // "02 Jan 06 15:04 MST"
	}})
	return t.Render()
}

func readMeta(path string) (string, error) {
	// Adapted from: https://www.bytesizego.com/blog/reading-file-line-by-line-golang
	file, err := os.Open(path)
	if err != nil {
		return "", fmt.Errorf("failed to open file %s: %s", path, err)
	}
	defer file.Close()

	// Read file line by line
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := scanner.Text()
		return line, nil
	}
	if err := scanner.Err(); err != nil {
		return "", fmt.Errorf("error reading file %s: %s", path, err)
	}
	return "", nil
}

func enrich(stat FileStat) (fs FileSummary, err error) {
	header, err := readMeta(stat.path)
	if err != nil {
		return
	}
	fs.stat = stat
	fs.header = header
	return
}

// Main Operations

func calculateStats(dir string) (stats []FileStat, err error) {
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
			stat := FileStat{file: file, fileInfo: fi, path: filepath.Join(dir, file.Name())}
			stats = append(stats, stat)
		}
	}
	return
}

func getStats(syncDir string) (stats []FileStat, err error) {
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
		summaries := []FileSummary{}
		for _, s := range stats {
			summary, err := enrich(s)
			if err != nil {
				return err
			}
			summaries = append(summaries, summary)
		}
		fmt.Println(output(summaries))
		return
	})
}
