# Yak Shears

Just yak shaving to create my personal note taking app. You probably want to use one of these instead:

| Service | Notes |
| --- | --- |
| [Obsidian](https://obsidian.md) | |
| [Joplin](https://joplinapp.org) | Open source note-taking app |
| [Evernote](https://evernote.com) | |
| [Notion](https://www.notion.so) | |
| [Notional Velocity](https://notational.net) ([Source](https://github.com/scrod/nv))| Introduced ideas that are now more commonplace. Such as "searching for notes is not a separate action; rather, it is the primary interface" |
| [nvpy](https://github.com/cpbotha/nvpy) | |
| [DayOne](https://dayoneapp.com) | Beautiful daily journaling mobile and web app |
| [Hypothesis](https://web.hypothes.is) | Collaboratively annotate the web |
| [Monica](https://github.com/monicahq/monica?tab=readme-ov-file#principles) | "Personal relationship CRM" |
| [SimpleNotes](https://simplenote.com) | |
| [Memos](https://www.usememos.com) | Twitter-like private note taking app |
| Open Source hosted on [Pika Pods](https://www.pikapods.com/apps#notes) | Includes Memos, [linkding](https://github.com/sissbruecker/linkding), etc. |

## Goals

1. Opinionated. This is my personal app and the design choices are what works for me.

    1. For example, tagging is intentionally limited because selecting the right tag and tagging older notes as the list changes is not an effective use of time. Instead, search and bi-directional linking are prioritized.
1. Limited features. Having few features is the goal, both for maintainability and focus.
1. Small composable tools rather than a walled garden/plugin ecosystem.

## Features

- Content is stored in files using the `djot` markup language rather than some flavor of markdown

    - The files can be edited in any editor (nvim, emacs, VSCode, NotePad++, etc.)
    - They can be synced using SyncThing, DropBox, iCloud, rsync, etc. or other service of choice
    - Notes can be captured on the go and synced later using Notes.app ([pulled with `notes`](https://github.com/RhetTbull/macnotesapp)), SimpleNote ([via the Simperium Data Sync Service](https://simperium.com/docs/websocket)), etc.
- Additional magic will be possible with `duckdb` and composable tooling

## Implementation Prioritization

- _Subfolder/Context_ ("Yak Pen"): set via environment variable or argument

    - `shears new (evergreen|personal|work)?`
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
