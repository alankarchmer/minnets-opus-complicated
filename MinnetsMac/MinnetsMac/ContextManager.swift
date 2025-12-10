import Foundation
import Combine
import AppKit

@MainActor
class ContextManager: ObservableObject {
    static let shared = ContextManager()
    
    @Published var currentSuggestions: [Suggestion] = []
    @Published var currentAppName: String?
    @Published var isCapturing = false
    @Published var lastCaptureTime: Date?
    @Published var isInShadowMode = true
    
    // Proactive insight timer (30 seconds)
    private var proactiveTimer: Timer?
    private let proactiveInterval: TimeInterval = 30.0
    
    // Context switch detection
    private var lastAppBundleId: String?
    private var lastCapturedContext: String = ""
    
    // Core components
    private let appleScriptCapture = AppleScriptCapture()
    private let accessibilityCapture = AccessibilityCapture()
    private let screenCapture = ScreenCapture()
    private let backendClient = BackendClient()
    
    // Interruptibility & Learning
    private let interruptibilityManager = InterruptibilityManager.shared
    private let feedbackTracker = ImplicitFeedbackTracker.shared
    private let shadowModeManager = ShadowModeManager.shared
    
    private var cancellables = Set<AnyCancellable>()
    
    private init() {
        setupObservers()
        setupAppSwitchDetection()
        
        // Check backend connectivity
        Task {
            await checkBackendConnection()
        }
        
        startProactiveInsights()
        
        // Fire initial capture after 5 seconds to give app time to initialize
        DispatchQueue.main.asyncAfter(deadline: .now() + 5.0) { [weak self] in
            Task { @MainActor in
                print("🚀 Initial proactive check (5s after launch)")
                await self?.captureAndAnalyze()
            }
        }
    }
    
    private func checkBackendConnection() async {
        do {
            let isHealthy = try await backendClient.healthCheck()
            if isHealthy {
                print("✅ Backend server is running at http://127.0.0.1:8000")
            } else {
                print("⚠️ Backend server responded but may not be healthy")
            }
        } catch let error as BackendError {
            print("❌ Backend server NOT reachable at http://127.0.0.1:8000")
            print("   Error: \(error.localizedDescription)")
            print("   💡 To start the backend:")
            print("      cd backend && source venv/bin/activate && python main.py")
        } catch {
            print("❌ Backend connection failed: \(error.localizedDescription)")
        }
    }
    
    // MARK: - Setup
    
    private func setupObservers() {
        // Observe shadow mode changes
        shadowModeManager.$isActive
            .receive(on: DispatchQueue.main)
            .sink { [weak self] isActive in
                self?.isInShadowMode = isActive
            }
            .store(in: &cancellables)
    }
    
    // MARK: - App Switch Detection
    
    private func setupAppSwitchDetection() {
        // Watch for app activation changes
        NSWorkspace.shared.notificationCenter.addObserver(
            forName: NSWorkspace.didActivateApplicationNotification,
            object: nil,
            queue: .main
        ) { [weak self] notification in
            guard let self = self else { return }
            
            if let app = notification.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication {
                let newBundleId = app.bundleIdentifier
                let appName = app.localizedName ?? "Unknown"
                
                // Detect context switch (different app)
                if newBundleId != self.lastAppBundleId {
                    print("🔄 Context switch detected: \(self.lastAppBundleId ?? "none") → \(newBundleId ?? "unknown")")
                    self.lastAppBundleId = newBundleId
                    
                    // Trigger capture on app switch
                    Task { @MainActor in
                        await self.captureAndAnalyze()
                    }
                }
            }
        }
        
        // Initialize with current app
        lastAppBundleId = NSWorkspace.shared.frontmostApplication?.bundleIdentifier
    }
    
    // MARK: - Proactive Insights (30 second timer)
    
    func startProactiveInsights() {
        proactiveTimer?.invalidate()
        proactiveTimer = Timer.scheduledTimer(
            withTimeInterval: proactiveInterval,
            repeats: true
        ) { [weak self] _ in
            Task { @MainActor in
                let now = Date()
                let formatter = DateFormatter()
                formatter.dateFormat = "HH:mm:ss"
                print("\n⏰ [\(formatter.string(from: now))] Proactive insight timer fired (every 30s)")
                print("   Frontmost app: \(NSWorkspace.shared.frontmostApplication?.localizedName ?? "unknown")")
                await self?.captureAndAnalyze()
            }
        }
        print("✅ Proactive insights started (every \(Int(proactiveInterval))s)")
        print("   Timer will fire at: \(Date().addingTimeInterval(proactiveInterval))")
    }
    
    func stopProactiveInsights() {
        proactiveTimer?.invalidate()
        proactiveTimer = nil
        print("⏹️ Proactive insights stopped")
    }
    
    // MARK: - Context Capture with Interruptibility
    
    /// Standard capture with interruptibility checks
    func captureAndAnalyze() async {
        await captureAndAnalyze(forceAnalyze: false)
    }
    
    /// Force capture and analyze - bypasses interruptibility for testing
    func forceCaptureAndAnalyze() async {
        await captureAndAnalyze(forceAnalyze: true)
    }
    
    private func captureAndAnalyze(forceAnalyze: Bool) async {
        isCapturing = true
        defer { isCapturing = false }
        
        // Get current app info
        let frontmostApp = NSWorkspace.shared.frontmostApplication
        currentAppName = frontmostApp?.localizedName
        
        print("\n🔍 === Starting context capture\(forceAnalyze ? " (FORCED)" : "") ===")
        print("   Current app: \(currentAppName ?? "Unknown")")
        
        // Step 1: Capture context using multiple methods
        guard let captureResult = await captureContext() else {
            notifyCaptureFailure()
            return
        }
        
        lastCapturedContext = captureResult.text
        
        // Step 2: Check interruptibility (skip if forced)
        if !forceAnalyze {
            let decision = await interruptibilityManager.shouldInterrupt(forContext: captureResult.text)
            if !decision.shouldInterrupt {
                print("🚫 Interrupt blocked: \(decision.reason)")
                return
            }
        } else {
            print("⚡ Bypassing interruptibility check (forced)")
        }
        
        // Step 3: Analyze and handle suggestions
        await analyzeAndPresentSuggestions(
            context: captureResult.text,
            windowTitle: captureResult.windowTitle,
            forceShow: forceAnalyze
        )
    }
    
    // MARK: - Context Capture Methods
    
    /// Result of context capture operation
    private struct CaptureResult {
        let text: String
        let windowTitle: String
        let method: CaptureMethod
        
        enum CaptureMethod: String {
            case appleScript = "AppleScript"
            case accessibility = "Accessibility API"
            case screenCapture = "ScreenCaptureKit + OCR"
        }
    }
    
    /// Attempts to capture context using multiple methods in order of reliability
    private func captureContext() async -> CaptureResult? {
        // Method 1: AppleScript (most reliable during development, no TCC issues)
        print("   Trying AppleScript...")
        if let (text, title) = appleScriptCapture.captureFromFrontmostWindow() {
            // Accept if we have a URL (backend will fetch content) OR enough text
            let hasUrl = text.contains("CURRENT_URL:")
            let hasEnoughText = text.count >= 100
            
            if hasUrl || hasEnoughText {
                print("   ✓ Captured via AppleScript (\(text.count) chars, hasUrl: \(hasUrl))")
                return CaptureResult(text: text, windowTitle: title, method: .appleScript)
            } else {
                print("   ⚠️ AppleScript captured \(text.count) chars but no URL - trying other methods")
            }
        }
        
        // Method 2: Accessibility API (gives structured text)
        print("   Trying Accessibility API...")
        if let (text, title) = accessibilityCapture.captureFromFrontmostWindow(), text.count >= 100 {
            print("   ✓ Captured via Accessibility API (\(text.count) chars)")
            return CaptureResult(text: text, windowTitle: title, method: .accessibility)
        }
        
        // Method 3: ScreenCaptureKit + OCR (fallback)
        print("   Trying ScreenCaptureKit + OCR...")
        if let (ocrText, title) = await screenCapture.captureScreen(), !ocrText.isEmpty {
            print("   ✓ Captured via ScreenCaptureKit + OCR (\(ocrText.count) chars)")
            return CaptureResult(text: ocrText, windowTitle: title, method: .screenCapture)
        }
        
        print("   ✗ All capture methods failed")
        return nil
    }
    
    /// Notifies UI that capture failed
    private func notifyCaptureFailure() {
        print("❌ No context captured from \(currentAppName ?? "app")")
        print("   Check: Accessibility permission, Screen Recording permission")
        print("   Note: Some apps (like Finder with no windows) don't have capturable content")
        
        NotificationCenter.default.post(name: .captureFailedNoPermissions, object: nil)
    }
    
    // MARK: - Analysis Methods
    
    /// Analyzes context with backend and presents suggestions
    private func analyzeAndPresentSuggestions(
        context: String,
        windowTitle: String,
        forceShow: Bool
    ) async {
        // Check backend availability
        guard await backendClient.isHealthy() else {
            print("❌ Backend server not available at http://127.0.0.1:8000")
            print("   💡 Start the backend: cd backend && source venv/bin/activate && python main.py")
            return
        }
        
        print("📡 Sending to backend for analysis...")
        print("   Context preview: \(String(context.prefix(100)))...")
        
        do {
            let suggestions = try await backendClient.analyze(
                context: context,
                appName: currentAppName ?? "Unknown",
                windowTitle: windowTitle
            )
            
            print("📥 Backend returned \(suggestions.count) suggestions")
            
            guard !suggestions.isEmpty else {
                print("   No suggestions returned from backend")
                return
            }
            
            // Handle shadow mode vs normal mode
            print("   Shadow mode check: isActive=\(shadowModeManager.isActive), forceShow=\(forceShow)")
            if shadowModeManager.isActive && !forceShow {
                handleShadowModeSuggestions(suggestions, context: context)
            } else {
                print("   ➡️ Presenting suggestions to user (not in shadow mode or force show)")
                presentSuggestions(suggestions, context: context)
            }
            
        } catch {
            print("❌ Analysis error: \(error)")
        }
    }
    
    /// Records suggestions in shadow mode without showing them
    private func handleShadowModeSuggestions(_ suggestions: [Suggestion], context: String) {
        for suggestion in suggestions {
            shadowModeManager.recordShadowSuggestion(suggestion, context: context)
        }
        print("👻 Shadow mode active: \(suggestions.count) suggestions recorded but not shown")
        print("   Interactions remaining: \(shadowModeManager.interactionsRemaining)")
    }
    
    /// Presents suggestions to the user
    private func presentSuggestions(_ suggestions: [Suggestion], context: String) {
        print("🎉 Showing \(suggestions.count) suggestions to user!")
        for (i, suggestion) in suggestions.enumerated() {
            print("   \(i+1). \(suggestion.title)")
            print("      Preview: \(String(suggestion.content.prefix(80)))...")
        }
        
        currentSuggestions = suggestions
        lastCaptureTime = Date()
        
        // Track that suggestions were shown
        for suggestion in suggestions {
            feedbackTracker.suggestionShown(suggestion, context: context)
        }
        
        // Notify UI
        print("📣 Posting .newSuggestionsAvailable notification...")
        NotificationCenter.default.post(name: .newSuggestionsAvailable, object: suggestions)
        
        // Update menubar icon
        if let appDelegate = NSApp.delegate as? AppDelegate {
            appDelegate.updateMenuBarIcon(hasSuggestion: true)
            print("📌 Menu bar icon updated to show suggestion indicator")
        }
    }
    
    // MARK: - Suggestion Actions (with Feedback Tracking)
    
    func dismissSuggestion(_ suggestion: Suggestion) {
        feedbackTracker.suggestionDismissed(suggestion.id)
        currentSuggestions.removeAll { $0.id == suggestion.id }
        
        if let appDelegate = NSApp.delegate as? AppDelegate {
            appDelegate.updateMenuBarIcon(hasSuggestion: !currentSuggestions.isEmpty)
        }
    }
    
    func expandSuggestion(_ suggestion: Suggestion) {
        feedbackTracker.suggestionExpanded(suggestion.id)
    }
    
    func copySuggestion(_ suggestion: Suggestion) {
        feedbackTracker.suggestionCopied(suggestion.id)
        
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        pasteboard.setString("\(suggestion.title)\n\n\(suggestion.content)", forType: .string)
    }
    
    func saveSuggestion(_ suggestion: Suggestion) {
        feedbackTracker.suggestionSaved(suggestion.id)
        
        // Save to Supermemory via backend
        Task {
            do {
                let response = try await backendClient.saveToMemory(
                    title: suggestion.title,
                    content: suggestion.content + "\n\n**Why relevant:** " + suggestion.reasoning,
                    sourceUrl: suggestion.sourceUrl,
                    context: lastCapturedContext
                )
                
                if response.status == "saved" {
                    print("✅ Saved to Supermemory: \(suggestion.title)")
                } else {
                    print("❌ Failed to save: \(response.message ?? "Unknown error")")
                }
            } catch {
                print("❌ Error saving to Supermemory: \(error)")
            }
        }
    }
    
    func clickSuggestion(_ suggestion: Suggestion) {
        feedbackTracker.suggestionClicked(suggestion.id)
    }
    
    func hoverStarted(_ suggestion: Suggestion) {
        feedbackTracker.suggestionHovered(suggestion.id)
    }
    
    func hoverEnded(_ suggestion: Suggestion) {
        feedbackTracker.suggestionHoverEnded(suggestion.id)
    }
    
    func clearSuggestions() {
        // Mark all as timed out
        for suggestion in currentSuggestions {
            feedbackTracker.suggestionTimedOut(suggestion.id)
        }
        
        currentSuggestions = []
        if let appDelegate = NSApp.delegate as? AppDelegate {
            appDelegate.updateMenuBarIcon(hasSuggestion: false)
        }
    }
    
    // MARK: - Manual Text Analysis
    
    /// Analyze manually provided text (bypasses all capture methods)
    func analyzeText(_ text: String, appName: String) async {
        print("\n📋 === Analyzing manual input ===")
        print("   Text length: \(text.count) chars")
        
        lastCapturedContext = text
        currentAppName = appName
        
        // Check if backend is available
        let isBackendAvailable = await backendClient.isHealthy()
        if !isBackendAvailable {
            print("❌ Backend server not available at http://127.0.0.1:8000")
            return
        }
        
        // Analyze with backend
        print("📡 Sending to backend for analysis...")
        
        do {
            print("📡 Calling backend.analyze()...")
            let suggestions = try await backendClient.analyze(
                context: text,
                appName: appName,
                windowTitle: "Manual Input"
            )
            
            print("📥 Backend returned \(suggestions.count) suggestions")
            for (i, s) in suggestions.enumerated() {
                print("   \(i+1). \(s.title) (relevance: \(s.relevanceScore))")
            }
            
            guard !suggestions.isEmpty else {
                print("   No suggestions returned from backend")
                return
            }
            
            print("✅ Updating currentSuggestions with \(suggestions.count) items")
            
            self.currentSuggestions = suggestions
            self.lastCaptureTime = Date()
            
            print("📣 Posting .newSuggestionsAvailable notification")
            // Notify UI
            NotificationCenter.default.post(
                name: .newSuggestionsAvailable,
                object: suggestions
            )
            
            // Update menubar icon
            if let appDelegate = NSApp.delegate as? AppDelegate {
                appDelegate.updateMenuBarIcon(hasSuggestion: true)
            }
            
            print("✅ analyzeText complete - suggestions should be visible now")
            
        } catch {
            print("❌ Analysis error: \(error)")
            if let backendError = error as? BackendError {
                print("   Backend error details: \(backendError.errorDescription ?? "unknown")")
            }
        }
    }
    
    // MARK: - Analytics
    
    func getFeedbackStats() -> RewardStats {
        return feedbackTracker.getRewardStats()
    }
}
