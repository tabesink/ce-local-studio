import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

function MarkdownContent({ children }: { children: ReactNode }) {
  return <article className="markdown-content">{children}</article>;
}

function ExampleContent() {
  return (
    <MarkdownContent>
      <h2>Synthetic answer</h2>
      <p>This example demonstrates governed typography.</p>
      <table><thead><tr><th>Item</th><th>State</th></tr></thead><tbody><tr><td>Example</td><td>Ready</td></tr></tbody></table>
      <pre><code>example()</code></pre>
    </MarkdownContent>
  );
}

describe("MarkdownContent parity harness (R10)", () => {
  it("preserves heading and paragraph semantics", () => {
    render(<ExampleContent />);
    expect(screen.getByRole("heading", { level: 2, name: "Synthetic answer" })).toBeInTheDocument();
    expect(screen.getByText("This example demonstrates governed typography.")).toBeInTheDocument();
  });

  it("preserves semantic table and code content", () => {
    render(<ExampleContent />);
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "State" })).toBeInTheDocument();
    expect(screen.getByText("example()")).toHaveProperty("tagName", "CODE");
  });

  it("renders within the light theme region", () => {
    render(<div data-theme="zai-light"><ExampleContent /></div>);
    expect(screen.getByRole("article").closest("[data-theme]")).toHaveAttribute("data-theme", "zai-light");
  });
});
