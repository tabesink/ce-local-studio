import { proxyContextEngineRequest, resolveBffProxyConfig } from "@/lib/server/bff-proxy";

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: Request, context: RouteContext): Promise<Response> {
  try {
    const { path } = await context.params;
    return await proxyContextEngineRequest(request, path, resolveBffProxyConfig());
  } catch (error) {
    if (request.signal.aborted) throw error;
    return Response.json(
      {
        error: {
          code: "dependency_unavailable",
          message: "Service unavailable.",
          requestId: crypto.randomUUID(),
          fields: {},
        },
      },
      { status: 503, headers: { "Cache-Control": "private, no-store" } },
    );
  }
}

export const dynamic = "force-dynamic";
export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
