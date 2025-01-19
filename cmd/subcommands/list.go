package subcommands

import (
	"fmt"
	"os"
	"strings"

	"github.com/KyleKing/yak-shears/cmd/config"
	"github.com/djherbis/times"
	"github.com/leaanthony/clir"
)

func getStats(dir string) ([]string, error) {
	stats := []string{}

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
			stats = append(stats, fmt.Sprintf("%v", t.ModTime()))

		}
	}
	return stats, nil
}

func AttachList(cli *clir.Cli) {
	listCmd := cli.NewSubCommand("list", "List notes")

	syncDir := config.GetSyncDir()
	listCmd.StringFlag("sync-dir", "Sync Directory", &syncDir)

	listCmd.Action(func() error {
		stats, err := getStats(syncDir)
		fmt.Println(stats)
		if err != nil {
			return err
		}
		return nil
	})
}
