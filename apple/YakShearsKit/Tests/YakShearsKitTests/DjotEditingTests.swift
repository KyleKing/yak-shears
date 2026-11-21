import Foundation
import Testing
@testable import YakShearsKit

/// Text with `|` marking the cursor, or `«` `»` marking a selection, so each case
/// reads as what the reader sees.
private func marked(_ marked: String) -> (text: String, selection: NSRange) {
    var text = marked
    if let start = text.firstIndex(of: "«"), let end = text.firstIndex(of: "»") {
        let location = text[..<start].utf16.count
        let length = marked[marked.index(after: start)..<end].utf16.count
        text.remove(at: end)
        text.remove(at: start)
        return (text, NSRange(location: location, length: length))
    }
    let index = text.firstIndex(of: "|")!
    let location = text[..<index].utf16.count
    text.remove(at: index)
    return (text, NSRange(location: location, length: 0))
}

private func render(_ text: String, _ selection: NSRange) -> String {
    let nsText = text as NSString
    if selection.length == 0 {
        return nsText.replacingCharacters(in: selection, with: "|")
    }
    return nsText.replacingCharacters(in: selection, with: "«" + nsText.substring(with: selection) + "»")
}

private func apply(_ edit: TextEdit?, to text: String) -> String? {
    edit.map { render($0.applied(to: text), $0.selection) }
}

@Suite struct DjotEditingTests {
    @Test(arguments: [
        ("- milk|", "- milk\n- |"),
        ("1. first|", "1. first\n2. |"),
        ("9) last|", "9) last\n10) |"),
        ("- [x] done|", "- [x] done\n- [ ] |"),
        ("  * nested|", "  * nested\n  * |"),
        ("- milk\n- |", "- milk\n|"),
        ("plain|", nil),
    ] as [(String, String?)])
    func enterContinuesOrEndsAList(before: String, after: String?) {
        let (text, selection) = marked(before)
        #expect(apply(DjotEditing.newline(in: text, at: selection.location), to: text) == after)
    }

    @Test(arguments: [
        // Indenting under a sibling adds the blank line Djot needs to nest.
        ("- a\n- b|", false, "- a\n\n    - b|"),
        // Outdenting back to the parent's level drops it again.
        ("- a\n\n    - b|", true, "- a\n- b|"),
        // Never more than one level below the parent.
        ("- a\n\n    - b|", false, "- a\n\n    - b|"),
        // A block moves together and keeps its inner nesting.
        ("- a\n\n- «b\n    - c»", false, "- a\n\n    - «b\n        - c»"),
        ("plain|", false, nil),
    ] as [(String, Bool, String?)])
    func tabMovesListItemsOneLevel(before: String, outdent: Bool, after: String?) {
        let (text, selection) = marked(before)
        #expect(apply(DjotEditing.indent(in: text, selection: selection, outdent: outdent), to: text) == after)
    }

    @Test(arguments: [
        ("buy |milk", "- [ ] buy |milk"),
        ("- [ ] buy |milk", "- [x] buy |milk"),
        ("- [x] buy |milk", "- buy |milk"),
        ("  - buy |milk", "  - [ ] buy |milk"),
    ])
    func checklistCycles(before: String, after: String) {
        let (text, selection) = marked(before)
        #expect(apply(DjotEditing.cycleChecklist(in: text, at: selection.location), to: text) == after)
    }

    @Test(arguments: [
        ("buy |milk", "- buy |milk"),
        ("- buy |milk", "buy |milk"),
        ("- [ ] buy |milk", "buy |milk"),
    ])
    func bulletToggles(before: String, after: String) {
        let (text, selection) = marked(before)
        #expect(apply(DjotEditing.toggleBullet(in: text, at: selection.location), to: text) == after)
    }

    @Test(arguments: [
        ("a «word» b", DjotEditing.Inline.strong, "a *«word»* b"),
        ("a *«word»* b", .strong, "a «word» b"),
        ("a «*word*» b", .strong, "a «word» b"),
        ("a | b", .emphasis, "a _|_ b"),
    ] as [(String, DjotEditing.Inline, String)])
    func inlineMarkersWrapAndUnwrap(before: String, inline: DjotEditing.Inline, after: String) {
        let (text, selection) = marked(before)
        #expect(apply(DjotEditing.toggle(inline, in: text, selection: selection), to: text) == after)
    }

    @Test func wikilinksCompleteFromWhatWasTyped() throws {
        let (text, selection) = marked("see [[gro|")
        let open = try #require(DjotEditing.openWikilink(in: text, at: selection.location))
        #expect(open.query == "gro")

        let edit = DjotEditing.completeWikilink(in: text, from: open.start, to: selection.location, target: "2026-11-21T09_15_00Z")
        #expect(apply(edit, to: text) == "see [[2026-11-21T09_15_00Z]]|")
        #expect(DjotEditing.openWikilink(in: "see [[done]] |", at: 13) == nil)
    }
}

@Suite struct DjotHighlighterTests {
    /// Each span as the text it covers and its kind, which reads better than offsets.
    private func spans(_ text: String) -> [String] {
        DjotHighlighter.spans(in: text).map { span in
            "\((text as NSString).substring(with: span.range))=\(span.kind)"
        }
    }

    @Test(arguments: [
        ("## Plans", ["## Plans=heading(level: 2)"]),
        ("- [x] *done* and _soon_", ["-=listMarker", "[x]=checkbox(done: true)", "*done*=strong", "_soon_=emphasis"]),
        ("see [[2026-11-21T09_15_00Z]] and [site](https://a.b) `x` #tag", [
            "[[2026-11-21T09_15_00Z]]=wikilink", "[site](https://a.b)=link", "`x`=code", "#tag=tag",
        ]),
        ("snake_case_name stays plain", []),
        ("```swift\nlet *x* = 1\n```\nafter", ["```swift=codeBlock", "let *x* = 1=codeBlock", "```=codeBlock"]),
        ("---\ntitle: T\n---\n# Body", ["---=frontmatter", "title: T=frontmatter", "---=frontmatter", "# Body=heading(level: 1)"]),
        ("<<<<<<< on disk\nmine", ["<<<<<<< on disk=conflictMarker"]),
    ])
    func stylesStructureLineByLine(text: String, expected: [String]) {
        #expect(spans(text) == expected)
    }
}
