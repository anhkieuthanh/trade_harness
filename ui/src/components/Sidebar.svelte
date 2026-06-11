<script>
  export let episodes = [];
  export let selectedEpisodeId = null;
  export let onSelectEpisode = () => {};
  export let isLoading = false;
  export let isCollapsed = false;

  let searchQuery = "";
  let statusFilter = "all";

  $: filteredEpisodes = episodes.filter(ep => {
    const matchesSearch = searchQuery === "" || 
      (ep.episode_id && ep.episode_id.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (ep.task_id && ep.task_id.toLowerCase().includes(searchQuery.toLowerCase()));

    const matchesStatus = statusFilter === "all" || 
      (ep.final_status && ep.final_status.toLowerCase() === statusFilter.toLowerCase());

    return matchesSearch && matchesStatus;
  });

  function formatTime(isoStr) {
    if (!isoStr) return "—";
    try {
      const date = new Date(isoStr);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) + 
             " " + date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } catch (_) {
      return isoStr;
    }
  }

  function getStatusBadgeClass(status) {
    if (!status) return "badge-primary";
    const s = status.toUpperCase();
    if (s === "SUCCESS") return "badge-success";
    if (s === "FAILED" || s === "ERROR") return "badge-danger";
    return "badge-warning";
  }
</script>

<div class="sidebar {isCollapsed ? 'collapsed' : ''}">
  <div class="sidebar-content">
    <div class="sidebar-header">
      <div class="title-row">
        <h2>Runs Log</h2>
        <span class="count-badge">{filteredEpisodes.length}</span>
      </div>
      
      <div class="search-box">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input 
          type="text" 
          placeholder="Search Episode ID..." 
          bind:value={searchQuery}
        />
      </div>

      <div class="filter-tabs">
        <button 
          class="tab-btn {statusFilter === 'all' ? 'active' : ''}" 
          on:click={() => statusFilter = 'all'}
        >
          All
        </button>
        <button 
          class="tab-btn {statusFilter === 'success' ? 'active' : ''}" 
          on:click={() => statusFilter = 'success'}
        >
          Success
        </button>
        <button 
          class="tab-btn {statusFilter === 'failed' ? 'active' : ''}" 
          on:click={() => statusFilter = 'failed'}
        >
          Failed
        </button>
        <button 
          class="tab-btn {statusFilter === 'blocked' ? 'active' : ''}" 
          on:click={() => statusFilter = 'blocked'}
        >
          Blocked
        </button>
      </div>
    </div>

    <div class="episodes-list">
      {#if isLoading}
        <div class="status-msg">
          <div class="spinner"></div>
          <span>Loading episodes...</span>
        </div>
      {:else if filteredEpisodes.length === 0}
        <div class="status-msg">
          <span>No episodes match filter criteria</span>
        </div>
      {:else}
        {#each filteredEpisodes as ep (ep.episode_id)}
          <button 
            class="episode-card {selectedEpisodeId === ep.episode_id ? 'selected' : ''}"
            on:click={() => onSelectEpisode(ep.episode_id)}
          >
            <div class="card-header">
              <span class="episode-id code-font">
                {ep.episode_id ? ep.episode_id.substring(0, 12) + '...' : 'Unknown ID'}
              </span>
              <span class="badge {getStatusBadgeClass(ep.final_status)}">
                {ep.final_status || 'Unknown'}
              </span>
            </div>

            <div class="card-meta">
              <div class="meta-item">
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>{formatTime(ep.started_at)}</span>
              </div>
              <div class="meta-item">
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16m-7 6h7" />
                </svg>
                <span>{ep.step_count || 0} step{ep.step_count === 1 ? '' : 's'}</span>
              </div>
            </div>

            {#if ep.termination_reason}
              <div class="card-footer">
                <span class="reason-label">Reason:</span>
                <span class="reason-val">{ep.termination_reason.replace(/_/g, ' ')}</span>
              </div>
            {/if}

            <div class="card-details">
              <span class="symbol-tag">{ep.symbol || 'BTCUSDT'}</span>
              <span class="mode-tag {ep.mode === 'live' ? 'live' : 'dry'}">{ep.mode || 'dry'}</span>
            </div>
          </button>
        {/each}
      {/if}
    </div>
  </div>
</div>

<style>
  .sidebar {
    width: 340px;
    height: 100%;
    background-color: var(--bg-sidebar);
    border-right: 1px solid var(--border-color);
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
    transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.3s;
    overflow: hidden;
  }

  .sidebar.collapsed {
    width: 0 !important;
    border-right-color: transparent !important;
  }

  .sidebar-content {
    width: 340px;
    height: 100%;
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
  }

  .sidebar-header {
    padding: 1.25rem;
    border-bottom: 1px solid var(--border-color);
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .title-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .title-row h2 {
    font-size: 1.25rem;
    font-weight: 700;
  }

  .count-badge {
    background-color: var(--bg-panel-hover);
    border: 1px solid var(--border-color);
    color: var(--text-secondary);
    padding: 0.125rem 0.5rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
  }

  .search-box {
    display: flex;
    align-items: center;
    background-color: var(--bg-main);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    padding: 0.5rem 0.75rem;
    color: var(--text-muted);
    gap: 0.5rem;
    transition: all 0.2s;
  }

  .search-box:focus-within {
    border-color: var(--color-primary);
    box-shadow: 0 0 0 2px var(--color-primary-light);
  }

  .search-box input {
    background: transparent;
    border: none;
    outline: none;
    color: var(--text-primary);
    font-family: var(--font-sans);
    font-size: 0.875rem;
    width: 100%;
  }

  .filter-tabs {
    display: flex;
    background-color: var(--bg-main);
    padding: 0.25rem;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-color);
  }

  .tab-btn {
    flex: 1;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0.375rem 0;
    border-radius: calc(var(--radius-sm) - 2px);
    color: var(--text-secondary);
    text-transform: capitalize;
  }

  .tab-btn:hover {
    color: var(--text-primary);
  }

  .tab-btn.active {
    background-color: var(--bg-panel);
    color: var(--color-primary);
    border: 1px solid var(--border-color);
    box-shadow: var(--shadow-sm);
  }

  .episodes-list {
    flex: 1;
    overflow-y: auto;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .status-msg {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    padding: 3rem 1rem;
    color: var(--text-muted);
    font-size: 0.875rem;
    text-align: center;
  }

  .spinner {
    width: 24px;
    height: 24px;
    border: 2px solid var(--border-color);
    border-top-color: var(--color-primary);
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .episode-card {
    text-align: left;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding: 1rem;
    background-color: var(--bg-panel);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .episode-card:hover {
    background-color: var(--bg-panel-hover);
    border-color: var(--border-color-hover);
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
  }

  .episode-card.selected {
    background-color: rgba(59, 130, 246, 0.08);
    border-color: var(--color-primary);
    box-shadow: var(--shadow-glow);
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .episode-id {
    color: var(--text-primary);
    font-weight: 500;
  }

  .card-meta {
    display: flex;
    gap: 1rem;
    color: var(--text-muted);
    font-size: 0.75rem;
  }

  .meta-item {
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }

  .card-footer {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.75rem;
    border-top: 1px dashed var(--border-color);
    padding-top: 0.5rem;
  }

  .reason-label {
    color: var(--text-muted);
  }

  .reason-val {
    color: var(--text-secondary);
    font-weight: 500;
    text-overflow: ellipsis;
    overflow: hidden;
    white-space: nowrap;
    text-transform: capitalize;
  }

  .card-details {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.25rem;
  }

  .symbol-tag, .mode-tag {
    font-size: 0.675rem;
    font-weight: 600;
    padding: 0.125rem 0.375rem;
    border-radius: 4px;
    border: 1px solid var(--border-color);
  }

  .symbol-tag {
    background-color: var(--bg-main);
    color: var(--text-secondary);
  }

  .mode-tag.live {
    background-color: rgba(239, 68, 68, 0.08);
    color: var(--color-danger);
    border-color: var(--color-danger-border);
  }

  .mode-tag.dry {
    background-color: var(--bg-main);
    color: var(--text-muted);
  }
</style>
