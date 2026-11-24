import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import ApplicationAssistantPage from "./ApplicationAssistantPage";
import DashboardPage from "./DashboardPage";
import ProfilePage, { emptyForm, toApi, toForm } from "./ProfilePage";
import TrackerPage from "./TrackerPage";
import AppLayout, { NAV } from "@/layouts/AppLayout";
import { Route, Routes } from "react-router-dom";
import { mockApi, renderApp } from "@/test/utils";
import type { Application, ApplicationDetail, Dashboard, Profile } from "@/types/api";

afterEach(() => vi.unstubAllGlobals());

const dash: Dashboard = { discovered_jobs: 12, matching_jobs: 4, submitted: 3, awaiting_approval: 2, interviews: 1, rejections: 1, offers: 0,
  by_status: { discovered: 1, shortlisted: 2, preparing: 0, awaiting_approval: 2, applied: 3, interview: 1, assessment: 0, offer: 0, rejected: 1, withdrawn: 0 },
  follow_ups: [{ id: 1, company: "Acme", position: "Dev", date: "2030-01-05T09:00:00Z" }], recent_activity: [{ actor: "discovery", action: "run", message: "3 new jobs", at: "2026-11-14T10:00:00Z" }] };

describe("layout", () => {
  it("shows all 12 navigation entries", () => {
    mockApi({ "GET /notifications": [] });
    renderApp(<Routes><Route element={<AppLayout />}><Route index element={<p>home</p>} /></Route></Routes>);
    const nav = within(screen.getAllByRole("navigation", { name: "Main" })[0]);
    expect(NAV).toHaveLength(12);
    NAV.forEach((n) => expect(nav.getByRole("link", { name: n.label })).toBeInTheDocument());
  });
});

describe("DashboardPage", () => {
  it("renders statistics, follow-ups and activity", async () => {
    mockApi({ "GET /dashboard": dash });
    renderApp(<DashboardPage />);
    expect((await screen.findAllByText("Discovered")).length).toBeGreaterThan(0);
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText(/2 application\(s\) are ready for your review/)).toBeInTheDocument();
    expect(screen.getByText(/@ Acme/)).toBeInTheDocument();
    expect(screen.getByText(/3 new jobs/)).toBeInTheDocument();
  });
  it("shows an error state with retry when the backend fails", async () => {
    mockApi({ "GET /dashboard": { status: 500, body: { error: "internal_error", message: "Unexpected server error." } } });
    renderApp(<DashboardPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Unexpected server error.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
  it("shows empty states for a new user", async () => {
    mockApi({ "GET /dashboard": { ...dash, follow_ups: [], recent_activity: [], awaiting_approval: 0 } });
    renderApp(<DashboardPage />);
    expect(await screen.findByText("No follow-ups scheduled")).toBeInTheDocument();
    expect(screen.getByText("No activity yet")).toBeInTheDocument();
  });
});

describe("profile mapping (never invents data)", () => {
  const p: Profile = { ...({} as Profile), full_name: "Ada", email: "a@b.co", phone: "", location: "", country: "", headline: "", summary: "", portfolio_url: "", github_url: "", linkedin_url: "",
    salary_min: null, salary_max: null, salary_currency: "USD", employment_types: [], preferred_locations: [], work_modes: ["remote"], notice_period: "", available_from: "", verified_facts: { work_authorization: "Citizen", other: "x" },
    education: [], employment: [{ company: "Acme", title: "Dev", location: "", start_date: "2023-01", end_date: "", is_current: true, description: "", achievements: ["Built X", "Did Y"] }],
    skills: [{ name: "Python", category: "technical", level: "", years: 3 }], certifications: [], languages: [] };
  it("round-trips without losing skill years or verified facts", () => {
    const api = toApi(toForm(p), p);
    expect(api.skills).toEqual([{ name: "Python", category: "technical", level: "", years: 3 }]);
    expect(api.employment[0].achievements).toEqual(["Built X", "Did Y"]);
    expect(api.work_modes).toEqual(["remote"]);
    expect(api.verified_facts).toEqual({ work_authorization: "Citizen", other: "x" });
    expect(api.salary_min).toBeNull();
  });
  it("clearing work authorization removes only that fact", () => {
    const f = { ...toForm(p), work_authorization: "" };
    expect(toApi(f, p).verified_facts).toEqual({ other: "x" });
  });
  it("empty profile maps to blanks, not placeholders", () => { expect(toForm(null)).toEqual(emptyForm); expect(toApi(emptyForm).skills).toEqual([]); });
});

describe("ProfilePage", () => {
  it("validates required fields and does not call the API", async () => {
    const calls = mockApi({ "GET /profile": null });
    renderApp(<ProfilePage />);
    await screen.findByRole("heading", { name: "My Profile" });
    await userEvent.type(screen.getByLabelText("Full name *"), "Ada");
    await userEvent.type(screen.getByLabelText("Email"), "not-an-email");
    await userEvent.click(screen.getAllByRole("button", { name: "Save profile" })[0]);
    expect(await screen.findByText("Enter a valid email address")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "PUT")).toHaveLength(0);
  });
  it("saves a valid profile", async () => {
    const calls = mockApi({ "GET /profile": null, "PUT /profile": (b: unknown) => b });
    renderApp(<ProfilePage />);
    await userEvent.type(await screen.findByLabelText("Full name *"), "Ada Tester");
    await userEvent.type(screen.getByLabelText("Technical and professional skills"), "Python, React");
    await userEvent.click(screen.getAllByRole("button", { name: "Save profile" })[0]);
    await waitFor(() => expect(calls.some((c) => c.method === "PUT")).toBe(true));
    const put = calls.find((c) => c.method === "PUT")!.body as Profile;
    expect(put.full_name).toBe("Ada Tester"); expect(put.skills.map((s) => s.name)).toEqual(["Python", "React"]);
  });
  it("adds and removes an employment entry", async () => {
    mockApi({ "GET /profile": null });
    renderApp(<ProfilePage />);
    await userEvent.click(await screen.findByRole("button", { name: /Add job/ }));
    expect(screen.getByLabelText("Company *")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Remove role 1/ }));
    expect(screen.queryByLabelText("Company *")).toBeNull();
  });
});

const baseApp: ApplicationDetail = { id: 7, listing_id: 1, company: "Globex", position: "Junior Dev", job_url: "https://g.example/apply", status: "awaiting_approval", applied_at: null, cv_id: 1, cover_letter_id: 1,
  confirmation: "", follow_up_date: null, notes: "", submission_result: "", approved_at: null, created_at: "2026-11-14T00:00:00Z", events: [], interviews: [], recruiters: [],
  fill_report: { status: "ready_for_review", filled: 3, pages: [{ page: 1, url: "u", fields: [{ field_id: "f1", label: "First name", action: "fill", status: "ok", value: "Ada", source: "profile", required: true, filled: true, verified: true, note: "" }] }] } };

describe("ApplicationAssistantPage — approval gate", () => {
  const listItem: Application = baseApp;
  function setup(app: ApplicationDetail) {
    return mockApi({
      "GET /applications": { items: [listItem], total: 1, page: 1, page_size: 100 }, "GET /applications/7": app, "GET /answers": [],
      "POST /applications/7/approve": { ...app, approved_at: "2026-11-14T10:00:00Z" },
      "POST /applications/7/submit": { result: "success" }, "POST /applications/7/prepare": { status: "ready_for_review" },
    });
  }

  it("cannot submit before approving", async () => {
    const calls = setup(baseApp);
    renderApp(<ApplicationAssistantPage />, "/assistant?app=7");
    const submit = await screen.findByRole("button", { name: /Submit application/ });
    expect(submit).toBeDisabled();
    expect(screen.getByRole("button", { name: "Approve for submission" })).toBeEnabled();
    expect(calls.some((c) => c.path.endsWith("/submit"))).toBe(false);
  });

  it("cannot approve while the form needs the user", async () => {
    setup({ ...baseApp, fill_report: { ...baseApp.fill_report, status: "needs_input", needs_user: ["Are you authorized to work?"] } });
    renderApp(<ApplicationAssistantPage />, "/assistant?app=7");
    expect(await screen.findByRole("button", { name: "Approve for submission" })).toBeDisabled();
    expect(screen.getByText(/never guesses legal, eligibility or demographic/)).toBeInTheDocument();
    expect(screen.getByText("Are you authorized to work?")).toBeInTheDocument();
  });

  it("requires a confirmation dialog, and cancelling sends nothing", async () => {
    const calls = setup({ ...baseApp, approved_at: "2026-11-14T10:00:00Z" });
    renderApp(<ApplicationAssistantPage />, "/assistant?app=7");
    await userEvent.click(await screen.findByRole("button", { name: /Submit application/ }));
    const dialog = await screen.findByRole("dialog", { name: "Submit this application now?" });
    expect(within(dialog).getByText(/cannot be recalled/)).toBeInTheDocument();
    expect(calls.some((c) => c.path.endsWith("/submit"))).toBe(false);
    await userEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(calls.some((c) => c.path.endsWith("/submit"))).toBe(false);
  });

  it("submits with confirm=true only after the dialog is confirmed", async () => {
    const calls = setup({ ...baseApp, approved_at: "2026-11-14T10:00:00Z" });
    renderApp(<ApplicationAssistantPage />, "/assistant?app=7");
    await userEvent.click(await screen.findByRole("button", { name: /Submit application/ }));
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Yes, submit" }));
    await waitFor(() => expect(calls.filter((c) => c.path.endsWith("/submit"))).toHaveLength(1));
    expect(calls.find((c) => c.path.endsWith("/submit"))!.body).toEqual({ confirm: true });
    expect(await screen.findByText(/Submitted and confirmed by the site/)).toBeInTheDocument();
  });

  it("shows CAPTCHA pauses as a call for human help", async () => {
    setup({ ...baseApp, status: "preparing", fill_report: { status: "intervention_required", reason: "A CAPTCHA / bot check is present." } });
    renderApp(<ApplicationAssistantPage />, "/assistant?app=7");
    expect(await screen.findByText(/Paused — your help is needed/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Submit application/ })).toBeDisabled();
  });

  it("surfaces a failed submission without claiming success", async () => {
    const calls = setup({ ...baseApp, approved_at: "x" });
    mockApi({ "GET /applications": { items: [listItem], total: 1, page: 1, page_size: 100 }, "GET /applications/7": { ...baseApp, approved_at: "x" }, "GET /answers": [], "POST /applications/7/submit": { result: "incomplete", reason: "Required fields are empty: Email" } });
    renderApp(<ApplicationAssistantPage />, "/assistant?app=7");
    await userEvent.click(await screen.findByRole("button", { name: /Submit application/ }));
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Yes, submit" }));
    expect(await screen.findByText(/Not completed \(incomplete\)/)).toBeInTheDocument();
    expect(screen.getByText(/Required fields are empty: Email/)).toBeInTheDocument();
    expect(screen.queryByText(/Submitted and confirmed/)).toBeNull();
    void calls;
  });
});

describe("TrackerPage", () => {
  const items: Application[] = [{ ...baseApp, status: "applied", applied_at: "2026-11-01T00:00:00Z" }];
  it("shows an empty state", async () => {
    mockApi({ "GET /applications": { items: [], total: 0, page: 1, page_size: 15 } });
    renderApp(<TrackerPage />);
    expect(await screen.findByText("No applications yet")).toBeInTheDocument();
  });
  it("updates a status inline", async () => {
    const calls = mockApi({ "GET /applications": { items, total: 1, page: 1, page_size: 15 }, "PATCH /applications/7": {} });
    renderApp(<TrackerPage />);
    await userEvent.selectOptions(await screen.findByLabelText("Status for Junior Dev"), "interview");
    await waitFor(() => expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ status: "interview" }));
  });
  it("asks for confirmation before deleting", async () => {
    const calls = mockApi({ "GET /applications": { items, total: 1, page: 1, page_size: 15 }, "DELETE /applications/7": {} });
    renderApp(<TrackerPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE")).toBe(true));
  });
  it("shows the duplicate warning from the server when adding", async () => {
    mockApi({ "GET /applications": { items: [], total: 0, page: 1, page_size: 15 }, "POST /applications": { status: 409, body: { error: "conflict", message: "You already have an application for 'Dev' at 'Acme' (status: applied)." } } });
    renderApp(<TrackerPage />);
    await userEvent.type(await screen.findByLabelText("Company"), "Acme");
    await userEvent.type(screen.getByLabelText("Position"), "Dev");
    await userEvent.type(screen.getByLabelText("Job URL"), "https://a.example/1");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect((await screen.findAllByText(/You already have an application/)).length).toBeGreaterThan(0);
  });
});
