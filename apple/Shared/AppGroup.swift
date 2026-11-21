import Foundation
import YakShearsKit

/// The container the app and its extensions share. Compiled into each target that
/// needs it, since an extension cannot link the app.
enum AppGroup {
    static let identifier = "group.me.kyleking.yakshears"

    /// The shared container. Nil when the entitlement is missing (an unsigned
    /// simulator build, or macOS, which has no extensions yet).
    static var container: URL? {
        FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: identifier)
    }

    /// Captures from extensions, waiting for the app to move them into the vault.
    static var inbox: Inbox? {
        container.map { Inbox(root: $0.appending(path: "Inbox", directoryHint: .isDirectory)) }
    }
}
