import Foundation
import AppKit

/// Shadow Mode Manager
/// During cold start (first 50 interactions), generates suggestions but doesn't show them.
/// Tracks when users manually search for things we would have suggested → massive positive signal.
@MainActor
class ShadowModeManager: ObservableObject {
    static let shared = ShadowModeManager()
    
    // RELAXED FOR TESTING: Shadow mode disabled so suggestions actually show
    // TODO: Restore to true and 50 after testing
    @Published var isActive: Bool = false
    @Published var interactionsRemaining: Int = 0
    
    // Shadow suggestions we would have shown
    private var shadowQueue: [ShadowSuggestion] = []
    private let maxQueueSize = 20
    
    // Browser/search monitoring
    private var searchMonitorTimer: Timer?
    
    private init() {
        // TESTING: Force shadow mode OFF - don't even check the bandit
        // TODO: Restore to check ContextualBandit.shared.isInShadowMode() after testing
        isActive = false
        print("👻 ShadowModeManager initialized (isActive: \(isActive))")
        setupSearchMonitoring()
    }
    
    // MARK: - Shadow Suggestion Recording
    
    /// Record a suggestion that would have been shown (but wasn't due to shadow mode)
    func recordShadowSuggestion(_ suggestion: Suggestion, context: String) {
        let shadow = ShadowSuggestion(
            suggestion: suggestion,
            context: context,
            timestamp: Date(),
            keywords: extractKeywords(from: suggestion)
        )
        
        shadowQueue.append(shadow)
        
        // Keep queue bounded
        if shadowQueue.count > maxQueueSize {
            shadowQueue.removeFirst()
        }
        
        print("👻 Shadow suggestion recorded: \(suggestion.title)")
    }
    
    /// Check if a user's search matches any shadow suggestion
    func checkSearchMatch(query: String) {
        let queryKeywords = Set(extractKeywords(from: query))
        
        for shadow in shadowQueue {
            let overlapCount = shadow.keywords.intersection(queryKeywords).count
            let matchScore = Double(overlapCount) / Double(max(shadow.keywords.count, 1))
            
            // If significant overlap, this is a shadow hit!
            if matchScore > 0.3 {
                recordShadowHit(shadow: shadow, query: query)
                
                // Remove from queue - we've learned from it
                shadowQueue.removeAll { $0.suggestion.id == shadow.suggestion.id }
                return
            }
        }
    }
    
    private func recordShadowHit(shadow: ShadowSuggestion, query: String) {
        print("🎯 SHADOW HIT! User searched for '\(query)' - we had: '\(shadow.suggestion.title)'")
        
        // Record to feedback tracker
        ImplicitFeedbackTracker.shared.recordShadowHit(
            query: query,
            matchedSuggestionId: shadow.suggestion.id
        )
        
        // Decrement remaining interactions faster on hits
        interactionsRemaining = max(0, interactionsRemaining - 5)
        
        if interactionsRemaining == 0 {
            exitShadowMode()
        }
    }
    
    // MARK: - Search Monitoring
    
    private func setupSearchMonitoring() {
        // Monitor for browser activity that might indicate searching
        searchMonitorTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.checkForSearchActivity()
            }
        }
    }
    
    private func checkForSearchActivity() {
        guard isActive else { return }
        
        // Check if user is in a browser using shared utility
        guard BrowserURLCapture.isBrowserActive() else { return }
        
        // Try to get URL/search from browser
        if let url = BrowserURLCapture.getActiveURL(),
           let searchQuery = BrowserURLCapture.extractSearchQuery(from: url) {
            checkSearchMatch(query: searchQuery)
        }
    }
    
    /// Stops search monitoring - call when shadow mode ends
    func stopMonitoring() {
        searchMonitorTimer?.invalidate()
        searchMonitorTimer = nil
    }
    
    // MARK: - Keyword Extraction
    
    private func extractKeywords(from suggestion: Suggestion) -> Set<String> {
        let text = "\(suggestion.title) \(suggestion.content)"
        return extractKeywords(from: text)
    }
    
    private func extractKeywords(from text: String) -> Set<String> {
        // Simple keyword extraction - split and filter
        let words = text.lowercased()
            .components(separatedBy: CharacterSet.alphanumerics.inverted)
            .filter { $0.count > 3 }  // Only words with 4+ chars
        
        // Remove common stop words
        let stopWords: Set<String> = [
            "the", "and", "for", "that", "this", "with", "from", "your", "have",
            "are", "was", "were", "been", "being", "will", "would", "could", "should",
            "about", "into", "through", "during", "before", "after", "above", "below"
        ]
        
        return Set(words).subtracting(stopWords)
    }
    
    // MARK: - Shadow Mode Lifecycle
    
    func recordInteraction() {
        interactionsRemaining = max(0, interactionsRemaining - 1)
        
        if interactionsRemaining == 0 {
            exitShadowMode()
        }
    }
    
    private func exitShadowMode() {
        isActive = false
        shadowQueue.removeAll()
        stopMonitoring()
        print("🌟 Exiting shadow mode - model is now calibrated!")
    }
}

// MARK: - Supporting Types

private struct ShadowSuggestion {
    let suggestion: Suggestion
    let context: String
    let timestamp: Date
    let keywords: Set<String>
}

