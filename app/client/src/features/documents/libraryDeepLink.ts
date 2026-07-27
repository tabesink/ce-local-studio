/**
 * Inbound Library deep-link parse + return-to-chat helpers (P9-03).
 *
 * Outbound chat → Library hrefs stay in `features/chat-shell/documentsDeepLink.ts`.
 * Return-to-chat uses `/chat?conversation=&turn=&evidence=` per navigation contract.
 */

export type LibraryDeepLink = {
  document: string | null;
  evidence: string | null;
  page: number | null;
  conversation: string | null;
  turn: string | null;
};

function nonEmpty(value: string | null): string | null {
  if (value == null) return null;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function parsePositivePage(value: string | null): number | null {
  const raw = nonEmpty(value);
  if (!raw) return null;
  if (!/^\d+$/.test(raw)) return null;
  const page = Number.parseInt(raw, 10);
  return page > 0 ? page : null;
}

/**
 * Parses inbound Library query params.
 * Accepts legacy `conversationId`/`turnId` inbound for compatibility; canonical
 * return builders emit `conversation`/`turn`/`evidence`.
 */
export function parseLibraryDeepLink(
  searchParams: URLSearchParams | { get(name: string): string | null },
): LibraryDeepLink {
  return {
    document: nonEmpty(searchParams.get("document")),
    evidence: nonEmpty(searchParams.get("evidence")),
    page: parsePositivePage(searchParams.get("page")),
    conversation:
      nonEmpty(searchParams.get("conversation")) ?? nonEmpty(searchParams.get("conversationId")),
    turn: nonEmpty(searchParams.get("turn")) ?? nonEmpty(searchParams.get("turnId")),
  };
}

export function hasChatReturn(link: LibraryDeepLink): boolean {
  return Boolean(link.conversation && link.turn);
}

export function buildChatReturnHref(
  conversation: string,
  turn: string,
  evidence?: string | null,
): string {
  const params = new URLSearchParams({
    conversation,
    turn,
  });
  const evidenceRef = nonEmpty(evidence ?? null);
  if (evidenceRef) params.set("evidence", evidenceRef);
  return `/chat?${params.toString()}`;
}
