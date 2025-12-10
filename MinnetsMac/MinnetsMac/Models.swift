import Foundation

// MARK: - Suggestion Model

struct Suggestion: Identifiable, Codable {
    let id: String
    let title: String
    let content: String
    let reasoning: String
    let source: SuggestionSource
    let relevanceScore: Double
    let noveltyScore: Double
    let timestamp: Date
    let sourceUrl: String?
    
    var combinedScore: Double {
        (relevanceScore + noveltyScore) / 2.0
    }
    
    enum CodingKeys: String, CodingKey {
        case id, title, content, reasoning, source, timestamp
        case relevanceScore = "relevanceScore"
        case noveltyScore = "noveltyScore"
        case sourceUrl = "sourceUrl"
    }
}

enum SuggestionSource: String, Codable {
    case supermemory = "supermemory"
    case webSearch = "web_search"
    case combined = "combined"
    case orthogonal = "orthogonal"
    
    var displayName: String {
        switch self {
        case .supermemory: return "Your Memory"
        case .webSearch: return "Web Search"
        case .combined: return "Memory + Web"
        case .orthogonal: return "Serendipity"
        }
    }
    
    var iconName: String {
        switch self {
        case .supermemory: return "brain"
        case .webSearch: return "globe"
        case .combined: return "sparkles"
        case .orthogonal: return "wand.and.stars"
        }
    }
}

// MARK: - Context Model

struct CapturedContext: Codable {
    let text: String
    let appName: String
    let windowTitle: String
    let timestamp: Date
    let captureMethod: CaptureMethod
    
    enum CaptureMethod: String, Codable {
        case accessibility
        case ocr
        case clipboard
    }
}

// MARK: - Backend API Models

struct AnalyzeRequest: Codable {
    let context: String
    let appName: String
    let windowTitle: String
}

struct AnalyzeResponse: Codable {
    let suggestions: [Suggestion]
    let processingTimeMs: Int
    
    enum CodingKeys: String, CodingKey {
        case suggestions
        case processingTimeMs = "processingTimeMs"
    }
}

// MARK: - App State

enum AppState: Equatable {
    case idle
    case capturing
    case analyzing
    case hasSuggestions
    case error(String)
    
    var statusText: String {
        switch self {
        case .idle: return "Monitoring..."
        case .capturing: return "Reading context..."
        case .analyzing: return "Finding insights..."
        case .hasSuggestions: return "New insights available"
        case .error(let message): return "Error: \(message)"
        }
    }
}

