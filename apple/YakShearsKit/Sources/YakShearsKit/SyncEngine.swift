import Foundation

/// What one sync did.
public struct SyncReport: Equatable, Sendable {
    public var downloaded: [String] = []
    public var uploaded: [String] = []
    public var deleted: [String] = []
    /// Yaks now carrying conflict markers, waiting for the reader.
    public var conflicted: [String] = []
    /// Yaks held back because they still carry markers from an earlier conflict.
    public var unresolved: [String] = []
    /// Yaks held back because their photos or videos have not reached the server.
    public var waitingOnMedia: [String] = []
    /// Media uploaded this sync, as the server URLs now in the yaks.
    public var mediaUploaded: [String] = []
    /// Yaks that could not be synced this time (a hand-named new yak the server
    /// refuses, a file that could not be read), with the reason. The rest still ran.
    public var failed: [String: String] = [:]

    public init() {}
}

/// Reconciles the local vault with the server.
///
/// The only state it keeps besides the files is each yak's lease as of the last
/// sync (the base), in a JSON file outside the vault. Comparing the file's lease and
/// the server's to the base says which side changed, so the server stays the single
/// writer to the real vault and nothing is overwritten without its version check.
public actor SyncEngine {
    public let vault: Vault
    private let client: SyncClient
    private let baseURL: URL

    /// - Parameter stateURL: Where the base leases are kept. Keep it outside the
    ///   vault, so it is never mistaken for a yak or exposed in the Files app.
    private let media: PendingMedia?

    /// - Parameter media: Where photos and videos wait for upload; nil when this
    ///   device never adds media.
    public init(vault: Vault, client: SyncClient, stateURL: URL, media: PendingMedia? = nil) {
        self.vault = vault
        self.client = client
        self.baseURL = stateURL
        self.media = media
    }

    public func sync() async throws -> SyncReport {
        var report = SyncReport()
        try await uploadMedia(report: &report)

        let remote = try await client.manifest()
        let (local, unresolved) = try vault.leases()
        let waiting = Set(media?.items().map(\.yakPath) ?? []).intersection(local.keys)
        var base = loadBase()
        defer { saveBase(base) }

        report.unresolved = unresolved.sorted()
        report.waitingOnMedia = waiting.sorted()
        let actions = SyncPlanner.plan(
            local: local, remote: Dictionary(uniqueKeysWithValues: remote.map { ($0.path, $0.lease) }), base: base,
            held: unresolved.union(waiting)
        )
        for action in actions {
            do {
                try await apply(action, base: &base, report: &report)
            } catch SyncError.unauthorized {
                // Every later request would fail the same way; stop and ask to sign in.
                throw SyncError.unauthorized
            } catch {
                report.failed[action.path] = Self.describe(error)
            }
        }
        return report
    }

    private func apply(_ action: SyncAction, base: inout [String: String], report: inout SyncReport) async throws {
        switch action {
        case .download(let path):
            let (content, lease) = try await client.fetch(path)
            try vault.write(path, content: content)
            base[path] = lease
            report.downloaded.append(path)

        case .upload(let path, let replacing):
            let content = try vault.read(path)
            do {
                base[path] = try await upload(path, content: content, replacing: replacing)
                report.uploaded.append(path)
            } catch let SyncError.conflict(current, lease) {
                // The server moved on since the plan was made, or already had a yak here.
                try weave(path, theirs: current, theirLease: lease, mine: content, base: &base, report: &report)
            }

        case .deleteLocal(let path):
            try vault.delete(path)
            base[path] = nil
            report.deleted.append(path)

        case .deleteRemote(let path, let replacing):
            do {
                try await client.delete(path, replacing: replacing)
                report.deleted.append(path)
                base[path] = nil
            } catch SyncError.notFound {
                base[path] = nil
            } catch let SyncError.conflict(current, lease) {
                // Edited on the server after this device deleted it: the edit wins.
                try vault.write(path, content: current)
                base[path] = lease
                report.downloaded.append(path)
            }

        case .adopt(let path, let lease):
            base[path] = lease

        case .conflict(let path):
            let (theirs, lease) = try await client.fetch(path)
            try weave(path, theirs: theirs, theirLease: lease, mine: vault.read(path), base: &base, report: &report)

        case .forget(let path):
            base[path] = nil
        }
    }

    /// Upload queued media and point each yak at the server's copy. Media whose
    /// yak was deleted is dropped; a failed upload stays queued for the next sync.
    private func uploadMedia(report: inout SyncReport) async throws {
        guard let media else { return }
        for item in media.items() {
            guard (try? vault.read(item.yakPath)) != nil else {
                try? media.discard(item)
                continue
            }
            do {
                let data = try Data(contentsOf: item.file)
                let url = try await client.uploadMedia(data, filename: item.filename, for: item.yakPath)
                try media.resolve(item, url: url, in: vault)
                report.mediaUploaded.append(url)
            } catch SyncError.unauthorized {
                throw SyncError.unauthorized
            } catch {
                report.failed[item.yakPath] = Self.describe(error)
            }
        }
    }

    /// Update, falling back to a create when the server no longer has the yak.
    private func upload(_ path: String, content: String, replacing: String?) async throws -> String {
        guard let replacing else {
            return try await client.create(path, content: content)
        }
        do {
            return try await client.update(path, content: content, replacing: replacing)
        } catch SyncError.notFound {
            // Deleted on the server while edited here: recreate it rather than lose the edit.
            return try await client.create(path, content: content)
        }
    }

    /// Write both versions into the local file with conflict markers, and record the
    /// server's lease as the base, so the resolved text uploads as a normal update.
    private func weave(
        _ path: String, theirs: String, theirLease: String, mine: String,
        base: inout [String: String], report: inout SyncReport
    ) throws {
        try vault.write(path, content: ConflictMarkup.weave(theirs: theirs, mine: mine))
        base[path] = theirLease
        report.conflicted.append(path)
    }

    private static func describe(_ error: Error) -> String {
        switch error {
        case SyncError.server(_, let message): message
        case SyncError.notFound: "Not on the server"
        case SyncError.conflict: "Changed on the server during sync"
        default: error.localizedDescription
        }
    }

    private func loadBase() -> [String: String] {
        guard let data = try? Data(contentsOf: baseURL) else { return [:] }
        return (try? JSONDecoder().decode([String: String].self, from: data)) ?? [:]
    }

    private func saveBase(_ base: [String: String]) {
        do {
            try FileManager.default.createDirectory(at: baseURL.deletingLastPathComponent(), withIntermediateDirectories: true)
            try JSONEncoder().encode(base).write(to: baseURL, options: .atomic)
        } catch {
            // Losing the base costs a slower next sync (every yak compares as new and
            // is adopted when equal), never data, so a failed save is not fatal.
        }
    }
}

extension SyncAction {
    var path: String {
        switch self {
        case .download(let path), .upload(let path, _), .deleteLocal(let path), .deleteRemote(let path, _),
             .adopt(let path, _), .conflict(let path), .forget(let path):
            path
        }
    }
}
