/// Weaves two versions of a yak into one text, marking each run where they disagree.
///
/// A port of the web editor's `_lineDiff` and `_conflictMarkup` (`editor.js`), with
/// the same marker lines, so a conflict written on one device reads the same in either
/// editor and either one refuses to treat it as resolved.
public enum ConflictMarkup {
    public static let open = "<<<<<<< on disk"
    public static let split = "======="
    public static let close = ">>>>>>> my draft"

    /// The server's version and this device's, with markers around every disagreement.
    public static func weave(theirs: String, mine: String) -> String {
        var output: [Substring] = []
        let rows = lineDiff(theirs: theirs, mine: mine)
        var index = 0
        while index < rows.count {
            if case .same(let line) = rows[index] {
                output.append(line)
                index += 1
                continue
            }
            var theirLines: [Substring] = []
            var myLines: [Substring] = []
            runLoop: while index < rows.count {
                switch rows[index] {
                case .same: break runLoop
                case .theirs(let line): theirLines.append(line)
                case .mine(let line): myLines.append(line)
                }
                index += 1
            }
            output.append(Substring(open))
            output.append(contentsOf: theirLines)
            output.append(Substring(split))
            output.append(contentsOf: myLines)
            output.append(Substring(close))
        }
        return output.joined(separator: "\n")
    }

    /// Whether any line starts like a conflict marker. Deliberately loose, as on the
    /// web: a false stop costs a second look, a false pass uploads the markers.
    public static func hasMarkers(_ content: String) -> Bool {
        content.split(separator: "\n", omittingEmptySubsequences: false).contains { line in
            ["<<<<<<<", "=======", ">>>>>>>"].contains { line.hasPrefix($0) }
        }
    }

    enum Row: Equatable {
        case same(Substring)
        case theirs(Substring)
        case mine(Substring)
    }

    static func lineDiff(theirs: String, mine: String) -> [Row] {
        let left = theirs.split(separator: "\n", omittingEmptySubsequences: false)
        let right = mine.split(separator: "\n", omittingEmptySubsequences: false)
        var common = [[Int]](repeating: [Int](repeating: 0, count: right.count + 1), count: left.count + 1)
        for leftIndex in stride(from: left.count - 1, through: 0, by: -1) {
            for rightIndex in stride(from: right.count - 1, through: 0, by: -1) {
                common[leftIndex][rightIndex] = left[leftIndex] == right[rightIndex]
                    ? common[leftIndex + 1][rightIndex + 1] + 1
                    : max(common[leftIndex + 1][rightIndex], common[leftIndex][rightIndex + 1])
            }
        }

        var rows: [Row] = []
        var leftIndex = 0
        var rightIndex = 0
        while leftIndex < left.count && rightIndex < right.count {
            if left[leftIndex] == right[rightIndex] {
                rows.append(.same(left[leftIndex]))
                leftIndex += 1
                rightIndex += 1
            } else if common[leftIndex + 1][rightIndex] >= common[leftIndex][rightIndex + 1] {
                rows.append(.theirs(left[leftIndex]))
                leftIndex += 1
            } else {
                rows.append(.mine(right[rightIndex]))
                rightIndex += 1
            }
        }
        rows.append(contentsOf: left[leftIndex...].map(Row.theirs))
        rows.append(contentsOf: right[rightIndex...].map(Row.mine))
        return rows
    }
}
