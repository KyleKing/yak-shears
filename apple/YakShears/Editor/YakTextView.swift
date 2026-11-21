import SwiftUI
import YakShearsKit

#if os(iOS)
import UIKit
typealias PlatformFont = UIFont
typealias PlatformColor = UIColor
typealias PlatformTextView = UITextView
#else
import AppKit
typealias PlatformFont = NSFont
typealias PlatformColor = NSColor
typealias PlatformTextView = NSTextView
#endif

/// The editing commands of the accessory bar and keyboard shortcuts.
enum EditorCommand: CaseIterable {
    case outdent, indent, bullet, checklist, strong, emphasis, wikilink

    var title: String {
        switch self {
        case .outdent: "Outdent"
        case .indent: "Indent"
        case .bullet: "Bullet"
        case .checklist: "Checklist"
        case .strong: "Bold"
        case .emphasis: "Italic"
        case .wikilink: "Link a Yak"
        }
    }

    var systemImage: String {
        switch self {
        case .outdent: "decrease.indent"
        case .indent: "increase.indent"
        case .bullet: "list.bullet"
        case .checklist: "checklist"
        case .strong: "bold"
        case .emphasis: "italic"
        case .wikilink: "link"
        }
    }
}

/// Owns the live text view so SwiftUI (the wikilink suggestions) can drive it.
///
/// Every command becomes a `TextEdit` from `DjotEditing` and goes through the text
/// view's own replace, so it lands in the undo stack like typing does.
@MainActor
final class EditorController {
    weak var textView: PlatformTextView?
    /// Called with the text after `[[` while a wikilink is open, nil once it closes.
    var onWikilinkQuery: (String?) -> Void = { _ in }

    /// - Returns: Whether the command applied; indenting outside a list does not,
    ///   so a hardware Tab can fall back to typing a tab.
    @discardableResult
    func perform(_ command: EditorCommand) -> Bool {
        guard let textView else { return false }
        let text = textView.currentText
        let selection = textView.currentSelection
        let edit: TextEdit?
        switch command {
        case .indent: edit = DjotEditing.indent(in: text, selection: selection, outdent: false)
        case .outdent: edit = DjotEditing.indent(in: text, selection: selection, outdent: true)
        case .bullet: edit = DjotEditing.toggleBullet(in: text, at: selection.location)
        case .checklist: edit = DjotEditing.cycleChecklist(in: text, at: selection.location)
        case .strong: edit = DjotEditing.toggle(.strong, in: text, selection: selection)
        case .emphasis: edit = DjotEditing.toggle(.emphasis, in: text, selection: selection)
        case .wikilink:
            // Open a link at the cursor; the selection, if any, becomes the query.
            let selected = (text as NSString).substring(with: selection)
            edit = TextEdit(range: selection, replacement: "[[" + selected, selection: NSRange(location: selection.location + 2 + selected.utf16.count, length: 0))
        }
        guard let edit else { return false }
        apply(edit)
        return true
    }

    /// Finish the open `[[` with a link to the yak whose filename stem is `target`.
    func completeWikilink(target: String) {
        guard let textView else { return }
        let text = textView.currentText
        let cursor = textView.currentSelection.location
        guard let open = DjotEditing.openWikilink(in: text, at: cursor) else { return }
        apply(DjotEditing.completeWikilink(in: text, from: open.start, to: cursor, target: target))
    }

    func apply(_ edit: TextEdit) {
        textView?.replace(edit.range, with: edit.replacement, select: edit.selection)
    }

    func textDidChange() {
        guard let textView else { return }
        Highlighter.apply(to: textView)
        onWikilinkQuery(DjotEditing.openWikilink(in: textView.currentText, at: textView.currentSelection.location)?.query)
    }
}

/// Styles Djot source in place, from `DjotHighlighter`'s spans.
@MainActor
enum Highlighter {
    #if os(iOS)
    static let baseFont = UIFont.monospacedSystemFont(ofSize: UIFont.preferredFont(forTextStyle: .body).pointSize, weight: .regular)
    #else
    static let baseFont = NSFont.monospacedSystemFont(ofSize: NSFont.systemFontSize + 1, weight: .regular)
    #endif

    static func apply(to textView: PlatformTextView) {
        #if os(iOS)
        // Restyling under marked text (dictation, CJK input) breaks the composition.
        guard textView.markedTextRange == nil else { return }
        let storage = textView.textStorage
        #else
        guard !textView.hasMarkedText(), let storage = textView.textStorage else { return }
        #endif
        let whole = NSRange(location: 0, length: storage.length)
        storage.beginEditing()
        storage.setAttributes([.font: baseFont, .foregroundColor: PlatformColor.labelColor], range: whole)
        for span in DjotHighlighter.spans(in: storage.string) where NSMaxRange(span.range) <= storage.length {
            storage.addAttributes(attributes(for: span.kind), range: span.range)
        }
        storage.endEditing()
    }

    private static func attributes(for kind: DjotHighlighter.Kind) -> [NSAttributedString.Key: Any] {
        let size = baseFont.pointSize
        switch kind {
        case .heading(let level):
            return [.font: PlatformFont.monospacedSystemFont(ofSize: size + CGFloat(max(0, 4 - level)) * 2, weight: .bold)]
        case .listMarker, .checkbox(done: false):
            return [.foregroundColor: PlatformColor.secondaryLabelColor]
        case .checkbox(done: true):
            return [.foregroundColor: PlatformColor.systemGreen]
        case .strong:
            return [.font: PlatformFont.monospacedSystemFont(ofSize: size, weight: .bold)]
        case .emphasis:
            return [.obliqueness: 0.18]
        case .code, .codeBlock:
            return [.foregroundColor: PlatformColor.systemIndigo, .backgroundColor: PlatformColor.systemIndigo.withAlphaComponent(0.08)]
        case .link, .wikilink:
            return [.foregroundColor: PlatformColor.tintColor]
        case .tag:
            return [.foregroundColor: PlatformColor.systemTeal]
        case .blockquote, .frontmatter:
            return [.foregroundColor: PlatformColor.secondaryLabelColor]
        case .conflictMarker:
            return [.foregroundColor: PlatformColor.systemOrange, .font: PlatformFont.monospacedSystemFont(ofSize: size, weight: .bold)]
        }
    }
}

#if os(iOS)
extension PlatformColor {
    static var labelColor: UIColor { .label }
    static var secondaryLabelColor: UIColor { .secondaryLabel }
}

extension UITextView {
    var currentText: String { text ?? "" }
    var currentSelection: NSRange { selectedRange }

    /// Replace through UIKit's text input, so the change joins the undo stack.
    func replace(_ range: NSRange, with replacement: String, select selection: NSRange) {
        guard let start = position(from: beginningOfDocument, offset: range.location),
              let end = position(from: start, offset: range.length),
              let textRange = textRange(from: start, to: end) else { return }
        replace(textRange, withText: replacement)
        selectedRange = selection
        delegate?.textViewDidChange?(self)
    }
}

/// Tab, Shift-Tab, ⌘B, ⌘I, and ⌃L on a hardware keyboard.
final class YakUITextView: UITextView {
    weak var controller: EditorController?

    override var keyCommands: [UIKeyCommand]? {
        [
            UIKeyCommand(input: "\t", modifierFlags: [], action: #selector(indentLine)),
            UIKeyCommand(input: "\t", modifierFlags: .shift, action: #selector(outdentLine)),
            UIKeyCommand(title: "Bold", action: #selector(makeStrong), input: "b", modifierFlags: .command),
            UIKeyCommand(title: "Italic", action: #selector(makeEmphasis), input: "i", modifierFlags: .command),
            UIKeyCommand(title: "Checklist", action: #selector(cycleChecklist), input: "l", modifierFlags: .control),
        ].map { command in
            command.wantsPriorityOverSystemBehavior = true
            return command
        }
    }

    @objc private func indentLine() {
        if controller?.perform(.indent) != true { insertText("\t") }
    }
    @objc private func outdentLine() { controller?.perform(.outdent) }
    @objc private func makeStrong() { controller?.perform(.strong) }
    @objc private func makeEmphasis() { controller?.perform(.emphasis) }
    @objc private func cycleChecklist() { controller?.perform(.checklist) }
}

struct YakTextView: UIViewRepresentable {
    @Binding var text: String
    let controller: EditorController

    func makeUIView(context: Context) -> YakUITextView {
        let textView = YakUITextView()
        textView.controller = controller
        textView.delegate = context.coordinator
        textView.font = Highlighter.baseFont
        textView.adjustsFontForContentSizeCategory = true
        textView.alwaysBounceVertical = true
        textView.keyboardDismissMode = .interactive
        textView.smartQuotesType = .no
        textView.smartDashesType = .no
        textView.textContainerInset = UIEdgeInsets(top: 12, left: 8, bottom: 12, right: 8)
        textView.inputAccessoryView = accessoryBar()
        textView.text = text
        controller.textView = textView
        Highlighter.apply(to: textView)
        return textView
    }

    func updateUIView(_ textView: YakUITextView, context: Context) {
        // Only an outside change (a load or a woven conflict) resets the text.
        guard textView.text != text else { return }
        let selection = textView.selectedRange
        textView.text = text
        textView.selectedRange = NSRange(location: min(selection.location, (text as NSString).length), length: 0)
        Highlighter.apply(to: textView)
    }

    func makeCoordinator() -> Coordinator { Coordinator(text: $text, controller: controller) }

    /// The system keyboard's own accessory bar: indent, outdent, bullet, checklist,
    /// bold, italic, and link, laid out and animated by iOS (ADR 0008's Option C).
    private func accessoryBar() -> UIToolbar {
        let bar = UIToolbar(frame: CGRect(x: 0, y: 0, width: 320, height: 44))
        var items: [UIBarButtonItem] = []
        for command in EditorCommand.allCases {
            let action = UIAction(title: command.title, image: UIImage(systemName: command.systemImage)) { [weak controller] _ in
                controller?.perform(command)
            }
            items.append(UIBarButtonItem(primaryAction: action))
            items.append(.flexibleSpace())
        }
        items.removeLast()
        bar.items = items
        bar.sizeToFit()
        return bar
    }

    @MainActor
    final class Coordinator: NSObject, UITextViewDelegate {
        @Binding var text: String
        let controller: EditorController

        init(text: Binding<String>, controller: EditorController) {
            _text = text
            self.controller = controller
        }

        func textView(_ textView: UITextView, shouldChangeTextIn range: NSRange, replacementText replacement: String) -> Bool {
            guard replacement == "\n", range.length == 0,
                  let edit = DjotEditing.newline(in: textView.currentText, at: range.location) else { return true }
            controller.apply(edit)
            return false
        }

        func textViewDidChange(_ textView: UITextView) {
            text = textView.currentText
            controller.textDidChange()
        }

        func textViewDidChangeSelection(_ textView: UITextView) {
            controller.onWikilinkQuery(DjotEditing.openWikilink(in: textView.currentText, at: textView.selectedRange.location)?.query)
        }
    }
}

#else

extension NSColor {
    static var tintColor: NSColor { .controlAccentColor }
}

extension NSTextView {
    var currentText: String { string }
    var currentSelection: NSRange { selectedRange() }

    /// Replace through AppKit's text input, so the change joins the undo stack.
    func replace(_ range: NSRange, with replacement: String, select selection: NSRange) {
        guard shouldChangeText(in: range, replacementString: replacement) else { return }
        textStorage?.replaceCharacters(in: range, with: replacement)
        didChangeText()
        setSelectedRange(selection)
    }
}

/// ⌘B and ⌘I on the Mac; Tab, Shift-Tab, and Return arrive as text commands.
final class YakNSTextView: NSTextView {
    weak var controller: EditorController?

    override func performKeyEquivalent(with event: NSEvent) -> Bool {
        guard event.modifierFlags.intersection(.deviceIndependentFlagsMask) == .command else {
            return super.performKeyEquivalent(with: event)
        }
        switch event.charactersIgnoringModifiers {
        case "b": controller?.perform(.strong); return true
        case "i": controller?.perform(.emphasis); return true
        default: return super.performKeyEquivalent(with: event)
        }
    }
}

struct YakTextView: NSViewRepresentable {
    @Binding var text: String
    let controller: EditorController

    func makeNSView(context: Context) -> NSScrollView {
        let scroll = NSScrollView()
        scroll.hasVerticalScroller = true
        scroll.drawsBackground = false
        let textView = YakNSTextView(frame: .zero)
        textView.isVerticallyResizable = true
        textView.isHorizontallyResizable = false
        textView.autoresizingMask = [.width]
        textView.minSize = .zero
        textView.maxSize = NSSize(width: CGFloat.greatestFiniteMagnitude, height: .greatestFiniteMagnitude)
        textView.textContainer?.widthTracksTextView = true
        scroll.documentView = textView
        textView.delegate = context.coordinator
        textView.font = Highlighter.baseFont
        textView.isRichText = false
        textView.allowsUndo = true
        textView.isAutomaticQuoteSubstitutionEnabled = false
        textView.isAutomaticDashSubstitutionEnabled = false
        textView.isContinuousSpellCheckingEnabled = true
        textView.textContainerInset = NSSize(width: 8, height: 12)
        textView.string = text
        textView.controller = controller
        controller.textView = textView
        Highlighter.apply(to: textView)
        return scroll
    }

    func updateNSView(_ scroll: NSScrollView, context: Context) {
        guard let textView = scroll.documentView as? NSTextView, textView.string != text else { return }
        let selection = textView.selectedRange()
        textView.string = text
        textView.setSelectedRange(NSRange(location: min(selection.location, (text as NSString).length), length: 0))
        Highlighter.apply(to: textView)
    }

    func makeCoordinator() -> Coordinator { Coordinator(text: $text, controller: controller) }

    @MainActor
    final class Coordinator: NSObject, NSTextViewDelegate {
        @Binding var text: String
        let controller: EditorController

        init(text: Binding<String>, controller: EditorController) {
            _text = text
            self.controller = controller
        }

        func textView(_ textView: NSTextView, doCommandBy selector: Selector) -> Bool {
            switch selector {
            case #selector(NSResponder.insertNewline(_:)):
                guard textView.selectedRange().length == 0,
                      let edit = DjotEditing.newline(in: textView.string, at: textView.selectedRange().location) else { return false }
                controller.apply(edit)
                return true
            case #selector(NSResponder.insertTab(_:)):
                return perform(.indent, in: textView)
            case #selector(NSResponder.insertBacktab(_:)):
                return perform(.outdent, in: textView)
            default:
                return false
            }
        }

        /// Tab means Tab outside a list, so only claim it when a list item moved.
        private func perform(_ command: EditorCommand, in textView: NSTextView) -> Bool {
            guard DjotEditing.indent(in: textView.string, selection: textView.selectedRange(), outdent: command == .outdent) != nil else {
                return false
            }
            controller.perform(command)
            return true
        }

        func textDidChange(_ notification: Notification) {
            guard let textView = notification.object as? NSTextView else { return }
            text = textView.string
            controller.textDidChange()
        }

        func textViewDidChangeSelection(_ notification: Notification) {
            guard let textView = notification.object as? NSTextView else { return }
            controller.onWikilinkQuery(DjotEditing.openWikilink(in: textView.string, at: textView.selectedRange().location)?.query)
        }
    }
}
#endif
