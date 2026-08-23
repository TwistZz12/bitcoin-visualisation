import { promises as fs } from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";

export async function GET() {
  const graphFile = path.join(process.cwd(), "public", "data", "demo_utxo_graph.json");
  const anomalyFile = path.join(process.cwd(), "public", "data", "anomaly_clusters.json");
  const [graph, anomalies] = await Promise.all([
    fs.readFile(graphFile, "utf8").then(JSON.parse),
    fs.readFile(anomalyFile, "utf8").then(JSON.parse),
  ]);
  return NextResponse.json({
    service: "chainscope-web-api",
    dataset: anomalies.metadata.source_file ?? "generated analysis dataset",
    dataset_type: "Synthetic demo dataset",
    transaction_count: graph.metadata.transaction_count,
    anomaly_count: anomalies.metadata.anomaly_count,
  });
}
