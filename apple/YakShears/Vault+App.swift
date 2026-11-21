import Foundation
import YakShearsKit

extension Vault {
    /// `Documents/Vault`, which iOS shows under "On My iPhone > Yak Shears" in the
    /// Files app (`UIFileSharingEnabled`).
    static let app = Vault(root: URL.documentsDirectory.appending(path: "Vault", directoryHint: .isDirectory))
}
