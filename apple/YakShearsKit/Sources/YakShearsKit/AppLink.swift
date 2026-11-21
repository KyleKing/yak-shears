import Foundation

/// The app's `yakshears://` URLs, used by widgets and controls, which cannot call
/// into the app and can only open a URL.
public enum AppLink: Equatable, Sendable {
    /// Open a yak in the editor.
    case open(path: String)
    /// Start a new, empty yak, optionally in a category.
    case new(category: String?)

    public static let scheme = "yakshears"

    public var url: URL {
        var components = URLComponents()
        components.scheme = Self.scheme
        switch self {
        case .open(let path):
            components.host = "open"
            components.queryItems = [URLQueryItem(name: "path", value: path)]
        case .new(let category):
            components.host = "new"
            components.queryItems = category.map { [URLQueryItem(name: "category", value: $0)] }
        }
        return components.url!
    }

    public init?(url: URL) {
        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false), components.scheme == Self.scheme else {
            return nil
        }
        let query = { (name: String) in components.queryItems?.first { $0.name == name }?.value }
        switch components.host {
        case "open":
            guard let path = query("path"), !path.isEmpty else { return nil }
            self = .open(path: path)
        case "new":
            self = .new(category: query("category"))
        default:
            return nil
        }
    }
}

/// The few newest yaks, as the app hands them to its widgets through the App Group.
public struct RecentYaks: Codable, Equatable, Sendable {
    public struct Entry: Codable, Equatable, Sendable {
        public let path: String
        public let title: String
        public let category: String?
        public let modified: Date
    }

    public let entries: [Entry]
    /// Yaks still carrying conflict markers, which the widget flags.
    public let conflicts: Int

    public static let fileName = "recent-yaks.json"
    public static let limit = 8

    public init(summaries: [YakSummary], conflicts: Int) {
        // Newest by edit, not by name: a widget shows what was touched lately.
        entries = summaries.sorted { $0.modified > $1.modified }.prefix(Self.limit).map {
            Entry(path: $0.path, title: $0.title, category: $0.category, modified: $0.modified)
        }
        self.conflicts = conflicts
    }

    public func write(to directory: URL) throws {
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        try JSONEncoder().encode(self).write(to: directory.appending(path: Self.fileName), options: .atomic)
    }

    public static func read(from directory: URL) -> RecentYaks? {
        guard let data = try? Data(contentsOf: directory.appending(path: fileName)) else { return nil }
        return try? JSONDecoder().decode(RecentYaks.self, from: data)
    }
}
