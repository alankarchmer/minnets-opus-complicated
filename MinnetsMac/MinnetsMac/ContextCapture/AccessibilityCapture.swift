import Foundation
import AppKit
import ApplicationServices

/// Error types for accessibility capture operations
enum AccessibilityCaptureError: Error, LocalizedError {
    case permissionDenied
    case noFrontmostApp
    case noWindowFound
    case noTextExtracted
    
    var errorDescription: String? {
        switch self {
        case .permissionDenied:
            return "Accessibility permission is not granted"
        case .noFrontmostApp:
            return "No frontmost application found"
        case .noWindowFound:
            return "No window found for the frontmost application"
        case .noTextExtracted:
            return "No text could be extracted from the window"
        }
    }
}

/// Captures text content from the frontmost window using Accessibility APIs
class AccessibilityCapture {
    
    // MARK: - Public Methods
    
    /// Captures text content from the frontmost window using Accessibility APIs
    /// Returns tuple of (text content, window title) or nil if capture fails
    func captureFromFrontmostWindow() -> (text: String, windowTitle: String)? {
        do {
            return try captureFromFrontmostWindowWithError()
        } catch {
            handleCaptureError(error)
            return nil
        }
    }
    
    /// Captures text content with detailed error reporting
    /// Throws AccessibilityCaptureError on failure
    func captureFromFrontmostWindowWithError() throws -> (text: String, windowTitle: String) {
        // Check permission first using direct API call (avoids MainActor isolation)
        guard AXIsProcessTrusted() else {
            throw AccessibilityCaptureError.permissionDenied
        }
        
        guard let frontmostApp = NSWorkspace.shared.frontmostApplication else {
            throw AccessibilityCaptureError.noFrontmostApp
        }
        
        let appName = frontmostApp.localizedName ?? "Unknown"
        let pid = frontmostApp.processIdentifier
        let appElement = AXUIElementCreateApplication(pid)
        
        // Try to get the focused window first
        var windowElement: AXUIElement?
        var windowTitle = appName
        
        var focusedWindow: CFTypeRef?
        let focusedResult = AXUIElementCopyAttributeValue(
            appElement,
            kAXFocusedWindowAttribute as CFString,
            &focusedWindow
        )
        
        if focusedResult == .success, let window = focusedWindow {
            windowElement = (window as! AXUIElement)
            
            // Get window title
            var titleValue: CFTypeRef?
            AXUIElementCopyAttributeValue(windowElement!, kAXTitleAttribute as CFString, &titleValue)
            windowTitle = (titleValue as? String) ?? appName
        } else {
            // Check if the error is due to permission
            if focusedResult == .apiDisabled || focusedResult == .notImplemented {
                throw AccessibilityCaptureError.permissionDenied
            }
            
            // Fallback: Try to get any window from the app's window list
            print("⚠️ Accessibility: No focused window (error: \(focusedResult.rawValue)), trying window list...")
            
            var windows: CFTypeRef?
            let windowsResult = AXUIElementCopyAttributeValue(
                appElement,
                kAXWindowsAttribute as CFString,
                &windows
            )
            
            if windowsResult == .apiDisabled {
                throw AccessibilityCaptureError.permissionDenied
            }
            
            if windowsResult == .success, let windowList = windows as? [AXUIElement], let firstWindow = windowList.first {
                windowElement = firstWindow
                
                var titleValue: CFTypeRef?
                AXUIElementCopyAttributeValue(firstWindow, kAXTitleAttribute as CFString, &titleValue)
                windowTitle = (titleValue as? String) ?? appName
                print("✓ Accessibility: Using first window from list: \(windowTitle)")
            } else {
                // Last resort: extract text directly from app element
                print("⚠️ Accessibility: No windows found, extracting from app element directly")
                windowElement = nil
            }
        }
        
        // Extract text from either window or app element
        var allText: [String] = []
        let elementToExtract = windowElement ?? appElement
        extractText(from: elementToExtract, into: &allText, depth: 0, maxDepth: 15)
        
        let combinedText = allText
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
            .joined(separator: "\n")
        
        // Truncate if too long (to avoid overwhelming the LLM)
        let maxLength = 8000
        let truncatedText = combinedText.count > maxLength
            ? String(combinedText.prefix(maxLength)) + "\n... [truncated]"
            : combinedText
        
        if truncatedText.isEmpty {
            print("⚠️ Accessibility: No text extracted from \(appName)")
            throw AccessibilityCaptureError.noTextExtracted
        }
        
        print("✓ Accessibility: Extracted \(truncatedText.count) chars from \(appName)")
        return (truncatedText, windowTitle)
    }
    
    // MARK: - Private Methods
    
    private func extractText(from element: AXUIElement, into texts: inout [String], depth: Int, maxDepth: Int) {
        guard depth < maxDepth else { return }
        
        // Try to get value (for text fields, text areas)
        var value: CFTypeRef?
        if AXUIElementCopyAttributeValue(element, kAXValueAttribute as CFString, &value) == .success {
            if let text = value as? String, !text.isEmpty {
                texts.append(text)
            }
        }
        
        // Try to get title (for labels, buttons, etc.)
        var title: CFTypeRef?
        if AXUIElementCopyAttributeValue(element, kAXTitleAttribute as CFString, &title) == .success {
            if let text = title as? String, !text.isEmpty {
                texts.append(text)
            }
        }
        
        // Try to get description
        var description: CFTypeRef?
        if AXUIElementCopyAttributeValue(element, kAXDescriptionAttribute as CFString, &description) == .success {
            if let text = description as? String, !text.isEmpty {
                texts.append(text)
            }
        }
        
        // Try to get static text content
        var staticText: CFTypeRef?
        if AXUIElementCopyAttributeValue(element, "AXStaticText" as CFString, &staticText) == .success {
            if let text = staticText as? String, !text.isEmpty {
                texts.append(text)
            }
        }
        
        // Recursively process children
        var children: CFTypeRef?
        if AXUIElementCopyAttributeValue(element, kAXChildrenAttribute as CFString, &children) == .success {
            if let childArray = children as? [AXUIElement] {
                for child in childArray {
                    extractText(from: child, into: &texts, depth: depth + 1, maxDepth: maxDepth)
                }
            }
        }
    }
    
    // MARK: - Error Handling
    
    private func handleCaptureError(_ error: Error) {
        if let captureError = error as? AccessibilityCaptureError {
            switch captureError {
            case .permissionDenied:
                print("❌ Accessibility: Permission denied - user needs to grant Accessibility access")
                NotificationCenter.default.post(name: .accessibilityPermissionNeeded, object: nil)
            case .noFrontmostApp:
                print("❌ Accessibility: No frontmost application found")
            case .noWindowFound:
                print("❌ Accessibility: No window found for the frontmost app")
            case .noTextExtracted:
                print("❌ Accessibility: No text could be extracted from the window")
            }
        } else {
            print("❌ Accessibility error: \(error.localizedDescription)")
        }
    }
}

// MARK: - Notification Names

extension Notification.Name {
    static let accessibilityPermissionNeeded = Notification.Name("minnets.accessibilityPermissionNeeded")
}
