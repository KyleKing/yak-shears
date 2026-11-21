import SwiftUI
import YakShearsKit

@main
struct YakShearsApp: App {
    @State private var library = Library.shared
    @State private var account = Account.shared

    var body: some Scene {
        WindowGroup {
            YakListView()
                .environment(library)
                .environment(account)
        }
    }
}
