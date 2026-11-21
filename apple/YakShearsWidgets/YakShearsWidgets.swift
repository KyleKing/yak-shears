import AppIntents
import SwiftUI
import WidgetKit
import YakShearsKit

@main
struct YakShearsWidgets: WidgetBundle {
    var body: some Widget {
        RecentYaksWidget()
        NewYakWidget()
        NewYakControl()
    }
}

// MARK: - Recent yaks

struct RecentYaksEntry: TimelineEntry {
    let date: Date
    let recent: RecentYaks?
}

/// Reads the snapshot the app writes into the App Group after every reload. The app
/// asks WidgetKit to reload when it writes one, so the timeline never polls.
struct RecentYaksProvider: TimelineProvider {
    func placeholder(in context: Context) -> RecentYaksEntry {
        RecentYaksEntry(date: .now, recent: nil)
    }

    func getSnapshot(in context: Context, completion: @escaping (RecentYaksEntry) -> Void) {
        completion(entry())
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<RecentYaksEntry>) -> Void) {
        completion(Timeline(entries: [entry()], policy: .never))
    }

    private func entry() -> RecentYaksEntry {
        RecentYaksEntry(date: .now, recent: AppGroup.container.flatMap(RecentYaks.read(from:)))
    }
}

/// The yaks touched most recently, each opening in the editor.
struct RecentYaksWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "RecentYaks", provider: RecentYaksProvider()) { entry in
            RecentYaksView(entry: entry)
                .containerBackground(.fill.tertiary, for: .widget)
        }
        .configurationDisplayName("Recent Yaks")
        .description("The yaks you edited last, one tap from the editor.")
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge, .accessoryRectangular])
    }
}

struct RecentYaksView: View {
    @Environment(\.widgetFamily) private var family
    let entry: RecentYaksEntry

    private var rows: Int {
        switch family {
        case .systemLarge: 7
        case .systemMedium: 3
        case .accessoryRectangular: 2
        default: 3
        }
    }

    var body: some View {
        let entries = Array((entry.recent?.entries ?? []).prefix(rows))
        VStack(alignment: .leading, spacing: family == .accessoryRectangular ? 0 : 6) {
            if family != .accessoryRectangular {
                HStack {
                    Text("Yaks").font(.headline)
                    if let conflicts = entry.recent?.conflicts, conflicts > 0 {
                        Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(.orange)
                    }
                    Spacer()
                    Link(destination: AppLink.new(category: nil).url) {
                        Image(systemName: "square.and.pencil")
                    }
                }
            }
            if entries.isEmpty {
                Text("Open Yak Shears to sync.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            ForEach(entries, id: \.path) { yak in
                // A small widget is one tap target, so only larger ones link per row.
                if family == .systemSmall {
                    row(yak)
                } else {
                    Link(destination: AppLink.open(path: yak.path).url) { row(yak) }
                }
            }
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .widgetURL(family == .systemSmall ? entries.first.map { AppLink.open(path: $0.path).url } : nil)
    }

    private func row(_ yak: RecentYaks.Entry) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(yak.title).font(.subheadline).lineLimit(1)
            if family == .systemLarge || family == .systemMedium {
                Text(yak.modified, format: .relative(presentation: .named))
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

// MARK: - New yak

/// A lock-screen button straight into a new, empty yak.
struct NewYakWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "NewYak", provider: RecentYaksProvider()) { _ in
            Image(systemName: "square.and.pencil")
                .font(.title2)
                .widgetAccentable()
                .containerBackground(.fill.tertiary, for: .widget)
                .widgetURL(AppLink.new(category: nil).url)
        }
        .configurationDisplayName("New Yak")
        .description("Opens a new, empty yak.")
        .supportedFamilies([.accessoryCircular])
    }
}

/// The same, for Control Center, the Lock Screen's control slots, and the Action
/// Button's control list. `OpenURLIntent` is the system's, so the extension needs no
/// app code to run it.
struct NewYakControl: ControlWidget {
    var body: some ControlWidgetConfiguration {
        StaticControlConfiguration(kind: "me.kyleking.yakshears.new-yak") {
            ControlWidgetButton(action: OpenURLIntent(AppLink.new(category: nil).url)) {
                Label("New Yak", systemImage: "square.and.pencil")
            }
        }
        .displayName("New Yak")
        .description("Opens a new, empty yak.")
    }
}
