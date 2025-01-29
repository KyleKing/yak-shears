# Yak Shears

Just yak shaving to create my personal note taking app, but you probably want to use one of these primarily open-source applications instead:

| Service | Notes |
| --- | --- |
| [Archivy](https://github.com/archivy/archivy) | "self-hostable knowledge repository" |
| [Awesome List of Note Taking Software](https://github.com/tehtbl/awesome-note-taking) | and more! |
| [Bear](https://bear.app) | "Markdown notes you’ll love" |
| [bookmarker](https://github.com/dellsystem/bookmarker) | "personal project to help me retain information from books" |
| [Buku](https://github.com/jarun/buku) | "Personal mini-web in text" |
| [DayOne](https://dayoneapp.com) | "Beautiful daily journaling mobile and web app" |
| [Docmost](https://github.com/docmost/docmost) | "collaborative wiki and documentation software" |
| [Evernote](https://evernote.com) | |
| [flatnotes](https://github.com/dullage/flatnotes) | "database-less note-taking web app that utilises a flat folder of markdown files" |
| [HedgeDoc](https://github.com/hedgedoc/hedgedoc) | "web-based, self-hosted, collaborative markdown editor" |
| [Hypothesis](https://web.hypothes.is) | "Collaboratively annotate the web" |
| [Joplin](https://joplinapp.org) | "Open source note-taking app" |
| [Jot](https://github.com/shashwatah/jot) | "Rapid note management for the terminal" |
| [Memos](https://www.usememos.com) | Twitter-like private note taking app |
| [Monica](https://github.com/monicahq/monica?tab=readme-ov-file#principles) | "Personal relationship CRM" |
| [nb](https://github.com/xwmx/nb) | "note‑taking, bookmarking, and archiving with linking, tagging, filtering .. + more" |
| [Notion](https://www.notion.so) | |
| [Notional Velocity](https://notational.net) ([Source](https://github.com/scrod/nv)) | Introduced ideas that are now more commonplace. Such as "searching for notes is not a separate action; rather, it is the primary interface" |
| [nvpy](https://github.com/cpbotha/nvpy) | |
| [Obsidian](https://obsidian.md) | |
| [Pinboard](https://pinboard.in/about/) | "One of the oldest independently run businesses on the web" with a text-first UI |
| [Rnote](https://github.com/flxzt/rnote) | "Sketch and take handwritten notes" |
| [Silicon Notes](https://github.com/cu/silicon) | "A web-based personal knowledge base with few frills" |
| [SimpleNote by Automatic](https://simplenote.com) | "All your notes, synced on all your devices" |
| [Siyuan](https://github.com/siyuan-note/siyuan) | "fine-grained block-level reference and Markdown WYSIWYG" |
| [Standard Notes](https://github.com/standardnotes/server) | "secure note-taking app" |
| [Textpod](https://github.com/freetonik/textpod) | "inspired by 'One Big Text File' idea" |
| [Trillium Next Notes](https://github.com/TriliumNext/Notes/) | "hierarchical note taking application with focus on building large personal knowledge bases" |
| [Untitled](https://github.com/12joan/untitled-note) | "An open-source app for taking notes that feels awesome to use" |
| [Zettlr](https://github.com/Zettlr/Zettlr) | "One-Stop Publication Workbench" |
| Open Source hosted on [Pika Pods](https://www.pikapods.com/apps#notes) | Includes Memos, [linkding](https://github.com/sissbruecker/linkding), etc. |

## Goals

![./assets/shears.webp](./assets/shears.webp)

1. Opinionated. This is my personal app and the design choices are what works for me.

    1. For example, tagging is intentionally limited in favor of search and bi-directional linking as [better explained here](https://blog.bityard.net/articles/2022/December/the-design-of-silicon-notes-with-cartoons).
1. Limited features. Having few features is the goal, for maintainability and usability.

## Features

- There is a CLI and API for local search, creation, and general management
- Content is stored in files using the `djot` markup language

    - The files can be edited in any editor (nvim, emacs, VSCode, NotePad++, etc.)
    - They can be synced using [Syncthing](https://syncthing.net/), [Dropbox](https://www.dropbox.com), iCloud, [rsync](https://jenkov.com/tutorials/rsync/detecting-file-differences.html), [hyperdrive](https://github.com/holepunchto/hyperdrive), [iroh](https://github.com/n0-computer/iroh), [any-sync](https://github.com/anyproto/tech-docs), etc.
- Each note is named by the creation timestamp to be unique, predictable, and easier to permalink

### Details

{% In Progress %}

- _Subfolder/Context_ ("Yak Pen"): set via environment variable or argument

    - `shears new (evergreen|personal|work)?`
    - What about having all notes in one directory rather than separate and using metadata instead?
- `shears list -order=(created|modified|count-links|count-merged|count-split) -desc? -status=(?)` defaults to showing the n-most recent notes by modification date
- No state initially, then manually set to `Atomic` once reviewed/edited. Tasks are just notes with state: `backlog|queue|in-progress|complete|not-planned`

    - `shears state <state> <to?>`
    - Tasks with subtasks don't need `on-hold` because the partially complete subtasks are self-documenting and can go back to the `queue`.
- _Operations_: notes have `split-from: []string` or `merged-from: []string` to support handling links to deleted files or moving content

    - For readability, the file header is displayed via virtual text (in NVIM, Web, etc.)
    - Consider `links: []string` to support bi-directional linking between notes (bi-directional part comes from database/tooling rather than in-code). Managed with `shears link <from?> <to?>`
    - `shears split <name>?` and `shears merge <from>? <to>?`. If either argument is missing, an interactive selection follows, which defaults to recent by modified date, then filters based on text input
- Import: `shears import from <source>` supports ingestion of Apple Notes for remote submission. Imported files appear in `/imports` with filename timestamp based on metadata from source or current. `shears import review` allows incremental review of each note for placement in the right context (not sure how to batch this because it is a `change-context`?)
- What is the story for planning? For example, there are time-sensitive tasks, but they can't start today? Maybe `start-date` and `hard-deadline` (and `soft-deadline`)?
- What about a concept of a `bookmarklet note` that is managed by a browser extension? This way bookmarked tabs can be archived more easily rather than clutter the bookmarks bar?
