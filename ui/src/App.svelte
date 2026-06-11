<script>
  import { onMount, onDestroy } from "svelte";
  import Sidebar from "./components/Sidebar.svelte";
  import FlowVisualizer from "./components/FlowVisualizer.svelte";
  import SettingsPanel from "./components/SettingsPanel.svelte";

  // Backend API URL configuration (empty string means relative paths, i.e., served from the same host/port)
  // We use relative paths for production builds, but during Vite development, we point to localhost:8080
  const API_BASE = import.meta.env.DEV ? "http://localhost:8080" : "";

  let episodes = [];
  let selectedEpisodeId = null;
  let selectedEpisode = null;
  let controlState = null;
  let evolutionStatus = null;

  let activeTab = "visualizer"; // visualizer | settings
  
  let isLoadingList = false;
  let isLoadingDetail = false;
  let isRefreshing = false;

  let pollInterval = null;

  // Compute metrics from episodes
  $: successCount = episodes.filter(ep => ep.final_status === 'SUCCESS').length;
  $: failedCount = episodes.filter(ep => ep.final_status === 'FAILED' || ep.final_status === 'ERROR').length;
  $: recentPassRate = episodes.length > 0 ? (successCount / episodes.length) * 100 : 0;

  async function fetchEpisodes(autoSelect = false) {
    if (episodes.length === 0) isLoadingList = true;
    try {
      const res = await fetch(`${API_BASE}/api/episodes?limit=100`);
      if (res.ok) {
        const data = await res.json();
        episodes = data.episodes || [];
        
        // Auto select first episode if none selected
        if (autoSelect && episodes.length > 0 && !selectedEpisodeId) {
          selectEpisode(episodes[0].episode_id);
        }
      }
    } catch (err) {
      console.error("Failed to fetch episodes list:", err);
    } finally {
      isLoadingList = false;
    }
  }

  async function fetchEpisodeDetail(id, showSpinner = true) {
    if (!id) return;
    if (showSpinner) isLoadingDetail = true;
    try {
      const res = await fetch(`${API_BASE}/api/episodes/${id}`);
      if (res.ok) {
        selectedEpisode = await res.json();
      }
    } catch (err) {
      console.error(`Failed to fetch episode details for ${id}:`, err);
    } finally {
      if (showSpinner) isLoadingDetail = false;
    }
  }

  async function fetchControlState() {
    try {
      const res = await fetch(`${API_BASE}/api/control`);
      if (res.ok) {
        controlState = await res.json();
      }
    } catch (err) {
      console.error("Failed to fetch control state:", err);
    }
  }

  async function fetchEvolutionStatus() {
    try {
      const res = await fetch(`${API_BASE}/api/evolution/status`);
      if (res.ok) {
        evolutionStatus = await res.json();
      }
    } catch (err) {
      console.error("Failed to fetch evolution status:", err);
    }
  }

  async function saveControlSettings(updatedState) {
    const res = await fetch(`${API_BASE}/api/control`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updatedState)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || "Internal Server Error");
    }
    // Refresh local copy
    await fetchControlState();
  }

  async function triggerOfflineEvolution() {
    try {
      const res = await fetch(`${API_BASE}/api/evolution/run`, { method: "POST" });
      if (res.ok) {
        await fetchEvolutionStatus();
      }
    } catch (err) {
      console.error("Failed to trigger offline evolution:", err);
    }
  }

  function selectEpisode(id) {
    selectedEpisodeId = id;
    fetchEpisodeDetail(id);
    activeTab = "visualizer"; // Auto-switch to visualizer tab when selecting a run
  }

  async function handleRefreshAll() {
    isRefreshing = true;
    await Promise.all([
      fetchEpisodes(),
      selectedEpisodeId ? fetchEpisodeDetail(selectedEpisodeId) : Promise.resolve(),
      fetchControlState(),
      fetchEvolutionStatus()
    ]);
    isRefreshing = false;
  }

  onMount(async () => {
    // Initial data fetch
    await fetchEpisodes(true);
    await fetchControlState();
    await fetchEvolutionStatus();

    // Setup periodic polling for live execution updates (every 5s)
    pollInterval = setInterval(() => {
      fetchEpisodes(false);
      if (selectedEpisodeId && activeTab === "visualizer") {
        fetchEpisodeDetail(selectedEpisodeId, false);
      }
    }, 5000);
  });

  onDestroy(() => {
    if (pollInterval) clearInterval(pollInterval);
  });
</script>

<div id="app">
  <!-- Sidebar Log Runs -->
  <Sidebar 
    {episodes} 
    {selectedEpisodeId} 
    isLoading={isLoadingList} 
    onSelectEpisode={selectEpisode}
  />

  <!-- Main Panel -->
  <div class="main-content">
    <!-- Top Global Header -->
    <header class="app-header">
      <div class="header-left">
        <div class="brand">
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5" class="brand-icon">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          <h2>TradeHarness Visualizer</h2>
        </div>
        
        <!-- Navigation Tabs -->
        <nav class="nav-tabs">
          <button 
            class="nav-tab {activeTab === 'visualizer' ? 'active' : ''}" 
            on:click={() => activeTab = 'visualizer'}
          >
            Trace Execution Flow
          </button>
          <button 
            class="nav-tab {activeTab === 'settings' ? 'active' : ''}" 
            on:click={() => activeTab = 'settings'}
          >
            Settings & Evolution
          </button>
        </nav>
      </div>

      <!-- Quick Metrics Strip -->
      <div class="header-right">
        <div class="quick-stats">
          <div class="stat-bubble font-mono">
            <span class="label">Pass Ratio (Window 100):</span>
            <span class="val success-text">{recentPassRate.toFixed(0)}%</span>
          </div>
          <div class="stat-bubble font-mono">
            <span class="label">S:</span>
            <span class="val success-text">{successCount}</span>
            <span class="label">F:</span>
            <span class="val error-text">{failedCount}</span>
          </div>
          
          {#if controlState}
            <div class="stat-bubble font-mono">
              <span class="label">Daemon:</span>
              <span class="val badge {controlState.live_enabled ? 'badge-success' : 'badge-danger'}">
                {controlState.live_enabled ? 'ALIVE' : 'STOPPED'}
              </span>
            </div>
          {/if}
        </div>

        <button class="btn btn-secondary refresh-btn" on:click={handleRefreshAll} disabled={isRefreshing}>
          {#if isRefreshing}
            <div class="spinner-mini"></div>
          {:else}
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/>
            </svg>
          {/if}
          Refresh
        </button>
      </div>
    </header>

    <!-- Main View Switcher -->
    <main class="content-body">
      {#if activeTab === "visualizer"}
        {#if isLoadingDetail}
          <div class="loading-overlay">
            <div class="spinner"></div>
            <span>Loading episode details...</span>
          </div>
        {/if}
        <FlowVisualizer episode={selectedEpisode} />
      {:else if activeTab === "settings"}
        {#if controlState}
          <SettingsPanel 
            bind:controlState 
            {evolutionStatus}
            onSaveSettings={saveControlSettings}
            onTriggerEvolution={triggerOfflineEvolution}
            onRefreshEvolution={fetchEvolutionStatus}
          />
        {:else}
          <div class="loading-overlay">
            <div class="spinner"></div>
            <span>Loading control state...</span>
          </div>
        {/if}
      {/if}
    </main>
  </div>
</div>

<style>
  .app-header {
    height: 64px;
    background-color: var(--bg-sidebar);
    border-bottom: 1px solid var(--border-color);
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 1.5rem;
    flex-shrink: 0;
    gap: 1.5rem;
  }

  .header-left, .header-right {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .brand-icon {
    color: var(--color-primary);
    filter: drop-shadow(0 0 4px var(--color-primary-light));
    animation: glow-pulse 3s infinite ease-in-out;
  }

  @keyframes glow-pulse {
    0%, 100% { filter: drop-shadow(0 0 2px var(--color-primary-light)); }
    50% { filter: drop-shadow(0 0 8px var(--color-primary)); }
  }

  .brand h2 {
    font-size: 1.125rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: var(--text-primary);
  }

  .nav-tabs {
    display: flex;
    height: 100%;
    align-items: center;
    border-left: 1px solid var(--border-color);
    padding-left: 1rem;
    gap: 0.375rem;
  }

  .nav-tab {
    padding: 0.375rem 0.75rem;
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--text-secondary);
    border-radius: var(--radius-sm);
    transition: all 0.2s;
  }

  .nav-tab:hover {
    color: var(--text-primary);
    background-color: var(--bg-panel-hover);
  }

  .nav-tab.active {
    background-color: var(--color-primary-light);
    color: var(--color-primary);
    border: 1px solid rgba(59, 130, 246, 0.2);
  }

  .quick-stats {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: nowrap;
  }

  .stat-bubble {
    background-color: var(--bg-panel);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    padding: 0.25rem 0.5rem;
    font-size: 0.75rem;
    display: flex;
    align-items: center;
    gap: 0.25rem;
    white-space: nowrap;
  }

  .stat-bubble .label {
    color: var(--text-muted);
  }

  .stat-bubble .val {
    font-weight: 700;
  }

  .success-text { color: var(--color-success); }
  .error-text { color: var(--color-danger); }

  .refresh-btn {
    padding: 0.375rem 0.75rem;
    font-size: 0.8125rem;
  }

  .spinner-mini {
    width: 12px;
    height: 12px;
    border: 2px solid var(--text-muted);
    border-top-color: var(--text-primary);
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .loading-overlay {
    position: absolute;
    inset: 0;
    background-color: rgba(9, 13, 22, 0.8);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 1rem;
    z-index: 100;
    backdrop-filter: blur(4px);
    color: var(--text-secondary);
    font-size: 0.875rem;
  }

  .spinner {
    width: 32px;
    height: 32px;
    border: 3px solid var(--border-color);
    border-top-color: var(--color-primary);
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }
</style>
