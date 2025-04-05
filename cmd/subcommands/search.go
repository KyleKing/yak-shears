package subcommands

import (
	_ "embed" // Required for compiler
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/jmoiron/sqlx"
	_ "github.com/marcboeker/go-duckdb"

	"github.com/KyleKing/yak-shears/cmd/config"
	"github.com/leaanthony/clir"
)

// TODO: implement Ollama client for embeddings
//  https://gobyexample.com/http-client
//  https://www.digitalocean.com/community/tutorials/how-to-make-http-requests-in-go

//go:embed sql/init.sql
var SQL_INIT string

//go:embed sql/searchQuery.sql
var SEARCH_QUERY string

//go:embed sql/insertNote.sql
var INSERT_NOTE string

//go:embed sql/insertEmbedding.sql
var INSERT_EMBEDDING string

type Note struct {
	sub_dir     string
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
}

func storeNotes(db *sqlx.DB, notes []Note) (err error) {
	for _, note := range notes {
		_, err := db.NamedExec(INSERT_NOTE, note)
		if err != nil {
			return err
		}

		for _, chunk := range strings.Split(note.content, `\n`) {
			_, err := db.NamedExec(INSERT_EMBEDDING, map[string]interface{}{
				"filename":  note.filename,
				"embedding": chunk,
			})
			if err != nil {
				return err
			}
		}
	}
	return
}

func ingestSubdir(db *sqlx.DB, syncDir, subDir string) (err error) {
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
			note := Note{sub_dir: subDir, filename: file.Name(), content: string(content), modified_at: fi.ModTime()}
			notes = append(notes, note)
		}
	}

	if err := storeNotes(db, notes); err != nil {
		return err
	}
	return
}

// Ingest ALL Notes
func ingestAllNotes(db *sqlx.DB, syncDir string) (err error) {
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
func removeAllNotes(db *sqlx.DB) {
	_, err := db.Exec("DELETE FROM embedding")
	check(err)
	_, err = db.Exec("DELETE FROM note")
	check(err)
}

// Search for note in database
func search(db *sqlx.DB, query string) (err error) {
	rows, err := db.Queryx(SEARCH_QUERY, 2, 0)
	if err != nil {
		return
	}
	defer rows.Close()

	for rows.Next() {
		n := Note{}
		if err := rows.StructScan(&n); err != nil {
			return err
		}
		log.Printf("%s | %s | %v\n%s", n.sub_dir, n.filename, n.modified_at.Format(time.RFC3339), n.content)
	}
	return
}

// Connect to the database and non-destructively initialize the schema, if not already found
func connectDb(dir string) (db *sqlx.DB, err error) {
	path := filepath.Join(dir, "yak-shears.db?access_mode=READ_WRITE")
	db, err = sqlx.Open("duckdb", path)
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
		// HACK: if the schema changes, the current workaround is to remove the file
		if err := os.Remove(filepath.Join(syncDir, "yak-shears.db")); err != nil {
			return err
		}

		db, err := connectDb(syncDir)
		if err != nil {
			return
		}
		defer db.Close()
		// // HACK: removal and re-ingestion is sub-optimal and only for development
		// removeAllNotes(db)
		if err := ingestAllNotes(db, syncDir); err != nil {
			return err
		}
		if err := search(db, searchQuery.Query); err != nil {
			return err
		}
		return
	})
}
