import Foundation
import Observation
import YakShearsKit

/// The list's view of the local vault, and the sync that keeps it current.
///
/// Reads happen off the main actor so a large vault never blocks the first frame;
/// the list draws from local files immediately and sync runs after.
@MainActor @Observable
final class Library {
    /// The one library in the process. The app's views and its App Intents share it,
    /// so an intent's sync can never run alongside the app's on the same base file.
    static let shared = Library(vault: .app)

    /// A yak the app was asked to show (by an intent, a Spotlight result, or a new
    /// capture); the list selects it and clears this.
    var requestedPath: String?

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

    /// File what extensions captured while the app was away. Shared items land in
    /// the vault root, named for when they were shared.
    func drainInbox() {
        do {
            try AppGroup.inbox?.drain(into: vault, category: nil)
        } catch {
            loadError = error.localizedDescription
        }
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
            let report = try await SyncEngine(vault: vault, client: client, stateURL: stateURL, media: .app).sync()
            syncStatus = .synced(at: .now, report: report)
        } catch SyncError.unauthorized {
            account.tokenWasRejected()
            syncStatus = .failed("Signed out by the server. Sign in again to sync.")
        } catch {
            syncStatus = .failed(error.localizedDescription)
        }
        await reload()
    }

    /// Create an empty yak and return its path. If its editor closes with nothing
    /// written, `discardIfAbandoned` deletes it, so an abandoned "New" leaves nothing.
    func createYak(in category: String?) async -> String? {
        do {
            let path = try vault.create(in: category)
            freshYaks.insert(path)
            await reload()
            return path
        } catch {
            loadError = error.localizedDescription
            return nil
        }
    }

    /// Delete a yak locally; the next sync deletes it on the server, provided the
    /// server still has the version this device last saw.
    func delete(_ summary: YakSummary) {
        try? vault.delete(summary.path)
        summaries.removeAll { $0.id == summary.id }
        unresolved.remove(summary.path)
    }

    /// Yaks created on this device and not yet closed, the only ones an empty editor
    /// may discard. Clearing an existing yak's text is an edit, not a delete.
    @ObservationIgnored private var freshYaks: Set<String> = []

    /// Called when an editor closes: drop a new yak that was never written in.
    func discardIfAbandoned(_ summary: YakSummary, text: String) {
        guard freshYaks.remove(summary.path) != nil, text.isEmpty else { return }
        delete(summary)
    }

    /// Category directories for the "New" menu, from the yaks already listed.
    var categories: [String] {
        Set(summaries.compactMap(\.category)).sorted()
    }

    @ObservationIgnored private var pendingSync: Task<Void, Never>?

    /// Sync once things go quiet: each request restarts the wait, so a burst of
    /// saves while typing becomes one sync a few seconds after the last keystroke.
    func requestSync(with account: Account, after delay: Duration = .seconds(3)) {
        pendingSync?.cancel()
        pendingSync = Task {
            try? await Task.sleep(for: delay)
            guard !Task.isCancelled else { return }
            await sync(with: account)
        }
    }

    func content(of summary: YakSummary) async throws -> String {
        let vault = vault
        return try await Task.detached(priority: .userInitiated) { try vault.read(summary.path) }.value
    }
}
