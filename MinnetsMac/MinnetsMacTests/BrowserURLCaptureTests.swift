import XCTest
@testable import MinnetsMac

/// Tests for BrowserURLCapture utility
final class BrowserURLCaptureTests: XCTestCase {
    
    // MARK: - Browser Detection Tests
    
    func testBrowserFromBundleIdentifier_Safari() {
        let browser = BrowserURLCapture.Browser.from(bundleIdentifier: "com.apple.Safari")
        XCTAssertEqual(browser, .safari)
    }
    
    func testBrowserFromBundleIdentifier_Chrome() {
        let browser = BrowserURLCapture.Browser.from(bundleIdentifier: "com.google.Chrome")
        XCTAssertEqual(browser, .chrome)
    }
    
    func testBrowserFromBundleIdentifier_Firefox() {
        let browser = BrowserURLCapture.Browser.from(bundleIdentifier: "org.mozilla.firefox")
        XCTAssertEqual(browser, .firefox)
    }
    
    func testBrowserFromBundleIdentifier_Arc() {
        let browser = BrowserURLCapture.Browser.from(bundleIdentifier: "company.thebrowser.Browser")
        XCTAssertEqual(browser, .arc)
    }
    
    func testBrowserFromBundleIdentifier_Unknown() {
        let browser = BrowserURLCapture.Browser.from(bundleIdentifier: "com.apple.Xcode")
        XCTAssertNil(browser)
    }
    
    func testBrowserFromBundleIdentifier_CaseInsensitive() {
        let browser = BrowserURLCapture.Browser.from(bundleIdentifier: "COM.APPLE.SAFARI")
        XCTAssertEqual(browser, .safari)
    }
    
    // MARK: - AppleScript Support Tests
    
    func testBrowserSupportsAppleScript() {
        XCTAssertTrue(BrowserURLCapture.Browser.safari.supportsAppleScript)
        XCTAssertTrue(BrowserURLCapture.Browser.chrome.supportsAppleScript)
        XCTAssertTrue(BrowserURLCapture.Browser.arc.supportsAppleScript)
        XCTAssertTrue(BrowserURLCapture.Browser.brave.supportsAppleScript)
        XCTAssertTrue(BrowserURLCapture.Browser.edge.supportsAppleScript)
        XCTAssertFalse(BrowserURLCapture.Browser.firefox.supportsAppleScript)
    }
    
    // MARK: - Search Query Extraction Tests
    
    func testExtractSearchQuery_Google() {
        let url = "https://www.google.com/search?q=swift+testing&sourceid=chrome"
        let query = BrowserURLCapture.extractSearchQuery(from: url)
        XCTAssertEqual(query, "swift testing")
    }
    
    func testExtractSearchQuery_GoogleWithEncodedSpaces() {
        let url = "https://www.google.com/search?q=swift%20unit%20testing"
        let query = BrowserURLCapture.extractSearchQuery(from: url)
        XCTAssertEqual(query, "swift unit testing")
    }
    
    func testExtractSearchQuery_Bing() {
        let url = "https://www.bing.com/search?q=xctest+framework"
        let query = BrowserURLCapture.extractSearchQuery(from: url)
        XCTAssertEqual(query, "xctest framework")
    }
    
    func testExtractSearchQuery_DuckDuckGo() {
        let url = "https://duckduckgo.com/?q=swift+async+await&t=h_"
        let query = BrowserURLCapture.extractSearchQuery(from: url)
        XCTAssertEqual(query, "swift async await")
    }
    
    func testExtractSearchQuery_Yahoo() {
        let url = "https://search.yahoo.com/search?p=macos+development"
        let query = BrowserURLCapture.extractSearchQuery(from: url)
        XCTAssertEqual(query, "macos development")
    }
    
    func testExtractSearchQuery_NonSearchURL() {
        let url = "https://developer.apple.com/documentation/swift"
        let query = BrowserURLCapture.extractSearchQuery(from: url)
        XCTAssertNil(query)
    }
    
    func testExtractSearchQuery_InvalidURL() {
        let url = "not a valid url"
        let query = BrowserURLCapture.extractSearchQuery(from: url)
        XCTAssertNil(query)
    }
    
    func testExtractSearchQuery_EmptyQuery() {
        let url = "https://www.google.com/search?q="
        let query = BrowserURLCapture.extractSearchQuery(from: url)
        XCTAssertEqual(query, "")
    }
    
    // MARK: - Browser Display Name Tests
    
    func testBrowserDisplayName() {
        XCTAssertEqual(BrowserURLCapture.Browser.safari.displayName, "Safari")
        XCTAssertEqual(BrowserURLCapture.Browser.chrome.displayName, "Google Chrome")
        XCTAssertEqual(BrowserURLCapture.Browser.firefox.displayName, "Firefox")
        XCTAssertEqual(BrowserURLCapture.Browser.arc.displayName, "Arc")
        XCTAssertEqual(BrowserURLCapture.Browser.brave.displayName, "Brave Browser")
        XCTAssertEqual(BrowserURLCapture.Browser.edge.displayName, "Microsoft Edge")
    }
}
