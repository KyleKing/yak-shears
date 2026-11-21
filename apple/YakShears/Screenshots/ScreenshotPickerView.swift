#if os(iOS)
import Photos
import SwiftUI
import YakShearsKit

/// Recent screenshots in a grid: pick some, import each as a yak, and (by default)
/// delete them from Photos once they are safely in the vault.
struct ScreenshotPickerView: View {
    @Environment(Library.self) private var library
    @Environment(Account.self) private var account
    @Environment(\.dismiss) private var dismiss

    @State private var assets: [PHAsset] = []
    @State private var selected: Set<String> = []
    @State private var deleteOriginals = true
    @State private var error: String?
    @State private var isImporting = false

    private let columns = [GridItem(.adaptive(minimum: 100), spacing: 4)]

    var body: some View {
        NavigationStack {
            ScrollView {
                if let error {
                    ContentUnavailableView("Can't Import Screenshots", systemImage: "photo.badge.exclamationmark", description: Text(error))
                } else {
                    LazyVGrid(columns: columns, spacing: 4) {
                        ForEach(assets, id: \.localIdentifier) { asset in
                            ScreenshotCell(asset: asset, isSelected: selected.contains(asset.localIdentifier))
                                .onTapGesture { toggle(asset) }
                        }
                    }
                    .padding(4)
                }
            }
            .safeAreaInset(edge: .bottom) {
                Toggle("Delete from Photos after importing", isOn: $deleteOriginals)
                    .padding()
                    .background(.bar)
            }
            .navigationTitle(selected.isEmpty ? "Screenshots" : "\(selected.count) Selected")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    if isImporting {
                        ProgressView()
                    } else {
                        Button("Import", action: importSelected).disabled(selected.isEmpty)
                    }
                }
            }
        }
        .task {
            do {
                try await ScreenshotImporter.authorize()
                assets = ScreenshotImporter.recent(limit: 60)
                if assets.isEmpty { error = ScreenshotImporter.Failure.noScreenshots.errorDescription }
            } catch {
                self.error = error.localizedDescription
            }
        }
    }

    private func toggle(_ asset: PHAsset) {
        if selected.remove(asset.localIdentifier) == nil {
            selected.insert(asset.localIdentifier)
        }
    }

    private func importSelected() {
        // Oldest first, so the yaks' names keep the order the screenshots were taken in.
        let chosen = assets.filter { selected.contains($0.localIdentifier) }.reversed()
        isImporting = true
        Task {
            defer { isImporting = false }
            do {
                let result = try await ScreenshotImporter.importScreenshots(Array(chosen), deleteOriginals: deleteOriginals)
                await library.reload()
                library.requestedPath = result.paths.count == 1 ? result.paths.first : nil
                library.requestSync(with: account, after: .zero)
                dismiss()
            } catch {
                self.error = error.localizedDescription
            }
        }
    }
}

private struct ScreenshotCell: View {
    let asset: PHAsset
    let isSelected: Bool
    @State private var image: UIImage?

    var body: some View {
        Color.secondary.opacity(0.15)
            .aspectRatio(9 / 19.5, contentMode: .fit)
            .overlay {
                if let image {
                    Image(uiImage: image).resizable().scaledToFill()
                }
            }
            .clipped()
            .overlay(alignment: .bottomTrailing) {
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .font(.title3)
                    .foregroundStyle(isSelected ? Color.accentColor : .white)
                    .shadow(radius: 2)
                    .padding(6)
            }
            .accessibilityAddTraits(isSelected ? .isSelected : [])
            .task { image = await ScreenshotImporter.thumbnail(for: asset, side: 300) }
    }
}
#endif
