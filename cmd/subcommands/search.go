package subcommands

// Notes:
// Prefer [native database libraries rather than an abstract interface](https://crawshaw.io/blog/go-and-sqlite) particular for local embedded.//
// Consider using [go:embed](https://pkg.go.dev/embed)

import (
	"fmt"

	"github.com/leaanthony/clir"
)

type SearchFlags struct {
	Query string `description:"Search Query" pos:"1"`
}

func searchAction(flags *SearchFlags) (err error) {
	fmt.Println(flags.Query)
	return
}

func AttachSearch(cli *clir.Cli) {
	cli.NewSubCommandFunction("search", "Search notes", searchAction)
}
