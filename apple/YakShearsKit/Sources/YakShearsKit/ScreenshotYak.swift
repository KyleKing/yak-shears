/// The text of a yak made from a screenshot.
public enum ScreenshotYak {
    /// Titled by the first line the screenshot says (or "Screenshot"), then the image,
    /// then everything recognised in a `screenshot-text` div, which keeps the yak
    /// findable by the words in the picture without passing them off as the reader's.
    public static func compose(embed: String, recognizedText lines: [String]) -> String {
        let recognized = lines.map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
        let title = recognized.first.map { $0.count > maxTitle ? String($0.prefix(maxTitle)) + "…" : $0 } ?? "Screenshot"
        var parts = ["# \(title)", embed]
        if !recognized.isEmpty {
            parts.append("::: screenshot-text\n\(recognized.joined(separator: "\n"))\n:::")
        }
        return parts.joined(separator: "\n\n") + "\n"
    }

    private static let maxTitle = 60
}
