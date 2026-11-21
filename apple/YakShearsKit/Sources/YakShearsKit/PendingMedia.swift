import Foundation

/// Photos and videos added on this device that the server has not received yet.
///
/// The server transcodes media and names it by content hash, so the real embed
/// (`![alt](/media/<category>/<hash>.jpg)`) only exists after an upload. Until then
/// the yak holds a placeholder that names a queued file, and the sync engine holds
/// that yak back. Each sync uploads what it can, swaps the placeholder for the
/// server's URL, and only then lets the yak sync. Adding media offline just waits
/// for the network.
///
/// The server files media by the yak's category, so a yak at the vault root cannot
/// hold media; callers put media yaks in a category.
public struct PendingMedia: Sendable {
    /// The scheme of a placeholder link; any yak containing it waits for media.
    public static let scheme = "pending-media:"

    public struct Item: Equatable, Sendable {
        public let id: String
        /// The yak the media belongs to; the server files media by its category.
        public let yakPath: String
        public let filename: String
        public let file: URL

        public var placeholder: String { "\(PendingMedia.scheme)\(id)" }
    }

    public let root: URL

    public init(root: URL) {
        self.root = root
    }

    /// Queue `data` for upload and return the Djot embed to put in the yak now.
    public func enqueue(_ data: Data, filename: String, for yakPath: String) throws -> String {
        let id = UUID().uuidString.lowercased()
        let folder = root.appending(path: id, directoryHint: .isDirectory)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        try data.write(to: folder.appending(path: Self.safeName(filename)), options: .atomic)
        try Data(yakPath.utf8).write(to: folder.appending(path: Self.yakFile), options: .atomic)
        let alt = (filename as NSString).deletingPathExtension
        return "![\(alt.isEmpty ? "attachment" : alt)](\(Self.scheme)\(id))"
    }

    /// Everything still waiting, oldest first.
    public func items() -> [Item] {
        let folders = (try? FileManager.default.contentsOfDirectory(
            at: root, includingPropertiesForKeys: [.creationDateKey], options: [.skipsHiddenFiles]
        )) ?? []
        return folders.compactMap { folder -> (Date, Item)? in
            guard let yakPath = try? String(contentsOf: folder.appending(path: Self.yakFile), encoding: .utf8),
                  let file = try? FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil)
                    .first(where: { $0.lastPathComponent != Self.yakFile })
            else { return nil }
            let created = (try? folder.resourceValues(forKeys: [.creationDateKey]).creationDate) ?? .distantPast
            return (created, Item(id: folder.lastPathComponent, yakPath: yakPath, filename: file.lastPathComponent, file: file))
        }
        .sorted { $0.0 < $1.0 }
        .map(\.1)
    }

    /// The server has the media: point the yak at it and drop the queued copy.
    ///
    /// Only the link target changes, so alt text edited on this device in the
    /// meantime survives.
    public func resolve(_ item: Item, url: String, in vault: Vault) throws {
        if let content = try? vault.read(item.yakPath) {
            try vault.write(item.yakPath, content: content.replacingOccurrences(of: item.placeholder, with: url))
        }
        try FileManager.default.removeItem(at: item.file.deletingLastPathComponent())
    }

    /// Drop media whose yak is gone, so a deleted yak's photo is never uploaded.
    public func discard(_ item: Item) throws {
        try FileManager.default.removeItem(at: item.file.deletingLastPathComponent())
    }

    private static let yakFile = ".yak"

    /// The server accepts only `[A-Za-z0-9._-]` in an upload's name.
    static func safeName(_ filename: String) -> String {
        let allowed = Set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
        let cleaned = String(filename.map { allowed.contains($0) ? $0 : "-" })
        return cleaned.isEmpty || cleaned.hasPrefix(".") ? "attachment" + cleaned : cleaned
    }
}
