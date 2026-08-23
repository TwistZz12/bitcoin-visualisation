import { promises as fs } from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";

export async function GET(_request: Request, context: { params: Promise<{ txid: string }> }) {
  const { txid } = await context.params;
  const file = path.join(process.cwd(), "data", "fixtures", "worm_cluster_transactions.json");
  const source = JSON.parse(await fs.readFile(file, "utf8"));
  const transaction = source.transactions.find((item: { txid: string }) => item.txid === txid);
  if (!transaction) return NextResponse.json({ error: "Transaction not found" }, { status: 404 });
  return NextResponse.json(transaction);
}
