/// What one sync must do for one yak.
public enum SyncAction: Equatable, Sendable {
    /// Bring the server's version down; this device has not changed the yak.
    case download(path: String)
    /// Send this device's version up. `replacing` is the lease the server is expected
    /// to hold, or nil to create the yak there.
    case upload(path: String, replacing: String?)
    /// The server deleted a yak this device had not changed.
    case deleteLocal(path: String)
    /// This device deleted a yak the server had not changed.
    case deleteRemote(path: String, replacing: String)
    /// Both sides now agree; record the shared lease and move on.
    case adopt(path: String, lease: String)
    /// Both sides changed the yak differently. Weave the two with conflict markers
    /// for the reader to resolve; nothing is overwritten.
    case conflict(path: String)
    /// Both sides deleted it; forget it.
    case forget(path: String)
}

/// Decides each yak's action by comparing three leases: the one on this device now,
/// the one on the server now, and the one both agreed on at the last sync (the base).
///
/// A side "changed" when its lease differs from the base. The rules never discard an
/// edit: an edit beats a delete on either side, and two different edits become a
/// conflict rather than a winner.
public enum SyncPlanner {
    /// - Parameters:
    ///   - local: Lease of every yak on this device.
    ///   - remote: Lease of every yak on the server.
    ///   - base: Lease of every yak as of the last successful sync.
    ///   - held: Yaks on this device that must not upload yet: ones still carrying
    ///     conflict markers, and ones waiting for their media to reach the server.
    public static func plan(
        local: [String: String], remote: [String: String], base: [String: String], held: Set<String> = []
    ) -> [SyncAction] {
        let paths = Set(local.keys).union(remote.keys).union(base.keys).sorted()
        return paths.compactMap { path in
            action(path: path, local: local[path], remote: remote[path], base: base[path], held: held.contains(path))
        }
    }

    static func action(path: String, local: String?, remote: String?, base: String?, held: Bool) -> SyncAction? {
        let localChanged = local != base
        let remoteChanged = remote != base

        switch (localChanged, remoteChanged) {
        case (false, false):
            return nil
        case (false, true):
            return remote == nil ? .deleteLocal(path: path) : .download(path: path)
        case (true, false):
            guard let local else {
                // Deleted here, untouched there. A local change to nil implies a base.
                return base.map { .deleteRemote(path: path, replacing: $0) }
            }
            if held { return nil }
            // A base with no remote is impossible here (remote unchanged == base), so
            // `base` is the lease the server holds, or nil for a yak never uploaded.
            return local == remote ? .adopt(path: path, lease: local) : .upload(path: path, replacing: base)
        case (true, true):
            switch (local, remote) {
            case (nil, nil):
                return .forget(path: path)
            case (nil, .some):
                // Deleted here, edited there: the edit wins.
                return .download(path: path)
            case (.some, nil):
                // Edited here, deleted there: recreate it rather than lose the edit.
                return held ? nil : .upload(path: path, replacing: nil)
            case (.some(let local), .some(let remote)):
                if local == remote { return .adopt(path: path, lease: local) }
                return held ? nil : .conflict(path: path)
            }
        }
    }
}
