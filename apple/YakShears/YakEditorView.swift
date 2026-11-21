import SwiftUI
import YakShearsKit

/// Edits one yak's Djot source in a native text view, saving to the local vault as
/// you type.
///
/// Lists, indenting, bold and italic, and wikilinks behave as on the web, from the
/// same rules in `DjotEditing`; on iPhone and iPad the commands ride on the
/// keyboard's own accessory bar, and on the Mac in the toolbar.
///
/// Saves go to disk only, so editing works offline; sync picks them up shortly
/// after typing stops and again when the editor closes. Every save names the lease
/// the editor started from, so a sync that rewrote the file meanwhile is woven in
/// with conflict markers instead of being overwritten.
struct YakEditorView: View {
    @Environment(Library.self) private var library
    @Environment(Account.self) private var account
    let summary: YakSummary

    @State private var text = ""
    /// Lease of the text on disk as this editor last read or wrote it.
    @State private var lease: String?
    @State private var loadError: String?
    @State private var pendingSave: Task<Void, Never>?
    @State private var controller = EditorController()
    /// The text after an open `[[`, while one is being typed.
    @State private var wikilinkQuery: String?

    private static let saveDelay: Duration = .milliseconds(500)

    var body: some View {
        Group {
            if let loadError {
                ContentUnavailableView("Couldn't Open the Yak", systemImage: "exclamationmark.triangle", description: Text(loadError))
            } else if lease == nil {
                ProgressView()
            } else {
                YakTextView(text: $text, controller: controller)
                    .onChange(of: text) { scheduleSave() }
                    .safeAreaInset(edge: .bottom) {
                        if let wikilinkQuery {
                            WikilinkSuggestions(query: wikilinkQuery, current: summary) { target in
                                controller.completeWikilink(target: target)
                            }
                        }
                    }
            }
        }
        .safeAreaInset(edge: .top) {
            if ConflictMarkup.hasMarkers(text) {
                ConflictBanner()
            }
        }
        .navigationTitle(summary.title)
        #if os(iOS)
        .navigationBarTitleDisplayMode(.inline)
        #endif
        #if os(macOS)
        .toolbar {
            ToolbarItemGroup {
                ForEach(EditorCommand.allCases, id: \.self) { command in
                    Button(command.title, systemImage: command.systemImage) { controller.perform(command) }
                }
            }
        }
        #endif
        .onAppear { controller.onWikilinkQuery = { wikilinkQuery = $0 } }
        .task(id: summary.path) { await load() }
        .onChange(of: summary.modified) { refreshIfUntouched() }
        .onDisappear { finish() }
    }

    private func load() async {
        do {
            let content = try await library.content(of: summary)
            text = content
            lease = Lease.of(content)
            loadError = nil
        } catch {
            loadError = error.localizedDescription
        }
    }

    private func scheduleSave() {
        guard let lease, Lease.of(text) != lease else { return }
        pendingSave?.cancel()
        pendingSave = Task {
            try? await Task.sleep(for: Self.saveDelay)
            guard !Task.isCancelled else { return }
            save()
        }
    }

    private func save() {
        guard let lease, Lease.of(text) != lease else { return }
        do {
            let saved = try library.vault.save(summary.path, content: text, replacing: lease)
            self.lease = saved.lease
            if saved.content != text {
                // The file moved underneath; show the woven conflict.
                text = saved.content
            }
            library.requestSync(with: account)
        } catch {
            loadError = error.localizedDescription
        }
    }

    /// A sync rewrote the open yak. With nothing unsaved, show the new text; with
    /// unsaved edits, leave them, and the next save weaves the two.
    private func refreshIfUntouched() {
        guard let lease, Lease.of(text) == lease else { return }
        Task { await load() }
    }

    /// Flush the last keystrokes, drop a new yak that was never written in, and sync.
    private func finish() {
        pendingSave?.cancel()
        save()
        library.discardIfAbandoned(summary, text: text)
        library.requestSync(with: account, after: .zero)
    }
}

private struct ConflictBanner: View {
    var body: some View {
        Label("Both versions are kept between the conflict markers. Edit down to one and remove the markers to sync.", systemImage: "exclamationmark.triangle.fill")
            .font(.footnote)
            .padding(10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.orange.opacity(0.15))
    }
}

/// Yaks to link while a `[[` is open: titles and filenames that contain the query,
/// newest first. Tapping one finishes the link with the yak's filename stem, which
/// is what the server resolves.
private struct WikilinkSuggestions: View {
    @Environment(Library.self) private var library
    let query: String
    let current: YakSummary
    let onPick: (String) -> Void

    private var matches: [YakSummary] {
        let needle = query.trimmingCharacters(in: .whitespaces)
        return library.summaries.filter { summary in
            summary.path != current.path && (needle.isEmpty
                || summary.title.localizedStandardContains(needle)
                || summary.path.localizedStandardContains(needle))
        }
        .prefix(12)
        .map { $0 }
    }

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(matches) { summary in
                    Button {
                        onPick(((summary.path as NSString).lastPathComponent as NSString).deletingPathExtension)
                    } label: {
                        Text(summary.title).lineLimit(1)
                    }
                    .buttonStyle(.bordered)
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
        }
        .background(.bar)
    }
}
