import SwiftUI
import YakShearsKit

/// Every yak in the local vault, newest first, with the selected one beside it on
/// wide screens and pushed on top of it on a phone.
struct YakListView: View {
    @Environment(Library.self) private var library
    @State private var selection: YakSummary.ID?

    var body: some View {
        NavigationSplitView {
            List(library.summaries, selection: $selection) { summary in
                YakRow(summary: summary)
            }
            .navigationTitle("Yaks")
            .overlay { emptyState }
            .refreshable { await library.reload() }
        } detail: {
            if let summary = library.summaries.first(where: { $0.id == selection }) {
                YakDetailView(summary: summary)
            } else {
                ContentUnavailableView("No Yak Selected", systemImage: "doc.text")
            }
        }
        .task { await library.reload() }
    }

    @ViewBuilder private var emptyState: some View {
        if let error = library.loadError {
            ContentUnavailableView("Couldn't Read the Vault", systemImage: "exclamationmark.triangle", description: Text(error))
        } else if library.hasLoaded && library.summaries.isEmpty {
            ContentUnavailableView(
                "No Yaks Yet",
                systemImage: "tray",
                description: Text("Copy .dj files into Yak Shears › Vault in the Files app, then pull to refresh.")
            )
        }
    }
}

private struct YakRow: View {
    let summary: YakSummary

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(summary.title)
                .lineLimit(1)
            HStack(spacing: 6) {
                if let category = summary.category {
                    Text(category)
                }
                Text(summary.created ?? summary.modified, format: .relative(presentation: .named))
            }
            .font(.caption)
            .foregroundStyle(.secondary)
            .lineLimit(1)
        }
    }
}
