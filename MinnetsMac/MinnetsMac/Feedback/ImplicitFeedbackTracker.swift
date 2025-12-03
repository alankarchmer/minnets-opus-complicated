import Foundation
import AppKit
import Combine

/// Tracks implicit user feedback signals without requiring explicit actions.
/// Signals: dismiss timing, hover duration, expand, copy, click
@MainActor
class ImplicitFeedbackTracker: ObservableObject {
    static let shared = ImplicitFeedbackTracker()
    
    // Active suggestion tracking
    private var activeSuggestions: [String: SuggestionSession] = [:]
    private var cancellables = Set<AnyCancellable>()
    
    // Feedback storage
    private let storageKey = "minnets.feedback.history"
    private var feedbackHistory: [FeedbackEvent] = []
    
    private init() {
        loadHistory()
        setupClipboardMonitor()
    }
    
    // MARK: - Suggestion Lifecycle
    
    /// Called when a suggestion is shown to the user
    func suggestionShown(_ suggestion: Suggestion, context: String) {
        let session = SuggestionSession(
            suggestionId: suggestion.id,
            shownAt: Date(),
            context: context,
            confusionSignal: ConfusionDetector.shared.confusionSignal
        )
        activeSuggestions[suggestion.id] = session
    }
    
    /// Called when user hovers over a suggestion card
    func suggestionHovered(_ suggestionId: String) {
        guard var session = activeSuggestions[suggestionId] else { return }
        
        if session.hoverStartTime == nil {
            session.hoverStartTime = Date()
            activeSuggestions[suggestionId] = session
        }
    }
    
    /// Called when hover ends
    func suggestionHoverEnded(_ suggestionId: String) {
        guard var session = activeSuggestions[suggestionId],
              let hoverStart = session.hoverStartTime else { return }
        
        let hoverDuration = Date().timeIntervalSince(hoverStart)
        session.totalHoverTime += hoverDuration
        session.hoverStartTime = nil
        activeSuggestions[suggestionId] = session
        
        // Log hover if significant (2+ seconds)
        if hoverDuration >= 2.0 {
            recordAction(suggestionId: suggestionId, action: .hover, dwellTime: hoverDuration)
        }
    }
    
    /// Called when user expands "Why this?" section
    func suggestionExpanded(_ suggestionId: String) {
        guard var session = activeSuggestions[suggestionId] else { return }
        session.wasExpanded = true
        activeSuggestions[suggestionId] = session
        
        recordAction(suggestionId: suggestionId, action: .expand)
    }
    
    /// Called when user copies suggestion content
    func suggestionCopied(_ suggestionId: String) {
        recordAction(suggestionId: suggestionId, action: .copy)
    }
    
    /// Called when user clicks a link in the suggestion
    func suggestionClicked(_ suggestionId: String) {
        recordAction(suggestionId: suggestionId, action: .click)
    }
    
    /// Called when user saves to Supermemory
    func suggestionSaved(_ suggestionId: String) {
        recordAction(suggestionId: suggestionId, action: .save)
    }
    
    /// Called when suggestion is dismissed
    func suggestionDismissed(_ suggestionId: String) {
        guard let session = activeSuggestions[suggestionId] else { return }
        
        let visibleDuration = Date().timeIntervalSince(session.shownAt)
        
        // Determine dismiss type based on timing
        let action: InterruptOutcome.UserAction
        if visibleDuration < 1.0 {
            action = .immediateDismiss
        } else if visibleDuration < 3.0 {
            action = .dismiss
        } else {
            // Viewed for a while before dismissing - not as negative
            action = .dismiss
        }
        
        recordAction(suggestionId: suggestionId, action: action, dwellTime: visibleDuration)
        activeSuggestions.removeValue(forKey: suggestionId)
    }
    
    /// Called when suggestion times out (auto-hidden)
    func suggestionTimedOut(_ suggestionId: String) {
        guard let session = activeSuggestions[suggestionId] else { return }
        
        // If they hovered or expanded, it's not really an ignore
        if session.wasExpanded || session.totalHoverTime > 2.0 {
            // Don't record negative - they engaged but didn't take action
            activeSuggestions.removeValue(forKey: suggestionId)
            return
        }
        
        recordAction(suggestionId: suggestionId, action: .ignore)
        activeSuggestions.removeValue(forKey: suggestionId)
    }
    
    // MARK: - Recording
    
    private func recordAction(
        suggestionId: String,
        action: InterruptOutcome.UserAction,
        dwellTime: TimeInterval? = nil
    ) {
        guard let session = activeSuggestions[suggestionId] else { return }
        
        let outcome = InterruptOutcome(
            suggestionId: suggestionId,
            action: action,
            dwellTimeMs: dwellTime.map { Int($0 * 1000) },
            context: session.context,
            confusionSignal: session.confusionSignal
        )
        
        // Record to bandit for learning
        InterruptibilityManager.shared.recordOutcome(outcome)
        
        // Store in local history
        let event = FeedbackEvent(
            suggestionId: suggestionId,
            action: action.rawValue,
            reward: outcome.reward,
            timestamp: Date(),
            context: session.context
        )
        feedbackHistory.append(event)
        
        // Keep last 1000 events
        if feedbackHistory.count > 1000 {
            feedbackHistory.removeFirst(500)
        }
        
        saveHistory()
        
        print("📊 Feedback: \(action.rawValue) → reward \(outcome.reward)")
    }
    
    // MARK: - Shadow Mode
    
    /// Records when user manually searches for something we would have suggested
    func recordShadowHit(query: String, matchedSuggestionId: String?) {
        let signal = ConfusionDetector.shared.confusionSignal
        
        Task {
            await ContextualBandit.shared.recordShadowHit(
                context: query,
                confusionSignal: signal
            )
        }
        
        print("🎯 Shadow hit: User searched for '\(query)'")
    }
    
    // MARK: - Clipboard Monitoring (for copy detection)
    
    private var lastClipboardContent: String?
    
    private func setupClipboardMonitor() {
        // Poll clipboard periodically to detect copies
        Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.checkClipboard()
            }
        }
    }
    
    private func checkClipboard() {
        guard let content = NSPasteboard.general.string(forType: .string),
              content != lastClipboardContent else {
            return
        }
        
        lastClipboardContent = content
        
        // TODO: In a real implementation, compare against active suggestion content
        // For now, just tracking clipboard changes for future use
    }
    
    // MARK: - Analytics
    
    func getRewardStats() -> RewardStats {
        guard !feedbackHistory.isEmpty else {
            return RewardStats(total: 0, positive: 0, negative: 0, averageReward: 0)
        }
        
        let total = feedbackHistory.count
        let positive = feedbackHistory.filter { $0.reward > 0 }.count
        let negative = feedbackHistory.filter { $0.reward < 0 }.count
        let avgReward = feedbackHistory.map { $0.reward }.reduce(0, +) / Double(total)
        
        return RewardStats(
            total: total,
            positive: positive,
            negative: negative,
            averageReward: avgReward
        )
    }
    
    // MARK: - Persistence
    
    private func saveHistory() {
        if let data = try? JSONEncoder().encode(feedbackHistory) {
            UserDefaults.standard.set(data, forKey: storageKey)
        }
    }
    
    private func loadHistory() {
        guard let data = UserDefaults.standard.data(forKey: storageKey),
              let history = try? JSONDecoder().decode([FeedbackEvent].self, from: data) else {
            return
        }
        feedbackHistory = history
    }
}

// MARK: - Supporting Types

private struct SuggestionSession {
    let suggestionId: String
    let shownAt: Date
    let context: String
    let confusionSignal: ConfusionDetector.ConfusionSignal?
    
    var hoverStartTime: Date?
    var totalHoverTime: TimeInterval = 0
    var wasExpanded: Bool = false
}

struct FeedbackEvent: Codable {
    let suggestionId: String
    let action: String
    let reward: Double
    let timestamp: Date
    let context: String
}

struct RewardStats {
    let total: Int
    let positive: Int
    let negative: Int
    let averageReward: Double
    
    var positiveRate: Double {
        guard total > 0 else { return 0 }
        return Double(positive) / Double(total)
    }
}

