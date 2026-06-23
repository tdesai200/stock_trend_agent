# App Store Submission Roadmap (v1.0)

Target launch: Q4 2026 (TestFlight beta → App Store)

## Phase 1: Compliance & Legal (Weeks 1-2)

### Must-Have (App Review Blockers)
- [ ] Disclaimer modal on first app load
  - "Educational tool, not financial advice"
  - Click to accept before using dashboard
  - Re-accept quarterly or on major version updates
  
- [ ] Settings screen with:
  - Privacy Policy link (external or in-app)
  - Terms of Use link (external or in-app)
  - "Send Feedback" contact form
  - "Delete My Data" button (local only for v1)
  - App version and build info
  
- [ ] Privacy Policy document (~1-2 pages):
  - What data we collect (market tickers, preferences)
  - What data we don't collect (never personal/financial info)
  - No tracking, no ads, no third-party data sharing
  - Local storage (watchlist saved on device)
  
- [ ] Terms of Use document (~1-2 pages):
  - Educational use only disclaimer
  - No warranty; decisions are user responsibility
  - No liability for market losses
  - Attribution to data sources (yfinance, Reuters, CNBC, etc.)

- [ ] Language audit across UI:
  - ✅ Remove "should buy", "best stock", "guaranteed"
  - ✅ Replace with "signal", "indicator", "trend", "insight"
  - ✅ Tag all decisions with "for educational purposes"

---

## Phase 2: Reliability & UX (Weeks 2-3)

### Loading States
- [ ] Loading spinner on "Analyze" button
- [ ] Loading spinner on "Run Daily Signals" button
- [ ] Loading spinner on "Save Watchlist" button
- [ ] 3-5 second timeout with user-facing "Try again" option

### Empty States
- [ ] Empty watchlist: "Add your first ticker to get started"
- [ ] Empty signals: "Click Run Daily Signals to populate this view"
- [ ] Empty rationale: "No detailed rationale available for this signal"
- [ ] API error: "Could not fetch data. Check your connection and try again."

### Error Handling & Retry
- [ ] HTTP 5xx errors → automatic 3-second retry (max 2 retries)
- [ ] Network timeout → show "Connection timeout" + Retry button
- [ ] Graceful degradation:
  - Live data unavailable → show cached badge
  - News API down → show "Trusted headlines unavailable"
  - Claude model unavailable → show "News filtering disabled; using basic sentiment"

### Data Quality Indicators
- [ ] All market data tagged with freshness badge (LIVE / FALLBACK / CACHED)
- [ ] Timestamp for all signals ("Last updated: 2026-06-23 14:32 ET")
- [ ] Confidence band explanation (0-0.55: weak, 0.55-0.75: moderate, 0.75+: strong)

---

## Phase 3: Architecture for Mobile (Weeks 2-3)

### Web API Layer
- [ ] Extract analysis pipeline into REST endpoints:
  - `POST /api/v1/analyze` → accept tickers, return scorecard
  - `GET /api/v1/watchlist` → return user watchlist
  - `POST /api/v1/watchlist` → save/update watchlist
  - `GET /api/v1/signals` → return daily signals for watchlist
  
- [ ] Session management:
  - Browser localStorage for watchlist persistence (v1)
  - Optional: Firebase or simple JWT for cloud sync (future)
  
- [ ] Error response format:
  ```json
  {
    "success": false,
    "error": "Insufficient market history for TICKER (need 50+ days)",
    "error_code": "INSUFFICIENT_HISTORY_50"
  }
  ```

- [ ] Rate limiting:
  - Max 10 analysis runs per session
  - Max 100 questions per session (via chat assistant)

### Mobile-Ready CSS
- [ ] Responsive breakpoints:
  - Mobile (max-width: 480px)
  - Tablet (481px - 768px)
  - Desktop (769px+)
  
- [ ] Audit current styles:
  - [ ] Scorecard table columns wrap on mobile
  - [ ] Watchlist chips stack on mobile
  - [ ] CTA buttons full-width on mobile (<320px)
  - [ ] Font sizes readable at 320px width
  
- [ ] Touch-friendly:
  - Button hit targets ≥44x44px
  - Input fields ≥44px tall
  - No hover-only interactions (must work on touch)

---

## Phase 4: App Store Assets (Week 3)

### App Icon
- [ ] 1024x1024 PNG with:
  - Rounded corners (safe zone: inner 960x960)
  - No text overlay
  - Friendly, recognizable design
  - Contrast ratio ≥4.5:1 for accessibility
  
- [ ] App icon suggestions:
  - Upward trend arrow + chart candlestick
  - Lightbulb (insight) + chart combo
  - Simple "S" monogram with trend elements

### Screenshots (5-7 for each device type)
Screenshots for iPhone (typical 6.1" resolution):

1. **Onboarding/Disclaimer**
   - Show disclaimer modal
   - Caption: "Educational tool for market insights"

2. **Watchlist**
   - Show saved watchlist with chips
   - Caption: "Manage up to 20 stock symbols"

3. **Daily Signals**
   - Show Daily Watchlist Signals table
   - Caption: "Explainable reasons + trusted news"

4. **Trend Alert Notification**
   - Show trend reversal alert
   - Caption: "Get notified on trend changes"

5. **Analyzer Deep Dive**
   - Show scorecard + rationale panel
   - Caption: "Transparent decision logic"

6. **Analysis Assistant**
   - Show chat bubble with example question
   - Caption: "Ask concept questions anytime"

7. **Settings & Trust**
   - Show Settings page with Privacy/Terms
   - Caption: "Your privacy and control"

### App Store Metadata
- **App Name**: "Stock Trend Agent" or "Trend Signals"
- **Subtitle**: "AI Market Insights (Educational)"
- **Category**: Finance
- **Keywords**: stock analysis, market trends, portfolio, signals, insights, educational
- **Description** (~300 words):
  ```
  Stock Trend Agent is an educational tool that transforms stock analysis 
  into one simple interface. Get explainable decisions combining technical 
  indicators, multi-source news, earnings context, and macro trends—all 
  with transparent confidence scoring.

  FEATURES:
  • Watchlist management (up to 20 symbols)
  • Daily signals with trend reversal alerts
  • Explainable reasons for every decision
  • Trusted news headlines from Reuters, CNBC, MarketWatch
  • Market macro context (supportive/neutral/risk-off)
  • In-app assistant for concept Q&A
  • Real-time data with cached fallback

  IMPORTANT: This is an educational tool, not financial advice. 
  Decisions are for informational purposes only. Always do your own 
  research and consult a financial advisor before investing.
  ```

- **Support URL**: GitHub Issues or dedicated support email
- **Privacy Policy URL**: Link to privacy doc (Notion, GitHub Pages, or hosted)
- **Terms of Use URL**: Link to terms doc

### Privacy Questionnaire
- [ ] Data collection: "Minimal" (only tickers watched, no personal info)
- [ ] Tracking/Ads: "None"
- [ ] Third-party sharing: "No data sharing"
- [ ] Health/Finance data deletion capability: "User can delete via Settings"

---

## Phase 5: TestFlight Build & Review (Week 4)

### Pre-Submission Checklist
- [ ] All UI text finalized and reviewed
- [ ] Privacy Policy + Terms finalized (legal review optional but recommended)
- [ ] 5+ screenshots captured in high quality
- [ ] App icon finalized (1024x1024)
- [ ] Support email set up and monitored
- [ ] Analytics (optional): Bugsnag or Sentry for crash reporting

### Build Configuration
- [ ] App version: 1.0.0
- [ ] Build number: 1
- [ ] Min iOS version: 14.0 (or relevant for React Native/Flutter if mobile)
- [ ] Device compatibility: iPhone + iPad
- [ ] Required capabilities: Network only (no camera, location, health, etc.)

### TestFlight Beta (14 days)
- [ ] Submit to TestFlight first (risk-free iteration)
- [ ] Internal testing: 3-5 team members, 3+ days
- [ ] External beta: 50+ external testers, 7+ days
- [ ] Iteration: Fix crashes, improve UX based on feedback
- [ ] Monitor:
  - Crash rate (target: <1%)
  - Session length (target: >2 min average first session)
  - Watchlist adoption (target: >50% save a watchlist)

### App Store Submission
- [ ] Build signed and notarized
- [ ] Privacy questionnaire completed
- [ ] Screenshots + icon uploaded
- [ ] Description, keywords, support info finalized
- [ ] Submit for review (24-48 hour typical review time)

---

## Phase 6: Launch & Post-Launch (Week 5+)

### Day 1 (App Store Approved)
- [ ] Announce on Twitter, Product Hunt, Hacker News
- [ ] Email list (if applicable)
- [ ] GitHub releases page
- [ ] Monitor App Store reviews and ratings

### Week 1 Post-Launch
- [ ] Fix any critical bugs reported
- [ ] Respond to App Store reviews
- [ ] Collect user feedback via "Send Feedback" form
- [ ] Track metrics:
  - Downloads
  - Active users (DAU)
  - Watchlist saves
  - Signal runs
  - Chat assistant usage

### v1.1 Roadmap (if successful)
- [ ] Mobile app (React Native or Flutter)
- [ ] User accounts + cloud sync for watchlist
- [ ] Push notifications (daily digest or trend alerts)
- [ ] Export reports as PDF
- [ ] Dark mode
- [ ] I18n (Spanish, Mandarin)

---

## Success Criteria for v1.0 Launch

### Before TestFlight
✅ New user can install, accept disclaimer, add 3 tickers, and see signals in <2 min  
✅ All navigation links work (Privacy, Terms, Settings, Support)  
✅ No crash-causing bugs on iOS 14+  
✅ All copy reviewed for non-advisory language  

### TestFlight Phase
✅ <1% crash rate over 7-day beta  
✅ >50% of external testers save a watchlist  
✅ >50% of external testers run at least one daily signal  
✅ Avg session length >90 seconds  
✅ Feedback sentiment >60% positive  

### App Store Launch
✅ Submit first build within 7 days of TestFlight end  
✅ Approve first time (no resubmission for violations)  
✅ Reach 50+ downloads in first week  
✅ Maintain 4.0+ star rating  

---

## Compliance Checkpoints

**Before TestFlight:**
- [ ] Apple Developer account active
- [ ] Certificates and provisioning profiles configured
- [ ] Privacy Policy URL live and accessible
- [ ] GDPR/CCPA clauses in Privacy Policy (if applicable)
- [ ] No mention of "guaranteed returns" anywhere
- [ ] No references to specific investment recommendations

**During Beta:**
- [ ] Collect beta tester feedback on disclaimer clarity
- [ ] Test account deletion flow (if implemented)
- [ ] Verify all links work (Privacy, Terms, Support)

**Before App Store Submit:**
- [ ] Legal team final review of Privacy + Terms (optional but recommended)
- [ ] Competitor analysis: Are similar apps live? What compliance did they use?
- [ ] App Store guideline cross-check: https://developer.apple.com/app-store/review/guidelines/

---

## References & Templates

### Privacy Policy Template
- Termly.io (auto-generate, customizable)
- iubenda.com (GDPR-compatible templates)
- GitHub Pages hosted example: https://github.com/example/privacy-policy

### Terms of Use Template
- Iubenda.com
- GitHub-hosted markdown template

### Icon Tools
- Figma (free tier)
- Sketch
- Adobe Express

### Screenshot Tools
- Apple's TestFlight built-in capture
- Figma mockups
- Framer
- Photoshop

---

## Questions for Team
1. Will we handle user accounts in v1.0 or v1.1?
2. Should we start with iOS only or also submit to Google Play (Android)?
3. Do we need legal review or proceed with standard template?
4. Plan for localization (non-English markets)?
5. Advertising or free-only for v1.0?

---

## Timeline Summary

| Week | Phase | Deliverable |
|------|-------|-------------|
| 1-2  | Compliance | Disclaimer modal, Settings page, Privacy/Terms docs |
| 2-3  | Reliability | Loading states, error handling, mobile responsive CSS |
| 3    | Assets | App icon, 5+ screenshots, metadata copy |
| 4    | TestFlight | Internal beta, iterate, prepare App Store build |
| 5+   | Launch | App Store submission, monitor, support users |
