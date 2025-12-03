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
    
    nonisolated func applicationDidFinishLaunching(_ notification: Notification) {
        Task { @MainActor in
            setupMenuBar()
            setupPopover()
            setupGlobalShortcut()
            
            // Check permissions before starting context capture
            await checkPermissionsAndStart()
        }
    }
    
    private func checkPermissionsAndStart() async {
        print("\n")
        print("╔═══════════════════════════════════════════╗")
        print("║          MINNETS STARTING UP              ║")
        print("║       (Permission checks DISABLED)        ║")
        print("╚═══════════════════════════════════════════╝")
        
        print("\n🚀 Initializing context manager (skipping permission checks)...")
        
        // Initialize context manager directly - skip all permission prompts
        _ = ContextManager.shared
        
        print("✓ Context manager initialized")
        print("✓ Backend check...")
    }
    
    private func setupMenuBar() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        
        if let button = statusItem?.button {
            // Brain icon with SF Symbols
            let config = NSImage.SymbolConfiguration(pointSize: 16, weight: .medium)
            let image = NSImage(systemSymbolName: "brain.head.profile", accessibilityDescription: "Minnets")
            button.image = image?.withSymbolConfiguration(config)
            button.action = #selector(togglePopover)
            button.target = self
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
        
        if popover.isShown {
            popover.performClose(nil)
        } else {
            popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
            
            // Make the popover the key window
            popover.contentViewController?.view.window?.makeKey()
        }
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
