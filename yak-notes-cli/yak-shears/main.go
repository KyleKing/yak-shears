package main

import (
	"fmt"
	"os"

	"github.com/KyleKing/yak-shears/cmd"
)

func main() {
	cli := cmd.InitCli()

	if err := cli.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "Error encountered: %v\n", err)
		os.Exit(1)
	}
}
