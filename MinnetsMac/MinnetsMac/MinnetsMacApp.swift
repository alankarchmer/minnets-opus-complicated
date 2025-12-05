import SwiftUI
import AppKit

@main
struct MinnetsMacApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    
    var body: some Scene {
        // Empty scene - we use MenuBarExtra for the UI
        Settings {
            EmptyView()
        }
    }
}

@MainActor
class AppDelegate: NSObject, NSApplicationDelegate {
    private var statusItem: NSStatusItem?
    private var popover: NSPopover?
    private var eventMonitor: Any?
    private var onboardingWindow: NSWindow?
    
    // UserDefaults key for tracking onboarding completion
    private let onboardingCompletedKey = "minnets.onboarding.completed"
    
    nonisolated func applicationDidFinishLaunching(_ notification: Notification) {
        Task { @MainActor in
            setupMenuBar()
            setupPopover()
            setupGlobalShortcut()
            
            // Check if onboarding is needed
            await checkPermissionsAndShowOnboardingIfNeeded()
        }
    }
    
    private func checkPermissionsAndShowOnboardingIfNeeded() async {
        print("\n")
        print("╔═══════════════════════════════════════════╗")
        print("║          MINNETS STARTING UP              ║")
        print("╚═══════════════════════════════════════════╝")
        
        // Refresh permission status
        await PermissionManager.shared.refreshAllPermissions()
        
        let hasAllPermissions = PermissionManager.shared.hasAllPermissions
        let onboardingCompleted = UserDefaults.standard.bool(forKey: onboardingCompletedKey)
        
        print("📋 Permission status:")
        print("   - Accessibility: \(PermissionManager.shared.accessibilityStatus.displayText)")
        print("   - Screen Recording: \(PermissionManager.shared.screenRecordingStatus.displayText)")
        print("   - Onboarding completed: \(onboardingCompleted)")
        
        if !hasAllPermissions || !onboardingCompleted {
            print("🚀 Showing onboarding...")
            showOnboardingWindow()
        } else {
            print("✅ All permissions granted, starting normally")
            startContextCapture()
        }
    }
    
    // MARK: - Onboarding Window
    
    private func showOnboardingWindow() {
        // Close existing window if any
        onboardingWindow?.close()
        
        let onboardingView = OnboardingView(onComplete: { [weak self] in
            self?.completeOnboarding()
        })
        
        let hostingController = NSHostingController(rootView: onboardingView)
        
        let window = NSWindow(contentViewController: hostingController)
        window.title = "Welcome to Minnets"
        window.styleMask = [.titled, .closable]
        window.isReleasedWhenClosed = false
        window.center()
        window.setFrameAutosaveName("OnboardingWindow")
        
        // Make window visible and front
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        
        onboardingWindow = window
    }
    
    private func completeOnboarding() {
        UserDefaults.standard.set(true, forKey: onboardingCompletedKey)
        onboardingWindow?.close()
        onboardingWindow = nil
        
        print("✅ Onboarding completed!")
        startContextCapture()
    }
    
    private func startContextCapture() {
        print("🚀 Initializing context manager...")
        _ = ContextManager.shared
        print("✅ Context manager initialized")
    }
    
    // MARK: - Menu Bar Setup
    
    private func setupMenuBar() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        
        if let button = statusItem?.button {
            // Brain icon with SF Symbols
            let config = NSImage.SymbolConfiguration(pointSize: 16, weight: .medium)
            let image = NSImage(systemSymbolName: "brain.head.profile", accessibilityDescription: "Minnets")
            button.image = image?.withSymbolConfiguration(config)
            button.action = #selector(togglePopover)
            button.target = self
            
            // Add right-click menu
            let menu = NSMenu()
            menu.addItem(NSMenuItem(title: "Show Panel", action: #selector(togglePopover), keyEquivalent: ""))
            menu.addItem(NSMenuItem.separator())
            menu.addItem(NSMenuItem(title: "Setup Permissions...", action: #selector(showPermissionSetup), keyEquivalent: ""))
            menu.addItem(NSMenuItem.separator())
            menu.addItem(NSMenuItem(title: "Quit Minnets", action: #selector(quitApp), keyEquivalent: "q"))
            
            statusItem?.menu = nil // Don't show menu on left click
            button.sendAction(on: [.leftMouseUp, .rightMouseUp])
        }
    }
    
    private func setupPopover() {
        popover = NSPopover()
        popover?.contentSize = NSSize(width: 380, height: 480)
        popover?.behavior = .transient
        popover?.animates = true
        popover?.contentViewController = NSHostingController(
            rootView: FloatingPanelView()
                .environment(\.contextManager, ContextManager.shared)
        )
    }
    
    private func setupGlobalShortcut() {
        // Register global keyboard shortcut: ⌘⇧M
        eventMonitor = NSEvent.addGlobalMonitorForEvents(matching: .keyDown) { [weak self] event in
            // Check for ⌘⇧M
            if event.modifierFlags.contains([.command, .shift]) && event.keyCode == 46 { // 46 = M
                Task { @MainActor in
                    self?.togglePopover()
                }
            }
        }
        
        // Also monitor local events when app is focused
        NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
            if event.modifierFlags.contains([.command, .shift]) && event.keyCode == 46 {
                Task { @MainActor in
                    self?.togglePopover()
                }
                return nil
            }
            return event
        }
    }
    
    @objc private func togglePopover() {
        guard let button = statusItem?.button, let popover = popover else { return }
        
        // Handle right-click to show menu
        if let event = NSApp.currentEvent, event.type == .rightMouseUp {
            showContextMenu()
            return
        }
        
        if popover.isShown {
            popover.performClose(nil)
        } else {
            popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
            
            // Make the popover the key window
            popover.contentViewController?.view.window?.makeKey()
        }
    }
    
    private func showContextMenu() {
        guard let button = statusItem?.button else { return }
        
        let menu = NSMenu()
        menu.addItem(NSMenuItem(title: "Show Panel", action: #selector(showPanel), keyEquivalent: ""))
        menu.addItem(NSMenuItem.separator())
        menu.addItem(NSMenuItem(title: "Setup Permissions...", action: #selector(showPermissionSetup), keyEquivalent: ""))
        menu.addItem(NSMenuItem.separator())
        menu.addItem(NSMenuItem(title: "Quit Minnets", action: #selector(quitApp), keyEquivalent: "q"))
        
        statusItem?.menu = menu
        button.performClick(nil)
        statusItem?.menu = nil
    }
    
    @objc private func showPanel() {
        guard let button = statusItem?.button, let popover = popover else { return }
        popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
        popover.contentViewController?.view.window?.makeKey()
    }
    
    @objc private func showPermissionSetup() {
        // Reset onboarding completed flag and show onboarding again
        UserDefaults.standard.set(false, forKey: onboardingCompletedKey)
        showOnboardingWindow()
    }
    
    @objc private func quitApp() {
        NSApp.terminate(nil)
    }
    
    func updateMenuBarIcon(hasSuggestion: Bool) {
        guard let button = statusItem?.button else { return }
        
        let symbolName = hasSuggestion ? "brain.head.profile.fill" : "brain.head.profile"
        let config = NSImage.SymbolConfiguration(pointSize: 16, weight: .medium)
        var image = NSImage(systemSymbolName: symbolName, accessibilityDescription: "Minnets")
        
        if hasSuggestion {
            // Add accent color when there's a suggestion
            image = image?.withSymbolConfiguration(
                config.applying(NSImage.SymbolConfiguration(paletteColors: [.systemCyan]))
            )
        } else {
            image = image?.withSymbolConfiguration(config)
        }
        
        button.image = image
    }
}

// Environment key for ContextManager
private struct ContextManagerKey: EnvironmentKey {
    @MainActor static var defaultValue: ContextManager { ContextManager.shared }
}

extension EnvironmentValues {
    var contextManager: ContextManager {
        get { self[ContextManagerKey.self] }
        set { self[ContextManagerKey.self] = newValue }
    }
}
