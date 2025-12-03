import SwiftUI

struct FloatingPanelView: View {
    @Environment(\.contextManager) var contextManager
    @State private var suggestions: [Suggestion] = []
    @State private var appState: AppState = .idle
    @State private var isRefreshing = false
    @State private var showPermissionError = false
    @State private var showManualInput = false
    @State private var manualInputText = ""
    
    var body: some View {
        VStack(spacing: 0) {
            // Header
            headerView
            
            Divider()
                .background(Color.white.opacity(0.1))
            
            // Content
            ScrollView {
                LazyVStack(spacing: 12) {
                    if suggestions.isEmpty {
                        emptyStateView
                    } else {
                        // Action bar when we have suggestions
                        suggestionsActionBar
                        
                        ForEach(suggestions) { suggestion in
                            SuggestionCard(suggestion: suggestion)
                        }
                    }
                }
                .padding(16)
            }
            
            Divider()
                .background(Color.white.opacity(0.1))
            
            // Footer
            footerView
        }
        .frame(width: 380, height: 480)
        .background(
            ZStack {
                VisualEffectBlur(material: .hudWindow, blendingMode: .behindWindow)
                
                // Subtle gradient overlay
                LinearGradient(
                    colors: [
                        Color.cyan.opacity(0.03),
                        Color.purple.opacity(0.03),
                        Color.cyan.opacity(0.03)
                    ],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            }
        )
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .onAppear {
            loadSuggestions()
        }
        .onReceive(NotificationCenter.default.publisher(for: .newSuggestionsAvailable)) { notification in
            if let newSuggestions = notification.object as? [Suggestion] {
                self.suggestions = newSuggestions
                self.appState = .hasSuggestions
                self.showPermissionError = false
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: .captureFailedNoPermissions)) { _ in
            self.isRefreshing = false
            self.showPermissionError = true
            self.appState = .error("No permissions")
        }
        .sheet(isPresented: $showManualInput) {
            manualInputSheet
        }
    }
    
    // MARK: - Header
    
    private var headerView: some View {
        HStack {
            // Logo and title
            HStack(spacing: 8) {
                Image(systemName: "brain.head.profile")
                    .font(.system(size: 20, weight: .semibold))
                    .foregroundStyle(
                        LinearGradient(
                            colors: [Color.cyan, Color.purple],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                
                Text("Minnets")
                    .font(.system(size: 16, weight: .semibold, design: .rounded))
                    .foregroundColor(.primary)
            }
            
            Spacer()
            
            // Status indicator
            statusIndicator
            
            // Refresh button
            Button(action: refreshSuggestions) {
                Image(systemName: "arrow.clockwise")
                    .font(.system(size: 14, weight: .medium))
                    .foregroundColor(.secondary)
            }
            .buttonStyle(.plain)
            .disabled(isRefreshing)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }
    
    private var statusIndicator: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(statusColor)
                .frame(width: 8, height: 8)
            
            Text(appState.statusText)
                .font(.system(size: 11, weight: .medium))
                .foregroundColor(.secondary)
        }
    }
    
    private var statusColor: Color {
        switch appState {
        case .idle: return .gray
        case .capturing: return .yellow
        case .analyzing: return .cyan
        case .hasSuggestions: return .green
        case .error: return .red
        }
    }
    
    // MARK: - Empty State
    
    private var emptyStateView: some View {
        VStack(spacing: 20) {
            Spacer()
            
            if isRefreshing {
                // Loading state
                ProgressView()
                    .scaleEffect(1.5)
                    .frame(width: 48, height: 48)
                
                VStack(spacing: 8) {
                    Text("Analyzing your screen...")
                        .font(.system(size: 17, weight: .semibold, design: .rounded))
                        .foregroundColor(.primary)
                    
                    Text("Searching for relevant insights.\nThis may take 10-15 seconds.")
                        .font(.system(size: 13))
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                        .lineSpacing(4)
                }
            } else if showPermissionError {
                // Permission error state
                Image(systemName: "lock.shield")
                    .font(.system(size: 48, weight: .light))
                    .foregroundColor(.orange)
                
                VStack(spacing: 8) {
                    Text("Permissions Required")
                        .font(.system(size: 17, weight: .semibold, design: .rounded))
                        .foregroundColor(.primary)
                    
                    Text("Minnets needs Accessibility and Screen Recording permissions to capture your screen.")
                        .font(.system(size: 13))
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                        .lineSpacing(4)
                }
                
                Button(action: openPermissionSettings) {
                    HStack(spacing: 6) {
                        Image(systemName: "gear")
                        Text("Open Settings")
                    }
                    .font(.system(size: 13, weight: .medium))
                    .foregroundColor(.white)
                    .padding(.horizontal, 20)
                    .padding(.vertical, 10)
                    .background(Color.orange)
                    .clipShape(Capsule())
                }
                .buttonStyle(.plain)
                
            } else {
                // Brain icon
                Image(systemName: "brain.head.profile")
                    .font(.system(size: 48, weight: .light))
                    .foregroundStyle(
                        LinearGradient(
                            colors: [.cyan.opacity(0.7), .purple.opacity(0.7)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                
                VStack(spacing: 8) {
                    Text("No insights yet")
                        .font(.system(size: 17, weight: .semibold, design: .rounded))
                        .foregroundColor(.primary)
                    
                    Text("Minnets is watching your screen.\nRelevant insights will appear here.")
                        .font(.system(size: 13))
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                        .lineSpacing(4)
                }
            }
            
            HStack(spacing: 12) {
                Button(action: refreshSuggestions) {
                    HStack(spacing: 6) {
                        if isRefreshing {
                            ProgressView()
                                .scaleEffect(0.7)
                                .frame(width: 14, height: 14)
                            Text("Analyzing...")
                        } else {
                            Image(systemName: "arrow.clockwise")
                            Text("Check Now")
                        }
                    }
                    .font(.system(size: 13, weight: .medium))
                    .foregroundColor(.white)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .background(
                        LinearGradient(
                            colors: isRefreshing ? [.gray, .gray.opacity(0.8)] : [.cyan, .purple],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .clipShape(Capsule())
                }
                .buttonStyle(.plain)
                .disabled(isRefreshing)
                
                Button(action: { showManualInput = true }) {
                    HStack(spacing: 6) {
                        Image(systemName: "doc.on.clipboard")
                        Text("Paste")
                    }
                    .font(.system(size: 13, weight: .medium))
                    .foregroundColor(.primary)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .background(Color.secondary.opacity(0.15))
                    .clipShape(Capsule())
                }
                .buttonStyle(.plain)
            }
            
            Spacer()
        }
        .frame(maxWidth: .infinity, minHeight: 280)
    }
    
    // MARK: - Suggestions Action Bar
    
    private var suggestionsActionBar: some View {
        HStack(spacing: 10) {
            // Paste new context button
            Button(action: { showManualInput = true }) {
                HStack(spacing: 5) {
                    Image(systemName: "doc.on.clipboard")
                        .font(.system(size: 11))
                    Text("New Analysis")
                        .font(.system(size: 11, weight: .medium))
                }
                .foregroundColor(.primary.opacity(0.8))
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(Color.secondary.opacity(0.12))
                .clipShape(Capsule())
            }
            .buttonStyle(.plain)
            
            Spacer()
            
            // Clear all button
            Button(action: clearAllSuggestions) {
                HStack(spacing: 4) {
                    Image(systemName: "xmark")
                        .font(.system(size: 9, weight: .semibold))
                    Text("Clear")
                        .font(.system(size: 11, weight: .medium))
                }
                .foregroundColor(.secondary)
                .padding(.horizontal, 8)
                .padding(.vertical, 5)
            }
            .buttonStyle(.plain)
        }
        .padding(.bottom, 4)
    }
    
    private func clearAllSuggestions() {
        withAnimation(.easeOut(duration: 0.2)) {
            contextManager.clearSuggestions()
            suggestions = []
            appState = .idle
        }
    }
    
    // MARK: - Footer
    
    private var footerView: some View {
        HStack {
            // Current context preview
            if let currentApp = contextManager.currentAppName {
                HStack(spacing: 6) {
                    Image(systemName: "eye")
                        .font(.system(size: 11))
                    Text("Watching: \(currentApp)")
                        .font(.system(size: 11))
                }
                .foregroundColor(.secondary)
            }
            
            Spacer()
            
            // Keyboard shortcut hint
            HStack(spacing: 4) {
                Text("⌘⇧M")
                    .font(.system(size: 10, weight: .medium, design: .monospaced))
                    .foregroundColor(.secondary)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Color.secondary.opacity(0.15))
                    .clipShape(RoundedRectangle(cornerRadius: 4))
                
                Text("to toggle")
                    .font(.system(size: 10))
                    .foregroundColor(.secondary.opacity(0.7))
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
    }
    
    // MARK: - Actions
    
    private func loadSuggestions() {
        suggestions = contextManager.currentSuggestions
        appState = suggestions.isEmpty ? .idle : .hasSuggestions
    }
    
    private func refreshSuggestions() {
        guard !isRefreshing else { return }
        
        isRefreshing = true
        appState = .capturing
        showPermissionError = false
        
        print("🔘 Check Now button pressed - starting analysis...")
        
        Task {
            // Use force analyze to bypass interruptibility checks when user explicitly clicks
            await contextManager.forceCaptureAndAnalyze()
            
            print("🔘 Analysis complete - loading suggestions...")
            isRefreshing = false
            loadSuggestions()
            
            if suggestions.isEmpty {
                print("🔘 No suggestions returned")
            } else {
                print("🔘 Got \(suggestions.count) suggestions!")
            }
        }
    }
    
    private func openPermissionSettings() {
        // Open Privacy & Security settings
        if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy") {
            NSWorkspace.shared.open(url)
        }
    }
    
    // MARK: - Manual Input Sheet
    
    private var manualInputSheet: some View {
        VStack(spacing: 16) {
            HStack {
                Text("Paste Your Context")
                    .font(.headline)
                Spacer()
                Button("Cancel") {
                    showManualInput = false
                    manualInputText = ""
                }
                .buttonStyle(.plain)
            }
            
            Text("Paste text, a URL, or any content you want Minnets to analyze.")
                .font(.caption)
                .foregroundColor(.secondary)
            
            TextEditor(text: $manualInputText)
                .font(.system(size: 12, design: .monospaced))
                .frame(minHeight: 150)
                .border(Color.secondary.opacity(0.3), width: 1)
            
            HStack {
                Button("Paste from Clipboard") {
                    if let clipboardText = NSPasteboard.general.string(forType: .string) {
                        manualInputText = clipboardText
                    }
                }
                .buttonStyle(.plain)
                .foregroundColor(.secondary)
                
                Spacer()
                
                Button(action: analyzeManualInput) {
                    HStack {
                        Image(systemName: "sparkles")
                        Text("Analyze")
                    }
                    .padding(.horizontal, 20)
                    .padding(.vertical, 8)
                    .background(Color.accentColor)
                    .foregroundColor(.white)
                    .clipShape(Capsule())
                }
                .buttonStyle(.plain)
                .disabled(manualInputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
        }
        .padding(20)
        .frame(width: 400, height: 300)
    }
    
    private func analyzeManualInput() {
        let text = manualInputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        
        showManualInput = false
        isRefreshing = true
        appState = .analyzing
        
        print("📋 Analyzing manually pasted context (\(text.count) chars)")
        
        Task {
            await contextManager.analyzeText(text, appName: "Manual Input")
            
            isRefreshing = false
            loadSuggestions()
            manualInputText = ""
        }
    }
}

// MARK: - Visual Effect Blur

struct VisualEffectBlur: NSViewRepresentable {
    let material: NSVisualEffectView.Material
    let blendingMode: NSVisualEffectView.BlendingMode
    
    func makeNSView(context: Context) -> NSVisualEffectView {
        let view = NSVisualEffectView()
        view.material = material
        view.blendingMode = blendingMode
        view.state = .active
        return view
    }
    
    func updateNSView(_ nsView: NSVisualEffectView, context: Context) {
        nsView.material = material
        nsView.blendingMode = blendingMode
    }
}

// MARK: - Notification Extension

extension Notification.Name {
    static let newSuggestionsAvailable = Notification.Name("newSuggestionsAvailable")
    static let captureFailedNoPermissions = Notification.Name("captureFailedNoPermissions")
}

#Preview {
    FloatingPanelView()
        .frame(width: 380, height: 480)
}
