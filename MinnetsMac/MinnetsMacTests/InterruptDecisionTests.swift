import XCTest
@testable import MinnetsMac

/// Tests for InterruptDecision and related types
final class InterruptDecisionTests: XCTestCase {
    
    // MARK: - InterruptDecision Tests
    
    func testInterruptDecision_ShouldInterrupt() {
        let decision = InterruptDecision(
            shouldInterrupt: true,
            confidence: 0.85,
            reason: "User appears confused",
            layer: .confusionDetector
        )
        
        XCTAssertTrue(decision.shouldInterrupt)
        XCTAssertEqual(decision.confidence, 0.85, accuracy: 0.01)
        XCTAssertEqual(decision.reason, "User appears confused")
        XCTAssertEqual(decision.layer, .confusionDetector)
    }
    
    func testInterruptDecision_ShouldNotInterrupt() {
        let decision = InterruptDecision(
            shouldInterrupt: false,
            confidence: 0.95,
            reason: "User is typing rapidly",
            layer: .flowGate
        )
        
        XCTAssertFalse(decision.shouldInterrupt)
        XCTAssertEqual(decision.layer, .flowGate)
    }
    
    func testInterruptDecision_BanditLayer() {
        let decision = InterruptDecision(
            shouldInterrupt: true,
            confidence: 0.7,
            reason: "Bandit suggests showing",
            layer: .bandit
        )
        
        XCTAssertEqual(decision.layer, .bandit)
    }
    
    // MARK: - FlowStateGate.BlockReason Tests
    
    func testBlockReason_RawValues() {
        XCTAssertEqual(FlowStateGate.BlockReason.highVelocityTyping.rawValue, "User is typing rapidly")
        XCTAssertEqual(FlowStateGate.BlockReason.presentationMode.rawValue, "Presentation in progress")
        XCTAssertEqual(FlowStateGate.BlockReason.blacklistedApp.rawValue, "Sensitive/meeting app active")
        XCTAssertEqual(FlowStateGate.BlockReason.videoCall.rawValue, "Video call in progress")
    }
    
    // MARK: - ConfusionDetector.ConfusionSignal Tests
    
    func testConfusionSignal_RawValues() {
        XCTAssertEqual(ConfusionDetector.ConfusionSignal.thrashing.rawValue, "Switching between apps rapidly")
        XCTAssertEqual(ConfusionDetector.ConfusionSignal.staring.rawValue, "Idle while viewing content")
        XCTAssertEqual(ConfusionDetector.ConfusionSignal.errorRate.rawValue, "High error/correction rate")
    }
}
