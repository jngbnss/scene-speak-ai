"""CTC forced alignment in numpy (same algorithm as torchaudio.functional.forced_align).

Given per-frame log probabilities from a CTC model and the known transcript, finds the
most likely frame-to-character path. No torch needed, so the aligner runs on the
onnxruntime that Kokoro already uses.
"""

import re
from dataclasses import dataclass

import numpy as np

NUMBER_WORDS = {
    "0": "zero",
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
    "10": "ten",
}


@dataclass
class WordSpan:
    word: str  # as written in the transcript
    start_frame: int
    end_frame: int  # exclusive
    score: float  # mean probability of the word's characters, 0..1


def spoken_form(word: str) -> str:
    """The letters a character-level English CTC model can emit for one written word."""
    w = word.lower().replace("’", "'")
    core = re.sub(r"[^a-z0-9']", "", w)
    if core in NUMBER_WORDS:
        return NUMBER_WORDS[core]
    return re.sub(r"[^a-z']", "", core).strip("'")


def log_softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max(axis=-1, keepdims=True)
    return shifted - np.log(np.exp(shifted).sum(axis=-1, keepdims=True))


def viterbi(log_probs: np.ndarray, tokens: list[int], blank: int = 0) -> list[int] | None:
    """Best CTC path. Returns, for each frame, the token index it belongs to (-1 = blank).

    None when the audio has too few frames for the transcript.
    """
    n_frames = log_probs.shape[0]
    labels = [blank]
    for t in tokens:
        labels += [t, blank]
    n_states = len(labels)
    labels_arr = np.array(labels)
    # A state may skip the blank before it when its label differs from two states back.
    can_skip = np.zeros(n_states, dtype=bool)
    for s in range(2, n_states):
        can_skip[s] = labels[s] != blank and labels[s] != labels[s - 2]
    repeats = sum(a == b for a, b in zip(tokens, tokens[1:], strict=False))
    if n_frames < len(tokens) + repeats:
        return None

    neg = -np.inf
    score = np.full(n_states, neg)
    score[0] = log_probs[0, labels[0]]
    if n_states > 1:
        score[1] = log_probs[0, labels[1]]
    back = np.zeros((n_frames, n_states), dtype=np.int8)  # 0 stay, 1 from s-1, 2 from s-2
    for t in range(1, n_frames):
        stay = score
        step = np.concatenate(([neg], score[:-1]))
        skip = np.where(can_skip, np.concatenate(([neg, neg], score[:-2])), neg)
        stacked = np.stack([stay, step, skip])
        choice = stacked.argmax(axis=0)
        score = stacked[choice, np.arange(n_states)] + log_probs[t, labels_arr]
        back[t] = choice

    # The path must end on the last label or the trailing blank.
    s = n_states - 1 if n_states == 1 or score[-1] >= score[-2] else n_states - 2
    if not np.isfinite(score[s]):
        return None
    path = [0] * n_frames
    for t in range(n_frames - 1, -1, -1):
        path[t] = (s - 1) // 2 if s % 2 == 1 else -1
        s -= int(back[t, s])
    return path


def align_words(
    log_probs: np.ndarray, words: list[str], vocab: dict[str, int], separator: str = "|"
) -> list[WordSpan]:
    """Aligns written words to frames. Words with no alignable letters get no span."""
    spoken = [spoken_form(w).upper() for w in words]
    tokens: list[int] = []
    owner: list[int] = []  # token index -> word index (-1 for separators)
    for i, letters in enumerate(spoken):
        if not letters:
            continue
        if tokens:
            tokens.append(vocab[separator])
            owner.append(-1)
        for ch in letters:
            tokens.append(vocab[ch])
            owner.append(i)
    if not tokens:
        return []
    path = viterbi(log_probs, tokens)
    if path is None:
        return []

    frames: dict[int, list[int]] = {}
    for t, token_index in enumerate(path):
        if token_index >= 0 and owner[token_index] >= 0:
            frames.setdefault(owner[token_index], []).append(t)
    spans = []
    for i, word_frames in sorted(frames.items()):
        probs = [float(np.exp(log_probs[t, tokens[path[t]]])) for t in word_frames]
        spans.append(
            WordSpan(
                word=words[i],
                start_frame=word_frames[0],
                end_frame=word_frames[-1] + 1,
                score=round(sum(probs) / len(probs), 3),
            )
        )
    return spans
