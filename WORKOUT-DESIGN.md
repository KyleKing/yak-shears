# Workout planner: outline

Drafted 2026-08-03 from the streams design session. This sharpens the two framings ROADMAP.md and PLAN.md left deferred: workouts as dated notes with structured frontmatter, and the vault as the sync layer. Nothing here is scheduled; it exists so the scope decision has a concrete shape to accept or cut.

## The three note shapes

Each workout is its own yak; a routine orders them; a session logs into a separate completion yak. All three are plain notes and every derived number is a query.

### Workout (`type: workout`)

One unique movement or exercise. The body carries form notes, links, and media (the vault already handles attachments).

```yaml
type: workout
name: Goblet squat
equipment: kettlebell
```

### Routine (`type: routine`)

An ordered program over workouts, with reps and rest. Order is the list order; bi-directionality (which routines use a workout) comes from the index, like streams.

```yaml
type: routine
name: Tuesday strength
schedule: 2/week
sequence:
  - workout: "[[2026-07-01T10_00_00Z]]"
    sets: 3
    reps: 8
    rest: 90
  - workout: "[[2026-07-01T10_02_00Z]]"
    sets: 3
    reps: 12
    rest: 60
```

`schedule` reuses the habits vocabulary verbatim, so a routine gets streaks, earned grace, and the heat row for free from the habits machinery. A routine is a habit whose completion happens to produce a log.

### Session log (`type: workout-log`)

Created by finishing a timer run. One note per session, filename is the session instant as usual, so history is chronological by construction.

```yaml
type: workout-log
routine: "[[2026-06-30T09_00_00Z]]"
completed:
  - workout: "[[2026-07-01T10_00_00Z]]"
    sets: 3
    reps: [8, 8, 6]
    weight: 24
```

Actuals diverge from the plan freely (`reps` as a list, optional `weight`); the plan stays in the routine note and never mutates.

## The timer

The routine page runs the session: current workout large, set counter, a rest countdown that starts when a set is marked done, next workout on deck. One press per set, matching the one-press habit key. Finishing writes the log yak and marks the routine's habit completion in the same action.

Timer state lives in the page (JS), never in files; abandoning a session writes nothing. This is the one surface where client-side state is genuinely required, and it still ends in a single file write.

## Views

- Routine bench: routines with their habit-derived streaks and next-scheduled state, one press to start
- History: logs grouped by routine, actuals against plan (did reps trend up)
- A workout's page shows which routines use it and its recent actuals (backlinks plus a filtered log query)

## Open questions

- Weights and progression: store per-set weight in logs only (above), or also a current working weight in the routine's sequence entries
- Rest semantics: per-entry `rest` (above) versus a routine-level default with overrides
- The iOS question from ROADMAP stands: a phone at the gym with flaky connectivity wants the vault-direct sibling app or offline support; the timer page is the first surface that genuinely suffers without it
- Whether `equipment` and similar workout fields deserve completion/validation (the Phase 3 frontmatter-key mechanic) or stay free text
