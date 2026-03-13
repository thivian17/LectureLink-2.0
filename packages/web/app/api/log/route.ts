import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const { level, component, message, detail } = await req.json();
    const timestamp = new Date().toISOString();
    const prefix = `[${timestamp}] [${level?.toUpperCase() ?? "WARN"}] [${component ?? "unknown"}]`;
    const logLine = `${prefix} ${message}${detail ? ` | detail: ${JSON.stringify(detail)}` : ""}`;

    if (level === "error") {
      console.error(logLine);
    } else {
      console.warn(logLine);
    }

    return NextResponse.json({ ok: true });
  } catch {
    return NextResponse.json({ ok: false }, { status: 400 });
  }
}
