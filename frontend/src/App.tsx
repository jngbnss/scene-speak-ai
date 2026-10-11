import { useCallback, useEffect, useState, type FormEvent } from "react";

import { ConversationScreen } from "./features/conversation/ConversationScreen";
import { ReviewView } from "./features/feedback/ReviewView";
import { ReportView } from "./features/report/ReportView";
import { NPCS, type NpcDef } from "./features/world/map";
import { WorldView } from "./features/world/WorldView";
import { login } from "./services/api";

const NICKNAME_KEY = "scenespeak.nickname";
const clearedKey = (nickname: string) => `scenespeak.cleared.${nickname}`;

function loadNickname(): string {
  try {
    return localStorage.getItem(NICKNAME_KEY) ?? "";
  } catch {
    return "";
  }
}

function loadCleared(nickname: string): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(clearedKey(nickname)) ?? "[]") as string[]);
  } catch {
    return new Set();
  }
}

function saveCleared(nickname: string, cleared: Set<string>): void {
  try {
    localStorage.setItem(clearedKey(nickname), JSON.stringify([...cleared]));
  } catch {
    // storage blocked: progress lasts for this visit only
  }
}

/** /report or #/report opens the evaluation report directly (also on GitHub Pages). */
function isReportRoute(): boolean {
  return window.location.hash === "#/report" || window.location.pathname.endsWith("/report");
}

function NicknameGate({ onDone }: { onDone: (name: string) => void }) {
  const [name, setName] = useState(loadNickname());
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const n = name.trim();
    if (!n) return;
    try {
      localStorage.setItem(NICKNAME_KEY, n);
    } catch {
      // storage blocked; the nickname still works for this visit
    }
    onDone(n);
  };
  return (
    <div className="gate">
      <p className="eyebrow">SceneSpeak · New York</p>
      <h1>뉴욕 거리를 걸으며 영어로 말해 보세요</h1>
      <p className="muted">
        카페, 핫도그 노점, 타임스스퀘어, 호텔, 지하철역에서 사람들이 기다리고 있어요. 닉네임별로 대화 기록과 복습
        문장이 저장됩니다.
      </p>
      <form onSubmit={submit} className="composer">
        <label htmlFor="nickname" className="visually-hidden">
          닉네임
        </label>
        <input
          id="nickname"
          value={name}
          maxLength={40}
          onChange={(e) => setName(e.target.value)}
          placeholder="닉네임 (예: mina)"
          autoFocus
        />
        <button type="submit" disabled={!name.trim()}>
          시작하기
        </button>
      </form>
      <p className="muted">
        <a href="#/report">평가 리포트 보기</a>
      </p>
    </div>
  );
}

type Tab = "world" | "review" | "report";

function Game({ nickname, onLogout }: { nickname: string; onLogout: () => void }) {
  const [tab, setTab] = useState<Tab>(isReportRoute() ? "report" : "world");
  const [talkingTo, setTalkingTo] = useState<NpcDef | null>(null);
  const [cleared, setCleared] = useState<Set<string>>(() => loadCleared(nickname));
  const [userId, setUserId] = useState<number | null>(null);
  const [muted, setMuted] = useState(false);
  const [reviewKey, setReviewKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    login(nickname)
      .then((r) => !cancelled && setUserId(r.user_id))
      .catch(() => undefined); // no backend (e.g. GitHub Pages): the street still works
    return () => {
      cancelled = true;
    };
  }, [nickname]);

  const finished = useCallback(
    (sceneId: string, success: boolean) => {
      setReviewKey((k) => k + 1);
      if (!success) return;
      setCleared((prev) => {
        const next = new Set(prev).add(sceneId);
        saveCleared(nickname, next);
        return next;
      });
    },
    [nickname],
  );

  const done = NPCS.filter((n) => cleared.has(n.sceneId)).length;

  return (
    <div className="app">
      <header className="top">
        <div>
          <p className="eyebrow">SceneSpeak · New York</p>
          <h1>
            미션 {done}/{NPCS.length}
          </h1>
        </div>
        <div className="top-actions">
          <button className="link" onClick={() => setMuted((m) => !m)} aria-pressed={muted}>
            {muted ? "음성 켜기" : "음성 끄기"}
          </button>
          <span className="muted">{nickname}</span>
          <button className="link" onClick={onLogout}>
            바꾸기
          </button>
        </div>
      </header>

      <nav className="tabs" aria-label="화면">
        <button aria-pressed={tab === "world"} onClick={() => setTab("world")}>
          거리
        </button>
        <button aria-pressed={tab === "review"} onClick={() => setTab("review")} disabled={userId === null}>
          복습
        </button>
        <button aria-pressed={tab === "report"} onClick={() => setTab("report")}>
          평가 리포트
        </button>
      </nav>

      {tab === "review" && userId !== null && <ReviewView key={reviewKey} userId={userId} />}
      {tab === "report" && <ReportView />}

      {/* The street stays mounted so the player keeps their spot while talking. */}
      <div hidden={tab !== "world"}>
        {talkingTo && (
          <ConversationScreen
            key={talkingTo.id}
            nickname={nickname}
            sceneId={talkingTo.sceneId}
            npcName={talkingTo.name}
            example={talkingTo.exampleEn}
            muted={muted}
            onClose={() => setTalkingTo(null)}
            onUserId={setUserId}
            onFinished={finished}
          />
        )}
        <div hidden={talkingTo !== null} className="world-layout">
          <WorldView cleared={cleared} paused={talkingTo !== null || tab !== "world"} onTalk={setTalkingTo} />
          <aside className="missions" aria-label="미션">
            <h2>오늘의 미션</h2>
            <ul>
              {NPCS.map((n) => (
                <li key={n.id} className={cleared.has(n.sceneId) ? "cleared" : ""}>
                  <span className="mission-mark" aria-hidden="true">
                    {cleared.has(n.sceneId) ? "✓" : "!"}
                  </span>
                  <span>
                    <b>{n.roleKo}</b> {n.name}
                    <br />
                    <span className="muted">{n.teaserKo}</span>
                  </span>
                </li>
              ))}
            </ul>
          </aside>
        </div>
      </div>
    </div>
  );
}

export function App() {
  const [nickname, setNickname] = useState<string | null>(null);
  const [reportOnly, setReportOnly] = useState(isReportRoute());

  useEffect(() => {
    const onHash = () => setReportOnly(isReportRoute());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  if (!nickname && reportOnly) {
    return (
      <div className="app">
        <p>
          <a href="#/">← SceneSpeak로 돌아가기</a>
        </p>
        <ReportView />
      </div>
    );
  }
  if (!nickname) return <NicknameGate onDone={setNickname} />;
  return <Game key={nickname} nickname={nickname} onLogout={() => setNickname(null)} />;
}
