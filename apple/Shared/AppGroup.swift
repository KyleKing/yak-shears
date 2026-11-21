import Foundation
import YakShearsKit

/// The container the app and its extensions share. Compiled into each target that
/// needs it, since an extension cannot link the app.
enum AppGroup {
    static let identifier = "group.me.kyleking.yakshears"

    /// Captures from extensions, waiting for the app to move them into the vault.
    /// Nil when the entitlement is missing (an unsigned simulator build, say).
    static var inbox: Inbox? {
        FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: identifier)
            .map { Inbox(root: $0.appending(path: "Inbox", directoryHint: .isDirectory)) }
    }
}
