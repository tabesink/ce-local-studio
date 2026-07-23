import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const apiBase = (process.env.CONTEXT_ENGINE_API_BASE ?? "http://127.0.0.1:8000").replace(/\/+$/, "");
  const destination = new URL(`${request.nextUrl.pathname}${request.nextUrl.search}`, apiBase);
  return NextResponse.rewrite(destination);
}

export const config = {
  matcher: ["/api/v1/:path*", "/health/:path*"],
};
