import Foundation
import YakShearsKit

extension Vault {
    /// `Documents/Vault`, which iOS shows under "On My iPhone > Yak Shears" in the
    /// Files app (`UIFileSharingEnabled`).
    static let app = Vault(root: URL.documentsDirectory.appending(path: "Vault", directoryHint: .isDirectory))
}

extension PendingMedia {
    /// Photos and videos waiting to upload. Outside the vault, so a queued original
    /// never shows up in the Files app or gets mistaken for an attachment.
    static let app = PendingMedia(root: URL.applicationSupportDirectory.appending(path: "PendingMedia", directoryHint: .isDirectory))
}
