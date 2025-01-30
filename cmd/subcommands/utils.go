package subcommands

// If the last argument is non-nil, calls panic with value
// Adapted from go-duckdb documentation
func check(args ...interface{}) {
	err := args[len(args)-1]
	if err != nil {
		panic(err)
	}
}
