import SwiftUI
import YakShearsKit

@main
struct YakShearsApp: App {
    @State private var library = Library(vault: Vault(root: Library.defaultRoot))

    var body: some Scene {
        WindowGroup {
            YakListView()
                .environment(library)
        }
    }
}
