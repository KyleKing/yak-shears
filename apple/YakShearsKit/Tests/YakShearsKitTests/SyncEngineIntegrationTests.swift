import Foundation
import Testing
@testable import YakShearsKit

/// Two devices syncing through the real server (`scripts/sync_fixture_server.py`).
///
/// Skipped unless `YAK_SHEARS_TEST_SERVER` names a running fixture server. Each run
/// works in its own category, so reruns against the same server do not collide.
@Suite(.enabled(if: ProcessInfo.processInfo.environment["YAK_SHEARS_TEST_SERVER"] != nil))
struct SyncEngineIntegrationTests {
    let server = URL(string: ProcessInfo.processInfo.environment["YAK_SHEARS_TEST_SERVER"] ?? "http://127.0.0.1:8765")!
    let category = "run-\(UUID().uuidString.prefix(8).lowercased())"

    struct Device {
        let vault: Vault
        let engine: SyncEngine

        let category: String

        /// Sync, keeping only what happened to this test's own yaks: other tests and
        /// earlier runs share the server.
        func sync() async throws -> SyncReport {
            let mine = { (paths: [String]) in paths.filter { $0.hasPrefix(category + "/") } }
            var report = try await engine.sync()
            report.downloaded = mine(report.downloaded)
            report.uploaded = mine(report.uploaded)
            report.deleted = mine(report.deleted)
            report.conflicted = mine(report.conflicted)
            report.unresolved = mine(report.unresolved)
            report.failed = report.failed.filter { $0.key.hasPrefix(category + "/") }
            return report
        }
    }

    func device() async throws -> Device {
        let scratch = FileManager.default.temporaryDirectory.appending(path: "yak-device-\(UUID().uuidString)")
        let token = try await SyncClient(baseURL: server).signIn(email: "test@example.com", password: "secure123")
        let vault = Vault(root: scratch.appending(path: "Vault"))
        let engine = SyncEngine(
            vault: vault, client: SyncClient(baseURL: server, token: token), stateURL: scratch.appending(path: "sync-base.json")
        )
        return Device(vault: vault, engine: engine, category: category)
    }

    @Test func editsTravelBothWaysAndConflictsAreWovenNotOverwritten() async throws {
        let phone = try await device()
        let laptop = try await device()
        let path = "\(category)/2026-11-21T09_15_00Z.dj"

        // Created on the phone, arrives on the laptop.
        try phone.vault.write(path, content: "# Groceries\n- eggs\n")
        #expect(try await phone.sync().uploaded == [path])
        #expect(try await laptop.sync().downloaded == [path])
        #expect(try laptop.vault.read(path) == "# Groceries\n- eggs\n")

        // Edited on the laptop, arrives on the phone.
        try laptop.vault.write(path, content: "# Groceries\n- eggs\n- milk\n")
        #expect(try await laptop.sync().uploaded == [path])
        #expect(try await phone.sync().downloaded == [path])

        // Both edit the same line: the second to sync gets both versions, marked.
        try phone.vault.write(path, content: "# Groceries\n- eggs\n- oat milk\n")
        try laptop.vault.write(path, content: "# Groceries\n- eggs\n- whole milk\n")
        #expect(try await phone.sync().uploaded == [path])
        #expect(try await laptop.sync().conflicted == [path])
        let woven = try laptop.vault.read(path)
        #expect(woven.contains("- oat milk") && woven.contains("- whole milk") && ConflictMarkup.hasMarkers(woven))

        // Unresolved markers never upload.
        let held = try await laptop.sync()
        #expect(held.unresolved == [path] && held.uploaded.isEmpty)

        // Resolving by hand uploads as an ordinary edit.
        try laptop.vault.write(path, content: "# Groceries\n- eggs\n- oat milk\n- whole milk\n")
        #expect(try await laptop.sync().uploaded == [path])
        #expect(try await phone.sync().downloaded == [path])
        #expect(try phone.vault.read(path) == "# Groceries\n- eggs\n- oat milk\n- whole milk\n")

        // Deleted on the phone, gone from the laptop.
        try phone.vault.delete(path)
        #expect(try await phone.sync().deleted == [path])
        #expect(try await laptop.sync().deleted == [path])
        #expect(try laptop.vault.leases().leases[path] == nil)
    }

    @Test func aHandNamedNewYakIsReportedAndTheRestStillSyncs() async throws {
        let phone = try await device()
        let handNamed = "\(category)/shopping.dj"
        let canonical = "\(category)/2026-11-21T10_00_00Z.dj"
        try phone.vault.write(handNamed, content: "hand")
        try phone.vault.write(canonical, content: "canonical")

        let report = try await phone.sync()

        #expect(report.failed.keys.sorted() == [handNamed])
        #expect(report.uploaded == [canonical])
    }

    @Test func aRevokedTokenStopsTheSync() async throws {
        let token = try await SyncClient(baseURL: server).signIn(email: "test@example.com", password: "secure123")
        let client = SyncClient(baseURL: server, token: token)
        try await client.signOut()

        await #expect(throws: SyncError.unauthorized) { try await client.manifest() }
    }
}
