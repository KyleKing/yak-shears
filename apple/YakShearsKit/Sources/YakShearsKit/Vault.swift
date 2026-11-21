import Foundation

/// One yak as the list shows it.
public struct YakSummary: Identifiable, Hashable, Sendable {
    /// Vault-relative POSIX path, the same key the server's sync API uses.
    public let path: String
    public let title: String
    /// The directory a yak sits in, or nil for the vault root.
    public let category: String?
    /// The instant the canonical filename encodes, or nil for a hand-named yak.
    public let created: Date?
    public let modified: Date

    public var id: String { path }
}

/// The app's local copy of the vault: plain `.dj` files under one directory.
///
/// Launch reads only this directory, never the network, so the list is on screen
/// before any sync starts.
public struct Vault: Sendable {
    public let root: URL

    public init(root: URL) {
        self.root = root
    }

    /// Every yak, newest filename first, matching the server's listing order.
    ///
    /// Hidden directories (Syncthing's `.stversions`) are skipped, as the server's
    /// manifest skips them.
    public func summaries() throws -> [YakSummary] {
        var summaries: [YakSummary] = []
        for path in try yakPaths() {
            let url = url(for: path)
            let values = try url.resourceValues(forKeys: [.contentModificationDateKey])
            let content = try String(contentsOf: url, encoding: .utf8)
            let directory = (path as NSString).deletingLastPathComponent
            summaries.append(YakSummary(
                path: path,
                title: Title.derive(content: content, fileName: url.lastPathComponent),
                category: directory.isEmpty ? nil : directory,
                created: CanonicalName.date(from: url.deletingPathExtension().lastPathComponent),
                modified: values.contentModificationDate ?? .distantPast
            ))
        }
        return summaries.sorted { lhs, rhs in
            let lhsName = (lhs.path as NSString).lastPathComponent
            let rhsName = (rhs.path as NSString).lastPathComponent
            return lhsName == rhsName ? lhs.path > rhs.path : lhsName > rhsName
        }
    }

    /// A yak's text.
    public func read(_ path: String) throws -> String {
        try String(contentsOf: url(for: path), encoding: .utf8)
    }

    /// Write a yak atomically, creating its category directory if needed.
    public func write(_ path: String, content: String) throws {
        let destination = url(for: path)
        try FileManager.default.createDirectory(at: destination.deletingLastPathComponent(), withIntermediateDirectories: true)
        try Data(content.utf8).write(to: destination, options: .atomic)
    }

    public func delete(_ path: String) throws {
        try FileManager.default.removeItem(at: url(for: path))
    }

    /// The lease of every yak, and which of them still carry conflict markers.
    public func leases() throws -> (leases: [String: String], unresolved: Set<String>) {
        var leases: [String: String] = [:]
        var unresolved: Set<String> = []
        for path in try yakPaths() {
            let content = try read(path)
            leases[path] = Lease.of(content)
            if ConflictMarkup.hasMarkers(content) {
                unresolved.insert(path)
            }
        }
        return (leases, unresolved)
    }

    /// Vault-relative paths of every `.dj` file outside hidden directories.
    func yakPaths() throws -> [String] {
        guard let walker = FileManager.default.enumerator(
            at: root, includingPropertiesForKeys: [.isRegularFileKey], options: [.skipsHiddenFiles]
        ) else { return [] }
        var paths: [String] = []
        for case let url as URL in walker where url.pathExtension == CanonicalName.fileExtension {
            if try url.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile == true {
                paths.append(relativePath(of: url))
            }
        }
        return paths
    }

    /// The file URL for a vault-relative path.
    public func url(for path: String) -> URL {
        root.appending(path: path, directoryHint: .notDirectory)
    }

    private func relativePath(of url: URL) -> String {
        let rootComponents = root.standardizedFileURL.resolvingSymlinksInPath().pathComponents
        let components = url.standardizedFileURL.resolvingSymlinksInPath().pathComponents
        return components.dropFirst(rootComponents.count).joined(separator: "/")
    }
}
