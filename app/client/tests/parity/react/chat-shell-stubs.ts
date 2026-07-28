import { vi } from "vitest";
import type { ChatMessage, EvidenceRow } from "@/features/chat-shell/types";
import type { AcceptedRef, ConversationSummary } from "@/features/chat-shell/api";

const chatShellMocks = vi.hoisted(() => {
  const SYNTHETIC_CONVERSATIONS: ConversationSummary[] = [
    {
      id: "conv_synth_a",
      title: "Valve maintenance notes",
      createdAt: "2026-07-28T11:00:00Z",
      updatedAt: "2026-07-28T12:00:00Z",
      version: 1,
    },
    {
      id: "conv_synth_b",
      title: "Synthetic domain query",
      createdAt: "2026-07-27T08:30:00Z",
      updatedAt: "2026-07-27T09:30:00Z",
      version: 1,
    },
  ];

  const SYNTHETIC_MESSAGES: ChatMessage[] = [
    {
      id: "msg_user_1",
      role: "user",
      turnId: "turn_synth_1",
      text: "Synthetic question about valves",
    },
    {
      id: "msg_asst_1",
      role: "assistant",
      turnId: "turn_synth_1",
      text: "Lorem ipsum grounded answer about valve inspection procedures.",
      blocks: [
        {
          kind: "text",
          id: "block_text_1",
          text: "Lorem ipsum grounded answer about valve inspection procedures.",
        },
      ],
      status: "completed",
      evidenceCount: 2,
    },
  ];

  const SYNTHETIC_EVIDENCE: EvidenceRow[] = [
    {
      id: "ev_synth_1",
      citationLabel: "1",
      sourceLabel: "Valve handbook",
      documentLabel: "Valve handbook",
      documentRef: "doc_synth_1",
      excerpt: "Inspect relief valves quarterly under normal operating pressure.",
      kind: "text",
      anchor: { pageNumber: 4, fallback: "page", region: null, sectionLabel: "Maintenance" },
    },
    {
      id: "ev_synth_2",
      citationLabel: "2",
      sourceLabel: "Operations guide",
      documentLabel: "Operations guide",
      documentRef: "doc_synth_2",
      excerpt: "Document synthetic test pressure before returning to service.",
      kind: "text",
      anchor: { pageNumber: 11, fallback: "page", region: null, sectionLabel: "Testing" },
    },
  ];

  const SYNTHETIC_ACCEPTED_REFS: AcceptedRef[] = [
    {
      id: "aref_synth_1",
      kind: "source",
      label: "Handbook excerpt",
      description: "Synthetic governed reference",
      order: 1,
    },
  ];

  function noopAsync() {
    return Promise.resolve();
  }

  function createChatShellStub(overrides: Record<string, unknown> = {}) {
    return {
      conversations: SYNTHETIC_CONVERSATIONS,
      conversation: { id: "conv_synth_a", title: "Valve maintenance notes" },
      domains: [
        { id: "dom_synth_1", displayName: "Plant manuals", queryEligible: true },
        { id: "dom_synth_2", displayName: "Legacy archive", queryEligible: false },
      ],
      messages: [] as ChatMessage[],
      turns: [],
      input: "",
      domainId: "",
      streaming: false,
      streamStage: null as string | null,
      streamTransportState: "connected" as const,
      loading: false,
      error: null as string | null,
      lastUserMessage: null as string | null,
      panelOpen: false,
      panelEvidence: [] as EvidenceRow[],
      panelAcceptedRefs: [] as AcceptedRef[],
      selectedTurnId: null as string | null,
      selectedEvidenceId: null as string | null,
      streamingTurnId: null as string | null,
      runningCancellableTurnId: null as string | null,
      selectedReplayableTurnId: null as string | null,
      replayingTurnId: null as string | null,
      submittedSnapshot: null,
      setPanelOpen: vi.fn(),
      selectTurn: vi.fn(),
      selectEvidence: vi.fn(),
      setDomainId: vi.fn(),
      updateInput: vi.fn(),
      loadConversation: vi.fn().mockImplementation(noopAsync),
      startConversation: vi.fn().mockImplementation(noopAsync),
      submit: vi.fn().mockImplementation(noopAsync),
      retryLast: vi.fn().mockImplementation(noopAsync),
      cancelTurn: vi.fn().mockImplementation(noopAsync),
      replayTurn: vi.fn().mockImplementation(noopAsync),
      clearError: vi.fn(),
      ...overrides,
    };
  }

  const mockChatShell = createChatShellStub();
  const resetChatShellStub = () => {
    const fresh = createChatShellStub();
    for (const key of Object.keys(mockChatShell)) {
      delete (mockChatShell as Record<string, unknown>)[key];
    }
    Object.assign(mockChatShell, fresh);
  };
  const applyChatShellStub = (overrides: Record<string, unknown> = {}) => {
    resetChatShellStub();
    Object.assign(mockChatShell, overrides);
    return mockChatShell;
  };

  return {
    mockChatShell,
    resetChatShellStub,
    applyChatShellStub,
    SYNTHETIC_CONVERSATIONS,
    SYNTHETIC_MESSAGES,
    SYNTHETIC_EVIDENCE,
    SYNTHETIC_ACCEPTED_REFS,
  };
});

export const mockChatShell = chatShellMocks.mockChatShell;
export const resetChatShellStub = chatShellMocks.resetChatShellStub;
export const applyChatShellStub = chatShellMocks.applyChatShellStub;
export const SYNTHETIC_CONVERSATIONS = chatShellMocks.SYNTHETIC_CONVERSATIONS;
export const SYNTHETIC_MESSAGES = chatShellMocks.SYNTHETIC_MESSAGES;
export const SYNTHETIC_EVIDENCE = chatShellMocks.SYNTHETIC_EVIDENCE;
export const SYNTHETIC_ACCEPTED_REFS = chatShellMocks.SYNTHETIC_ACCEPTED_REFS;
