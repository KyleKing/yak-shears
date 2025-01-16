package cmd

import (
	"fmt"
	"os"

	"github.com/leaanthony/clir"
	"syscall"
	"time"
)

type Flags struct {
	Name string `name:"name" description:"The name of the person" default:"John"`
	Age  int    `name:"age" description:"The age of the person" default:"20"`
}

func Main() *clir.Cli {
	cli := clir.NewCli("yak-shears", "Simple note taking", "v0.0.1")

	// >> Base
	name := "Anonymous"
	cli.StringFlag("name", "Your name", &name)

	var age int
	cli.IntFlag("age", "Your age", &age)

	var awesome bool
	cli.BoolFlag("awesome", "Are you awesome?", &awesome)

	cli.Action(func() error {
		fmt.Printf("Hello %s (age=%d) who is awesome=%v!\n", name, age, awesome)
		if !awesome {
			return fmt.Errorf("Not awesome. Quitting")
		}
		return nil
	})

	// >> Create
	init := cli.NewSubCommand("create", "Create a person")
	person := &Flags{
		Age: 30, // FYI: Defaults set in struct, which override this
	}
	init.AddFlags(person)
	init.Action(func() error {

		// https://github.com/djherbis/times/blob/d1af0aa12128959e70b9e802c912f302c743c35b/times_darwin.go
		timespecToTime := func(ts syscall.Timespec) string {
			return time.Unix(int64(ts.Sec), int64(ts.Nsec)).UTC().Format(time.RFC3339)
		}

		fileInfo, err := os.Lstat(person.Name)
		if err != nil {
			return err
		}
		stat := fileInfo.Sys().(*syscall.Stat_t)
		fmt.Println(timespecToTime(stat.Ctimespec), timespecToTime(stat.Birthtimespec))

		fmt.Println("Name:", person.Name, "Age:", person.Age)
		return nil
	})

	// Also position and boolean arguments: https://clir.leaanthony.com/guide/flags/

	return cli
}
