<script>
  import CandleChart from "./CandleChart.svelte";

  export let episode = null;

  let expandedThoughts = {};
  let expandedLogs = {};

  $: steps = episode?.steps || [];
  $: episodeOutcome = episode?.final_outcome || {};

  function toggleThought(idx) {
    expandedThoughts[idx] = !expandedThoughts[idx];
  }

  function toggleLog(idx) {
    expandedLogs[idx] = !expandedLogs[idx];
  }

  function formatTime(isoStr) {
    if (!isoStr) return "—";
    try {
      return new Date(isoStr).toLocaleTimeString();
    } catch (_) {
      return isoStr;
    }
  }

  function cleanJson(data) {
    if (!data) return "";
    if (typeof data === "string") {
      try {
        return JSON.stringify(JSON.parse(data), null, 2);
      } catch (_) {
        return data;
      }
    }
    return JSON.stringify(data, null, 2);
  }

  function getDecisionColorClass(decision) {
    if (!decision) return "dec-none";
    const d = decision.toUpperCase();
    if (d === "EXECUTE" || d === "ALLOW") return "dec-allow";
    if (d === "BLOCK" || d === "STOP" || d === "FORCE_CLOSE") return "dec-block";
    if (d === "WARN" || d === "HOLD") return "dec-warn";
    return "dec-none";
  }

  // Parse final response string if it is double serialized
  function tryParseFinalResponse(text) {
    if (!text) return "";
    try {
      const parsed = JSON.parse(text);
      if (parsed.final) return parsed.final;
      return text;
    } catch (_) {
      return text;
    }
  }
</script>

<div class="flow-visualizer">
  {#if !episode}
    <div class="no-selection">
      <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" class="icon">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
      </svg>
      <h3>Select a TradeHarness Run to Visualize</h3>
      <p>Choose an episode from the runs log sidebar to trace the decision flow step-by-step.</p>
    </div>
  {:else}
    <div class="visualizer-header animate-fade">
      <div class="ep-info">
        <div class="title-row">
          <h1>Run Tracing: <span class="highlight font-mono">{episode.episode_id}</span></h1>
          <span class="badge {episode.final_status === 'SUCCESS' ? 'badge-success' : 'badge-danger'}">
            {episode.final_status}
          </span>
        </div>
        <p class="subtitle">
          Task ID: <span class="font-mono">{episode.task_id}</span> · 
          Harness Version: <span class="badge badge-primary">{episode.harness_version}</span> ·
          Started: <span class="font-mono">{formatTime(episode.started_at)}</span> ·
          Ended: <span class="font-mono">{formatTime(episode.ended_at)}</span>
        </p>
      </div>
    </div>

    <div class="steps-timeline animate-fade">
      {#each steps as step, idx (step.step_index)}
        {@const observation = step.observation || {}}
        {@const marketSnapshot = observation.market_snapshot || null}
        {@const positionState = observation.position_state || null}
        {@const strategyState = observation.strategy_state || null}
        {@const riskState = observation.risk_state || null}
        {@const action = step.action || {}}
        {@const intervention = step.harness_intervention || {}}
        {@const feedback = step.environment_feedback || {}}
        {@const isRiskBlock = intervention.layer === "risk" && intervention.decision === "BLOCK"}
        {@const isGateBlock = intervention.layer === "gate" && intervention.decision === "BLOCK"}
        {@const isTrajStop = intervention.layer === "trajectory" && intervention.decision === "STOP"}

        <div class="timeline-step">
          <!-- Step Number badge Left -->
          <div class="step-badge-col">
            <div class="step-num font-mono">{step.step_index}</div>
            {#if idx < steps.length - 1}
              <div class="step-line"></div>
            {/if}
          </div>

          <!-- Step Cards Right -->
          <div class="step-card-col">
            <div class="step-header">
              <h3>Step {step.step_index}: State Observation & Thought</h3>
              {#if positionState}
                <div class="pos-badge code-font {positionState.side === 'LONG' ? 'long' : positionState.side === 'SHORT' ? 'short' : 'flat'}">
                  Position: {positionState.side} ({positionState.quantity || 0} BTC)
                </div>
              {/if}
            </div>

            <!-- Block 1: Observations (Candle chart, risk state, strategy state) -->
            <div class="grid-sub-cards">
              {#if marketSnapshot}
                <div class="sub-card">
                  <div class="card-tag">Market Snapshot</div>
                  <CandleChart 
                    candles={marketSnapshot.candles} 
                    price={marketSnapshot.price} 
                    symbol={marketSnapshot.symbol || episode.symbol} 
                  />
                </div>
              {/if}

              {#if riskState || strategyState}
                <div class="sub-card flex-col gap-sm">
                  <div class="card-tag">Internal States</div>
                  {#if strategyState && strategyState.opened_at}
                    <div class="state-indicator font-mono">
                      <span class="label">Strategy Status:</span>
                      <span class="val">Active {strategyState.side} entered {formatTime(strategyState.opened_at)}</span>
                    </div>
                  {/if}
                  
                  {#if riskState}
                    <div class="state-indicator font-mono">
                      <span class="label">Daily Start Bal:</span>
                      <span class="val">${riskState.day_start_balance_usdt ? riskState.day_start_balance_usdt.toFixed(2) : "0.00"}</span>
                    </div>
                    {#if riskState.hard_stop_reason}
                      <div class="state-indicator font-mono error-text">
                        <span class="label">Hard Stop:</span>
                        <span class="val">{riskState.hard_stop_reason}</span>
                      </div>
                    {/if}
                  {/if}
                </div>
              {/if}
            </div>

            <!-- Block 2: Agent Thought & Intent -->
            <div class="flow-node thought-node">
              <div class="node-icon bg-primary">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
              <div class="node-content">
                <div class="node-header">
                  <h4>Agent Thought & Strategy Rationale</h4>
                  <button class="toggle-btn" on:click={() => toggleThought(step.step_index)}>
                    {expandedThoughts[step.step_index] ? "Collapse" : "Expand"}
                  </button>
                </div>
                <p class="thought-summary">
                  {step.decision_summary ? tryParseFinalResponse(step.decision_summary) : "State inspection completed."}
                </p>
                {#if expandedThoughts[step.step_index] && step.decision_summary}
                  <pre class="raw-box font-mono">{cleanJson(step.decision_summary)}</pre>
                {/if}
              </div>
            </div>

            <!-- Visual Flow Connector -->
            <div class="flow-connector-line"></div>

            <!-- Block 3: Verification Gateways (Harness Interventions) -->
            <div class="gateway-block">
              <div class="gateway-header">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
                <span>Harness Safety Verification Layers</span>
              </div>
              
              <div class="gateways-grid">
                <!-- Gate 1: Skill Layer -->
                <div class="gate-status pass">
                  <div class="gate-status-indicator"></div>
                  <div class="gate-info">
                    <span class="gate-name">Procedural Skill</span>
                    <span class="gate-outcome">Injected</span>
                  </div>
                </div>

                <!-- Gate 2: Risk Guard -->
                <div class="gate-status {isRiskBlock ? 'blocked' : 'pass'}">
                  <div class="gate-status-indicator"></div>
                  <div class="gate-info">
                    <span class="gate-name">Live Risk Guard</span>
                    <span class="gate-outcome">{isRiskBlock ? 'Blocked' : 'Pass'}</span>
                  </div>
                </div>

                <!-- Gate 3: Action Realization -->
                <div class="gate-status {isGateBlock ? 'blocked' : 'pass'}">
                  <div class="gate-status-indicator"></div>
                  <div class="gate-info">
                    <span class="gate-name">Action Realization</span>
                    <span class="gate-outcome">{isGateBlock ? 'Blocked' : 'Pass'}</span>
                  </div>
                </div>

                <!-- Gate 4: Trajectory Regulation -->
                <div class="gate-status {isTrajStop ? 'blocked' : 'pass'}">
                  <div class="gate-status-indicator"></div>
                  <div class="gate-info">
                    <span class="gate-name">Trajectory Monitor</span>
                    <span class="gate-outcome">{isTrajStop ? 'Blocked' : 'Pass'}</span>
                  </div>
                </div>
              </div>

              <!-- Gate Decision Banner -->
              <div class="gate-verdict {getDecisionColorClass(intervention.decision)}">
                <span class="label">Harness Layer Verdict:</span>
                <span class="val code-font">{intervention.decision || 'ALLOW'}</span>
                {#if intervention.reason}
                  <p class="verdict-reason font-mono">{intervention.reason}</p>
                {/if}
              </div>
            </div>

            <!-- Visual Flow Connector -->
            <div class="flow-connector-line"></div>

            <!-- Block 4: Target Tool Call Action & Exchange Feedback -->
            <div class="flow-node action-node">
              <div class="node-icon {action.tool ? 'bg-warn' : 'bg-success'}">
                {#if action.tool}
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                {:else}
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                {/if}
              </div>
              <div class="node-content">
                <div class="node-header">
                  <h4>
                    {#if action.tool}
                      Proposed API Call: <span class="highlight font-mono">{action.tool}</span>
                    {:else}
                      Final Intent Emitted
                    {/if}
                  </h4>
                </div>
                
                {#if action.arguments}
                  <div class="args-list font-mono font-sm">
                    {#each Object.entries(action.arguments) as [key, val]}
                      <span class="arg-item">{key}: <span class="val">{val}</span></span>
                    {/each}
                  </div>
                {/if}

                {#if feedback}
                  <div class="environment-feedback font-mono">
                    <div class="feedback-header">
                      <span>Exchange Output / API Feedback:</span>
                      <button class="toggle-btn" on:click={() => toggleLog(step.step_index)}>
                        {expandedLogs[step.step_index] ? "Hide JSON" : "Show JSON"}
                      </button>
                    </div>
                    
                    {#if feedback.error}
                      <p class="error-text">{feedback.error}</p>
                    {:else if feedback.blocked}
                      <p class="warn-text">Blocked: {feedback.feedback || "Action realizer check triggered."}</p>
                    {:else if feedback.status === "submitted" || feedback.orderId}
                      <p class="success-text">Order Submitted: ID {feedback.orderId || feedback.exchange_response?.orderId || "N/A"}</p>
                    {:else if feedback.price || feedback.available_balance}
                      <p class="info-text">
                        Data retrieved: 
                        {#if feedback.price}Price ${feedback.price}{/if}
                        {#if feedback.available_balance}Available ${feedback.available_balance.toFixed(2)}{/if}
                      </p>
                    {/if}

                    {#if expandedLogs[step.step_index]}
                      <pre class="raw-box font-mono mt-sm">{cleanJson(feedback)}</pre>
                    {/if}
                  </div>
                {/if}
              </div>
            </div>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .flow-visualizer {
    flex: 1;
    height: 100%;
    overflow-y: auto;
    background-color: var(--bg-main);
    display: flex;
    flex-direction: column;
  }

  .no-selection {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    flex: 1;
    color: var(--text-muted);
    padding: 3rem;
    text-align: center;
    gap: 1rem;
    max-width: 600px;
    margin: 0 auto;
  }

  .no-selection .icon {
    color: var(--border-color);
  }

  .no-selection h3 {
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--text-primary);
  }

  .visualizer-header {
    padding: 1.5rem;
    border-bottom: 1px solid var(--border-color);
    background-color: var(--bg-sidebar);
  }

  .title-row {
    display: flex;
    align-items: center;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .visualizer-header h1 {
    font-size: 1.375rem;
    font-weight: 800;
  }

  .highlight {
    color: var(--color-primary);
  }

  .subtitle {
    font-size: 0.8125rem;
    color: var(--text-secondary);
    margin-top: 0.25rem;
  }

  .steps-timeline {
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
  }

  .timeline-step {
    display: flex;
    gap: 1.5rem;
  }

  .step-badge-col {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 32px;
    flex-shrink: 0;
  }

  .step-num {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background-color: var(--bg-panel);
    border: 2px solid var(--border-color);
    color: var(--text-primary);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 0.875rem;
    z-index: 10;
  }

  .step-line {
    width: 2px;
    background-color: var(--border-color);
    flex: 1;
    margin: 0.25rem 0;
  }

  .step-card-col {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding-bottom: 2rem;
  }

  .step-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .step-header h3 {
    font-size: 1.125rem;
    font-weight: 700;
    color: var(--text-primary);
  }

  .pos-badge {
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0.125rem 0.5rem;
    border-radius: 4px;
    border: 1px solid var(--border-color);
  }

  .pos-badge.long {
    background-color: var(--color-success-light);
    color: var(--color-success);
    border-color: var(--color-success-border);
  }

  .pos-badge.short {
    background-color: var(--color-danger-light);
    color: var(--color-danger);
    border-color: var(--color-danger-border);
  }

  .pos-badge.flat {
    background-color: var(--bg-panel);
    color: var(--text-secondary);
  }

  .grid-sub-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .sub-card {
    background-color: var(--bg-panel);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 0.75rem;
    position: relative;
  }

  .card-tag {
    font-size: 0.675rem;
    font-weight: 700;
    text-transform: uppercase;
    color: var(--text-muted);
    letter-spacing: 0.05em;
    margin-bottom: 0.5rem;
  }

  .flex-col {
    display: flex;
    flex-direction: column;
  }

  .gap-sm {
    gap: 0.5rem;
  }

  .state-indicator {
    display: flex;
    justify-content: space-between;
    font-size: 0.75rem;
    border-bottom: 1px dashed var(--border-color);
    padding-bottom: 0.25rem;
  }

  .state-indicator .label {
    color: var(--text-secondary);
  }

  .state-indicator .val {
    color: var(--text-primary);
    font-weight: 500;
  }

  /* Node Graph elements */
  .flow-node {
    display: flex;
    gap: 1rem;
    background-color: var(--bg-panel);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 1rem;
    position: relative;
  }

  .node-icon {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #ffffff;
    flex-shrink: 0;
  }

  .bg-primary { background-color: var(--color-primary); }
  .bg-warn { background-color: var(--color-warning); }
  .bg-success { background-color: var(--color-success); }

  .node-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .node-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .node-header h4 {
    font-size: 0.9375rem;
    font-weight: 700;
    color: var(--text-primary);
  }

  .thought-summary {
    font-size: 0.875rem;
    color: var(--text-secondary);
  }

  .toggle-btn {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--color-primary);
  }

  .toggle-btn:hover {
    color: var(--text-primary);
  }

  .raw-box {
    background-color: var(--bg-main);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    padding: 0.75rem;
    font-size: 0.75rem;
    color: var(--text-secondary);
    overflow-x: auto;
    white-space: pre-wrap;
    max-height: 200px;
    overflow-y: auto;
  }

  .flow-connector-line {
    width: 2px;
    height: 20px;
    background-color: var(--border-color);
    margin-left: 28px;
  }

  /* Gateway Interventions */
  .gateway-block {
    background-color: var(--bg-panel);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .gateway-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.8125rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
  }

  .gateways-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 0.75rem;
  }

  .gate-status {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    background-color: var(--bg-main);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    padding: 0.5rem;
  }

  .gate-status-indicator {
    width: 10px;
    height: 10px;
    border-radius: 50%;
  }

  .gate-status.pass .gate-status-indicator {
    background-color: var(--color-success);
    box-shadow: 0 0 8px var(--color-success);
  }

  .gate-status.blocked .gate-status-indicator {
    background-color: var(--color-danger);
    box-shadow: 0 0 8px var(--color-danger);
  }

  .gate-info {
    display: flex;
    flex-direction: column;
  }

  .gate-name {
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--text-secondary);
  }

  .gate-outcome {
    font-size: 0.675rem;
    font-weight: 700;
    color: var(--text-muted);
  }

  .gate-status.pass .gate-outcome {
    color: var(--color-success);
  }

  .gate-status.blocked .gate-outcome {
    color: var(--color-danger);
  }

  .gate-verdict {
    border-radius: var(--radius-sm);
    padding: 0.75rem;
    font-size: 0.8125rem;
  }

  .gate-verdict .label {
    font-weight: 600;
    color: var(--text-secondary);
  }

  .gate-verdict .val {
    font-weight: 700;
  }

  .dec-allow {
    background-color: var(--color-success-light);
    border: 1px solid var(--color-success-border);
    color: var(--color-success);
  }

  .dec-block {
    background-color: var(--color-danger-light);
    border: 1px solid var(--color-danger-border);
    color: var(--color-danger);
  }

  .dec-warn {
    background-color: var(--color-warning-light);
    border: 1px solid var(--color-warning-border);
    color: var(--color-warning);
  }

  .dec-none {
    background-color: var(--bg-main);
    border: 1px solid var(--border-color);
    color: var(--text-muted);
  }

  .verdict-reason {
    margin-top: 0.375rem;
    font-size: 0.75rem;
    color: var(--text-primary);
  }

  /* Action Proposed node details */
  .args-list {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
    background-color: var(--bg-main);
    padding: 0.5rem;
    border-radius: var(--radius-sm);
  }

  .arg-item {
    font-size: 0.75rem;
    color: var(--text-secondary);
  }

  .arg-item .val {
    color: var(--text-primary);
    font-weight: 600;
  }

  .environment-feedback {
    background-color: var(--bg-main);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    padding: 0.75rem;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .feedback-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.75rem;
    color: var(--text-muted);
    font-weight: 600;
  }

  .error-text { color: var(--color-danger); }
  .warn-text { color: var(--color-warning); }
  .success-text { color: var(--color-success); }
  .info-text { color: var(--color-primary); }

  .mt-sm { margin-top: 0.5rem; }
</style>
