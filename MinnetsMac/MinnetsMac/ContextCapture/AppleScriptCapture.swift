import Foundation
import AppKit

/// Captures screen content using AppleScript
/// This approach often works better during development as it uses different permission mechanisms
class AppleScriptCapture {
    
    /// Captures the frontmost window content using AppleScript
    /// For browsers, returns URL that backend can use to fetch content
    func captureFromFrontmostWindow() -> (text: String, windowTitle: String)? {
        guard let frontmostApp = NSWorkspace.shared.frontmostApplication else {
            print("❌ AppleScript: No frontmost application")
            return nil
        }
        
        let appName = frontmostApp.localizedName ?? "Unknown"
        print("🍎 AppleScript: Capturing from \(appName)")
        
        // Try to get window title and URL (for browsers)
        var windowTitle = appName
        var capturedText = ""
        
        // Get window title
        if let title = getWindowTitle(appName: appName) {
            windowTitle = title
            capturedText += "Window Title: \(title)\n"
        }
        
        // For browsers, get the URL - this is the key info!
        if let url = getBrowserURL(appName: appName) {
            capturedText += "CURRENT_URL: \(url)\n"
            print("🍎 AppleScript: Got browser URL: \(url)")
        }
        
        // Try to get selected text (user might have highlighted something)
        if let selectedText = getSelectedText() {
            capturedText += "\nSelected Text:\n\(selectedText)\n"
        }
        
        // Get the document content if available (for text editors)
        if let docContent = getDocumentContent(appName: appName) {
            capturedText += "\nDocument Content:\n\(docContent)"
        }
        
        // If we got nothing useful, return nil
        if capturedText.isEmpty || (!capturedText.contains("CURRENT_URL") && capturedText.count < 50) {
            print("🍎 AppleScript: No useful content captured")
            return nil
        }
        
        print("🍎 AppleScript: Captured \(capturedText.count) chars")
        return (capturedText, windowTitle)
    }
    
    private func getWindowTitle(appName: String) -> String? {
        let script = """
        tell application "System Events"
            tell process "\(appName)"
                try
                    return name of front window
                end try
            end tell
        end tell
        """
        return runAppleScript(script)
    }
    
    private func getBrowserURL(appName: String) -> String? {
        var script: String
        
        if appName.contains("Chrome") {
            script = """
            tell application "Google Chrome"
                if (count of windows) > 0 then
                    return URL of active tab of front window
                end if
            end tell
            """
        } else if appName.contains("Safari") {
            script = """
            tell application "Safari"
                if (count of windows) > 0 then
                    return URL of current tab of front window
                end if
            end tell
            """
        } else if appName.contains("Firefox") {
            // Firefox doesn't support AppleScript well
            return nil
        } else if appName.contains("Arc") {
            script = """
            tell application "Arc"
                if (count of windows) > 0 then
                    return URL of active tab of front window
                end if
            end tell
            """
        } else {
            return nil
        }
        
        return runAppleScript(script)
    }
    
    private func getSelectedText() -> String? {
        // Try to get selected text via clipboard trick
        // Save current clipboard, simulate Cmd+C, get clipboard, restore
        // This is invasive so we skip it for now
        return nil
    }
    
    private func getDocumentContent(appName: String) -> String? {
        // For text editors and document apps, try to get content
        if appName.contains("TextEdit") {
            let script = """
            tell application "TextEdit"
                if (count of documents) > 0 then
                    return text of front document
                end if
            end tell
            """
            return runAppleScript(script)
        }
        
        if appName.contains("Notes") {
            let script = """
            tell application "Notes"
                if (count of notes) > 0 then
                    return body of first note
                end if
            end tell
            """
            return runAppleScript(script)
        }
        
        // VS Code / Cursor - try to get file path at least
        if appName.contains("Code") || appName.contains("Cursor") {
            let script = """
            tell application "System Events"
                tell process "\(appName)"
                    try
                        return name of front window
                    end try
                end tell
            end tell
            """
            if let windowName = runAppleScript(script) {
                return "Editing: \(windowName)"
            }
        }
        
        // Xcode
        if appName.contains("Xcode") {
            let script = """
            tell application "System Events"
                tell process "Xcode"
                    try
                        return name of front window
                    end try
                end tell
            end tell
            """
            if let windowName = runAppleScript(script) {
                return "Editing: \(windowName)"
            }
        }
        
        return nil
    }
    
    private func runAppleScript(_ source: String) -> String? {
        var error: NSDictionary?
        if let script = NSAppleScript(source: source) {
            let result = script.executeAndReturnError(&error)
            if let error = error {
                // Don't print errors for expected failures
                let errorNum = error["NSAppleScriptErrorNumber"] as? Int ?? 0
                if errorNum != -1728 && errorNum != -1719 { // Common "can't get" errors
                    print("   AppleScript error: \(error)")
                }
                return nil
            }
            return result.stringValue
        }
        return nil
    }
}

