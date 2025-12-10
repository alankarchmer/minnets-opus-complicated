import Foundation
import AppKit

/// Layer 3: Contextual Bandit
/// Learns user preferences for when to show suggestions.
/// Uses Thompson Sampling with contextual features.
actor ContextualBandit {
    static let shared = ContextualBandit()
    
    // Model state
    private var weights: [String: Double] = [:]
    private var counts: [String: Int] = [:]
    private var rewards: [String: Double] = [:]
    
    // Shadow mode
    // RELAXED FOR TESTING: Shadow mode disabled so suggestions actually show
    // TODO: Restore to true after testing
    private var shadowMode: Bool = false
    private var interactionCount: Int = 0
    private let shadowModeThreshold = 50
    
    // Persistence
    private let storageKey = "minnets.bandit.state"
    
    private init() {
        // Load state synchronously from UserDefaults
        if let data = UserDefaults.standard.data(forKey: storageKey),
           let state = try? JSONDecoder().decode(BanditState.self, from: data) {
            weights = state.weights
            counts = state.counts
            rewards = state.rewards
            interactionCount = state.interactionCount
            // TESTING: Force shadow mode OFF regardless of saved state
            // TODO: Restore to state.shadowMode after testing
            shadowMode = false
        }
        print("🎰 ContextualBandit initialized (shadowMode: \(shadowMode))")
    }
    
    // MARK: - Public API
    
    /// Returns probability (0-1) that we should interrupt
    func shouldInterrupt(
        context: String,
        confusionSignal: ConfusionDetector.ConfusionSignal?,
        confusionScore: Double
    ) async -> Double {
        let features = await extractFeatures(
            context: context,
            confusionSignal: confusionSignal,
            confusionScore: confusionScore
        )
        
        // Thompson Sampling: sample from posterior
        var score = 0.5  // Prior
        
        for (feature, value) in features {
            let key = feature
            let n = counts[key] ?? 0
            let totalReward = rewards[key] ?? 0
            
            if n > 0 {
                // Posterior mean with some uncertainty
                let mean = totalReward / Double(n)
                let uncertainty = 1.0 / sqrt(Double(n + 1))
                
                // Sample from approximate posterior (Beta-like)
                let sample = mean + Double.random(in: -uncertainty...uncertainty)
                score += sample * value * (weights[key] ?? 0.1)
            }
        }
        
        // Clamp to [0, 1]
        return max(0, min(1, score))
    }
    
    /// Records the outcome of showing (or not showing) a suggestion
    func recordReward(outcome: InterruptOutcome) async {
        interactionCount += 1
        
        // Exit shadow mode after threshold
        if interactionCount >= shadowModeThreshold {
            shadowMode = false
        }
        
        let features = await extractFeatures(
            context: outcome.context,
            confusionSignal: outcome.confusionSignal,
            confusionScore: 0.5
        )
        
        // Update counts and rewards for each feature
        for (feature, value) in features where value > 0.5 {
            counts[feature, default: 0] += 1
            rewards[feature, default: 0] += outcome.reward
            
            // Update weight towards observed reward
            let n = Double(counts[feature] ?? 1)
            let learningRate = 1.0 / n
            let currentWeight = weights[feature] ?? 0.1
            let targetWeight = outcome.reward > 0 ? 1.0 : -1.0
            weights[feature] = currentWeight + learningRate * (targetWeight - currentWeight)
        }
        
        saveState()
    }
    
    /// Returns true if we're still in shadow mode (learning without showing)
    func isInShadowMode() -> Bool {
        return shadowMode
    }
    
    /// Records a "shadow hit" - when we would have shown something the user searched for
    func recordShadowHit(context: String, confusionSignal: ConfusionDetector.ConfusionSignal?) async {
        let features = await extractFeatures(
            context: context,
            confusionSignal: confusionSignal,
            confusionScore: 0.5
        )
        
        for (feature, value) in features where value > 0.5 {
            counts[feature, default: 0] += 1
            rewards[feature, default: 0] += 10.0  // Shadow hit = +10 reward
        }
        
        saveState()
    }
    
    // MARK: - Feature Extraction
    
    private func extractFeatures(
        context: String,
        confusionSignal: ConfusionDetector.ConfusionSignal?,
        confusionScore: Double
    ) async -> [(String, Double)] {
        var features: [(String, Double)] = []
        
        // Time of day features
        let hour = Calendar.current.component(.hour, from: Date())
        features.append(("hour_morning", hour >= 6 && hour < 12 ? 1.0 : 0.0))
        features.append(("hour_afternoon", hour >= 12 && hour < 17 ? 1.0 : 0.0))
        features.append(("hour_evening", hour >= 17 && hour < 22 ? 1.0 : 0.0))
        
        // Day of week
        let weekday = Calendar.current.component(.weekday, from: Date())
        features.append(("day_weekend", (weekday == 1 || weekday == 7) ? 1.0 : 0.0))
        
        // Current app category - access from MainActor
        let bundleId = await MainActor.run {
            NSWorkspace.shared.frontmostApplication?.bundleIdentifier
        }
        
        if let frontApp = bundleId {
            features.append(("app_ide", frontApp.contains("Code") || frontApp.contains("Xcode") ? 1.0 : 0.0))
            features.append(("app_browser", frontApp.contains("Safari") || frontApp.contains("Chrome") ? 1.0 : 0.0))
            features.append(("app_docs", frontApp.contains("Preview") || frontApp.contains("Word") ? 1.0 : 0.0))
        }
        
        // Confusion signal features
        if let signal = confusionSignal {
            features.append(("confusion_thrashing", signal == .thrashing ? 1.0 : 0.0))
            features.append(("confusion_staring", signal == .staring ? 1.0 : 0.0))
            features.append(("confusion_errors", signal == .errorRate ? 1.0 : 0.0))
        }
        
        // Confusion intensity
        features.append(("confusion_score", confusionScore))
        
        // Context content features (simplified)
        let contextLower = context.lowercased()
        features.append(("context_code", contextLower.contains("function") || contextLower.contains("class") ? 1.0 : 0.0))
        features.append(("context_research", contextLower.contains("paper") || contextLower.contains("study") ? 1.0 : 0.0))
        
        return features
    }
    
    // MARK: - Persistence
    
    private func saveState() {
        let state = BanditState(
            weights: weights,
            counts: counts,
            rewards: rewards,
            interactionCount: interactionCount,
            shadowMode: shadowMode
        )
        
        if let data = try? JSONEncoder().encode(state) {
            UserDefaults.standard.set(data, forKey: storageKey)
        }
    }
}

// MARK: - Persistence Model

private struct BanditState: Codable {
    let weights: [String: Double]
    let counts: [String: Int]
    let rewards: [String: Double]
    let interactionCount: Int
    let shadowMode: Bool
}
