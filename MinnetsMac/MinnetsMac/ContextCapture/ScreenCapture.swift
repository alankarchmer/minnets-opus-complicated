import Foundation
import AppKit
import ScreenCaptureKit
import Vision

/// Modern screen capture using ScreenCaptureKit (macOS 12.3+)
/// Captures the frontmost window and performs OCR to extract text
class ScreenCapture {
    
    // MARK: - Public Methods
    
    /// Captures the frontmost window and performs OCR to extract text
    /// Returns tuple of (extracted text, window title) or nil if capture fails
    func captureScreen() async -> (text: String, windowTitle: String)? {
        // Skip permission check - just try to capture
        // (Permission APIs are buggy during development)
        
        do {
            // Get shareable content (windows and displays)
            let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
            
            print("📊 ScreenCapture: Found \(content.windows.count) windows, \(content.displays.count) displays")
            
            // Find the frontmost app's window
            guard let frontmostApp = NSWorkspace.shared.frontmostApplication else {
                print("❌ ScreenCapture: No frontmost application")
                return nil
            }
            
            let appName = frontmostApp.localizedName ?? "Unknown"
            let pid = frontmostApp.processIdentifier
            
            // Find windows belonging to the frontmost app
            let appWindows = content.windows.filter { window in
                window.owningApplication?.processID == pid
            }
            
            print("📊 ScreenCapture: Found \(appWindows.count) windows for \(appName)")
            
            // Get the main window (prefer the one that's on screen and has a title)
            guard let targetWindow = appWindows.first(where: { $0.isOnScreen && $0.title?.isEmpty == false }) 
                  ?? appWindows.first(where: { $0.isOnScreen })
                  ?? appWindows.first else {
                print("❌ ScreenCapture: No windows found for \(appName)")
                
                // Fallback: try to capture the main display instead
                if let display = content.displays.first {
                    print("⚠️ ScreenCapture: Falling back to display capture")
                    return await captureDisplay(display, appName: appName)
                }
                return nil
            }
            
            let windowTitle = targetWindow.title ?? appName
            print("📷 ScreenCapture: Capturing window '\(windowTitle)'")
            
            // Capture the window
            guard let image = await captureWindow(targetWindow) else {
                print("❌ ScreenCapture: Failed to capture window image")
                return nil
            }
            
            // Perform OCR on the captured image
            guard let text = await performOCR(on: image) else {
                print("❌ ScreenCapture: OCR returned no text")
                return nil
            }
            
            print("✓ ScreenCapture: Extracted \(text.count) chars via OCR")
            return (text, windowTitle)
            
        } catch let error as NSError {
            print("❌ ScreenCaptureKit error: \(error.localizedDescription) (code: \(error.code))")
            if error.code == -3801 {
                print("   This usually means screen recording permission is not granted or app needs restart")
            }
            return nil
        }
    }
    
    /// Fallback: Capture the entire display
    private func captureDisplay(_ display: SCDisplay, appName: String) async -> (text: String, windowTitle: String)? {
        do {
            let filter = SCContentFilter(display: display, excludingWindows: [])
            
            let config = SCStreamConfiguration()
            config.width = display.width
            config.height = display.height
            config.showsCursor = false
            
            let image = try await SCScreenshotManager.captureImage(
                contentFilter: filter,
                configuration: config
            )
            
            guard let text = await performOCR(on: image) else {
                return nil
            }
            
            return (text, appName)
        } catch {
            print("❌ Display capture error: \(error)")
            return nil
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
}

