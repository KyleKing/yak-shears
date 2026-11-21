import Foundation
import Observation
import Security
import YakShearsKit

/// Which server this device syncs with, and the bearer token for it.
///
/// The URL lives in UserDefaults; the token lives in the Keychain, scoped to this
/// device only, so it is never in a backup or the Files app.
@MainActor @Observable
final class Account {
    /// Shared by the app's views and its App Intents.
    static let shared = Account()

    static let defaultServer = URL(string: "https://yak-shears.kyleking.me")!
    private static let serverKey = "serverURL"

    private(set) var server: URL?
    private(set) var token: String?

    init() {
        server = UserDefaults.standard.url(forKey: Self.serverKey)
        token = server.flatMap { Keychain.read(account: $0.absoluteString) }
    }

    var isSignedIn: Bool { server != nil && token != nil }

    var client: SyncClient? {
        guard let server, let token else { return nil }
        return SyncClient(baseURL: server, token: token)
    }

    /// The base leases belong to one server, so each server gets its own file.
    var syncStateURL: URL? {
        server.map { server in
            URL.applicationSupportDirectory.appending(path: "sync-base-\(server.host() ?? "server").json")
        }
    }

    func signIn(server: URL, email: String, password: String) async throws {
        let token = try await SyncClient(baseURL: server).signIn(email: email, password: password)
        Keychain.write(token, account: server.absoluteString)
        UserDefaults.standard.set(server, forKey: Self.serverKey)
        self.server = server
        self.token = token
    }

    /// Forget the token here, and revoke it on the server when it can be reached.
    func signOut() async {
        try? await client?.signOut()
        if let server {
            Keychain.delete(account: server.absoluteString)
        }
        token = nil
    }

    /// The server refused the token (expired or revoked elsewhere): drop it locally.
    func tokenWasRejected() {
        if let server {
            Keychain.delete(account: server.absoluteString)
        }
        token = nil
    }
}

private enum Keychain {
    private static let service = "me.kyleking.yakshears.sync"

    private static func query(account: String) -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecUseDataProtectionKeychain as String: true,
        ]
    }

    static func read(account: String) -> String? {
        var query = query(account: account)
        query[kSecReturnData as String] = true
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess, let data = item as? Data else {
            return nil
        }
        return String(data: data, encoding: .utf8)
    }

    static func write(_ value: String, account: String) {
        delete(account: account)
        var item = query(account: account)
        item[kSecValueData as String] = Data(value.utf8)
        item[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        SecItemAdd(item as CFDictionary, nil)
    }

    static func delete(account: String) {
        SecItemDelete(query(account: account) as CFDictionary)
    }
}
