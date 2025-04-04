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

// TODO: implement Ollama client for embeddings
//  https://gobyexample.com/http-client
//  https://www.digitalocean.com/community/tutorials/how-to-make-http-requests-in-go

//go:embed sql/init.sql
var SQL_INIT string

//go:embed sql/searchQuery.sql
var SEARCH_QUERY string

type Note struct {
	subDir      string
	filename    string
	content     string
	modified_at time.Time
}

// Upsert modified notes
func storeNotes(db *sql.DB, notes []Note) (err error) {
	stmtNote, err := db.Prepare("INSERT INTO note VALUES(?, ?, ?, ?)")
	if err != nil {
		return
	}
	defer stmtNote.Close()

	stmtEmbed, err := db.Prepare("INSERT INTO embedding VALUES(?, ?)")
	if err != nil {
		return
	}
	defer stmtEmbed.Close()

	for _, note := range notes {
		if _, err := stmtNote.Exec(note.subDir, note.filename, note.content, note.modified_at); err != nil {
			return err
		}
		// TODO: Consider alternative chunking techniques
		for _, chunk := range strings.Split(note.content, `\n`) {
			if _, err := stmtEmbed.Exec(note.filename, chunk); err != nil {
				return err
			}
		}
	}
	return
}

func ingestSubdir(db *sql.DB, syncDir, subDir string) (err error) {
	dir := filepath.Join(syncDir, subDir)
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
			note := Note{subDir: subDir, filename: file.Name(), content: string(content), modified_at: fi.ModTime()}
			notes = append(notes, note)
		}
	}

	if err := storeNotes(db, notes); err != nil {
		return err
	}
	return
}

// Ingest ALL Notes
func ingestAllNotes(db *sql.DB, syncDir string) (err error) {
	folderNames, err := ListsubDirs(syncDir)
	if err != nil {
		return
	}
	for _, subDir := range folderNames {
		err := ingestSubdir(db, syncDir, subDir)
		if err != nil {
			return err
		}
	}
	return
}

// Remove ALL notes
func removeAllNotes(db *sql.DB) {
    // PLANNED: CASCADE from table note didn't work
	res, err := db.Exec("DELETE FROM embedding")
	check(err)
	res, err = db.Exec("DELETE FROM note")
	check(err)

	ra, _ := res.RowsAffected()
	log.Printf("Deleted %d rows\n", ra)
}

// Search for note in database
func search(db *sql.DB, query string) (err error) {
	// TODO: currently only a PoC with LIMIT rather than WHERE and 'query'
	stmt, err := db.Prepare(SEARCH_QUERY)
	if err != nil {
		return
	}

	rows, err := stmt.Query(2)
	defer rows.Close()
	if err != nil {
		return
	}

	log.Println("\n\n==============\n ")
	for rows.Next() {
		n := new(Note)
		if err := rows.Scan(&n.subDir, &n.filename, &n.content, &n.modified_at); err != nil {
			return err
		}
		log.Println("\n\n--------------\n ")
		log.Printf("%s | %s | %v", n.subDir, n.filename, n.modified_at.Format(time.RFC3339))
		log.Println(n.content)
	}
	log.Println("\n\n==============\n ")
	return
}

// Connect to the database and non-destructively initialize the schema, if not already found
func connectDb(dir string) (db *sql.DB, err error) {
	path := filepath.Join(dir, "yak-shears.db?access_mode=READ_WRITE")
	db, err = sql.Open("duckdb", path)
	if err != nil {
		return
	}

	// PLANNED: use a connection for threading
	// conn, err := db.Conn(context.Background())
	// check(err)
	// defer conn.Close()
	// return conn, nil

	_, err = db.Exec(SQL_INIT)
	if err != nil {
		return
	}
	return
}

// CLI

type SearchQuery struct {
	Query string `description:"" pos:"1"`
}

func AttachSearch(cli *clir.Cli) {
	searchCmd := cli.NewSubCommand("search", "Search notes")

	searchQuery := SearchQuery{}
	searchCmd.AddFlags(&searchQuery)

	syncDir := config.GetSyncDir()
	searchCmd.StringFlag("sync-dir", "Sync Directory", &syncDir)

	searchCmd.Action(func() (err error) {
		db, err := connectDb(syncDir)
		if err != nil {
			return
		}
		defer db.Close()
		// HACK: if the schema changes, the current workaround is to run:
		// rm yak-shears.db
		// HACK: removal and re-ingestion is sub-optimal and only for development
		removeAllNotes(db)
		if err := ingestAllNotes(db, syncDir); err != nil {
			return err
		}
		if err := search(db, searchQuery.Query); err != nil {
			return err
		}
		return
	})
}
