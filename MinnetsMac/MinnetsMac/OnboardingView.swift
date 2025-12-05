import SwiftUI

/// Onboarding view that guides users through granting required permissions
struct OnboardingView: View {
    @ObservedObject private var permissionManager = PermissionManager.shared
    @State private var currentStep: OnboardingStep = .welcome
    @State private var pollingTask: Task<Void, Never>?
    
    var onComplete: () -> Void
    
    enum OnboardingStep: Int, CaseIterable {
        case welcome
        case accessibility
        case screenRecording
        case complete
        
        var title: String {
            switch self {
            case .welcome: return "Welcome to Minnets"
            case .accessibility: return "Accessibility Permission"
            case .screenRecording: return "Screen Recording Permission"
            case .complete: return "You're All Set!"
            }
        }
    }
    
    var body: some View {
        VStack(spacing: 0) {
            // Progress indicator
            progressBar
                .padding(.top, 20)
                .padding(.horizontal, 24)
            
            // Main content
            Group {
                switch currentStep {
                case .welcome:
                    welcomeView
                case .accessibility:
                    accessibilityView
                case .screenRecording:
                    screenRecordingView
                case .complete:
                    completeView
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .padding(.horizontal, 32)
            
            // Navigation buttons
            navigationButtons
                .padding(.horizontal, 32)
                .padding(.bottom, 24)
        }
        .frame(width: 520, height: 460)
        .background(Color(nsColor: .windowBackgroundColor))
        .onAppear {
            startPolling()
        }
        .onDisappear {
            pollingTask?.cancel()
        }
    }
    
    // MARK: - Progress Bar
    
    private var progressBar: some View {
        HStack(spacing: 8) {
            ForEach(OnboardingStep.allCases, id: \.rawValue) { step in
                if step != .welcome {
                    Capsule()
                        .fill(step.rawValue <= currentStep.rawValue ? Color.accentColor : Color.secondary.opacity(0.3))
                        .frame(height: 4)
                }
            }
        }
    }
    
    // MARK: - Welcome View
    
    private var welcomeView: some View {
        VStack(spacing: 24) {
            Spacer()
            
            Image(systemName: "brain.head.profile")
                .font(.system(size: 64))
                .foregroundStyle(.linearGradient(
                    colors: [.cyan, .blue],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                ))
            
            VStack(spacing: 12) {
                Text("Welcome to Minnets")
                    .font(.system(size: 28, weight: .bold))
                
                Text("Your intelligent memory assistant that surfaces relevant information based on what you're working on.")
                    .font(.body)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: 380)
            }
            
            VStack(alignment: .leading, spacing: 16) {
                permissionPreviewRow(
                    icon: "hand.raised.fill",
                    title: "Accessibility",
                    description: "Read text from your screen"
                )
                
                permissionPreviewRow(
                    icon: "rectangle.dashed.badge.record",
                    title: "Screen Recording",
                    description: "Capture visual content"
                )
            }
            .padding(.top, 16)
            
            Spacer()
        }
    }
    
    private func permissionPreviewRow(icon: String, title: String, description: String) -> some View {
        HStack(spacing: 16) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundColor(.accentColor)
                .frame(width: 32)
            
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.headline)
                Text(description)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
        }
        .padding(.horizontal, 40)
    }
    
    // MARK: - Accessibility View
    
    private var accessibilityView: some View {
        permissionStepView(
            icon: "hand.raised.fill",
            iconColor: .blue,
            title: "Accessibility Permission",
            description: "Minnets needs Accessibility access to read text content from applications. This allows us to understand what you're working on and provide relevant suggestions.",
            status: permissionManager.accessibilityStatus,
            onRequestPermission: {
                permissionManager.requestAccessibilityPermission()
            },
            onOpenSettings: {
                permissionManager.openAccessibilitySettings()
            }
        )
    }
    
    // MARK: - Screen Recording View
    
    private var screenRecordingView: some View {
        permissionStepView(
            icon: "rectangle.dashed.badge.record",
            iconColor: .purple,
            title: "Screen Recording Permission",
            description: "Minnets uses screen capture to read visual content when text isn't directly accessible. Your screen content is analyzed locally and never stored or transmitted.",
            status: permissionManager.screenRecordingStatus,
            onRequestPermission: {
                permissionManager.requestScreenRecordingPermission()
            },
            onOpenSettings: {
                permissionManager.openScreenRecordingSettings()
            },
            additionalNote: "After enabling, you may need to restart Minnets for the permission to take effect."
        )
    }
    
    private func permissionStepView(
        icon: String,
        iconColor: Color,
        title: String,
        description: String,
        status: PermissionManager.PermissionStatus,
        onRequestPermission: @escaping () -> Void,
        onOpenSettings: @escaping () -> Void,
        additionalNote: String? = nil
    ) -> some View {
        VStack(spacing: 24) {
            Spacer()
            
            // Icon with status indicator
            ZStack(alignment: .bottomTrailing) {
                Image(systemName: icon)
                    .font(.system(size: 56))
                    .foregroundColor(iconColor)
                
                Image(systemName: status.symbolName)
                    .font(.system(size: 24))
                    .foregroundColor(Color(nsColor: status.color))
                    .background(
                        Circle()
                            .fill(Color(nsColor: .windowBackgroundColor))
                            .frame(width: 28, height: 28)
                    )
                    .offset(x: 8, y: 8)
            }
            
            VStack(spacing: 12) {
                Text(title)
                    .font(.system(size: 24, weight: .bold))
                
                Text(description)
                    .font(.body)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: 400)
            }
            
            // Status pill
            HStack(spacing: 8) {
                Circle()
                    .fill(Color(nsColor: status.color))
                    .frame(width: 8, height: 8)
                
                Text("Status: \(status.displayText)")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .background(Color.secondary.opacity(0.1))
            .cornerRadius(16)
            
            // Action buttons
            VStack(spacing: 12) {
                if status != .granted {
                    Button(action: onRequestPermission) {
                        Label("Grant Permission", systemImage: "checkmark.shield")
                            .frame(maxWidth: 200)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    
                    Button(action: onOpenSettings) {
                        Label("Open System Settings", systemImage: "gear")
                    }
                    .buttonStyle(.borderless)
                    .foregroundColor(.accentColor)
                }
            }
            
            if let note = additionalNote, status != .granted {
                Text(note)
                    .font(.caption)
                    .foregroundColor(.orange)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: 360)
            }
            
            Spacer()
        }
    }
    
    // MARK: - Complete View
    
    private var completeView: some View {
        VStack(spacing: 24) {
            Spacer()
            
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 72))
                .foregroundStyle(.linearGradient(
                    colors: [.green, .cyan],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                ))
            
            VStack(spacing: 12) {
                Text("You're All Set!")
                    .font(.system(size: 28, weight: .bold))
                
                Text("Minnets is now ready to help you. It will run in the background and provide relevant suggestions based on what you're working on.")
                    .font(.body)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: 380)
            }
            
            VStack(spacing: 8) {
                HStack {
                    Image(systemName: "menubar.rectangle")
                        .foregroundColor(.accentColor)
                    Text("Look for the brain icon in your menu bar")
                        .font(.subheadline)
                }
                
                HStack {
                    Image(systemName: "command")
                        .foregroundColor(.accentColor)
                    Text("Press ⌘⇧M to quickly toggle the panel")
                        .font(.subheadline)
                }
            }
            .foregroundColor(.secondary)
            .padding(.top, 8)
            
            Spacer()
        }
    }
    
    // MARK: - Navigation Buttons
    
    private var navigationButtons: some View {
        HStack {
            // Back button
            if currentStep != .welcome && currentStep != .complete {
                Button("Back") {
                    withAnimation {
                        goToPreviousStep()
                    }
                }
                .buttonStyle(.borderless)
            }
            
            Spacer()
            
            // Next/Continue button
            Button(action: {
                withAnimation {
                    goToNextStep()
                }
            }) {
                Text(nextButtonTitle)
                    .frame(minWidth: 100)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(!canProceed)
        }
    }
    
    private var nextButtonTitle: String {
        switch currentStep {
        case .welcome: return "Get Started"
        case .accessibility, .screenRecording:
            return canProceed ? "Continue" : "Grant Permission to Continue"
        case .complete: return "Start Using Minnets"
        }
    }
    
    private var canProceed: Bool {
        switch currentStep {
        case .welcome: return true
        case .accessibility: return permissionManager.accessibilityStatus.isGranted
        case .screenRecording: return permissionManager.screenRecordingStatus.isGranted
        case .complete: return true
        }
    }
    
    // MARK: - Navigation
    
    private func goToNextStep() {
        switch currentStep {
        case .welcome:
            currentStep = .accessibility
        case .accessibility:
            if permissionManager.accessibilityStatus.isGranted {
                currentStep = .screenRecording
            }
        case .screenRecording:
            if permissionManager.screenRecordingStatus.isGranted {
                currentStep = .complete
            }
        case .complete:
            onComplete()
        }
    }
    
    private func goToPreviousStep() {
        switch currentStep {
        case .accessibility:
            currentStep = .welcome
        case .screenRecording:
            currentStep = .accessibility
        default:
            break
        }
    }
    
    // MARK: - Polling
    
    private func startPolling() {
        pollingTask = permissionManager.startPollingForPermissionChanges { [self] in
            // Auto-advance if permission was granted while on that step
            if currentStep == .accessibility && permissionManager.accessibilityStatus.isGranted {
                withAnimation(.easeInOut(duration: 0.3)) {
                    currentStep = .screenRecording
                }
            } else if currentStep == .screenRecording && permissionManager.screenRecordingStatus.isGranted {
                withAnimation(.easeInOut(duration: 0.3)) {
                    currentStep = .complete
                }
            }
        }
    }
}

#Preview {
    OnboardingView(onComplete: {})
}

