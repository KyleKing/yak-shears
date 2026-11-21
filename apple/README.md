# Yak Shears for iOS and macOS

A native client that keeps its own copy of the vault as plain `.dj` files and, from a later PR in the stack, syncs it with the server over `/api/v1` (see the "Sync API" section of `AGENTS.md`). The plan and the order of the stacked PRs are in `docs/PLAN.md` under "Native iOS and macOS app".

## Layout

```
apple/
├── project.yml        # XcodeGen spec; the .xcodeproj is generated, never committed
├── ExportOptions.plist# TestFlight upload settings used by CI
├── YakShears/         # SwiftUI app (iOS 26, macOS 26)
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

Until sync lands, the app reads whatever is in its `Vault` folder. On iPhone that folder appears in the Files app under On My iPhone › Yak Shears › Vault, so you can copy notes in from the Syncthing folder to try the list.

## CI and TestFlight

`.github/workflows/apple.yml` runs on every PR that touches `apple/`, stacked PRs included. It tests the package, generates the project, and builds for the iOS Simulator and macOS without signing.

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
