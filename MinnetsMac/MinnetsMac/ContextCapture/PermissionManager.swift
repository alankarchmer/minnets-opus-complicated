import Foundation
import AppKit
import ScreenCaptureKit

/// Centralized permission management for Minnets
/// Handles checking and requesting Accessibility and Screen Recording permissions
@MainActor
class PermissionManager: ObservableObject {
    static let shared = PermissionManager()
    
    // MARK: - Published State
    
    @Published private(set) var accessibilityStatus: PermissionStatus = .unknown
    @Published private(set) var screenRecordingStatus: PermissionStatus = .unknown
    
    /// Whether all required permissions are granted
    var hasAllPermissions: Bool {
        accessibilityStatus == .granted && screenRecordingStatus == .granted
    }
    
    // MARK: - Permission Status Enum
    
    enum PermissionStatus: Equatable {
        case unknown
        case granted
        case denied
        
        var isGranted: Bool { self == .granted }
        
        var displayText: String {
            switch self {
            case .unknown: return "Checking..."
            case .granted: return "Granted"
            case .denied: return "Not Granted"
            }
        }
        
        var symbolName: String {
            switch self {
            case .unknown: return "questionmark.circle"
            case .granted: return "checkmark.circle.fill"
            case .denied: return "xmark.circle.fill"
            }
        }
        
        var color: NSColor {
            switch self {
            case .unknown: return .secondaryLabelColor
            case .granted: return .systemGreen
            case .denied: return .systemOrange
            }
        }
    }
    
    // MARK: - Initialization
    
    private init() {
        // Initial check on startup
        refreshAllPermissions()
    }
    
    // MARK: - Permission Checking
    
    /// Refreshes the status of all permissions (synchronous)
    func refreshAllPermissions() {
        let oldAccessibility = accessibilityStatus
        let oldScreenRecording = screenRecordingStatus
        
        accessibilityStatus = checkAccessibilityPermission()
        screenRecordingStatus = checkScreenRecordingPermission()
        
        // Only log if status changed
        if oldAccessibility != accessibilityStatus || oldScreenRecording != screenRecordingStatus {
            print("📋 Permissions - Accessibility: \(accessibilityStatus.displayText), Screen Recording: \(screenRecordingStatus.displayText)")
        }
    }
    
    /// Checks if accessibility permission is granted
    /// Uses AXIsProcessTrusted() which is the standard API for this check
    func checkAccessibilityPermission() -> PermissionStatus {
        let trusted = AXIsProcessTrusted()
        return trusted ? .granted : .denied
    }
    
    /// Checks if screen recording permission is granted
    /// Uses CGPreflightScreenCaptureAccess() which returns the current permission state
    func checkScreenRecordingPermission() -> PermissionStatus {
        // CGPreflightScreenCaptureAccess is the correct API to check screen recording permission
        // It returns true if permission is granted, false otherwise
        // Note: On macOS, even after granting permission, the app may need to restart
        // for SCShareableContent to work, but this API will return the correct status
        let hasPermission = CGPreflightScreenCaptureAccess()
        return hasPermission ? .granted : .denied
    }
    
    // MARK: - Permission Requesting
    
    /// Requests accessibility permission by showing the system prompt
    /// Returns the new permission status after the request
    @discardableResult
    func requestAccessibilityPermission() -> PermissionStatus {
        // This will show the system dialog prompting the user to grant permission
        let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
        let trusted = AXIsProcessTrustedWithOptions(options)
        
        accessibilityStatus = trusted ? .granted : .denied
        return accessibilityStatus
    }
    
    /// Requests screen recording permission
    /// Uses CGRequestScreenCaptureAccess() which shows the system prompt
    /// Note: After granting, user may need to restart the app
    @discardableResult
    func requestScreenRecordingPermission() -> PermissionStatus {
        // CGRequestScreenCaptureAccess triggers the system permission dialog
        // and adds the app to the Screen Recording list in System Settings
        let granted = CGRequestScreenCaptureAccess()
        
        screenRecordingStatus = granted ? .granted : .denied
        print("📺 Screen Recording permission requested, granted: \(granted)")
        
        return screenRecordingStatus
    }
    
    // MARK: - Open System Settings
    
    /// Opens System Settings to the Accessibility pane
    func openAccessibilitySettings() {
        let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility")!
        NSWorkspace.shared.open(url)
    }
    
    /// Opens System Settings to the Screen Recording pane
    func openScreenRecordingSettings() {
        let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture")!
        NSWorkspace.shared.open(url)
    }
    
    // MARK: - Polling for Permission Changes
    
    /// Starts polling for permission status changes
    /// Useful during onboarding when user is granting permissions in System Settings
    func startPollingForPermissionChanges(interval: TimeInterval = 2.0, onUpdate: @escaping () -> Void) -> Task<Void, Never> {
        return Task { [weak self] in
            while !Task.isCancelled {
                guard let self = self else { break }
                
                let previousAccessibility = self.accessibilityStatus
                let previousScreenRecording = self.screenRecordingStatus
                
                await MainActor.run {
                    self.refreshAllPermissions()
                }
                
                // Notify if anything changed
                if self.accessibilityStatus != previousAccessibility || self.screenRecordingStatus != previousScreenRecording {
                    await MainActor.run {
                        onUpdate()
                    }
                }
                
                // Stop polling if all permissions granted
                if self.hasAllPermissions {
                    print("✅ All permissions granted, stopping poll")
                    break
                }
                
                try? await Task.sleep(nanoseconds: UInt64(interval * 1_000_000_000))
            }
        }
    }
}
