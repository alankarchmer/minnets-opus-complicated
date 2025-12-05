import Foundation
import AppKit
import ScreenCaptureKit
import Vision

/// Error types for screen capture operations
enum ScreenCaptureError: Error, LocalizedError {
    case permissionDenied
    case noDisplaysFound
    case noWindowsFound
    case captureFailed(Error)
    case ocrFailed
    
    var errorDescription: String? {
        switch self {
        case .permissionDenied:
            return "Screen recording permission is not granted"
        case .noDisplaysFound:
            return "No displays found to capture"
        case .noWindowsFound:
            return "No windows found for the frontmost application"
        case .captureFailed(let error):
            return "Screen capture failed: \(error.localizedDescription)"
        case .ocrFailed:
            return "OCR text extraction failed"
        }
    }
}

/// Modern screen capture using ScreenCaptureKit (macOS 12.3+)
/// Captures the frontmost window and performs OCR to extract text
class ScreenCapture {
    
    // MARK: - Public Methods
    
    /// Captures the frontmost window and performs OCR to extract text
    /// Returns tuple of (extracted text, window title) or nil if capture fails
    func captureScreen() async -> (text: String, windowTitle: String)? {
        do {
            return try await captureScreenWithError()
        } catch {
            handleCaptureError(error)
            return nil
        }
    }
    
    /// Captures the frontmost window with detailed error reporting
    /// Throws ScreenCaptureError on failure
    func captureScreenWithError() async throws -> (text: String, windowTitle: String) {
        // Check permission first using direct API call (avoids MainActor issues)
        guard CGPreflightScreenCaptureAccess() else {
            throw ScreenCaptureError.permissionDenied
        }
        
        // Get shareable content (windows and displays)
        let content: SCShareableContent
        do {
            content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
        } catch let error as NSError {
            if error.code == -3801 || error.code == -3802 {
                throw ScreenCaptureError.permissionDenied
            }
            throw ScreenCaptureError.captureFailed(error)
        }
        
        print("📊 ScreenCapture: Found \(content.windows.count) windows, \(content.displays.count) displays")
        
        // Find the frontmost app's window
        guard let frontmostApp = NSWorkspace.shared.frontmostApplication else {
            print("❌ ScreenCapture: No frontmost application")
            throw ScreenCaptureError.noWindowsFound
        }
        
        let appName = frontmostApp.localizedName ?? "Unknown"
        let pid = frontmostApp.processIdentifier
        
        // Find windows belonging to the frontmost app
        let appWindows = content.windows.filter { window in
            window.owningApplication?.processID == pid
        }
        
        print("📊 ScreenCapture: Found \(appWindows.count) windows for \(appName)")
        
        // Get the main window (prefer the one that's on screen and has a title)
        if let targetWindow = appWindows.first(where: { $0.isOnScreen && $0.title?.isEmpty == false })
            ?? appWindows.first(where: { $0.isOnScreen })
            ?? appWindows.first {
            
            let windowTitle = targetWindow.title ?? appName
            print("📷 ScreenCapture: Capturing window '\(windowTitle)'")
            
            // Capture the window
            guard let image = await captureWindow(targetWindow) else {
                throw ScreenCaptureError.captureFailed(NSError(domain: "ScreenCapture", code: -1, userInfo: [NSLocalizedDescriptionKey: "Failed to capture window image"]))
            }
            
            // Perform OCR on the captured image
            guard let text = await performOCR(on: image) else {
                throw ScreenCaptureError.ocrFailed
            }
            
            print("✓ ScreenCapture: Extracted \(text.count) chars via OCR")
            return (text, windowTitle)
        }
        
        // Fallback: try to capture the main display instead
        print("⚠️ ScreenCapture: No windows found for \(appName), falling back to display capture")
        
        guard let display = content.displays.first else {
            throw ScreenCaptureError.noDisplaysFound
        }
        
        return try await captureDisplay(display, appName: appName)
    }
    
    // MARK: - Private Methods
    
    /// Fallback: Capture the entire display
    private func captureDisplay(_ display: SCDisplay, appName: String) async throws -> (text: String, windowTitle: String) {
        let filter = SCContentFilter(display: display, excludingWindows: [])
        
        let config = SCStreamConfiguration()
        config.width = display.width
        config.height = display.height
        config.showsCursor = false
        
        do {
            let image = try await SCScreenshotManager.captureImage(
                contentFilter: filter,
                configuration: config
            )
            
            guard let text = await performOCR(on: image) else {
                throw ScreenCaptureError.ocrFailed
            }
            
            return (text, appName)
        } catch {
            throw ScreenCaptureError.captureFailed(error)
        }
    }
    
    // MARK: - Window Capture
    
    private func captureWindow(_ window: SCWindow) async -> CGImage? {
        do {
            // Create a filter for just this window
            let filter = SCContentFilter(desktopIndependentWindow: window)
            
            // Configure capture settings
            let config = SCStreamConfiguration()
            config.width = Int(window.frame.width) * 2  // Retina resolution
            config.height = Int(window.frame.height) * 2
            config.scalesToFit = false
            config.showsCursor = false
            config.captureResolution = .best
            
            // Capture the image
            let image = try await SCScreenshotManager.captureImage(
                contentFilter: filter,
                configuration: config
            )
            
            return image
            
        } catch {
            print("Window capture error: \(error)")
            return nil
        }
    }
    
    // MARK: - OCR
    
    private func performOCR(on image: CGImage) async -> String? {
        return await withCheckedContinuation { continuation in
            let request = VNRecognizeTextRequest { request, error in
                if let error = error {
                    print("OCR error: \(error)")
                    continuation.resume(returning: nil)
                    return
                }
                
                guard let observations = request.results as? [VNRecognizedTextObservation] else {
                    continuation.resume(returning: nil)
                    return
                }
                
                // Extract text from observations, sorted by position (top to bottom, left to right)
                let sortedObservations = observations.sorted { obs1, obs2 in
                    // Sort by Y position (inverted because Vision uses bottom-left origin)
                    if abs(obs1.boundingBox.origin.y - obs2.boundingBox.origin.y) > 0.02 {
                        return obs1.boundingBox.origin.y > obs2.boundingBox.origin.y
                    }
                    // Then by X position
                    return obs1.boundingBox.origin.x < obs2.boundingBox.origin.x
                }
                
                let texts = sortedObservations.compactMap { observation -> String? in
                    observation.topCandidates(1).first?.string
                }
                
                let combinedText = texts.joined(separator: "\n")
                
                // Truncate if too long
                let maxLength = 8000
                let truncatedText = combinedText.count > maxLength
                    ? String(combinedText.prefix(maxLength)) + "\n... [truncated]"
                    : combinedText
                
                continuation.resume(returning: truncatedText.isEmpty ? nil : truncatedText)
            }
            
            // Configure for accurate recognition
            request.recognitionLevel = .accurate
            request.usesLanguageCorrection = true
            request.recognitionLanguages = ["en-US"]
            
            let handler = VNImageRequestHandler(cgImage: image, options: [:])
            
            do {
                try handler.perform([request])
            } catch {
                print("Failed to perform OCR: \(error)")
                continuation.resume(returning: nil)
            }
        }
    }
    
    // MARK: - Error Handling
    
    private func handleCaptureError(_ error: Error) {
        if let captureError = error as? ScreenCaptureError {
            switch captureError {
            case .permissionDenied:
                print("❌ ScreenCapture: Permission denied - user needs to grant Screen Recording access")
                NotificationCenter.default.post(name: .screenRecordingPermissionNeeded, object: nil)
            case .noDisplaysFound:
                print("❌ ScreenCapture: No displays found")
            case .noWindowsFound:
                print("❌ ScreenCapture: No windows found for the frontmost app")
            case .captureFailed(let underlyingError):
                print("❌ ScreenCapture: Capture failed - \(underlyingError.localizedDescription)")
            case .ocrFailed:
                print("❌ ScreenCapture: OCR text extraction failed")
            }
        } else if let nsError = error as NSError? {
            print("❌ ScreenCaptureKit error: \(nsError.localizedDescription) (code: \(nsError.code))")
            if nsError.code == -3801 || nsError.code == -3802 {
                print("   This means screen recording permission is not granted")
                NotificationCenter.default.post(name: .screenRecordingPermissionNeeded, object: nil)
            }
        } else {
            print("❌ ScreenCapture error: \(error.localizedDescription)")
        }
    }
}

// MARK: - Notification Names

extension Notification.Name {
    static let screenRecordingPermissionNeeded = Notification.Name("minnets.screenRecordingPermissionNeeded")
}
