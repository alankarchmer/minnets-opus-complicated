import Foundation
import AppKit
import Vision

class OCRCapture {
    
    // MARK: - Public Methods
    
    /// Captures the frontmost window and performs OCR to extract text
    func captureScreen() async -> String? {
        guard let image = captureWindowImage() else {
            print("Failed to capture window image")
            return nil
        }
        
        return await performOCR(on: image)
    }
    
    // MARK: - Screen Capture
    
    private func captureWindowImage() -> CGImage? {
        guard let frontmostApp = NSWorkspace.shared.frontmostApplication else {
            return nil
        }
        
        let pid = frontmostApp.processIdentifier
        
        // Get list of windows for this app
        let windowList = CGWindowListCopyWindowInfo([.optionOnScreenOnly], kCGNullWindowID) as? [[String: Any]] ?? []
        
        // Find windows belonging to the frontmost app
        let appWindows = windowList.filter { windowInfo in
            guard let ownerPID = windowInfo[kCGWindowOwnerPID as String] as? Int32 else {
                return false
            }
            return ownerPID == pid
        }
        
        // Get the main window (typically the first one, or the largest)
        guard let windowInfo = appWindows.first,
              let windowID = windowInfo[kCGWindowNumber as String] as? CGWindowID else {
            return nil
        }
        
        // Capture the window
        let image = CGWindowListCreateImage(
            .null,
            .optionIncludingWindow,
            windowID,
            [.boundsIgnoreFraming, .nominalResolution]
        )
        
        return image
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

