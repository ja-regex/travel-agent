"use client";

import { FormEvent, useMemo, useRef, useState } from "react";
import type { ChatMessage, StreamEvent, UsageEvent } from "@/lib/types";

type UsageTotals = {
  estimatedCostUsd: number;
  webFetches: number;
  searches: number;
};

const starter =
  "I have 10 days in Laos in November, like food, rivers, slow travel, and guesthouses under $45/night. Recommend places that are not too rushed.";

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState(starter);
  const [researchLog, setResearchLog] = useState<string[]>([]);
  const [usage, setUsage] = useState<UsageEvent[]>([]);
  const [totals, setTotals] = useState<UsageTotals | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const answer = useMemo(() => messages.filter((message) => message.role === "assistant").at(-1)?.content ?? "", [messages]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isRunning) return;

    const nextMessages: ChatMessage[] = [...messages, { role: "user", content: trimmed }, { role: "assistant", content: "" }];
    setMessages(nextMessages);
    setInput("");
    setResearchLog([]);
    setUsage([]);
    setTotals(null);
    setIsRunning(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ messages: nextMessages.slice(0, -1) }),
        signal: controller.signal
      });

      if (!response.ok || !response.body) {
        throw new Error(await response.text());
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.trim()) continue;
          const event = JSON.parse(line) as StreamEvent;

          if (event.type === "status") {
            setResearchLog((current) => [...current, event.message].slice(-10));
          }

          if (event.type === "token") {
            setMessages((current) => {
              const copy = [...current];
              const last = copy[copy.length - 1];
              copy[copy.length - 1] = { ...last, content: last.content + event.text };
              return copy;
            });
          }

          if (event.type === "usage") {
            setUsage(event.usage);
            setTotals(event.totals);
          }

          if (event.type === "error") {
            setResearchLog((current) => [...current, event.message]);
          }
        }
      }
    } catch (error) {
      if ((error as Error).name !== "AbortError") {
        setResearchLog((current) => [...current, (error as Error).message]);
      }
    } finally {
      setIsRunning(false);
      abortRef.current = null;
    }
  }

  function stop() {
    abortRef.current?.abort();
    setIsRunning(false);
  }

  return (
    <main className="shell">
      <section className="workspace" aria-label="Travel companion chat">
        <header className="topbar">
          <div className="brandLockup">
            <span className="brandMark" aria-hidden="true">
              TC
            </span>
            <div>
              <p className="eyebrow">Travel Companion</p>
              <h1>Go farther.<br />Travel slower.</h1>
            </div>
          </div>
          <div className="budgetPill">
            <span>${totals ? totals.estimatedCostUsd.toFixed(3) : "0.000"}</span>
            <small>research cost</small>
          </div>
        </header>

        <div className="chatPanel">
          {messages.length === 0 ? (
            <div className="emptyState">
              <p className="sectionNumber">01 / Imagine</p>
              <h2>What kind of journey are you craving?</h2>
              <p>Share your dates, rhythm, budget, and curiosities. Your companion will research the details and shape them into a trip with room to breathe.</p>
              <div className="promptNotes" aria-label="Planning suggestions">
                <span>Place</span>
                <span>Pace</span>
                <span>Budget</span>
                <span>Curiosity</span>
              </div>
            </div>
          ) : (
            messages.map((message, index) => (
              <article className={`bubble ${message.role}`} key={`${message.role}-${index}`}>
                <div className="role">{message.role === "user" ? "You" : "Agent"}</div>
                <div className="content">{message.content || (isRunning ? "Thinking..." : "")}</div>
              </article>
            ))
          )}
        </div>

        <form className="composer" onSubmit={submit}>
          <label className="composerLabel" htmlFor="trip-description">
            Start with a rough idea
          </label>
          <textarea
            id="trip-description"
            aria-label="Trip description"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Tell me dates, budget, pace, interests, constraints, and where you are considering."
            rows={4}
          />
          <div className="composerActions">
            <button className="secondary" disabled={!isRunning} onClick={stop} type="button">
              Stop
            </button>
            <button disabled={isRunning || !input.trim()} type="submit">
              {isRunning ? "Researching" : answer ? "Ask follow-up" : "Plan research"}
            </button>
          </div>
        </form>
      </section>

      <aside className="sidePanel" aria-label="Research progress">
        <div className="panelHeader">
          <div>
            <p className="sectionNumber">02 / Field notes</p>
            <h2>Research trail</h2>
          </div>
          <span className={isRunning ? "statusLive" : ""}>{isRunning ? "Live" : "Ready"}</span>
        </div>
        <ol className="logList">
          {researchLog.length === 0 ? (
            <li>Your sources, searches, and research decisions will gather here.</li>
          ) : (
            researchLog.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)
          )}
        </ol>

        <p className="usageLabel">Journey footprint</p>
        <div className="usageGrid">
          <div>
            <strong>{totals?.searches ?? 0}</strong>
            <span>searches</span>
          </div>
          <div>
            <strong>{totals?.webFetches ?? 0}</strong>
            <span>fetches</span>
          </div>
          <div>
            <strong>{usage.reduce((sum, item) => sum + (item.totalTokens ?? item.estimatedTokens ?? 0), 0).toLocaleString()}</strong>
            <span>tokens</span>
          </div>
        </div>
      </aside>
    </main>
  );
}
