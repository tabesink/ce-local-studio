"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  ArrowUp,
  AtSign,
  ChevronDown,
  History,
  PanelRightClose,
  PanelRightOpen,
  Pencil,
  Plus,
  RotateCcw,
  Square,
  Trash2,
  X,
} from "lucide-react";
import { cx } from "@/lib/cx";
import { StatusPill } from "@/ui";
import { UiModal, UiModalHeader, SettingsButton } from "@/_shared/ui";
import { EvidencePanel } from "@/features/chat-shell/EvidencePanel";
import { useChatShell } from "@/features/chat-shell/use-chat-shell";
import type { AssistantBlock, ChatMessage } from "@/features/chat-shell/types";

/* LS chat-shell layout over CE conversations: pane header, block timeline,
   composer with domain selector and source/template composer refs (Evidence attach deferred),
   safe status bar, and the turn-scoped Evidence/Refs/Source inspector. */
export function ChatShell() {
  return (
    <Suspense
      fallback={
        <div className="flex h-full min-h-0 items-center justify-center bg-[var(--agent-bg)] text-[var(--dim)]">
          Loading conversation.
        </div>
      }
    >
      <ChatShellInner />
    </Suspense>
  );
}

function ChatShellInner() {
  const chat = useChatShell();
  const searchParams = useSearchParams();
  const timelineRef = useRef<HTMLDivElement>(null);
  const returnRestoredRef = useRef(false);

  useEffect(() => {
    const node = timelineRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [chat.messages.length, chat.streaming]);

  /* Back to chat / citation return: restore conversation + jump-from turn once.
     Canonical query keys are conversation/turn/evidence; accept legacy conversationId/turnId. */
  useEffect(() => {
    if (returnRestoredRef.current) return;
    const conversationId =
      searchParams.get("conversation")?.trim() ||
      searchParams.get("conversationId")?.trim() ||
      null;
    const turnId =
      searchParams.get("turn")?.trim() || searchParams.get("turnId")?.trim() || null;
    const evidenceId = searchParams.get("evidence")?.trim() || null;
    if (!conversationId || !turnId) return;
    returnRestoredRef.current = true;
    void chat.loadConversation(conversationId, { turnId, evidenceId });
  }, [chat.loadConversation, searchParams]);

  return (
    <div className="flex h-full min-h-0 bg-[var(--agent-bg)] text-[var(--ui-fg)]">
      <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col">
      {/* Pane header */}
      <header className="flex h-10 shrink-0 items-center justify-between gap-3 border-b border-[var(--border)]/35 px-4">
        <div className="flex min-w-0 items-center gap-2">
          <ConversationTitle chat={chat} />
          <span role="status" aria-live="polite">
            {chat.streamTransportState === "reconnecting" ? (
              <StatusPill tone="info">Reconnecting</StatusPill>
            ) : chat.streamTransportState === "offline" ? (
              <StatusPill tone="danger">Offline</StatusPill>
            ) : chat.streaming && chat.streamStage ? (
              <StatusPill tone="info">{chat.streamStage}</StatusPill>
            ) : null}
          </span>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <ConversationPicker chat={chat} />
          <button
            type="button"
            onClick={() => void chat.startConversation()}
            title="New conversation"
            aria-label="New conversation"
            className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--dim)] transition-colors hover:bg-[var(--hover)] hover:text-[var(--fg)]"
          >
            <Plus className="h-4 w-4" />
          </button>
          {chat.runningCancellableTurnId ? (
            <button
              type="button"
              onClick={() => void chat.cancelTurn()}
              title="Cancel running answer"
              aria-label="Cancel running answer"
              className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--dim)] transition-colors hover:bg-[var(--hover)] hover:text-[var(--fg)]"
            >
              <Square className="h-4 w-4" />
            </button>
          ) : null}
          {chat.selectedReplayableTurnId ? (
            <button
              type="button"
              onClick={() => void chat.replayTurn()}
              disabled={chat.streaming || chat.replayingTurnId !== null}
              title={chat.replayingTurnId === chat.selectedReplayableTurnId ? "Replaying turn" : "Replay selected turn"}
              aria-label="Replay selected turn"
              className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--dim)] transition-colors hover:bg-[var(--hover)] hover:text-[var(--fg)] disabled:cursor-not-allowed disabled:opacity-40"
            >
              <RotateCcw className={cx("h-4 w-4", chat.replayingTurnId === chat.selectedReplayableTurnId ? "animate-spin" : "")} />
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => chat.setPanelOpen(!chat.panelOpen)}
            title={chat.panelOpen ? "Close evidence panel" : "Open evidence panel"}
            aria-label={chat.panelOpen ? "Close evidence panel" : "Open evidence panel"}
            aria-expanded={chat.panelOpen}
            className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--dim)] transition-colors hover:bg-[var(--hover)] hover:text-[var(--fg)]"
          >
            {chat.panelOpen ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
          </button>
        </div>
      </header>

      {/* Error banner with Retry */}
      {chat.error ? (
        <div
          className="flex items-center gap-3 border-b border-[var(--err)]/30 bg-[var(--err)]/10 px-4 py-2 text-[length:var(--fs-sm)] text-[var(--err)]"
          role="alert"
        >
          <span className="min-w-0 flex-1 truncate">{chat.error}</span>
          {chat.lastUserMessage ? (
            <button
              type="button"
              onClick={() => void chat.retryLast()}
              className="shrink-0 rounded-md px-2 py-1 font-medium transition-colors hover:bg-[var(--err)]/15"
            >
              Retry
            </button>
          ) : null}
          <button
            type="button"
            onClick={chat.clearError}
            aria-label="Dismiss error"
            className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md transition-colors hover:bg-[var(--err)]/15"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ) : null}

      {/* Timeline */}
      <div ref={timelineRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6">
        {chat.messages.length === 0 ? (
          <div className="flex h-full items-center justify-center text-[var(--dim)]">
            {chat.loading ? "Loading conversation." : "Ask Context Engine to start."}
          </div>
        ) : (
          <div className="mx-auto flex w-full max-w-[var(--thread-w)] flex-col gap-5">
            {chat.messages.map((message) => (
              <TimelineMessage
                key={message.id}
                message={message}
                streaming={chat.streaming}
                selected={message.turnId !== null && message.turnId === chat.selectedTurnId}
                onSelectTurn={chat.selectTurn}
              />
            ))}
          </div>
        )}
      </div>

      {/* Composer */}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void chat.submit();
        }}
        className="shrink-0 bg-[var(--agent-bg)] px-4 pb-2 pt-2.5 sm:px-6"
      >
        <div className="relative mx-auto w-full max-w-[var(--composer-w)] rounded-[var(--composer-radius)] border border-[var(--border)]/60 bg-[var(--composer)] shadow-[var(--composer-shadow)]">
          {chat.composerRefs.length > 0 ? (
            <div className="flex flex-wrap gap-1.5 px-3 pt-3" data-testid="composer-ref-chips">
              {chat.composerRefs.map((ref) => (
                <span
                  key={ref.token}
                  className="inline-flex max-w-full items-center gap-1 rounded-md border border-[var(--border)]/50 bg-[var(--hover)]/40 px-2 py-0.5 text-[length:var(--fs-xs)] text-[var(--fg)]"
                >
                  <span className="truncate font-mono uppercase text-[var(--dim)]">{ref.kind}</span>
                  <span className="truncate">{ref.label}</span>
                  <button
                    type="button"
                    aria-label={`Remove ${ref.label}`}
                    onClick={() => chat.removeComposerRef(ref.token)}
                    className="rounded p-0.5 text-[var(--dim)] hover:bg-[var(--hover)] hover:text-[var(--fg)]"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
            </div>
          ) : null}
          <textarea
            value={chat.input}
            onChange={(event) => chat.updateInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void chat.submit();
              }
            }}
            placeholder="Ask anything — choose a domain for grounded answers"
            className="min-h-24 w-full resize-none bg-transparent px-4 py-3 text-[length:var(--fs-base)] leading-6 text-[var(--fg)] outline-none placeholder:text-[var(--dim)]/60"
          />
          <div className="flex items-center justify-between px-2.5 pb-2.5">
            <div className="flex items-center gap-1">
              <RefPicker chat={chat} />
              <DomainPicker chat={chat} />
            </div>
            <button
              type="submit"
              disabled={chat.streaming || !chat.input.trim()}
              title="Send message"
              aria-label="Send message"
              data-testid="composer-send"
              className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--fg)]/90 text-[var(--bg)] transition-colors hover:bg-[var(--fg)] disabled:opacity-30"
            >
              <ArrowUp className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Status bar — safe metadata only */}
        <div className="mx-auto mt-1 flex w-full max-w-[var(--composer-w)] items-center justify-between gap-3 px-1 font-mono text-[length:var(--fs-xs)] text-[var(--dim)]/80">
          <span className="truncate">
            {chat.domainId
              ? `domain: ${chat.domains.find((d) => d.id === chat.domainId)?.displayName ?? "selected"}`
              : "direct chat"}
          </span>
          <span className="flex shrink-0 items-center gap-3">
            <span
              data-testid="chat-streaming"
              data-streaming={chat.streaming ? "true" : "false"}
              data-transport-state={chat.streamTransportState}
            >
              {chat.streamTransportState === "connected"
                ? chat.streaming ? "streaming" : ""
                : chat.streamTransportState}
            </span>
          </span>
        </div>
      </form>
      </div>

      {/* Turn-scoped inspector — fed by turn SSE/history only */}
      <EvidencePanel
        open={chat.panelOpen}
        rows={chat.panelEvidence}
        acceptedRefs={chat.panelAcceptedRefs}
        selectedEvidenceId={chat.selectedEvidenceId}
        onSelectEvidence={chat.selectEvidence}
        onClose={() => chat.setPanelOpen(false)}
        conversationId={chat.conversation?.id ?? null}
        turnId={chat.selectedTurnId}
      />
    </div>
  );
}

type ChatState = ReturnType<typeof useChatShell>;

function ConversationTitle({ chat }: { chat: ChatState }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(chat.conversation?.title ?? "");
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    if (!editing) setDraft(chat.conversation?.title ?? "");
  }, [chat.conversation?.id, chat.conversation?.title, editing]);

  if (!chat.conversation) {
    return (
      <span className="truncate text-[length:var(--fs-base)] font-medium text-[var(--fg)]">New conversation</span>
    );
  }

  return (
    <>
      {editing ? (
        <form
          className="flex min-w-0 items-center gap-1"
          onSubmit={(event) => {
            event.preventDefault();
            void chat.renameActiveConversation(draft).then(() => setEditing(false));
          }}
        >
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                event.preventDefault();
                setEditing(false);
                setDraft(chat.conversation?.title ?? "");
              }
            }}
            aria-label="Conversation title"
            data-testid="conversation-title-input"
            className="h-7 min-w-0 max-w-[14rem] rounded-md border border-[var(--border)] bg-transparent px-2 text-[length:var(--fs-base)] text-[var(--fg)] outline-none"
            autoFocus
          />
          <button type="submit" className="rounded-md px-2 text-[length:var(--fs-sm)] text-[var(--fg)] hover:bg-[var(--hover)]">
            Save
          </button>
          <button
            type="button"
            onClick={() => {
              setEditing(false);
              setDraft(chat.conversation?.title ?? "");
            }}
            className="rounded-md px-2 text-[length:var(--fs-sm)] text-[var(--dim)] hover:bg-[var(--hover)]"
          >
            Cancel
          </button>
        </form>
      ) : (
        <div className="flex min-w-0 items-center gap-1">
          <span className="truncate text-[length:var(--fs-base)] font-medium text-[var(--fg)]">
            {chat.conversation.title ?? "Untitled"}
          </span>
          <button
            type="button"
            title="Rename conversation"
            aria-label="Rename conversation"
            data-testid="conversation-rename"
            onClick={() => setEditing(true)}
            className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--dim)] hover:bg-[var(--hover)] hover:text-[var(--fg)]"
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            title="Delete conversation"
            aria-label="Delete conversation"
            data-testid="conversation-delete"
            onClick={() => setConfirmDelete(true)}
            className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--dim)] hover:bg-[var(--hover)] hover:text-[var(--fg)]"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
      <UiModal isOpen={confirmDelete} onClose={() => setConfirmDelete(false)} maxWidth="max-w-md">
        <UiModalHeader title="Delete conversation" onClose={() => setConfirmDelete(false)} />
        <div className="space-y-4 px-6 py-4">
          <p className="text-[length:var(--fs-base)] text-[var(--fg)]">
            Delete &ldquo;{chat.conversation.title ?? "Untitled"}&rdquo;? This cannot be undone.
          </p>
          <div className="flex justify-end gap-2">
            <SettingsButton onClick={() => setConfirmDelete(false)}>Cancel</SettingsButton>
            <SettingsButton
              tone="danger"
              onClick={() => {
                setConfirmDelete(false);
                void chat.deleteActiveConversation();
              }}
            >
              Delete
            </SettingsButton>
          </div>
        </div>
      </UiModal>
    </>
  );
}

function ConversationPicker({ chat }: { chat: ChatState }) {
  return (
    <div className="group relative">
      <button
        type="button"
        title="Conversations"
        aria-label="Conversations"
        className="flex h-7 items-center gap-1 rounded-md px-2 text-[length:var(--fs-sm)] text-[var(--dim)] transition-colors hover:bg-[var(--hover)] hover:text-[var(--fg)]"
      >
        <History className="h-3.5 w-3.5" />
        <ChevronDown className="h-3 w-3" />
      </button>
      <div className="absolute right-0 top-8 z-50 hidden w-64 rounded-lg border border-[var(--border)] bg-[var(--color-popover)] py-1 shadow-[var(--composer-shadow)] group-focus-within:block group-hover:block">
        {chat.conversations.length === 0 ? (
          <div className="px-3 py-1.5 text-[length:var(--fs-sm)] text-[var(--dim)]">No conversations yet.</div>
        ) : (
          chat.conversations.slice(0, 12).map((row) => (
            <button
              key={row.id}
              type="button"
              onClick={() => void chat.loadConversation(row.id)}
              className={cx(
                "flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left text-[length:var(--fs-sm)] transition-colors hover:bg-[var(--hover)]",
                row.id === chat.conversation?.id ? "text-[var(--fg)]" : "text-[var(--dim)]",
              )}
            >
              <span className="truncate">{row.title ?? "Untitled"}</span>
              {row.id === chat.conversation?.id ? (
                <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--ok)]" />
              ) : null}
            </button>
          ))
        )}
      </div>
    </div>
  );
}

function RefPicker({ chat }: { chat: ChatState }) {
  return (
    <div className="relative">
      <button
        type="button"
        data-testid="ref-picker"
        aria-label="Attach source or template reference"
        title="Attach source or template reference"
        aria-expanded={chat.refPickerOpen}
        disabled={chat.streaming}
        onClick={() => {
          if (chat.refPickerOpen) chat.closeRefPicker();
          else void chat.openRefPicker();
        }}
        className="flex h-8 w-8 items-center justify-center rounded-md text-[var(--dim)] transition-colors hover:bg-[var(--hover)] hover:text-[var(--fg)] disabled:cursor-not-allowed disabled:opacity-40"
      >
        <AtSign className="h-4 w-4" />
      </button>
      {chat.refPickerOpen ? (
        <div
          className="absolute bottom-10 left-0 z-50 w-72 rounded-lg border border-[var(--border)] bg-[var(--color-popover)] p-2 shadow-[var(--composer-shadow)]"
          role="dialog"
          aria-label="Reference picker"
        >
          <input
            value={chat.refPickerQuery}
            onChange={(event) => chat.setRefPickerQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                event.preventDefault();
                chat.closeRefPicker();
              }
              if (event.key === "Enter") {
                event.preventDefault();
                void chat.openRefPicker();
              }
            }}
            placeholder="Search sources and templates"
            aria-label="Search sources and templates"
            className="mb-2 h-8 w-full rounded-md border border-[var(--border)] bg-transparent px-2 text-[length:var(--fs-sm)] text-[var(--fg)] outline-none"
          />
          {chat.refPickerState === "loading" ? (
            <p className="px-1 py-1 text-[length:var(--fs-sm)] text-[var(--dim)]">Loading references…</p>
          ) : null}
          {chat.refPickerState === "empty" ? (
            <p className="px-1 py-1 text-[length:var(--fs-sm)] text-[var(--dim)]">No matching references.</p>
          ) : null}
          {chat.refPickerState === "error" ? (
            <p className="px-1 py-1 text-[length:var(--fs-sm)] text-[var(--err)]" role="alert">
              {chat.refPickerError ?? "References unavailable."}
            </p>
          ) : null}
          {chat.refPickerState === "ready" ? (
            <ul className="max-h-48 space-y-1 overflow-y-auto">
              {chat.refPickerResults.map((ref) => (
                <li key={ref.token}>
                  <button
                    type="button"
                    onClick={() => chat.attachComposerRef(ref)}
                    className="flex w-full flex-col rounded-md px-2 py-1.5 text-left hover:bg-[var(--hover)]"
                  >
                    <span className="font-mono text-[length:var(--fs-xs)] uppercase text-[var(--dim)]">{ref.kind}</span>
                    <span className="truncate text-[length:var(--fs-sm)] text-[var(--fg)]">{ref.label}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function DomainPicker({ chat }: { chat: ChatState }) {
  return (
    <label className="flex items-center gap-1.5 text-[length:var(--fs-sm)] text-[var(--dim)]">
      <select
        value={chat.domainId}
        onChange={(event) => chat.setDomainId(event.target.value)}
        aria-label="Knowledge Domain"
        data-testid="domain-selector"
        className="h-8 max-w-44 rounded-md border border-transparent bg-transparent px-2 text-[length:var(--fs-sm)] text-[var(--dim)] outline-none transition-colors hover:bg-[var(--hover)] hover:text-[var(--fg)] focus:border-[var(--ui-border)]"
      >
        <option value="">Direct chat</option>
        {chat.domains.map((domain) => (
          <option key={domain.id} value={domain.id} disabled={!domain.queryEligible}>
            {domain.displayName}
          </option>
        ))}
      </select>
    </label>
  );
}

function TimelineMessage({
  message,
  streaming,
  selected,
  onSelectTurn,
}: {
  message: ChatMessage;
  streaming: boolean;
  selected: boolean;
  onSelectTurn: (turnId: string | null) => void;
}) {
  if (message.role === "user") {
    return (
      <div className="ml-auto flex max-w-[80%] flex-col items-end gap-1">
        {message.acceptedRefs && message.acceptedRefs.length > 0 ? (
          <div className="flex flex-wrap justify-end gap-1">
            {message.acceptedRefs.map((ref) => (
              <span
                key={ref.id}
                className="inline-flex items-center gap-1 rounded-md bg-[var(--surface)] px-1.5 py-0.5 font-mono text-[length:var(--fs-2xs)] text-[var(--dim)]"
                title={ref.description ?? undefined}
              >
                <AtSign className="h-2.5 w-2.5" />
                {ref.label ?? ref.kind}
              </span>
            ))}
          </div>
        ) : null}
        <div className="rounded-2xl bg-[var(--surface)] px-4 py-2.5">
          <div className="whitespace-pre-wrap text-[length:var(--fs-base)] leading-6 text-[var(--fg)]">
            {message.text}
          </div>
        </div>
      </div>
    );
  }

  /* Clicking a persisted assistant message binds the Evidence Panel to that
     turn. The in-flight assistant (turnId null) already drives the panel. */
  const blocks = message.blocks ?? [];
  const selectable = message.turnId !== null;
  const body = (
    <>
      {blocks.length === 0 && message.status === "running" && streaming ? (
        <div className="text-[length:var(--fs-sm)] text-[var(--dim)]">Streaming...</div>
      ) : null}
      {blocks.map((block) => (
        <TimelineBlock key={block.id} block={block} />
      ))}
      {typeof message.evidenceCount === "number" && message.evidenceCount > 0 ? (
        <div className="font-mono text-[length:var(--fs-2xs)] uppercase tracking-[0.12em] text-[var(--dim)]/60">
          {message.evidenceCount} evidence
        </div>
      ) : null}
      {message.status === "redacted" ? (
        <div className="text-[length:var(--fs-sm)] italic text-[var(--dim)]">This turn was redacted.</div>
      ) : null}
      {message.status === "cancelled" ? (
        <div className="text-[length:var(--fs-sm)] italic text-[var(--dim)]">This turn was cancelled.</div>
      ) : null}
    </>
  );

  if (!selectable) {
    return (
      <div data-testid="assistant-turn" className="mr-auto w-full max-w-[92%] space-y-2.5">
        {body}
      </div>
    );
  }

  return (
    <div
      role="button"
      tabIndex={0}
      data-testid="assistant-turn"
      onClick={() => onSelectTurn(message.turnId)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelectTurn(message.turnId);
        }
      }}
      title="Show this answer's evidence"
      className={cx(
        "mr-auto w-full max-w-[92%] cursor-pointer space-y-2.5 rounded-md border-l-2 py-1 pl-3 transition-colors",
        selected ? "border-[var(--link)]/70 bg-[var(--hover)]/50" : "border-transparent hover:border-[var(--border)]",
      )}
    >
      {body}
    </div>
  );
}

function TimelineBlock({ block }: { block: AssistantBlock }) {
  switch (block.kind) {
    case "event":
      return (
        <div className="font-mono text-[length:var(--fs-xs)] uppercase tracking-[0.12em] text-[var(--dim)]/70">
          {block.text}
        </div>
      );
    case "error":
      return (
        <div className="rounded-md border border-[var(--err)]/30 bg-[var(--err)]/10 px-3 py-2 text-[length:var(--fs-sm)] text-[var(--err)]">
          {block.text}
        </div>
      );
    default:
      return (
        <div className="whitespace-pre-wrap text-[length:var(--fs-base)] leading-7 text-[var(--fg)]">{block.text}</div>
      );
  }
}
