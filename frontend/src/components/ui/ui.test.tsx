import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ScoreBadge, StatusBadge } from "./Badge";
import { Button } from "./Button";
import { ConfirmDialog } from "./ConfirmDialog";
import { Input } from "./Form";
import { Pagination } from "./Pagination";
import { ErrorState } from "./States";

describe("Button", () => {
  it("is disabled and busy while loading", () => {
    render(<Button loading>Save</Button>);
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
    expect(screen.getByRole("button")).toHaveAttribute("aria-busy", "true");
  });
  it("does not fire onClick when disabled", async () => {
    const fn = vi.fn(); render(<Button disabled onClick={fn}>Go</Button>);
    await userEvent.click(screen.getByRole("button")); expect(fn).not.toHaveBeenCalled();
  });
});

describe("Input", () => {
  it("links label, error and aria-invalid", () => {
    render(<Input label="Email" error="Invalid email" />);
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("alert")).toHaveTextContent("Invalid email");
  });
});

describe("Pagination", () => {
  it("navigates and disables edges", async () => {
    const onPage = vi.fn(); render(<Pagination page={1} pageSize={10} total={25} onPage={onPage} />);
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Next" })); expect(onPage).toHaveBeenCalledWith(2);
    expect(screen.getByText(/Page 1 of 3/)).toBeInTheDocument();
  });
  it("hides controls for a single page", () => {
    render(<Pagination page={1} pageSize={10} total={3} onPage={() => {}} />);
    expect(screen.queryByRole("button")).toBeNull(); expect(screen.getByText("3 results")).toBeInTheDocument();
  });
});

describe("ConfirmDialog", () => {
  it("only confirms on explicit click and cancels with Escape", async () => {
    const onConfirm = vi.fn(), onCancel = vi.fn();
    render(<ConfirmDialog open title="Delete?" description="Sure" confirmLabel="Yes" onConfirm={onConfirm} onCancel={onCancel} />);
    expect(screen.getByRole("dialog", { name: "Delete?" })).toBeInTheDocument();
    expect(onConfirm).not.toHaveBeenCalled();
    await userEvent.keyboard("{Escape}"); expect(onCancel).toHaveBeenCalled(); expect(onConfirm).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Yes" })); expect(onConfirm).toHaveBeenCalledTimes(1);
  });
  it("renders nothing when closed", () => {
    render(<ConfirmDialog open={false} title="T" description="d" onConfirm={() => {}} onCancel={() => {}} />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("badges and states", () => {
  it("score badge exposes an accessible label", () => { render(<ScoreBadge score={82} />); expect(screen.getByText(/Match score/)).toBeInTheDocument(); expect(screen.getByText(/82%/)).toBeInTheDocument(); });
  it("status badge humanises the status", () => { render(<StatusBadge status="awaiting_approval" />); expect(screen.getByText("awaiting approval")).toBeInTheDocument(); });
  it("error state shows message and retry", async () => {
    const retry = vi.fn(); render(<ErrorState error={new Error("Backend down")} onRetry={retry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Backend down"); await userEvent.click(screen.getByRole("button", { name: "Try again" })); expect(retry).toHaveBeenCalled();
  });
});
