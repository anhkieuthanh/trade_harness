<script>
  export let candles = [];
  export let price = null;
  export let symbol = "BTCUSDT";

  let hoveredCandle = null;
  let chartWidth = 500;
  let chartHeight = 180;
  let paddingLeft = 10;
  let paddingRight = 60;
  let paddingTop = 15;
  let paddingBottom = 25;

  $: ohlcCandles = Array.isArray(candles) ? candles : [];

  // Compute boundaries
  $: prices = ohlcCandles.flatMap(c => [c.high, c.low, c.open, c.close]);
  $: minPrice = prices.length ? Math.min(...prices) * 0.9998 : 0;
  $: maxPrice = prices.length ? Math.max(...prices) * 1.0002 : 100;
  $: priceDiff = maxPrice - minPrice;

  $: maxVol = ohlcCandles.length ? Math.max(...ohlcCandles.map(c => c.volume || 0)) : 1;

  // Map coordinate helpers
  function getX(index, total) {
    const usableWidth = chartWidth - paddingLeft - paddingRight;
    const step = total > 1 ? usableWidth / (total - 1) : usableWidth;
    return paddingLeft + index * step;
  }

  function getY(priceVal) {
    if (priceDiff === 0) return chartHeight / 2;
    const usableHeight = chartHeight - paddingTop - paddingBottom;
    return chartHeight - paddingBottom - ((priceVal - minPrice) / priceDiff * usableHeight);
  }

  function formatPrice(p) {
    if (p === null || p === undefined) return "—";
    return p.toLocaleString([], { minimumFractionDigits: 1, maximumFractionDigits: 2 });
  }

  function formatTime(timestamp) {
    try {
      const date = new Date(timestamp);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (_) {
      return "";
    }
  }
</script>

<div class="candle-chart-container" bind:clientWidth={chartWidth}>
  <div class="chart-header">
    <span class="symbol font-mono">{symbol}</span>
    {#if price}
      <span class="price font-mono">${formatPrice(price)}</span>
    {/if}
    
    {#if hoveredCandle}
      <div class="tooltip-data font-mono">
        <span>O: <span class="val">${formatPrice(hoveredCandle.open)}</span></span>
        <span>H: <span class="val">${formatPrice(hoveredCandle.high)}</span></span>
        <span>L: <span class="val">${formatPrice(hoveredCandle.low)}</span></span>
        <span>C: <span class="val">${formatPrice(hoveredCandle.close)}</span></span>
        <span>V: <span class="val">{hoveredCandle.volume ? hoveredCandle.volume.toFixed(2) : "0.00"}</span></span>
      </div>
    {/if}
  </div>

  {#if ohlcCandles.length === 0}
    <div class="no-data">
      <span>No candles to render</span>
    </div>
  {:else}
    <svg class="chart-svg" width={chartWidth} height={chartHeight}>
      <!-- Grid Lines -->
      <line x1={paddingLeft} y1={getY(minPrice)} x2={chartWidth - paddingRight} y2={getY(minPrice)} class="grid-line" />
      <line x1={paddingLeft} y1={getY((minPrice + maxPrice) / 2)} x2={chartWidth - paddingRight} y2={getY((minPrice + maxPrice) / 2)} class="grid-line" />
      <line x1={paddingLeft} y1={getY(maxPrice)} x2={chartWidth - paddingRight} y2={getY(maxPrice)} class="grid-line" />

      <!-- Price Labels (Right Y Axis) -->
      <text x={chartWidth - paddingRight + 5} y={getY(maxPrice) + 4} class="axis-label font-mono">${formatPrice(maxPrice)}</text>
      <text x={chartWidth - paddingRight + 5} y={getY((minPrice + maxPrice) / 2) + 4} class="axis-label font-mono">${formatPrice((minPrice + maxPrice) / 2)}</text>
      <text x={chartWidth - paddingRight + 5} y={getY(minPrice) + 4} class="axis-label font-mono">${formatPrice(minPrice)}</text>

      <!-- Draw Candles & Volume -->
      {#each ohlcCandles as candle, idx}
        {@const x = getX(idx, ohlcCandles.length)}
        {@const yOpen = getY(candle.open)}
        {@const yClose = getY(candle.close)}
        {@const yHigh = getY(candle.high)}
        {@const yLow = getY(candle.low)}
        {@const isUp = candle.close >= candle.open}
        {@const colorClass = isUp ? 'green' : 'red'}
        {@const candleWidth = Math.max(6, Math.min(18, (chartWidth - paddingLeft - paddingRight) / ohlcCandles.length * 0.7))}
        
        <!-- Wick (High/Low line) -->
        <line x1={x} y1={yHigh} x2={x} y2={yLow} class="wick {colorClass}" />

        <!-- Real Body (Open/Close rect) -->
        <rect 
          x={x - candleWidth / 2} 
          y={Math.min(yOpen, yClose)} 
          width={candleWidth} 
          height={Math.max(1.5, Math.abs(yOpen - yClose))} 
          class="body-rect {colorClass}" 
          rx="1"
        />

        <!-- Volume Bar (drawn at bottom 15% of chart) -->
        {@const volHeight = maxVol > 0 ? (candle.volume || 0) / maxVol * 25 : 0}
        <rect 
          x={x - candleWidth / 2} 
          y={chartHeight - paddingBottom - volHeight} 
          width={candleWidth} 
          height={volHeight} 
          class="volume-rect {colorClass}"
          opacity="0.2"
        />

        <!-- Time Axis Tick -->
        {#if idx % Math.max(1, Math.floor(ohlcCandles.length / 5)) === 0}
          <line x1={x} y1={chartHeight - paddingBottom} x2={x} y2={chartHeight - paddingBottom + 4} class="axis-tick" />
          <text x={x} y={chartHeight - paddingBottom + 16} class="time-label font-mono" text-anchor="middle">
            {formatTime(candle.open_time)}
          </text>
        {/if}

        <!-- Interactive Overlay Hover Target -->
        <rect 
          x={x - (chartWidth - paddingLeft - paddingRight) / ohlcCandles.length / 2}
          y={paddingTop}
          width={(chartWidth - paddingLeft - paddingRight) / ohlcCandles.length}
          height={chartHeight - paddingTop - paddingBottom}
          fill="transparent"
          on:mouseenter={() => hoveredCandle = candle}
          on:mouseleave={() => hoveredCandle = null}
        />
      {/each}
    </svg>
  {/if}
</div>

<style>
  .candle-chart-container {
    background-color: var(--bg-main);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    padding: 0.75rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    position: relative;
    user-select: none;
  }

  .chart-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    font-size: 0.8125rem;
    flex-wrap: wrap;
    min-height: 20px;
  }

  .symbol {
    font-weight: 700;
    color: var(--text-primary);
  }

  .price {
    font-weight: 600;
    color: var(--text-secondary);
  }

  .tooltip-data {
    display: flex;
    gap: 0.75rem;
    color: var(--text-muted);
    font-size: 0.75rem;
    margin-left: auto;
  }

  .tooltip-data .val {
    color: var(--text-secondary);
    font-weight: 500;
  }

  .no-data {
    height: 120px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
    font-size: 0.875rem;
  }

  .chart-svg {
    display: block;
    width: 100%;
  }

  .grid-line {
    stroke: var(--border-color);
    stroke-dasharray: 2 3;
    stroke-width: 1;
  }

  .axis-label {
    fill: var(--text-muted);
    font-size: 0.675rem;
    alignment-baseline: middle;
  }

  .time-label {
    fill: var(--text-muted);
    font-size: 0.675rem;
  }

  .axis-tick {
    stroke: var(--border-color);
    stroke-width: 1;
  }

  .wick {
    stroke-width: 1.5;
  }

  .wick.green {
    stroke: var(--color-success);
  }

  .wick.red {
    stroke: var(--color-danger);
  }

  .body-rect.green {
    fill: var(--color-success);
  }

  .body-rect.red {
    fill: var(--color-danger);
  }

  .volume-rect.green {
    fill: var(--color-success);
  }

  .volume-rect.red {
    fill: var(--color-danger);
  }
</style>
