import Foundation
import Observation
import YakShearsKit

/// The list's view of the local vault, and the sync that keeps it current.
///
/// Reads happen off the main actor so a large vault never blocks the first frame;
/// the list draws from local files immediately and sync runs after.
@MainActor @Observable
final class Library {
    /// `Documents/Vault`, which iOS shows under "On My iPhone > Yak Shears" in the Files
    /// app (`UIFileSharingEnabled`).
    static var defaultRoot: URL {
        URL.documentsDirectory.appending(path: "Vault", directoryHint: .isDirectory)
    }

    enum SyncStatus: Equatable {
        case idle
        case syncing
        case synced(at: Date, report: SyncReport)
        case failed(String)
    }

    let vault: Vault
    private(set) var summaries: [YakSummary] = []
    /// Yaks carrying conflict markers, shown with a badge until resolved.
    private(set) var unresolved: Set<String> = []
    private(set) var hasLoaded = false
    private(set) var loadError: String?
    private(set) var syncStatus: SyncStatus = .idle

    init(vault: Vault) {
        self.vault = vault
    }

    func reload() async {
        let vault = vault
        do {
            try FileManager.default.createDirectory(at: vault.root, withIntermediateDirectories: true)
            let (summaries, unresolved) = try await Task.detached(priority: .userInitiated) {
                (try vault.summaries(), try vault.leases().unresolved)
            }.value
            self.summaries = summaries
            self.unresolved = unresolved
            loadError = nil
        } catch {
            loadError = error.localizedDescription
        }
        hasLoaded = true
    }

    /// Sync with the account's server, then re-read the vault. A no-op when signed
    /// out or when a sync is already running.
    func sync(with account: Account) async {
        guard syncStatus != .syncing, let client = account.client, let stateURL = account.syncStateURL else { return }
        syncStatus = .syncing
        do {
            let report = try await SyncEngine(vault: vault, client: client, stateURL: stateURL).sync()
            syncStatus = .synced(at: .now, report: report)
        } catch SyncError.unauthorized {
            account.tokenWasRejected()
            syncStatus = .failed("Signed out by the server. Sign in again to sync.")
        } catch {
            syncStatus = .failed(error.localizedDescription)
        }
        await reload()
    }

    func content(of summary: YakSummary) async throws -> String {
        let vault = vault
        return try await Task.detached(priority: .userInitiated) { try vault.read(summary.path) }.value
    }
}
