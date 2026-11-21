import { describe, expect, it } from "vitest";
import { createSseParser, type AgentEvent } from "./agentStream";

describe("createSseParser", () => {
  it("reassembles events split across arbitrary chunks", () => {
    const events: AgentEvent[] = [];
    const parser = createSseParser((e) => events.push(e));
    const wire =
      'data: {"type":"step","step":1,"total":5,"status":"running"}\n\n' +
      'data: {"type":"token","text":"Ha, 21 kun [1]"}\n\n' +
      'data: {"type":"done","response":{"answer":"Ha, 21 kun [1]","mode":"extractive"}}\n\n';
    for (let i = 0; i < wire.length; i += 7) parser.push(wire.slice(i, i + 7));
    parser.flush();
    expect(events.map((e) => e.type)).toEqual(["step", "token", "done"]);
    expect(events[1]).toEqual({ type: "token", text: "Ha, 21 kun [1]" });
  });

  it("handles CRLF line endings, skips malformed events and flushes a trailing event", () => {
    const events: AgentEvent[] = [];
    const parser = createSseParser((e) => events.push(e));
    parser.push('data: {"type":"token","text":"a"}\r\n\r\ndata: {broken\r\n\r\n: comment\r\n\r\n');
    parser.push('data: {"type":"error","code":"agent_unavailable"}');
    parser.flush();
    expect(events).toEqual([
      { type: "token", text: "a" },
      { type: "error", code: "agent_unavailable" },
    ]);
  });
});
