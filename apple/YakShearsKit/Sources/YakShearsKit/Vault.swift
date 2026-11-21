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

    /// Create an empty yak named for `date`, in `category` or the vault root.
    ///
    /// Two yaks created in the same second would share a name, so the instant moves
    /// forward a second at a time until it is free, which keeps the name canonical
    /// and the listing order true to creation order.
    ///
    /// - Returns: The new yak's vault-relative path.
    @discardableResult
    public func create(in category: String?, at date: Date = .now) throws -> String {
        var instant = date
        while true {
            let name = "\(CanonicalName.stem(for: instant)).\(CanonicalName.fileExtension)"
            let path = category.map { "\($0)/\(name)" } ?? name
            if !FileManager.default.fileExists(atPath: url(for: path).path) {
                try write(path, content: "")
                return path
            }
            instant = instant.addingTimeInterval(1)
        }
    }

    /// Create a yak holding `text`, for captures that arrive from outside the app
    /// (Siri, Shortcuts, the share sheet).
    ///
    /// - Returns: The new yak's vault-relative path.
    @discardableResult
    public func capture(_ text: String, in category: String?, at date: Date = .now) throws -> String {
        let path = try create(in: category, at: date)
        try write(path, content: Self.endingInNewline(text))
        return path
    }

    /// Add `text` as a new paragraph at the end of a yak.
    public func append(_ text: String, to path: String) throws {
        let existing = try read(path)
        let separator = existing.isEmpty ? "" : existing.hasSuffix("\n\n") ? "" : existing.hasSuffix("\n") ? "\n" : "\n\n"
        try write(path, content: existing + separator + Self.endingInNewline(text))
    }

    /// Yaks whose title or text contains every word of `query`, ignoring case and
    /// diacritics, newest first. Title matches rank ahead of body-only matches.
    public func search(_ query: String) throws -> [YakSummary] {
        let words = query.split(whereSeparator: \.isWhitespace).map(String.init)
        let all = try summaries()
        guard !words.isEmpty else { return all }
        func matches(_ haystack: String) -> Bool {
            words.allSatisfy { haystack.range(of: $0, options: [.caseInsensitive, .diacriticInsensitive]) != nil }
        }
        let inTitle = all.filter { matches($0.title) }
        let titled = Set(inTitle.map(\.path))
        let inBody = try all.filter { summary in
            guard !titled.contains(summary.path) else { return false }
            return matches(try read(summary.path))
        }
        return inTitle + inBody
    }

    private static func endingInNewline(_ text: String) -> String {
        text.hasSuffix("\n") ? text : text + "\n"
    }

    /// Save an edit made against the version whose lease is `replacing`.
    ///
    /// A sync can rewrite a yak while it is open. Rather than overwrite what it
    /// downloaded, a save onto a file that moved weaves the two with conflict markers,
    /// the same rule the server applies to every write. A yak deleted underneath the
    /// editor is simply written back, because an edit beats a delete.
    ///
    /// - Returns: The text now on disk (the edit, or the woven conflict) and its lease.
    public func save(_ path: String, content: String, replacing lease: String) throws -> (content: String, lease: String) {
        let saved: String
        if let current = try? read(path), Lease.of(current) != lease {
            saved = ConflictMarkup.weave(theirs: current, mine: content)
        } else {
            saved = content
        }
        try write(path, content: saved)
        return (saved, Lease.of(saved))
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
