import Foundation

actor BackendClient {
    private let baseURL: URL
    private let session: URLSession
    
    init(baseURL: URL = URL(string: "http://127.0.0.1:8000")!) {
        self.baseURL = baseURL
        
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 60  // Analysis can take 15-20s with LLM calls
        config.timeoutIntervalForResource = 90
        self.session = URLSession(configuration: config)
    }
    
    // MARK: - API Methods
    
    func analyze(context: String, appName: String, windowTitle: String) async throws -> [Suggestion] {
        let endpoint = baseURL.appendingPathComponent("/analyze")
        
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let requestBody = AnalyzeRequest(
            context: context,
            appName: appName,
            windowTitle: windowTitle
        )
        
        request.httpBody = try JSONEncoder().encode(requestBody)
        
        let (data, response) = try await session.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw BackendError.invalidResponse
        }
        
        guard httpResponse.statusCode == 200 else {
            throw BackendError.httpError(statusCode: httpResponse.statusCode)
        }
        
        let decoder = JSONDecoder()
        // Use custom date decoding to handle Python's ISO8601 format (without timezone)
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let dateString = try container.decode(String.self)
            
            // Python outputs: "2025-12-03T21:20:44.215558" (no timezone)
            // Try DateFormatter first (more flexible)
            let df = DateFormatter()
            df.locale = Locale(identifier: "en_US_POSIX")
            
            // Try with fractional seconds (Python's default)
            df.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"
            if let date = df.date(from: dateString) {
                return date
            }
            
            // Try with fewer fractional digits
            df.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSS"
            if let date = df.date(from: dateString) {
                return date
            }
            
            // Try without fractional seconds
            df.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
            if let date = df.date(from: dateString) {
                return date
            }
            
            // Try ISO8601 with Z suffix
            let iso = ISO8601DateFormatter()
            iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            if let date = iso.date(from: dateString) {
                return date
            }
            
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Cannot decode date: \(dateString)")
        }
        
        do {
            let analyzeResponse = try decoder.decode(AnalyzeResponse.self, from: data)
            return analyzeResponse.suggestions
        } catch let decodingError as DecodingError {
            print("❌ JSON decoding error:")
            switch decodingError {
            case .keyNotFound(let key, let context):
                print("   Key '\(key.stringValue)' not found: \(context.debugDescription)")
            case .typeMismatch(let type, let context):
                print("   Type mismatch for \(type): \(context.debugDescription)")
            case .valueNotFound(let type, let context):
                print("   Value not found for \(type): \(context.debugDescription)")
            case .dataCorrupted(let context):
                print("   Data corrupted: \(context.debugDescription)")
            @unknown default:
                print("   Unknown decoding error: \(decodingError)")
            }
            // Print raw JSON for debugging
            if let jsonString = String(data: data, encoding: .utf8) {
                print("   Raw JSON: \(jsonString.prefix(500))...")
            }
            throw BackendError.decodingError(decodingError)
        }
    }
    
    func healthCheck() async -> Bool {
        let endpoint = baseURL.appendingPathComponent("/health")
        
        var request = URLRequest(url: endpoint)
        request.httpMethod = "GET"
        request.timeoutInterval = 3  // Quick 3-second timeout for health checks
        
        do {
            let (_, response) = try await session.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                return false
            }
            
            return httpResponse.statusCode == 200
        } catch {
            return false
        }
    }
    
    func saveToMemory(title: String, content: String, sourceUrl: String?, context: String?) async throws -> SaveToMemoryResponse {
        let endpoint = baseURL.appendingPathComponent("/save-to-memory")
        
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let requestBody = SaveToMemoryRequest(
            title: title,
            content: content,
            sourceUrl: sourceUrl,
            context: context
        )
        
        request.httpBody = try JSONEncoder().encode(requestBody)
        
        let (data, response) = try await session.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw BackendError.invalidResponse
        }
        
        guard httpResponse.statusCode == 200 else {
            throw BackendError.httpError(statusCode: httpResponse.statusCode)
        }
        
        return try JSONDecoder().decode(SaveToMemoryResponse.self, from: data)
    }
}

// MARK: - Save to Memory Models

struct SaveToMemoryRequest: Codable {
    let title: String
    let content: String
    let sourceUrl: String?
    let context: String?
    
    enum CodingKeys: String, CodingKey {
        case title
        case content
        case sourceUrl = "source_url"
        case context
    }
}

struct SaveToMemoryResponse: Codable {
    let status: String
    let memoryId: String?
    let message: String?
    
    enum CodingKeys: String, CodingKey {
        case status
        case memoryId = "memory_id"
        case message
    }
}

// MARK: - Errors

enum BackendError: LocalizedError {
    case invalidResponse
    case httpError(statusCode: Int)
    case decodingError(Error)
    case networkError(Error)
    
    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "Invalid response from backend"
        case .httpError(let statusCode):
            return "HTTP error: \(statusCode)"
        case .decodingError(let error):
            return "Failed to decode response: \(error.localizedDescription)"
        case .networkError(let error):
            return "Network error: \(error.localizedDescription)"
        }
    }
}

