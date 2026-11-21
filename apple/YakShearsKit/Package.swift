// swift-tools-version: 6.2
// The app's logic, kept free of SwiftUI so it builds and tests on Linux as well as Apple platforms.

import PackageDescription

let package = Package(
    name: "YakShearsKit",
    platforms: [.iOS(.v26), .macOS(.v26)],
    products: [
        .library(name: "YakShearsKit", targets: ["YakShearsKit"]),
    ],
    targets: [
        .target(name: "YakShearsKit"),
        .testTarget(name: "YakShearsKitTests", dependencies: ["YakShearsKit"]),
    ]
)
