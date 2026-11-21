import Foundation
import Testing
@testable import YakShearsKit

@Suite struct LeaseTests {
    /// Expected values come from the server's `yak_lease`, so a drift in either
    /// implementation fails here rather than as a phantom conflict on every sync.
    @Test(arguments: [
        ("", "e3b0c44298fc1c14"),
        ("# Existing\n", "6834266323e35839"),
        ("Ünïcödé ✂️ yak", "a49267649c036874"),
        (String(repeating: "x", count: 55), "d5e285683cd4efc0"),
        (String(repeating: "x", count: 56), "04c26261370ee754"),
        (String(repeating: "x", count: 64), "7ce100971f64e700"),
        (String(repeating: "x", count: 1000), "44f8354494a5ba03"),
    ])
    func matchesTheServer(content: String, expected: String) {
        #expect(Lease.of(content) == expected)
    }
}

@Suite struct ConflictMarkupTests {
    @Test(arguments: [
        ("a\nb\nc", "a\nB\nc", "a\n<<<<<<< on disk\nb\n=======\nB\n>>>>>>> my draft\nc"),
        ("same", "same", "same"),
        ("a\nb", "a\nb\nmine only", "a\nb\n<<<<<<< on disk\n=======\nmine only\n>>>>>>> my draft"),
    ])
    func weavesOnlyTheDisagreements(theirs: String, mine: String, expected: String) {
        #expect(ConflictMarkup.weave(theirs: theirs, mine: mine) == expected)
    }

    @Test(arguments: [
        ("plain text", false),
        ("Heading\n=======\n", true),
        ("inline <<<<<<< is fine", false),
        (ConflictMarkup.weave(theirs: "a", mine: "b"), true),
    ])
    func recognisesMarkersAtLineStart(content: String, expected: Bool) {
        #expect(ConflictMarkup.hasMarkers(content) == expected)
    }
}

@Suite struct SyncPlannerTests {
    /// One yak at path "p", described by (local, remote, base) leases; nil is absent.
    @Test(arguments: [
        // Nothing changed anywhere.
        ("A", "A", "A", false, nil),
        // One side changed.
        ("A", "B", "A", false, .download(path: "p")),
        ("B", "A", "A", false, .upload(path: "p", replacing: "A")),
        (nil, "A", "A", false, .deleteRemote(path: "p", replacing: "A")),
        ("A", nil, "A", false, .deleteLocal(path: "p")),
        // New on one side only.
        ("A", nil, nil, false, .upload(path: "p", replacing: nil)),
        (nil, "A", nil, false, .download(path: "p")),
        // Both changed.
        ("B", "B", "A", false, .adopt(path: "p", lease: "B")),
        ("A", "A", nil, false, .adopt(path: "p", lease: "A")),
        ("B", "C", "A", false, .conflict(path: "p")),
        ("B", "C", nil, false, .conflict(path: "p")),
        (nil, nil, "A", false, .forget(path: "p")),
        // An edit beats a delete, whichever side deleted.
        (nil, "B", "A", false, .download(path: "p")),
        ("B", nil, "A", false, .upload(path: "p", replacing: nil)),
        // A held yak (markers, or media still uploading) never uploads, but still downloads.
        ("B", "A", "A", true, nil),
        ("B", "C", "A", true, nil),
        ("B", nil, "A", true, nil),
    ] as [(String?, String?, String?, Bool, SyncAction?)])
    func decidesFromThreeLeases(local: String?, remote: String?, base: String?, held: Bool, expected: SyncAction?) {
        let plan = SyncPlanner.plan(
            local: local.map { ["p": $0] } ?? [:],
            remote: remote.map { ["p": $0] } ?? [:],
            base: base.map { ["p": $0] } ?? [:],
            held: held ? ["p"] : []
        )
        #expect(plan == (expected.map { [$0] } ?? []))
    }
}

@Suite struct InboxTests {
    @Test func capturesMoveIntoTheVaultUnderTheirCaptureTime() throws {
        let scratch = FileManager.default.temporaryDirectory.appending(path: UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: scratch) }
        let inbox = Inbox(root: scratch.appending(path: "Inbox"))
        let vault = Vault(root: scratch.appending(path: "Vault"))
        let instant = try #require(CanonicalName.date(from: "2026-11-21T09_15_00Z"))
        try inbox.add("first", at: instant)
        try inbox.add("same second", at: instant)

        let paths = try inbox.drain(into: vault, category: "inbox")

        #expect(paths == ["inbox/2026-11-21T09_15_00Z.dj", "inbox/2026-11-21T09_15_01Z.dj"])
        #expect(try vault.read(paths[1]) == "same second\n")
        #expect(try inbox.drain(into: vault, category: "inbox").isEmpty)
    }

    @Test(arguments: [
        ("", "https://example.com/a", "A [bracketed] title", "[A \\[bracketed\\] title](https://example.com/a)"),
        ("  read later \n", "https://example.com/a", nil, "read later\n\n<https://example.com/a>"),
        ("just text", nil, nil, "just text"),
    ] as [(String, String?, String?, String)])
    func sharedPagesBecomeDjotLinks(note: String, url: String?, title: String?, expected: String) {
        #expect(SharedContent.compose(note: note, url: url.flatMap(URL.init(string:)), title: title) == expected)
    }
}

@Suite struct PendingMediaTests {
    @Test func placeholdersResolveToTheServerURLAndHoldTheYakUntilThen() throws {
        let scratch = FileManager.default.temporaryDirectory.appending(path: UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: scratch) }
        let vault = Vault(root: scratch.appending(path: "Vault"))
        let media = PendingMedia(root: scratch.appending(path: "Media"))
        let path = "screenshots/2026-11-21T09_15_00Z.dj"

        let embed = try media.enqueue(Data([1, 2, 3]), filename: "Screen Shot 1.png", for: path)
        try vault.write(path, content: "\(embed)\n")
        let item = try #require(media.items().first)

        #expect(embed == "![Screen Shot 1](\(item.placeholder))")
        #expect(item.filename == "Screen-Shot-1.png")
        #expect(item.yakPath == path)

        try media.resolve(item, url: "/media/screenshots/abc.jpg", in: vault)

        #expect(try vault.read(path) == "![Screen Shot 1](/media/screenshots/abc.jpg)\n")
        #expect(media.items().isEmpty)
    }
}

@Suite struct ScreenshotYakTests {
    @Test(arguments: [
        (["  Order #1234 confirmed ", "", "Ships Tuesday"], "# Order #1234 confirmed\n\n![s](u)\n\n::: screenshot-text\nOrder #1234 confirmed\nShips Tuesday\n:::\n"),
        ([], "# Screenshot\n\n![s](u)\n"),
        ([String(repeating: "a", count: 70)], "# \(String(repeating: "a", count: 60))…\n\n![s](u)\n\n::: screenshot-text\n\(String(repeating: "a", count: 70))\n:::\n"),
    ])
    func titlesByTheFirstRecognisedLine(lines: [String], expected: String) {
        #expect(ScreenshotYak.compose(embed: "![s](u)", recognizedText: lines) == expected)
    }
}
