package main

import (
	"fmt"
	"os"
	"time"

	"github.com/KyleKing/yak-shears/cmd"
)

func main() {
	fmt.Println(time.Now().UTC().Format(time.RFC3339) + ".md")

	cli := cmd.Main()

	if err := cli.Run(); err != nil {
		fmt.Println("Error encountered: ", err)
		os.Exit(1)
	}
}
