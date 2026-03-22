import { NextRequest, NextResponse } from "next/server";
import { fetchCheckpointState } from "../_utils";

type RouteParams = {
  params: Promise<{ threadId: string }> | { threadId: string };
};

export async function GET(_req: NextRequest, context: RouteParams) {
  try {
    const { threadId } = await context.params;

    const result = await fetchCheckpointState(threadId);
    return NextResponse.json(result.data, { status: result.status });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      { error: `Failed to fetch checkpoint state: ${message}` },
      { status: 500 }
    );
  }
}
