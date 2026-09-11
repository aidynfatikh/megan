import { Check } from "lucide-react";
import type { Job } from "../types";

export function ProcessingStages({ job }: { job: Job }) {
  const separate = job.diarization_status !== "disabled";
  const steps = [
    ["decode", "Prepare"],
    ["transcribe", "Transcribe"],
    ...(separate ? [["diarize", "Separate speakers"]] : []),
    ["analyze", "Analyze"],
    ["check_sources", "Check sources"],
  ];
  const aliases: Record<string, string> = {
    queued: "decode",
    release_models: job.segments.length && separate ? "diarize" : "transcribe",
    transcript_ready: separate ? "diarize" : "analyze",
    speakers_ready: "analyze",
    persist: "check_sources",
  };
  const current = steps.findIndex(
    ([id]) => id === (aliases[job.stage] ?? job.stage),
  );
  return (
    <div className="stage-track">
      {steps.map(([id, label], i) => (
        <div
          key={id}
          className={i < current ? "complete" : i === current ? "current" : ""}
          aria-current={i === current ? "step" : undefined}
        >
          <span>{i < current ? <Check size={13} /> : i + 1}</span>
          <span>{label}</span>
        </div>
      ))}
    </div>
  );
}
