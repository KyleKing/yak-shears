#if os(iOS)
import AppIntents
import YakShearsKit

/// The newest screenshot becomes a yak, and the original leaves Photos. Opens the
/// app because PhotoKit's delete confirmation needs a foreground app; bind it to
/// the Action Button or a Back Tap for screenshot-to-note in one press.
struct YakLatestScreenshotIntent: AppIntent {
    static let title: LocalizedStringResource = "Yak Latest Screenshot"
    static let description = IntentDescription("Saves the newest screenshot as a yak with its text, then deletes it from Photos.")
    static let openAppWhenRun = true

    @Parameter(title: "Delete from Photos", default: true)
    var deleteOriginal: Bool

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        try await ScreenshotImporter.authorize()
        guard let newest = ScreenshotImporter.recent(limit: 1).first else {
            throw ScreenshotImporter.Failure.noScreenshots
        }
        let result = try await ScreenshotImporter.importScreenshots([newest], deleteOriginals: deleteOriginal)
        Library.shared.requestedPath = result.paths.first
        Library.shared.requestSync(with: Account.shared, after: .zero)
        return .result(dialog: result.deleted || !deleteOriginal ? "Saved the screenshot as a yak." : "Saved the screenshot as a yak and kept the original.")
    }
}
#endif
