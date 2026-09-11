import { useEffect, useState } from "react";
import { ArrowUpRight, LoaderCircle } from "lucide-react";
import { api } from "../api";

export function NotionExport({
  jobId,
  revision,
}: {
  jobId: string;
  revision: number;
}) {
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [setup, setSetup] = useState(false);
  const [token, setToken] = useState("");
  const [dataSource, setDataSource] = useState("");
  const [parentPage, setParentPage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ url: string; reused: boolean } | null>(
    null,
  );

  useEffect(() => {
    let active = true;
    api
      .notionStatus()
      .then((status) => {
        if (active) setConfigured(status.configured);
      })
      .catch((err: Error) => {
        if (active) setError(err.message);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <section className="panel notion-panel" aria-label="Notion integration">
      <div className="notion-heading">
        <div>
          <strong>Notion</strong>
          <p className="muted">
            Export this report and its cited passages. Audio stays on this
            machine.
          </p>
        </div>
        <div className="notion-buttons">
          {configured ? (
            <button
              className="secondary-button"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setError("");
                try {
                  setResult(await api.notionExport(jobId, revision));
                } catch (err) {
                  setError((err as Error).message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              {busy ? (
                <LoaderCircle className="spin" size={15} />
              ) : (
                <ArrowUpRight size={15} />
              )}
              Export to Notion
            </button>
          ) : null}
          <button
            className="text-button"
            disabled={busy || configured === null}
            onClick={() => setSetup(!setup)}
          >
            {configured ? "Connection settings" : "Connect Notion"}
          </button>
        </div>
      </div>
      {result ? (
        <p role="status">
          {result.reused
            ? "This revision is already exported."
            : "Report exported."}{" "}
          <a href={result.url} target="_blank" rel="noreferrer">
            Open in Notion
          </a>
        </p>
      ) : null}
      {error ? <p role="alert">{error}</p> : null}
      {setup ? (
        <form
          className="notion-setup"
          onSubmit={async (event) => {
            event.preventDefault();
            setBusy(true);
            setError("");
            try {
              const status = await api.notionConnect(
                token,
                dataSource.trim(),
                parentPage.trim(),
              );
              setConfigured(status.configured);
              setToken("");
              setSetup(false);
              setResult(null);
            } catch (err) {
              setError((err as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <label>
            Notion API token
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              autoComplete="off"
              required
              minLength={10}
              maxLength={500}
            />
          </label>
          <label>
            Existing Megan data source ID (optional)
            <input
              value={dataSource}
              onChange={(e) => setDataSource(e.target.value)}
            />
          </label>
          <label>
            Parent page ID (optional)
            <input
              value={parentPage}
              onChange={(e) => setParentPage(e.target.value)}
            />
          </label>
          <p className="muted">
            Leave the IDs blank to create a private Megan Meetings database.
            Internal connections need a shared parent page ID. The token is
            saved only on the local app server.
          </p>
          <button
            className="secondary-button"
            disabled={busy || token.length < 10}
          >
            {busy ? "Connecting…" : "Save connection"}
          </button>
        </form>
      ) : null}
    </section>
  );
}
