import SwiftUI
import YakShearsKit

/// A yak's source text, read-only until the native editor lands.
struct YakDetailView: View {
    @Environment(Library.self) private var library
    let summary: YakSummary
    @State private var content: Result<String, Error>?

    var body: some View {
        ScrollView {
            switch content {
            case .success(let text):
                Text(text)
                    .font(.body.monospaced())
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
            case .failure(let error):
                ContentUnavailableView("Couldn't Open the Yak", systemImage: "exclamationmark.triangle", description: Text(error.localizedDescription))
            case nil:
                ProgressView()
                    .padding()
            }
        }
        .navigationTitle(summary.title)
        #if os(iOS)
        .navigationBarTitleDisplayMode(.inline)
        #endif
        .task(id: summary.id) {
            do {
                content = .success(try await library.content(of: summary))
            } catch {
                content = .failure(error)
            }
        }
    }
}
