import { promises as fs } from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";

export async function GET() {
  const file = path.join(process.cwd(), "public", "data", "demo_utxo_graph.json");
  const graph = JSON.parse(await fs.readFile(file, "utf8"));
  return NextResponse.json(graph);
}
