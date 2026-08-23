import { promises as fs } from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";

export async function GET() {
  const directory = path.join(process.cwd(), "data", "fixtures");
  const names = (await fs.readdir(directory)).filter(name => name.endsWith(".json"));
  const datasets = await Promise.all(names.map(async name => {
    const data = JSON.parse(await fs.readFile(path.join(directory, name), "utf8"));
    return { name, transaction_count: data.transactions?.length ?? 0, anomaly_count: 0 };
  }));
  return NextResponse.json({ datasets, selected: "worm_cluster_transactions.json" });
}
