import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const apiBase = (process.env.CONTEXT_ENGINE_API_BASE ?? "http://127.0.0.1:8000").replace(/\/+$/, "");
  return NextResponse.rewrite(new URL(`${request.nextUrl.pathname}${request.nextUrl.search}`, apiBase));
}

export const config = {
  matcher: ["/health/:path*"],
};
