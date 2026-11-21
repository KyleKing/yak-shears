import Foundation

/// Where to style Djot source in the editor. Line-based, like the web editor's
/// highlighter: good enough to see structure while typing, without a full parse.
public enum DjotHighlighter {
    public enum Kind: Equatable, Sendable {
        case heading(level: Int)
        case listMarker
        case checkbox(done: Bool)
        case strong
        case emphasis
        case code
        case codeBlock
        case link
        case wikilink
        case tag
        case blockquote
        case frontmatter
        case conflictMarker
    }

    public struct Span: Equatable, Sendable {
        public let range: NSRange
        public let kind: Kind
    }

    /// Spans for the whole text, in order of their starts.
    public static func spans(in text: String) -> [Span] {
        let nsText = text as NSString
        var spans: [Span] = []
        var inFence = false
        var inFrontmatter = false
        var location = 0
        var lineIndex = 0

        while location < nsText.length {
            let lineRange = nsText.lineRange(for: NSRange(location: location, length: 0))
            var content = lineRange
            if content.length > 0, nsText.character(at: content.upperBound - 1) == 0x0A { content.length -= 1 }
            let line = nsText.substring(with: content)
            defer {
                location = lineRange.upperBound
                lineIndex += 1
            }

            if lineIndex == 0, line == "---" {
                inFrontmatter = true
                spans.append(Span(range: content, kind: .frontmatter))
                continue
            }
            if inFrontmatter {
                spans.append(Span(range: content, kind: .frontmatter))
                if line == "---" { inFrontmatter = false }
                continue
            }
            if line.hasPrefix("```") {
                inFence.toggle()
                spans.append(Span(range: content, kind: .codeBlock))
                continue
            }
            if inFence {
                spans.append(Span(range: content, kind: .codeBlock))
                continue
            }
            if ["<<<<<<<", "=======", ">>>>>>>"].contains(where: line.hasPrefix) {
                spans.append(Span(range: content, kind: .conflictMarker))
                continue
            }
            spans.append(contentsOf: lineSpans(line, at: content.location))
        }
        return spans
    }

    private static func lineSpans(_ line: String, at offset: Int) -> [Span] {
        var spans: [Span] = []
        let whole = NSRange(location: 0, length: (line as NSString).length)
        func add(_ regex: NSRegularExpression, group: Int = 0, _ kind: (NSTextCheckingResult) -> Kind) {
            for match in regex.matches(in: line, range: whole) {
                let range = match.range(at: group)
                spans.append(Span(range: NSRange(location: offset + range.location, length: range.length), kind: kind(match)))
            }
        }

        if let heading = Patterns.heading.firstMatch(in: line, range: whole) {
            return [Span(range: NSRange(location: offset, length: whole.length), kind: .heading(level: heading.range(at: 1).length))]
        }
        if line.hasPrefix(">") {
            spans.append(Span(range: NSRange(location: offset, length: whole.length), kind: .blockquote))
        }
        add(Patterns.listMarker, group: 1) { _ in .listMarker }
        add(Patterns.checkbox, group: 1) { match in .checkbox(done: (line as NSString).substring(with: match.range(at: 1)).lowercased().contains("x")) }
        add(Patterns.code) { _ in .code }
        add(Patterns.wikilink) { _ in .wikilink }
        add(Patterns.link) { _ in .link }
        add(Patterns.strong) { _ in .strong }
        add(Patterns.emphasis) { _ in .emphasis }
        add(Patterns.tag, group: 1) { _ in .tag }
        return spans.sorted { $0.range.location < $1.range.location }
    }

    private enum Patterns {
        // NSRegularExpression is thread-safe for matching; compiled once.
        nonisolated(unsafe) static let heading = try! NSRegularExpression(pattern: "^(#{1,6}) ")
        nonisolated(unsafe) static let listMarker = try! NSRegularExpression(pattern: "^ *([-*+]|\\d+[.)]) ")
        nonisolated(unsafe) static let checkbox = try! NSRegularExpression(pattern: "^ *- (\\[[ xX]\\]) ")
        nonisolated(unsafe) static let code = try! NSRegularExpression(pattern: "`[^`\\n]+`")
        nonisolated(unsafe) static let wikilink = try! NSRegularExpression(pattern: "\\[\\[[^\\]\\n]+\\]\\]")
        nonisolated(unsafe) static let link = try! NSRegularExpression(pattern: "(?<!\\[)!?\\[[^\\[\\]\\n]*\\]\\([^)\\n]*\\)|<https?://[^>\\s]+>")
        nonisolated(unsafe) static let strong = try! NSRegularExpression(pattern: "(?<![\\w*])\\*(?=\\S)[^*\\n]+(?<=\\S)\\*(?![\\w*])")
        nonisolated(unsafe) static let emphasis = try! NSRegularExpression(pattern: "(?<![\\w_])_(?=\\S)[^_\\n]+(?<=\\S)_(?![\\w_])")
        nonisolated(unsafe) static let tag = try! NSRegularExpression(pattern: "(?:^|\\s)(#[A-Za-z0-9_-]+)")
    }
}
