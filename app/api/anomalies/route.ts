import { promises as fs } from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";

export async function GET(request: Request) {
  const file = path.join(process.cwd(), "public", "data", "anomaly_clusters.json");
  const data = JSON.parse(await fs.readFile(file, "utf8"));
  const threshold = Number(new URL(request.url).searchParams.get("minRisk") ?? "0");
  if (Number.isNaN(threshold)) return NextResponse.json({ error: "minRisk must be a number" }, { status: 400 });
  return NextResponse.json({
    ...data,
    anomalies: data.anomalies.filter((item: { risk_score: number }) => item.risk_score >= threshold),
  });
}
