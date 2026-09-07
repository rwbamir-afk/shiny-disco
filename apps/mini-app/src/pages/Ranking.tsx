import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useSession } from "../state/session";
import type { RankingEntry } from "../lib/contracts";
import type { Navigate } from "../App";

export function Ranking({ navigate }: { navigate: Navigate }) {
  const { accessToken } = useSession();

  const [rows, setRows] = useState<RankingEntry[]>([]);
  const [tab, setTab] = useState<"global" | "weekly">("global");
  const [error, setError] = useState<string | null>(null);
  const [position, setPosition] = useState<number | null>(null);
  const [around, setAround] = useState<RankingEntry[]>([]);

  useEffect(() => {
    api<RankingEntry[]>(
      `/api/v1/rankings/${tab}`,
      {
        token: accessToken,
      },
    )
      .then(setRows)
      .catch((e) => {
        setError(
          e instanceof Error
            ? e.message
            : "خطا",
        );
      });
  }, [tab, accessToken]);

  useEffect(() => {
    Promise.all([
      api<{ position: number }>(
        "/api/v1/rankings/me/position",
        {
          token: accessToken,
        },
      ),

      api<{
        entries: Array<RankingEntry & { position: number }>;
      }>(
        "/api/v1/rankings/around-me?window=2",
        {
          token: accessToken,
        },
      ),
    ])
      .then(([p, a]) => {
        setPosition(p.position);
        setAround(a.entries);
      })
      .catch(() => undefined);
  }, [accessToken]);

  const fa = (n: number) =>
    n.toLocaleString("fa-IR");

  return (
    <div className="app pad col">
      <h2>رتبه‌بندی</h2>

      <div className="row">
        <button
          className={`btn ${
            tab === "global"
              ? "primary"
              : "ghost"
          }`}
          onClick={() => setTab("global")}
        >
          کلی
        </button>

        <button
          className={`btn ${
            tab === "weekly"
              ? "primary"
              : "ghost"
          }`}
          onClick={() => setTab("weekly")}
        >
          هفتگی
        </button>
      </div>

      {position !== null && (
        <div className="status good">
          جایگاه فعلی تو: {fa(position)}
        </div>
      )}

      {around.length > 0 && (
        <section className="panel pad col mt">
          <div className="section-title">
            اطراف جایگاه من
          </div>

          {around.map((r) => (
            <div
              key={r.user_id}
              className="row"
            >
              <span>
                {r.position !== undefined
                  ? `${fa(r.position)}.`
                  : "-"}
              </span>

              <span className="grow">
                {r.display_name}
              </span>

              <b>
                {fa(r.rating)}
              </b>
            </div>
          ))}
        </section>
      )}

      <div className="col mt">
        {rows.map((r, i) => (
          <div
            key={r.user_id}
            className="panel pad row"
          >
            <span
              className="section-title"
              style={{ width: 32 }}
            >
              {r.position !== undefined
                ? fa(r.position)
                : fa(i + 1)}
            </span>

            <span
              className="grow"
              style={{ fontWeight: 700 }}
            >
              {r.display_name}
            </span>

            <span className="teamchip">
              {r.rank_tier?.title ?? ""} ·{" "}
              {fa(r.rating)}
            </span>
          </div>
        ))}

        {!rows.length && !error && (
          <div className="status info">
            رتبه‌ای ثبت نشده
          </div>
        )}
      </div>

      {error && (
        <div className="status error mt">
          {error}
        </div>
      )}

      <button
        className="btn ghost mt"
        onClick={() => navigate("home")}
      >
        بازگشت
      </button>
    </div>
  );
}
