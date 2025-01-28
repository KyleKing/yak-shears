"""Example code for working with macnotesapp.

Based on: https://github.com/RhetTbull/macnotesapp

"""

import shutil
from pathlib import Path

from macnotesapp import NotesApp, Note


def save(out_dir: Path, note: Note) -> None:
    print(f"Saving: {note.name}")
    content = f""": id={note.id}\\
: creation_date={note.creation_date.isoformat()}\\
: modification_date={note.modification_date.isoformat()}\\
: name={note.name}\\
: folder={note.folder}\\
: account={note.account}\\

````` =html
{note.body.strip()}
`````

***

{note.plaintext}
"""

    ts = note.creation_date.isoformat().replace(":", "_") + "Z"
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
