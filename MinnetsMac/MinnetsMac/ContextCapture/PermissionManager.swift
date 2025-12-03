import Foundation
import AppKit
import ScreenCaptureKit

/// Centralized permission management for Minnets
/// Handles checking and requesting Accessibility and Screen Recording permissions
@MainActor
class PermissionManager: ObservableObject {
    static let shared = PermissionManager()
    
    @Published var hasAccessibilityPermission = false
    @Published var hasScreenRecordingPermission = false
    
    // Track if we've already shown alerts this session to avoid nagging
    private var hasShownAccessibilityAlert = false
    private var hasShownScreenRecordingAlert = false
    
    // UserDefaults key to remember if user acknowledged permissions
    private let permissionsAcknowledgedKey = "minnets.permissions.acknowledged"
    
    var hasAllPermissions: Bool {
        hasAccessibilityPermission && hasScreenRecordingPermission
    }
    
    private init() {
        refreshPermissionStatus()
    }
    
    // MARK: - Permission Checking
    
    /// Refreshes the current status of all permissions
    func refreshPermissionStatus() {
        hasAccessibilityPermission = checkAccessibilityPermission()
        hasScreenRecordingPermission = checkScreenRecordingPermission()
        
        print("📋 Permission status - Accessibility: \(hasAccessibilityPermission), Screen Recording: \(hasScreenRecordingPermission)")
    }
    
    /// Checks if accessibility permission is granted
    func checkAccessibilityPermission() -> Bool {
        return AXIsProcessTrusted()
    }
    
    /// Checks if screen recording permission is granted using CGPreflightScreenCaptureAccess
    func checkScreenRecordingPermission() -> Bool {
        // CGPreflightScreenCaptureAccess is the proper way to check screen recording permission
        // It returns true if the app has permission, false otherwise
        return CGPreflightScreenCaptureAccess()
    }
    
    // MARK: - Permission Requesting with Alerts
    
    /// Checks all permissions and shows alerts for any that are missing
    /// Returns true if all permissions are granted
    func checkAndRequestPermissions() async -> Bool {
        refreshPermissionStatus()
        
        // If we already have all permissions, we're done
        if hasAllPermissions {
            print("✅ All permissions already granted")
            return true
        }
        
        // Check if user has already been shown the permission prompts before
        let previouslyAcknowledged = UserDefaults.standard.bool(forKey: permissionsAcknowledgedKey)
        
        if previouslyAcknowledged {
            // User has seen the prompts before - don't nag, just log what's missing
            print("⚠️ Permissions previously acknowledged but still missing:")
            if !hasAccessibilityPermission {
                print("   - Accessibility: NOT GRANTED")
            }
            if !hasScreenRecordingPermission {
                print("   - Screen Recording: NOT GRANTED (may need app restart)")
            }
            return hasAllPermissions
        }
        
        // First time - show prompts
        
        // Check accessibility
        if !hasAccessibilityPermission && !hasShownAccessibilityAlert {
            hasShownAccessibilityAlert = true
            
            // First, try to trigger the system prompt
            triggerAccessibilityPermissionPrompt()
            
            // Wait a moment for system dialog
            try? await Task.sleep(nanoseconds: 500_000_000)
            
            // Re-check
            hasAccessibilityPermission = checkAccessibilityPermission()
            
            if !hasAccessibilityPermission {
                await showAccessibilityPermissionAlert()
                hasAccessibilityPermission = checkAccessibilityPermission()
            }
        }
        
        // Check screen recording
        if !hasScreenRecordingPermission && !hasShownScreenRecordingAlert {
            hasShownScreenRecordingAlert = true
            
            // CGRequestScreenCaptureAccess() returns current state but doesn't always show dialog
            // We need to actually try to capture to trigger the permission dialog
            print("📺 Requesting Screen Recording permission...")
            
            // First try the API call
            let currentlyGranted = CGRequestScreenCaptureAccess()
            
            if !currentlyGranted {
                // Try to trigger by actually attempting a capture (this shows the dialog)
                await triggerScreenRecordingPermissionPrompt()
                
                // Wait for user to potentially grant permission
                try? await Task.sleep(nanoseconds: 1_000_000_000)
                
                // Re-check
                hasScreenRecordingPermission = checkScreenRecordingPermission()
                
                if !hasScreenRecordingPermission {
                    await showScreenRecordingPermissionAlert()
                }
            }
            
            hasScreenRecordingPermission = checkScreenRecordingPermission()
        }
        
        // Mark as acknowledged so we don't nag on future launches
        UserDefaults.standard.set(true, forKey: permissionsAcknowledgedKey)
        
        return hasAllPermissions
    }
    
    /// Force re-check permissions (call after user says they granted them)
    func forceRecheck() {
        refreshPermissionStatus()
        
        if hasAllPermissions {
            print("✅ All permissions now granted!")
        } else {
            if !hasAccessibilityPermission {
                print("⚠️ Still missing Accessibility permission")
            }
            if !hasScreenRecordingPermission {
                print("⚠️ Still missing Screen Recording permission - you may need to restart the app")
            }
        }
    }
    
    /// Reset the acknowledged flag (for testing or if user wants to see prompts again)
    func resetAcknowledgment() {
        UserDefaults.standard.removeObject(forKey: permissionsAcknowledgedKey)
        hasShownAccessibilityAlert = false
        hasShownScreenRecordingAlert = false
    }
    
    // MARK: - Alert Dialogs
    
    /// Shows an alert requesting accessibility permission
    private func showAccessibilityPermissionAlert() async {
        let alert = NSAlert()
        alert.messageText = "Accessibility Permission Required"
        alert.informativeText = "Minnets needs Accessibility permission to read text from your screen and provide contextual suggestions.\n\nClick 'Open System Settings' and enable Minnets in Privacy & Security → Accessibility."
        alert.alertStyle = .warning
        alert.addButton(withTitle: "Open System Settings")
        alert.addButton(withTitle: "I've Already Enabled It")
        alert.addButton(withTitle: "Later")
        
        let response = alert.runModal()
        
        if response == .alertFirstButtonReturn {
            openAccessibilityPreferences()
        } else if response == .alertSecondButtonReturn {
            // User says they've enabled it - recheck
            refreshPermissionStatus()
        }
    }
    
    /// Shows an alert requesting screen recording permission
    private func showScreenRecordingPermissionAlert() async {
        let alert = NSAlert()
        alert.messageText = "Screen Recording Permission Required"
        alert.informativeText = """
Minnets needs Screen Recording permission to capture your screen content.

To enable:
1. Click 'Open System Settings' below
2. Look for 'MinnetsMac' in the list
3. Toggle it ON
4. If MinnetsMac is not listed, click the + button to add it manually

⚠️ After enabling, you MUST quit and reopen Minnets.
"""
        alert.alertStyle = .warning
        alert.addButton(withTitle: "Open System Settings")
        alert.addButton(withTitle: "I've Enabled It - Quit Now")
        alert.addButton(withTitle: "Later")
        
        let response = alert.runModal()
        
        if response == .alertFirstButtonReturn {
            openScreenRecordingPreferences()
        } else if response == .alertSecondButtonReturn {
            // User says they've enabled it - quit so it takes effect
            NSApplication.shared.terminate(nil)
        }
    }
    
    /// Shows an alert explaining that a restart is needed
    private func showRestartRequiredAlert() async {
        let alert = NSAlert()
        alert.messageText = "Restart Required"
        alert.informativeText = "macOS requires apps to be restarted after granting Screen Recording permission.\n\nPlease quit Minnets and reopen it."
        alert.alertStyle = .informational
        alert.addButton(withTitle: "Quit Now")
        alert.addButton(withTitle: "Later")
        
        let response = alert.runModal()
        
        if response == .alertFirstButtonReturn {
            NSApplication.shared.terminate(nil)
        }
    }
    
    // MARK: - Open System Preferences
    
    /// Opens the Accessibility preferences pane
    func openAccessibilityPreferences() {
        let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility")!
        NSWorkspace.shared.open(url)
    }
    
    /// Opens the Screen Recording preferences pane
    func openScreenRecordingPreferences() {
        let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture")!
        NSWorkspace.shared.open(url)
    }
    
    // MARK: - Trigger Permission Prompts
    
    /// Triggers the system accessibility permission prompt
    func triggerAccessibilityPermissionPrompt() {
        let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
        _ = AXIsProcessTrustedWithOptions(options)
    }
    
    /// Triggers the screen recording permission by attempting to capture
    /// This will show the system permission dialog if not already granted
    func triggerScreenRecordingPermissionPrompt() async {
        print("🎬 Triggering screen recording permission prompt...")
        
        do {
            // First get shareable content
            let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
            
            print("   Got \(content.displays.count) displays, \(content.windows.count) windows")
            
            // Actually try to capture something - this should definitely trigger the dialog
            if let display = content.displays.first {
                let filter = SCContentFilter(display: display, excludingWindows: [])
                let config = SCStreamConfiguration()
                config.width = 100
                config.height = 100
                
                // This capture attempt should trigger the permission dialog
                _ = try await SCScreenshotManager.captureImage(contentFilter: filter, configuration: config)
                print("   ✓ Screen capture succeeded - permission granted")
            }
        } catch let error as NSError {
            print("   Screen recording permission trigger failed: \(error.localizedDescription)")
            print("   Error code: \(error.code)")
            
            // Error code -3801 or -3802 typically means no permission
            if error.code == -3801 || error.code == -3802 {
                print("   → This should have added the app to Screen Recording list")
                print("   → Please check System Settings → Screen Recording and enable MinnetsMac")
            }
        }
    }
}

