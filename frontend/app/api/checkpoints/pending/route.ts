import { NextRequest, NextResponse } from "next/server";
import { fetchPendingCheckpoints } from "../_utils";

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const rawLimit = Number(searchParams.get("limit") || "100");
    const limit = Number.isFinite(rawLimit) ? rawLimit : 100;

    const result = await fetchPendingCheckpoints(limit);
    return NextResponse.json(result.data, { status: result.status });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      { error: `Failed to fetch pending checkpoints: ${message}` },
      { status: 500 }
    );
  }
}
