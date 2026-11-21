import SwiftUI
import UIKit
import UniformTypeIdentifiers
import YakShearsKit

/// The share sheet's entry point: reads what was shared, lets the reader add a
/// note, and queues the result in the App Group inbox.
///
/// Nothing here touches the network or the vault. The app files the capture the next
/// time it becomes active, so sharing works offline and never waits on a sync.
final class ShareViewController: UIViewController {
    override func viewDidLoad() {
        super.viewDidLoad()
        let item = extensionContext?.inputItems.first as? NSExtensionItem
        let compose = ShareComposeView(
            title: item?.attributedContentText?.string ?? item?.attributedTitle?.string,
            loadShared: { await Self.loadShared(from: item) },
            onSave: { [weak self] text in self?.save(text) },
            onCancel: { [weak self] in
                self?.extensionContext?.cancelRequest(withError: CocoaError(.userCancelled))
            }
        )
        let host = UIHostingController(rootView: compose)
        addChild(host)
        host.view.frame = view.bounds
        host.view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        view.addSubview(host.view)
        host.didMove(toParent: self)
    }

    private func save(_ text: String) {
        do {
            guard let inbox = AppGroup.inbox else { throw CocoaError(.fileNoSuchFile) }
            try inbox.add(text)
            extensionContext?.completeRequest(returningItems: nil)
        } catch {
            extensionContext?.cancelRequest(withError: error)
        }
    }

    /// The shared web page, if any, and any shared plain text.
    @MainActor
    private static func loadShared(from item: NSExtensionItem?) async -> (url: URL?, text: String) {
        var url: URL?
        var text = ""
        for provider in item?.attachments ?? [] {
            if url == nil, provider.hasItemConformingToTypeIdentifier(UTType.url.identifier),
               let loaded = await load(URL.self, from: provider), !loaded.isFileURL {
                url = loaded
            } else if provider.hasItemConformingToTypeIdentifier(UTType.plainText.identifier),
                      let loaded = await load(String.self, from: provider) {
                text = text.isEmpty ? loaded : text + "\n\n" + loaded
            }
        }
        return (url, text)
    }

    /// `loadTransferable` hands back Sendable values, unlike `loadItem`'s NSSecureCoding.
    @MainActor
    private static func load<Value: Transferable & Sendable>(_ type: Value.Type, from provider: NSItemProvider) async -> Value? {
        await withCheckedContinuation { continuation in
            _ = provider.loadTransferable(type: type) { result in
                continuation.resume(returning: try? result.get())
            }
        }
    }
}

/// A note field over the shared link, with Cancel and Save.
private struct ShareComposeView: View {
    let title: String?
    let loadShared: () async -> (url: URL?, text: String)
    let onSave: (String) -> Void
    let onCancel: () -> Void

    @State private var note = ""
    @State private var url: URL?
    @State private var hasLoaded = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Note") {
                    TextField("Add a note", text: $note, axis: .vertical)
                        .lineLimit(3...10)
                }
                if let url {
                    Section("Link") {
                        Text(title.flatMap { $0.isEmpty ? nil : $0 } ?? url.absoluteString)
                            .lineLimit(2)
                        Text(url.host() ?? url.absoluteString)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .navigationTitle("New Yak")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel", action: onCancel)
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        onSave(SharedContent.compose(note: note, url: url, title: title))
                    }
                    .disabled(!hasLoaded || (note.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && url == nil))
                }
            }
        }
        .task {
            let shared = await loadShared()
            url = shared.url
            if note.isEmpty {
                note = shared.text
            }
            hasLoaded = true
        }
    }
}
