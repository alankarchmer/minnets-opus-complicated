import XCTest
@testable import MinnetsMac

/// Tests for FeedbackEvent and related types
final class FeedbackTrackerTests: XCTestCase {
    
    // MARK: - FeedbackEvent Tests
    
    func testFeedbackEventEncoding() throws {
        let event = FeedbackEvent(
            suggestionId: "sug-123",
            action: "copy",
            reward: 5.0,
            timestamp: Date(),
            context: "User was reading documentation"
        )
        
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let data = try encoder.encode(event)
        
        XCTAssertNotNil(data)
        
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let decoded = try decoder.decode(FeedbackEvent.self, from: data)
        
        XCTAssertEqual(decoded.suggestionId, "sug-123")
        XCTAssertEqual(decoded.action, "copy")
        XCTAssertEqual(decoded.reward, 5.0)
        XCTAssertEqual(decoded.context, "User was reading documentation")
    }
    
    // MARK: - RewardStats Tests
    
    func testRewardStats_Initialization() {
        let stats = RewardStats(
            total: 100,
            positive: 60,
            negative: 30,
            averageReward: 1.5
        )
        
        XCTAssertEqual(stats.total, 100)
        XCTAssertEqual(stats.positive, 60)
        XCTAssertEqual(stats.negative, 30)
        XCTAssertEqual(stats.averageReward, 1.5)
    }
    
    func testRewardStats_PositiveRate() {
        let stats = RewardStats(
            total: 100,
            positive: 80,
            negative: 10,
            averageReward: 2.0
        )
        
        XCTAssertEqual(stats.positiveRate, 0.8, accuracy: 0.001)
    }
    
    func testRewardStats_PositiveRateEdgeCases() {
        // Zero total
        let zeroStats = RewardStats(total: 0, positive: 0, negative: 0, averageReward: 0)
        XCTAssertEqual(zeroStats.positiveRate, 0)
        
        // All positive
        let allPositive = RewardStats(total: 50, positive: 50, negative: 0, averageReward: 3.0)
        XCTAssertEqual(allPositive.positiveRate, 1.0)
        
        // All negative
        let allNegative = RewardStats(total: 50, positive: 0, negative: 50, averageReward: -2.0)
        XCTAssertEqual(allNegative.positiveRate, 0)
    }
}
