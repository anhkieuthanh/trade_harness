<script>
  export let onClose = () => {};

  let activeSection = 'overview';

  const sections = [
    { id: 'overview',     label: '🗺️ Tổng quan',           group: null },
    { id: 'architecture', label: '🏗️ Kiến trúc hệ thống',  group: null },
    { id: 'supervisor',   label: '🔁 Supervisor Loop',      group: 'Runtime' },
    { id: 'agent',        label: '🤖 Agent Cycle',          group: 'Runtime' },
    { id: 'strategy',     label: '📊 RSI Strategy',         group: 'Runtime' },
    { id: 'risk',         label: '🛡️ Risk Guard',           group: 'Runtime' },
    { id: 'llm',          label: '🧠 LLM Reasoning',        group: 'Runtime' },
    { id: 'evolution',    label: '🧬 Evo Block',            group: 'Learning' },
    { id: 'trajectory',   label: '📼 Trajectory Log',       group: 'Learning' },
    { id: 'binance',      label: '🔌 Binance Integration',  group: 'Integrations' },
    { id: 'ui',           label: '🖥️ UI & API Server',      group: 'Interfaces' },
    { id: 'config',       label: '⚙️ Config & .env',        group: 'Interfaces' },
    { id: 'dataflow',     label: '🌊 Data Flow',            group: null },
    { id: 'envvars',      label: '📋 Env Variables',        group: null },
  ];

  function scrollTo(id) {
    activeSection = id;
    document.getElementById('docs-section-' + id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  let lastGroup = null;
</script>

<div class="docs-overlay">
  <div class="docs-container">

    <!-- Top Bar -->
    <div class="docs-topbar">
      <div class="docs-topbar-left">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5" class="docs-logo-icon">
          <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        <span class="docs-title">TradeHarness — System Docs</span>
        <span class="docs-version-badge">v1.0 · feat/rsi-crossover-strategy</span>
      </div>
      <button class="docs-close-btn" on:click={onClose}>
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
        </svg>
        Close Docs
      </button>
    </div>

    <div class="docs-body">
      <!-- Sidebar Nav -->
      <nav class="docs-nav">
        <p class="docs-nav-header">Navigation</p>
        {#each sections as sec}
          {#if sec.group !== lastGroup}
            {#if sec.group}
              <p class="docs-nav-group">{sec.group}</p>
            {/if}
          {/if}
          <!-- svelte-ignore deprecated-slot-attribute -->
          <!-- track group for rendering -->
          <button
            class="docs-nav-item {activeSection === sec.id ? 'active' : ''}"
            on:click={() => scrollTo(sec.id)}
          >
            {sec.label}
          </button>
          <!-- We can't mutate lastGroup reactively here, use a different approach -->
        {/each}
      </nav>

      <!-- Content -->
      <div class="docs-content" on:scroll={(e) => {
        // Update active section based on scroll
        const scrollTop = e.target.scrollTop;
        for (const sec of [...sections].reverse()) {
          const el = document.getElementById('docs-section-' + sec.id);
          if (el && el.offsetTop - 120 <= scrollTop) {
            activeSection = sec.id;
            break;
          }
        }
      }}>

        <!-- ── OVERVIEW ── -->
        <section id="docs-section-overview" class="docs-section">
          <div class="section-hero">
            <div class="hero-badge">Open Source · Binance Futures Testnet</div>
            <h1 class="hero-title">TradeHarness</h1>
            <p class="hero-sub">Một hệ thống trading algorithmic tự động, kết hợp <strong>programmatic strategy</strong> (RSI) với <strong>LLM reasoning</strong> để ra quyết định, có vòng lặp <strong>offline evolution</strong> để tự cải thiện theo thời gian.</p>
            <div class="hero-stats">
              <div class="hstat"><span class="hstat-num">5</span><span class="hstat-label">Core Layers</span></div>
              <div class="hstat"><span class="hstat-num">RSI-7</span><span class="hstat-label">Strategy</span></div>
              <div class="hstat"><span class="hstat-num">5m</span><span class="hstat-label">Timeframe</span></div>
              <div class="hstat"><span class="hstat-num">40%</span><span class="hstat-label">LLM Veto Threshold</span></div>
            </div>
          </div>
        </section>

        <!-- ── ARCHITECTURE ── -->
        <section id="docs-section-architecture" class="docs-section">
          <h2 class="section-title">🏗️ Kiến trúc hệ thống</h2>
          <p class="section-desc">TradeHarness được chia thành 5 layer chính, mỗi layer có trách nhiệm rõ ràng và không overlap:</p>

          <div class="arch-diagram">
            <div class="arch-layer layer-1">
              <span class="layer-label">EXECUTION LAYER</span>
              <div class="arch-blocks">
                <div class="arch-block primary">🔁 Supervisor Loop</div>
                <div class="arch-block primary">🤖 Agent Cycle</div>
              </div>
            </div>
            <div class="arch-arrow">↓ produces decisions ↓</div>
            <div class="arch-layer layer-2">
              <span class="layer-label">DECISION LAYER</span>
              <div class="arch-blocks">
                <div class="arch-block success">📊 RSI Strategy</div>
                <div class="arch-block warning">🧠 LLM Veto</div>
                <div class="arch-block danger">🛡️ Risk Guard</div>
                <div class="arch-block primary">⚙️ Action Gate</div>
              </div>
            </div>
            <div class="arch-arrow">↓ executes via ↓</div>
            <div class="arch-layer layer-3">
              <span class="layer-label">INTEGRATION LAYER</span>
              <div class="arch-blocks">
                <div class="arch-block">🔌 Binance Client</div>
                <div class="arch-block">🧠 LMStudio Client</div>
              </div>
            </div>
            <div class="arch-arrow">↓ logs to ↓</div>
            <div class="arch-layer layer-4">
              <span class="layer-label">STORAGE LAYER</span>
              <div class="arch-blocks">
                <div class="arch-block info">📼 Trajectory Log</div>
                <div class="arch-block info">📁 State Files</div>
                <div class="arch-block info">📋 Incidents Log</div>
              </div>
            </div>
            <div class="arch-arrow">↓ feeds into ↓</div>
            <div class="arch-layer layer-5">
              <span class="layer-label">LEARNING LAYER</span>
              <div class="arch-blocks">
                <div class="arch-block evolution">🧬 Evo Block (offline)</div>
                <div class="arch-block evolution">📦 Artifact Versioning</div>
              </div>
            </div>
          </div>
        </section>

        <!-- ── SUPERVISOR ── -->
        <section id="docs-section-supervisor" class="docs-section">
          <h2 class="section-title">🔁 Supervisor Loop</h2>
          <div class="module-path">tradeharness/supervisor.py</div>
          <p class="section-desc">Là <strong>entry point</strong> của toàn bộ hệ thống. Chạy một vòng lặp vô hạn, mỗi iteration thực hiện 2 việc song song:</p>

          <div class="feature-grid">
            <div class="feature-card">
              <div class="feature-icon">⚡</div>
              <h4>Live Trading Cycle</h4>
              <p>Gọi <code>run_agent_cycle()</code> nếu <code>live_enabled = true</code> trong control state. Mỗi cycle là một <em>episode</em> độc lập.</p>
            </div>
            <div class="feature-card">
              <div class="feature-icon">🧬</div>
              <h4>Offline Evolution</h4>
              <p>Kiểm tra xem có đến giờ chạy evolution chưa (<code>offline_evolution_time</code>) và trigger nếu cần. Chạy trong cùng thread.</p>
            </div>
            <div class="feature-card">
              <div class="feature-icon">🖥️</div>
              <h4>UI Server</h4>
              <p>Khởi động Svelte UI server (port 8080) trong background thread. Dashboard accessible ngay khi supervisor start.</p>
            </div>
            <div class="feature-card">
              <div class="feature-icon">💾</div>
              <h4>Failure Recording</h4>
              <p>Mọi exception trong live cycle đều được ghi vào <code>var/runtime/incidents.jsonl</code> — không crash toàn hệ thống.</p>
            </div>
          </div>

          <div class="code-block">
            <div class="code-label">Vòng lặp chính (sleep 5s/iteration)</div>
            <pre>while True:
    state = load_control_state()
    if state.live_enabled:
        run_agent_cycle(settings)   # ← một episode
    if should_run_offline_evolution(state):
        run_scheduled_evolution()
    time.sleep(5)</pre>
          </div>

          <div class="callout callout-info">
            <strong>Control State Hotswap:</strong> Supervisor đọc <code>state.json</code> mỗi iteration → bạn có thể bật/tắt live trading, đổi strategy mode, thay đổi risk params <strong>không cần restart</strong> thông qua UI Settings panel.
          </div>
        </section>

        <!-- ── AGENT CYCLE ── -->
        <section id="docs-section-agent" class="docs-section">
          <h2 class="section-title">🤖 Agent Cycle</h2>
          <div class="module-path">tradeharness/runtime/agent.py</div>
          <p class="section-desc">Core của một episode. Nhận <code>Settings</code>, thực hiện toàn bộ pipeline từ fetch data → decide → execute → log.</p>

          <div class="flow-steps">
            <div class="flow-step">
              <div class="step-num">1</div>
              <div class="step-body">
                <h4>Fetch Market Snapshot</h4>
                <p>Lấy 50 candles 5m + giá hiện tại từ Binance API. Kết quả này là <em>immutable</em> trong suốt episode.</p>
              </div>
            </div>
            <div class="flow-step">
              <div class="step-num">2</div>
              <div class="step-body">
                <h4>Fetch Position State</h4>
                <p>Kiểm tra vị thế đang mở trên Binance (quantity, entry_price, side).</p>
              </div>
            </div>
            <div class="flow-step">
              <div class="step-num">3</div>
              <div class="step-body">
                <h4>Route to Strategy</h4>
                <p><code>rsi_strategy</code> → <code>_run_programmatic_strategy_cycle()</code>. Các mode khác có thể route sang LLM cycle.</p>
              </div>
            </div>
            <div class="flow-step">
              <div class="step-num">4</div>
              <div class="step-body">
                <h4>Risk Guard Evaluation</h4>
                <p>Kiểm tra daily loss, max positions, volatility. Có thể BLOCK hoặc FORCE_CLOSE.</p>
              </div>
            </div>
            <div class="flow-step">
              <div class="step-num">5</div>
              <div class="step-body">
                <h4>LLM Veto Check</h4>
                <p>Chỉ khi action là <code>open_long/open_short</code>. LLM đánh giá confidence. Nếu &lt; 40% → skip lệnh.</p>
              </div>
            </div>
            <div class="flow-step">
              <div class="step-num">6</div>
              <div class="step-body">
                <h4>Action Realization Gate</h4>
                <p>Validate action cuối cùng (đã inspect đủ state chưa?). BLOCK nếu vi phạm pre-conditions.</p>
              </div>
            </div>
            <div class="flow-step">
              <div class="step-num">7</div>
              <div class="step-body">
                <h4>Execute & Log Episode</h4>
                <p>Gọi Binance API thực thi lệnh. Ghi toàn bộ episode record vào <code>episodes.jsonl</code>.</p>
              </div>
            </div>
          </div>

          <div class="callout callout-warning">
            <strong>Episode isolation:</strong> Mỗi call đến <code>run_agent_cycle()</code> tạo ra một <code>episode_id</code> UUID duy nhất. Mọi step, decision, intervention đều được log đầy đủ trong episode đó.
          </div>
        </section>

        <!-- ── RSI STRATEGY ── -->
        <section id="docs-section-strategy" class="docs-section">
          <h2 class="section-title">📊 RSI Crossover Strategy</h2>
          <div class="module-path">tradeharness/runtime/strategies/rsi_strategy.py</div>
          <p class="section-desc">Chiến lược trading dựa trên chỉ số RSI (Relative Strength Index) với Wilder Smoothing EMA.</p>

          <div class="params-grid">
            <div class="param-row header">
              <span>Parameter</span><span>Value</span><span>Env Var</span>
            </div>
            <div class="param-row"><span>RSI Period</span><span class="val mono">7</span><span class="muted">hardcoded</span></div>
            <div class="param-row"><span>Oversold threshold</span><span class="val mono">30</span><span class="muted">hardcoded</span></div>
            <div class="param-row"><span>Overbought threshold</span><span class="val mono">70</span><span class="muted">hardcoded</span></div>
            <div class="param-row"><span>Candle interval</span><span class="val mono">5m</span><span class="muted">CANDLE_INTERVAL</span></div>
            <div class="param-row"><span>Candles fetched</span><span class="val mono">50</span><span class="muted">CANDLE_LIMIT</span></div>
            <div class="param-row"><span>Hold window</span><span class="val mono">300s</span><span class="muted">TRADE_HOLD_SECONDS</span></div>
            <div class="param-row"><span>Cooldown post-close</span><span class="val mono">60s</span><span class="muted">TRADE_COOLDOWN_SECONDS</span></div>
          </div>

          <h4 class="subsection-title">Decision Logic</h4>
          <div class="decision-tree">
            <div class="dtree-node root">build_plan()</div>
            <div class="dtree-branch">
              <div class="dtree-path">
                <div class="dtree-condition">Position đang mở?</div>
                <div class="dtree-children">
                  <div class="dtree-leaf yes">
                    <div class="dtree-condition">Hold đủ 300s?</div>
                    <div class="dtree-leaf success">→ close_position</div>
                    <div class="dtree-condition">RSI revert về 50?</div>
                    <div class="dtree-leaf success">→ close_position</div>
                    <div class="dtree-leaf neutral">→ hold</div>
                  </div>
                  <div class="dtree-leaf no">
                    <div class="dtree-condition">Cooldown active?</div>
                    <div class="dtree-leaf neutral">→ hold</div>
                    <div class="dtree-condition">RSI ≤ 30?</div>
                    <div class="dtree-leaf buy">→ open_long (LONG)</div>
                    <div class="dtree-condition">RSI ≥ 70?</div>
                    <div class="dtree-leaf sell">→ open_short (SHORT)</div>
                    <div class="dtree-leaf neutral">→ hold</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <h4 class="subsection-title">State Persistence</h4>
          <p class="section-desc">Strategy state được lưu vào <code>var/control/trade_strategy_state.json</code> sau mỗi action:</p>
          <div class="code-block">
            <pre>{`{
  "opened_at": "2026-06-11T09:00:00+00:00",
  "side": "LONG",
  "quantity": 0.008,
  "last_closed_at": null,
  "entry_rsi": 27.3
}`}</pre>
          </div>
        </section>

        <!-- ── RISK GUARD ── -->
        <section id="docs-section-risk" class="docs-section">
          <h2 class="section-title">🛡️ Live Risk Guard</h2>
          <div class="module-path">tradeharness/runtime/risk.py</div>
          <p class="section-desc">Layer bảo vệ vốn chạy <strong>trước mỗi lệnh mở</strong>. Có 4 điều kiện chặn độc lập:</p>

          <div class="risk-rules">
            <div class="risk-rule">
              <div class="risk-icon danger">💸</div>
              <div class="risk-body">
                <h4>Daily Loss Limit</h4>
                <p>Nếu <code>day_start_balance - current_balance ≥ max_daily_loss_usdt</code> (mặc định 50 USDT) → <strong>BLOCK</strong> hoặc <strong>FORCE_CLOSE</strong> nếu đang có lệnh.</p>
              </div>
            </div>
            <div class="risk-rule">
              <div class="risk-icon warning">🌋</div>
              <div class="risk-body">
                <h4>Candle Volatility Hard Stop</h4>
                <p>Nếu <code>(high - low) / close × 100 ≥ 2%</code> trên candle cuối → thị trường quá volatile → BLOCK.</p>
              </div>
            </div>
            <div class="risk-rule">
              <div class="risk-icon warning">📌</div>
              <div class="risk-body">
                <h4>Max Open Positions</h4>
                <p>Nếu đã có <code>max_open_positions</code> (mặc định 1) position đang mở → không mở thêm.</p>
              </div>
            </div>
            <div class="risk-rule">
              <div class="risk-icon info">❄️</div>
              <div class="risk-body">
                <h4>Loss Cooldown</h4>
                <p>Sau khi đóng lệnh thua, chờ <code>loss_cooldown_seconds</code> (mặc định 1800s = 30 phút) trước khi mở lệnh mới.</p>
              </div>
            </div>
          </div>

          <div class="callout callout-info">
            <strong>Daily Baseline Reset:</strong> Mỗi ngày mới, <code>day_start_balance_usdt</code> được cập nhật tự động → daily loss counter reset về 0.
          </div>
        </section>

        <!-- ── LLM REASONING ── -->
        <section id="docs-section-llm" class="docs-section">
          <h2 class="section-title">🧠 LLM Reasoning Layer</h2>
          <div class="module-path">tradeharness/runtime/agent.py · tradeharness/integrations/lmstudio/client.py</div>
          <p class="section-desc">LLM đóng vai trò <strong>analyst</strong> — đánh giá chất lượng tín hiệu RSI trước khi thực thi. Có quyền <strong>veto</strong> (Option B) nếu confidence thấp.</p>

          <div class="llm-flow">
            <div class="llm-step">
              <div class="llm-step-icon">📡</div>
              <div class="llm-step-body">
                <h4>Prompt Construction</h4>
                <p>Gửi LLM: RSI value, signal direction, 5 candles OHLC cuối, balance USDT, position state hiện tại.</p>
              </div>
            </div>
            <div class="llm-arrow">→</div>
            <div class="llm-step">
              <div class="llm-step-icon">🤖</div>
              <div class="llm-step-body">
                <h4>LMStudio Inference</h4>
                <p>Model: <code>google/gemma-4-e2b</code> (local). Return JSON: <code>{`{confidence, reasoning, market_context}`}</code></p>
              </div>
            </div>
            <div class="llm-arrow">→</div>
            <div class="llm-step">
              <div class="llm-step-icon">⚖️</div>
              <div class="llm-step-body">
                <h4>Veto Decision</h4>
                <p><strong>confidence ≥ 40%</strong> → Execute lệnh. <strong>confidence &lt; 40%</strong> → Skip, log <code>llm_veto_hold</code>.</p>
              </div>
            </div>
          </div>

          <div class="callout callout-success">
            <strong>Graceful fallback:</strong> Nếu LMStudio offline hoặc timeout → <code>veto = False</code> (không block). Lỗi infra không được phép block trading.
          </div>

          <h4 class="subsection-title">Trajectory Log khi LLM veto</h4>
          <div class="code-block">
            <pre>{`{
  "termination_reason": "llm_veto_hold",
  "observation": {
    "llm_reasoning": {
      "confidence": 25,
      "reasoning": "RSI oversold nhưng downtrend...",
      "market_context": "strong bearish momentum",
      "veto": true,
      "error": null
    }
  }
}`}</pre>
          </div>
        </section>

        <!-- ── EVOLUTION ── -->
        <section id="docs-section-evolution" class="docs-section">
          <h2 class="section-title">🧬 Evo Block (Offline Evolution)</h2>
          <div class="module-path">tradeharness/evolution/</div>
          <p class="section-desc">Vòng lặp học tự động chạy ngoài giờ. Phân tích trajectory logs, khai thác patterns, tự động cập nhật artifacts (skills, rules, contract).</p>

          <div class="feature-grid">
            <div class="feature-card">
              <div class="feature-icon">⛏️</div>
              <h4>Pattern Mining</h4>
              <p>Quét <code>episodes.jsonl</code>, phân loại thành công/thất bại, extract patterns thường gặp (<code>evolution/mining/</code>).</p>
            </div>
            <div class="feature-card">
              <div class="feature-icon">📦</div>
              <h4>Artifact Versioning</h4>
              <p>Output của mỗi evo run được versioned trong <code>var/evolution/runs/</code>. Current version symlink ở <code>artifacts/current/</code>.</p>
            </div>
            <div class="feature-card">
              <div class="feature-icon">📜</div>
              <h4>Skills Update</h4>
              <p>Skills (few-shot examples) được update tự động dựa trên các episode thành công. LLM dùng skills này làm context trong LLM-mode.</p>
            </div>
            <div class="feature-card">
              <div class="feature-icon">📋</div>
              <h4>Action Rules</h4>
              <p>Rules được đúc kết từ các block/fail patterns. Gửi vào LLM như một constraint list để tránh lặp lỗi cũ.</p>
            </div>
          </div>

          <div class="params-grid">
            <div class="param-row header"><span>Artifact File</span><span>Nội dung</span></div>
            <div class="param-row"><span><code>contract.json</code></span><span>Environment contract: tools, symbols, constraints</span></div>
            <div class="param-row"><span><code>skills.json</code></span><span>Few-shot trading examples cho LLM</span></div>
            <div class="param-row"><span><code>action_rules.json</code></span><span>Rules đúc kết từ failures (do not trade when...)</span></div>
            <div class="param-row"><span><code>trajectory_rules.json</code></span><span>Anti-loop rules cho trajectory regulation</span></div>
            <div class="param-row"><span><code>harness_meta.json</code></span><span>Version info của harness</span></div>
          </div>
        </section>

        <!-- ── TRAJECTORY ── -->
        <section id="docs-section-trajectory" class="docs-section">
          <h2 class="section-title">📼 Trajectory Log</h2>
          <div class="module-path">var/trajectories/episodes.jsonl</div>
          <p class="section-desc">Mỗi episode được serialize thành một JSON line. Đây là nguồn dữ liệu duy nhất cho Evolution Block và UI Visualizer.</p>

          <div class="code-block">
            <div class="code-label">Episode Record Schema</div>
            <pre>{`{
  "episode_id": "episode-abc123",
  "task_id": "trade:BTCUSDT:5m:50:inspect_then_decide",
  "harness_version": "local",
  "symbol": "BTCUSDT",
  "mode": "live",
  "started_at": "2026-06-11T09:00:00Z",
  "ended_at": "2026-06-11T09:00:02Z",
  "final_status": "SUCCESS",
  "termination_reason": "rsi_strategy_cycle_completed",
  "final_outcome": { "final": "..." },
  "steps": [
    {
      "step_index": 1,
      "observation": {
        "market_snapshot": {...},
        "position_state": {...},
        "balance_state": {...},
        "risk_state": {...},
        "llm_reasoning": {...}   // ← chỉ có khi open_long/open_short
      },
      "decision_summary": "RSI is oversold (RSI: 27.3 <= 30.0)",
      "action": { "tool": "open_long", "arguments": {...} },
      "harness_intervention": { "decision": "EXECUTE", "layer": "strategy" },
      "environment_feedback": {...}
    }
  ]
}`}</pre>
          </div>

          <div class="callout callout-info">
            <strong>termination_reason values:</strong> <code>rsi_strategy_hold</code> · <code>rsi_strategy_cycle_completed</code> · <code>llm_veto_hold</code> · <code>risk_guard_hold</code> · <code>tool_execution_error</code> · <code>trajectory_regulation_stop</code>
          </div>
        </section>

        <!-- ── BINANCE ── -->
        <section id="docs-section-binance" class="docs-section">
          <h2 class="section-title">🔌 Binance Integration</h2>
          <div class="module-path">tradeharness/integrations/binance/client.py · tradeharness/tools/binance.py</div>

          <div class="feature-grid">
            <div class="feature-card">
              <div class="feature-icon">📈</div>
              <h4>get_market_snapshot</h4>
              <p>Lấy giá spot + N candles OHLCV từ <code>/fapi/v1/klines</code> + <code>/fapi/v1/ticker/price</code>.</p>
            </div>
            <div class="feature-card">
              <div class="feature-icon">💰</div>
              <h4>get_balance</h4>
              <p>Lấy available balance USDT từ <code>/fapi/v2/balance</code>. Trả về 0.0 nếu asset chưa khởi tạo (graceful).</p>
            </div>
            <div class="feature-card">
              <div class="feature-icon">📊</div>
              <h4>get_position</h4>
              <p>Kiểm tra vị thế hiện tại từ <code>/fapi/v2/positionRisk</code>. Trả về <code>is_open, side, quantity, entry_price</code>.</p>
            </div>
            <div class="feature-card">
              <div class="feature-icon">🟢</div>
              <h4>open_long / open_short</h4>
              <p>Đặt lệnh MARKET với <code>trade_entry_quantity_btc</code> (0.008 BTC mặc định). DRY_RUN mode sẽ simulate không gọi API thật.</p>
            </div>
            <div class="feature-card">
              <div class="feature-icon">🔴</div>
              <h4>close_position</h4>
              <p>Đóng toàn bộ vị thế với MARKET order, side ngược lại. Tự động tính side từ position state.</p>
            </div>
          </div>

          <div class="callout callout-warning">
            <strong>Testnet:</strong> Hệ thống chạy trên Binance Futures <strong>Testnet</strong> (<code>testnet.binancefuture.com</code>). API keys trong <code>.env</code> là testnet keys, không phải live.
          </div>
        </section>

        <!-- ── UI ── -->
        <section id="docs-section-ui" class="docs-section">
          <h2 class="section-title">🖥️ UI & API Server</h2>
          <div class="module-path">ui/ · tradeharness/ui_server.py</div>

          <div class="feature-grid">
            <div class="feature-card">
              <div class="feature-icon">⚡</div>
              <h4>Svelte Frontend</h4>
              <p>Build với Vite + Svelte. Dist được serve static bởi Python Flask server. Dev mode proxy sang <code>localhost:8080</code>.</p>
            </div>
            <div class="feature-card">
              <div class="feature-icon">🔄</div>
              <h4>Flow Visualizer</h4>
              <p>Hiển thị episode steps dưới dạng flow diagram. Live tracking tự động chọn episode mới nhất mỗi 5 giây.</p>
            </div>
            <div class="feature-card">
              <div class="feature-icon">⚙️</div>
              <h4>Settings Panel</h4>
              <p>Thay đổi strategy mode, risk params, enable/disable live trading. Ghi ngay vào <code>state.json</code> — effective ngay iteration tiếp theo.</p>
            </div>
          </div>

          <div class="params-grid">
            <div class="param-row header"><span>API Endpoint</span><span>Method</span><span>Mô tả</span></div>
            <div class="param-row"><span><code>/api/episodes</code></span><span class="badge badge-primary">GET</span><span>Danh sách episodes (limit=100)</span></div>
            <div class="param-row"><span><code>/api/episodes/:id</code></span><span class="badge badge-primary">GET</span><span>Chi tiết một episode</span></div>
            <div class="param-row"><span><code>/api/control</code></span><span class="badge badge-primary">GET</span><span>Đọc control state</span></div>
            <div class="param-row"><span><code>/api/control</code></span><span class="badge badge-success">POST</span><span>Cập nhật control state</span></div>
            <div class="param-row"><span><code>/api/evolution/status</code></span><span class="badge badge-primary">GET</span><span>Trạng thái evo block</span></div>
            <div class="param-row"><span><code>/api/evolution/run</code></span><span class="badge badge-success">POST</span><span>Trigger offline evolution ngay</span></div>
          </div>
        </section>

        <!-- ── CONFIG ── -->
        <section id="docs-section-config" class="docs-section">
          <h2 class="section-title">⚙️ Config & Settings</h2>
          <div class="module-path">tradeharness/config/settings.py · .env</div>
          <p class="section-desc">Toàn bộ config được load từ environment variables (hoặc <code>.env</code> file). <code>load_settings()</code> trả về frozen dataclass.</p>

          <div class="callout callout-warning">
            <strong>Override từ Control State:</strong> Supervisor overrides <code>trade_strategy_mode</code>, <code>hold_seconds</code>, <code>cooldown_seconds</code>, và tất cả risk params bằng giá trị từ <code>state.json</code> — cho phép thay đổi live mà không cần restart.
          </div>
        </section>

        <!-- ── DATA FLOW ── -->
        <section id="docs-section-dataflow" class="docs-section">
          <h2 class="section-title">🌊 Data Flow End-to-End</h2>
          <p class="section-desc">Luồng data hoàn chỉnh từ khi supervisor tick đến khi episode được ghi vào log:</p>

          <div class="flow-diagram">
            <div class="flow-row">
              <div class="flow-node source">Binance API<br/><small>50 candles 5m</small></div>
              <div class="flow-arrow">→</div>
              <div class="flow-node process">RSI Calculator<br/><small>period=7</small></div>
              <div class="flow-arrow">→</div>
              <div class="flow-node process">build_plan()<br/><small>LONG/SHORT/HOLD</small></div>
            </div>
            <div class="flow-down">↓</div>
            <div class="flow-row reverse">
              <div class="flow-node guard">Risk Guard<br/><small>ALLOW/BLOCK/FORCE_CLOSE</small></div>
              <div class="flow-arrow">←</div>
              <div class="flow-node source">get_balance()<br/><small>USDT balance</small></div>
            </div>
            <div class="flow-down">↓ (if ALLOW)</div>
            <div class="flow-row">
              <div class="flow-node llm">LLM Veto<br/><small>confidence 0-100%</small></div>
              <div class="flow-arrow">→</div>
              <div class="flow-node process">Action Gate<br/><small>pre-condition check</small></div>
              <div class="flow-arrow">→</div>
              <div class="flow-node execute">Binance Execute<br/><small>MARKET order</small></div>
            </div>
            <div class="flow-down">↓</div>
            <div class="flow-row">
              <div class="flow-node storage">episodes.jsonl<br/><small>trajectory log</small></div>
              <div class="flow-arrow">→</div>
              <div class="flow-node storage">UI Visualizer<br/><small>real-time display</small></div>
              <div class="flow-arrow">→</div>
              <div class="flow-node storage">Evo Block<br/><small>offline learning</small></div>
            </div>
          </div>
        </section>

        <!-- ── ENV VARS ── -->
        <section id="docs-section-envvars" class="docs-section">
          <h2 class="section-title">📋 Environment Variables</h2>

          <div class="params-grid">
            <div class="param-row header"><span>Variable</span><span>Default</span><span>Mô tả</span></div>

            <div class="param-row group-header"><span colspan="3">🔐 Credentials</span></div>
            <div class="param-row"><span><code>BINANCE_API_KEY</code></span><span class="muted">required</span><span>Testnet API key</span></div>
            <div class="param-row"><span><code>BINANCE_API_SECRET</code></span><span class="muted">required</span><span>Testnet API secret</span></div>
            <div class="param-row"><span><code>EVALUATOR_API_KEY</code></span><span class="muted">""</span><span>LLMGate API key cho evaluator</span></div>

            <div class="param-row group-header"><span colspan="3">📊 Trading</span></div>
            <div class="param-row"><span><code>SYMBOL</code></span><span class="val mono">BTCUSDT</span><span>Trading pair</span></div>
            <div class="param-row"><span><code>CANDLE_INTERVAL</code></span><span class="val mono">5m</span><span>Timeframe</span></div>
            <div class="param-row"><span><code>CANDLE_LIMIT</code></span><span class="val mono">50</span><span>Số candles fetch</span></div>
            <div class="param-row"><span><code>TRADE_STRATEGY_MODE</code></span><span class="val mono">rsi_strategy</span><span>Strategy mode</span></div>
            <div class="param-row"><span><code>TRADE_ENTRY_QUANTITY_BTC</code></span><span class="val mono">0.008</span><span>Kích thước lệnh (BTC)</span></div>
            <div class="param-row"><span><code>TRADE_HOLD_SECONDS</code></span><span class="val mono">300</span><span>Thời gian giữ vị thế</span></div>
            <div class="param-row"><span><code>TRADE_COOLDOWN_SECONDS</code></span><span class="val mono">60</span><span>Cooldown sau đóng lệnh</span></div>
            <div class="param-row"><span><code>DRY_RUN</code></span><span class="val mono">false</span><span>Simulate không execute thật</span></div>
            <div class="param-row"><span><code>POLL_INTERVAL_SECONDS</code></span><span class="val mono">60</span><span>Tần suất supervisor loop</span></div>

            <div class="param-row group-header"><span colspan="3">🛡️ Risk</span></div>
            <div class="param-row"><span><code>TRADE_RISK_MAX_DAILY_LOSS_USDT</code></span><span class="val mono">50</span><span>Giới hạn lỗ ngày</span></div>
            <div class="param-row"><span><code>TRADE_RISK_MAX_OPEN_POSITIONS</code></span><span class="val mono">1</span><span>Số vị thế tối đa</span></div>
            <div class="param-row"><span><code>TRADE_RISK_LOSS_COOLDOWN_SECONDS</code></span><span class="val mono">1800</span><span>Cooldown sau thua (30 phút)</span></div>
            <div class="param-row"><span><code>TRADE_RISK_HARD_STOP_CANDLE_RANGE_PCT</code></span><span class="val mono">2.0</span><span>Max volatility % cho phép</span></div>

            <div class="param-row group-header"><span colspan="3">🧠 LLM</span></div>
            <div class="param-row"><span><code>LMSTUDIO_BASE_URL</code></span><span class="val mono">192.168.10.17:1234</span><span>LMStudio server URL</span></div>
            <div class="param-row"><span><code>LMSTUDIO_MODEL</code></span><span class="val mono">google/gemma-4-e2b</span><span>Model cho trading decisions</span></div>
            <div class="param-row"><span><code>EVALUATOR_MODEL</code></span><span class="val mono">gpt-5.4</span><span>Model cho evolution evaluator</span></div>

            <div class="param-row group-header"><span colspan="3">🧬 Evolution</span></div>
            <div class="param-row"><span><code>TRAJECTORY_LOG_PATH</code></span><span class="val mono">var/trajectories/episodes.jsonl</span><span>Episode log file</span></div>
            <div class="param-row"><span><code>EVOLUTION_OUTPUT_DIR</code></span><span class="val mono">var/evolution</span><span>Evo output directory</span></div>
            <div class="param-row"><span><code>EVOLUTION_MINIMUM_SUPPORT</code></span><span class="val mono">1</span><span>Min episodes to trigger evolution</span></div>
          </div>

          <div class="callout callout-info" style="margin-top: 2rem;">
            <strong>Quick start:</strong> Copy <code>.env.example</code> → <code>.env</code>, điền API keys, chạy <code>python3 -m tradeharness.supervisor</code>. UI available tại <code>http://localhost:8080</code>.
          </div>
        </section>

        <div class="docs-footer">
          <p>TradeHarness · feat/rsi-crossover-strategy · Generated {new Date().toLocaleDateString('vi-VN')}</p>
        </div>

      </div>
    </div>
  </div>
</div>

<style>
  .docs-overlay {
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, 0.6);
    backdrop-filter: blur(4px);
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    animation: fadeInOverlay 0.2s ease;
  }

  @keyframes fadeInOverlay {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  .docs-container {
    width: 95vw;
    height: 92vh;
    max-width: 1400px;
    background: var(--bg-main);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    box-shadow: 0 25px 60px rgba(0,0,0,0.15);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  }

  @keyframes slideUp {
    from { opacity: 0; transform: translateY(20px) scale(0.98); }
    to { opacity: 1; transform: translateY(0) scale(1); }
  }

  /* Top bar */
  .docs-topbar {
    height: 56px;
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border-bottom: 1px solid rgba(255,255,255,0.08);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 1.5rem;
    flex-shrink: 0;
  }

  .docs-topbar-left {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .docs-logo-icon {
    color: #3b82f6;
    filter: drop-shadow(0 0 6px rgba(59, 130, 246, 0.5));
  }

  .docs-title {
    font-size: 0.9375rem;
    font-weight: 700;
    color: #f1f5f9;
    letter-spacing: -0.01em;
  }

  .docs-version-badge {
    font-size: 0.6875rem;
    font-family: var(--font-mono);
    color: #64748b;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 999px;
    padding: 0.125rem 0.5rem;
  }

  .docs-close-btn {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.375rem 0.875rem;
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: var(--radius-sm);
    color: #94a3b8;
    font-size: 0.8125rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }

  .docs-close-btn:hover {
    background: rgba(255,255,255,0.14);
    color: #f1f5f9;
  }

  /* Body layout */
  .docs-body {
    display: flex;
    flex: 1;
    overflow: hidden;
  }

  /* Sidebar nav */
  .docs-nav {
    width: 220px;
    flex-shrink: 0;
    background: var(--bg-sidebar);
    border-right: 1px solid var(--border-color);
    overflow-y: auto;
    padding: 1rem 0.75rem;
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
  }

  .docs-nav-header {
    font-size: 0.6875rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    padding: 0 0.5rem;
    margin-bottom: 0.5rem;
  }

  .docs-nav-group {
    font-size: 0.6875rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    padding: 0.75rem 0.5rem 0.25rem;
    margin-top: 0.25rem;
    border-top: 1px solid var(--border-color);
  }

  .docs-nav-item {
    width: 100%;
    text-align: left;
    padding: 0.4375rem 0.625rem;
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--text-secondary);
    border-radius: var(--radius-sm);
    transition: all 0.15s;
    cursor: pointer;
  }

  .docs-nav-item:hover {
    background: var(--bg-panel-hover);
    color: var(--text-primary);
  }

  .docs-nav-item.active {
    background: var(--color-primary-light);
    color: var(--color-primary);
    font-weight: 600;
  }

  /* Content area */
  .docs-content {
    flex: 1;
    overflow-y: auto;
    padding: 0;
    scroll-behavior: smooth;
  }

  .docs-section {
    padding: 2.5rem 3rem;
    border-bottom: 1px solid var(--border-color);
  }

  .docs-section:last-of-type {
    border-bottom: none;
  }

  /* Hero */
  .section-hero {
    text-align: center;
    padding: 2rem 0 1rem;
  }

  .hero-badge {
    display: inline-block;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--color-primary);
    background: var(--color-primary-light);
    border: 1px solid rgba(37,99,235,0.2);
    border-radius: 999px;
    padding: 0.25rem 0.875rem;
    margin-bottom: 1rem;
  }

  .hero-title {
    font-size: 3rem;
    font-weight: 900;
    letter-spacing: -0.04em;
    color: var(--text-primary);
    margin-bottom: 1rem;
    background: linear-gradient(135deg, #0f172a 0%, #3b82f6 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  .hero-sub {
    font-size: 1.0625rem;
    color: var(--text-secondary);
    max-width: 600px;
    margin: 0 auto 2rem;
    line-height: 1.7;
  }

  .hero-stats {
    display: flex;
    justify-content: center;
    gap: 2rem;
    flex-wrap: wrap;
  }

  .hstat {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.25rem;
  }

  .hstat-num {
    font-size: 1.75rem;
    font-weight: 800;
    color: var(--color-primary);
    font-family: var(--font-mono);
  }

  .hstat-label {
    font-size: 0.75rem;
    color: var(--text-muted);
    font-weight: 500;
  }

  /* Sections */
  .section-title {
    font-size: 1.5rem;
    font-weight: 800;
    color: var(--text-primary);
    letter-spacing: -0.02em;
    margin-bottom: 0.5rem;
  }

  .module-path {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--color-primary);
    background: var(--color-primary-light);
    border: 1px solid rgba(37,99,235,0.15);
    border-radius: var(--radius-sm);
    padding: 0.25rem 0.625rem;
    display: inline-block;
    margin-bottom: 1rem;
  }

  .section-desc {
    color: var(--text-secondary);
    font-size: 0.9375rem;
    line-height: 1.7;
    margin-bottom: 1.5rem;
  }

  .subsection-title {
    font-size: 1rem;
    font-weight: 700;
    color: var(--text-primary);
    margin: 1.5rem 0 0.75rem;
  }

  /* Architecture diagram */
  .arch-diagram {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
    padding: 1.5rem;
    background: var(--bg-panel);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
  }

  .arch-layer {
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
  }

  .arch-arrow {
    font-size: 0.75rem;
    color: var(--text-muted);
    font-weight: 500;
    font-family: var(--font-mono);
  }

  .layer-label {
    font-size: 0.6875rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
  }

  .arch-blocks {
    display: flex;
    gap: 0.625rem;
    flex-wrap: wrap;
    justify-content: center;
  }

  .arch-block {
    padding: 0.5rem 1rem;
    border-radius: var(--radius-sm);
    font-size: 0.8125rem;
    font-weight: 600;
    background: var(--bg-panel-hover);
    border: 1px solid var(--border-color);
    color: var(--text-secondary);
  }

  .arch-block.primary { background: var(--color-primary-light); color: var(--color-primary); border-color: rgba(37,99,235,0.2); }
  .arch-block.success { background: var(--color-success-light); color: var(--color-success); border-color: var(--color-success-border); }
  .arch-block.warning { background: var(--color-warning-light); color: var(--color-warning); border-color: var(--color-warning-border); }
  .arch-block.danger  { background: var(--color-danger-light);  color: var(--color-danger);  border-color: var(--color-danger-border); }
  .arch-block.info    { background: rgba(139,92,246,0.06); color: #7c3aed; border-color: rgba(139,92,246,0.2); }
  .arch-block.evolution { background: rgba(236,72,153,0.06); color: #db2777; border-color: rgba(236,72,153,0.2); }

  /* Feature grid */
  .feature-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  .feature-card {
    background: var(--bg-panel);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 1.25rem;
    transition: border-color 0.2s;
  }

  .feature-card:hover { border-color: var(--border-color-hover); }

  .feature-icon {
    font-size: 1.5rem;
    margin-bottom: 0.625rem;
  }

  .feature-card h4 {
    font-size: 0.875rem;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 0.375rem;
  }

  .feature-card p {
    font-size: 0.8125rem;
    color: var(--text-secondary);
    line-height: 1.6;
  }

  /* Flow steps */
  .flow-steps {
    display: flex;
    flex-direction: column;
    gap: 0;
    margin-bottom: 1.5rem;
    position: relative;
  }

  .flow-step {
    display: flex;
    gap: 1rem;
    align-items: flex-start;
    padding: 1rem 0;
    border-bottom: 1px solid var(--border-color);
  }

  .flow-step:last-child { border-bottom: none; }

  .step-num {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: var(--color-primary);
    color: white;
    font-size: 0.75rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .step-body h4 {
    font-size: 0.875rem;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 0.25rem;
  }

  .step-body p {
    font-size: 0.8125rem;
    color: var(--text-secondary);
    line-height: 1.6;
  }

  /* Code blocks */
  .code-block {
    background: #0f172a;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: var(--radius-md);
    margin: 1rem 0;
    overflow: hidden;
  }

  .code-label {
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #64748b;
    padding: 0.5rem 1rem;
    border-bottom: 1px solid rgba(255,255,255,0.06);
  }

  .code-block pre {
    padding: 1rem;
    font-family: var(--font-mono);
    font-size: 0.8125rem;
    color: #94a3b8;
    overflow-x: auto;
    line-height: 1.7;
    white-space: pre-wrap;
    word-break: break-all;
  }

  /* Callouts */
  .callout {
    padding: 0.875rem 1rem;
    border-radius: var(--radius-sm);
    font-size: 0.8125rem;
    line-height: 1.6;
    margin: 1rem 0;
  }

  .callout-info    { background: rgba(139,92,246,0.06); border-left: 3px solid #7c3aed; color: var(--text-secondary); }
  .callout-warning { background: var(--color-warning-light); border-left: 3px solid var(--color-warning); color: var(--text-secondary); }
  .callout-success { background: var(--color-success-light); border-left: 3px solid var(--color-success); color: var(--text-secondary); }

  .callout strong { color: var(--text-primary); }

  /* Params grid */
  .params-grid {
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    overflow: hidden;
    font-size: 0.8125rem;
    margin-bottom: 1.5rem;
  }

  .param-row {
    display: grid;
    grid-template-columns: 2fr 1.2fr 1.5fr;
    gap: 0;
    padding: 0.625rem 1rem;
    border-bottom: 1px solid var(--border-color);
    align-items: center;
  }

  .param-row:last-child { border-bottom: none; }

  .param-row.header {
    background: var(--bg-panel-hover);
    font-weight: 700;
    font-size: 0.6875rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-muted);
  }

  .param-row.group-header {
    background: linear-gradient(135deg, var(--color-primary-light), transparent);
    font-weight: 700;
    font-size: 0.75rem;
    color: var(--color-primary);
    grid-template-columns: 1fr;
  }

  .param-row code {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    background: var(--bg-panel-hover);
    padding: 0.125rem 0.375rem;
    border-radius: 4px;
    color: var(--color-primary);
  }

  .param-row .val { font-family: var(--font-mono); font-size: 0.75rem; font-weight: 600; color: var(--text-primary); }
  .param-row .muted { color: var(--text-muted); font-style: italic; }

  /* Risk rules */
  .risk-rules {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    margin-bottom: 1.5rem;
  }

  .risk-rule {
    display: flex;
    gap: 1rem;
    align-items: flex-start;
    padding: 1rem;
    background: var(--bg-panel);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
  }

  .risk-icon {
    font-size: 1.25rem;
    flex-shrink: 0;
  }

  .risk-body h4 { font-size: 0.875rem; font-weight: 700; color: var(--text-primary); margin-bottom: 0.25rem; }
  .risk-body p  { font-size: 0.8125rem; color: var(--text-secondary); line-height: 1.6; }

  /* LLM flow */
  .llm-flow {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
  }

  .llm-step {
    flex: 1;
    min-width: 160px;
    background: var(--bg-panel);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 1rem;
  }

  .llm-step-icon { font-size: 1.25rem; margin-bottom: 0.5rem; }
  .llm-step-body h4 { font-size: 0.8125rem; font-weight: 700; color: var(--text-primary); margin-bottom: 0.25rem; }
  .llm-step-body p  { font-size: 0.75rem; color: var(--text-secondary); line-height: 1.5; }

  .llm-arrow { align-self: center; font-size: 1.25rem; color: var(--text-muted); flex-shrink: 0; }

  /* Decision tree */
  .decision-tree {
    background: var(--bg-panel);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 1.25rem;
    font-size: 0.8125rem;
    margin-bottom: 1.5rem;
  }

  .dtree-node.root {
    display: inline-block;
    background: var(--color-primary);
    color: white;
    padding: 0.375rem 1rem;
    border-radius: 999px;
    font-weight: 700;
    font-size: 0.875rem;
    margin-bottom: 0.75rem;
  }

  .dtree-branch { padding-left: 1rem; border-left: 2px solid var(--border-color); }
  .dtree-condition { color: var(--text-secondary); font-style: italic; margin: 0.375rem 0 0.25rem; }
  .dtree-children { display: flex; gap: 2rem; flex-wrap: wrap; margin-top: 0.25rem; }
  .dtree-path { width: 100%; }
  .dtree-leaf { padding: 0.25rem 0; padding-left: 1rem; border-left: 2px solid var(--border-color); margin-bottom: 0.375rem; }
  .dtree-leaf.yes, .dtree-leaf.no { border-color: transparent; padding-left: 0; flex: 1; min-width: 160px; }
  .dtree-leaf.success { color: var(--color-danger); font-weight: 700; }
  .dtree-leaf.buy  { color: var(--color-success); font-weight: 700; }
  .dtree-leaf.sell { color: var(--color-danger); font-weight: 700; }
  .dtree-leaf.neutral { color: var(--text-muted); }

  /* Flow diagram */
  .flow-diagram {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    align-items: center;
    padding: 1.5rem;
    background: var(--bg-panel);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
  }

  .flow-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
    justify-content: center;
  }

  .flow-row.reverse { flex-direction: row-reverse; }

  .flow-node {
    padding: 0.625rem 1rem;
    border-radius: var(--radius-md);
    font-size: 0.75rem;
    font-weight: 600;
    text-align: center;
    border: 1px solid;
    min-width: 130px;
  }

  .flow-node small { font-weight: 400; font-family: var(--font-mono); display: block; margin-top: 0.125rem; opacity: 0.8; }

  .flow-node.source  { background: var(--color-primary-light); color: var(--color-primary); border-color: rgba(37,99,235,0.25); }
  .flow-node.process { background: var(--bg-panel-hover); color: var(--text-secondary); border-color: var(--border-color); }
  .flow-node.guard   { background: var(--color-danger-light); color: var(--color-danger); border-color: var(--color-danger-border); }
  .flow-node.llm     { background: var(--color-warning-light); color: var(--color-warning); border-color: var(--color-warning-border); }
  .flow-node.execute { background: var(--color-success-light); color: var(--color-success); border-color: var(--color-success-border); }
  .flow-node.storage { background: rgba(139,92,246,0.06); color: #7c3aed; border-color: rgba(139,92,246,0.2); }

  .flow-arrow  { color: var(--text-muted); font-size: 1rem; }
  .flow-down   { font-size: 0.75rem; color: var(--text-muted); font-family: var(--font-mono); }

  /* Footer */
  .docs-footer {
    padding: 2rem 3rem;
    text-align: center;
    color: var(--text-muted);
    font-size: 0.75rem;
    border-top: 1px solid var(--border-color);
  }
</style>
