/**
 * RealtyAssistant Chat Widget
 * 
 * A beautiful, embeddable chat widget for real estate lead qualification.
 * Supports both text chat and voice interaction.
 * 
 * Usage:
 *   <script src="widget.js"></script>
 *   <script>
 *     RealtyAssistantWidget.init({
 *       apiUrl: 'http://localhost:8080',
 *       primaryColor: '#667eea'
 *     });
 *   </script>
 */

(function () {
    'use strict';

    // Configuration
    const DEFAULT_CONFIG = {
        apiUrl: '.', // Relative path for flexibility (supports subdirectories/proxies)
        primaryColor: '#325998', // Brand Blue
        secondaryColor: '#984275', // Brand Magenta
        position: 'bottom-right',
        greeting: "Hello! 👋 I'm your RealtyAssistant. I can help you find the perfect property. What's your name?",
        botName: 'RealtyAssistant',
        botAvatar: '🏠'
    };

    // State management
    const state = {
        isOpen: false,
        isTyping: false,
        isRecording: false,
        messages: [],
        sessionId: null,
        currentStage: 'greeting',
        collectedData: {},
        mediaRecorder: null,
        audioChunks: [],
        config: { ...DEFAULT_CONFIG }
    };

    // Conversation stages matching realtyassistant.in form EXACTLY
    // NEW FLOW: Name -> Search Fields -> Show Results -> Ask Consent -> If Yes: Budget/Phone/Email -> Complete
    const CONVERSATION_FLOW = {
        greeting: {
            question: null, // Initial greeting is in config
            field: 'name',
            next: 'location'
        },
        location: {
            question: "Nice to meet you, {name}! 🎉 Which city are you looking for property in?",
            field: 'location',
            // All 16 cities from the form - EXACT ORDER
            options: [
                'Noida', 'Greater Noida', 'Greater Noida West', 'Lucknow',
                'Gurugram', 'Ghaziabad', 'Pune', 'Thane', 'Mumbai',
                'Navi Mumbai', 'Dehradun', 'Agra', 'Vrindavan', 'Delhi',
                'Varanasi', 'Bengaluru'
            ],
            next: 'property_category'
        },
        property_category: {
            question: "Got it! What category of property?",
            field: 'property_category',
            // Exact match to form
            options: ['Residential Properties', 'Commercial Properties'],
            next: 'property_type'
        },
        property_type: {
            question: null, // Dynamic based on property category
            field: 'property_type',
            next: 'bedroom'
        },
        bedroom: {
            question: "And how many bedrooms do you need?",
            field: 'bedroom',
            // Exact match to form
            options: ['1 BHK', '2 BHK', '3 BHK', '4 BHK', '5 BHK', 'Studio'],
            next: 'search_and_show' // Trigger search after possession
        },
        // After search, ask if user wants to be contacted
        search_and_show: {
            question: null, // Search results shown programmatically
            field: null,
            next: 'consent_after_search'
        },
        consent_after_search: {
            question: "Would you like our property experts to call you with more relevant information and personalized recommendations? 📞",
            field: 'consent',
            options: ['Yes, call me!', 'No, thanks'],
            next: null // Dynamic - handled in code
        },
        // Only if user consents
        budget: {
            question: "Great! 💰 What's your budget range? (e.g., 50 lakhs, 1-2 crore, etc.)",
            field: 'budget',
            next: 'phone'
        },
        phone: {
            question: "Perfect! 📱 What's your phone number?",
            field: 'phone',
            next: 'email'
        },
        email: {
            question: "And your email? We'll send you property alerts! 📧",
            field: 'email',
            next: 'complete'
        },
        complete: {
            question: null,
            field: null,
            next: null
        },
        // If user declines
        thank_you: {
            question: null, // Handled in code
            field: null,
            next: null
        }
    };

    // CSS Styles
    const styles = `
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        #realty-widget-container * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }

        /* Chat Bubble Button - Larger and more prominent */
        .realty-chat-bubble {
            position: fixed;
            bottom: 28px;
            right: 28px;
            width: 68px;
            height: 68px;
            border-radius: 50%;
            background: linear-gradient(145deg, var(--primary-color) 0%, var(--secondary-color) 100%);
            box-shadow: 0 8px 32px rgba(102, 126, 234, 0.45), 
                        0 4px 12px rgba(102, 126, 234, 0.25);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            z-index: 999998;
            border: none;
        }

        .realty-chat-bubble:hover {
            transform: scale(1.12) translateY(-3px);
            box-shadow: 0 14px 45px rgba(102, 126, 234, 0.55),
                        0 8px 20px rgba(102, 126, 234, 0.3);
        }

        .realty-chat-bubble.open {
            transform: rotate(45deg);
        }

        .realty-chat-bubble svg {
            width: 30px;
            height: 30px;
            fill: white;
            transition: transform 0.4s ease;
            filter: drop-shadow(0 2px 4px rgba(0,0,0,0.1));
        }

        .realty-chat-bubble.open svg {
            transform: rotate(-45deg);
        }

        /* Notification Badge - Animated */
        .realty-notification-badge {
            position: absolute;
            top: -5px;
            right: -5px;
            width: 24px;
            height: 24px;
            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: 700;
            color: white;
            animation: bounce 1.2s infinite;
            box-shadow: 0 2px 8px rgba(239, 68, 68, 0.5);
        }

        @keyframes bounce {
            0%, 100% { transform: translateY(0) scale(1); }
            50% { transform: translateY(-5px) scale(1.05); }
        }

        /* Chat Window - Larger and more spacious */
        .realty-chat-window {
            position: fixed;
            bottom: 110px;
            right: 28px;
            width: 420px;
            height: 650px;
            max-height: calc(100vh - 150px);
            background: #ffffff;
            border-radius: 28px;
            box-shadow: 0 25px 80px rgba(0, 0, 0, 0.18),
                        0 10px 30px rgba(0, 0, 0, 0.08);
            display: flex;
            flex-direction: column;
            overflow: hidden;
            z-index: 999999;
            opacity: 0;
            visibility: hidden;
            transform: translateY(25px) scale(0.92);
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .realty-chat-window.open {
            opacity: 1;
            visibility: visible;
            transform: translateY(0) scale(1);
        }

        @media (max-width: 480px) {
            .realty-chat-window {
                width: calc(100vw - 16px);
                height: calc(100vh - 90px);
                right: 8px;
                bottom: 82px;
                border-radius: 24px;
            }
        }

        /* Chat Header - Premium gradient */
        .realty-chat-header {
            background: linear-gradient(145deg, var(--primary-color) 0%, var(--secondary-color) 100%);
            padding: 22px 26px;
            display: flex;
            align-items: center;
            gap: 16px;
            box-shadow: 0 4px 20px rgba(102, 126, 234, 0.3);
            position: relative;
            z-index: 1;
        }

        .realty-avatar {
            width: 52px;
            height: 52px;
            background: rgba(255, 255, 255, 0.22);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 26px;
            backdrop-filter: blur(8px);
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }

        .realty-header-info {
            flex: 1;
        }

        .realty-header-name {
            color: white;
            font-size: 1.15rem;
            font-weight: 700;
            letter-spacing: 0.2px;
            text-shadow: 0 1px 2px rgba(0,0,0,0.1);
        }

        .realty-header-status {
            color: rgba(255, 255, 255, 0.9);
            font-size: 0.9rem;
            display: flex;
            align-items: center;
            gap: 8px;
            margin-top: 3px;
        }

        .realty-status-dot {
            width: 10px;
            height: 10px;
            background: linear-gradient(135deg, #4ade80 0%, #22c55e 100%);
            border-radius: 50%;
            box-shadow: 0 0 8px rgba(34, 197, 94, 0.6);
            animation: pulse-status 2s infinite;
        }

        @keyframes pulse-status {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }

        .realty-header-actions {
            display: flex;
            gap: 10px;
        }

        .realty-header-btn {
            width: 40px;
            height: 40px;
            background: rgba(255, 255, 255, 0.18);
            border: none;
            border-radius: 50%;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.25s;
            backdrop-filter: blur(4px);
        }

        .realty-header-btn:hover {
            background: rgba(255, 255, 255, 0.3);
            transform: scale(1.08);
        }

        .realty-header-btn svg {
            width: 20px;
            height: 20px;
            fill: white;
        }

        /* Messages Area - More spacious */
        .realty-messages {
            flex: 1;
            overflow-y: auto;
            padding: 24px;
            display: flex;
            flex-direction: column;
            gap: 20px;
            background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
        }

        .realty-messages::-webkit-scrollbar {
            width: 7px;
        }

        .realty-messages::-webkit-scrollbar-track {
            background: transparent;
        }

        .realty-messages::-webkit-scrollbar-thumb {
            background: linear-gradient(180deg, #cbd5e1 0%, #94a3b8 100%);
            border-radius: 4px;
        }

        .realty-messages::-webkit-scrollbar-thumb:hover {
            background: #94a3b8;
        }

        /* Message Bubbles - Larger padding and more modern */
        .realty-message {
            display: flex;
            gap: 14px;
            max-width: 88%;
            animation: messageIn 0.35s ease;
        }

        @keyframes messageIn {
            from {
                opacity: 0;
                transform: translateY(15px) scale(0.98);
            }
            to {
                opacity: 1;
                transform: translateY(0) scale(1);
            }
        }

        .realty-message.bot {
            align-self: flex-start;
            padding: 10px 18px !important;
        }

        .realty-message.user {
            align-self: flex-end;
            flex-direction: row-reverse;
        }

        .realty-message-avatar {
            width: 38px;
            height: 38px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 16px;
            flex-shrink: 0;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .realty-message.bot .realty-message-avatar {
            background: linear-gradient(145deg, var(--primary-color) 0%, var(--secondary-color) 100%);
        }

        .realty-message.user .realty-message-avatar {
            background: linear-gradient(145deg, #e2e8f0 0%, #cbd5e1 100%);
        }

        .realty-message-content {
            background: white !important;
            padding: 16px 20px !important;
            border-radius: 22px !important;
            box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06) !important;
            font-size: 0.98rem !important;
            line-height: 1.65 !important;
            color: #334155 !important;
            max-width: 100% !important;
            word-wrap: break-word !important;
            overflow-wrap: break-word !important;
        }

        .realty-message.user .realty-message-content {
            background: linear-gradient(145deg, var(--primary-color) 0%, var(--secondary-color) 100%) !important;
            color: white !important;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3) !important;
        }

        .realty-message.bot .realty-message-content {
            border-bottom-left-radius: 6px !important;
        }

        .realty-message.user .realty-message-content {
            border-bottom-right-radius: 6px !important;
        }

        /* Message Wrapper - Contains content and options */
        .realty-message-wrapper {
            display: flex;
            flex-direction: column;
            gap: 12px;
            max-width: 100%;
            min-width: 0;
        }

        /* Quick Reply Options - More attractive */
        .realty-quick-replies {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 4px;
            padding: 5px !important;
        }

        .realty-quick-reply {
            background: linear-gradient(145deg, #ffffff 0%, #f8fafc 100%);
            border: 2px solid var(--primary-color);
            color: var(--primary-color);
            padding: 10px 18px !important;
            border-radius: 22px;
            font-size: 0.88rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 2px 8px rgba(102, 126, 234, 0.12);
            white-space: nowrap;
            line-height: 1.2;
        }

        .realty-quick-reply:hover {
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
            color: white;
            border-color: var(--primary-color);
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(102, 126, 234, 0.35);
        }

        .realty-quick-reply:active {
            transform: translateY(0);
            box-shadow: 0 2px 6px rgba(102, 126, 234, 0.2);
        }

        /* Typing Indicator */
        .realty-typing {
            display: flex;
            gap: 12px;
            align-self: flex-start;
            padding: 4px 0;
        }

        .realty-typing-dots {
            display: flex;
            gap: 5px;
            padding: 18px 22px !important;
            background: white;
            border-radius: 24px;
            box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
        }

        .realty-typing-dot {
            width: 10px;
            height: 10px;
            background: linear-gradient(135deg, #94a3b8 0%, #64748b 100%);
            border-radius: 50%;
            animation: typingDot 1.4s infinite;
        }

        .realty-typing-dot:nth-child(2) { animation-delay: 0.2s; }
        .realty-typing-dot:nth-child(3) { animation-delay: 0.4s; }

        @keyframes typingDot {
            0%, 60%, 100% { transform: translateY(0); }
            30% { transform: translateY(-10px); }
        }

        /* Input Area - More spacious */
        .realty-input-area {
            padding: 20px 24px;
            background: linear-gradient(180deg, rgba(255,255,255,0.95) 0%, #ffffff 100%);
            border-top: 1px solid rgba(226, 232, 240, 0.8);
            display: flex;
            align-items: center;
            gap: 14px;
            backdrop-filter: blur(10px);
        }

        .realty-input-wrapper {
            flex: 1;
            display: flex;
            align-items: center;
            background: linear-gradient(145deg, #f8fafc 0%, #f1f5f9 100%);
            border-radius: 28px;
            padding: 6px 8px 6px 20px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            border: 2px solid transparent;
        }

        .realty-input-wrapper:focus-within {
            border-color: var(--primary-color);
            box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.15);
            background: white;
        }

        .realty-input {
            flex: 1;
            border: none;
            background: transparent;
            font-size: 1rem;
            padding: 10px 10px !important;
            outline: none;
            color: #1e293b;
            font-weight: 400;
        }

        .realty-input::placeholder {
            color: #94a3b8;
            font-weight: 400;
        }

        .realty-send-btn {
            width: 48px;
            height: 48px;
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
            border: none;
            border-radius: 50%;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.35);
        }

        .realty-send-btn:hover:not(:disabled) {
            transform: scale(1.08) translateY(-2px);
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.5);
        }

        .realty-send-btn:active:not(:disabled) {
            transform: scale(0.95);
        }

        .realty-send-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            box-shadow: none;
        }

        .realty-send-btn svg {
            width: 22px;
            height: 22px;
            fill: white;
        }

        /* Voice Button */
        .realty-voice-btn {
            width: 48px;
            height: 48px;
            background: linear-gradient(145deg, #f8fafc 0%, #e2e8f0 100%);
            border: none;
            border-radius: 50%;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        }

        .realty-voice-btn:hover {
            background: linear-gradient(145deg, #e2e8f0 0%, #cbd5e1 100%);
            transform: scale(1.05);
        }

        .realty-voice-btn.recording {
            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
            animation: pulse-record 1.5s infinite;
            box-shadow: 0 4px 20px rgba(239, 68, 68, 0.4);
        }

        @keyframes pulse-record {
            0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.5); }
            50% { box-shadow: 0 0 0 15px rgba(239, 68, 68, 0); }
        }

        .realty-voice-btn svg {
            width: 24px;
            height: 24px;
            fill: #64748b;
        }

        .realty-voice-btn.recording svg {
            fill: white;
        }

        /* Results Card - Premium look */
        .realty-result-card {
            background: linear-gradient(145deg, #f0f9ff 0%, #e0f2fe 50%, #f0f9ff 100%);
            border: 1px solid rgba(186, 230, 253, 0.6);
            border-radius: 20px;
            padding: 20px !important;
            margin-top: 12px;
            box-shadow: 0 4px 20px rgba(14, 165, 233, 0.1);
            backdrop-filter: blur(10px);
        }

        .realty-result-card h4 {
            color: #0369a1;
            font-size: 1rem;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-weight: 600;
        }

        .realty-result-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid rgba(186, 230, 253, 0.4);
            font-size: 0.9rem;
        }

        .realty-result-item:last-of-type {
            border-bottom: none;
        }

        .realty-result-label {
            color: #64748b;
            font-weight: 500;
        }

        .realty-result-value {
            color: #0f172a;
            font-weight: 600;
            text-align: right;
            max-width: 60%;
        }

        .realty-status-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 10px 20px;
            border-radius: 25px;
            font-size: 0.9rem;
            font-weight: 700;
            margin-top: 16px;
            letter-spacing: 0.3px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }

        .realty-status-badge.qualified {
            background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%);
            color: #166534;
            border: 1px solid rgba(22, 163, 74, 0.2);
        }

        .realty-status-badge.not-qualified {
            background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
            color: #991b1b;
        }

        /* Property Listing Cards - Premium Design */
        .realty-property-list {
            display: flex;
            flex-direction: column;
            gap: 14px;
            margin-top: 14px;
        }

        .realty-property-card {
            background: linear-gradient(145deg, #ffffff 0%, #fafbfc 100%);
            border: 1px solid rgba(226, 232, 240, 0.8);
            border-radius: 16px;
            padding: 16px;
            display: flex;
            gap: 14px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
        }

        .realty-property-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background: linear-gradient(180deg, var(--primary-color) 0%, var(--secondary-color) 100%);
            opacity: 0;
            transition: opacity 0.3s;
        }

        .realty-property-card:hover {
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.15);
            transform: translateY(-2px);
            border-color: rgba(102, 126, 234, 0.3);
        }

        .realty-property-card:hover::before {
            opacity: 1;
        }

        .realty-property-image {
            width: 72px;
            height: 72px;
            background: linear-gradient(145deg, #e0e7ff 0%, #c7d2fe 100%);
            border-radius: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 32px;
            flex-shrink: 0;
            box-shadow: 0 2px 8px rgba(199, 210, 254, 0.5);
        }

        .realty-property-info {
            flex: 1;
            min-width: 0;
            display: flex;
            flex-direction: column;
            justify-content: center;
            gap: 4px;
        }

        .realty-property-title {
            font-weight: 700;
            font-size: 0.95rem;
            color: #1e293b;
            margin-bottom: 2px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            letter-spacing: -0.2px;
        }

        .realty-property-price {
            color: #10b981;
            font-weight: 700;
            font-size: 0.9rem;
            margin-bottom: 2px;
        }

        .realty-property-details {
            font-size: 0.8rem;
            color: #64748b;
            line-height: 1.4;
        }

        /* Powered By - More elegant */
        .realty-powered-by {
            text-align: center;
            padding: 12px;
            font-size: 0.8rem;
            color: #94a3b8;
            background: linear-gradient(180deg, #fafafa 0%, #f5f5f5 100%);
            border-top: 1px solid rgba(226, 232, 240, 0.5);
        }

        .realty-powered-by a {
            color: var(--primary-color);
            text-decoration: none;
            font-weight: 600;
            transition: color 0.2s;
        }

        .realty-powered-by a:hover {
            color: var(--secondary-color);
        }
    `;

    // HTML Template
    function createWidgetHTML() {
        return `
            <style>
                :root {
                    --primary-color: ${state.config.primaryColor};
                    --secondary-color: ${state.config.secondaryColor};
                }
                ${styles}
            </style>
            
            <!-- Chat Bubble Button -->
            <button class="realty-chat-bubble" id="realtyBubble" aria-label="Open chat">
                <span class="realty-notification-badge" id="realtyBadge">1</span>
                <svg viewBox="0 0 24 24">
                    <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/>
                </svg>
            </button>
            
            <!-- Chat Window -->
            <div class="realty-chat-window" id="realtyChatWindow">
                <!-- Header -->
                <div class="realty-chat-header">
                    <div class="realty-avatar">${state.config.botAvatar}</div>
                    <div class="realty-header-info">
                        <div class="realty-header-name">${state.config.botName}</div>
                        <div class="realty-header-status">
                            <span class="realty-status-dot"></span>
                            <span>Online • Ready to help</span>
                        </div>
                    </div>
                    <div class="realty-header-actions">
                        <button class="realty-header-btn" id="realtyRestart" title="Restart conversation">
                            <svg viewBox="0 0 24 24">
                                <path d="M17.65 6.35A7.958 7.958 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
                            </svg>
                        </button>
                        <button class="realty-header-btn" id="realtyMinimize" title="Minimize">
                            <svg viewBox="0 0 24 24">
                                <path d="M19 13H5v-2h14v2z"/>
                            </svg>
                        </button>
                    </div>
                </div>
                
                <!-- Messages -->
                <div class="realty-messages" id="realtyMessages">
                    <!-- Messages will be inserted here -->
                </div>
                
                <!-- Input Area -->
                <div class="realty-input-area">
                    <button class="realty-voice-btn" id="realtyVoice" title="Voice input">
                        <svg viewBox="0 0 24 24">
                            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1-9c0-.55.45-1 1-1s1 .45 1 1v6c0 .55-.45 1-1 1s-1-.45-1-1V5zm6 6c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
                        </svg>
                    </button>
                    <div class="realty-input-wrapper">
                        <input type="text" class="realty-input" id="realtyInput" placeholder="Type your message..." autocomplete="off">
                        <button class="realty-send-btn" id="realtySend" disabled>
                            <svg viewBox="0 0 24 24">
                                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                            </svg>
                        </button>
                    </div>
                </div>
                
                <!-- Powered By -->
                <div class="realty-powered-by">
                    Powered by <a href="https://realtyassistant.in" target="_blank">RealtyAssistant AI</a>
                </div>
            </div>
        `;
    }

    // Initialize widget
    function init(config = {}) {
        state.config = { ...DEFAULT_CONFIG, ...config };
        state.sessionId = generateSessionId();

        // Create container
        const container = document.createElement('div');
        container.id = 'realty-widget-container';
        container.innerHTML = createWidgetHTML();
        document.body.appendChild(container);

        // Bind events
        bindEvents();

        // Show initial greeting after a delay
        setTimeout(() => {
            addBotMessage(state.config.greeting);
        }, 1000);

        console.log('RealtyAssistant Widget initialized');
    }

    // Bind event listeners
    function bindEvents() {
        const bubble = document.getElementById('realtyBubble');
        const chatWindow = document.getElementById('realtyChatWindow');
        const input = document.getElementById('realtyInput');
        const sendBtn = document.getElementById('realtySend');
        const voiceBtn = document.getElementById('realtyVoice');
        const minimizeBtn = document.getElementById('realtyMinimize');
        const restartBtn = document.getElementById('realtyRestart');
        const badge = document.getElementById('realtyBadge');

        // Toggle chat
        bubble.addEventListener('click', () => {
            state.isOpen = !state.isOpen;
            chatWindow.classList.toggle('open', state.isOpen);
            bubble.classList.toggle('open', state.isOpen);
            if (state.isOpen) {
                badge.style.display = 'none';
                input.focus();
            }
        });

        // Minimize
        minimizeBtn.addEventListener('click', () => {
            state.isOpen = false;
            chatWindow.classList.remove('open');
            bubble.classList.remove('open');
        });

        // Restart
        restartBtn.addEventListener('click', restartConversation);

        // Input handling
        input.addEventListener('input', () => {
            sendBtn.disabled = !input.value.trim();
        });

        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && input.value.trim()) {
                sendMessage(input.value.trim());
                input.value = '';
                sendBtn.disabled = true;
            }
        });

        sendBtn.addEventListener('click', () => {
            if (input.value.trim()) {
                sendMessage(input.value.trim());
                input.value = '';
                sendBtn.disabled = true;
            }
        });

        // Voice handling
        voiceBtn.addEventListener('click', toggleVoiceRecording);
    }

    // Add bot message
    function addBotMessage(text, options = null) {
        const messagesContainer = document.getElementById('realtyMessages');

        const messageDiv = document.createElement('div');
        messageDiv.className = 'realty-message bot';

        let optionsHTML = '';
        if (options && options.length) {
            optionsHTML = `
                <div class="realty-quick-replies">
                    ${options.map(opt => {
                // Escape single quotes for onclick handler
                const escapedOpt = opt.replace(/'/g, "\\'");
                return `<button class="realty-quick-reply" onclick="RealtyAssistantWidget.sendMessage('${escapedOpt}')">${opt}</button>`;
            }).join('')}
                </div>
            `;
        }

        messageDiv.innerHTML = `
            <div class="realty-message-avatar">${state.config.botAvatar}</div>
            <div class="realty-message-wrapper">
                <div class="realty-message-content">${formatMessage(text)}</div>
                ${optionsHTML}
            </div>
        `;

        messagesContainer.appendChild(messageDiv);
        scrollToBottom();

        state.messages.push({ role: 'assistant', content: text });
    }

    // Add user message
    function addUserMessage(text) {
        const messagesContainer = document.getElementById('realtyMessages');

        const messageDiv = document.createElement('div');
        messageDiv.className = 'realty-message user';
        messageDiv.innerHTML = `
            <div class="realty-message-avatar">👤</div>
            <div class="realty-message-content">${escapeHtml(text)}</div>
        `;

        messagesContainer.appendChild(messageDiv);
        scrollToBottom();

        state.messages.push({ role: 'user', content: text });
    }

    // Show typing indicator
    function showTyping() {
        state.isTyping = true;
        const messagesContainer = document.getElementById('realtyMessages');

        const typingDiv = document.createElement('div');
        typingDiv.className = 'realty-typing';
        typingDiv.id = 'realtyTyping';
        typingDiv.innerHTML = `
            <div class="realty-message-avatar" style="background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);">${state.config.botAvatar}</div>
            <div class="realty-typing-dots">
                <div class="realty-typing-dot"></div>
                <div class="realty-typing-dot"></div>
                <div class="realty-typing-dot"></div>
            </div>
        `;

        messagesContainer.appendChild(typingDiv);
        scrollToBottom();
    }

    // Hide typing indicator
    function hideTyping() {
        state.isTyping = false;
        const typingDiv = document.getElementById('realtyTyping');
        if (typingDiv) {
            typingDiv.remove();
        }
    }

    // Send message
    function sendMessage(text) {
        addUserMessage(text);
        processUserInput(text);
    }

    // Smart parsing - extract data using LOCAL pattern matching only (NO AI)
    // Matches user text to exact form options
    function smartParseInput(text) {
        const extracted = {};
        const lowerText = text.toLowerCase().trim();

        // === LOCATION MATCHING ===
        // All 16 cities from the form - exact match
        const formCities = [
            'noida', 'greater noida', 'greater noida west', 'lucknow',
            'gurugram', 'ghaziabad', 'pune', 'thane', 'mumbai',
            'navi mumbai', 'dehradun', 'agra', 'vrindavan', 'delhi',
            'varanasi', 'bengaluru', 'bangalore', 'gurgaon' // aliases
        ];

        // Sort by length descending to match "greater noida west" before "noida"
        const sortedCities = [...formCities].sort((a, b) => b.length - a.length);
        for (const city of sortedCities) {
            if (lowerText.includes(city)) {
                // Normalize aliases
                let matchedCity = city;
                if (city === 'bangalore') matchedCity = 'bengaluru';
                if (city === 'gurgaon') matchedCity = 'gurugram';
                // Capitalize properly
                extracted.location = matchedCity.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
                break;
            }
        }

        // === PROPERTY CATEGORY MATCHING ===
        if (lowerText.includes('commercial')) {
            extracted.property_category = 'Commercial Properties';
        } else if (lowerText.includes('residential') || lowerText.includes('apartment') ||
            lowerText.includes('flat') || lowerText.includes('villa') ||
            lowerText.includes('house') || lowerText.includes('home')) {
            extracted.property_category = 'Residential Properties';
        }

        // === PROPERTY TYPE MATCHING (subtypes from form) ===
        const residentialTypes = [
            'apartments', 'villas', 'residential plots', 'independent floor',
            'residential studio', 'residential prelease', 'other residential'
        ];
        const commercialTypes = [
            'commercial plots', 'commercial studio', 'office space',
            'food court', 'high street retail', 'shops', 'showrooms',
            'commercial preleased', 'others commercial'
        ];

        // Check residential types
        for (const ptype of residentialTypes) {
            if (lowerText.includes(ptype) || lowerText.includes(ptype.replace(' ', ''))) {
                extracted.property_type = ptype.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
                extracted.property_category = 'Residential Properties';
                break;
            }
        }

        // Check commercial types
        if (!extracted.property_type) {
            for (const ptype of commercialTypes) {
                if (lowerText.includes(ptype) || lowerText.includes(ptype.replace(' ', ''))) {
                    extracted.property_type = ptype.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
                    extracted.property_category = 'Commercial Properties';
                    break;
                }
            }
        }

        // === BEDROOM MATCHING ===
        // Match exact form options: 1 BHK, 2 BHK, 3 BHK, 4 BHK, 5 BHK, Studio
        const bhkMatch = lowerText.match(/(\d+)\s*bhk/i);
        if (bhkMatch) {
            const num = parseInt(bhkMatch[1]);
            if (num >= 1 && num <= 5) {
                extracted.bedroom = `${num} BHK`;
            }
        } else if (lowerText.includes('studio')) {
            extracted.bedroom = 'Studio';
        }

        // === PROJECT STATUS MATCHING ===
        // Match exact form options: Launching soon, New Launch, Under Construction, Ready to move in
        const projectStatusOptions = [
            { keywords: ['launching soon', 'launching', 'upcoming'], value: 'Launching soon' },
            { keywords: ['new launch', 'newly launched', 'just launched'], value: 'New Launch' },
            { keywords: ['under construction', 'construction', 'building'], value: 'Under Construction' },
            { keywords: ['ready to move', 'ready', 'move in', 'immediate', 'completed'], value: 'Ready to move in' }
        ];
        for (const status of projectStatusOptions) {
            if (status.keywords.some(kw => lowerText.includes(kw))) {
                extracted.project_status = status.value;
                break;
            }
        }

        // === POSSESSION MATCHING ===
        // Match exact form options: 3 Months, 6 Months, 1 year, 2+ years, Ready To Move
        const possessionOptions = [
            { keywords: ['3 month', 'three month', '3month'], value: '3 Months' },
            { keywords: ['6 month', 'six month', '6month', 'half year'], value: '6 Months' },
            { keywords: ['1 year', 'one year', '1year', '12 month'], value: '1 year' },
            { keywords: ['2 year', '2+ year', 'two year', '2year', 'more than 2', 'after 2'], value: '2+ years' },
            { keywords: ['ready to move', 'ready', 'immediate', 'now', 'asap'], value: 'Ready To Move' }
        ];
        for (const poss of possessionOptions) {
            if (poss.keywords.some(kw => lowerText.includes(kw))) {
                extracted.possession = poss.value;
                break;
            }
        }

        // === BUDGET MATCHING ===
        // Parse budget strings like "50 lakhs", "1-2 crore", "75L", "1.5Cr", "50-75 lakhs"
        const budgetPatterns = [
            /(\d+(?:\.\d+)?)\s*(?:to|-)\s*(\d+(?:\.\d+)?)\s*(lakh|lac|l|crore|cr)/i,  // Range: 50-75 lakhs
            /(\d+(?:\.\d+)?)\s*(lakh|lac|l|crore|cr)/i,  // Single: 50 lakhs
            /(?:budget|range|price)?\s*(?:is|:)?\s*(\d+(?:\.\d+)?)\s*(lakh|lac|l|crore|cr)/i  // "Budget is 50 lakhs"
        ];
        for (const pattern of budgetPatterns) {
            const budgetMatch = lowerText.match(pattern);
            if (budgetMatch) {
                extracted.budget = text.match(pattern)[0].trim();
                break;
            }
        }

        // === PHONE NUMBER MATCHING ===
        const phoneMatch = text.match(/(?:\+91|91|0)?[6789]\d{9}/);
        if (phoneMatch) {
            // Clean up phone number
            let phone = phoneMatch[0].replace(/^(?:\+91|91|0)/, '');
            if (phone.length === 10) {
                extracted.phone = phone;
            }
        }

        // === EMAIL MATCHING ===
        const emailMatch = text.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);
        if (emailMatch) {
            extracted.email = emailMatch[0].toLowerCase();
        }

        return extracted;
    }


    // Process user input based on current stage with smart parsing
    function processUserInput(text) {
        const currentStage = CONVERSATION_FLOW[state.currentStage];

        if (!currentStage) return;

        // Try to extract multiple data points from user message
        const extracted = smartParseInput(text);

        // Store the current field
        if (currentStage.field) {
            state.collectedData[currentStage.field] = text;
        }

        // Also store any additional extracted data
        Object.keys(extracted).forEach(key => {
            if (!state.collectedData[key] && extracted[key]) {
                state.collectedData[key] = extracted[key];
            }
        });

        // Determine next stage
        let nextStage = currentStage.next;

        // SKIP BEDROOM for Commercial properties
        if (state.currentStage === 'property_type' && nextStage === 'bedroom') {
            const category = state.collectedData.property_category?.toLowerCase() || '';
            if (category.includes('commercial')) {
                nextStage = 'search_and_show'; // Skip directly to search
            }
        }

        // Handle consent_after_search - route based on user's answer
        if (state.currentStage === 'consent_after_search') {
            const userSaidYes = text.toLowerCase().includes('yes') || text.toLowerCase().includes('call');
            state.collectedData.consent = userSaidYes;
            nextStage = userSaidYes ? 'budget' : 'thank_you';
        }

        // Skip stages where we already have the data (except special stages)
        const specialStages = ['search_and_show', 'consent_after_search', 'complete', 'thank_you'];
        while (nextStage && CONVERSATION_FLOW[nextStage] && !specialStages.includes(nextStage)) {
            const nextStageData = CONVERSATION_FLOW[nextStage];
            if (nextStageData.field && state.collectedData[nextStageData.field]) {
                nextStage = nextStageData.next;
            } else {
                break;
            }
        }

        state.currentStage = nextStage;

        showTyping();

        // Simulate processing delay
        setTimeout(() => {
            hideTyping();

            // Handle search_and_show - trigger property search
            if (state.currentStage === 'search_and_show') {
                triggerPropertySearch();
                return;
            }

            // Handle thank_you - user declined contact
            if (state.currentStage === 'thank_you') {
                addBotMessage(`Thank you for your interest, ${state.collectedData.name || 'there'}! 🙏\n\nFeel free to come back anytime you need help finding a property. Have a great day! 🏠`);
                // Save minimal lead info (no contact details)
                saveLeadToDatabase(false);
                return;
            }

            // Handle complete - user provided all info
            if (state.currentStage === 'complete') {
                submitQualification();
                return;
            }

            // Check if we extracted a lot of data - acknowledge it
            const extractedKeys = Object.keys(extracted);
            if (extractedKeys.length >= 2) {
                const acknowledgment = generateSmartAcknowledgment(extracted);
                addBotMessage(acknowledgment);
                setTimeout(() => {
                    askNextQuestion();
                }, 600);
            } else {
                askNextQuestion();
            }
        }, 800 + Math.random() * 400);
    }


    // Generate smart acknowledgment when user provides multiple pieces of info
    function generateSmartAcknowledgment(extracted) {
        const parts = [];

        if (extracted.location) {
            parts.push(`${extracted.location}`);
        }
        if (extracted.property_category) {
            parts.push(`${extracted.property_category.replace(' Properties', '').toLowerCase()} property`);
        }
        if (extracted.bedroom) {
            parts.push(extracted.bedroom);
        }

        if (parts.length >= 2) {
            return `Got it! 🎯 So you're looking for ${parts.join(', ')}. Let me find the best matches for you!`;
        }
        return `Thanks for that info! Let me note that down. 📝`;
    }

    // Ask the next question
    function askNextQuestion() {
        const stage = CONVERSATION_FLOW[state.currentStage];

        if (!stage) return;

        let question = stage.question;
        let options = stage.options;

        // Handle dynamic property_type question based on property_category
        if (state.currentStage === 'property_type') {
            const category = state.collectedData.property_category?.toLowerCase() || '';
            const location = state.collectedData.location || 'that area';

            if (category.includes('commercial')) {
                question = `Nice! Commercial properties in ${location}! 🏢\n\nWhat type are you looking for?`;
                // EXACT options from form for Commercial
                options = [
                    'Commercial Plots', 'Commercial Studio', 'Office Space',
                    'Food Court', 'High Street Retail', 'Shops',
                    'Showrooms', 'Commercial Preleased', 'Others Commercial'
                ];
            } else {
                question = `Great choice! ${location} has some lovely options. 🏠\n\nWhat type of property?`;
                // EXACT options from form for Residential
                options = [
                    'Apartments', 'Villas', 'Residential Plots',
                    'Independent Floor', 'Residential Studio',
                    'Residential Prelease', 'Other Residential'
                ];
            }
        }

        // Replace placeholders in question
        if (question) {
            question = question.replace('{name}', state.collectedData.name || 'there');
            question = question.replace('{location}', state.collectedData.location || '');
        }

        addBotMessage(question, options);
    }

    // Trigger property search and show results (called after possession is collected)
    async function triggerPropertySearch() {
        showTyping();

        let propertyCount = 0;
        let apiSuccess = false;
        let properties = [];

        // Try to fetch real results from API
        try {
            // Map property_category to property_type for API
            const category = state.collectedData.property_category?.toLowerCase() || '';
            const propertyType = category.includes('commercial') ? 'commercial' : 'residential';

            // Build search params with ALL form fields
            const searchParams = new URLSearchParams({
                location: state.collectedData.location || '',
                property_type: propertyType,
                topology: state.collectedData.bedroom || ''
            });

            // Add optional parameters if they exist
            if (state.collectedData.project_status) {
                searchParams.set('project_status', state.collectedData.project_status);
            }
            if (state.collectedData.possession) {
                searchParams.set('possession', state.collectedData.possession);
            }

            const response = await fetch(`${state.config.apiUrl}/api/search?${searchParams}`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' },
                signal: AbortSignal.timeout(30000)
            });

            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    propertyCount = data.count || 0;
                    properties = data.properties || [];
                    apiSuccess = true;
                    // Store for later use
                    state.searchResults = { count: propertyCount, properties, success: true };
                    console.log(`API returned ${propertyCount} properties from realtyassistant.in`);
                }
            }
        } catch (error) {
            console.log('API search failed:', error.message);
            state.searchResults = { count: 0, properties: [], success: false };
        }

        // Hide typing and show results
        setTimeout(() => {
            hideTyping();

            // Show results message with total count
            if (propertyCount > 0) {
                addBotMessage(`🎉 Great news, ${state.collectedData.name}! I found **${propertyCount} matching properties** in ${state.collectedData.location}!`);
            } else {
                addBotMessage(`I searched for properties matching your criteria in ${state.collectedData.location}, but couldn't find exact matches right now. Our property experts can help you find similar options!`);
            }

            // Show top 3 property listings with total count info
            if (apiSuccess && properties.length > 0) {
                setTimeout(() => {
                    showApiPropertyListings(properties.slice(0, 3), propertyCount); // Top 3 + total count
                }, 600);
            }

            // Now ask for consent - after showing results
            setTimeout(() => {
                state.currentStage = 'consent_after_search';
                askNextQuestion();
            }, properties.length > 0 ? 1200 : 800);

        }, 500);
    }

    // Submit qualification - called when user completes all info (after consent)
    async function submitQualification() {
        showTyping();

        const propertyCount = state.searchResults?.count || 0;
        const consent = state.collectedData.consent === true;

        setTimeout(() => {
            hideTyping();

            // Show final result card
            showInstantResultCard(propertyCount, consent, consent && propertyCount > 0);

            // Final message
            setTimeout(() => {
                addBotMessage(`Thanks ${state.collectedData.name}! 🎉\n\nWe've saved your preferences and a property expert will call you at **${state.collectedData.phone}** with personalized recommendations.\n\n📧 A summary has been sent to **${state.collectedData.email}**!\n\nHave a great day! 🏠`);
            }, 600);

        }, 500);

        // Save lead to database (with full contact info)
        saveLeadToDatabase(true);
        sendEmailSummary();
    }


    // REMOVED: showDynamicSuggestions - was generating fake suggestions
    // Now we only show real data from the API

    // Send email summary (backend API call)
    async function sendEmailSummary() {
        if (!state.collectedData.email) {
            console.log('No email provided, skipping email summary');
            return;
        }

        const emailData = {
            to: state.collectedData.email,
            cc: 'support@dmj.one',
            subject: `Property Search Summary - ${state.collectedData.name}`,
            lead: state.collectedData,
            searchUrl: buildRealtyAssistantUrl()
        };

        try {
            await fetch(`${state.config.apiUrl}/api/send-summary-email`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(emailData)
            });
            console.log('Email summary sent successfully');
        } catch (error) {
            console.log('Email sending failed (will be queued):', error.message);
        }
    }

    // Save lead to database via API
    async function saveLeadToDatabase(hasContact = false) {
        const leadData = {
            session_id: state.sessionId,
            timestamp: new Date().toISOString(),
            name: state.collectedData.name || 'Website Visitor',
            phone: hasContact ? (state.collectedData.phone || null) : null,
            email: hasContact ? (state.collectedData.email || null) : null,
            consent: state.collectedData.consent === true,

            // Search preferences
            location: state.collectedData.location || null,
            property_category: state.collectedData.property_category || null,
            property_type: state.collectedData.property_type || null,
            bedroom: state.collectedData.bedroom || null,
            project_status: state.collectedData.project_status || null,
            possession: state.collectedData.possession || null,
            budget: hasContact ? (state.collectedData.budget || null) : null,

            // Search results
            properties_found: state.searchResults?.count || 0,
            search_url: buildRealtyAssistantUrl(),

            // Qualification
            qualified: hasContact && state.collectedData.consent === true && (state.searchResults?.count || 0) > 0
        };

        try {
            const response = await fetch(`${state.config.apiUrl}/api/leads`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(leadData)
            });

            if (response.ok) {
                console.log('Lead saved to database successfully');
            } else {
                throw new Error('API returned error');
            }
        } catch (error) {
            console.log('Database save failed, saving to localStorage:', error.message);
            // Fallback to localStorage
            try {
                const leads = JSON.parse(localStorage.getItem('realtyAssistantLeads') || '[]');
                leads.push(leadData);
                localStorage.setItem('realtyAssistantLeads', JSON.stringify(leads));
                console.log(`Lead saved locally. Total: ${leads.length}`);
            } catch (e) {
                console.error('Failed to save lead:', e);
            }
        }
    }


    // Show instant result card with qualification status
    function showInstantResultCard(propertyCount, hasConsent, isQualified = null) {
        const messagesContainer = document.getElementById('realtyMessages');

        // Determine qualification status if not passed
        // Rule: QUALIFIED if properties > 0 AND consent = true
        if (isQualified === null) {
            isQualified = propertyCount > 0 && hasConsent;
        }

        const statusClass = isQualified ? 'qualified' : 'not-qualified';
        const statusText = isQualified ? '✓ Qualified Lead' : '✗ Not Qualified';

        const cardDiv = document.createElement('div');
        cardDiv.className = 'realty-message bot';
        cardDiv.innerHTML = `
            <div class="realty-message-avatar">${state.config.botAvatar}</div>
            <div class="realty-result-card">
                <h4>📋 Qualification Summary</h4>
                <div class="realty-result-item">
                    <span class="realty-result-label">Name</span>
                    <span class="realty-result-value">${state.collectedData.name || 'Not specified'}</span>
                </div>
                <div class="realty-result-item">
                    <span class="realty-result-label">Phone</span>
                    <span class="realty-result-value">${state.collectedData.phone || 'Not provided'}</span>
                </div>
                <div class="realty-result-item">
                    <span class="realty-result-label">Email</span>
                    <span class="realty-result-value">${state.collectedData.email || 'Not provided'}</span>
                </div>
                <div class="realty-result-item">
                    <span class="realty-result-label">Location</span>
                    <span class="realty-result-value">${state.collectedData.location || 'Not specified'}</span>
                </div>
                <div class="realty-result-item">
                    <span class="realty-result-label">Property Type</span>
                    <span class="realty-result-value">${state.collectedData.bedroom || ''} ${state.collectedData.property_type || ''}</span>
                </div>
                <div class="realty-result-item">
                    <span class="realty-result-label">Project Status</span>
                    <span class="realty-result-value">${state.collectedData.project_status || 'Any'}</span>
                </div>
                <div class="realty-result-item">
                    <span class="realty-result-label">Possession</span>
                    <span class="realty-result-value">${state.collectedData.possession || 'Flexible'}</span>
                </div>
                <div class="realty-result-item">
                    <span class="realty-result-label">Budget</span>
                    <span class="realty-result-value">${state.collectedData.budget || 'Not specified'}</span>
                </div>
                <div class="realty-result-item">
                    <span class="realty-result-label">Properties Found</span>
                    <span class="realty-result-value" style="color: ${propertyCount > 0 ? '#10b981' : '#ef4444'}; font-weight: 600;">${propertyCount} properties</span>
                </div>
                <div class="realty-result-item">
                    <span class="realty-result-label">Sales Consent</span>
                    <span class="realty-result-value">${hasConsent ? 'Yes' : 'No'}</span>
                </div>
                <div class="realty-status-badge ${statusClass}">
                    ${statusText}
                </div>
            </div>
        `;

        messagesContainer.appendChild(cardDiv);
        scrollToBottom();
    }


    // REMOVED: generateSampleProperties - was generating fake/hallucinated property data
    // Now we only show real data from the API search

    // Parse budget string to number
    function parseBudgetToNumber(budget) {
        const lower = budget.toLowerCase();
        let num = parseFloat(lower.replace(/[^\d.]/g, '')) || 50;

        if (lower.includes('crore') || lower.includes('cr')) {
            return num * 10000000;
        } else if (lower.includes('lakh') || lower.includes('lac')) {
            return num * 100000;
        }
        return num * 100000; // Default to lakhs
    }

    // Format price for display
    function formatPrice(num) {
        if (num >= 10000000) {
            return '₹' + (num / 10000000).toFixed(2) + ' Cr';
        } else if (num >= 100000) {
            return '₹' + (num / 100000).toFixed(1) + ' Lakhs';
        }
        return '₹' + num.toLocaleString('en-IN');
    }

    // Capitalize first letter
    function capitalizeFirst(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }

    // Build search URL for realtyassistant.in with correct parameters
    function buildRealtyAssistantUrl() {
        const baseUrl = 'https://realtyassistant.in/properties';
        const params = new URLSearchParams();

        // City ID mapping from the form
        const cityIds = {
            'noida': 10,
            'greater noida': 5,
            'greater noida west': 21,
            'lucknow': 6,
            'gurugram': 9,
            'gurgaon': 9,
            'ghaziabad': 16,
            'pune': 8,
            'thane': 17,
            'mumbai': 1,
            'navi mumbai': 11,
            'dehradun': 18,
            'agra': 19,
            'vrindavan': 20,
            'delhi': 4,
            'varanasi': 15,
            'bengaluru': 2,
            'bangalore': 2,
            // Mumbai areas map to Mumbai
            'andheri': 1, 'bandra': 1, 'malad': 1, 'goregaon': 1, 'powai': 1,
            'worli': 1, 'borivali': 1, 'kandivali': 1, 'juhu': 1, 'khar': 1,
            'santacruz': 1, 'versova': 1, 'lokhandwala': 1, 'oshiwara': 1,
            'wadala': 1, 'dadar': 1, 'parel': 1, 'lower parel': 1, 'bkc': 1,
            'kurla': 1, 'ghatkopar': 1, 'mulund': 1, 'vikhroli': 1, 'chembur': 1
        };

        // Find city ID from location (sort by length to match longer names first)
        if (state.collectedData.location) {
            const locationLower = state.collectedData.location.toLowerCase();
            // Sort by city name length descending to match "greater noida" before "noida"
            const sortedCities = Object.entries(cityIds).sort((a, b) => b[0].length - a[0].length);
            for (const [city, id] of sortedCities) {
                if (locationLower.includes(city)) {
                    params.set('city', id);
                    break;
                }
            }
        }

        // Property category: 1 = Residential, 4 = Commercial
        if (state.collectedData.property_category) {
            const category = state.collectedData.property_category.toLowerCase();
            if (category.includes('commercial')) {
                params.set('property_category', '4');
            } else {
                params.set('property_category', '1');
            }
        }

        // Property type - exact value from form
        if (state.collectedData.property_type) {
            params.set('property_type', state.collectedData.property_type);
        }

        // Bedroom - exact value from form
        if (state.collectedData.bedroom) {
            const bedroom = state.collectedData.bedroom;
            // Only set bedroom for residential (not commercial)
            const category = state.collectedData.property_category?.toLowerCase() || '';
            if (!category.includes('commercial')) {
                params.set('bedroom', bedroom);
            }
        }

        // Project Status - exact value from form
        if (state.collectedData.project_status) {
            params.set('project_status', state.collectedData.project_status);
        }

        // Possession - exact value from form
        if (state.collectedData.possession) {
            params.set('possession', state.collectedData.possession);
        }

        params.set('submit', 'Search');

        const queryString = params.toString();
        return queryString ? `${baseUrl}?${queryString}` : baseUrl;
    }


    // REMOVED: showPropertyListings - was used to display fake/generated properties
    // Now we only use showApiPropertyListings for real API data

    // Show property listings from API with direct links to actual properties
    // Shows top 3 properties with total count info for exploration
    function showApiPropertyListings(properties, totalCount = 0) {
        if (!properties || properties.length === 0) {
            return; // Don't show anything if no properties
        }

        const messagesContainer = document.getElementById('realtyMessages');
        const listingDiv = document.createElement('div');
        listingDiv.className = 'realty-message bot';

        const defaultIcons = ['🏠', '🏢', '🏡'];
        const searchUrl = buildRealtyAssistantUrl();
        const remainingCount = totalCount > 3 ? totalCount - 3 : 0;

        // Generate property cards with images and clickable links
        const propertyCards = properties.map((prop, idx) => {
            const propertyUrl = prop.link || searchUrl;
            const title = prop.title || `Property ${idx + 1}`;
            const location = prop.location || state.collectedData.location || '';
            const price = prop.price || '₹On Request';
            const area = prop.area || '';
            const status = prop.status || '';
            const hasImage = prop.image && prop.image.startsWith('http');

            // Use image if available, otherwise show icon
            const imageContent = hasImage
                ? `<img src="${prop.image}" alt="${title}" style="width: 100%; height: 100%; object-fit: cover; border-radius: 12px;">`
                : `<span style="font-size: 28px;">${defaultIcons[idx % 3]}</span>`;

            return `
            <a href="${propertyUrl}" target="_blank" rel="noopener noreferrer" class="realty-property-link" style="text-decoration: none; color: inherit; display: block;">
                <div class="realty-property-card" style="cursor: pointer; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); border: 1px solid #e2e8f0; border-radius: 16px; padding: 14px; margin-bottom: 10px; background: linear-gradient(145deg, #ffffff 0%, #f8fafc 100%); position: relative; overflow: hidden;" 
                     onmouseover="this.style.transform='translateY(-3px)'; this.style.boxShadow='0 8px 25px rgba(102,126,234,0.2)'; this.style.borderColor='rgba(102,126,234,0.4)';" 
                     onmouseout="this.style.transform=''; this.style.boxShadow=''; this.style.borderColor='#e2e8f0';">
                    <div style="position: absolute; top: 0; left: 0; width: 4px; height: 100%; background: linear-gradient(180deg, #667eea 0%, #764ba2 100%); opacity: 0; transition: opacity 0.3s;" class="card-accent"></div>
                    <div style="display: flex; gap: 14px; align-items: flex-start;">
                        <div style="width: 72px; height: 72px; background: linear-gradient(145deg, #e0e7ff 0%, #c7d2fe 100%); border-radius: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; overflow: hidden; box-shadow: 0 2px 8px rgba(199, 210, 254, 0.5);">
                            ${imageContent}
                        </div>
                        <div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px;">
                            <div style="font-weight: 700; font-size: 0.92rem; color: #1e293b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; letter-spacing: -0.2px;">${title}</div>
                            <div style="color: #10b981; font-weight: 700; font-size: 0.88rem;">${price}</div>
                            <div style="color: #64748b; font-size: 0.8rem; display: flex; align-items: center; gap: 4px;">
                                <span>📍</span>
                                <span style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${location}</span>
                            </div>
                            ${status ? `<div style="display: inline-flex; align-items: center; gap: 4px; padding: 3px 8px; background: ${status.includes('Ready') ? 'rgba(16, 185, 129, 0.1)' : 'rgba(245, 158, 11, 0.1)'}; color: ${status.includes('Ready') ? '#059669' : '#d97706'}; border-radius: 12px; font-size: 0.7rem; font-weight: 600; width: fit-content;">${status}</div>` : ''}
                            <div style="color: #667eea; font-size: 0.75rem; margin-top: 4px; display: flex; align-items: center; gap: 4px; font-weight: 500;">
                                <span>View Details</span>
                                <span>→</span>
                            </div>
                        </div>
                    </div>
                </div>
            </a>
        `}).join('');

        // Build the complete message with header and footer
        listingDiv.innerHTML = `
            <div class="realty-message-avatar">${state.config.botAvatar}</div>
            <div style="max-width: 100%;">
                <div class="realty-message-content" style="margin-bottom: 12px; padding: 14px 18px;">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                        <span style="font-size: 1.1rem;">🏠</span>
                        <strong style="color: #1e293b;">Top ${properties.length} Properties</strong>
                        ${totalCount > 3 ? `<span style="background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.7rem; font-weight: 600;">+${remainingCount} more</span>` : ''}
                    </div>
                    <div style="font-size: 0.82rem; color: #64748b;">Click any property to view full details on RealtyAssistant.in ↗️</div>
                </div>
                <div class="realty-property-list" style="display: flex; flex-direction: column; gap: 0;">
                    ${propertyCards}
                </div>
                ${totalCount > 3 ? `
                <div style="text-align: center; margin-top: 14px; padding: 14px; background: linear-gradient(145deg, #f0f9ff 0%, #e0f2fe 100%); border-radius: 12px; border: 1px solid rgba(186, 230, 253, 0.5);">
                    <div style="font-size: 0.85rem; color: #0369a1; margin-bottom: 10px; font-weight: 500;">
                        📊 <strong>${remainingCount} more properties</strong> match your criteria!
                    </div>
                    <div style="display: flex; gap: 8px; justify-content: center; flex-wrap: wrap;">
                        <a href="${searchUrl}" target="_blank" rel="noopener noreferrer" 
                           style="display: inline-flex; align-items: center; gap: 6px; padding: 10px 16px; background: linear-gradient(135deg, #667eea, #764ba2); color: white; text-decoration: none; border-radius: 20px; font-size: 0.82rem; font-weight: 600; transition: all 0.2s; box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);" 
                           onmouseover="this.style.transform='scale(1.03)'; this.style.boxShadow='0 4px 15px rgba(102, 126, 234, 0.4)';" 
                           onmouseout="this.style.transform=''; this.style.boxShadow='0 2px 8px rgba(102, 126, 234, 0.3)';">
                            🔍 View All ${totalCount} Properties
                        </a>
                    </div>
                    <div style="font-size: 0.75rem; color: #64748b; margin-top: 10px;">
                        Or continue chatting for personalized recommendations, or let our expert call you!
                    </div>
                </div>
                ` : `
                <div style="text-align: center; margin-top: 12px;">
                    <a href="${searchUrl}" target="_blank" rel="noopener noreferrer" 
                       style="display: inline-block; padding: 10px 18px; background: linear-gradient(135deg, #667eea, #764ba2); color: white; text-decoration: none; border-radius: 20px; font-size: 0.85rem; font-weight: 600; transition: all 0.2s;" 
                       onmouseover="this.style.transform='scale(1.02)';" 
                       onmouseout="this.style.transform='';">
                        🔍 View on RealtyAssistant.in
                    </a>
                </div>
                `}
            </div>
        `;

        messagesContainer.appendChild(listingDiv);
        scrollToBottom();
    }

    // Display results from API
    function displayResults(data) {
        const status = data.status || 'pending';
        const propertyCount = data.collected_data?.property_count || 0;

        let resultMessage = "";

        if (status === 'qualified') {
            resultMessage = `🎉 Great news, ${state.collectedData.name}! Based on your requirements, I found **${propertyCount} matching properties** in ${state.collectedData.location}!`;
        } else {
            resultMessage = `Thank you, ${state.collectedData.name}! I've noted your requirements for a **${state.collectedData.topology}** property in **${state.collectedData.location}** with a budget of **${state.collectedData.budget}**.`;
        }

        addBotMessage(resultMessage);

        setTimeout(() => {
            showResultCard(data);
        }, 500);

        setTimeout(() => {
            if (state.collectedData.consent?.toLowerCase().includes('yes')) {
                addBotMessage("A property expert will call you shortly with personalized recommendations. Is there anything else I can help you with?");
            } else {
                addBotMessage("We'll send you property details via email. Feel free to chat again anytime you need assistance! 🏠");
            }
        }, 1500);
    }

    // Display local results (when API unavailable)
    function displayLocalResults() {
        const consent = state.collectedData.consent?.toLowerCase().includes('yes');

        addBotMessage(`Thank you, ${state.collectedData.name}! 🎉 I've captured your property requirements:`);

        setTimeout(() => {
            showLocalResultCard();
        }, 500);

        setTimeout(() => {
            if (consent) {
                addBotMessage("Our property expert will call you shortly with matching properties in " + state.collectedData.location + "!");
            } else {
                addBotMessage("We'll email you property updates for " + state.collectedData.location + ". Happy house hunting! 🏠");
            }
        }, 1500);
    }

    // Show result card
    function showResultCard(data) {
        const messagesContainer = document.getElementById('realtyMessages');
        const status = data?.status || 'pending';
        const isQualified = status === 'qualified';

        const cardDiv = document.createElement('div');
        cardDiv.className = 'realty-message bot';
        cardDiv.innerHTML = `
            <div class="realty-message-avatar">${state.config.botAvatar}</div>
            <div class="realty-result-card">
                <h4>📋 Your Property Requirements</h4>
                <div class="realty-result-item">
                    <span class="realty-result-label">Location</span>
                    <span class="realty-result-value">${state.collectedData.location || 'Not specified'}</span>
                </div>
                <div class="realty-result-item">
                    <span class="realty-result-label">Property Type</span>
                    <span class="realty-result-value">${state.collectedData.property_type || 'Not specified'}</span>
                </div>
                <div class="realty-result-item">
                    <span class="realty-result-label">Configuration</span>
                    <span class="realty-result-value">${state.collectedData.topology || 'Not specified'}</span>
                </div>
                <div class="realty-result-item">
                    <span class="realty-result-label">Budget</span>
                    <span class="realty-result-value">${state.collectedData.budget || 'Not specified'}</span>
                </div>
                <div class="realty-result-item">
                    <span class="realty-result-label">Properties Found</span>
                    <span class="realty-result-value">${data?.collected_data?.property_count || 'Searching...'}</span>
                </div>
                <div class="realty-status-badge ${isQualified ? 'qualified' : 'not-qualified'}">
                    ${isQualified ? '✓ Qualified Lead' : '⏳ Pending Review'}
                </div>
            </div>
        `;

        messagesContainer.appendChild(cardDiv);
        scrollToBottom();
    }

    // Show local result card (when API unavailable)
    function showLocalResultCard() {
        const messagesContainer = document.getElementById('realtyMessages');

        const cardDiv = document.createElement('div');
        cardDiv.className = 'realty-message bot';
        cardDiv.innerHTML = `
            <div class="realty-message-avatar">${state.config.botAvatar}</div>
            <div class="realty-result-card">
                <h4>📋 Your Property Requirements</h4>
                <div class="realty-result-item">
                    <span class="realty-result-label">Name</span>
                    <span class="realty-result-value">${state.collectedData.name || 'Not specified'}</span>
                </div>
                <div class="realty-result-item">
                    <span class="realty-result-label">Location</span>
                    <span class="realty-result-value">${state.collectedData.location || 'Not specified'}</span>
                </div>
                <div class="realty-result-item">
                    <span class="realty-result-label">Property Type</span>
                    <span class="realty-result-value">${state.collectedData.property_type || 'Not specified'}</span>
                </div>
                <div class="realty-result-item">
                    <span class="realty-result-label">Configuration</span>
                    <span class="realty-result-value">${state.collectedData.topology || 'Not specified'}</span>
                </div>
                <div class="realty-result-item">
                    <span class="realty-result-label">Budget</span>
                    <span class="realty-result-value">${state.collectedData.budget || 'Not specified'}</span>
                </div>
                <div class="realty-status-badge qualified">
                    ✓ Requirements Captured
                </div>
            </div>
        `;

        messagesContainer.appendChild(cardDiv);
        scrollToBottom();
    }

    // Toggle voice recording
    async function toggleVoiceRecording() {
        const voiceBtn = document.getElementById('realtyVoice');

        if (state.isRecording) {
            // Stop recording
            state.isRecording = false;
            voiceBtn.classList.remove('recording');

            if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
                state.mediaRecorder.stop();
            }
        } else {
            // Start recording
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                state.mediaRecorder = new MediaRecorder(stream);
                state.audioChunks = [];

                state.mediaRecorder.ondataavailable = (event) => {
                    state.audioChunks.push(event.data);
                };

                state.mediaRecorder.onstop = async () => {
                    const audioBlob = new Blob(state.audioChunks, { type: 'audio/webm' });
                    processVoiceInput(audioBlob);

                    // Stop all tracks
                    stream.getTracks().forEach(track => track.stop());
                };

                state.mediaRecorder.start();
                state.isRecording = true;
                voiceBtn.classList.add('recording');

                addBotMessage("🎤 I'm listening... Speak your response and click the mic again when done.");
            } catch (error) {
                console.error('Microphone access error:', error);
                addBotMessage("⚠️ Could not access microphone. Please check your browser permissions.");
            }
        }
    }

    // Process voice input
    async function processVoiceInput(audioBlob) {
        addUserMessage("🎤 [Voice message]");
        showTyping();

        // In a full implementation, this would send to a speech-to-text API
        // For now, we'll simulate with a placeholder
        setTimeout(() => {
            hideTyping();
            addBotMessage("I heard your voice message! For the demo, please type your response. Voice processing requires the server to be running with Whisper enabled.");
        }, 1000);
    }

    // Restart conversation
    function restartConversation() {
        state.currentStage = 'greeting';
        state.collectedData = {};
        state.messages = [];
        state.sessionId = generateSessionId();

        const messagesContainer = document.getElementById('realtyMessages');
        messagesContainer.innerHTML = '';

        setTimeout(() => {
            addBotMessage(state.config.greeting);
        }, 500);
    }

    // Utility functions
    function generateSessionId() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    function scrollToBottom() {
        const messagesContainer = document.getElementById('realtyMessages');
        setTimeout(() => {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }, 100);
    }

    function formatMessage(text) {
        // Convert **bold** to <strong>
        return text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Expose public API
    window.RealtyAssistantWidget = {
        init,
        sendMessage,
        restartConversation,
        getState: () => ({ ...state }),
        getCollectedData: () => ({ ...state.collectedData })
    };
})();
