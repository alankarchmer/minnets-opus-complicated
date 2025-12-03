import SwiftUI

struct SuggestionCard: View {
    let suggestion: Suggestion
    @Environment(\.contextManager) var contextManager
    
    @State private var isExpanded = false
    @State private var isHovered = false
    @State private var showCopiedFeedback = false
    @State private var showSavedFeedback = false
    @State private var isSaving = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Main card content
            VStack(alignment: .leading, spacing: 12) {
                // Header with source badge
                HStack {
                    sourceTag
                    Spacer()
                    scoreIndicator
                }
                
                // Title
                Text(suggestion.title)
                    .font(.system(size: 14, weight: .semibold, design: .rounded))
                    .foregroundColor(.primary)
                    .lineLimit(2)
                
                // Content preview
                Text(suggestion.content)
                    .font(.system(size: 13))
                    .foregroundColor(.secondary)
                    .lineLimit(isExpanded ? nil : 3)
                
                // Expandable reasoning section
                if isExpanded {
                    reasoningSection
                }
                
                // Actions
                actionBar
            }
            .padding(14)
        }
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color(nsColor: .controlBackgroundColor).opacity(0.5))
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .strokeBorder(
                            LinearGradient(
                                colors: isHovered ? [.cyan.opacity(0.5), .purple.opacity(0.5)] : [.clear],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            ),
                            lineWidth: 1
                        )
                )
        )
        .shadow(color: .black.opacity(0.1), radius: 4, y: 2)
        .onHover { hovering in
            isHovered = hovering
            
            // Track hover for feedback
            if hovering {
                contextManager.hoverStarted(suggestion)
            } else {
                contextManager.hoverEnded(suggestion)
            }
        }
    }
    
    // MARK: - Source Tag
    
    private var sourceTag: some View {
        HStack(spacing: 4) {
            Image(systemName: suggestion.source.iconName)
                .font(.system(size: 10, weight: .semibold))
            Text(suggestion.source.displayName)
                .font(.system(size: 10, weight: .semibold))
        }
        .foregroundColor(sourceColor)
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(
            Capsule()
                .fill(sourceColor.opacity(0.15))
        )
    }
    
    private var sourceColor: Color {
        switch suggestion.source {
        case .supermemory: return .cyan
        case .webSearch: return .orange
        case .combined: return .purple
        }
    }
    
    // MARK: - Score Indicator
    
    private var scoreIndicator: some View {
        HStack(spacing: 10) {
            // Relevance
            HStack(spacing: 3) {
                Image(systemName: "target")
                    .font(.system(size: 9))
                    .foregroundColor(.green.opacity(0.7))
                Text(String(format: "%.0f%%", suggestion.relevanceScore * 100))
                    .font(.system(size: 10, weight: .medium, design: .monospaced))
            }
            .foregroundColor(.secondary.opacity(0.8))
            .help("Relevance to your context")
            
            // Novelty
            HStack(spacing: 3) {
                Image(systemName: "sparkle")
                    .font(.system(size: 9))
                    .foregroundColor(.purple.opacity(0.7))
                Text(String(format: "%.0f%%", suggestion.noveltyScore * 100))
                    .font(.system(size: 10, weight: .medium, design: .monospaced))
            }
            .foregroundColor(.secondary.opacity(0.8))
            .help("Novelty - how much new info this adds")
        }
    }
    
    // MARK: - Reasoning Section
    
    private var reasoningSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Divider()
                .background(Color.secondary.opacity(0.2))
            
            HStack(spacing: 6) {
                Image(systemName: "lightbulb.fill")
                    .font(.system(size: 11))
                    .foregroundColor(.yellow)
                Text("Why this?")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(.primary)
            }
            
            Text(suggestion.reasoning)
                .font(.system(size: 12))
                .foregroundColor(.secondary)
                .lineSpacing(3)
        }
        .padding(.top, 4)
    }
    
    // MARK: - Action Bar
    
    private var actionBar: some View {
        HStack(spacing: 16) {
            // Expand/collapse button
            Button(action: toggleExpand) {
                HStack(spacing: 4) {
                    Text(isExpanded ? "Less" : "Why this?")
                        .font(.system(size: 11, weight: .medium))
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .font(.system(size: 9, weight: .semibold))
                }
                .foregroundColor(.cyan)
            }
            .buttonStyle(.plain)
            
            Spacer()
            
            // Save to Supermemory
            Button(action: saveToSupermemory) {
                Group {
                    if isSaving {
                        ProgressView()
                            .scaleEffect(0.6)
                            .frame(width: 14, height: 14)
                    } else if showSavedFeedback {
                        Image(systemName: "checkmark.circle.fill")
                            .font(.system(size: 14))
                            .foregroundColor(.green)
                    } else {
                        Image(systemName: "plus.circle")
                            .font(.system(size: 14))
                            .foregroundColor(.secondary)
                    }
                }
            }
            .buttonStyle(.plain)
            .disabled(isSaving || showSavedFeedback)
            .help(showSavedFeedback ? "Saved to memory!" : "Save to Supermemory")
            
            // Copy content
            Button(action: copyContent) {
                Image(systemName: showCopiedFeedback ? "checkmark.circle.fill" : "doc.on.doc")
                    .font(.system(size: 13))
                    .foregroundColor(showCopiedFeedback ? .green : .secondary)
            }
            .buttonStyle(.plain)
            .help("Copy to clipboard")
            
            // Open source URL (if available)
            if suggestion.sourceUrl != nil {
                Button(action: openSource) {
                    Image(systemName: "arrow.up.right.square")
                        .font(.system(size: 13))
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
                .help("Open source")
            }
            
            // Dismiss
            Button(action: dismiss) {
                Image(systemName: "xmark.circle")
                    .font(.system(size: 13))
                    .foregroundColor(.secondary)
            }
            .buttonStyle(.plain)
            .help("Dismiss")
        }
        .padding(.top, 4)
    }
    
    // MARK: - Actions (with Feedback Tracking)
    
    private func toggleExpand() {
        isExpanded.toggle()
        
        if isExpanded {
            contextManager.expandSuggestion(suggestion)
        }
    }
    
    private func saveToSupermemory() {
        isSaving = true
        contextManager.saveSuggestion(suggestion)
        
        // Show feedback after a brief delay (to simulate save completion)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
            isSaving = false
            showSavedFeedback = true
            
            // Reset after showing feedback
            DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
                showSavedFeedback = false
            }
        }
    }
    
    private func copyContent() {
        contextManager.copySuggestion(suggestion)
        
        // Show feedback
        showCopiedFeedback = true
        
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
            showCopiedFeedback = false
        }
    }
    
    private func dismiss() {
        contextManager.dismissSuggestion(suggestion)
    }
    
    private func openSource() {
        guard let urlString = suggestion.sourceUrl,
              let url = URL(string: urlString) else { return }
        
        contextManager.clickSuggestion(suggestion)
        NSWorkspace.shared.open(url)
    }
}

// MARK: - Preview

#Preview {
    VStack(spacing: 16) {
        SuggestionCard(suggestion: Suggestion(
            id: "1",
            title: "LSTM Networks and Vanishing Gradients",
            content: "Your notes from 2021 mention that LSTM networks struggle with very long sequences due to vanishing gradients. The Transformer architecture you're reading about was designed to solve this exact problem using self-attention mechanisms.",
            reasoning: "You're currently reading about Transformer architecture. This connects to your previous research on sequence models and highlights why Transformers were invented.",
            source: .supermemory,
            relevanceScore: 0.78,
            noveltyScore: 0.85,
            timestamp: Date(),
            sourceUrl: nil
        ))
        
        SuggestionCard(suggestion: Suggestion(
            id: "2",
            title: "Flash Attention 2 Performance Gains",
            content: "Recent paper shows Flash Attention 2 achieves 2x speedup over the original, with memory usage reduced by 50%. Particularly relevant for fine-tuning large models on consumer GPUs.",
            reasoning: "Based on your context about attention mechanisms, this recent optimization technique could be valuable for your work.",
            source: .webSearch,
            relevanceScore: 0.72,
            noveltyScore: 0.92,
            timestamp: Date(),
            sourceUrl: "https://arxiv.org/abs/2307.08691"
        ))
    }
    .padding()
    .frame(width: 380)
    .background(Color(nsColor: .windowBackgroundColor))
}
