import Foundation

/// One change to make to the editor's text: replace `range` with `replacement`,
/// then select `selection`. Offsets are UTF-16, as UIKit and AppKit count them.
public struct TextEdit: Equatable, Sendable {
    public let range: NSRange
    public let replacement: String
    public let selection: NSRange

    public init(range: NSRange, replacement: String, selection: NSRange) {
        self.range = range
        self.replacement = replacement
        self.selection = selection
    }

    /// The text after the edit, for tests and for editors that set text wholesale.
    public func applied(to text: String) -> String {
        (text as NSString).replacingCharacters(in: range, with: replacement)
    }
}

/// The editing commands the web editor has (`editor.js`), as pure functions over
/// Djot source, so the native editors behave the same and the rules are tested once.
public enum DjotEditing {
    public static let indentWidth = 4

    // MARK: Lists

    /// Enter inside a list item: continue the list on the next line, or, on an item
    /// with nothing after its marker, end the list by removing the marker.
    ///
    /// - Returns: nil when the line is not a list item, for a plain newline.
    public static func newline(in text: String, at cursor: Int) -> TextEdit? {
        let line = Line(in: text, at: cursor)
        guard let item = ListItem(line.text) else { return nil }
        if item.content.isEmpty {
            return TextEdit(range: line.range, replacement: "", selection: NSRange(location: line.range.location, length: 0))
        }
        let continuation = "\n" + item.indent + item.nextMarker
        return TextEdit(
            range: NSRange(location: cursor, length: 0), replacement: continuation,
            selection: NSRange(location: cursor + continuation.utf16.count, length: 0)
        )
    }

    /// Tab and Shift-Tab: move every line the selection touches one level, as a block.
    ///
    /// Only the block's first line is measured against the item above, so nesting
    /// inside the block survives, and an item never sinks more than one level below
    /// its parent. Djot only nests a list after a blank line, so indenting adds one
    /// ahead of the block and outdenting back to the parent's level removes it.
    ///
    /// - Returns: nil when no touched line is a list item, so Tab can mean Tab.
    public static func indent(in text: String, selection: NSRange, outdent: Bool) -> TextEdit? {
        let nsText = text as NSString
        let block = nsText.lineRange(for: selection)
        let blockText = nsText.substring(with: block)
        let trailingNewline = blockText.hasSuffix("\n")
        let lines = (trailingNewline ? String(blockText.dropLast()) : blockText).components(separatedBy: "\n")
        guard lines.contains(where: { ListItem($0) != nil }) else { return nil }

        let shifted = lines.map { line -> String in
            if line.trimmingCharacters(in: .whitespaces).isEmpty { return line }
            if !outdent { return String(repeating: " ", count: indentWidth) + line }
            return String(line.dropFirst(min(indentWidth, leadingSpaces(line))))
        }
        if shifted == lines { return TextEdit(range: selection, replacement: nsText.substring(with: selection), selection: selection) }

        let previous = previousLines(of: block.location, in: nsText)
        if !outdent, let parent = previous.first(where: { !$0.isBlank }), leadingSpaces(shifted[0]) > leadingSpaces(parent.text) + indentWidth {
            return TextEdit(range: selection, replacement: nsText.substring(with: selection), selection: selection)
        }

        var start = block.location
        var head = ""
        if !outdent, let above = previous.first, !above.isBlank, leadingSpaces(above.text) < leadingSpaces(shifted[0]) {
            head = "\n"
        } else if outdent, previous.count >= 2, previous[0].isBlank, !previous[1].isBlank,
                  leadingSpaces(previous[1].text) <= leadingSpaces(shifted[0]) {
            start = previous[0].range.location
        }

        let replacement = head + shifted.joined(separator: "\n") + (trailingNewline ? "\n" : "")
        let range = NSRange(location: start, length: block.upperBound - start)
        let headDelta = head.utf16.count - (block.location - start)
        let firstDelta = shifted[0].utf16.count - lines[0].utf16.count
        let totalDelta = zip(shifted, lines).reduce(0) { $0 + $1.0.utf16.count - $1.1.utf16.count }
        let firstLineStart = block.location + headDelta
        let newStart = max(firstLineStart, selection.location + headDelta + firstDelta)
        let newEnd = max(firstLineStart, selection.upperBound + headDelta + totalDelta)
        return TextEdit(range: range, replacement: replacement, selection: NSRange(location: newStart, length: newEnd - newStart))
    }

    /// Cycle a line through plain → `- [ ]` → `- [x]` → `- ` → `- [ ]`, as Ctrl-L does
    /// on the web.
    public static func cycleChecklist(in text: String, at cursor: Int) -> TextEdit {
        let line = Line(in: text, at: cursor)
        let indent = String(line.text.prefix(leadingSpaces(line.text)))
        let body = String(line.text.dropFirst(indent.count))
        let replaced: String
        if body.hasPrefix("- [x] ") {
            replaced = indent + "- " + body.dropFirst(6)
        } else if body.hasPrefix("- [ ] ") {
            replaced = indent + "- [x] " + body.dropFirst(6)
        } else if body.hasPrefix("- ") {
            replaced = indent + "- [ ] " + body.dropFirst(2)
        } else {
            replaced = indent + "- [ ] " + body
        }
        return replaceLine(line, with: replaced, cursor: cursor)
    }

    /// Add or remove a bullet (and any checkbox) at the start of the line.
    public static func toggleBullet(in text: String, at cursor: Int) -> TextEdit {
        let line = Line(in: text, at: cursor)
        let indent = String(line.text.prefix(leadingSpaces(line.text)))
        let body = String(line.text.dropFirst(indent.count))
        let replaced: String
        if body.hasPrefix("- [ ] ") || body.hasPrefix("- [x] ") {
            replaced = indent + body.dropFirst(6)
        } else if body.hasPrefix("- ") {
            replaced = indent + body.dropFirst(2)
        } else {
            replaced = indent + "- " + body
        }
        return replaceLine(line, with: replaced, cursor: cursor)
    }

    // MARK: Inline

    /// Strong in Djot is `*text*`, emphasis is `_text_`.
    public enum Inline: String, Sendable {
        case strong = "*"
        case emphasis = "_"
    }

    /// Wrap the selection in the marker, or unwrap it when it is already wrapped
    /// (inside or just outside the selection). With nothing selected, insert a pair
    /// and put the cursor between them.
    public static func toggle(_ inline: Inline, in text: String, selection: NSRange) -> TextEdit {
        let nsText = text as NSString
        let marker = inline.rawValue
        let width = marker.utf16.count
        let selected = nsText.substring(with: selection)

        if selected.utf16.count >= 2 * width, selected.hasPrefix(marker), selected.hasSuffix(marker) {
            let inner = String(selected.dropFirst().dropLast())
            return TextEdit(range: selection, replacement: inner, selection: NSRange(location: selection.location, length: inner.utf16.count))
        }
        if selection.location >= width, selection.upperBound + width <= nsText.length,
           nsText.substring(with: NSRange(location: selection.location - width, length: width)) == marker,
           nsText.substring(with: NSRange(location: selection.upperBound, length: width)) == marker {
            let range = NSRange(location: selection.location - width, length: selection.length + 2 * width)
            return TextEdit(range: range, replacement: selected, selection: NSRange(location: range.location, length: selection.length))
        }
        return TextEdit(
            range: selection, replacement: marker + selected + marker,
            selection: NSRange(location: selection.location + width, length: selection.length)
        )
    }

    // MARK: Wikilinks

    /// The `[[` being typed on the cursor's line and the text after it, while no
    /// `]]` has closed it, for completion.
    public static func openWikilink(in text: String, at cursor: Int) -> (start: Int, query: String)? {
        let nsText = text as NSString
        let lineStart = nsText.lineRange(for: NSRange(location: cursor, length: 0)).location
        let before = nsText.substring(with: NSRange(location: lineStart, length: cursor - lineStart))
        guard let open = before.range(of: "[[", options: .backwards) else { return nil }
        let query = String(before[open.upperBound...])
        if query.contains("]") || query.contains("[") { return nil }
        return (lineStart + before[..<open.lowerBound].utf16.count, query)
    }

    /// Replace what was typed from `[[` to the cursor with a finished link to `target`
    /// (a yak's filename stem, as the web's completion inserts).
    public static func completeWikilink(in text: String, from start: Int, to cursor: Int, target: String) -> TextEdit {
        let link = "[[\(target)]]"
        return TextEdit(
            range: NSRange(location: start, length: cursor - start), replacement: link,
            selection: NSRange(location: start + link.utf16.count, length: 0)
        )
    }

    // MARK: Helpers

    struct Line {
        /// The line without its newline.
        let range: NSRange
        let text: String
        var isBlank: Bool { text.trimmingCharacters(in: .whitespaces).isEmpty }

        init(in text: String, at location: Int) {
            let nsText = text as NSString
            var range = nsText.lineRange(for: NSRange(location: location, length: 0))
            if range.length > 0, nsText.character(at: range.upperBound - 1) == 0x0A {
                range.length -= 1
            }
            self.range = range
            self.text = nsText.substring(with: range)
        }
    }

    /// A list item line: indent, marker, and what follows the marker.
    struct ListItem {
        let indent: String
        let nextMarker: String
        let content: String

        private nonisolated(unsafe) static let pattern = /^( *)(- \[[ xX]\] |[-*+] |(\d+)([.)]) )(.*)$/

        init?(_ line: String) {
            guard let match = line.wholeMatch(of: Self.pattern) else { return nil }
            indent = String(match.1)
            content = String(match.5)
            let marker = String(match.2)
            if let number = match.3.flatMap({ Int($0) }), let closer = match.4 {
                nextMarker = "\(number + 1)\(closer) "
            } else if marker.hasPrefix("- [") {
                nextMarker = "- [ ] "
            } else {
                nextMarker = marker
            }
        }
    }

    private static func leadingSpaces(_ line: String) -> Int {
        line.prefix(while: { $0 == " " }).count
    }

    /// Lines above `location`, nearest first.
    private static func previousLines(of location: Int, in text: NSString) -> [Line] {
        var lines: [Line] = []
        var cursor = location
        while cursor > 0, lines.count < 64 {
            let line = Line(in: text as String, at: cursor - 1)
            lines.append(line)
            cursor = line.range.location
        }
        return lines
    }

    private static func replaceLine(_ line: Line, with replaced: String, cursor: Int) -> TextEdit {
        let delta = replaced.utf16.count - line.text.utf16.count
        return TextEdit(
            range: line.range, replacement: replaced,
            selection: NSRange(location: max(line.range.location, cursor + delta), length: 0)
        )
    }
}
