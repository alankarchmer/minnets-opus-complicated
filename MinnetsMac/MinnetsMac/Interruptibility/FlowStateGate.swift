import Foundation
import AppKit
import Carbon

/// Layer 1: Flow State Gate
/// Hard rules to prevent catastrophic annoyance.
/// If any condition is true, suggestions are completely blocked.
@MainActor
class FlowStateGate: ObservableObject {
    static let shared = FlowStateGate()
    
    @Published var isBlocked: Bool = false
    @Published var blockReason: BlockReason?
    
    // Configuration
    private let highVelocityThreshold: Double = 50.0  // chars per minute
    private let velocityWindowSeconds: Double = 5.0
    
    // Tracking
    private var keyPressTimestamps: [Date] = []
    private var eventMonitor: Any?
    private var appObserver: NSObjectProtocol?
    
    // Blacklisted apps (bundle identifiers)
    private let blacklistedApps: Set<String> = [
        "us.zoom.xos",                    // Zoom
        "com.discord.Discord",            // Discord
        "com.apple.FaceTime",             // FaceTime
        "com.microsoft.teams",            // Teams
        "com.apple.Keynote",              // Keynote (check fullscreen separately)
        "com.microsoft.Powerpoint",       // PowerPoint
        "com.google.Chrome.app.kjgfgldnnfoeklkmfkjfagphfepbbdan",  // Meet
    ]
    
    // Partial matches for banking/sensitive apps
    private let sensitiveAppPatterns: [String] = [
        "bank", "chase", "wellsfargo", "capitalone", "citi",
        "1password", "lastpass", "bitwarden", "keychain"
    ]
    
    enum BlockReason: String {
        case highVelocityTyping = "User is typing rapidly"
        case presentationMode = "Presentation in progress"
        case blacklistedApp = "Sensitive/meeting app active"
        case videoCall = "Video call in progress"
    }
    
    private init() {
        startMonitoring()
    }
    
    // MARK: - Public API
    
    func shouldBlock() -> (blocked: Bool, reason: BlockReason?) {
        // Check all conditions
        if isHighVelocityTyping() {
            return (true, .highVelocityTyping)
        }
        
        if isInPresentationMode() {
            return (true, .presentationMode)
        }
        
        if isBlacklistedAppActive() {
            return (true, .blacklistedApp)
        }
        
        return (false, nil)
    }
    
    // MARK: - High Velocity Typing Detection
    
    private func isHighVelocityTyping() -> Bool {
        let now = Date()
        let windowStart = now.addingTimeInterval(-velocityWindowSeconds)
        
        // Filter to recent keypresses
        keyPressTimestamps = keyPressTimestamps.filter { $0 > windowStart }
        
        // Calculate chars per minute
        let charsInWindow = Double(keyPressTimestamps.count)
        let charsPerMinute = charsInWindow * (60.0 / velocityWindowSeconds)
        
        return charsPerMinute > highVelocityThreshold
    }
    
    private func recordKeyPress() {
        keyPressTimestamps.append(Date())
        
        // Keep only last 100 keypresses to prevent memory growth
        if keyPressTimestamps.count > 100 {
            keyPressTimestamps.removeFirst(50)
        }
        
        updateBlockStatus()
    }
    
    // MARK: - Presentation Mode Detection
    
    private func isInPresentationMode() -> Bool {
        // Check if any presentation app is in fullscreen
        guard let frontApp = NSWorkspace.shared.frontmostApplication else {
            return false
        }
        
        let presentationApps = ["com.apple.Keynote", "com.microsoft.Powerpoint", "com.google.android.apps.docs.editors.slides"]
        
        if presentationApps.contains(frontApp.bundleIdentifier ?? "") {
            // Check if it's fullscreen
            if let screen = NSScreen.main {
                for window in NSApp.windows {
                    if window.frame == screen.frame {
                        return true
                    }
                }
            }
            
            // Also check via CGWindow
            return isAppFullscreen(bundleId: frontApp.bundleIdentifier ?? "")
        }
        
        return false
    }
    
    private func isAppFullscreen(bundleId: String) -> Bool {
        let windowList = CGWindowListCopyWindowInfo([.optionOnScreenOnly], kCGNullWindowID) as? [[String: Any]] ?? []
        
        for window in windowList {
            guard let ownerName = window[kCGWindowOwnerName as String] as? String,
                  let bounds = window[kCGWindowBounds as String] as? [String: Any] else {
                continue
            }
            
            // Check if window fills the screen
            if let screen = NSScreen.main {
                let windowWidth = bounds["Width"] as? CGFloat ?? 0
                let windowHeight = bounds["Height"] as? CGFloat ?? 0
                
                if windowWidth >= screen.frame.width && windowHeight >= screen.frame.height {
                    return true
                }
            }
        }
        
        return false
    }
    
    // MARK: - Blacklisted App Detection
    
    private func isBlacklistedAppActive() -> Bool {
        guard let frontApp = NSWorkspace.shared.frontmostApplication,
              let bundleId = frontApp.bundleIdentifier?.lowercased() else {
            return false
        }
        
        // Direct blacklist check
        if blacklistedApps.contains(bundleId) {
            return true
        }
        
        // Pattern matching for banking/sensitive apps
        for pattern in sensitiveAppPatterns {
            if bundleId.contains(pattern) {
                return true
            }
        }
        
        // Check app name as fallback
        let appName = frontApp.localizedName?.lowercased() ?? ""
        for pattern in sensitiveAppPatterns {
            if appName.contains(pattern) {
                return true
            }
        }
        
        return false
    }
    
    // MARK: - Monitoring
    
    private func startMonitoring() {
        // Monitor global key events for typing velocity
        eventMonitor = NSEvent.addGlobalMonitorForEvents(matching: .keyDown) { [weak self] event in
            // Only count character keys, not modifiers
            if event.characters?.isEmpty == false {
                self?.recordKeyPress()
            }
        }
        
        // Monitor app switches
        appObserver = NSWorkspace.shared.notificationCenter.addObserver(
            forName: NSWorkspace.didActivateApplicationNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            self?.updateBlockStatus()
        }
    }
    
    private func updateBlockStatus() {
        let (blocked, reason) = shouldBlock()
        
        DispatchQueue.main.async {
            self.isBlocked = blocked
            self.blockReason = reason
        }
    }
    
    deinit {
        if let monitor = eventMonitor {
            NSEvent.removeMonitor(monitor)
        }
        if let observer = appObserver {
            NSWorkspace.shared.notificationCenter.removeObserver(observer)
        }
    }
}

