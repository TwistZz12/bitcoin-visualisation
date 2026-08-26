"use client";

import cytoscape, { type Core, type ElementDefinition, type NodeSingular } from "cytoscape";
import { useEffect, useMemo, useRef, useState } from "react";
import type { AnomalyCluster, GraphNode, UtxoGraphData } from "@/types/graph";


type SelectedNode = {
  kind: "transaction" | "utxo";
  title: string;
  subtitle: string;
  txid?: string;
  address?: string;
};

function shortId(id: string) {
  return id.length > 20 ? `${id.slice(0, 10)}…${id.slice(-5)}` : id;
}

function runLayout(core: Core) {
  core.layout({
    name: "cose",
    animate: false,
    fit: true,
    padding: 48,
    nodeRepulsion: () => 7800,
    idealEdgeLength: edge => edge.data("type") === "address_reuse" ? 95 : 48,
    edgeElasticity: edge => edge.data("type") === "address_reuse" ? 35 : 120,
    nestingFactor: 1.1,
    gravity: 0.38,
    numIter: 1200,
    randomize: true,
  }).run();
}

function selectedNodeData(node: NodeSingular): SelectedNode {
  if (node.data("type") === "transaction") {
    return {
      kind: "transaction",
      txid: node.data("txid"),
      title: `Transaction ${shortId(node.data("txid"))}`,
      subtitle: `${node.data("input_count")} inputs · ${node.data("output_count")} outputs · block ${node.data("block_height")}`,
    };
  }
  return {
    kind: "utxo",
    title: `UTXO #${node.data("vout")} · ${Number(node.data("value_btc")).toFixed(4)} BTC`,
    subtitle: node.data("spent_by") ? `Spent by ${shortId(node.data("spent_by"))}` : "Unspent output",
    address: node.data("address"),
  };
}

export default function TransactionGraph({ graph, cluster, onTransactionSelect }: { graph: UtxoGraphData; cluster: AnomalyCluster; onTransactionSelect?: (txid: string) => void }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const coreRef = useRef<Core | null>(null);
  const [showBackground, setShowBackground] = useState(false);
  const [showAddressReuse, setShowAddressReuse] = useState(true);
  const [selectedNode, setSelectedNode] = useState<SelectedNode | null>(null);

  const elements = useMemo(() => {
    const activeTransactions = new Set(cluster.transactions);
    const nodesById = new Map(graph.nodes.map(node => [node.id, node]));
    const outputsByTransaction = new Map<string, GraphNode[]>();
    for (const node of graph.nodes) {
      if (node.type !== "utxo" || !node.txid) continue;
      outputsByTransaction.set(node.txid, [...(outputsByTransaction.get(node.txid) ?? []), node]);
    }
    const mainUtxos = new Set<string>();
    const smallUtxos = new Set<string>();
    for (const outputs of outputsByTransaction.values()) {
      const largest = Math.max(...outputs.map(output => output.value_btc ?? 0));
      for (const output of outputs) {
        if ((output.value_btc ?? 0) === largest) mainUtxos.add(output.id);
        if ((output.value_btc ?? 0) <= largest * 0.05) smallUtxos.add(output.id);
      }
    }

    const visibleNodeIds = new Set<string>();
    for (const node of graph.nodes) {
      const active = node.type === "transaction"
        ? activeTransactions.has(node.txid ?? "")
        : activeTransactions.has(node.txid ?? "");
      if (showBackground || active) visibleNodeIds.add(node.id);
    }
    // In focused mode, include the one-hop UTXO lineage around the selected
    // anomaly so different single-transaction clusters produce distinct views.
    if (!showBackground) {
      for (const edge of graph.edges) {
        const source = nodesById.get(edge.source);
        const target = nodesById.get(edge.target);
        if (activeTransactions.has(source?.txid ?? "") || activeTransactions.has(target?.txid ?? "")) {
          visibleNodeIds.add(edge.source);
          visibleNodeIds.add(edge.target);
        }
      }
    }
    // Keep the funding UTXO and its source transaction visible at the head of the anomaly.
    for (const edge of graph.edges.filter(item => item.type === "spends")) {
      const target = nodesById.get(edge.target);
      if (target?.txid && activeTransactions.has(target.txid)) {
        visibleNodeIds.add(edge.source);
        const creator = graph.edges.find(item => item.type === "creates" && item.target === edge.source);
        if (creator) visibleNodeIds.add(creator.source);
      }
    }

    const result: ElementDefinition[] = [];
    for (const node of graph.nodes) {
      if (!visibleNodeIds.has(node.id)) continue;
      const active = activeTransactions.has(node.txid ?? "");
      const classes = [node.type, active ? "anomaly" : "context"];
      if (mainUtxos.has(node.id)) classes.push("main-value");
      if (smallUtxos.has(node.id)) classes.push("small-output");
      result.push({
        group: "nodes",
        data: {
          ...node,
          label: node.type === "transaction" ? shortId(node.txid ?? node.id) : `${node.value_btc?.toFixed(3)} BTC`,
        },
        classes: classes.join(" "),
      });
    }
    for (const edge of graph.edges) {
      if (!visibleNodeIds.has(edge.source) || !visibleNodeIds.has(edge.target)) continue;
      if (edge.type === "address_reuse" && !showAddressReuse) continue;
      const source = nodesById.get(edge.source);
      const target = nodesById.get(edge.target);
      const active = activeTransactions.has(source?.txid ?? "") || activeTransactions.has(target?.txid ?? "");
      const mainPath = edge.type !== "address_reuse" && (mainUtxos.has(edge.source) || mainUtxos.has(edge.target));
      result.push({
        group: "edges",
        data: edge,
        classes: `${edge.type} ${active ? "anomaly" : "context"} ${mainPath ? "main-path" : "side-path"}`,
      });
    }
    return result;
  }, [cluster, graph, showAddressReuse, showBackground]);

  useEffect(() => {
    if (!containerRef.current) return;
    const core = cytoscape({
      container: containerRef.current,
      elements,
      minZoom: 0.18,
      maxZoom: 3.5,
      wheelSensitivity: 0.18,
      style: [
        { selector: "node", style: { "font-family": "Arial, sans-serif", "font-size": 7, "text-valign": "bottom", "text-margin-y": 6, color: "#b7c9cd", "text-outline-color": "#071014", "text-outline-width": 2 } },
        { selector: "node.transaction", style: { shape: "ellipse", width: 25, height: 25, "background-color": "#10282d", "border-width": 2, "border-color": "#5fe0da", label: "data(label)" } },
        { selector: "node.transaction.anomaly", style: { width: 29, height: 29, "background-color": "#17383b", "border-width": 3, "border-color": "#72f2e8", color: "#eaffff", "font-size": 8 } },
        { selector: "node.utxo", style: { shape: "round-rectangle", width: "mapData(value_btc, 0, 8, 7, 31)", height: "mapData(value_btc, 0, 8, 7, 31)", "background-color": "#517ac5", "border-width": 1, "border-color": "#83aaf6", label: "" } },
        { selector: "node.utxo.anomaly.main-value", style: { "background-color": "#ffad58", "border-width": 2, "border-color": "#ffe0af", "shadow-blur": 13, "shadow-color": "#ff9b3d", "shadow-opacity": 0.75 } },
        { selector: "node.utxo.anomaly.small-output", style: { "background-color": "#697fd2", "border-color": "#9eaef5" } },
        { selector: "node.context", style: { opacity: 0.32 } },
        { selector: "edge", style: { width: 1.2, "curve-style": "bezier", "target-arrow-shape": "triangle", "arrow-scale": 0.65, opacity: 0.5 } },
        { selector: "edge.creates", style: { "line-color": "#5885d5", "target-arrow-color": "#5885d5" } },
        { selector: "edge.spends", style: { "line-color": "#4fc5c2", "target-arrow-color": "#4fc5c2" } },
        { selector: "edge.main-path.anomaly", style: { width: 2.7, opacity: 0.92, "line-color": "#ffad58", "target-arrow-color": "#ffad58", "shadow-blur": 7, "shadow-color": "#ffad58", "shadow-opacity": 0.5 } },
        { selector: "edge.side-path.anomaly", style: { opacity: 0.48 } },
        { selector: "edge.address_reuse", style: { width: 0.8, opacity: 0.22, "line-style": "dashed", "line-color": "#aeb7bd", "target-arrow-shape": "none", "curve-style": "unbundled-bezier", "control-point-distances": 35 } },
        { selector: ":selected", style: { "overlay-color": "#fff2cb", "overlay-opacity": 0.16, "overlay-padding": 7 } },
      ],
    });
    coreRef.current = core;
    core.on("tap", "node", event => {
      const details = selectedNodeData(event.target);
      setSelectedNode(details);
      if (details.kind === "transaction" && details.txid) onTransactionSelect?.(details.txid);
    });
    core.on("tap", event => { if (event.target === core) setSelectedNode(null); });
    runLayout(core);
    return () => {
      core.destroy();
      coreRef.current = null;
    };
  }, [elements, onTransactionSelect]);

  return <div className="cy-shell">
    <div className="cy-toolbar">
      <button onClick={() => coreRef.current?.fit(undefined, 45)}>Fit graph</button>
      <button onClick={() => coreRef.current && runLayout(coreRef.current)}>Re-layout</button>
      <button className={showBackground ? "active" : ""} onClick={() => setShowBackground(value => !value)}>Context</button>
      <button className={showAddressReuse ? "active" : ""} onClick={() => setShowAddressReuse(value => !value)}>Address links</button>
    </div>
    <div className="cy-canvas" ref={containerRef} aria-label="Interactive Bitcoin UTXO transaction graph" />
    <div className="cy-hint">Scroll to zoom · Drag to pan · Select a node for details</div>
    {selectedNode && <div className="node-inspector">
      <small>{selectedNode.kind === "transaction" ? "TRANSACTION" : "OUTPUT UTXO"}</small>
      <b>{selectedNode.title}</b>
      <span>{selectedNode.subtitle}</span>
      {selectedNode.address && <code>{selectedNode.address}</code>}
    </div>}
  </div>;
}
