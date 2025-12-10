import Foundation
import Combine

/// Orchestrates the three-layer interruptibility system.
/// Layer 1: Flow State Gate (hard blocks)
/// Layer 2: Confusion Detector (opportunity signals)
/// Layer 3: Contextual Bandit (personalized decision)
@MainActor
class InterruptibilityManager: ObservableObject {
    static let shared = InterruptibilityManager()
    
    @Published var canInterrupt: Bool = false
    @Published var interruptReason: String?
    @Published var confidenceScore: Double = 0.0
    
    private let flowGate: FlowStateGate
    private let confusionDetector: ConfusionDetector
    private let bandit = ContextualBandit.shared
    
    private var cancellables = Set<AnyCancellable>()
    private var evaluationTimer: Timer?
    
    private init() {
        self.flowGate = FlowStateGate.shared
        self.confusionDetector = ConfusionDetector.shared
        setupObservers()
        startPeriodicEvaluation()
    }
    
    // MARK: - Public API
    
    /// Evaluates whether now is a good time to show a suggestion
    func shouldInterrupt(forContext context: String) async -> InterruptDecision {
        // Layer 1: Hard gate check
        let (blocked, blockReason) = flowGate.shouldBlock()
        if blocked {
            return InterruptDecision(
                shouldInterrupt: false,
                confidence: 1.0,
                reason: "Blocked: \(blockReason?.rawValue ?? "Unknown")",
                layer: .flowGate
            )
        }
        
        // Layer 2: Confusion detection
        let (confused, signal, confusionScore) = confusionDetector.detectConfusion()
        
        if !confused {
            // RELAXED FOR TESTING: Allow proactive suggestions even without confusion
            // Original threshold was 0.8, now allowing with much lower bar
            let banditScore = await bandit.shouldInterrupt(
                context: context,
                confusionSignal: nil,
                confusionScore: 0
            )
            
            // Always allow proactive suggestions for testing
            // TODO: Restore stricter logic after testing
            return InterruptDecision(
                shouldInterrupt: true,
                confidence: max(0.6, banditScore),
                reason: "Proactive suggestion (testing mode - confusion not required)",
                layer: .bandit
            )
        }
        
        // Layer 3: Ask the bandit
        let banditScore = await bandit.shouldInterrupt(
            context: context,
            confusionSignal: signal,
            confusionScore: confusionScore
        )
        
        let shouldShow = banditScore > 0.5
        
        return InterruptDecision(
            shouldInterrupt: shouldShow,
            confidence: shouldShow ? banditScore : (1.0 - banditScore),
            reason: shouldShow 
                ? "Confusion detected (\(signal?.rawValue ?? "unknown")), bandit approves" 
                : "Confusion detected but bandit suggests waiting",
            layer: .bandit
        )
    }
    
    /// Records the outcome of an interruption for bandit learning
    func recordOutcome(_ outcome: InterruptOutcome) {
        Task {
            await bandit.recordReward(outcome: outcome)
        }
    }
    
    // MARK: - Private
    
    private func setupObservers() {
        // Observe flow gate changes
        flowGate.$isBlocked
            .receive(on: DispatchQueue.main)
            .sink { [weak self] blocked in
                if blocked {
                    self?.canInterrupt = false
                    self?.interruptReason = self?.flowGate.blockReason?.rawValue
                }
            }
            .store(in: &cancellables)
        
        // Observe confusion signals
        confusionDetector.$confusionSignal
            .receive(on: DispatchQueue.main)
            .sink { [weak self] signal in
                if let signal = signal {
                    self?.interruptReason = signal.rawValue
                }
            }
            .store(in: &cancellables)
    }
    
    private func startPeriodicEvaluation() {
        evaluationTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.evaluateCurrentState()
            }
        }
    }
    
    private func evaluateCurrentState() {
        let (blocked, _) = flowGate.shouldBlock()
        let (confused, signal, score) = confusionDetector.detectConfusion()
        
        if blocked {
            canInterrupt = false
            confidenceScore = 0
        } else if confused {
            // Preliminary: will be refined by bandit when actual suggestion is ready
            canInterrupt = true
            confidenceScore = score
            interruptReason = signal?.rawValue
        } else {
            canInterrupt = false
            confidenceScore = 0
            interruptReason = nil
        }
    }
}

// MARK: - Supporting Types

struct InterruptDecision {
    let shouldInterrupt: Bool
    let confidence: Double
    let reason: String
    let layer: InterruptLayer
    
    enum InterruptLayer {
        case flowGate
        case confusionDetector
        case bandit
    }
}

struct InterruptOutcome {
    let suggestionId: String
    let action: UserAction
    let dwellTimeMs: Int?
    let context: String
    let confusionSignal: ConfusionDetector.ConfusionSignal?
    
    enum UserAction: String {
        case immediateDismiss = "immediate_dismiss"  // < 1 second
        case dismiss = "dismiss"                      // 1-3 seconds
        case ignore = "ignore"                        // timeout
        case hover = "hover"                          // 2+ seconds hover
        case expand = "expand"                        // clicked "why this?"
        case copy = "copy"                            // copied content
        case click = "click"                          // clicked link/action
        case save = "save"                            // saved to memory
    }
    
    var reward: Double {
        switch action {
        case .immediateDismiss: return -5.0
        case .dismiss: return -1.0
        case .ignore: return -0.5
        case .hover: return 1.0
        case .expand: return 2.0
        case .copy: return 5.0
        case .click: return 5.0
        case .save: return 5.0
        }
    }
}
