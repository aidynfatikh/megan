import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import rawExample from "../test/example.json";
import type { Job } from "../types";
import { ReportView } from "./ReportView";

const example = rawExample as Job;

test("shows all mandatory sections and distinguishes examples from actual processing", () => {
  render(<ReportView job={example} onSource={vi.fn()} onEdit={vi.fn()} />);
  expect(
    screen.getByRole("heading", { name: "Executive summary" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "Decisions" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "Topics & takeaways" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "Open questions" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "Action items" }),
  ).toBeInTheDocument();
  expect(screen.queryByText(/verified against audio/i)).not.toBeInTheDocument();
});

test("source buttons return the original segment and its timestamp", () => {
  const onSource = vi.fn();
  render(<ReportView job={example} onSource={onSource} onEdit={vi.fn()} />);
  fireEvent.click(screen.getAllByRole("button", { name: /View source S2/ })[0]);
  expect(onSource).toHaveBeenCalledWith(
    expect.objectContaining({ segment_id: "S2", start: 12 }),
  );
});

test("empty action items explain that no tasks were found instead of inventing suggestions", () => {
  const job = structuredClone(example);
  job.report!.action_items = [];
  render(<ReportView job={job} onSource={vi.fn()} onEdit={vi.fn()} />);
  expect(
    screen.getByText("No explicit action items were found."),
  ).toBeInTheDocument();
});

test("unknown owner, deadline and priority have honest labels", () => {
  const job = structuredClone(example);
  const action = job.report!.action_items[0];
  action.assignee = null;
  action.speaker_id = null;
  action.due = { raw: null, date: null, resolution: "not_stated" };
  action.priority = "unspecified";
  render(<ReportView job={job} onSource={vi.fn()} onEdit={vi.fn()} />);
  expect(screen.getByText("Unassigned")).toBeInTheDocument();
  expect(screen.getByText("No deadline stated")).toBeInTheDocument();
  expect(screen.getAllByText("Not specified").length).toBeGreaterThan(0);
});
