import {
  CopilotRuntime,
  ExperimentalEmptyAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import { LangGraphAgent } from "@copilotkit/runtime/langgraph";
import { NextRequest } from "next/server";

const serviceAdapter = new ExperimentalEmptyAdapter();

const deploymentUrl = process.env.LANGGRAPH_DEPLOYMENT_URL || "http://127.0.0.1:2024";
const langsmithApiKey = process.env.LANGSMITH_API_KEY || "";

let agents = {};
if (deploymentUrl) {
  agents = {
    procurement_agent: new LangGraphAgent({
      deploymentUrl,
      graphId: "procurement_agent",
      ...(langsmithApiKey ? { langsmithApiKey } : {}),
    }),
  };
} else {
  // Optionally log or handle missing env vars
  agents = {};
}

const runtime = new CopilotRuntime({
  agents,
});

export const POST = async (req: NextRequest) => {
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter,
    endpoint: "/api/copilotkit",
  });

  return handleRequest(req);
};