let ctx: AudioContext | null = null;

function getContext() {
  if (typeof window === "undefined") return null;
  if (!ctx) ctx = new AudioContext();
  if (ctx.state === "suspended") void ctx.resume();
  return ctx;
}

export function playUiSound(kind: "card" | "trump" | "win" | "error") {
  const audio = getContext();
  if (!audio) return;
  const now = audio.currentTime;
  const gain = audio.createGain();
  const osc = audio.createOscillator();
  const frequencies = { card: 420, trump: 560, win: 720, error: 180 };
  osc.frequency.setValueAtTime(frequencies[kind], now);
  osc.type = kind === "error" ? "sawtooth" : "sine";
  gain.gain.setValueAtTime(0.0001, now);
  gain.gain.exponentialRampToValueAtTime(0.045, now + 0.012);
  gain.gain.exponentialRampToValueAtTime(0.0001, now + (kind === "win" ? 0.22 : 0.09));
  osc.connect(gain).connect(audio.destination);
  osc.start(now);
  osc.stop(now + (kind === "win" ? 0.24 : 0.11));
}
