"""Example code for working with macnotesapp.

Based on: https://github.com/RhetTbull/macnotesapp

```sh
uv sync
uv run note_import.py
# Creates local directory `./notes-export`
```

"""

import shutil
from datetime import UTC, datetime
from pathlib import Path

from macnotesapp import NotesApp, Note


def instant(moment: datetime) -> datetime:
    """Anchor one of Notes' naive local timestamps to a real instant.

    AppleScript reports dates in the exporting machine's zone with no offset,
    so the same note exports under different names from different machines.
    """
    return moment.astimezone()


def save(out_dir: Path, note: Note) -> None:
    print(f"Saving: {note.name}")
    content = f""": id={note.id}\\
: creation_date={instant(note.creation_date).isoformat()}\\
: modification_date={instant(note.modification_date).isoformat()}\\
: name={note.name}\\
: folder={note.folder}\\
: account={note.account}\\

````` =html
{note.body.strip()}
`````

***

{note.plaintext}
"""

    ts = instant(note.creation_date).astimezone(UTC).strftime("%Y-%m-%dT%H_%M_%SZ")
    (out_dir / f"{ts}.dj").write_text(content)


def main(pth: Path) -> None:
    # NotesApp() provides interface to Notes.app
    notesapp = NotesApp()
    # Get list of notes (Note objects for each note)
    notes = notesapp.notes()

    out_dir = pth / "notes-export"
    if out_dir.is_dir():
        shutil.rmtree(out_dir)
    out_dir.mkdir()

    for note in notes:
        save(out_dir, note)


if __name__ == "__main__":
    main(Path.cwd().absolute())
