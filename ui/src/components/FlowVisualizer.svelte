<script>
  import CandleChart from "./CandleChart.svelte";

  export let episode = null;

  let showDetailedTrace = false;
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
      return new Date(isoStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
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

  function getStepOutcomeSummary(step) {
    const feedback = step.environment_feedback || {};
    if (feedback.error) return `Error: ${feedback.error}`;
    if (feedback.blocked) return `Blocked: ${feedback.feedback || 'Safety Layer block'}`;
    if (feedback.status === "submitted" || feedback.orderId) {
      const orderId = feedback.orderId || feedback.exchange_response?.orderId || "N/A";
      return `Order submitted (ID: ${orderId})`;
    }
    if (feedback.price) return `Price: $${feedback.price.toLocaleString()}`;
    if (feedback.available_balance) return `Balance: $${feedback.available_balance.toFixed(2)}`;
    return "Executed successfully";
  }
</script>

<div class="flow-visualizer">
  {#if !episode}
    <div class="no-selection">
      <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" class="icon">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
      </svg>
      <h3>Select a run to view</h3>
      <p>Choose an episode from the runs log sidebar to display its execution details.</p>
    </div>
  {:else}
    <div class="summary-cards-container animate-fade">
      <!-- High Level Verdict Card -->
      <div class="outcome-card">
        <div class="outcome-title">Final Execution Result</div>
        <div class="outcome-value font-mono">
          {episode.termination_reason ? episode.termination_reason.toUpperCase().replace(/_/g, ' ') : 'UNKNOWN'}
        </div>
        <div class="outcome-desc">
          {tryParseFinalResponse(episode.final_outcome?.final || episode.final_outcome || "")}
        </div>
      </div>

      <!-- Compact Steps Overview Table -->
      <div class="steps-table-card">
        <div class="card-header-row">
          <h3>Steps Summary ({steps.length})</h3>
          <button 
            class="btn btn-secondary btn-sm" 
            on:click={() => showDetailedTrace = !showDetailedTrace}
          >
            {showDetailedTrace ? "Hide Detailed Logs" : "Show Detailed Trace Logs"}
          </button>
        </div>
        
        <table class="compact-table font-mono">
          <thead>
            <tr>
              <th width="80">Step</th>
              <th width="200">Proposed Action</th>
              <th width="120">Safety Verdict</th>
              <th>Execution Outcome / Result</th>
            </tr>
          </thead>
          <tbody>
            {#each steps as step (step.step_index)}
              {@const action = step.action || {}}
              {@const intervention = step.harness_intervention || {}}
              <tr>
                <td class="center font-bold">#{step.step_index}</td>
                <td>
                  <span class="action-tag">{action.tool || 'final_response'}</span>
                </td>
                <td>
                  <span class="badge {getDecisionColorClass(intervention.decision)}">
                    {intervention.decision || 'ALLOW'}
                  </span>
                </td>
                <td class="outcome-cell">
                  {getStepOutcomeSummary(step)}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Hidden detailed running trace collapsible panel -->
    {#if showDetailedTrace}
      <div class="steps-timeline animate-fade">
        <h2 class="timeline-title">Detailed Trace Log</h2>
        
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
            <div class="step-badge-col">
              <div class="step-num font-mono">{step.step_index}</div>
              {#if idx < steps.length - 1}
                <div class="step-line"></div>
              {/if}
            </div>

            <div class="step-card-col">
              <div class="step-header">
                <h3>Step {step.step_index}: State & Decision</h3>
                {#if positionState}
                  <div class="pos-badge code-font {positionState.side === 'LONG' ? 'long' : positionState.side === 'SHORT' ? 'short' : 'flat'}">
                    Position: {positionState.side} ({positionState.quantity || 0} BTC)
                  </div>
                {/if}
              </div>

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

              <!-- Thought Node -->
              <div class="flow-node thought-node">
                <div class="node-icon bg-primary">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                </div>
                <div class="node-content">
                  <div class="node-header">
                    <h4>Agent Rationale</h4>
                    <button class="toggle-btn" on:click={() => toggleThought(step.step_index)}>
                      {expandedThoughts[step.step_index] ? "Hide Detail" : "Show Detail"}
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

              <div class="flow-connector-line"></div>

              <!-- Verification Gateways -->
              <div class="gateway-block">
                <div class="gateway-header">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                  </svg>
                  <span>Harness Gateways</span>
                </div>
                
                <div class="gateways-grid">
                  <div class="gate-status pass">
                    <div class="gate-status-indicator"></div>
                    <div class="gate-info"><span class="gate-name">Skills Layer</span></div>
                  </div>
                  <div class="gate-status {isRiskBlock ? 'blocked' : 'pass'}">
                    <div class="gate-status-indicator"></div>
                    <div class="gate-info"><span class="gate-name">Risk Guard</span></div>
                  </div>
                  <div class="gate-status {isGateBlock ? 'blocked' : 'pass'}">
                    <div class="gate-status-indicator"></div>
                    <div class="gate-info"><span class="gate-name">Action Gate</span></div>
                  </div>
                  <div class="gate-status {isTrajStop ? 'blocked' : 'pass'}">
                    <div class="gate-status-indicator"></div>
                    <div class="gate-info"><span class="gate-name">Trajectory</span></div>
                  </div>
                </div>

                <div class="gate-verdict {getDecisionColorClass(intervention.decision)}">
                  <span class="label">Verdict:</span> <span class="val">{intervention.decision || 'ALLOW'}</span>
                  {#if intervention.reason}
                    <p class="verdict-reason font-mono">{intervention.reason}</p>
                  {/if}
                </div>
              </div>

              <div class="flow-connector-line"></div>

              <!-- Proposed API Action -->
              <div class="flow-node action-node">
                <div class="node-icon {action.tool ? 'bg-warn' : 'bg-success'}">
                  {#if action.tool}
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    </svg>
                  {:else}
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  {/if}
                </div>
                <div class="node-content">
                  <h4>
                    {#if action.tool}
                      Proposed Call: <span class="highlight font-mono">{action.tool}</span>
                    {:else}
                      Final Outcome Emitted
                    {/if}
                  </h4>
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
                        <span>API Response:</span>
                        <button class="toggle-btn" on:click={() => toggleLog(step.step_index)}>
                          {expandedLogs[step.step_index] ? "Hide Logs" : "Show Logs"}
                        </button>
                      </div>
                      {#if feedback.error}
                        <p class="error-text">{feedback.error}</p>
                      {:else}
                        <p class="info-text">{getStepOutcomeSummary(step)}</p>
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



  .summary-cards-container {
    padding: 2rem;
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
  }

  .outcome-card {
    background-color: var(--bg-panel);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 1.25rem;
    box-shadow: var(--shadow-sm);
  }

  .outcome-title {
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    color: var(--text-muted);
    letter-spacing: 0.05em;
  }

  .outcome-value {
    font-size: 1.375rem;
    font-weight: 800;
    color: var(--color-primary);
    margin: 0.25rem 0 0.5rem;
  }

  .outcome-desc {
    font-size: 0.875rem;
    color: var(--text-secondary);
    line-height: 1.5;
  }

  .steps-table-card {
    background-color: var(--bg-panel);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 1.25rem;
    box-shadow: var(--shadow-sm);
  }

  .card-header-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
  }

  .card-header-row h3 {
    font-size: 1rem;
    font-weight: 700;
  }

  .compact-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8125rem;
  }

  .compact-table th {
    background-color: var(--bg-main);
    color: var(--text-secondary);
    font-weight: 700;
    text-align: left;
    padding: 0.625rem;
    border-bottom: 1px solid var(--border-color);
  }

  .compact-table td {
    padding: 0.75rem 0.625rem;
    border-bottom: 1px solid var(--border-color);
    color: var(--text-secondary);
  }

  .compact-table tbody tr:hover {
    background-color: var(--bg-panel-hover);
  }

  .center {
    text-align: center;
  }

  .font-bold {
    font-weight: 700;
    color: var(--text-primary) !important;
  }

  .action-tag {
    font-weight: 600;
    color: var(--text-primary);
    background-color: var(--bg-main);
    padding: 0.125rem 0.375rem;
    border-radius: 4px;
    border: 1px solid var(--border-color);
  }

  .outcome-cell {
    color: var(--text-primary) !important;
  }

  /* Detailed trace timeline */
  .steps-timeline {
    padding: 1.5rem;
    border-top: 1px solid var(--border-color);
    background-color: var(--bg-panel-hover);
  }

  .timeline-title {
    font-size: 1.125rem;
    font-weight: 700;
    margin-bottom: 1.5rem;
    color: var(--text-primary);
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
  }

  .card-tag {
    font-size: 0.675rem;
    font-weight: 700;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 0.5rem;
  }

  .state-indicator {
    display: flex;
    justify-content: space-between;
    font-size: 0.75rem;
    border-bottom: 1px dashed var(--border-color);
    padding-bottom: 0.25rem;
  }

  .state-indicator .label { color: var(--text-secondary); }
  .state-indicator .val { color: var(--text-primary); }

  .flow-node {
    display: flex;
    gap: 1rem;
    background-color: var(--bg-panel);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 1rem;
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
    margin-left: 15px;
  }

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
    color: var(--text-muted);
  }

  .gateways-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.5rem;
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
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }

  .gate-status.pass .gate-status-indicator {
    background-color: var(--color-success);
  }

  .gate-status.blocked .gate-status-indicator {
    background-color: var(--color-danger);
  }

  .gate-name {
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--text-secondary);
  }

  .gate-verdict {
    border-radius: var(--radius-sm);
    padding: 0.5rem 0.75rem;
    font-size: 0.8125rem;
  }

  .gate-verdict .label {
    font-weight: 600;
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
    margin-top: 0.25rem;
    font-size: 0.75rem;
  }

  .args-list {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
    background-color: var(--bg-main);
    padding: 0.5rem;
    border-radius: var(--radius-sm);
    margin: 0.5rem 0;
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
  }

  .feedback-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .error-text { color: var(--color-danger); }
  .info-text { color: var(--text-primary); }
  .btn-sm { padding: 0.25rem 0.5rem; font-size: 0.75rem; }
  .font-sm { font-size: 0.75rem; }
  .mt-sm { margin-top: 0.5rem; }
  .gap-sm { gap: 0.5rem; }
  .flex-col { display: flex; flex-direction: column; }
</style>
