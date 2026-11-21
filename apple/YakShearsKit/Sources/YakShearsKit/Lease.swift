import Foundation

/// A content fingerprint, identical to the server's `yak_lease`: the first 16 hex
/// characters of the SHA-256 of the UTF-8 text.
///
/// The sync API sends it as an ETag and checks it on every write. Because it is a
/// pure function of the text, the client can tell whether a file changed since the
/// last sync by comparing the file's lease to the one it recorded then, with no
/// second store of content.
public enum Lease {
    public static let length = 16

    public static func of(_ content: String) -> String {
        SHA256.hex(Array(content.utf8)).prefix(length).lowercased()
    }
}

/// SHA-256 (FIPS 180-4), written out because CryptoKit is Apple-only and this
/// package also builds on Linux. Used for fingerprints, not for security.
enum SHA256 {
    static func hex(_ message: [UInt8]) -> String {
        digest(message).map { byte in
            let digits = String(byte, radix: 16)
            return digits.count == 1 ? "0" + digits : digits
        }.joined()
    }

    static func digest(_ message: [UInt8]) -> [UInt8] {
        var hash: [UInt32] = [
            0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
        ]
        var padded = message
        padded.append(0x80)
        while padded.count % 64 != 56 { padded.append(0) }
        let bitLength = UInt64(message.count) * 8
        for shift in stride(from: 56, through: 0, by: -8) {
            padded.append(UInt8(truncatingIfNeeded: bitLength >> UInt64(shift)))
        }

        var schedule = [UInt32](repeating: 0, count: 64)
        for chunkStart in stride(from: 0, to: padded.count, by: 64) {
            for index in 0..<16 {
                let offset = chunkStart + index * 4
                schedule[index] = UInt32(padded[offset]) << 24 | UInt32(padded[offset + 1]) << 16
                    | UInt32(padded[offset + 2]) << 8 | UInt32(padded[offset + 3])
            }
            for index in 16..<64 {
                let early = schedule[index - 15], late = schedule[index - 2]
                let sigma0 = early.rotatedRight(7) ^ early.rotatedRight(18) ^ (early >> 3)
                let sigma1 = late.rotatedRight(17) ^ late.rotatedRight(19) ^ (late >> 10)
                schedule[index] = schedule[index - 16] &+ sigma0 &+ schedule[index - 7] &+ sigma1
            }

            var working = hash
            for index in 0..<64 {
                let (a, b, c, d, e, f, g, h) = (working[0], working[1], working[2], working[3], working[4], working[5], working[6], working[7])
                let sum1 = e.rotatedRight(6) ^ e.rotatedRight(11) ^ e.rotatedRight(25)
                let choice = (e & f) ^ (~e & g)
                let temp1 = h &+ sum1 &+ choice &+ roundConstants[index] &+ schedule[index]
                let sum0 = a.rotatedRight(2) ^ a.rotatedRight(13) ^ a.rotatedRight(22)
                let majority = (a & b) ^ (a & c) ^ (b & c)
                let temp2 = sum0 &+ majority
                working = [temp1 &+ temp2, a, b, c, d &+ temp1, e, f, g]
            }
            for index in 0..<8 { hash[index] = hash[index] &+ working[index] }
        }
        return hash.flatMap { word in (0..<4).map { UInt8(truncatingIfNeeded: word >> UInt32(24 - $0 * 8)) } }
    }

    private static let roundConstants: [UInt32] = [
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
    ]
}

private extension UInt32 {
    func rotatedRight(_ count: UInt32) -> UInt32 {
        (self >> count) | (self << (32 - count))
    }
}
