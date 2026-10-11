/** Float32 samples in [-1, 1] -> 16-bit little-endian PCM, base64 (what the server expects). */
export function float32ToPcm16Base64(samples: Float32Array): string {
  const bytes = new Uint8Array(samples.length * 2);
  const view = new DataView(bytes.buffer);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

export function base64ToBlob(data: string, type: string): Blob {
  const binary = atob(data);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return new Blob([bytes], { type });
}

/** Plays NPC lines one after another and reports when it is speaking. */
export class NpcVoice {
  private queue: string[] = [];
  private current: HTMLAudioElement | null = null;
  muted = false;

  constructor(private readonly onSpeaking: (speaking: boolean) => void) {}

  enqueue(wavBase64: string): void {
    if (this.muted) return;
    this.queue.push(URL.createObjectURL(base64ToBlob(wavBase64, "audio/wav")));
    if (!this.current) this.playNext();
  }

  stop(): void {
    this.queue.forEach((url) => URL.revokeObjectURL(url));
    this.queue = [];
    if (this.current) {
      this.current.pause();
      this.current = null;
    }
    this.onSpeaking(false);
  }

  private playNext(): void {
    const url = this.queue.shift();
    if (!url) {
      this.current = null;
      this.onSpeaking(false);
      return;
    }
    const audio = new Audio(url);
    this.current = audio;
    this.onSpeaking(true);
    const done = () => {
      URL.revokeObjectURL(url);
      if (this.current === audio) this.playNext();
    };
    audio.onended = done;
    audio.onerror = done;
    audio.play().catch(done); // autoplay refused: skip, the text is on screen anyway
  }
}

/**
 * Plays seconds [start, end) of a recording. Returns a function that stops it early.
 * `onDone(false)` means the file could not be loaded (e.g. deleted after the retention period).
 */
export function playClip(
  url: string,
  start: number,
  end: number,
  onDone: (loaded: boolean) => void,
): () => void {
  const audio = new Audio(url);
  let timer: ReturnType<typeof setTimeout> | undefined;
  let finished = false;
  const finish = (loaded = true) => {
    if (finished) return;
    finished = true;
    clearTimeout(timer);
    audio.pause();
    onDone(loaded);
  };
  audio.onloadedmetadata = () => {
    audio.currentTime = start;
    audio
      .play()
      .then(() => {
        timer = setTimeout(() => finish(), Math.max(0, end - start) * 1000);
      })
      .catch(() => finish());
  };
  audio.ontimeupdate = () => audio.currentTime >= end && finish();
  audio.onended = () => finish();
  audio.onerror = () => finish(false);
  return () => finish();
}
