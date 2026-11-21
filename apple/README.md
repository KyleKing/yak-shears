# Yak Shears for iOS and macOS

A native client that keeps its own copy of the vault as plain `.dj` files and syncs it with the server over `/api/v1` (see the "Sync API" section of `AGENTS.md`). The plan and the order of the stacked PRs are in `docs/PLAN.md` under "Native iOS and macOS app".

## Layout

```
apple/
├── project.yml        # XcodeGen spec; the .xcodeproj is generated, never committed
├── ExportOptions.plist# TestFlight upload settings used by CI
├── Shared/           # Source compiled into the app and its extensions (App Group)
├── YakShears/         # SwiftUI app (iOS 26, macOS 26)
├── YakShearsShare/    # iOS share extension
├── YakShearsWidgets/  # iOS widgets and Control Center control
└── YakShearsKit/      # Swift package with the logic, no SwiftUI, tested on Linux and macOS
```

Keep logic in `YakShearsKit` and the app target thin. The package builds and tests with a plain `swift test`, including on Linux, so most changes can be verified without Xcode.

## Local development

```sh
brew install xcodegen            # or download the pinned release CI uses (see apple.yml)
xcodegen generate --spec apple/project.yml
open apple/YakShears.xcodeproj   # set your team under Signing & Capabilities, then run
swift test --package-path apple/YakShearsKit
```

Re-run `xcodegen generate` after adding or removing files, or after editing `project.yml`.

The `Vault` folder also appears in the Files app under On My iPhone › Yak Shears › Vault.

To sync against a server on your laptop, run `uv run serve --host 0.0.0.0` and sign in from the phone with `http://<laptop-ip>:8080`. The app allows plain HTTP to local addresses only (`NSAllowsLocalNetworking`).

## Sync

`SyncEngine` keeps one piece of state besides the files: each yak's lease as of the last sync (the *base*), in `Application Support/sync-base-<host>.json`. A lease is a pure function of the text (`Lease.swift` mirrors the server's `yak_lease`), so comparing the file's lease and the server's to the base says which side changed:

| This device | Server    | Result                                                        |
| ----------- | --------- | ------------------------------------------------------------- |
| unchanged   | edited    | download                                                      |
| edited      | unchanged | upload with `If-Match: <base>`                                |
| edited      | edited    | conflict markers in the local file (same as the web editor)  |
| deleted     | edited    | download, because an edit beats a delete                      |
| edited      | deleted   | re-create, because an edit beats a delete                     |

The editor saves to the local vault as you type, half a second after the last keystroke, and requests a sync a few seconds after that. A save also names the lease it started from (`Vault.save`), so a sync that rewrote the open yak gets woven in with markers rather than overwritten.

A yak with conflict markers is never uploaded. Once the markers are removed, it uploads as an ordinary edit. The rules are in `SyncPlan.swift`, and `SyncTests.swift` covers every row.

The integration tests run two simulated devices against the real server:

```sh
uv run python scripts/sync_fixture_server.py --port 8765 &   # throwaway vault and test user
YAK_SHEARS_TEST_SERVER=http://127.0.0.1:8765 swift test --package-path apple/YakShearsKit
```

Without `YAK_SHEARS_TEST_SERVER` those tests are skipped. CI always runs them.

## Siri, Shortcuts, and the Action Button

App Intents in `YakShears/Intents/` need no setup; Siri and Shortcuts find them once the app is installed:

| Action          | Runs without opening the app | Siri phrase                         |
| --------------- | ---------------------------- | ----------------------------------- |
| New Yak         | yes, then syncs              | "New yak in Yak Shears"             |
| Append to Yak   | yes, then syncs              | "Append to a yak in Yak Shears"     |
| Open Yak        | opens the editor             | "Open a yak in Yak Shears"          |
| Start a Yak     | opens a new, empty yak       | "Start a yak in Yak Shears"         |

For one press from the lock screen to typing, set the Action Button (Settings › Action Button › Shortcut) to **Start a Yak**. For capture without looking, set it to **New Yak**, which asks for dictation.

The intents share the app's `Library.shared` and `Account.shared`, so a sync an intent starts can never overlap the app's own.

## Share sheet

`YakShearsShare` is an iOS share extension for text and web links. Use it from Safari or any app's share sheet, add a note, and tap Save. The extension can't reach the app's vault, so it writes a finished `.dj` file into an **inbox** in the App Group container (`group.me.kyleking.yakshears`, see `Shared/AppGroup.swift`). The app files everything in the inbox into the vault root whenever it becomes active, then syncs. Sharing works offline and never waits on the network.

A link becomes `[page title](url)` under your note. Images aren't accepted yet; they need attachment sync, which comes with screenshot-to-yak.

The App Group and the extension's bundle ID (`me.kyleking.yakshears.share`) are registered automatically by the TestFlight job's cloud signing. When running from Xcode, pick your team on both targets.

## Screenshot to yak

Two ways in, both iOS only:

- **New › Import Screenshots…** shows your recent screenshots. Pick any number and tap Import.
- **Yak Latest Screenshot**, a Shortcuts action and Siri phrase. It imports the newest screenshot. Bind it to the Action Button or Back Tap (Settings › Accessibility › Touch › Back Tap) for screenshot-to-note in one gesture.

Each screenshot becomes its own yak in `screenshots/`, named for when it was taken. The yak is titled by the first line of text Vision reads from the image, followed by the image and a `::: screenshot-text` div holding everything recognised. That makes the yak searchable by what the screenshot said. The originals are then deleted from Photos. iOS always asks you to confirm that, and declining keeps them; the yaks are made either way.

Images go through `PendingMedia`, a queue outside the vault. The yak holds a `pending-media:` placeholder until the next sync uploads the image to `/media/upload`. The server converts it to JPEG and returns its URL, which replaces the placeholder. A yak waiting on media is held back from sync like one with conflict markers, so no other device ever sees a placeholder. Importing offline just waits for the network.

## Spotlight

Every yak is indexed with Core Spotlight: its title, full text, category as a keyword, and created and modified dates. System search then finds a yak by anything it says, and tapping a result opens it in the editor. The index updates after each reload with only what changed (`Spotlight/SpotlightIndex.swift`), and deleted yaks are removed.

## Widgets and controls

`YakShearsWidgets` (iOS) adds:

- **Recent Yaks** on the Home Screen (small, medium, large) and the Lock Screen (rectangular). It shows the yaks edited most recently, each opening in the editor. A ⚠️ marks unresolved conflicts, and a pencil starts a new yak.
- **New Yak** on the Lock Screen (circular).
- **New Yak** as a control for Control Center, the Lock Screen's bottom slots, and the Action Button's Controls list.

Widgets can't read the app's Documents, so after each reload the app writes `recent-yaks.json` into the App Group (`RecentYaks`). It asks WidgetKit to redraw only when that snapshot changes, so the widget never polls. Taps come back as `yakshears://open?path=…` and `yakshears://new` (`AppLink`). The control uses the system's `OpenURLIntent`, so the extension runs no app code.

Home-screen icon quick actions are not included. The App Shortcuts from the Siri section already appear in Spotlight and the Shortcuts app, and a static quick-action menu would duplicate them.

## CI and TestFlight

`.github/workflows/apple.yml` runs on every PR that touches `apple/` or the server's sync and auth code, stacked PRs included. It starts the fixture server, tests the package against it, generates the project, and builds for the iOS Simulator and macOS without signing.

The `testflight` job then archives and uploads an iOS build, using the workflow's run number as the build number. It stays skipped, with a notice, until the following one-time setup is done:

1. **Register the bundle ID.** In the Apple Developer portal, under Certificates, IDs & Profiles › Identifiers, add an explicit App ID for `me.kyleking.yakshears`.
2. **Create the app record.** In App Store Connect, under Apps › +, create "Yak Shears" with that bundle ID.
3. **Create an API key.** In App Store Connect, under Users and Access › Integrations › App Store Connect API › Team Keys, generate a key with the **Admin** role. Cloud-managed signing creates the distribution certificate, which lower roles cannot do. Download the `.p8` file; it can only be downloaded once.
4. **Add the repository secrets and variable.** In GitHub, under Settings › Secrets and variables › Actions:

   | Kind     | Name                              | Value                                 |
   | -------- | --------------------------------- | ------------------------------------- |
   | Secret   | `APP_STORE_CONNECT_API_KEY_ID`    | The key ID                            |
   | Secret   | `APP_STORE_CONNECT_API_ISSUER_ID` | The issuer ID shown above the key list |
   | Secret   | `APP_STORE_CONNECT_API_KEY_P8`    | The full contents of the `.p8` file   |
   | Variable | `APPLE_TEAM_ID`                   | Your 10-character team ID             |

5. **Add yourself as a tester.** In TestFlight, add yourself to an internal testing group. Each upload appears in the TestFlight app once App Store Connect finishes processing it, which usually takes 5 to 15 minutes.

`ITSAppUsesNonExemptEncryption` is `false` (the app uses only HTTPS), so builds skip the export compliance question.
