/**
 * The words the server asks the owner to reply with ("Reply "Yes, do it" to approve it." / "回复“好，执行”即可批准。"), read out of its own reply, so the
 * button says what the server said it would take: "Yes, run it" confirms a plan, "Yes, do it" approves what waits in the queue. Null when the
 * reply names none (the caller then keeps its dictionary word).
 */
export function confirmWord(reply: string): string | null {
  const m = /Reply\s+"([^"]+)"\s+to\b/.exec(reply) ?? /回复“([^”]+)”/.exec(reply);
  return m ? m[1] : null;
}
