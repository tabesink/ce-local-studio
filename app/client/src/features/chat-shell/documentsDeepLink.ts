/**
 * Outbound chat → Library deep-link builder (P9-02).
 *
 * Builds opaque `/documents?document=&evidence=&page=` hrefs from approved
 * EvidenceItem public fields only. Does not overload return-to-chat
 * `features/documents/libraryDeepLink.ts`.
 */

export type DocumentsDeepLinkFields = {
  documentRef?: string | null;
  evidenceRef?: string | null;
  page?: number | null;
  /** Opaque conversation ref for return-to-chat when history Back is unavailable. */
  conversation?: string | null;
  /** Opaque turn ref for return-to-chat when history Back is unavailable. */
  turn?: string | null;
};

/** Library preview surface enabled after P9-03 member content/location path. */
export const LIBRARY_SURFACE_AVAILABLE = true;

function nonEmpty(value: string | null | undefined): string | null {
  if (value == null) return null;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

/**
 * Returns an opaque Library href, or null when required refs are missing.
 * Never embeds paths, object URLs, raw block IDs, or excerpts.
 */
export function buildDocumentsDeepLinkHref(fields: DocumentsDeepLinkFields): string | null {
  const document = nonEmpty(fields.documentRef);
  const evidence = nonEmpty(fields.evidenceRef);
  if (!document || !evidence) return null;

  const params = new URLSearchParams({
    document,
    evidence,
  });

  if (typeof fields.page === "number" && Number.isFinite(fields.page) && fields.page > 0) {
    params.set("page", String(Math.trunc(fields.page)));
  }

  const conversation = nonEmpty(fields.conversation);
  const turn = nonEmpty(fields.turn);
  if (conversation && turn) {
    params.set("conversation", conversation);
    params.set("turn", turn);
  }

  return `/documents?${params.toString()}`;
}

export function isOpenInLibraryEnabled(
  href: string | null,
  libraryAvailable: boolean = LIBRARY_SURFACE_AVAILABLE,
): boolean {
  return Boolean(href) && libraryAvailable;
}
