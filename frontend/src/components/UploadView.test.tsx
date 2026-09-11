import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { UploadView } from "./UploadView";
import type { Health } from "../types";

const health = { ready: true, busy: false, max_upload_mb: 100 } as Health;

test("uploads a selected file without inventing a meeting date", async () => {
  const user = userEvent.setup();
  const onUpload = vi.fn();
  render(
    <UploadView
      health={health}
      submitting={false}
      onUpload={onUpload}
      onExample={vi.fn()}
    />,
  );
  const submit = screen.getByRole("button", { name: "Create meeting report" });
  expect(submit).toBeDisabled();
  const file = new File(["audio"], "meeting.m4a", { type: "audio/mp4" });
  await user.upload(screen.getByLabelText("Meeting recording"), file);
  await user.selectOptions(screen.getByLabelText("Report language"), "en");
  await user.click(submit);
  expect(onUpload).toHaveBeenCalledWith(file, "", "en");
});

test("unavailable services prevent uploads while allowing the labeled example", async () => {
  const user = userEvent.setup();
  const onExample = vi.fn();
  render(
    <UploadView
      health={{ ...health, ready: false }}
      submitting={false}
      onUpload={vi.fn()}
      onExample={onExample}
    />,
  );
  await user.upload(
    screen.getByLabelText("Meeting recording"),
    new File(["audio"], "test.wav", { type: "audio/wav" }),
  );
  expect(
    screen.getByRole("button", { name: "Create meeting report" }),
  ).toBeDisabled();
  await user.click(
    screen.getByRole("button", { name: "View sample report" }),
  );
  expect(onExample).toHaveBeenCalledOnce();
});

test("reselecting the active input tab preserves an already selected file", async () => {
  const user = userEvent.setup();
  const onUpload = vi.fn();
  render(
    <UploadView
      health={health}
      submitting={false}
      onUpload={onUpload}
      onExample={vi.fn()}
    />,
  );
  const file = new File(["audio"], "meeting.wav", { type: "audio/wav" });
  await user.upload(screen.getByLabelText("Meeting recording"), file);
  await user.click(screen.getByRole("button", { name: "Upload audio" }));
  await user.click(
    screen.getByRole("button", { name: "Create meeting report" }),
  );
  expect(onUpload).toHaveBeenCalledWith(file, "", "ru");
});
