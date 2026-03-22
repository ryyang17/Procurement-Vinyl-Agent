import { NextRequest, NextResponse } from "next/server";
import { submitCheckpointDecision } from "../../_utils";

type RouteParams = {
  params: Promise<{ threadId: string }> | { threadId: string };
};

export async function POST(req: NextRequest, context: RouteParams) {
  try {
    const { threadId } = await context.params;
    const body = await req.json();

    const result = await submitCheckpointDecision(threadId, body);
    return NextResponse.json(result.data, { status: result.status });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      { error: `Failed to submit decision: ${message}` },
      { status: 500 }
    );
  }
}
