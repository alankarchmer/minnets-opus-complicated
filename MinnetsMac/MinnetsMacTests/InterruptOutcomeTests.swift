import XCTest
@testable import MinnetsMac

/// Tests for InterruptOutcome reward calculations
final class InterruptOutcomeTests: XCTestCase {
    
    // MARK: - Reward Calculation Tests
    
    func testReward_ImmediateDismiss() {
        let outcome = InterruptOutcome(
            suggestionId: "test",
            action: .immediateDismiss,
            dwellTimeMs: 500,
            context: "test context",
            confusionSignal: nil
        )
        XCTAssertEqual(outcome.reward, -5.0)
    }
    
    func testReward_Dismiss() {
        let outcome = InterruptOutcome(
            suggestionId: "test",
            action: .dismiss,
            dwellTimeMs: 2000,
            context: "test context",
            confusionSignal: nil
        )
        XCTAssertEqual(outcome.reward, -1.0)
    }
    
    func testReward_Ignore() {
        let outcome = InterruptOutcome(
            suggestionId: "test",
            action: .ignore,
            dwellTimeMs: nil,
            context: "test context",
            confusionSignal: nil
        )
        XCTAssertEqual(outcome.reward, -0.5)
    }
    
    func testReward_Hover() {
        let outcome = InterruptOutcome(
            suggestionId: "test",
            action: .hover,
            dwellTimeMs: 3000,
            context: "test context",
            confusionSignal: .staring
        )
        XCTAssertEqual(outcome.reward, 1.0)
    }
    
    func testReward_Expand() {
        let outcome = InterruptOutcome(
            suggestionId: "test",
            action: .expand,
            dwellTimeMs: nil,
            context: "test context",
            confusionSignal: nil
        )
        XCTAssertEqual(outcome.reward, 2.0)
    }
    
    func testReward_Copy() {
        let outcome = InterruptOutcome(
            suggestionId: "test",
            action: .copy,
            dwellTimeMs: nil,
            context: "test context",
            confusionSignal: nil
        )
        XCTAssertEqual(outcome.reward, 5.0)
    }
    
    func testReward_Click() {
        let outcome = InterruptOutcome(
            suggestionId: "test",
            action: .click,
            dwellTimeMs: nil,
            context: "test context",
            confusionSignal: nil
        )
        XCTAssertEqual(outcome.reward, 5.0)
    }
    
    func testReward_Save() {
        let outcome = InterruptOutcome(
            suggestionId: "test",
            action: .save,
            dwellTimeMs: nil,
            context: "test context",
            confusionSignal: nil
        )
        XCTAssertEqual(outcome.reward, 5.0)
    }
    
    // MARK: - User Action Raw Value Tests
    
    func testUserActionRawValues() {
        XCTAssertEqual(InterruptOutcome.UserAction.immediateDismiss.rawValue, "immediate_dismiss")
        XCTAssertEqual(InterruptOutcome.UserAction.dismiss.rawValue, "dismiss")
        XCTAssertEqual(InterruptOutcome.UserAction.ignore.rawValue, "ignore")
        XCTAssertEqual(InterruptOutcome.UserAction.hover.rawValue, "hover")
        XCTAssertEqual(InterruptOutcome.UserAction.expand.rawValue, "expand")
        XCTAssertEqual(InterruptOutcome.UserAction.copy.rawValue, "copy")
        XCTAssertEqual(InterruptOutcome.UserAction.click.rawValue, "click")
        XCTAssertEqual(InterruptOutcome.UserAction.save.rawValue, "save")
    }
    
    // MARK: - Reward Stats Tests
    
    func testRewardStats_PositiveRate() {
        let stats = RewardStats(total: 100, positive: 75, negative: 25, averageReward: 0.5)
        XCTAssertEqual(stats.positiveRate, 0.75, accuracy: 0.001)
    }
    
    func testRewardStats_PositiveRateZeroTotal() {
        let stats = RewardStats(total: 0, positive: 0, negative: 0, averageReward: 0)
        XCTAssertEqual(stats.positiveRate, 0)
    }
}
