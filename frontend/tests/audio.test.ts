import { describe, expect, it } from "vitest";

import { base64ToBlob, float32ToPcm16Base64 } from "../src/services/audio";

function decode(b64: string): Int16Array {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Int16Array(bytes.buffer);
}

describe("float32ToPcm16Base64", () => {
  it("encodes little-endian 16-bit PCM and clips out-of-range samples", () => {
    const pcm = decode(float32ToPcm16Base64(new Float32Array([0, 1, -1, 0.5, 2, -2])));
    expect(Array.from(pcm)).toEqual([0, 32767, -32768, 16383, 32767, -32768]);
  });

  it("handles long utterances without overflowing the call stack", () => {
    const samples = new Float32Array(16000 * 15); // 15 s at 16 kHz
    expect(decode(float32ToPcm16Base64(samples)).length).toBe(samples.length);
  });
});

describe("base64ToBlob", () => {
  it("restores the bytes", async () => {
    const blob = base64ToBlob(btoa("RIFF"), "audio/wav");
    expect(blob.type).toBe("audio/wav");
    expect(await blob.text()).toBe("RIFF");
  });
});
