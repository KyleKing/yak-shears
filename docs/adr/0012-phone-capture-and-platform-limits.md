# 0012: Phone Capture and What iOS Actually Supports

## Status

Accepted (2026-08-05). Narrows [ADR 0009](./0009-ios-homescreen-app-and-offline.md), which established the manifest, by recording which of the manifest's other members iOS ignores.

## Context

The goal was one-tap capture from a phone: get from a locked screen to a cursor in a new note without walking the app. The obvious mechanism is the manifest's `shortcuts` member, which on Android puts quick actions behind a long press on the icon.

iOS does not implement it. App icon shortcuts, dynamic shortcuts, and widgets are all absent for web apps added to the Home Screen from Safari, and the documented path to Quick Actions runs through publishing a native wrapper to the App Store. Building against `shortcuts` would have shipped nothing to the only phone this app is used on.

That is worth recording rather than rediscovering, because the manifest is a spec whose members are individually optional and Safari's support is not enumerated anywhere authoritative. ADR 0009 established the two members iOS does honour (`display` and `scope`, which is what stops the in-app browser overlay). This one records the rest of the survey.

## Decision

1. No `shortcuts` member. It is dead weight on the target platform.
2. No `share_target`. It is Chrome and Android only, so sharing a URL into a yak from iOS is not reachable this way either.
3. Make `apple-mobile-web-app-title` a per-page template block, so a second Home Screen icon can be added from `/new` and read "New Yak" rather than a second "Yak Shears".

The third is the mechanism that does work on iOS. Any URL can be added to the Home Screen, the manifest's `scope: /` keeps it launching standalone rather than in Safari, and the only thing missing was that every such icon carried the same name.

Capture is then: tap the "New Yak" icon, tap a category, type. Two taps from the Home Screen, against three through the app.

## What iOS supports, as of this record

| Manifest member                | iOS | Note                                                          |
| ------------------------------ | --- | ------------------------------------------------------------- |
| `display: standalone`          | yes | Required, or every navigation opens an in-app browser (ADR 0009) |
| `scope`                        | yes | Declare it explicitly; the default is unreliable               |
| `icons`, `apple-touch-icon`    | yes | `apple-touch-icon` wins when both are present                  |
| `theme_color`                  | yes | Honoured per colour scheme via paired meta tags                |
| `start_url`                    | yes | Applies to the icon created from the app's own page            |
| `shortcuts`                    | no  | The reason this ADR exists                                     |
| `share_target`                 | no  | Android and Chrome only                                        |

Anything not listed was not tested and should not be assumed.

## Options considered

### Option A: a second Home Screen icon pointed at `/new` (chosen)

Costs one template block. Uses a mechanism iOS has supported since long before web app manifests existed, and degrades to a normal bookmark everywhere else.

The cost is that it is user-installed. Nothing in the app can create the icon, so it needs to be documented rather than shipped, and a fresh device needs the step repeated.

### Option B: a `GET /new/quick` that creates a note and redirects into the editor

This is the true one-tap version, and it is the reason it was rejected: a GET with a side effect will be fired by Safari's speculative prefetch and by any link scanner, and each firing leaves an empty note behind. Making it a POST puts a form in the way, which is the tap this was meant to remove.

Revisit only with a mechanism that proves user intent, which on the web means a POST or a token that a prefetch cannot mint.

### Option C: an iOS Shortcut or the Action Button

A Shortcut that opens a URL can be bound to the Action Button, Control Centre, or the Lock Screen, which beats two taps. It needs nothing from the app beyond a stable URL, so it is available today and costs no code.

Not chosen as *the* answer because it is entirely user-side configuration, but it is the best available answer for capture speed and worth documenting alongside the icon.

### Option D: a native wrapper

Unlocks Quick Actions, widgets, and the share sheet. Rejected on the same grounds as the SPA question in ADR 0009: the cost is an App Store presence and a build pipeline for a single-user notes app.

## Consequences

Capture from the Home Screen is two taps and the icon says what it does. Nothing in the app depends on a manifest member iOS ignores.

The Android story is now deliberately unserved. If that changes, `shortcuts` and `share_target` are both additive and neither affects iOS.

The `/new` picker is still the second tap. Reducing it further means either remembering the last category or accepting Option B's prefetch problem, and neither is decided here.
