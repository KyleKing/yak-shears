import Foundation

/// Derives a yak's display title the way the server's `derive_title` does:
/// a `title` or `name` in the frontmatter, else the first non-blank line with any
/// heading marks removed, else the filename.
///
/// Frontmatter is read for those two top-level scalar keys only, not as full YAML,
/// which is all a title needs.
public enum Title {
    public static func derive(content: String, fileName: String) -> String {
        let (metadata, body) = splitFrontmatter(content)
        for key in ["title", "name"] {
            if let value = metadata[key], !value.isEmpty {
                return value
            }
        }
        for line in body.split(separator: "\n", omittingEmptySubsequences: true) {
            let stripped = line.trimmingCharacters(in: .whitespaces)
            guard !stripped.isEmpty else { continue }
            let unmarked = stripped.drop(while: { $0 == "#" }).trimmingCharacters(in: .whitespaces)
            return unmarked.isEmpty ? stripped : unmarked
        }
        return fileName
    }

    /// Split YAML (`---` fenced) or Apple Notes export (`: key=value\`) metadata from the body.
    static func splitFrontmatter(_ content: String) -> (metadata: [String: String], body: Substring) {
        if content.hasPrefix("---\n"), let close = content.range(of: "\n---\n", range: content.index(content.startIndex, offsetBy: 3)..<content.endIndex) {
            let block = content[content.index(content.startIndex, offsetBy: 4)..<close.lowerBound]
            var metadata: [String: String] = [:]
            for line in block.split(separator: "\n") where !line.hasPrefix(" ") && !line.hasPrefix("\t") {
                guard let colon = line.firstIndex(of: ":") else { continue }
                let key = line[..<colon].trimmingCharacters(in: .whitespaces)
                let value = line[line.index(after: colon)...].trimmingCharacters(in: .whitespaces)
                metadata[key] = unquote(value)
            }
            return (metadata, content[close.upperBound...])
        }

        var metadata: [String: String] = [:]
        var rest = content[...]
        while rest.hasPrefix(": ") {
            let line = rest.prefix(while: { $0 != "\n" })
            guard let equals = line.firstIndex(of: "=") else { break }
            let key = line[line.index(line.startIndex, offsetBy: 2)..<equals].trimmingCharacters(in: .whitespaces)
            var value = line[line.index(after: equals)...]
            if value.hasSuffix("\\") { value = value.dropLast() }
            metadata[key] = value.trimmingCharacters(in: .whitespaces)
            rest = rest[line.endIndex...].drop(while: { $0 == "\n" })
        }
        return (metadata, rest)
    }

    private static func unquote(_ value: String) -> String {
        for quote in ["\"", "'"] where value.count >= 2 && value.hasPrefix(quote) && value.hasSuffix(quote) {
            return String(value.dropFirst().dropLast())
        }
        return value
    }
}
