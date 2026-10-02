// Test helper ONLY (scripts/check-mocks.test.mjs). Not imported by the app and not used to write mocks.
// A port of the server-side yuan formatter (services/api/app/domain/money.py), used to turn the golden fen values into the
// strings the recorded mocks must carry.

export function fmtYuan(fen) {
  const sign = fen < 0 ? "−" : "";
  const abs = Math.abs(fen);
  const y = Math.floor(abs / 100);
  const f = abs % 100;
  return `${sign}¥${y.toLocaleString("en-US")}.${String(f).padStart(2, "0")}`;
}
