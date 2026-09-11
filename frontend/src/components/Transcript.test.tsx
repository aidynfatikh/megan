import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import rawExample from "../test/example.json";
import type { Job } from "../types";
import { Transcript } from "./Transcript";

const example = rawExample as Job;

function show(job: Job = example) {
  render(
    <Transcript job={job} currentTime={0} onSource={vi.fn()} />,
  );
}

test("speaker chips filter the transcript instead of opening a rename field", () => {
  show();
  expect(screen.getByText(/The landing page is ready/)).toBeInTheDocument();
  expect(screen.getByText(/Mira will prepare the launch copy/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Dana", pressed: false }));
  expect(screen.getByText(/The landing page is ready/)).toBeInTheDocument();
  expect(
    screen.queryByText(/Mira will prepare the launch copy/),
  ).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Speaker name")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
});

test("selecting a second voice widens the filter and deselecting restores every segment", () => {
  show();
  fireEvent.click(screen.getByRole("button", { name: "Dana" }));
  fireEvent.click(screen.getByRole("button", { name: "Mira" }));
  expect(screen.getByText(/The landing page is ready/)).toBeInTheDocument();
  expect(screen.getByText(/Mira will prepare the launch copy/)).toBeInTheDocument();
  expect(
    screen.queryByText(/Alex will finish the accessibility review/),
  ).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Dana", pressed: true }));
  fireEvent.click(screen.getByRole("button", { name: "Mira", pressed: true }));
  expect(
    screen.getByText(/Alex will finish the accessibility review/),
  ).toBeInTheDocument();
});

test("a filter that matches nothing says so rather than showing an empty panel", () => {
  const job = structuredClone(example);
  // Unattributed segments belong to no voice, so a speaker filter must hide them.
  job.segments = job.segments.map((s) => ({ ...s, speaker_id: null }));
  show(job);
  fireEvent.click(screen.getByRole("button", { name: "Dana" }));
  expect(screen.getByText("No matching transcript segments.")).toBeInTheDocument();
});

test("a transcript without speakers shows no filter row", () => {
  const job = structuredClone(example);
  job.speakers = [];
  show(job);
  expect(
    screen.queryByRole("group", { name: "Filter by speaker" }),
  ).not.toBeInTheDocument();
  expect(screen.getByText(/The landing page is ready/)).toBeInTheDocument();
});
