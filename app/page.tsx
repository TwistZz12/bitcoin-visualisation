"use client";

import { useCallback, useEffect, useState } from "react";
import type { AnomalyCluster, AnomalyData, UtxoGraphData } from "@/types/graph";
import TransactionGraph from "./TransactionGraph";

function shortenId(id: string) { return id.length > 16 ? `${id.slice(0, 8)}…${id.slice(-4)}` : id; }

type TransactionDetails = {
  txid: string;
  timestamp: string;
  block_height: number;
  inputs: { prev_txid: string; prev_vout: number }[];
  outputs: { vout: number; address: string; value_btc: number }[];
};

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

  const loadTransactionDetails = useCallback(async (txid: string) => {
    setDetailsLoading(true);
    try {
      const response = await fetch(`${apiBase}/api/transactions/${encodeURIComponent(txid)}`);
      if (!response.ok) throw new Error("Unable to load transaction details");
      setTransactionDetails(await response.json() as TransactionDetails);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to load transaction details");
    } finally { setDetailsLoading(false); }
  }, [apiBase]);

  useEffect(() => {
    async function loadData() {
      try {
        const [anomalyResponse, graphResponse] = await Promise.all([fetch(`${apiBase}/api/anomalies`), fetch(`${apiBase}/api/graph`)]);
        if (!anomalyResponse.ok || !graphResponse.ok) throw new Error("Unable to load analysis data from the backend API");
        const anomalyData: AnomalyData = await anomalyResponse.json();
        const graphData: UtxoGraphData = await graphResponse.json();
        setAnomalies(anomalyData.anomalies);
        setGraph(graphData);
        setActiveId(anomalyData.anomalies[0]?.id ?? null);
      } catch (caughtError) {
        setError(caughtError instanceof Error ? caughtError.message : "An unexpected error occurred");
      } finally { setLoading(false); }
    }
    loadData();
  }, [apiBase]);

  if (loading) return <main className="loading-state">Loading transaction graph data…</main>;
  const activeCluster = anomalies.find(anomaly => anomaly.id === activeId);
  if (error || !graph || !activeCluster) return <main className="loading-state">Unable to load data: {error ?? "No anomalous transactions were detected"}</main>;

  const visibleAnomalies = anomalies.filter(anomaly => anomaly.risk_score >= score);
  const activeTransactionId = activeCluster.transactions[0];

  return <main>
    <header><div className="brand">◈ <b>ChainScope</b><span>Anomaly Transaction Graph Explorer</span></div><div className="live">● Local demo data · {graph.metadata.transaction_count} transactions</div></header>
    <nav><button className="play" onClick={() => setPlaying(!playing)}>{playing ? "Ⅱ" : "▶"}</button><div><b>2024-05-18</b><small>Demo transaction window</small></div><div className="timeline"><i /><b style={{ left: playing ? "72%" : "53%" }} /></div><div className="tags">{["Collection", "Split", "Worm"].map(tag => <em key={tag}>{tag}</em>)}</div></nav>
    <section className="layout">
      <aside><label>Anomaly threshold <b>≥ {score}</b><input type="range" min="50" max="95" value={score} onChange={event => setScore(+event.target.value)} /></label><p className="eyebrow">PATTERN QUEUE</p><h1>Anomaly clusters <sup>{visibleAnomalies.length}</sup></h1>{visibleAnomalies.map(anomaly => <button className={`case ${anomaly.id === activeId ? "selected" : ""}`} onClick={() => setActiveId(anomaly.id)} key={anomaly.id}><i>{anomaly.pattern}</i><span><b>{anomaly.pattern} / {shortenId(anomaly.transactions[0])}</b><small>{anomaly.transaction_count} transaction · {anomaly.value_btc.toFixed(2)} BTC</small></span><strong>{anomaly.risk_score}</strong></button>)}</aside>
      <article>
        <div className="title"><div><p className="eyebrow">GRAPH EXPLORER · UTXO ANOMALY CLUSTER</p><h2>{activeCluster.pattern} / {activeCluster.transaction_count} transaction{activeCluster.transaction_count > 1 ? "s" : ""}</h2></div><div className="legend"><span className="tx-dot" /> Transaction <span className="utxo-dot" /> UTXO <span className="worm-dot" /> Main value <span className="reuse-key" /> Address reuse</div></div>
        <div className="graph">
          <TransactionGraph graph={graph} cluster={activeCluster} onTransactionSelect={loadTransactionDetails} />
        </div><footer>Interactive anomaly cluster · {graph.metadata.node_count} nodes · {graph.metadata.edge_count} relationships · {graph.metadata.reused_address_count ?? 0} reused addresses</footer>
      </article>
      <aside className="explain"><p className="eyebrow">EXPLAINABILITY</p><h2>Anomaly rationale <sup>Risk {activeCluster.risk_score}</sup></h2><div className="card"><i>{activeCluster.pattern}</i><div><b>{activeCluster.pattern} / {activeTransactionId}</b><p>Evidence combines UTXO lineage, temporal density, value structure, and address reuse.</p></div></div><div className="metrics"><span>Transactions<b>{activeCluster.transaction_count}</b></span><span>Value involved<b>{activeCluster.value_btc.toFixed(2)} BTC</b></span><span>Avg. hop<b>{activeCluster.features?.avg_hop_seconds ?? "–"} sec</b></span><span>Address reuse<b>{activeCluster.features?.address_reuse_count ?? "–"}</b></span></div><h3>Evidence</h3><div className="evidence">{activeCluster.evidence.map(item => <p key={item}>✓ {item}</p>)}</div><h3>Analysis path</h3><div className="steps">Detect ━ <b>Locate</b> ━ Verify</div>{transactionDetails && <div className="transaction-details"><b>{shortenId(transactionDetails.txid)}</b><span>{new Date(transactionDetails.timestamp).toLocaleString()} · block {transactionDetails.block_height}</span><span>{transactionDetails.inputs.length} inputs · {transactionDetails.outputs.length} outputs</span><small>{transactionDetails.outputs.map(output => `${output.value_btc.toFixed(4)} BTC → ${output.address}`).join(" · ")}</small></div>}<button className="inspect" onClick={() => loadTransactionDetails(activeTransactionId)}>{detailsLoading ? "Loading transaction details…" : "Open transaction details →"}</button></aside>
    </section>
  </main>;
}
