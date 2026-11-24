import { expect, test } from "@playwright/test";

const PAGES: [string, string][] = [
  ["/", "Dashboard"], ["/profile", "My Profile"], ["/discovery", "Job Discovery"], ["/recommended", "Recommended Jobs"],
  ["/documents", "CV & Documents"], ["/cover-letters", "Cover Letters"], ["/assistant", "Application Assistant"],
  ["/tracker", "Application Tracker"], ["/interviews", "Interview Preparation"], ["/automation", "Automation Settings"],
  ["/ai", "AI Settings"], ["/system", "System Settings"],
];

test("all 12 pages render without crashing", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  for (const [path, title] of PAGES) {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: title, exact: true }).first()).toBeVisible();
  }
  expect(errors).toEqual([]);
});

test("create a profile and track an application end to end", async ({ page }) => {
  await page.goto("/profile");
  await page.getByLabel("Full name *").fill("E2E Tester");
  await page.getByLabel("Email").fill("e2e@example.com");
  await page.getByLabel("Technical and professional skills").fill("Python, React");
  await page.getByRole("button", { name: "Save profile" }).first().click();
  await expect(page.getByText(/saved/i).first()).toBeVisible();

  await page.goto("/tracker");
  await page.getByLabel("Company").fill("Acme");
  await page.getByLabel("Position").fill("Junior Developer");
  await page.getByLabel("Job URL").fill("https://jobs.example/acme/1");
  await page.getByRole("button", { name: "Add" }).click();
  await expect(page.getByRole("button", { name: "Junior Developer" })).toBeVisible();

  // duplicate protection surfaces in the UI
  await page.getByLabel("Company").fill("Acme");
  await page.getByLabel("Position").fill("Junior Developer");
  await page.getByLabel("Job URL").fill("https://jobs.example/acme/2");
  await page.getByRole("button", { name: "Add" }).click();
  await expect(page.getByText(/already have an application/i).first()).toBeVisible();
});

test("AI features degrade gracefully when AI is off", async ({ page }) => {
  await page.goto("/ai");
  await expect(page.getByText(/turned off|not running|Ollama/i).first()).toBeVisible();
});
