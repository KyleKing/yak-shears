import SwiftUI
import YakShearsKit

/// Every yak in the local vault, newest first, with the selected one open in the
/// editor beside it on wide screens and pushed on top of it on a phone.
///
/// The list draws from local files first and syncs after, so launch never waits on
/// the network.
struct YakListView: View {
    @Environment(Library.self) private var library
    @Environment(Account.self) private var account
    @Environment(\.scenePhase) private var scenePhase
    @State private var selection: YakSummary.ID?
    @State private var isSigningIn = false

    var body: some View {
        NavigationSplitView {
            List(selection: $selection) {
                ForEach(library.summaries) { summary in
                    YakRow(summary: summary, isUnresolved: library.unresolved.contains(summary.path))
                }
                .onDelete { offsets in
                    for summary in offsets.map({ library.summaries[$0] }) {
                        library.delete(summary)
                    }
                    library.requestSync(with: account)
                }
            }
            .navigationTitle("Yaks")
            .overlay { emptyState }
            .refreshable { await refresh() }
            .safeAreaInset(edge: .bottom) { SyncStatusLine(status: library.syncStatus) }
            .toolbar {
                newYakMenu
                accountMenu
            }
        } detail: {
            if let summary = library.summaries.first(where: { $0.id == selection }) {
                YakEditorView(summary: summary)
            } else {
                ContentUnavailableView("No Yak Selected", systemImage: "doc.text")
            }
        }
        .task {
            await library.reload()
            await library.sync(with: account)
        }
        .onChange(of: library.requestedPath, initial: true) { _, path in
            guard let path else { return }
            Task {
                await library.reload()
                selection = path
                library.requestedPath = nil
            }
        }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active {
                Task { await library.sync(with: account) }
            }
        }
        .sheet(isPresented: $isSigningIn) {
            SignInView { Task { await library.sync(with: account) } }
        }
    }

    private func refresh() async {
        if account.isSignedIn {
            await library.sync(with: account)
        } else {
            await library.reload()
        }
    }

    /// New yaks go into a category, as on the web's /new picker, or the vault root.
    @ToolbarContentBuilder private var newYakMenu: some ToolbarContent {
        ToolbarItem(placement: .primaryAction) {
            Menu {
                ForEach(library.categories, id: \.self) { category in
                    Button(category) { create(in: category) }
                }
                Divider()
                Button("No Category") { create(in: nil) }
            } label: {
                Label("New Yak", systemImage: "square.and.pencil")
            }
        }
    }

    private func create(in category: String?) {
        Task {
            if let path = await library.createYak(in: category) {
                selection = path
            }
        }
    }

    @ToolbarContentBuilder private var accountMenu: some ToolbarContent {
        ToolbarItem {
            Menu {
                if account.isSignedIn, let server = account.server {
                    Text(server.host() ?? server.absoluteString)
                    Button("Sync Now", systemImage: "arrow.triangle.2.circlepath") {
                        Task { await library.sync(with: account) }
                    }
                    Button("Sign Out", systemImage: "rectangle.portrait.and.arrow.right", role: .destructive) {
                        Task { await account.signOut() }
                    }
                } else {
                    Button("Sign In to Sync", systemImage: "person.crop.circle") { isSigningIn = true }
                }
            } label: {
                Label("Account", systemImage: account.isSignedIn ? "person.crop.circle.fill" : "person.crop.circle")
            }
        }
    }

    @ViewBuilder private var emptyState: some View {
        if let error = library.loadError {
            ContentUnavailableView("Couldn't Read the Vault", systemImage: "exclamationmark.triangle", description: Text(error))
        } else if library.hasLoaded && library.summaries.isEmpty {
            if account.isSignedIn {
                ContentUnavailableView("No Yaks Yet", systemImage: "tray", description: Text("Pull to sync."))
            } else {
                ContentUnavailableView {
                    Label("No Yaks Yet", systemImage: "tray")
                } description: {
                    Text("Sign in to sync with your Yak Shears server.")
                } actions: {
                    Button("Sign In") { isSigningIn = true }
                }
            }
        }
    }
}

private struct YakRow: View {
    let summary: YakSummary
    let isUnresolved: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 4) {
                if isUnresolved {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundStyle(.orange)
                        .accessibilityLabel("Has a sync conflict")
                }
                Text(summary.title)
                    .lineLimit(1)
            }
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

/// One line under the list saying when the last sync ran and what needs attention.
private struct SyncStatusLine: View {
    let status: Library.SyncStatus

    var body: some View {
        Group {
            switch status {
            case .idle:
                EmptyView()
            case .syncing:
                Label("Syncing…", systemImage: "arrow.triangle.2.circlepath")
            case .synced(let date, let report):
                if !report.failed.isEmpty {
                    Label("\(report.failed.count) couldn't sync", systemImage: "exclamationmark.triangle")
                } else if !(report.conflicted + report.unresolved).isEmpty {
                    Label("Conflicts to resolve", systemImage: "exclamationmark.triangle")
                } else {
                    Text("Synced \(date, format: .relative(presentation: .named))")
                }
            case .failed(let message):
                Label(message, systemImage: "wifi.exclamationmark")
            }
        }
        .font(.caption)
        .foregroundStyle(.secondary)
        .lineLimit(1)
        .padding(.vertical, 6)
        .frame(maxWidth: .infinity)
        .background(.bar)
    }
}
