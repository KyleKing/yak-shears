### README Details

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

### Other

>> And see updated notes in Concepts App adapted from:

    Planning >> Metadata: Address/GPS/Location? Time Range: [0.25, 4]? Cost: ($, $$, $$$, ...)? Must-See: bool? Category: Musuem, Restaurant (Breakfast/Lunch/Dinner?), etc.? Best time of day? Dates: [12Mar2026, ...] (if recurring or one-day)? >> then allow for dynamical calendar scheduling and looking up nearby places on the fly

    Separate notes tracking daylong trips where we saw some of these places as a way to check them off?
