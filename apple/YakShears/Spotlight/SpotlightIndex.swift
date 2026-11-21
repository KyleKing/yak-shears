import CoreSpotlight
import YakShearsKit

/// Keeps system search in step with the vault: every yak's title and full text,
/// so Spotlight finds a yak by anything it says. Tapping a result opens the app on
/// it (`YakListView` handles the `CSSearchableItemActionType` activity).
///
/// Indexing runs after each reload and sends only what changed since the last pass
/// in this launch; the first pass after launch sends everything, which Spotlight
/// treats as an update for identifiers it already has.
@MainActor
final class SpotlightIndex {
    static let shared = SpotlightIndex()

    nonisolated private static let domain = "yaks"
    private var indexed: [String: Date] = [:]

    func update(with summaries: [YakSummary], vault: Vault) {
        let current = Dictionary(uniqueKeysWithValues: summaries.map { ($0.path, $0.modified) })
        let changed = summaries.filter { indexed[$0.path] != $0.modified }
        let removed = Set(indexed.keys).subtracting(current.keys)
        indexed = current
        guard !changed.isEmpty || !removed.isEmpty else { return }

        Task.detached(priority: .utility) {
            let items = changed.compactMap { summary -> CSSearchableItem? in
                guard let text = try? vault.read(summary.path) else { return nil }
                let attributes = CSSearchableItemAttributeSet(contentType: .text)
                attributes.title = summary.title
                attributes.textContent = text
                attributes.contentDescription = Self.preview(of: text, title: summary.title)
                attributes.contentModificationDate = summary.modified
                attributes.contentCreationDate = summary.created
                if let category = summary.category {
                    attributes.keywords = [category]
                }
                return CSSearchableItem(uniqueIdentifier: summary.path, domainIdentifier: Self.domain, attributeSet: attributes)
            }
            let index = CSSearchableIndex.default()
            if !removed.isEmpty {
                try? await index.deleteSearchableItems(withIdentifiers: Array(removed))
            }
            if !items.isEmpty {
                try? await index.indexSearchableItems(items)
            }
        }
    }

    /// The first lines after the title, for the result's subtitle.
    nonisolated private static func preview(of text: String, title: String) -> String {
        text.split(separator: "\n")
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty && !$0.hasPrefix("---") && !$0.contains(title) }
            .prefix(3)
            .joined(separator: " ")
    }
}
