import { NextResponse } from "next/server";

export function GET() {
  return NextResponse.json({ status: "ok", service: "chainscope-web", version: "1.0.0" });
}
