import Foundation

/// Yak filenames are the UTC instant the yak was created, e.g. `2026-07-22T14_03_51Z.dj`.
///
/// Mirrors `filenames.CANONICAL_FORMAT` on the server. The listing sort is a plain
/// filename compare, so every writer, this app included, has to name new yaks this way.
public enum CanonicalName {
    public static let fileExtension = "dj"

    /// The canonical stem for an instant, without the extension.
    public static func stem(for date: Date) -> String {
        let parts = utc.dateComponents([.year, .month, .day, .hour, .minute, .second], from: date)
        func pad(_ value: Int?) -> String {
            let digits = String(value ?? 0)
            return digits.count < 2 ? "0" + digits : digits
        }
        return "\(parts.year ?? 0)-\(pad(parts.month))-\(pad(parts.day))T\(pad(parts.hour))_\(pad(parts.minute))_\(pad(parts.second))Z"
    }

    /// Whether a stem already has the canonical shape.
    public static func isCanonical(_ stem: String) -> Bool {
        stem.wholeMatch(of: pattern) != nil
    }

    /// The instant a canonical stem encodes, or nil for any other name.
    public static func date(from stem: String) -> Date? {
        guard let match = stem.wholeMatch(of: pattern) else { return nil }
        let parts = DateComponents(
            year: Int(match.1), month: Int(match.2), day: Int(match.3),
            hour: Int(match.4), minute: Int(match.5), second: Int(match.6)
        )
        return utc.date(from: parts)
    }

    private static let utc: Calendar = {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "UTC")!
        return calendar
    }()

    nonisolated(unsafe) private static let pattern = /(\d{4})-(\d{2})-(\d{2})T(\d{2})_(\d{2})_(\d{2})Z/
}
