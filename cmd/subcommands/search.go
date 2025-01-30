package subcommands

import (
	"context"
	"database/sql"
	_ "embed" // Required for compiler
	"fmt"
	"log"
	"path/filepath"
	"time"

	"github.com/KyleKing/yak-shears/cmd/config"
	"github.com/leaanthony/clir"
	_ "github.com/marcboeker/go-duckdb"
)

var db *sql.DB

//go:embed sql/init.sql
var SQL_INIT string

type user struct {
	username string
	age      int
	height   float32
	awesome  bool
	bday     time.Time
}

func simpleMain(dir string) {
	var err error
	db, err = sql.Open("duckdb", filepath.Join(dir, "db.duckdb?access_mode=READ_WRITE"))
	check(err)
	defer db.Close()

	check(db.Ping())

	setting := db.QueryRow("SELECT current_setting('access_mode')")
	var accessMode string
	check(setting.Scan(&accessMode))
	log.Printf("DB opened with access mode %s", accessMode)

	check(db.Exec(SQL_INIT))
	check(db.Exec("INSERT INTO users VALUES('marc', 99, 1.91, true, '1970-01-01')"))

	rows, err := db.QueryContext(
		context.Background(), `
		SELECT username, age, height, awesome, bday
		FROM users
		WHERE (username = ? OR username = ?) AND age > ? AND awesome = ?`,
		"macgyver", "marc", 30, true,
	)
	check(err)
	defer rows.Close()

	for rows.Next() {
		u := new(user)
		err := rows.Scan(&u.username, &u.age, &u.height, &u.awesome, &u.bday)
		if err != nil {
			log.Fatal(err)
		}
		log.Printf(
			"%s is %d years old, %.2f tall, bday on %s and has awesomeness: %t\n",
			u.username, u.age, u.height, u.bday.Format(time.RFC3339), u.awesome,
		)
	}
	check(rows.Err())

	res, err := db.Exec("DELETE FROM users CASCADE")
	check(err)

	ra, _ := res.RowsAffected()
	log.Printf("Deleted %d rows\n", ra)

	runTransaction()
	testPreparedStmt()
}

func runTransaction() {
	log.Println("Starting transaction...")
	tx, err := db.Begin()
	check(err)

	check(
		tx.ExecContext(
			context.Background(),
			"INSERT INTO users VALUES('gru', 25, 1.35, false, '1996-04-03')",
		),
	)
	row := tx.QueryRow("SELECT COUNT(*) FROM users WHERE username = ?", "gru")
	var count int64
	check(row.Scan(&count))
	if count > 0 {
		log.Println("User Gru was inserted")
	}

	log.Println("Rolling back transaction...")
	check(tx.Rollback())

	row = db.QueryRow("SELECT COUNT(*) FROM users WHERE username = ?", "gru")
	check(row.Scan(&count))
	if count > 0 {
		log.Println("Found user Gru")
	} else {
		log.Println("Couldn't find user Gru")
	}
}

func testPreparedStmt() {
	stmt, err := db.Prepare("INSERT INTO users VALUES(?, ?, ?, ?, ?)")
	check(err)
	defer stmt.Close()

	check(stmt.Exec("Kevin", 11, 0.55, true, "2013-07-06"))
	check(stmt.Exec("Bob", 12, 0.73, true, "2012-11-04"))
	check(stmt.Exec("Stuart", 13, 0.66, true, "2014-02-12"))

	stmt, err = db.Prepare("SELECT * FROM users WHERE age > ?")
	check(err)

	rows, err := stmt.Query(1)
	defer rows.Close()
	check(err)

	for rows.Next() {
		u := new(user)
		err := rows.Scan(&u.username, &u.age, &u.height, &u.awesome, &u.bday)
		if err != nil {
			log.Fatal(err)
		}
		log.Printf(
			"%s is %d years old, %.2f tall, bday on %s and has awesomeness: %t\n",
			u.username, u.age, u.height, u.bday.Format(time.RFC3339), u.awesome,
		)
	}
}

// func dontForgetToClose() {
// 	db, err := sql.Open("duckdb", "/path/to/foo.db")
// 	defer db.Close()
//
// 	conn, err := db.Conn(context.Background())
// 	defer conn.Close()
//
// 	rows, err := conn.Query("SELECT 42")
// 	// Alternatively, rows.Next() has to return false.
// 	rows.Close()
//
// 	appender, err := NewAppenderFromConn(conn, "", "test")
// 	defer appender.Close()
//
// 	// If not passed to sql.OpenDB.
// 	connector, err := NewConnector("", nil)
// 	defer connector.Close()
// }

type SearchQuery struct {
	Query string `description:"" pos:"1"`
}

func AttachSearch(cli *clir.Cli) {
	searchCmd := cli.NewSubCommand("search", "Search notes")

	syncDir := config.GetSyncDir()
	searchCmd.StringFlag("sync-dir", "Sync Directory", &syncDir)

	// var query string
	// searchCmd.StringFlag("query", "Search Query", &query)
	searchQuery := SearchQuery{}
	searchCmd.AddFlags(&searchQuery)

	searchCmd.Action(func() (err error) {
		fmt.Println(searchQuery.Query)
		simpleMain(syncDir)
		return
	})
}
