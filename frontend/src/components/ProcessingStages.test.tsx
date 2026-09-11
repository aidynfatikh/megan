import { render, screen } from "@testing-library/react";
import { ProcessingStages } from "./ProcessingStages";
import rawExample from "../test/example.json";
import type { Job } from "../types";

test("speaker separation has its own active stage before analysis", () => {
  const job = structuredClone(rawExample) as Job;
  job.stage = "diarize";
  job.diarization_status = "running";
  render(<ProcessingStages job={job} />);
  expect(
    screen.getByText("Separate speakers").closest("[aria-current]"),
  ).toHaveAttribute("aria-current", "step");
  expect(screen.getByText("Analyze").closest("[aria-current]")).toBeNull();
});

test("the two-model profile does not display a disabled speaker stage", () => {
  const job = structuredClone(rawExample) as Job;
  job.stage = "transcribe";
  job.diarization_status = "disabled";
  render(<ProcessingStages job={job} />);
  expect(screen.queryByText("Separate speakers")).not.toBeInTheDocument();
});
