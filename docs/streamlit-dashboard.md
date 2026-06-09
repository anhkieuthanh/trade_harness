# Streamlit forward-test dashboard

## Install

```bash
cd /Users/atif/Public/TradeHarness
python3 -m pip install -r requirements.txt
```

## Run

```bash
cd /Users/atif/Public/TradeHarness
python3 -m streamlit run streamlit_app.py --server.port 8766
```

Open:

- `http://127.0.0.1:8766`

## What it shows

- runtime alive vs stale/dead from latest trajectory timestamp
- symbol, mode, poll interval, episode count
- latest cycle summary
- recent activity table
- recent final-status and harness-decision counts
- raw latest payload for debugging

## Notes

- default data source: `var/trajectories/episodes.jsonl`
- it reads `.env` for `POLL_INTERVAL_SECONDS`, `SYMBOL`, and `DRY_RUN`
- if runtime is expected to trade but dashboard only shows inspect/final-response cycles, check task/gate/runtime config first
