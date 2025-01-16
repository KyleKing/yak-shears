package main

import (
	"fmt"
	"os"

	"github.com/KyleKing/yak-shears/cmd"
)

func main() {
	cli := cmd.Main()

	if err := cli.Run(); err != nil {
		fmt.Println("Error encountered: ", err)
		os.Exit(1)
	}
}
