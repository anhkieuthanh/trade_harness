<script>
  import { onMount, onDestroy } from "svelte";

  export let controlState = {
    live_enabled: false,
    offline_evolution_enabled: false,
    offline_evolution_time: "01:00",
    last_offline_evolution_run_date: null,
    strategy: {
      mode: "random_flip",
      entry_quantity_btc: 0.008,
      hold_seconds: 120,
      cooldown_seconds: 0
    },
    risk: {
      max_daily_loss_usdt: 50.0,
      max_open_positions: 1,
      loss_cooldown_seconds: 1800,
      hard_stop_candle_range_pct: 2.0
    }
  };
  export let onSaveSettings = async () => {};
  export let evolutionStatus = null;
  export let onTriggerEvolution = async () => {};
  export let onRefreshEvolution = async () => {};

  let isSaving = false;
  let saveMessage = "";
  let saveMessageType = "success"; // success | error
  let refreshInterval = null;

  $: evolutionIsRunning = evolutionStatus?.run_status?.status === "running";

  onMount(() => {
    // Poll evolution status if it is running
    refreshInterval = setInterval(() => {
      onRefreshEvolution();
    }, 3000);
  });

  onDestroy(() => {
    if (refreshInterval) clearInterval(refreshInterval);
  });

  async function handleSave() {
    isSaving = true;
    saveMessage = "";
    try {
      await onSaveSettings(controlState);
      saveMessage = "Settings updated successfully!";
      saveMessageType = "success";
      setTimeout(() => saveMessage = "", 3000);
    } catch (err) {
      saveMessage = "Failed to update settings: " + err.message;
      saveMessageType = "error";
    } finally {
      isSaving = false;
    }
  }

  function formatLocalTime(isoStr) {
    if (!isoStr) return "—";
    try {
      const d = new Date(isoStr);
      return d.toLocaleTimeString() + " " + d.toLocaleDateString();
    } catch (_) {
      return isoStr;
    }
  }
</script>

<div class="settings-panel">
  <div class="panel-section">
    <div class="section-title">
      <h3>Live Operator Controls</h3>
      <p>Configure agent execution limits and strategy parameters</p>
    </div>

    {#if saveMessage}
      <div class="alert {saveMessageType === 'success' ? 'alert-success' : 'alert-error'}">
        {saveMessage}
      </div>
    {/if}

    <div class="form-container">
      <div class="form-row flex-row">
        <label class="toggle-container">
          <input type="checkbox" bind:checked={controlState.live_enabled} />
          <span class="toggle-slider"></span>
          <span class="toggle-label">Enable Live Agent Loop</span>
        </label>
        
        <label class="toggle-container">
          <input type="checkbox" bind:checked={controlState.offline_evolution_enabled} />
          <span class="toggle-slider"></span>
          <span class="toggle-label">Scheduled Evolution</span>
        </label>
      </div>

      <div class="form-row">
        <label for="evolution_time">Daily Evolution Time (UTC)</label>
        <input 
          id="evolution_time" 
          type="text" 
          placeholder="HH:MM" 
          bind:value={controlState.offline_evolution_time} 
        />
        <span class="field-desc">Time to auto-trigger evolution batch report.</span>
      </div>

      <div class="divider">Strategy Configuration</div>

      <div class="grid-2">
        <div class="form-row">
          <label for="strategy_mode">Strategy Mode</label>
          <select id="strategy_mode" bind:value={controlState.strategy.mode}>
            <option value="random_flip">Random Flip (Automated Trade/Hold)</option>
            <option value="manual_only">Manual Hold Strategy</option>
            <option value="inspect_then_decide">Inspect Then Decide (LLM/Brain Mode)</option>
          </select>
        </div>

        <div class="form-row">
          <label for="entry_qty">Entry Size (BTC)</label>
          <input 
            id="entry_qty" 
            type="number" 
            step="0.001" 
            bind:value={controlState.strategy.entry_quantity_btc} 
          />
        </div>

        <div class="form-row">
          <label for="hold_sec">Hold Duration (seconds)</label>
          <input 
            id="hold_sec" 
            type="number" 
            bind:value={controlState.strategy.hold_seconds} 
          />
        </div>

        <div class="form-row">
          <label for="cooldown_sec">Cooldown Duration (seconds)</label>
          <input 
            id="cooldown_sec" 
            type="number" 
            bind:value={controlState.strategy.cooldown_seconds} 
          />
        </div>
      </div>

      <div class="divider">Risk Guard Limits</div>

      <div class="grid-2">
        <div class="form-row">
          <label for="max_daily_loss">Max Daily Loss (USDT)</label>
          <input 
            id="max_daily_loss" 
            type="number" 
            step="0.5" 
            bind:value={controlState.risk.max_daily_loss_usdt} 
          />
        </div>

        <div class="form-row">
          <label for="max_positions">Max Open Positions</label>
          <input 
            id="max_positions" 
            type="number" 
            bind:value={controlState.risk.max_open_positions} 
          />
        </div>

        <div class="form-row">
          <label for="loss_cooldown">Loss Cooldown (seconds)</label>
          <input 
            id="loss_cooldown" 
            type="number" 
            bind:value={controlState.risk.loss_cooldown_seconds} 
          />
        </div>

        <div class="form-row">
          <label for="hard_stop_candle">Hard Stop Candle Range (%)</label>
          <input 
            id="hard_stop_candle" 
            type="number" 
            step="0.1" 
            bind:value={controlState.risk.hard_stop_candle_range_pct} 
          />
        </div>
      </div>

      <button 
        class="btn btn-primary btn-save" 
        on:click={handleSave} 
        disabled={isSaving}
      >
        {#if isSaving}
          <div class="mini-spinner"></div>
          Saving Settings...
        {:else}
          Save Configuration
        {/if}
      </button>
    </div>
  </div>

  <div class="panel-section ev-section">
    <div class="section-title">
      <h3>Offline Evolution Batch</h3>
      <p>Evaluate recent episodes, run Failure Annotation, stage layers updates</p>
    </div>

    <div class="evolution-status-panel">
      <div class="status-item">
        <span class="label">Job Status:</span>
        <span class="val badge {evolutionIsRunning ? 'badge-warning' : 'badge-primary'}">
          {evolutionStatus?.run_status?.status || 'unknown'}
        </span>
      </div>
      <div class="status-item">
        <span class="label">Last run date:</span>
        <span class="val font-mono">{formatLocalTime(evolutionStatus?.run_status?.last_run)}</span>
      </div>
      
      {#if evolutionStatus?.pass_metrics?.overall}
        <div class="status-item">
          <span class="label">Harness Pass@1:</span>
          <span class="val font-mono success-text">
            {(evolutionStatus.pass_metrics.overall.pass_at_1 * 100).toFixed(0)}% 
            ({evolutionStatus.pass_metrics.overall.total_episodes} episodes)
          </span>
        </div>
      {/if}

      {#if evolutionStatus?.run_status?.error}
        <div class="alert alert-error font-mono text-sm">
          Error: {evolutionStatus.run_status.error}
        </div>
      {/if}

      <div class="ev-actions">
        <button 
          class="btn btn-secondary flex-1" 
          on:click={onTriggerEvolution}
          disabled={evolutionIsRunning}
        >
          {#if evolutionIsRunning}
            <div class="mini-spinner"></div>
            Running Evolution...
          {:else}
            Run Evolution Now
          {/if}
        </button>
        <button class="btn btn-secondary" on:click={onRefreshEvolution}>
          Refresh
        </button>
      </div>
    </div>

    {#if evolutionStatus?.daily_report}
      <div class="report-box">
        <h4>Latest Daily Report Summary</h4>
        <div class="report-content font-mono">
          {evolutionStatus.daily_report}
        </div>
      </div>
    {/if}
  </div>
</div>

<style>
  .settings-panel {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    height: 100%;
    overflow-y: auto;
    padding: 1.5rem;
  }

  .panel-section {
    background-color: var(--bg-panel);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .section-title h3 {
    font-size: 1.125rem;
    font-weight: 700;
  }

  .section-title p {
    font-size: 0.8125rem;
    color: var(--text-secondary);
  }

  .form-container {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .flex-row {
    display: flex;
    flex-direction: row;
    gap: 1.5rem;
    flex-wrap: wrap;
    align-items: center;
  }

  .grid-2 {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1rem;
  }

  .divider {
    font-size: 0.75rem;
    font-weight: 700;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px dashed var(--border-color);
    padding-bottom: 0.25rem;
    margin-top: 0.5rem;
  }

  .form-row {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .form-row label {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--text-secondary);
  }

  .form-row input[type="text"],
  .form-row input[type="number"],
  .form-row select {
    background-color: var(--bg-main);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    color: var(--text-primary);
    font-family: var(--font-sans);
    font-size: 0.875rem;
    padding: 0.5rem;
    outline: none;
    transition: border-color 0.2s;
  }

  .form-row input:focus,
  .form-row select:focus {
    border-color: var(--color-primary);
  }

  .field-desc {
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .toggle-container {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    font-size: 0.875rem;
    font-weight: 500;
  }

  .toggle-container input {
    display: none;
  }

  .toggle-slider {
    position: relative;
    width: 36px;
    height: 20px;
    background-color: var(--bg-main);
    border: 1px solid var(--border-color);
    border-radius: 9999px;
    transition: background-color 0.2s;
  }

  .toggle-slider::after {
    content: '';
    position: absolute;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background-color: var(--text-secondary);
    top: 2px;
    left: 2px;
    transition: transform 0.2s, background-color 0.2s;
  }

  .toggle-container input:checked + .toggle-slider {
    background-color: var(--color-primary-light);
    border-color: var(--color-primary);
  }

  .toggle-container input:checked + .toggle-slider::after {
    transform: translateX(16px);
    background-color: var(--color-primary);
  }

  .btn-save {
    margin-top: 0.5rem;
    width: 100%;
    padding: 0.625rem;
    font-weight: 600;
  }

  .alert {
    padding: 0.75rem;
    border-radius: var(--radius-sm);
    font-size: 0.8125rem;
    border-width: 1px;
    border-style: solid;
  }

  .alert-success {
    background-color: var(--color-success-light);
    border-color: var(--color-success-border);
    color: var(--color-success);
  }

  .alert-error {
    background-color: var(--color-danger-light);
    border-color: var(--color-danger-border);
    color: var(--color-danger);
  }

  .mini-spinner {
    width: 14px;
    height: 14px;
    border: 2px solid transparent;
    border-top-color: currentColor;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  .font-mono {
    font-family: var(--font-mono);
  }

  .text-sm {
    font-size: 0.75rem;
  }

  .success-text {
    color: var(--color-success);
    font-weight: 600;
  }

  /* Evolution Panel Specifics */
  .evolution-status-panel {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    background-color: var(--bg-main);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    padding: 0.75rem;
  }

  .status-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.8125rem;
  }

  .status-item .label {
    color: var(--text-secondary);
  }

  .status-item .val {
    color: var(--text-primary);
  }

  .ev-actions {
    display: flex;
    gap: 0.75rem;
    margin-top: 0.5rem;
  }

  .flex-1 {
    flex: 1;
  }

  .report-box {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .report-box h4 {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--text-secondary);
  }

  .report-content {
    background-color: var(--bg-main);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    padding: 0.75rem;
    height: 150px;
    overflow-y: auto;
    font-size: 0.75rem;
    white-space: pre-wrap;
    color: var(--text-secondary);
  }
</style>
