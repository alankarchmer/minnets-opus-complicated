import Foundation
import AppKit

/// Shared utility for capturing URLs and search queries from browsers
/// Consolidates browser-specific AppleScript logic in one place
enum BrowserURLCapture {
    
    /// Known browser bundle identifiers
    enum Browser: CaseIterable {
        case safari
        case chrome
        case firefox
        case arc
        case brave
        case edge
        
        var bundleIdentifiers: [String] {
            switch self {
            case .safari: return ["com.apple.Safari"]
            case .chrome: return ["com.google.Chrome"]
            case .firefox: return ["org.mozilla.firefox"]
            case .arc: return ["company.thebrowser.Browser"]
            case .brave: return ["com.brave.Browser"]
            case .edge: return ["com.microsoft.edgemac"]
            }
        }
        
        var displayName: String {
            switch self {
            case .safari: return "Safari"
            case .chrome: return "Google Chrome"
            case .firefox: return "Firefox"
            case .arc: return "Arc"
            case .brave: return "Brave Browser"
            case .edge: return "Microsoft Edge"
            }
        }
        
        /// Whether this browser supports AppleScript URL retrieval
        var supportsAppleScript: Bool {
            switch self {
            case .firefox: return false  // Firefox has limited AppleScript support
            default: return true
            }
        }
        
        static func from(bundleIdentifier: String) -> Browser? {
            let lowercased = bundleIdentifier.lowercased()
            return Browser.allCases.first { browser in
                browser.bundleIdentifiers.contains { lowercased.contains($0.lowercased()) }
            }
        }
    }
    
    // MARK: - Public API
    
    /// Gets the URL of the active tab in the frontmost browser
    /// - Returns: The URL string, or nil if not a browser or URL couldn't be retrieved
    static func getActiveURL() -> String? {
        guard let frontApp = NSWorkspace.shared.frontmostApplication,
              let bundleId = frontApp.bundleIdentifier,
              let browser = Browser.from(bundleIdentifier: bundleId),
              browser.supportsAppleScript else {
            return nil
        }
        
        return getURL(for: browser)
    }
    
    /// Checks if the frontmost app is a browser
    static func isBrowserActive() -> Bool {
        guard let frontApp = NSWorkspace.shared.frontmostApplication,
              let bundleId = frontApp.bundleIdentifier else {
            return false
        }
        return Browser.from(bundleIdentifier: bundleId) != nil
    }
    
    /// Extracts search query from a URL if it's a search engine results page
    /// - Parameter url: The URL to parse
    /// - Returns: The search query, or nil if not a search URL
    static func extractSearchQuery(from url: String) -> String? {
        guard let components = URLComponents(string: url) else { return nil }
        
        // Common search query parameter names
        let searchParams = ["q", "query", "search", "p", "text", "wd"]
        
        for param in searchParams {
            if let value = components.queryItems?.first(where: { $0.name == param })?.value {
                return value.removingPercentEncoding ?? value
            }
        }
        
        // Check if it's a known search engine
        let searchHosts = [
            "google.com", "www.google.com",
            "bing.com", "www.bing.com",
            "duckduckgo.com", "www.duckduckgo.com",
            "search.yahoo.com",
            "baidu.com", "www.baidu.com",
            "yandex.com", "www.yandex.com"
        ]
        
        if let host = components.host?.lowercased(),
           searchHosts.contains(where: { host.contains($0) }) {
            // Already checked above, but this confirms it's a search page
            return components.queryItems?.first(where: { $0.name == "q" })?.value
        }
        
        return nil
    }
    
    // MARK: - Private Implementation
    
    private static func getURL(for browser: Browser) -> String? {
        let script: String
        
        switch browser {
        case .safari:
            script = """
            tell application "Safari"
                if (count of windows) > 0 then
                    return URL of current tab of front window
                end if
            end tell
            """
            
        case .chrome, .brave, .edge:
            // Chrome-based browsers use the same AppleScript API
            let appName = browser.displayName
            script = """
            tell application "\(appName)"
                if (count of windows) > 0 then
                    return URL of active tab of front window
                end if
            end tell
            """
            
        case .arc:
            script = """
            tell application "Arc"
                if (count of windows) > 0 then
                    return URL of active tab of front window
                end if
            end tell
            """
            
        case .firefox:
            // Firefox doesn't support AppleScript well
            return nil
        }
        
        return runAppleScript(script)
    }
    
    private static func runAppleScript(_ source: String) -> String? {
        var error: NSDictionary?
        guard let script = NSAppleScript(source: source) else { return nil }
        
        let result = script.executeAndReturnError(&error)
        
        if let error = error {
            // Don't log common "can't get" errors (app not running, no windows, etc.)
            let errorNum = error["NSAppleScriptErrorNumber"] as? Int ?? 0
            if errorNum != -1728 && errorNum != -1719 && errorNum != -609 {
                print("⚠️ BrowserURLCapture AppleScript error: \(error)")
            }
            return nil
        }
        
        return result.stringValue
    }
}
