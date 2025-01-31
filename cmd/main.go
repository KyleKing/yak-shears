package cmd

import (
	// PLANNED: Consider building with the builtin package instead
	"github.com/leaanthony/clir"

	"github.com/KyleKing/yak-shears/cmd/subcommands"
)

func Main() (cli *clir.Cli) {
	cli = clir.NewCli("yak-shears", "Simple note taking", "v0.0.1")
	subcommands.AttachList(cli)
	subcommands.AttachNew(cli)
	subcommands.AttachRename(cli)
	return
}
