import Foundation
import Observation
import YakShearsKit

/// The list's view of the local vault.
///
/// Reads happen off the main actor so a large vault never blocks the first frame;
/// the list draws immediately and fills in once the walk finishes.
@MainActor @Observable
final class Library {
    /// `Documents/Vault`, which iOS shows under "On My iPhone > Yak Shears" in the Files
    /// app (`UIFileSharingEnabled`), so yaks can be copied in by hand until sync lands.
    static var defaultRoot: URL {
        URL.documentsDirectory.appending(path: "Vault", directoryHint: .isDirectory)
    }

    let vault: Vault
    private(set) var summaries: [YakSummary] = []
    private(set) var hasLoaded = false
    private(set) var loadError: String?

    init(vault: Vault) {
        self.vault = vault
    }

    func reload() async {
        let vault = vault
        do {
            try FileManager.default.createDirectory(at: vault.root, withIntermediateDirectories: true)
            summaries = try await Task.detached(priority: .userInitiated) { try vault.summaries() }.value
            loadError = nil
        } catch {
            loadError = error.localizedDescription
        }
        hasLoaded = true
    }

    func content(of summary: YakSummary) async throws -> String {
        let vault = vault
        return try await Task.detached(priority: .userInitiated) { try vault.read(summary.path) }.value
    }
}
