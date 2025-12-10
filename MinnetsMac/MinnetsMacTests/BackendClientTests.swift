import XCTest
@testable import MinnetsMac

/// Tests for BackendClient
final class BackendClientTests: XCTestCase {
    
    // MARK: - BackendError Tests
    
    func testBackendError_InvalidResponse() {
        let error = BackendError.invalidResponse
        XCTAssertEqual(error.errorDescription, "Invalid response from backend")
    }
    
    func testBackendError_HttpError() {
        let error = BackendError.httpError(statusCode: 500)
        XCTAssertEqual(error.errorDescription, "HTTP error: 500")
    }
    
    func testBackendError_HttpError404() {
        let error = BackendError.httpError(statusCode: 404)
        XCTAssertEqual(error.errorDescription, "HTTP error: 404")
    }
    
    func testBackendError_DecodingError() {
        let underlyingError = DecodingError.dataCorrupted(
            DecodingError.Context(codingPath: [], debugDescription: "Test error")
        )
        let error = BackendError.decodingError(underlyingError)
        
        XCTAssertNotNil(error.errorDescription)
        XCTAssertTrue(error.errorDescription!.contains("Failed to decode"))
    }
    
    func testBackendError_NetworkError() {
        let underlyingError = NSError(domain: NSURLErrorDomain, code: -1009, userInfo: [
            NSLocalizedDescriptionKey: "The Internet connection appears to be offline."
        ])
        let error = BackendError.networkError(underlyingError)
        
        XCTAssertNotNil(error.errorDescription)
        XCTAssertTrue(error.errorDescription!.contains("Network error"))
    }
    
    // MARK: - SaveToMemoryRequest Tests
    
    func testSaveToMemoryRequestEncoding() throws {
        let request = SaveToMemoryRequest(
            title: "Test Title",
            content: "Test Content",
            sourceUrl: "https://example.com",
            context: "Test Context"
        )
        
        let encoder = JSONEncoder()
        let data = try encoder.encode(request)
        let jsonString = String(data: data, encoding: .utf8)!
        
        // Check that snake_case is used for source_url
        XCTAssertTrue(jsonString.contains("\"source_url\""))
        XCTAssertTrue(jsonString.contains("Test Title"))
        XCTAssertTrue(jsonString.contains("Test Content"))
    }
    
    func testSaveToMemoryRequestEncodingWithNils() throws {
        let request = SaveToMemoryRequest(
            title: "Test",
            content: "Content",
            sourceUrl: nil,
            context: nil
        )
        
        let encoder = JSONEncoder()
        let data = try encoder.encode(request)
        
        XCTAssertNotNil(data)
    }
    
    // MARK: - SaveToMemoryResponse Tests
    
    func testSaveToMemoryResponseDecoding() throws {
        let json = """
        {
            "status": "saved",
            "memory_id": "mem-123",
            "message": "Successfully saved"
        }
        """.data(using: .utf8)!
        
        let decoder = JSONDecoder()
        let response = try decoder.decode(SaveToMemoryResponse.self, from: json)
        
        XCTAssertEqual(response.status, "saved")
        XCTAssertEqual(response.memoryId, "mem-123")
        XCTAssertEqual(response.message, "Successfully saved")
    }
    
    func testSaveToMemoryResponseDecodingWithNulls() throws {
        let json = """
        {
            "status": "error",
            "memory_id": null,
            "message": null
        }
        """.data(using: .utf8)!
        
        let decoder = JSONDecoder()
        let response = try decoder.decode(SaveToMemoryResponse.self, from: json)
        
        XCTAssertEqual(response.status, "error")
        XCTAssertNil(response.memoryId)
        XCTAssertNil(response.message)
    }
    
    // MARK: - AnalyzeResponse Tests
    
    func testAnalyzeResponseDecoding() throws {
        let json = """
        {
            "suggestions": [
                {
                    "id": "sug-1",
                    "title": "Test Suggestion",
                    "content": "Content here",
                    "reasoning": "Because...",
                    "source": "supermemory",
                    "relevanceScore": 0.9,
                    "noveltyScore": 0.8,
                    "timestamp": "2024-12-09T10:30:00",
                    "sourceUrl": null
                }
            ],
            "processingTimeMs": 1500
        }
        """.data(using: .utf8)!
        
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let response = try decoder.decode(AnalyzeResponse.self, from: json)
        
        XCTAssertEqual(response.suggestions.count, 1)
        XCTAssertEqual(response.processingTimeMs, 1500)
        XCTAssertEqual(response.suggestions[0].title, "Test Suggestion")
    }
    
    func testAnalyzeResponseDecodingEmptySuggestions() throws {
        let json = """
        {
            "suggestions": [],
            "processingTimeMs": 100
        }
        """.data(using: .utf8)!
        
        let decoder = JSONDecoder()
        let response = try decoder.decode(AnalyzeResponse.self, from: json)
        
        XCTAssertTrue(response.suggestions.isEmpty)
        XCTAssertEqual(response.processingTimeMs, 100)
    }
}
