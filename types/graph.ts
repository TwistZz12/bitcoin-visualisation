export type GraphNodeType = "transaction" | "utxo";
export type GraphEdgeType = "creates" | "spends" | "address_reuse";

export interface GraphNode {
  id: string;
  type: GraphNodeType;

  // Transaction 节点字段
  txid?: string;
  timestamp?: string;
  block_height?: number;
  input_count?: number;
  output_count?: number;

  // UTXO 节点字段
  vout?: number;
  address?: string;
  value_btc?: number;
  spent_by?: string | null;
  external?: boolean;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: GraphEdgeType;
  address?: string;
}

export interface UtxoGraphData {
  metadata: {
    transaction_count: number;
    node_count: number;
    edge_count: number;
    reused_address_count?: number;
  };
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface AnomalyCluster {
  id: string;
  pattern: "Collection" | "Split" | "Worm";
  risk_score: number;
  transactions: string[];
  transaction_count: number;
  value_btc: number;
  time_range: {
    start: string;
    end: string;
  };
  features?: {
    chain_length: number;
    hop_count: number;
    duration_seconds: number;
    avg_hop_seconds: number;
    unique_address_count: number;
    address_reuse_count: number;
    address_reuse_ratio: number;
    small_output_count: number;
    small_output_ratio: number;
    avg_main_output_ratio: number;
    avg_branching_factor: number;
    value_retention_ratio: number;
  };
  evidence: string[];
}

export interface AnomalyData {
  metadata: {
    source_transaction_count: number;
    anomaly_count: number;
    source_file?: string;
    detector_version?: string;
  };
  anomalies: AnomalyCluster[];
}
