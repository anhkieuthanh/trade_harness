<script>
  import CandleChart from "./CandleChart.svelte";

  export let episode = null;
  export let episodes = [];
  export let evolutionStatus = null;
  export let onTriggerEvolution = null;

  let showDetailedTrace = false;
  let expandedThoughts = {};
  let expandedLogs = {};
  let selectedStepIdx = 0;

  let zoomLevel = 1.0;
  function changeZoom(delta) {
    zoomLevel = Math.max(0.5, Math.min(1.5, parseFloat((zoomLevel + delta).toFixed(2))));
  }

  $: if (episode) {
    selectedStepIdx = 0;
  }

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

      <!-- Svelte Flow Step Visualizer Canvas -->
      {#if steps.length > 0}
        {@const step = steps[selectedStepIdx] || steps[0]}
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

        <div class="step-selector-card">
          <div class="card-header-row">
            <h3>Step Flow Visualizer</h3>
            <div class="step-pills">
              {#each steps as s, i}
                <button 
                  class="step-pill {selectedStepIdx === i ? 'active' : ''}" 
                  on:click={() => selectedStepIdx = i}
                >
                  Step #{s.step_index} ({s.action?.tool || 'final_response'})
                </button>
              {/each}
            </div>
          </div>

          <div class="flow-container-rel">
            <!-- Floating Zoom Controls -->
            <div class="zoom-controls">
              <button class="zoom-btn" on:click={() => changeZoom(-0.1)} title="Zoom Out">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M20 12H4" />
                </svg>
              </button>
              <span class="zoom-text font-mono">{Math.round(zoomLevel * 100)}%</span>
              <button class="zoom-btn" on:click={() => changeZoom(0.1)} title="Zoom In">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
                </svg>
              </button>
              <button class="zoom-btn reset" on:click={() => zoomLevel = 1.0} title="Reset Zoom">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 7.89M9 11l3-3 3 3" />
                </svg>
              </button>
            </div>

            <div class="flow-canvas-wrapper">
              <div class="flow-canvas" style="--zoom: {zoomLevel};">
                <div class="flow-board">
                  
                  <!-- Connection Edges (SVG overlay) -->
                  <svg class="flow-edges-svg" width="1240" height="680">
                    <defs>
                      <marker id="arrow-active" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                        <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="var(--color-primary)" />
                      </marker>
                      <marker id="arrow-inactive" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                        <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="var(--border-color)" />
                      </marker>
                      <marker id="arrow-blocked" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                        <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="var(--color-danger)" />
                      </marker>
                    </defs>

                    <!-- Evolution -> Initialization Links -->
                    <path d="M 270 290 C 285 290, 285 155, 300 155" class="path-flow-active" />
                    <path d="M 270 290 C 285 290, 285 425, 300 425" class="path-flow-active" />

                    <!-- Initialization -> Observation Links -->
                    <path d="M 550 155 L 580 155" class="path-flow-active" marker-end="url(#arrow-active)" />
                    <path d="M 550 425 C 565 425, 565 155, 580 155" class="path-flow-active" marker-end="url(#arrow-active)" />

                    <!-- Step Loop Links -->
                    <!-- Edge 1: Observation -> LLM -->
                    <path d="M 850 120 L 910 120" class="path-flow-active" marker-end="url(#arrow-active)" />

                    <!-- Edge 2: LLM -> Action -->
                    <path d="M 1045 200 L 1045 220" class="path-flow-active" marker-end="url(#arrow-active)" />

                    <!-- Edge 3: Action -> Safety Shield -->
                    <path d="M 1045 360 L 1045 380" class="path-flow-active" marker-end="url(#arrow-active)" />

                    <!-- Edge 4: Safety Shield -> Execution Outcome (if allowed) -->
                    {#if isRiskBlock || isGateBlock || isTrajStop}
                      <path d="M 910 475 C 880 475, 880 420, 850 420" class="path-flow-inactive" marker-end="url(#arrow-inactive)" />
                    {:else}
                      <path d="M 910 475 C 880 475, 880 420, 850 420" class="path-flow-active" marker-end="url(#arrow-active)" />
                    {/if}

                    <!-- Edge 5: Safety Shield -> Feedback back to LLM (if blocked) -->
                    {#if isRiskBlock || isGateBlock || isTrajStop}
                      <path d="M 1180 475 C 1220 475, 1220 120, 1180 120" class="path-flow-blocked" marker-end="url(#arrow-blocked)" />
                    {/if}

                    <!-- Edge 6: Execution Outcome -> Observation loop back -->
                    {#if isRiskBlock || isGateBlock || isTrajStop}
                      <path d="M 715 300 L 715 270" class="path-flow-inactive" marker-end="url(#arrow-inactive)" />
                    {:else}
                      <path d="M 715 300 L 715 270" class="path-flow-active" marker-end="url(#arrow-active)" />
                    {/if}
                  </svg>

                <!-- Column 1: Harness Evolution (Offline) -->
                <div class="flow-node-card node-evo">
                  <div class="node-port port-right" style="top: 50%;"></div>
                  <div class="node-header">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                    </svg>
                    <h4>Harness Evolution (Offline)</h4>
                  </div>
                  <div class="node-body flex-col gap-sm">
                    <!-- Section 1: Training Trajectories -->
                    <div class="sub-panel">
                      <div class="card-tag">Training Trajectories</div>
                      <div class="flex-col font-mono text-xs">
                        <div>Total Episodes: <span class="highlight-mini">{episodes.length}</span></div>
                        <div>Success Runs: <span class="val success-text">{episodes.filter(e => e.final_status === 'SUCCESS').length}</span></div>
                      </div>
                    </div>

                    <!-- Section 2: Pattern Mining & Analysis -->
                    <div class="sub-panel">
                      <div class="card-tag">Failure Pattern Mining</div>
                      <div class="flex-col font-mono text-xs">
                        <div>Failed Runs: <span class="val error-text">{episodes.filter(e => e.final_status === 'FAILED' || e.final_status === 'ERROR').length}</span></div>
                        {#if evolutionStatus}
                          <div>Evo Status: <span class="val highlight-mini">{evolutionStatus.run_status?.status ? evolutionStatus.run_status.status.toUpperCase() : 'IDLE'}</span></div>
                          {#if evolutionStatus.run_status?.last_run}
                            <div class="text-muted text-xxs mt-xs">Last: {new Date(evolutionStatus.run_status.last_run).toLocaleDateString()}</div>
                          {/if}
                        {/if}
                      </div>
                    </div>

                    <!-- Section 3: Harness Updates -->
                    <div class="sub-panel">
                      <div class="card-tag">Harness Updates</div>
                      <button 
                        class="btn btn-primary btn-sm w-full mt-xs" 
                        on:click={onTriggerEvolution}
                        disabled={evolutionStatus?.run_status?.status === 'running'}
                      >
                        {#if evolutionStatus?.run_status?.status === 'running'}
                          Running...
                        {:else}
                          Trigger Evolution Run
                        {/if}
                      </button>
                    </div>
                  </div>
                </div>

                <!-- Column 2: Initialization -->
                <!-- Environment Contract Layer -->
                <div class="flow-node-card node-contract">
                  <div class="node-port port-left" style="top: 50%;"></div>
                  <div class="node-port port-right" style="top: 50%;"></div>
                  <div class="node-header">
                    <span class="badge badge-primary font-mono mr-xs">1</span>
                    <h4>Env Contract Layer</h4>
                  </div>
                  <div class="node-body">
                    <div class="card-tag">Tool & Interface Constraints</div>
                    <div class="flex-col gap-xs font-mono text-xs mt-xs">
                      <div class="state-indicator"><span class="label">Symbol:</span> <span class="val font-bold">{episode?.symbol || 'BTCUSDT'}</span></div>
                      <div class="divider-line">Calibrated Tools</div>
                      <div class="tool-list flex-row gap-xs mt-xs" style="flex-wrap: wrap;">
                        <span class="action-tag text-xxs">submit_order</span>
                        <span class="action-tag text-xxs">cancel_order</span>
                        <span class="action-tag text-xxs">final_response</span>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Procedural Skill Layer -->
                <div class="flow-node-card node-skills-layer">
                  <div class="node-port port-left" style="top: 50%;"></div>
                  <div class="node-port port-right" style="top: 50%;"></div>
                  <div class="node-header">
                    <span class="badge badge-primary font-mono mr-xs">2</span>
                    <h4>Procedural Skill Layer</h4>
                  </div>
                  <div class="node-body">
                    <div class="card-tag">Retrieved Skills & State Alignment</div>
                    <div class="flex-col gap-xs mt-xs">
                      <ul class="skills-list font-mono text-xs">
                        <li>• Daily Risk check alignment</li>
                        <li>• Binance API safety alignment</li>
                        <li>• Trajectory repetition checks</li>
                        <li>• Historical regression checks</li>
                      </ul>
                    </div>
                  </div>
                </div>

                <!-- Column 3: Per-step Interaction (Vòng lặp) -->
                <!-- Node 3.1: Observation (Input State) -->
                <div class="flow-node-card node-input">
                  <div class="node-port port-left" style="top: 50%;"></div>
                  <div class="node-port port-right" style="top: 50%;"></div>
                  <div class="node-header">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                    <h4>Observation</h4>
                  </div>
                  <div class="node-body">
                    {#if marketSnapshot}
                      <div class="mini-chart-container">
                        <div class="card-tag">Market Snapshot ({marketSnapshot.symbol || episode.symbol})</div>
                        <div class="price-badge">${marketSnapshot.price ? marketSnapshot.price.toLocaleString() : "—"}</div>
                        <CandleChart 
                          candles={marketSnapshot.candles} 
                          price={marketSnapshot.price} 
                          symbol={marketSnapshot.symbol || episode.symbol} 
                        />
                      </div>
                    {/if}
                    {#if positionState}
                      <div class="divider-line">Position State</div>
                      <div class="pos-badge code-font {positionState.side === 'LONG' ? 'long' : positionState.side === 'SHORT' ? 'short' : 'flat'}">
                        {positionState.side} ({positionState.quantity || 0} BTC)
                      </div>
                    {/if}
                  </div>
                </div>

                <!-- Node 3.2: LLM Decision -->
                <div class="flow-node-card node-brain">
                  <div class="node-port port-left" style="top: 50%;"></div>
                  <div class="node-port port-bottom" style="left: 50%;"></div>
                  <div class="node-port port-right" style="top: 50%;"></div>
                  <div class="node-header">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                    <h4>LLM Decision (Frozen)</h4>
                  </div>
                  <div class="node-body">
                    <p class="thought-summary-mini">
                      {step.decision_summary ? tryParseFinalResponse(step.decision_summary) : "State inspection completed."}
                    </p>
                    <button class="btn btn-secondary btn-sm" on:click={() => toggleThought(step.step_index)}>
                      {expandedThoughts[step.step_index] ? "Hide Rationale" : "Show Rationale"}
                    </button>
                    {#if expandedThoughts[step.step_index] && step.decision_summary}
                      <pre class="raw-box font-mono mt-sm">{cleanJson(step.decision_summary)}</pre>
                    {/if}
                  </div>
                </div>

                <!-- Node 3.3: Proposed Action -->
                <div class="flow-node-card node-action">
                  <div class="node-port port-top" style="left: 50%;"></div>
                  <div class="node-port port-bottom" style="left: 50%;"></div>
                  <div class="node-header">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                    </svg>
                    <h4>Proposed Action</h4>
                  </div>
                  <div class="node-body">
                    <span class="action-tag">{action.tool || 'final_response'}</span>
                    {#if action.arguments}
                      <div class="args-list font-mono font-sm">
                        {#each Object.entries(action.arguments) as [key, val]}
                          <div class="arg-item">{key}: <span class="val">{val}</span></div>
                        {/each}
                      </div>
                    {/if}
                  </div>
                </div>

                <!-- Node 3.4: Action Realization (Safety Shield) -->
                <div class="flow-node-card node-safety">
                  <div class="node-port port-top" style="left: 50%;"></div>
                  <div class="node-port port-left" style="top: 50%;"></div>
                  <div class="node-port port-right" style="top: 50%;"></div>
                  <div class="node-header">
                    <span class="badge badge-warning font-mono mr-xs">3</span>
                    <h4>Action Realization</h4>
                  </div>
                  <div class="node-body">
                    <div class="layers-pipeline">
                      <!-- Layer 2: Risk Guard -->
                      <div class="layer-item {isRiskBlock ? 'blocked' : 'pass'}">
                        <div class="layer-hdr">
                          <span class="indicator"></span>
                          <span class="layer-name">Risk Guard Check</span>
                        </div>
                        <div class="layer-data text-xxs">
                          {#if riskState}
                            Loss: ${riskState.daily_loss_usdt ? riskState.daily_loss_usdt.toFixed(1) : '0.0'}/${riskState.max_daily_loss_usdt || '50.0'}
                          {:else}
                            Daily limits OK
                          {/if}
                        </div>
                      </div>

                      <!-- Layer 3: Action Gate -->
                      <div class="layer-item {isGateBlock ? 'blocked' : 'pass'}">
                        <div class="layer-hdr">
                          <span class="indicator"></span>
                          <span class="layer-name">Action Gate check</span>
                        </div>
                        <div class="layer-data text-xxs">
                          Tool: <span class="highlight-mini">{action.tool || 'final_response'}</span>
                        </div>
                      </div>
                    </div>
                    
                    <div class="gate-verdict-mini {getDecisionColorClass(intervention.decision)} mt-xs">
                      <span class="label">Verdict:</span> <strong>{intervention.decision || 'ALLOW'}</strong>
                      {#if intervention.reason}
                        <div class="verdict-reason font-mono text-xxs">{intervention.reason}</div>
                      {/if}
                    </div>
                  </div>
                </div>

                <!-- Node 5: Result / Feedback -->
                <div class="flow-node-card node-result {isRiskBlock || isGateBlock || isTrajStop ? 'node-disabled' : ''}">
                  <div class="node-port port-top"></div>
                  <div class="node-header">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <h4>Execution Outcome</h4>
                  </div>
                  <div class="node-body">
                    {#if feedback.error}
                      <div class="error-feedback font-mono text-sm">
                        {feedback.error}
                      </div>
                    {:else}
                      <div class="success-feedback font-mono text-sm">
                        {getStepOutcomeSummary(step)}
                      </div>
                    {/if}
                    <button class="btn btn-secondary btn-sm mt-sm" on:click={() => toggleLog(step.step_index)}>
                      {expandedLogs[step.step_index] ? "Hide Raw API" : "Show Raw API"}
                    </button>
                    {#if expandedLogs[step.step_index]}
                      <pre class="raw-box font-mono mt-sm">{cleanJson(feedback)}</pre>
                    {/if}
                  </div>
                </div>

                <!-- Node 3.6: Trajectory Regulation (bottom bar) -->
                <div class="flow-node-card node-trajectory">
                  <div class="trajectory-content">
                    <div class="trajectory-left">
                      <span class="badge badge-danger font-mono mr-xs">4</span>
                      <h4 class="trajectory-title">Trajectory Regulation Layer</h4>
                      <span class="trajectory-desc text-xxs">Monitor trajectories, detect loops & errors</span>
                    </div>
                    <div class="trajectory-right">
                      {#if isTrajStop}
                        <span class="badge badge-danger text-xxs font-mono">STATUS: STOPPED (BLOCKED)</span>
                      {:else}
                        <span class="badge badge-success text-xxs font-mono">STATUS: PASS (ACTIVE)</span>
                      {/if}
                    </div>
                  </div>
                </div>

              </div>
            </div>
          </div>
        </div>
        </div>
      {/if}

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
            {#each steps as step, i (step.step_index)}
              {@const action = step.action || {}}
              {@const intervention = step.harness_intervention || {}}
              <tr class={selectedStepIdx === i ? 'selected-row' : ''} on:click={() => selectedStepIdx = i} style="cursor: pointer;">
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

  /* Svelte Flow visual canvas styles */
  .step-selector-card {
    background-color: var(--bg-panel);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 1.25rem;
    box-shadow: var(--shadow-sm);
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .step-pills {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .step-pill {
    padding: 0.375rem 0.75rem;
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--text-secondary);
    background-color: var(--bg-main);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    transition: all 0.2s;
  }

  .step-pill:hover {
    color: var(--text-primary);
    background-color: var(--bg-panel-hover);
    border-color: var(--border-color-hover);
  }

  .step-pill.active {
    background-color: var(--color-primary-light);
    color: var(--color-primary);
    border-color: var(--color-primary);
  }

  .flow-container-rel {
    position: relative;
    width: 100%;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-sm);
    overflow: hidden;
  }

  .flow-canvas-wrapper {
    position: relative;
    width: 100%;
    overflow-x: auto;
  }

  .zoom-controls {
    position: absolute;
    top: 12px;
    right: 12px;
    display: flex;
    align-items: center;
    gap: 0.25rem;
    background-color: var(--bg-panel);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    padding: 0.25rem;
    box-shadow: var(--shadow-md);
    z-index: 50;
    user-select: none;
  }

  .zoom-btn {
    width: 26px;
    height: 26px;
    border-radius: 4px;
    border: 1px solid transparent;
    background-color: transparent;
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s;
  }

  .zoom-btn:hover {
    color: var(--text-primary);
    background-color: var(--bg-panel-hover);
    border-color: var(--border-color-hover);
  }

  .zoom-btn.reset {
    border-left: 1px solid var(--border-color);
    border-radius: 0 4px 4px 0;
    margin-left: 0.25rem;
    padding-left: 0.25rem;
  }

  .zoom-text {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--text-secondary);
    min-width: 40px;
    text-align: center;
  }

  .flow-canvas {
    background-color: var(--bg-main);
    background-size: 16px 16px;
    background-image: radial-gradient(var(--border-color) 1px, transparent 1px);
    width: 100%;
    height: calc(680px * var(--zoom));
    min-width: calc(1240px * var(--zoom));
    position: relative;
  }

  .flow-board {
    position: absolute;
    top: 0;
    left: 0;
    width: 1240px;
    height: 680px;
    flex-shrink: 0;
    transform: scale(var(--zoom));
    transform-origin: 0 0;
  }

  .flow-edges-svg {
    position: absolute;
    top: 0;
    left: 0;
    width: 1240px;
    height: 640px;
    z-index: 1;
    pointer-events: none;
  }

  .path-flow-active {
    stroke: var(--color-primary);
    stroke-width: 3px;
    fill: none;
    stroke-dasharray: 6 4;
    animation: flow-dash-anim 30s linear infinite;
  }

  .path-flow-blocked {
    stroke: var(--color-danger);
    stroke-width: 3px;
    fill: none;
    stroke-dasharray: 6 4;
    animation: flow-dash-anim 30s linear infinite;
  }

  .path-flow-inactive {
    stroke: var(--border-color);
    stroke-width: 2px;
    fill: none;
    opacity: 0.5;
  }

  @keyframes flow-dash-anim {
    to {
      stroke-dashoffset: -1000;
    }
  }

  .flow-node-card {
    background-color: var(--bg-panel);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-md);
    padding: 1rem;
    position: absolute;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    transition: all 0.2s;
    z-index: 2;
  }

  .node-evo {
    left: 20px;
    top: 40px;
    width: 250px;
    height: 500px;
  }

  .node-contract {
    left: 300px;
    top: 40px;
    width: 250px;
    height: 230px;
  }

  .node-skills-layer {
    left: 300px;
    top: 310px;
    width: 250px;
    height: 230px;
  }

  .node-input {
    left: 580px;
    top: 40px;
    width: 270px;
    height: 230px;
  }

  .node-brain {
    left: 910px;
    top: 40px;
    width: 270px;
    height: 160px;
  }

  .node-action {
    left: 910px;
    top: 220px;
    width: 270px;
    height: 140px;
  }

  .node-safety {
    left: 910px;
    top: 380px;
    width: 270px;
    height: 190px;
  }

  .node-result {
    left: 580px;
    top: 300px;
    width: 270px;
    height: 240px;
  }

  .node-trajectory {
    left: 580px;
    top: 600px;
    width: 600px;
    height: 50px;
    padding: 0 1rem;
    display: flex;
    align-items: center;
    box-shadow: var(--shadow-sm);
  }

  .trajectory-content {
    display: flex;
    width: 100%;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
  }

  .trajectory-left {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .trajectory-title {
    font-size: 0.875rem;
    font-weight: 700;
    margin: 0;
    color: var(--text-primary);
  }

  .trajectory-desc {
    color: var(--text-muted);
    font-size: 0.75rem;
  }

  .sub-panel {
    background-color: var(--bg-main);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    padding: 0.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .skills-list {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .skills-list li {
    font-size: 0.75rem;
    color: var(--text-secondary);
    line-height: 1.4;
  }

  .text-xxs {
    font-size: 0.6875rem;
  }

  .text-xxs.text-muted {
    color: var(--text-muted);
  }

  .mr-xs {
    margin-right: 0.25rem;
  }

  .mt-xs {
    margin-top: 0.25rem;
  }

  .w-full {
    width: 100%;
  }

  .badge-primary {
    background-color: var(--color-primary-light);
    color: var(--color-primary);
  }

  .badge-warning {
    background-color: var(--color-warning-light);
    color: var(--color-warning);
  }

  .badge-danger {
    background-color: var(--color-danger-light);
    color: var(--color-danger);
  }

  .badge-success {
    background-color: var(--color-success-light);
    color: var(--color-success);
  }

  .node-disabled {
    opacity: 0.5;
    border-color: var(--border-color);
  }

  .flow-node-card:hover {
    box-shadow: var(--shadow-lg);
    border-color: var(--color-primary);
  }

  .node-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    border-bottom: 1px solid var(--border-color);
    padding-bottom: 0.5rem;
    color: var(--text-primary);
  }

  .node-header h4 {
    font-size: 0.875rem;
    font-weight: 700;
  }

  .node-header svg {
    color: var(--color-primary);
    flex-shrink: 0;
  }

  .node-body {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    font-size: 0.8125rem;
    overflow-y: auto;
    flex: 1;
    min-height: 0;
  }

  .node-port {
    position: absolute;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: var(--border-color-hover);
    border: 1px solid var(--border-color);
    z-index: 10;
  }

  .port-right {
    right: -5px;
    top: 50%;
    transform: translateY(-50%);
  }

  .port-left {
    left: -5px;
    top: 50%;
    transform: translateY(-50%);
  }

  .port-top {
    top: -5px;
    left: 50%;
    transform: translateX(-50%);
  }

  .port-bottom {
    bottom: -5px;
    left: 50%;
    transform: translateX(-50%);
  }

  .mini-chart-container {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .price-badge {
    font-size: 1.125rem;
    font-weight: 800;
    color: var(--text-primary);
  }

  .divider-line {
    font-size: 0.6875rem;
    font-weight: 700;
    color: var(--text-muted);
    text-transform: uppercase;
    border-bottom: 1px dashed var(--border-color);
    padding-bottom: 0.25rem;
    margin-top: 0.25rem;
  }

  .thought-summary-mini {
    font-size: 0.8125rem;
    line-height: 1.4;
    color: var(--text-secondary);
  }


  .gate-verdict-mini {
    margin-top: 0.25rem;
    border-radius: var(--radius-sm);
    padding: 0.375rem;
    font-size: 0.75rem;
  }

  .error-feedback {
    color: var(--color-danger);
    background-color: var(--color-danger-light);
    border: 1px solid var(--color-danger-border);
    padding: 0.5rem;
    border-radius: var(--radius-sm);
  }

  .success-feedback {
    color: var(--color-success);
    background-color: var(--color-success-light);
    border: 1px solid var(--color-success-border);
    padding: 0.5rem;
    border-radius: var(--radius-sm);
  }

  .compact-table tbody tr.selected-row {
    background-color: var(--color-primary-light) !important;
  }
  .compact-table tbody tr.selected-row td {
    color: var(--color-primary) !important;
  }

  /* Layers pipeline styling */
  .layers-pipeline {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
    background-color: var(--bg-main);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    padding: 0.375rem;
  }

  .layer-item {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
    padding: 0.25rem 0.375rem;
    border-radius: var(--radius-sm);
    border: 1px solid transparent;
  }

  .layer-item.pass {
    background-color: rgba(16, 185, 129, 0.02);
    border-color: rgba(16, 185, 129, 0.08);
  }

  .layer-item.blocked {
    background-color: rgba(239, 68, 68, 0.02);
    border-color: rgba(239, 68, 68, 0.08);
  }

  .layer-hdr {
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }

  .layer-hdr .indicator {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    display: inline-block;
  }

  .layer-item.pass .indicator {
    background-color: var(--color-success);
  }

  .layer-item.blocked .indicator {
    background-color: var(--color-danger);
  }

  .layer-name {
    font-size: 0.75rem;
    font-weight: 700;
    color: var(--text-primary);
  }

  .layer-data {
    font-size: 0.6875rem;
    color: var(--text-secondary);
    padding-left: 0.5rem;
    font-family: var(--font-mono);
  }

  .highlight-mini {
    background-color: var(--bg-panel);
    border: 1px solid var(--border-color);
    border-radius: 3px;
    padding: 0 0.1875rem;
    color: var(--text-primary);
  }
</style>
