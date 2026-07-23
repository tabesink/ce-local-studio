/**
 * Safe return-to-chat query params.
 *
 * Phase 1 deliberately ignores raw domain/source/page Library deep-links until
 * governed opaque evidence-location and document-content routes are available.
 */
export type LibraryDeepLink = {
  conversationId: string | null;
  turnId: string | null;
};

function nonEmpty(value: string | null): string | null {
  if (value == null) return null;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

export function parseLibraryDeepLink(
  searchParams: URLSearchParams | { get(name: string): string | null },
): LibraryDeepLink {
  return {
    conversationId: nonEmpty(searchParams.get("conversationId")),
    turnId: nonEmpty(searchParams.get("turnId")),
  };
}

export function hasChatReturn(link: LibraryDeepLink): boolean {
  return Boolean(link.conversationId && link.turnId);
}

export function buildChatReturnHref(conversationId: string, turnId: string): string {
  const params = new URLSearchParams({
    conversationId,
    turnId,
  });
  return "/chat?" + params.toString();
}
