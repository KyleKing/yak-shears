import AppIntents
import YakShearsKit

/// Capture text as a new yak without opening the app: Siri dictation, a Shortcut,
/// or the Action Button.
struct NewYakIntent: AppIntent {
    static let title: LocalizedStringResource = "New Yak"
    static let description = IntentDescription("Saves text as a new yak and syncs it.")

    @Parameter(title: "Text", requestValueDialog: "What should the yak say?")
    var text: String

    @Parameter(title: "Category", optionsProvider: CategoryOptions())
    var category: String?

    static var parameterSummary: some ParameterSummary {
        Summary("Add \(\.$text) as a new yak") {
            \.$category
        }
    }

    @MainActor
    func perform() async throws -> some IntentResult & ReturnsValue<YakEntity> & ProvidesDialog {
        let path = try Vault.app.capture(text, in: category)
        await Library.shared.sync(with: Account.shared)
        let summary = try Vault.app.summaries().first { $0.path == path }
        guard let summary else { throw YakIntentError.missing }
        return .result(value: YakEntity(summary), dialog: "Added to Yak Shears.")
    }
}

/// Add a paragraph to the end of an existing yak.
struct AppendToYakIntent: AppIntent {
    static let title: LocalizedStringResource = "Append to Yak"
    static let description = IntentDescription("Adds text as a new paragraph at the end of a yak, then syncs it.")

    @Parameter(title: "Yak")
    var yak: YakEntity

    @Parameter(title: "Text", requestValueDialog: "What should be added?")
    var text: String

    static var parameterSummary: some ParameterSummary {
        Summary("Append \(\.$text) to \(\.$yak)")
    }

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        try Vault.app.append(text, to: yak.id)
        await Library.shared.sync(with: Account.shared)
        return .result(dialog: "Added to \(yak.title).")
    }
}

/// Open a yak in the editor.
struct OpenYakIntent: OpenIntent {
    static let title: LocalizedStringResource = "Open Yak"

    @Parameter(title: "Yak")
    var target: YakEntity

    @MainActor
    func perform() async throws -> some IntentResult {
        Library.shared.requestedPath = target.id
        return .result()
    }
}

/// Open the app on a new, empty yak with the cursor in it: the fastest path from
/// the Action Button or Control Center to typing (ADR 0012's goal, which the web
/// app could only reach in two taps).
struct StartYakIntent: AppIntent {
    static let title: LocalizedStringResource = "Start a Yak"
    static let description = IntentDescription("Opens Yak Shears on a new, empty yak.")
    static let openAppWhenRun = true

    @Parameter(title: "Category", optionsProvider: CategoryOptions())
    var category: String?

    @MainActor
    func perform() async throws -> some IntentResult {
        Library.shared.requestedPath = await Library.shared.createYak(in: category)
        return .result()
    }
}

enum YakIntentError: Error, CustomLocalizedStringResourceConvertible {
    case missing

    var localizedStringResource: LocalizedStringResource {
        "The yak could not be found after saving it."
    }
}
