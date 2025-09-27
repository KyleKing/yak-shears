# Yak Shears

My personal note taking app, but you probably want to use one of these primarily open-source applications instead:

| Service                                                                                   | Notes                                                                                                                                       |
| ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| [Archivy](https://github.com/archivy/archivy)                                             | "Self-hostable knowledge repository"                                                                                                        |
| [Bear](https://bear.app)                                                                  | "Markdown notes you’ll love" (Closed source)                                                                                                |
| [bookmarker](https://github.com/dellsystem/bookmarker)                                    | "Personal project to help me retain information from books"                                                                                 |
| [Buku](https://github.com/jarun/buku)                                                     | "Personal mini-web in text"                                                                                                                 |
| [DayOne](https://dayoneapp.com)                                                           | "Beautiful daily journaling mobile and web app" (Closed source)                                                                             |
| [Docmost](https://github.com/docmost/docmost)                                             | "Collaborative wiki and documentation software"                                                                                             |
| [Evernote](https://evernote.com)                                                          | "Remember everything and tackle any project with your notes, tasks, and schedule all in one place" (Closed source)                          |
| [flatnotes](https://github.com/dullage/flatnotes)                                         | "Database-less note-taking web app that utilises a flat folder of markdown files"                                                           |
| [Foam](https://github.com/foambubble/foam)                                                | "A personal knowledge management and sharing system for VSCode"                                                                             |
| [HedgeDoc](https://github.com/hedgedoc/hedgedoc)                                          | "Web-based, self-hosted, collaborative markdown editor"                                                                                     |
| [Hypothesis](https://web.hypothes.is)                                                     | "Collaboratively annotate the web" (Closed source)                                                                                          |
| [Joplin](https://github.com/laurent22/joplin)                                             | "Privacy-focused note taking app with sync capabilities for Windows, macOS, Linux, Android and iOS"                                         |
| [Jot](https://github.com/shashwatah/jot)                                                  | "Rapid note management for the terminal"                                                                                                    |
| [Memos](https://github.com/usememos/memos)                                                | "The pain-less way to create your meaningful notes. Your Notes, Your Way"                                                                   |
| [Monica](https://github.com/monicahq/monica?tab=readme-ov-file#principles)                | "Personal relationship CRM"                                                                                                                 |
| [nb](https://github.com/xwmx/nb)                                                          | "Note‑taking, bookmarking, and archiving with linking, tagging, filtering .. + more"                                                        |
| [Notion](https://www.notion.so)                                                           | "Write. Plan. Collaborate. With a little help from AI" (Closed source)                                                                      |
| [Notional Velocity](https://notational.net) ([Source](https://github.com/scrod/nv))       | Introduced ideas that are now more commonplace. Such as "searching for notes is not a separate action; rather, it is the primary interface" |
| [nvpy](https://github.com/cpbotha/nvpy)                                                   | "Simplenote syncing note-taking application, inspired by Notational Velocity and ResophNotes, but uglier and cross-platformerer"            |
| [Obsidian](https://obsidian.md)                                                           | "With thousands of plugins and themes, you can shape Obsidian to fit your way of thinking" (Closed source)                                  |
| [Org-Mode](https://orgmode.org/features.html)                                             | Support Clocking, Capture, and Task/Agenda                                                                                                  |
| [Org-Roam](https://github.com/org-roam/org-roam)                                          | "Rudimentary Roam replica with Org-mode"                                                                                                    |
| [Outline](https://github.com/outline/outline)                                             | "The fastest knowledge base for growing teams. Beautiful, realtime collaborative, feature packed, and markdown compatible."                 |
| [Pinboard](https://pinboard.in/about/)                                                    | "One of the oldest independently run businesses on the web" with a text-first UI                                                            |
| [Rnote](https://github.com/flxzt/rnote)                                                   | "Sketch and take handwritten notes"                                                                                                         |
| [Roam Research](https://roamresearch.com)                                                 | "As easy to use as a document. As powerful as a graph database. Roam helps you organize your research for the long haul" (Closed source)    |
| [Silicon Notes](https://github.com/cu/silicon)                                            | "A web-based personal knowledge base with few frills"                                                                                       |
| [SimpleNote by Automatic](https://simplenote.com)                                         | "All your notes, synced on all your devices" (Closed source)                                                                                |
| [Siyuan](https://github.com/siyuan-note/siyuan)                                           | "Fine-grained block-level reference and Markdown WYSIWYG"                                                                                   |
| [Standard Notes](https://github.com/standardnotes/server)                                 | "Secure note-taking app"                                                                                                                    |
| [Textpod](https://github.com/freetonik/textpod)                                           | "Inspired by 'One Big Text File' idea"                                                                                                      |
| [TiddlyWiki](https://github.com/TiddlyWiki/TiddlyWiki5)                                   | "A unique non-linear notebook for capturing, organising and sharing complex information"                                                    |
| [Trillium Next Notes](https://github.com/TriliumNext/Notes/)                              | "Hierarchical note taking application with focus on building large personal knowledge bases"                                                |
| [Untitled](https://github.com/12joan/untitled-note)                                       | "An open-source app for taking notes that feels awesome to use"                                                                             |
| [Zettlr](https://github.com/Zettlr/Zettlr)                                                | "One-Stop Publication Workbench"                                                                                                            |
| _["Awesome" List of Note Taking Software](https://github.com/tehtbl/awesome-note-taking)_ | "A curated list of awesome note-taking software"                                                                                            |
| _[Digital Gardens](https://github.com/MaggieAppleton/digital-gardeners)_                  | "Resources, links, projects, and ideas for gardeners tending their digital notes on the public interwebs"                                   |
| Open Source hosted on [Pika Pods](https://www.pikapods.com/apps#notes)                    | Supports self-hosting of Memos, [linkding](https://github.com/sissbruecker/linkding), etc.                                                  |

## Quick Start

If still interested, these are the high-level commands necessary to run locally

```sh
# Initial Setup
brew install mise uv
uv sync
mise install
hk install --mise

# Formatting
mise run format ::: typecheck
hk run pre-commit --all

# Testing
mise run test
mise run test --snapshot-update
uv run ptw .

# Local Development
uv run yak-shears-users list
uv run serve
mise run dev
```
