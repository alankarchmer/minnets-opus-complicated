import XCTest
@testable import MinnetsMac

/// Tests for Models.swift - Suggestion, CapturedContext, and API models
final class ModelsTests: XCTestCase {
    
    // MARK: - Suggestion Tests
    
    func testSuggestionDecoding() throws {
        let json = """
        {
            "id": "test-123",
            "title": "Test Suggestion",
            "content": "This is test content",
            "reasoning": "Because it's relevant",
            "source": "supermemory",
            "relevanceScore": 0.85,
            "noveltyScore": 0.72,
            "timestamp": "2024-12-09T10:30:00",
            "sourceUrl": "https://example.com"
        }
        """.data(using: .utf8)!
        
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        
        let suggestion = try decoder.decode(Suggestion.self, from: json)
        
        XCTAssertEqual(suggestion.id, "test-123")
        XCTAssertEqual(suggestion.title, "Test Suggestion")
        XCTAssertEqual(suggestion.content, "This is test content")
        XCTAssertEqual(suggestion.reasoning, "Because it's relevant")
        XCTAssertEqual(suggestion.source, .supermemory)
        XCTAssertEqual(suggestion.relevanceScore, 0.85, accuracy: 0.01)
        XCTAssertEqual(suggestion.noveltyScore, 0.72, accuracy: 0.01)
        XCTAssertEqual(suggestion.sourceUrl, "https://example.com")
    }
    
    func testSuggestionDecodingWithNullSourceUrl() throws {
        let json = """
        {
            "id": "test-456",
            "title": "Test",
            "content": "Content",
            "reasoning": "Reason",
            "source": "web_search",
            "relevanceScore": 0.5,
            "noveltyScore": 0.5,
            "timestamp": "2024-12-09T10:30:00",
            "sourceUrl": null
        }
        """.data(using: .utf8)!
        
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        
        let suggestion = try decoder.decode(Suggestion.self, from: json)
        
        XCTAssertNil(suggestion.sourceUrl)
        XCTAssertEqual(suggestion.source, .webSearch)
    }
    
    func testSuggestionCombinedScore() {
        let suggestion = Suggestion(
            id: "test",
            title: "Test",
            content: "Content",
            reasoning: "Reason",
            source: .combined,
            relevanceScore: 0.8,
            noveltyScore: 0.6,
            timestamp: Date(),
            sourceUrl: nil
        )
        
        XCTAssertEqual(suggestion.combinedScore, 0.7, accuracy: 0.01)
    }
    
    func testSuggestionEncoding() throws {
        let suggestion = Suggestion(
            id: "encode-test",
            title: "Encode Test",
            content: "Content",
            reasoning: "Reason",
            source: .supermemory,
            relevanceScore: 0.9,
            noveltyScore: 0.8,
            timestamp: Date(),
            sourceUrl: "https://example.com"
        )
        
        let encoder = JSONEncoder()
        let data = try encoder.encode(suggestion)
        
        XCTAssertNotNil(data)
        XCTAssertGreaterThan(data.count, 0)
    }
    
    // MARK: - SuggestionSource Tests
    
    func testSuggestionSourceDisplayName() {
        XCTAssertEqual(SuggestionSource.supermemory.displayName, "Your Memory")
        XCTAssertEqual(SuggestionSource.webSearch.displayName, "Web Search")
        XCTAssertEqual(SuggestionSource.combined.displayName, "Memory + Web")
    }
    
    func testSuggestionSourceIconName() {
        XCTAssertEqual(SuggestionSource.supermemory.iconName, "brain")
        XCTAssertEqual(SuggestionSource.webSearch.iconName, "globe")
        XCTAssertEqual(SuggestionSource.combined.iconName, "sparkles")
    }
    
    // MARK: - CapturedContext Tests
    
    func testCapturedContextEncoding() throws {
        let context = CapturedContext(
            text: "Sample captured text",
            appName: "Safari",
            windowTitle: "Apple Developer Documentation",
            timestamp: Date(),
            captureMethod: .accessibility
        )
        
        let encoder = JSONEncoder()
        let data = try encoder.encode(context)
        
        XCTAssertNotNil(data)
        
        let decoder = JSONDecoder()
        let decoded = try decoder.decode(CapturedContext.self, from: data)
        
        XCTAssertEqual(decoded.text, context.text)
        XCTAssertEqual(decoded.appName, context.appName)
        XCTAssertEqual(decoded.windowTitle, context.windowTitle)
        XCTAssertEqual(decoded.captureMethod, .accessibility)
    }
    
    // MARK: - AppState Tests
    
    func testAppStateStatusText() {
        XCTAssertEqual(AppState.idle.statusText, "Monitoring...")
        XCTAssertEqual(AppState.capturing.statusText, "Reading context...")
        XCTAssertEqual(AppState.analyzing.statusText, "Finding insights...")
        XCTAssertEqual(AppState.hasSuggestions.statusText, "New insights available")
        XCTAssertEqual(AppState.error("Test error").statusText, "Error: Test error")
    }
    
    func testAppStateEquality() {
        XCTAssertEqual(AppState.idle, AppState.idle)
        XCTAssertEqual(AppState.error("A"), AppState.error("A"))
        XCTAssertNotEqual(AppState.error("A"), AppState.error("B"))
        XCTAssertNotEqual(AppState.idle, AppState.capturing)
    }
    
    // MARK: - AnalyzeRequest Tests
    
    func testAnalyzeRequestEncoding() throws {
        let request = AnalyzeRequest(
            context: "User is reading documentation",
            appName: "Safari",
            windowTitle: "Swift Documentation"
        )
        
        let encoder = JSONEncoder()
        let data = try encoder.encode(request)
        let jsonString = String(data: data, encoding: .utf8)
        
        XCTAssertNotNil(jsonString)
        XCTAssertTrue(jsonString!.contains("context"))
        XCTAssertTrue(jsonString!.contains("appName"))
        XCTAssertTrue(jsonString!.contains("windowTitle"))
    }
}
