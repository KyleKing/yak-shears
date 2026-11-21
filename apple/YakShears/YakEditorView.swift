import SwiftUI
import YakShearsKit

/// Edits one yak's source text, saving to the local vault as you type.
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

    private static let saveDelay: Duration = .milliseconds(500)

    var body: some View {
        Group {
            if let loadError {
                ContentUnavailableView("Couldn't Open the Yak", systemImage: "exclamationmark.triangle", description: Text(loadError))
            } else if lease == nil {
                ProgressView()
            } else {
                TextEditor(text: $text)
                    .font(.body.monospaced())
                    .contentMargins(.horizontal, 12, for: .scrollContent)
                    #if os(iOS)
                    .scrollDismissesKeyboard(.interactively)
                    #endif
                    .onChange(of: text) { scheduleSave() }
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
