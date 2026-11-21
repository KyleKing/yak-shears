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
        // Unresolved markers hold every upload back, but never a download.
        ("B", "A", "A", true, nil),
        ("B", "C", "A", true, nil),
        ("B", nil, "A", true, nil),
    ] as [(String?, String?, String?, Bool, SyncAction?)])
    func decidesFromThreeLeases(local: String?, remote: String?, base: String?, unresolved: Bool, expected: SyncAction?) {
        let plan = SyncPlanner.plan(
            local: local.map { ["p": $0] } ?? [:],
            remote: remote.map { ["p": $0] } ?? [:],
            base: base.map { ["p": $0] } ?? [:],
            unresolved: unresolved ? ["p"] : []
        )
        #expect(plan == (expected.map { [$0] } ?? []))
    }
}
