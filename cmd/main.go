package cmd

import (
	"github.com/leaanthony/clir"

	"github.com/KyleKing/yak-shears/cmd/subcommands"
)

// type Flags struct {
// 	Name string `name:"name" description:"The name of the person" default:"John"`
// 	Age  int    `name:"age" description:"The age of the person" default:"20"`
// }

func Main() *clir.Cli {
	cli := clir.NewCli("yak-shears", "Simple note taking", "v0.0.1")
	subcommands.AttachList(cli)
	subcommands.AttachNew(cli)
	subcommands.AttachRename(cli)

	// // >> Base
	// name := "Anonymous"
	// cli.StringFlag("name", "Your name", &name)
	//
	// var age int
	// cli.IntFlag("age", "Your age", &age)
	//
	// var awesome bool
	// cli.BoolFlag("awesome", "Are you awesome?", &awesome)
	//
	// cli.Action(func() error {
	// 	fmt.Printf("Hello %s (age=%d) who is awesome=%v!\n", name, age, awesome)
	// 	if !awesome {
	// 		return fmt.Errorf("Not awesome. Quitting")
	// 	}
	// 	return nil
	// })
	//
	// // >> Create
	// init := cli.NewSubCommand("create", "Create a person")
	// person := &Flags{
	// 	Age: 30, // FYI: Defaults set in struct, which override this
	// }
	// init.AddFlags(person)
	// init.Action(func() error {
	// 	fmt.Println("Name:", person.Name, "Age:", person.Age)
	// 	return nil
	// })
	//
	// // Also position and boolean arguments: https://clir.leaanthony.com/guide/flags/

	return cli
}
