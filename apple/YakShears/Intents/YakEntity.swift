import AppIntents
import YakShearsKit

/// A yak as Shortcuts, Siri, and Spotlight see it.
struct YakEntity: AppEntity {
    static let typeDisplayRepresentation: TypeDisplayRepresentation = "Yak"
    static let defaultQuery = YakQuery()

    /// The vault-relative path, the same key the sync API uses.
    let id: String
    let title: String
    let category: String?

    init(_ summary: YakSummary) {
        id = summary.path
        title = summary.title
        category = summary.category
    }

    var displayRepresentation: DisplayRepresentation {
        DisplayRepresentation(
            title: "\(title)",
            subtitle: category.map { "\($0)" },
            image: .init(systemName: "doc.text")
        )
    }
}

/// Finds yaks by path or by the words in their title and text.
struct YakQuery: EntityStringQuery {
    func entities(for identifiers: [YakEntity.ID]) async throws -> [YakEntity] {
        let wanted = Set(identifiers)
        return try Vault.app.summaries().filter { wanted.contains($0.path) }.map(YakEntity.init)
    }

    func entities(matching string: String) async throws -> [YakEntity] {
        try Vault.app.search(string).prefix(50).map(YakEntity.init)
    }

    /// The newest yaks, offered before anything is typed.
    func suggestedEntities() async throws -> [YakEntity] {
        try Vault.app.summaries().prefix(10).map(YakEntity.init)
    }
}

/// Category choices for the intents' "in" parameter: the directories that already
/// hold yaks.
struct CategoryOptions: DynamicOptionsProvider {
    func results() async throws -> [String] {
        Set(try Vault.app.summaries().compactMap(\.category)).sorted()
    }
}
