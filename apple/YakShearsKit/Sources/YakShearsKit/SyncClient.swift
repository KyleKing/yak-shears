import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// One yak as the server's manifest lists it.
public struct RemoteYak: Decodable, Hashable, Sendable {
    public let path: String
    public let lease: String
    public let modified: String
}

public enum SyncError: Error, Equatable, Sendable {
    /// The token is missing, expired, or revoked; sign in again.
    case unauthorized
    /// The yak is not on the server (deleted there, or never uploaded).
    case notFound
    /// The server's copy is not the version the write assumed. Carries what the
    /// server has, which is everything needed to show or weave the difference.
    case conflict(current: String, lease: String)
    /// Any other refusal, with the server's message when it sent one.
    case server(status: Int, message: String)
}

/// The `/api/v1` sync API. Every write is conditional: an update or delete names
/// the lease it replaces, and a create asserts that nothing exists yet.
public struct SyncClient: Sendable {
    public let baseURL: URL
    public var token: String?
    private let session: URLSession

    public init(baseURL: URL, token: String? = nil, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.token = token
        self.session = session
    }

    /// Trade credentials for a bearer token.
    public func signIn(email: String, password: String) async throws -> String {
        struct Credentials: Encodable { let email: String; let password: String }
        struct Issued: Decodable { let token: String }
        var request = URLRequest(url: baseURL.appending(path: "api/v1/token"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(Credentials(email: email, password: password))
        let (data, _) = try await send(request, accepting: [201])
        return try JSONDecoder().decode(Issued.self, from: data).token
    }

    /// Revoke the token this client carries.
    public func signOut() async throws {
        _ = try await send(authorized("api/v1/token", method: "DELETE"), accepting: [204])
    }

    public func manifest() async throws -> [RemoteYak] {
        struct Manifest: Decodable { let yaks: [RemoteYak] }
        let (data, _) = try await send(authorized("api/v1/yaks"), accepting: [200])
        return try JSONDecoder().decode(Manifest.self, from: data).yaks
    }

    /// A yak's text and its lease.
    public func fetch(_ path: String) async throws -> (content: String, lease: String) {
        let (data, response) = try await send(authorized(yakPath(path)), accepting: [200])
        return (String(decoding: data, as: UTF8.self), Self.lease(from: response))
    }

    /// Create a yak, refusing if one already exists at the path.
    public func create(_ path: String, content: String) async throws -> String {
        var request = authorized(yakPath(path), method: "PUT")
        request.setValue("*", forHTTPHeaderField: "If-None-Match")
        request.httpBody = Data(content.utf8)
        return Self.lease(from: try await send(request, accepting: [201]).1)
    }

    /// Replace a yak, but only if the server still has the version `lease` names.
    public func update(_ path: String, content: String, replacing lease: String) async throws -> String {
        var request = authorized(yakPath(path), method: "PUT")
        request.setValue("\"\(lease)\"", forHTTPHeaderField: "If-Match")
        request.httpBody = Data(content.utf8)
        return Self.lease(from: try await send(request, accepting: [200]).1)
    }

    /// Delete a yak, but only if the server still has the version `lease` names.
    public func delete(_ path: String, replacing lease: String) async throws {
        var request = authorized(yakPath(path), method: "DELETE")
        request.setValue("\"\(lease)\"", forHTTPHeaderField: "If-Match")
        _ = try await send(request, accepting: [204])
    }

    private func yakPath(_ path: String) -> String {
        "api/v1/yaks/" + path
    }

    private func authorized(_ path: String, method: String = "GET") -> URLRequest {
        var request = URLRequest(url: baseURL.appending(path: path))
        request.httpMethod = method
        if let token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        return request
    }

    private func send(_ request: URLRequest, accepting statuses: Set<Int>) async throws -> (Data, HTTPURLResponse) {
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw SyncError.server(status: 0, message: "Not an HTTP response")
        }
        if statuses.contains(http.statusCode) {
            return (data, http)
        }
        switch http.statusCode {
        case 401:
            throw SyncError.unauthorized
        case 404:
            throw SyncError.notFound
        case 412:
            throw SyncError.conflict(current: String(decoding: data, as: UTF8.self), lease: Self.lease(from: http))
        default:
            struct Refusal: Decodable { let error: String }
            let message = (try? JSONDecoder().decode(Refusal.self, from: data).error) ?? String(decoding: data, as: UTF8.self)
            throw SyncError.server(status: http.statusCode, message: message)
        }
    }

    private static func lease(from response: HTTPURLResponse) -> String {
        let etag = response.value(forHTTPHeaderField: "ETag") ?? ""
        return etag.replacingOccurrences(of: "W/", with: "").trimmingCharacters(in: CharacterSet(charactersIn: "\""))
    }
}
