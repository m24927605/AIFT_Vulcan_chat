import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ChatInput } from "@/components/ChatInput";

describe("ChatInput", () => {
  it("renders input and send button", () => {
    render(<ChatInput onSend={vi.fn()} />);
    expect(screen.getByPlaceholderText("Ask anything...")).toBeDefined();
    expect(screen.getByText("Send")).toBeDefined();
  });

  it("calls onSend when button clicked with text", () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);

    const textarea = screen.getByPlaceholderText("Ask anything...");
    fireEvent.change(textarea, { target: { value: "Hello" } });
    fireEvent.click(screen.getByText("Send"));

    expect(onSend).toHaveBeenCalledWith("Hello");
  });

  it("does not send empty messages", () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);

    fireEvent.click(screen.getByText("Send"));
    expect(onSend).not.toHaveBeenCalled();
  });

  it("disables input when disabled prop is true", () => {
    render(<ChatInput onSend={vi.fn()} disabled />);
    const textarea = screen.getByPlaceholderText("Ask anything...");
    expect(textarea).toHaveProperty("disabled", true);
  });
});
