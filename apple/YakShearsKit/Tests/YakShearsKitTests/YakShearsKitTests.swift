import Foundation
import Testing
@testable import YakShearsKit

@Suite struct CanonicalNameTests {
    @Test func stemMatchesTheServerFormat() {
        let date = Date(timeIntervalSince1970: 1_784_729_031) // 2026-07-22T14:03:51Z
        #expect(CanonicalName.stem(for: date) == "2026-07-22T14_03_51Z")
        #expect(CanonicalName.date(from: "2026-07-22T14_03_51Z") == date)
    }

    @Test(arguments: [
        ("2026-07-22T14_03_51Z", true),
        ("2026-07-22T14:03:51Z", false),
        ("2026-07-22", false),
        ("hand-named", false),
    ])
    func recognisesOnlyTheCanonicalShape(stem: String, expected: Bool) {
        #expect(CanonicalName.isCanonical(stem) == expected)
        #expect((CanonicalName.date(from: stem) != nil) == expected)
    }
}

@Suite struct TitleTests {
    @Test(arguments: [
        ("---\ntitle: From YAML\n---\n# Heading\n", "From YAML"),
        ("---\nname: \"Quoted\"\ntags: [a]\n---\nBody\n", "Quoted"),
        ("---\ntags:\n  title: nested\n---\nBody line\n", "Body line"),
        (": title=From Export\\\n: created=2026\\\n\nBody\n", "From Export"),
        ("\n\n## A heading\nBody\n", "A heading"),
        ("####\nBody\n", "####"),
        ("", "2026-07-22T14_03_51Z.dj"),
    ])
    func matchesTheServersDerivation(content: String, expected: String) {
        #expect(Title.derive(content: content, fileName: "2026-07-22T14_03_51Z.dj") == expected)
    }
}

@Suite struct VaultTests {
    @Test func listsYaksNewestFirstAndSkipsHiddenDirectories() throws {
        let root = FileManager.default.temporaryDirectory.appending(path: UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let files = [
            "2026-01-01T00_00_00Z.dj": "# Oldest",
            "notes/2026-07-22T14_03_51Z.dj": "# Newest",
            "notes/hand-named.dj": "Hand",
            ".stversions/2026-12-31T00_00_00Z.dj": "backup",
            "notes/readme.txt": "not a yak",
        ]
        for (path, content) in files {
            let url = root.appending(path: path)
            try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
            try content.write(to: url, atomically: true, encoding: .utf8)
        }

        let vault = Vault(root: root)
        let summaries = try vault.summaries()

        #expect(summaries.map(\.path) == ["notes/hand-named.dj", "notes/2026-07-22T14_03_51Z.dj", "2026-01-01T00_00_00Z.dj"])
        #expect(summaries.map(\.title) == ["Hand", "Newest", "Oldest"])
        #expect(summaries.map(\.category) == ["notes", "notes", nil])
        #expect(summaries[0].created == nil)
        #expect(summaries[1].created == CanonicalName.date(from: "2026-07-22T14_03_51Z"))
        #expect(try vault.read("notes/2026-07-22T14_03_51Z.dj") == "# Newest")
    }

    @Test func createdYaksAreCanonicalAndNeverCollide() throws {
        let root = FileManager.default.temporaryDirectory.appending(path: UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let vault = Vault(root: root)
        let instant = try #require(CanonicalName.date(from: "2026-11-21T09_15_00Z"))

        let first = try vault.create(in: "notes", at: instant)
        let second = try vault.create(in: "notes", at: instant)
        let rooted = try vault.create(in: nil, at: instant)

        #expect(first == "notes/2026-11-21T09_15_00Z.dj")
        #expect(second == "notes/2026-11-21T09_15_01Z.dj")
        #expect(rooted == "2026-11-21T09_15_00Z.dj")
        #expect(try vault.read(first).isEmpty)
    }

    @Test(arguments: [
        // (on disk when the editor saves, expected on disk after)
        ("opened", "edited"),
        ("synced in", "\(ConflictMarkup.open)\nsynced in\n\(ConflictMarkup.split)\nedited\n\(ConflictMarkup.close)"),
        (nil, "edited"),
    ] as [(String?, String)])
    func saveNeverOverwritesAChangeMadeUnderneath(onDisk: String?, expected: String) throws {
        let root = FileManager.default.temporaryDirectory.appending(path: UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let vault = Vault(root: root)
        let path = "notes/2026-11-21T09_15_00Z.dj"
        if let onDisk {
            try vault.write(path, content: onDisk)
        }

        let saved = try vault.save(path, content: "edited", replacing: Lease.of("opened"))

        #expect(saved.content == expected)
        #expect(saved.lease == Lease.of(expected))
        #expect(try vault.read(path) == expected)
    }

    @Test func missingRootListsNothing() throws {
        let vault = Vault(root: FileManager.default.temporaryDirectory.appending(path: UUID().uuidString))
        #expect(try vault.summaries().isEmpty)
    }
}
