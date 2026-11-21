import AppIntents

/// Phrases Siri recognises without any setup, and the actions offered to the Action
/// Button and Spotlight. Every phrase must include the app's name.
struct YakShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: NewYakIntent(),
            phrases: [
                "New yak in \(.applicationName)",
                "Add a yak to \(.applicationName)",
                "Take a note in \(.applicationName)",
            ],
            shortTitle: "New Yak",
            systemImageName: "square.and.pencil"
        )
        AppShortcut(
            intent: StartYakIntent(),
            phrases: ["Start a yak in \(.applicationName)"],
            shortTitle: "Start a Yak",
            systemImageName: "pencil.line"
        )
        AppShortcut(
            intent: AppendToYakIntent(),
            phrases: ["Append to a yak in \(.applicationName)"],
            shortTitle: "Append to Yak",
            systemImageName: "text.append"
        )
        AppShortcut(
            intent: OpenYakIntent(),
            phrases: ["Open a yak in \(.applicationName)"],
            shortTitle: "Open Yak",
            systemImageName: "doc.text"
        )
    }
}
