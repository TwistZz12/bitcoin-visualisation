"use client";

import { useCallback, useEffect, useState } from "react";
import type { AnomalyCluster, AnomalyData, UtxoGraphData } from "@/types/graph";
import TransactionGraph from "./TransactionGraph";

function shortenId(id: string) { return id.length > 16 ? `${id.slice(0, 8)}…${id.slice(-4)}` : id; }
function formatBtc(value: number) { return value < 0.01 ? value.toFixed(8) : value.toFixed(4); }

type TransactionDetails = {
  txid: string;
  timestamp: string;
  block_height: number;
  inputs: { prev_txid: string; prev_vout: number }[];
  outputs: { vout: number; address: string; value_btc: number }[];
};

type AnalysisMetadata = {
  dataset: string;
  dataset_type: string;
  transaction_count: number;
  api_version?: string;
  block_height?: number;
  block_hash?: string;
  retrieved_at?: string;
  confirmed_transaction_count?: number;
  mempool_transaction_count?: number;
  stale?: boolean;
};

type DatasetOption = { name: string; transaction_count: number; anomaly_count: number };
type LiveOverview = { height: number; timestamp: number; transaction_count: number; anomaly_count: number; max_risk: number };

export default function Home() {
  const apiBase = process.env.NEXT_PUBLIC_ANALYSIS_API_URL ?? "";
  const [score, setScore] = useState(65);
  const [playing, setPlaying] = useState(false);
  const [anomalies, setAnomalies] = useState<AnomalyCluster[]>([]);
  const [graph, setGraph] = useState<UtxoGraphData | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [transactionDetails, setTransactionDetails] = useState<TransactionDetails | null>(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [metadata, setMetadata] = useState<AnalysisMetadata | null>(null);
  const [datasets, setDatasets] = useState<DatasetOption[]>([]);
  const [dataset, setDataset] = useState<string | null>(null);
  const [liveMode, setLiveMode] = useState(false);
  const [liveLoading, setLiveLoading] = useState(false);
  const [liveOverview, setLiveOverview] = useState<LiveOverview[]>([]);
  const datasetQuery = dataset ? `?dataset=${encodeURIComponent(dataset)}` : "";

  const loadTransactionDetails = useCallback(async (txid: string) => {
    setDetailsLoading(true);
    try {
      const endpoint = liveMode ? `/api/live/transactions/${encodeURIComponent(txid)}` : `/api/transactions/${encodeURIComponent(txid)}${datasetQuery}`;
      const response = await fetch(`${apiBase}${endpoint}`);
      if (!response.ok) throw new Error("Unable to load transaction details");
      setTransactionDetails(await response.json() as TransactionDetails);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to load transaction details");
    } finally { setDetailsLoading(false); }
  }, [apiBase, datasetQuery, liveMode]);

  const loadLiveAnalysis = useCallback(async () => {
    setLiveLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiBase}/api/live/analysis?window_blocks=6&transactions_per_block=25&mempool_transactions=10`);
      if (!response.ok) throw new Error("Unable to load the rolling Bitcoin transaction window");
      const result = await response.json() as { metadata: AnalysisMetadata; graph: UtxoGraphData; anomalies: AnomalyCluster[]; overview: LiveOverview[] };
      setMetadata(result.metadata);
      setGraph(result.graph);
      setAnomalies(result.anomalies);
      setLiveOverview(result.overview);
      setActiveId(result.anomalies[0]?.id ?? null);
      setTransactionDetails(null);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to load live Bitcoin data");
    } finally { setLiveLoading(false); }
  }, [apiBase]);

  useEffect(() => {
    if (!liveMode) return;
    const initialLoad = window.setTimeout(() => void loadLiveAnalysis(), 0);
    const interval = window.setInterval(() => void loadLiveAnalysis(), 30_000);
    return () => { window.clearTimeout(initialLoad); window.clearInterval(interval); };
  }, [liveMode, loadLiveAnalysis]);

  useEffect(() => {
    async function loadData() {
      try {
        setError(null);
        const [anomalyResponse, graphResponse, metadataResponse, datasetsResponse] = await Promise.all([fetch(`${apiBase}/api/anomalies${datasetQuery}`), fetch(`${apiBase}/api/graph${datasetQuery}`), fetch(`${apiBase}/api/metadata${datasetQuery}`), fetch(`${apiBase}/api/datasets`)]);
        if (!anomalyResponse.ok || !graphResponse.ok || !metadataResponse.ok || !datasetsResponse.ok) throw new Error("Unable to load analysis data from the backend API");
        const anomalyData: AnomalyData = await anomalyResponse.json();
        const graphData: UtxoGraphData = await graphResponse.json();
        const metadataData = await metadataResponse.json() as AnalysisMetadata;
        const datasetData = await datasetsResponse.json() as { datasets: DatasetOption[]; selected: string };
        setMetadata(metadataData);
        setDatasets(datasetData.datasets);
        if (!dataset) setDataset(metadataData.dataset);
        setAnomalies(anomalyData.anomalies);
        setGraph(graphData);
        setLiveOverview([]);
        setActiveId(anomalyData.anomalies[0]?.id ?? null);
      } catch (caughtError) {
        setError(caughtError instanceof Error ? caughtError.message : "An unexpected error occurred");
      } finally { setLoading(false); }
    }
    loadData();
  }, [apiBase, dataset, datasetQuery]);

  if (loading) return <main className="loading-state">Loading transaction graph data…</main>;
  const activeCluster = anomalies.find(anomaly => anomaly.id === activeId);
  if (error || !graph) return <main className="loading-state">Unable to load data: {error ?? "The analysis API returned no graph"}</main>;
  if (!activeCluster) return <main className="loading-state"><div className="empty-state"><b>No anomalous transactions detected</b><span>{metadata?.dataset ?? "This dataset"} contains no patterns above the current detection rules.</span><small>Choose a dataset with a known anomaly, such as the Worm demo, to explore the anomaly graph.</small></div></main>;

  const visibleAnomalies = anomalies.filter(anomaly => anomaly.risk_score >= score);
  const activeTransactionId = activeCluster.transactions[0];

  return <main>
    <header><div className="brand">◈ <b>ChainScope</b><span>Anomaly Transaction Graph Explorer</span></div><div className="live"><button className={`mode-button ${!liveMode ? "active" : ""}`} onClick={() => setLiveMode(false)}>Demo</button><button className={`mode-button ${liveMode ? "active" : ""}`} onClick={() => setLiveMode(true)}>Live</button>{liveMode ? ` · block ${metadata?.block_height ?? "…"}${metadata?.stale ? " · last successful snapshot" : liveLoading ? " · refreshing…" : ""}` : <><span> · {metadata?.dataset_type ?? "Analysis API"} · </span><select className="dataset-select" value={dataset ?? ""} onChange={event => { setDataset(event.target.value); setTransactionDetails(null); }} aria-label="Select transaction dataset">{datasets.map(option => <option value={option.name} key={option.name}>{option.name} · {option.transaction_count} tx</option>)}</select></>}</div></header>
    <nav><button className="play" onClick={() => setPlaying(!playing)}>{playing ? "Ⅱ" : "▶"}</button><div><b>{liveMode ? `Block ${metadata?.block_height ?? "…"}` : "2024-05-18"}</b><small>{liveMode ? `${metadata?.confirmed_transaction_count ?? 0} confirmed + ${metadata?.mempool_transaction_count ?? 0} mempool transactions` : "Demo transaction window"}</small></div>{liveMode ? <div className="live-overview" aria-label="Rolling block window overview">{liveOverview.map(block => <div className="block-bar" key={block.height} title={`Block ${block.height}: ${block.transaction_count} transactions, ${block.anomaly_count} anomalies`}><i style={{ height: `${Math.max(12, Math.min(100, block.max_risk))}%` }} /><small>{block.height}</small><b>{block.anomaly_count}</b></div>)}</div> : <div className="timeline"><i /><b style={{ left: playing ? "72%" : "53%" }} /></div>}<div className="tags">{["Collection", "Split", "Worm"].map(tag => <em key={tag}>{tag}</em>)}</div></nav>
    <section className="layout">
      <aside><label>Anomaly threshold <b>≥ {score}</b><input type="range" min="50" max="95" value={score} onChange={event => setScore(+event.target.value)} /></label><p className="eyebrow">PATTERN QUEUE</p><h1>Anomaly clusters <sup>{visibleAnomalies.length}</sup></h1>{visibleAnomalies.map(anomaly => <button className={`case ${anomaly.id === activeId ? "selected" : ""}`} onClick={() => setActiveId(anomaly.id)} key={anomaly.id}><i>{anomaly.pattern}</i><span><b>{anomaly.pattern} / {shortenId(anomaly.transactions[0])}</b><small>{anomaly.transaction_count} transaction · {formatBtc(anomaly.value_btc)} BTC</small></span><strong>{anomaly.risk_score}</strong></button>)}</aside>
      <article>
        <div className="title"><div><p className="eyebrow">GRAPH EXPLORER · UTXO ANOMALY CLUSTER</p><h2>{activeCluster.pattern} / {activeCluster.transaction_count} transaction{activeCluster.transaction_count > 1 ? "s" : ""}</h2></div><div className="legend"><span className="tx-dot" /> Transaction <span className="utxo-dot" /> UTXO <span className="worm-dot" /> Main value <span className="reuse-key" /> Address reuse</div></div>
        <div className="graph">
          <TransactionGraph key={activeCluster.id} graph={graph} cluster={activeCluster} onTransactionSelect={loadTransactionDetails} />
        </div><footer>Interactive anomaly cluster · {graph.metadata.node_count} nodes · {graph.metadata.edge_count} relationships · {graph.metadata.reused_address_count ?? 0} reused addresses</footer>
      </article>
      <aside className="explain"><p className="eyebrow">EXPLAINABILITY</p><h2>Anomaly rationale <sup>Risk {activeCluster.risk_score}</sup></h2><div className="card"><i>{activeCluster.pattern}</i><div><b>{activeCluster.pattern} / {activeTransactionId}</b><p>Evidence combines UTXO lineage, temporal density, value structure, address reuse, and available entity labels.</p></div></div><div className="metrics"><span>Transactions<b>{activeCluster.transaction_count}</b></span><span>Value involved<b>{formatBtc(activeCluster.value_btc)} BTC</b></span><span>Avg. hop<b>{activeCluster.features?.avg_hop_seconds ?? "–"} sec</b></span><span>Address reuse<b>{activeCluster.features?.address_reuse_count ?? "–"}</b></span></div>{activeCluster.entity_labels?.length ? <><h3>Address intelligence</h3><div className="entity-labels">{activeCluster.entity_labels.map(item => <div key={item.address}><b>{item.category}: {item.entity}</b><small>{shortenId(item.address)} · {item.confidence} confidence</small></div>)}</div></> : null}<h3>Evidence</h3><div className="evidence">{activeCluster.evidence.map(item => <p key={item}>✓ {item}</p>)}</div><h3>Analysis path</h3><div className="steps">Detect ━ <b>Locate</b> ━ Verify</div>{transactionDetails && <div className="transaction-details"><b>{shortenId(transactionDetails.txid)}</b><span>{new Date(transactionDetails.timestamp).toLocaleString()} · block {transactionDetails.block_height}</span><span>{transactionDetails.inputs.length} inputs · {transactionDetails.outputs.length} outputs</span><small>{transactionDetails.outputs.map(output => `${formatBtc(output.value_btc)} BTC → ${output.address}`).join(" · ")}</small></div>}<button className="inspect" onClick={() => loadTransactionDetails(activeTransactionId)}>{detailsLoading ? "Loading transaction details…" : "Open transaction details →"}</button></aside>
    </section>
  </main>;
}
