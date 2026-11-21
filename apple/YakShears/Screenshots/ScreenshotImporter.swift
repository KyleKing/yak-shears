#if os(iOS)
import Photos
import UIKit
import Vision
import YakShearsKit

/// Turns screenshots in Photos into yaks: one yak per screenshot, named for when it
/// was taken, holding the image and the text Vision reads from it, so the yak is
/// searchable by what the screenshot said.
///
/// The image goes through `PendingMedia` like any other attachment, so importing
/// works offline and uploads on the next sync. Deleting the originals goes through
/// PhotoKit, which always asks the reader to confirm.
@MainActor
enum ScreenshotImporter {
    /// Screenshots land in their own category: the server files media by category,
    /// so a yak holding an image cannot sit at the vault root.
    static let category = "screenshots"

    enum Failure: LocalizedError {
        case notAuthorized
        case noScreenshots
        case unreadable

        var errorDescription: String? {
            switch self {
            case .notAuthorized: "Yak Shears needs access to Photos to import screenshots. Allow it in Settings › Privacy › Photos."
            case .noScreenshots: "There are no screenshots in Photos."
            case .unreadable: "The screenshot could not be read from Photos."
            }
        }
    }

    /// Ask for read-write access, which deleting the originals needs.
    static func authorize() async throws {
        let status = await PHPhotoLibrary.requestAuthorization(for: .readWrite)
        guard status == .authorized || status == .limited else { throw Failure.notAuthorized }
    }

    /// The newest screenshots, newest first.
    static func recent(limit: Int) -> [PHAsset] {
        let options = PHFetchOptions()
        options.predicate = NSPredicate(
            format: "(mediaSubtypes & %d) != 0", PHAssetMediaSubtype.photoScreenshot.rawValue
        )
        options.sortDescriptors = [NSSortDescriptor(key: "creationDate", ascending: false)]
        options.fetchLimit = limit
        let result = PHAsset.fetchAssets(with: .image, options: options)
        return (0..<result.count).map { result.object(at: $0) }
    }

    /// Import each screenshot as a yak, then optionally delete the originals.
    ///
    /// - Returns: The new yaks' paths, and whether the originals were deleted (the
    ///   reader can decline the system's confirmation, which keeps them).
    static func importScreenshots(_ assets: [PHAsset], deleteOriginals: Bool) async throws -> (paths: [String], deleted: Bool) {
        var paths: [String] = []
        for asset in assets {
            guard let data = await imageData(for: asset) else { throw Failure.unreadable }
            let text = await recognizedText(in: data)
            let path = try Vault.app.create(in: category, at: asset.creationDate ?? .now)
            let embed = try PendingMedia.app.enqueue(data, filename: originalFilename(of: asset), for: path)
            try Vault.app.write(path, content: ScreenshotYak.compose(embed: embed, recognizedText: text))
            paths.append(path)
        }

        var deleted = false
        if deleteOriginals, !assets.isEmpty {
            do {
                try await PHPhotoLibrary.shared().performChanges {
                    PHAssetChangeRequest.deleteAssets(assets as NSArray)
                }
                deleted = true
            } catch {
                // Declined at the system prompt: the yaks exist, the originals stay.
            }
        }
        return (paths, deleted)
    }

    static func thumbnail(for asset: PHAsset, side: CGFloat) async -> UIImage? {
        let options = PHImageRequestOptions()
        options.deliveryMode = .highQualityFormat
        options.isNetworkAccessAllowed = true
        let size = CGSize(width: side, height: side)
        return await withCheckedContinuation { continuation in
            PHImageManager.default().requestImage(for: asset, targetSize: size, contentMode: .aspectFill, options: options) { image, _ in
                continuation.resume(returning: image)
            }
        }
    }

    private static func imageData(for asset: PHAsset) async -> Data? {
        let options = PHImageRequestOptions()
        options.deliveryMode = .highQualityFormat
        options.isNetworkAccessAllowed = true
        options.version = .current
        return await withCheckedContinuation { continuation in
            PHImageManager.default().requestImageDataAndOrientation(for: asset, options: options) { data, _, _, _ in
                continuation.resume(returning: data)
            }
        }
    }

    private static func recognizedText(in data: Data) async -> [String] {
        var request = RecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = true
        let observations = (try? await request.perform(on: data)) ?? []
        return observations.compactMap { $0.topCandidates(1).first?.string }
    }

    private static func originalFilename(of asset: PHAsset) -> String {
        PHAssetResource.assetResources(for: asset).first?.originalFilename ?? "screenshot.png"
    }
}
#endif
