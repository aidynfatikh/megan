import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { api } from "../api";
import { NotionExport } from "./NotionExport";

vi.mock("../api", () => ({
  api: { notionStatus: vi.fn(), notionExport: vi.fn(), notionConnect: vi.fn() },
}));

test("exports the displayed revision only after an explicit click", async () => {
  vi.mocked(api.notionStatus).mockResolvedValue({
    configured: true,
    destination: "Megan Meetings",
  });
  vi.mocked(api.notionExport).mockResolvedValue({
    url: "https://www.notion.so/report",
    page_id: "page",
    revision: 3,
    reused: false,
  });
  render(<NotionExport jobId="meeting" revision={3} />);
  const button = await screen.findByRole("button", {
    name: "Export to Notion",
  });
  expect(api.notionExport).not.toHaveBeenCalled();
  await userEvent.click(button);
  expect(api.notionExport).toHaveBeenCalledWith("meeting", 3);
  expect(
    await screen.findByRole("link", { name: "Open in Notion" }),
  ).toHaveAttribute("href", "https://www.notion.so/report");
});

test("keeps a failed export visible and retryable", async () => {
  vi.mocked(api.notionStatus).mockResolvedValue({
    configured: true,
    destination: "Megan Meetings",
  });
  vi.mocked(api.notionExport).mockRejectedValue(
    new Error("Notion is busy. Try again later."),
  );
  render(<NotionExport jobId="meeting" revision={1} />);
  await userEvent.click(
    await screen.findByRole("button", { name: "Export to Notion" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent("Notion is busy");
  expect(
    screen.getByRole("button", { name: "Export to Notion" }),
  ).toBeEnabled();
});

test("connection input masks the token and clears it after saving", async () => {
  vi.mocked(api.notionStatus).mockResolvedValue({
    configured: false,
    destination: null,
  });
  vi.mocked(api.notionConnect).mockResolvedValue({
    configured: true,
    destination: "Megan Meetings",
  });
  const user = userEvent.setup();
  render(<NotionExport jobId="meeting" revision={1} />);
  await user.click(
    await screen.findByRole("button", { name: "Connect Notion" }),
  );
  const token = screen.getByLabelText("Notion API token");
  expect(token).toHaveAttribute("type", "password");
  await user.type(token, "test-token-value");
  await user.click(screen.getByRole("button", { name: "Save connection" }));
  expect(
    await screen.findByRole("button", { name: "Export to Notion" }),
  ).toBeEnabled();
  expect(screen.queryByLabelText("Notion API token")).not.toBeInTheDocument();
});
