"""Fake data seeded from real experiment branches."""

EXPERIMENTS = [
    {"branch": "exp/344-baseline", "score": 343.60, "title": "Baseline flat 30bps", "proposer": "—", "status": "baseline"},
    {"branch": "exp/376-high-floor-core", "score": 376.49, "title": "High-floor core + corrected displacement", "proposer": "claude-sonnet-4-6", "status": "keep"},
    {"branch": "exp/380-raise-the-floor", "score": 379.96, "title": "Raise floor to high fixed-fee core", "proposer": "gpt-5.4", "status": "keep"},
    {"branch": "exp/380-ablation-high-floor", "score": 380.39, "title": "Ablation-first high floor with anchor", "proposer": "deepseek-v3.2", "status": "keep"},
    {"branch": "exp/384-adaptive-base-fee", "score": 383.82, "title": "Adaptive base fee with vol-driven range", "proposer": "gpt-4o", "status": "keep"},
    {"branch": "exp/386-timestamp-classifier", "score": 385.91, "title": "Timestamp-classifier with high floor", "proposer": "claude-sonnet-4-6", "status": "keep"},
    {"branch": "exp/394-inventory-skew", "score": 393.62, "title": "Inventory-skew state with asymmetric anchor", "proposer": "gemini-2.5-pro", "status": "keep"},
    {"branch": "exp/394-hazard-pulse", "score": 394.06, "title": "One-step hazard pulse with displacement", "proposer": "gpt-5.4", "status": "best"},
]

MODELS = [
    {"id": "claude-sonnet-4-6", "color": "#cc7832", "wins": 2},
    {"id": "gpt-5.4", "color": "#6a9955", "wins": 3},
    {"id": "gemini-2.5-pro", "color": "#4488cc", "wins": 1},
    {"id": "deepseek-v3.2", "color": "#b060d0", "wins": 1},
]

PROPOSALS_ROUND = [
    {"id": 1, "title": "Arb-optimal fee via closed-form loss minimization", "model": "claude-sonnet-4-6", "impact": "large",
     "desc": "Derive the fee analytically from the known simulation structure. The arb profit on a CFMM is approximately proportional to sigma^2 * k / fee. Set fee = c * sigma * sqrt(k/reserveY) where sigma is estimated from the EMA of ratio changes."},
    {"id": 2, "title": "Confidence-gated wide asymmetry from aligned signals", "model": "gpt-5.4", "impact": "large",
     "desc": "Replace the always-on mild asymmetry with a confidence-gated spread. Compute directional confidence from alignment of vol EMA, displacement direction, and trade direction. Only apply wide asymmetry when 2+ signals agree."},
    {"id": 3, "title": "Multi-regime volatility with hysteresis bands", "model": "gemini-2.5-pro", "impact": "medium",
     "desc": "Classify market into calm/normal/volatile using hysteresis bands on the vol EMA. Each regime has its own fee curve. Hysteresis prevents rapid switching between regimes."},
    {"id": 4, "title": "Inventory-driven rebalancing premium", "model": "deepseek-v3.2", "impact": "medium",
     "desc": "Track net inventory drift from initialization. When reserves are skewed, add a premium on the side that would worsen imbalance. Premium scales with deviation magnitude."},
    {"id": 5, "title": "Quiet-toxicity premium from slow displacement EMA", "model": "gpt-5.4", "impact": "medium",
     "desc": "Add a symmetric premium driven by slow EMA of normalized displacement. Captures 'quiet but toxic' conditions where the price has drifted significantly but volatility appears low."},
    {"id": 6, "title": "Mean-reversion-aware base fee using displacement persistence", "model": "claude-sonnet-4-6", "impact": "medium",
     "desc": "Track how long the price has been displaced in one direction. Longer persistence = higher base fee. Short-lived displacements get lower fees to capture retail."},
]

CRITIQUES = [
    {"proposal_id": 1, "reviewer": "gpt-5.4", "strength": "Grounded in LVR framework, theoretically sound", "weakness": "Requires sigma estimation which is noisy with limited data"},
    {"proposal_id": 1, "reviewer": "gemini-2.5-pro", "strength": "Direct mathematical approach to the problem", "weakness": "The constant c needs careful calibration, risk of overfitting"},
    {"proposal_id": 2, "reviewer": "claude-sonnet-4-6", "strength": "Addresses the key issue of when to apply asymmetry", "weakness": "Signal alignment may be too conservative, missing opportunities"},
    {"proposal_id": 2, "reviewer": "deepseek-v3.2", "strength": "Novel gating mechanism not tried before", "weakness": "Adds complexity with unclear marginal benefit over simple asymmetry"},
    {"proposal_id": 3, "reviewer": "gpt-5.4", "strength": "Hysteresis prevents regime flapping", "weakness": "Experiment history warns dual EMA hurts — this may repeat that mistake"},
    {"proposal_id": 4, "reviewer": "claude-sonnet-4-6", "strength": "Inventory signal is direct and noise-free", "weakness": "GBM has zero drift, so inventory drift is random walk noise"},
]

VOTES = [
    {"proposal_id": 1, "scores": {"claude-sonnet-4-6": 85, "gpt-5.4": 78, "gemini-2.5-pro": 72, "deepseek-v3.2": 80}, "total": 315},
    {"proposal_id": 2, "scores": {"claude-sonnet-4-6": 90, "gpt-5.4": 88, "gemini-2.5-pro": 75, "deepseek-v3.2": 82}, "total": 335},
    {"proposal_id": 3, "scores": {"claude-sonnet-4-6": 45, "gpt-5.4": 40, "gemini-2.5-pro": 65, "deepseek-v3.2": 50}, "total": 200},
    {"proposal_id": 4, "scores": {"claude-sonnet-4-6": 55, "gpt-5.4": 50, "gemini-2.5-pro": 60, "deepseek-v3.2": 70}, "total": 235},
    {"proposal_id": 5, "scores": {"claude-sonnet-4-6": 60, "gpt-5.4": 72, "gemini-2.5-pro": 55, "deepseek-v3.2": 58}, "total": 245},
    {"proposal_id": 6, "scores": {"claude-sonnet-4-6": 70, "gpt-5.4": 65, "gemini-2.5-pro": 50, "deepseek-v3.2": 55}, "total": 240},
]

FAKE_CHAT_RESPONSES = [
    "Interesting idea. Based on the experiment history, approaches that modify the base fee floor have consistently helped. Let me think about how to combine that with your suggestion...",
    "The key insight from our experiments is that 75bps fixed beats 30bps. Any dynamic approach needs to average around that level, not below it. Your approach could work if we anchor the base fee higher.",
    "I'd suggest a slightly different angle: instead of tracking inventory directly, use the displacement from the slow price EMA as a proxy. It's less noisy and captures the same information.",
    "Looking at the vote history, proposals that build on proven ideas (high floor + vol spike) tend to score better than novel but unvalidated approaches. Consider framing this as an improvement to the hazard pulse.",
    "That's a solid proposal. I'd rate it around 75/100. The main risk is parameter sensitivity — the threshold values would need careful tuning through experimentation.",
]
