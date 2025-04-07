# Yak Shears

My personal note taking app, but you probably want to use one of these primarily open-source applications instead:

| Service | Notes |
| --- | --- |
| [Archivy](https://github.com/archivy/archivy) | "Self-hostable knowledge repository" |
| [Bear](https://bear.app) | "Markdown notes you’ll love" (Closed source) |
| [bookmarker](https://github.com/dellsystem/bookmarker) | "Personal project to help me retain information from books" |
| [Buku](https://github.com/jarun/buku) | "Personal mini-web in text" |
| [DayOne](https://dayoneapp.com) | "Beautiful daily journaling mobile and web app" (Closed source) |
| [Docmost](https://github.com/docmost/docmost) | "Collaborative wiki and documentation software" |
| [Evernote](https://evernote.com) | "Remember everything and tackle any project with your notes, tasks, and schedule all in one place" (Closed source) |
| [flatnotes](https://github.com/dullage/flatnotes) | "Database-less note-taking web app that utilises a flat folder of markdown files" |
| [Foam](https://github.com/foambubble/foam) | "A personal knowledge management and sharing system for VSCode" |
| [HedgeDoc](https://github.com/hedgedoc/hedgedoc) | "Web-based, self-hosted, collaborative markdown editor" |
| [Hypothesis](https://web.hypothes.is) | "Collaboratively annotate the web" (Closed source) |
| [Joplin](https://github.com/laurent22/joplin) | "Privacy-focused note taking app with sync capabilities for Windows, macOS, Linux, Android and iOS" |
| [Jot](https://github.com/shashwatah/jot) | "Rapid note management for the terminal" |
| [Memos](https://github.com/usememos/memos) | "The pain-less way to create your meaningful notes. Your Notes, Your Way" |
| [Monica](https://github.com/monicahq/monica?tab=readme-ov-file#principles) | "Personal relationship CRM" |
| [nb](https://github.com/xwmx/nb) | "Note‑taking, bookmarking, and archiving with linking, tagging, filtering .. + more" |
| [Notion](https://www.notion.so) | "Write. Plan. Collaborate. With a little help from AI" (Closed source) |
| [Notional Velocity](https://notational.net) ([Source](https://github.com/scrod/nv)) | Introduced ideas that are now more commonplace. Such as "searching for notes is not a separate action; rather, it is the primary interface" |
| [nvpy](https://github.com/cpbotha/nvpy) | "Simplenote syncing note-taking application, inspired by Notational Velocity and ResophNotes, but uglier and cross-platformerer" |
| [Obsidian](https://obsidian.md) | "With thousands of plugins and themes, you can shape Obsidian to fit your way of thinking" (Closed source) |
| [Org-Mode](https://orgmode.org/features.html) | Support Clocking, Capture, and Task/Agenda |
| [Org-Roam](https://github.com/org-roam/org-roam) | "Rudimentary Roam replica with Org-mode" |
| [Outline](https://github.com/outline/outline) | "The fastest knowledge base for growing teams. Beautiful, realtime collaborative, feature packed, and markdown compatible." |
| [Pinboard](https://pinboard.in/about/) | "One of the oldest independently run businesses on the web" with a text-first UI |
| [Rnote](https://github.com/flxzt/rnote) | "Sketch and take handwritten notes" |
| [Roam Research](https://roamresearch.com) | "As easy to use as a document. As powerful as a graph database. Roam helps you organize your research for the long haul" (Closed source) |
| [Silicon Notes](https://github.com/cu/silicon) | "A web-based personal knowledge base with few frills" |
| [SimpleNote by Automatic](https://simplenote.com) | "All your notes, synced on all your devices" (Closed source) |
| [Siyuan](https://github.com/siyuan-note/siyuan) | "Fine-grained block-level reference and Markdown WYSIWYG" |
| [Standard Notes](https://github.com/standardnotes/server) | "Secure note-taking app" |
| [Textpod](https://github.com/freetonik/textpod) | "Inspired by 'One Big Text File' idea" |
| [TiddlyWiki](https://github.com/TiddlyWiki/TiddlyWiki5) | "A unique non-linear notebook for capturing, organising and sharing complex information" |
| [Trillium Next Notes](https://github.com/TriliumNext/Notes/) | "Hierarchical note taking application with focus on building large personal knowledge bases" |
| [Untitled](https://github.com/12joan/untitled-note) | "An open-source app for taking notes that feels awesome to use" |
| [Zettlr](https://github.com/Zettlr/Zettlr) | "One-Stop Publication Workbench" |
| _["Awesome" List of Note Taking Software](https://github.com/tehtbl/awesome-note-taking)_ | "A curated list of awesome note-taking software" |
| _[Digital Gardens](https://github.com/MaggieAppleton/digital-gardeners)_ | "Resources, links, projects, and ideas for gardeners tending their digital notes on the public interwebs" |
| Open Source hosted on [Pika Pods](https://www.pikapods.com/apps#notes) | Supports self-hosting of Memos, [linkding](https://github.com/sissbruecker/linkding), etc. |

## Installation

1. Run `echo '[env]\nMISE_ENV = "hk"' > mise.local.toml`
1. Then run `mise install` and `hk` (`brew install mise hk`)
2. Validate with `mise run format ::: test`

## Goals

![./assets/shears.webp](./assets/shears.webp)

1. Opinionated. This is my personal app and the design choices are what works for me.

    1. For example, tagging is intentionally limited in favor of search and bi-directional linking as [better explained here](https://blog.bityard.net/articles/2022/December/the-design-of-silicon-notes-with-cartoons).
1. Limited features. Having few features is the goal, for maintainability and usability.

## Features

- There is a CLI and API for local search, creation, and general management
- Content is stored in files using the `djot` markup language

    - The files can be edited in any editor (nvim, emacs, VSCode, NotePad++, etc.)
    - They can be synced using [Rclone](https://github.com/rclone/rclone), [rsync](https://jenkov.com/tutorials/rsync/detecting-file-differences.html), [Gofile](https://gofile.io/home), [Syncthing](https://syncthing.net/), [Dropbox](https://www.dropbox.com), [Apple iCloud](https://www.icloud.com), [hyperdrive](https://github.com/holepunchto/hyperdrive), [iroh](https://github.com/n0-computer/iroh), [any-sync](https://github.com/anyproto/tech-docs), etc.
- Each note is named by the creation timestamp to be unique, predictable, and easier to permalink

### Details

{% In Progress %}

- _subDir/Context_ ("Yak Pen"): set via environment variable or argument

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
- What is the story for planning? For example, there are time-sensitive tasks, but they can't start today? Maybe `start-date` and `hard-deadline` (and `soft-deadline`)?
- What about a concept of a `bookmarklet note` that is managed by a browser extension? This way bookmarked tabs can be archived more easily rather than clutter the bookmarks bar?
