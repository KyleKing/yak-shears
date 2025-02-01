package subcommands

import (
	"database/sql"
	_ "embed" // Required for compiler
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/KyleKing/yak-shears/cmd/config"
	"github.com/leaanthony/clir"
	_ "github.com/marcboeker/go-duckdb"
)

//go:embed sql/init.sql
var SQL_INIT string

type Note struct {
	subfolder   string
	filename    string
	content     string
	modified_at time.Time
}

// Upsert modified notes
func storeNotes(db *sql.DB, notes []Note) {
	stmt, err := db.Prepare("INSERT INTO note VALUES(?, ?, ?, ?)")
	check(err)
	defer stmt.Close()

	for _, note := range notes {
		check(stmt.Exec(note.subfolder, note.filename, note.content, note.modified_at))
	}
}

func ingestSubdir(db *sql.DB, syncDir, subfolder string) (err error) {
	dir := filepath.Join(syncDir, subfolder)
	files, err := os.ReadDir(dir)
	if err != nil {
		return
	}

	notes := []Note{}
	for _, file := range files {
		if !file.IsDir() && strings.HasSuffix(file.Name(), ".dj") {
			fi, err := file.Info()
			if err != nil {
				return fmt.Errorf("Error with specified file (`%v`): %w", file, err)
			}
			content, err := os.ReadFile(filepath.Join(dir, file.Name()))
			if err != nil {
				return err
			}
			note := Note{subfolder: subfolder, filename: file.Name(), content: string(content), modified_at: fi.ModTime()}
			notes = append(notes, note)
		}
	}

	storeNotes(db, notes)
	return
}

// Ingest ALL Notes
func ingestAllNotes(db *sql.DB, syncDir string) (err error) {
	folderNames, err := ListSubfolders(syncDir)
	if err != nil {
		return
	}
	for _, subfolder := range folderNames {
		err := ingestSubdir(db, syncDir, subfolder)
		if err != nil {
			return err
		}
	}
	return
}

// Remove ALL notes
func removeAllNotes(db *sql.DB) {
	res, err := db.Exec("DELETE FROM note CASCADE")
	check(err)

	ra, _ := res.RowsAffected()
	log.Printf("Deleted %d rows\n", ra)
}

// Search for note in database
func search(db *sql.DB) (err error) {
	// TODO: currently only a PoC with LIMIT rather than WHERE
	stmt, err := db.Prepare("SELECT * FROM note LIMIT ?")
	check(err)

	rows, err := stmt.Query(10)
	defer rows.Close()
	check(err)

	log.Println("\n\n==============\n ")
	for rows.Next() {
		n := new(Note)
		if err := rows.Scan(&n.subfolder, &n.filename, &n.content, &n.modified_at); err != nil {
			return err
		}
		log.Println("\n\n--------------\n ")
		log.Printf("%s | %s | %v", n.subfolder, n.filename, n.modified_at.Format(time.RFC3339))
		log.Println(n.content)
	}
	log.Println("\n\n==============\n ")
	return
}

// Connect to the database and non-destructively initialize the schema, if not already found
func connectDb(dir string) (db *sql.DB) {
	var err error
	db, err = sql.Open("duckdb", filepath.Join(dir, "yak-shears.db?access_mode=READ_WRITE"))
	check(err)

	// PLANNED: when you want to use a Connection rather than DB?
	// conn, err := db.Conn(context.Background())
	// check(err)
	// defer conn.Close()
	// return conn

	check(db.Exec(SQL_INIT))

	return db
}

// CLI

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
		db := connectDb(syncDir)
		defer db.Close()
		if err := ingestAllNotes(db, syncDir); err != nil {
			return err
		}
		// PLANNED: Use the query against embedded data
		fmt.Println(searchQuery.Query)
		if err := search(db); err != nil {
			return err
		}
		removeAllNotes(db)
		return
	})
}
