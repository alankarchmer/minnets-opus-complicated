import Foundation
import AppKit

/// Layer 2: Confusion Detector
/// Heuristics to identify moments when the user might need help.
@MainActor
class ConfusionDetector: ObservableObject {
    static let shared = ConfusionDetector()
    
    @Published var confusionSignal: ConfusionSignal?
    @Published var confusionScore: Double = 0.0  // 0.0 to 1.0
    
    // Configuration
    private let thrashingThreshold = 3          // app switches
    private let thrashingWindowSeconds = 15.0
    private let stareThresholdSeconds = 5.0
    private let backspaceRatioThreshold = 0.3   // 30% of keystrokes are backspaces
    
    // Tracking
    private var appSwitchTimestamps: [(Date, String)] = []  // (time, bundleId)
    private var lastMouseMoveTime: Date = Date()
    private var lastActiveApp: String?
    private var recentKeystrokes: [KeystrokeType] = []
    private var stareTimer: Timer?
    
    private var mouseMonitor: Any?
    private var keyMonitor: Any?
    private var appObserver: NSObjectProtocol?
    
    enum ConfusionSignal: String {
        case thrashing = "Switching between apps rapidly"
        case staring = "Idle while viewing content"
        case errorRate = "High error/correction rate"
    }
    
    enum KeystrokeType {
        case character
        case backspace
        case enter
    }
    
    private init() {
        startMonitoring()
    }
    
    // MARK: - Public API
    
    func detectConfusion() -> (detected: Bool, signal: ConfusionSignal?, score: Double) {
        var signals: [(ConfusionSignal, Double)] = []
        
        // Check thrashing
        if let thrashScore = detectThrashing() {
            signals.append((.thrashing, thrashScore))
        }
        
        // Check staring
        if let stareScore = detectStaring() {
            signals.append((.staring, stareScore))
        }
        
        // Check error rate
        if let errorScore = detectHighErrorRate() {
            signals.append((.errorRate, errorScore))
        }
        
        // Return highest signal
        if let strongest = signals.max(by: { $0.1 < $1.1 }) {
            return (true, strongest.0, strongest.1)
        }
        
        return (false, nil, 0.0)
    }
    
    // MARK: - Thrashing Detection
    
    /// Detects rapid app switching (IDE ↔ Browser pattern)
    private func detectThrashing() -> Double? {
        let now = Date()
        let windowStart = now.addingTimeInterval(-thrashingWindowSeconds)
        
        // Filter to recent switches
        appSwitchTimestamps = appSwitchTimestamps.filter { $0.0 > windowStart }
        
        guard appSwitchTimestamps.count >= thrashingThreshold else {
            return nil
        }
        
        // Check for IDE ↔ Browser pattern specifically
        let browserBundles = ["com.apple.Safari", "com.google.Chrome", "org.mozilla.firefox", "com.brave.Browser"]
        let ideBundles = ["com.microsoft.VSCode", "com.apple.dt.Xcode", "com.jetbrains", "com.sublimetext"]
        
        var ideCount = 0
        var browserCount = 0
        
        for (_, bundleId) in appSwitchTimestamps {
            if browserBundles.contains(where: { bundleId.contains($0) }) {
                browserCount += 1
            } else if ideBundles.contains(where: { bundleId.contains($0) }) {
                ideCount += 1
            }
        }
        
        // Strong signal: alternating between IDE and browser
        if ideCount >= 2 && browserCount >= 2 {
            let score = min(1.0, Double(appSwitchTimestamps.count) / 6.0)
            return score
        }
        
        // Weaker signal: just lots of switching
        if appSwitchTimestamps.count >= thrashingThreshold {
            return 0.5
        }
        
        return nil
    }
    
    private func recordAppSwitch(to bundleId: String) {
        let now = Date()
        
        // Only record if actually switching to a different app
        if bundleId != lastActiveApp {
            appSwitchTimestamps.append((now, bundleId))
            lastActiveApp = bundleId
            
            // Keep only last 20 switches
            if appSwitchTimestamps.count > 20 {
                appSwitchTimestamps.removeFirst(10)
            }
            
            updateConfusionStatus()
        }
    }
    
    // MARK: - Stare Detection
    
    /// Detects when user is idle (reading/thinking) while content is displayed
    private func detectStaring() -> Double? {
        let timeSinceMove = Date().timeIntervalSince(lastMouseMoveTime)
        
        // Must be idle for at least the threshold
        guard timeSinceMove >= stareThresholdSeconds else {
            return nil
        }
        
        // Check if a document/content app is active
        guard let frontApp = NSWorkspace.shared.frontmostApplication,
              let bundleId = frontApp.bundleIdentifier else {
            return nil
        }
        
        let contentApps = [
            "com.apple.Preview",
            "com.apple.Safari",
            "com.google.Chrome",
            "org.mozilla.firefox",
            "com.microsoft.Word",
            "com.apple.iWork.Pages",
            "com.readdle.PDFExpert",
            "com.microsoft.VSCode",
            "com.apple.dt.Xcode",
            "md.obsidian",
            "com.notion.id"
        ]
        
        let isContentApp = contentApps.contains(where: { bundleId.contains($0) })
        
        if isContentApp {
            // Score increases with stare duration (caps at 30 seconds)
            let score = min(1.0, timeSinceMove / 30.0)
            return score
        }
        
        return nil
    }
    
    private func recordMouseMove() {
        lastMouseMoveTime = Date()
        
        // Cancel stare timer
        stareTimer?.invalidate()
        
        // Start new stare timer
        stareTimer = Timer.scheduledTimer(withTimeInterval: stareThresholdSeconds, repeats: false) { [weak self] _ in
            self?.updateConfusionStatus()
        }
    }
    
    // MARK: - Error Rate Detection
    
    /// Detects high backspace/correction rate (frustration signal)
    private func detectHighErrorRate() -> Double? {
        guard recentKeystrokes.count >= 20 else {
            return nil
        }
        
        let backspaceCount = recentKeystrokes.filter { $0 == .backspace }.count
        let ratio = Double(backspaceCount) / Double(recentKeystrokes.count)
        
        if ratio >= backspaceRatioThreshold {
            return min(1.0, ratio / 0.5)  // Normalize: 50% backspace = score 1.0
        }
        
        return nil
    }
    
    private func recordKeystroke(_ type: KeystrokeType) {
        recentKeystrokes.append(type)
        
        // Keep only last 50 keystrokes
        if recentKeystrokes.count > 50 {
            recentKeystrokes.removeFirst(25)
        }
        
        updateConfusionStatus()
    }
    
    // MARK: - Monitoring
    
    private func startMonitoring() {
        // Monitor mouse movement
        mouseMonitor = NSEvent.addGlobalMonitorForEvents(matching: [.mouseMoved, .leftMouseDragged]) { [weak self] _ in
            Task { @MainActor in
                self?.recordMouseMove()
            }
        }
        
        // Monitor keystrokes for error rate
        keyMonitor = NSEvent.addGlobalMonitorForEvents(matching: .keyDown) { [weak self] event in
            Task { @MainActor in
                if event.keyCode == 51 {  // Backspace
                    self?.recordKeystroke(.backspace)
                } else if event.keyCode == 36 {  // Enter
                    self?.recordKeystroke(.enter)
                } else if event.characters?.isEmpty == false {
                    self?.recordKeystroke(.character)
                }
            }
        }
        
        // Monitor app switches
        appObserver = NSWorkspace.shared.notificationCenter.addObserver(
            forName: NSWorkspace.didActivateApplicationNotification,
            object: nil,
            queue: .main
        ) { [weak self] notification in
            Task { @MainActor in
                if let app = notification.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication,
                   let bundleId = app.bundleIdentifier {
                    self?.recordAppSwitch(to: bundleId)
                }
            }
        }
    }
    
    /// Stops all monitoring - call during app termination if needed
    func stopMonitoring() {
        if let monitor = mouseMonitor {
            NSEvent.removeMonitor(monitor)
            mouseMonitor = nil
        }
        if let monitor = keyMonitor {
            NSEvent.removeMonitor(monitor)
            keyMonitor = nil
        }
        if let observer = appObserver {
            NSWorkspace.shared.notificationCenter.removeObserver(observer)
            appObserver = nil
        }
        stareTimer?.invalidate()
        stareTimer = nil
        
        appSwitchTimestamps.removeAll()
        recentKeystrokes.removeAll()
    }
    
    private func updateConfusionStatus() {
        let (detected, signal, score) = detectConfusion()
        confusionSignal = detected ? signal : nil
        confusionScore = score
    }
}

