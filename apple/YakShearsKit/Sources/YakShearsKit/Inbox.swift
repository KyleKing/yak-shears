import Foundation

/// Captures waiting to become yaks, written by extensions that cannot reach the
/// app's own vault (the share sheet), and moved into the vault by the app.
///
/// An extension runs in its own sandbox; the inbox lives in the App Group container
/// both can see. Each capture is a finished `.dj` file, so draining is a move, and a
/// capture made offline or while the app is closed is never lost, only delayed.
public struct Inbox: Sendable {
    public let root: URL

    public init(root: URL) {
        self.root = root
    }

    /// Queue `text` to become a yak, named for the moment it was captured.
    @discardableResult
    public func add(_ text: String, at date: Date = .now) throws -> URL {
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        var instant = date
        while true {
            let file = root.appending(path: "\(CanonicalName.stem(for: instant)).\(CanonicalName.fileExtension)")
            if !FileManager.default.fileExists(atPath: file.path) {
                try Data((text.hasSuffix("\n") ? text : text + "\n").utf8).write(to: file, options: .atomic)
                return file
            }
            instant = instant.addingTimeInterval(1)
        }
    }

    /// Move every queued capture into `vault`, keeping its capture time as its name.
    ///
    /// - Returns: The new yaks' vault-relative paths, oldest first.
    @discardableResult
    public func drain(into vault: Vault, category: String?) throws -> [String] {
        guard let files = try? FileManager.default.contentsOfDirectory(at: root, includingPropertiesForKeys: nil) else {
            return []
        }
        var paths: [String] = []
        for file in files.filter({ $0.pathExtension == CanonicalName.fileExtension }).sorted(by: { $0.lastPathComponent < $1.lastPathComponent }) {
            let captured = CanonicalName.date(from: file.deletingPathExtension().lastPathComponent) ?? .now
            let content = try String(contentsOf: file, encoding: .utf8)
            paths.append(try vault.capture(content, in: category, at: captured))
            try FileManager.default.removeItem(at: file)
        }
        return paths
    }
}

/// Turns what another app shares into yak text.
public enum SharedContent {
    /// A shared page becomes a Djot link under any note the reader typed, with the
    /// page title as the link text when the sharing app supplied one.
    public static func compose(note: String, url: URL?, title: String?) -> String {
        var parts: [String] = []
        let trimmedNote = note.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmedNote.isEmpty {
            parts.append(trimmedNote)
        }
        if let url {
            let label = title?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            parts.append(label.isEmpty ? "<\(url.absoluteString)>" : "[\(escape(label))](\(url.absoluteString))")
        }
        return parts.joined(separator: "\n\n")
    }

    /// Square brackets would end the link text early.
    private static func escape(_ label: String) -> String {
        label.replacingOccurrences(of: "[", with: "\\[").replacingOccurrences(of: "]", with: "\\]")
    }
}
