import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, Trash2, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useFieldArray, useForm, type Resolver } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Input, Select, Textarea } from "@/components/ui/Form";
import { PageHeader } from "@/components/ui/Page";
import { ErrorState, Notice, Spinner } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { useAction, useGet } from "@/hooks/useApi";
import { api } from "@/services/api";
import type { Profile } from "@/types/api";

const date = z.string().regex(/^(\d{4}(-\d{2})?)?$/, "Use YYYY or YYYY-MM");
const url = z.string().refine((v) => v === "" || /^https?:\/\//i.test(v), "Must start with http:// or https://");

export const profileSchema = z.object({
  full_name: z.string().min(1, "Full name is required").max(200),
  email: z.string().refine((v) => v === "" || /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v), "Enter a valid email address"),
  phone: z.string().max(50), location: z.string().max(200), country: z.string().max(100),
  headline: z.string().max(300), summary: z.string().max(4000),
  portfolio_url: url, github_url: url, linkedin_url: url,
  salary_min: z.string().regex(/^\d*$/, "Digits only"), salary_max: z.string().regex(/^\d*$/, "Digits only"), salary_currency: z.string().max(10),
  employment_types: z.string(), preferred_locations: z.string(), notice_period: z.string().max(100), available_from: z.string().max(50),
  work_remote: z.boolean(), work_hybrid: z.boolean(), work_onsite: z.boolean(),
  work_authorization: z.string().max(300),
  skills: z.string(),
  education: z.array(z.object({ institution: z.string().min(1, "Required"), degree: z.string(), field_of_study: z.string(), start_date: date, end_date: date, description: z.string() })),
  employment: z.array(z.object({ company: z.string().min(1, "Required"), title: z.string().min(1, "Required"), location: z.string(), start_date: date, end_date: date, is_current: z.boolean(), description: z.string(), achievements: z.string() })),
  certifications: z.array(z.object({ name: z.string().min(1, "Required"), issuer: z.string(), issue_date: date })),
  languages: z.array(z.object({ language: z.string().min(1, "Required"), proficiency: z.string() })),
});
export type FormValues = z.infer<typeof profileSchema>;

const list = (s: string) => s.split(/[,\n]/).map((x) => x.trim()).filter(Boolean);

export const emptyForm: FormValues = {
  full_name: "", email: "", phone: "", location: "", country: "", headline: "", summary: "", portfolio_url: "", github_url: "", linkedin_url: "",
  salary_min: "", salary_max: "", salary_currency: "USD", employment_types: "", preferred_locations: "", notice_period: "", available_from: "",
  work_remote: false, work_hybrid: false, work_onsite: false, work_authorization: "", skills: "",
  education: [], employment: [], certifications: [], languages: [],
};

export function toForm(p: Partial<Profile> | null | undefined): FormValues {
  if (!p) return emptyForm;
  const modes = p.work_modes ?? [];
  return {
    ...emptyForm,
    full_name: p.full_name ?? "", email: p.email ?? "", phone: p.phone ?? "", location: p.location ?? "", country: p.country ?? "",
    headline: p.headline ?? "", summary: p.summary ?? "", portfolio_url: p.portfolio_url ?? "", github_url: p.github_url ?? "", linkedin_url: p.linkedin_url ?? "",
    salary_min: p.salary_min?.toString() ?? "", salary_max: p.salary_max?.toString() ?? "", salary_currency: p.salary_currency ?? "USD",
    employment_types: (p.employment_types ?? []).join(", "), preferred_locations: (p.preferred_locations ?? []).join(", "),
    notice_period: p.notice_period ?? "", available_from: p.available_from ?? "",
    work_remote: modes.includes("remote"), work_hybrid: modes.includes("hybrid"), work_onsite: modes.includes("onsite"),
    work_authorization: p.verified_facts?.work_authorization ?? "",
    skills: (p.skills ?? []).map((s) => s.name).join(", "),
    education: (p.education ?? []).map((e) => ({ institution: e.institution ?? "", degree: e.degree ?? "", field_of_study: e.field_of_study ?? "", start_date: e.start_date ?? "", end_date: e.end_date ?? "", description: e.description ?? "" })),
    employment: (p.employment ?? []).map((e) => ({ company: e.company ?? "", title: e.title ?? "", location: e.location ?? "", start_date: e.start_date ?? "", end_date: e.end_date ?? "", is_current: !!e.is_current, description: e.description ?? "", achievements: (e.achievements ?? []).join("\n") })),
    certifications: (p.certifications ?? []).map((c) => ({ name: c.name ?? "", issuer: c.issuer ?? "", issue_date: c.issue_date ?? "" })),
    languages: (p.languages ?? []).map((l) => ({ language: l.language ?? "", proficiency: l.proficiency ?? "" })),
  };
}

export function toApi(v: FormValues, existing?: Profile | null): Profile {
  const keepYears = new Map((existing?.skills ?? []).map((s) => [s.name.toLowerCase(), s]));
  return {
    full_name: v.full_name, email: v.email, phone: v.phone, location: v.location, country: v.country, headline: v.headline, summary: v.summary,
    portfolio_url: v.portfolio_url, github_url: v.github_url, linkedin_url: v.linkedin_url,
    salary_min: v.salary_min ? Number(v.salary_min) : null, salary_max: v.salary_max ? Number(v.salary_max) : null, salary_currency: v.salary_currency || "USD",
    employment_types: list(v.employment_types), preferred_locations: list(v.preferred_locations),
    work_modes: [v.work_remote && "remote", v.work_hybrid && "hybrid", v.work_onsite && "onsite"].filter(Boolean) as string[],
    notice_period: v.notice_period, available_from: v.available_from,
    verified_facts: v.work_authorization ? { ...(existing?.verified_facts ?? {}), work_authorization: v.work_authorization } : Object.fromEntries(Object.entries(existing?.verified_facts ?? {}).filter(([k]) => k !== "work_authorization")),
    skills: list(v.skills).map((name) => ({ name, category: keepYears.get(name.toLowerCase())?.category ?? "technical", level: keepYears.get(name.toLowerCase())?.level ?? "", years: keepYears.get(name.toLowerCase())?.years ?? null })),
    education: v.education,
    employment: v.employment.map((e) => ({ ...e, achievements: e.achievements.split("\n").map((x) => x.trim()).filter(Boolean) })),
    certifications: v.certifications.map((c) => ({ ...c, expiry_date: "", credential_url: "" })),
    languages: v.languages,
  };
}

function Section({ title, onAdd, addLabel, children }: { title: string; onAdd: () => void; addLabel: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader title={title} action={<Button variant="secondary" size="sm" onClick={onAdd}><Plus className="h-4 w-4" aria-hidden /> {addLabel}</Button>} />
      <CardBody className="space-y-5">{children}</CardBody>
    </Card>
  );
}

export default function ProfilePage() {
  const toast = useToast();
  const { data: profile, isLoading, error, refetch } = useGet<Profile | null>(["profile"], "/profile");
  const form = useForm<FormValues>({ resolver: zodResolver(profileSchema) as unknown as Resolver<FormValues>, defaultValues: emptyForm });
  const { register, control, handleSubmit, reset, formState: { errors, isDirty } } = form;
  const edu = useFieldArray({ control, name: "education" });
  const emp = useFieldArray({ control, name: "employment" });
  const cert = useFieldArray({ control, name: "certifications" });
  const lang = useFieldArray({ control, name: "languages" });
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [imported, setImported] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => { if (!isLoading) reset(toForm(profile)); }, [profile, isLoading, reset]);

  const save = useAction((v: FormValues) => api.put<Profile>("/profile", toApi(v, profile)), {
    success: "Profile saved", invalidate: [["profile"], ["dashboard"]], onSuccess: () => setImported(false),
  });
  const remove = useAction(() => api.del("/profile"), { success: "Profile deleted", invalidate: [["profile"]], onSuccess: () => setConfirmDelete(false) });

  async function onImport(file: File) {
    const fd = new FormData(); fd.append("file", file);
    try {
      const res = await api.upload<{ draft: Partial<Profile> }>("/profile/import-cv", fd);
      const draft = toForm(res.draft); const cur = form.getValues();
      // Only fill what the CV actually contained; never overwrite what the user already entered with blanks.
      const merged = Object.fromEntries(Object.entries(draft).map(([k, v]) => {
        const old = (cur as Record<string, unknown>)[k];
        const empty = v === "" || (Array.isArray(v) && v.length === 0);
        return [k, empty ? old : v];
      })) as FormValues;
      reset(merged, { keepDefaultValues: false });
      form.trigger(); setImported(true);
      toast.success("CV read. Review the extracted details, then save.");
    } catch (e) { toast.error((e as Error).message); }
  }

  if (isLoading) return <Spinner />;
  if (error) return <ErrorState error={error} onRetry={refetch} />;

  return (
    <form onSubmit={handleSubmit((v) => save.mutate(v))} noValidate className="space-y-6">
      <PageHeader title="My Profile" description="The single source of truth for every CV, letter and form. The agent never invents information that is not here."
        actions={<>
          <input ref={fileRef} type="file" accept=".pdf,.docx" className="sr-only" aria-label="Import CV file" onChange={(e) => { const f = e.target.files?.[0]; if (f) onImport(f); e.target.value = ""; }} />
          <Button variant="secondary" onClick={() => fileRef.current?.click()}><Upload className="h-4 w-4" aria-hidden /> Import from CV</Button>
          <Button type="submit" loading={save.isPending} disabled={!isDirty && !imported}>Save profile</Button>
        </>} />
      {imported && <Notice tone="warn">Details were extracted automatically from your CV. Please check them carefully — nothing is saved until you press “Save profile”.</Notice>}

      <Card>
        <CardHeader title="Personal details" />
        <CardBody className="grid gap-4 sm:grid-cols-2">
          <Input label="Full name *" {...register("full_name")} error={errors.full_name?.message} autoComplete="name" />
          <Input label="Email" type="email" {...register("email")} error={errors.email?.message} autoComplete="email" />
          <Input label="Phone" {...register("phone")} error={errors.phone?.message} autoComplete="tel" />
          <Input label="Location (city)" {...register("location")} />
          <Input label="Country" {...register("country")} />
          <Input label="Professional headline" {...register("headline")} hint="e.g. Junior Full-Stack Developer" />
          <div className="sm:col-span-2"><Textarea label="Summary" {...register("summary")} hint="Written by you; used as-is in CVs and answers." /></div>
          <Input label="Portfolio URL" {...register("portfolio_url")} error={errors.portfolio_url?.message} />
          <Input label="GitHub URL" {...register("github_url")} error={errors.github_url?.message} />
          <Input label="LinkedIn URL" {...register("linkedin_url")} error={errors.linkedin_url?.message} />
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Skills" description="Comma-separated. Only skills listed here (or evidenced in your experience) are ever claimed." />
        <CardBody><Textarea label="Technical and professional skills" rows={2} {...register("skills")} /></CardBody>
      </Card>

      <Section title="Employment history" addLabel="Add job" onAdd={() => emp.append({ company: "", title: "", location: "", start_date: "", end_date: "", is_current: false, description: "", achievements: "" })}>
        {emp.fields.length === 0 && <p className="text-sm text-slate-500">No roles added yet.</p>}
        {emp.fields.map((f, i) => (
          <fieldset key={f.id} className="space-y-3 rounded-lg border border-slate-200 p-4">
            <legend className="px-1 text-sm font-medium text-slate-600">Role {i + 1}</legend>
            <div className="grid gap-3 sm:grid-cols-2">
              <Input label="Company *" {...register(`employment.${i}.company`)} error={errors.employment?.[i]?.company?.message} />
              <Input label="Job title *" {...register(`employment.${i}.title`)} error={errors.employment?.[i]?.title?.message} />
              <Input label="Start (YYYY-MM)" {...register(`employment.${i}.start_date`)} error={errors.employment?.[i]?.start_date?.message} />
              <Input label="End (YYYY-MM)" {...register(`employment.${i}.end_date`)} error={errors.employment?.[i]?.end_date?.message} />
              <Input label="Location" {...register(`employment.${i}.location`)} />
              <label className="flex items-center gap-2 pt-6 text-sm"><input type="checkbox" {...register(`employment.${i}.is_current`)} /> I currently work here</label>
            </div>
            <Textarea label="Description" rows={2} {...register(`employment.${i}.description`)} />
            <Textarea label="Achievements (one per line)" rows={3} {...register(`employment.${i}.achievements`)} hint="Real, factual achievements only." />
            <Button variant="ghost" size="sm" onClick={() => emp.remove(i)}><Trash2 className="h-4 w-4" aria-hidden /> Remove role {i + 1}</Button>
          </fieldset>
        ))}
      </Section>

      <Section title="Education" addLabel="Add education" onAdd={() => edu.append({ institution: "", degree: "", field_of_study: "", start_date: "", end_date: "", description: "" })}>
        {edu.fields.length === 0 && <p className="text-sm text-slate-500">No education added yet.</p>}
        {edu.fields.map((f, i) => (
          <fieldset key={f.id} className="grid gap-3 rounded-lg border border-slate-200 p-4 sm:grid-cols-2">
            <legend className="px-1 text-sm font-medium text-slate-600">Education {i + 1}</legend>
            <Input label="Institution *" {...register(`education.${i}.institution`)} error={errors.education?.[i]?.institution?.message} />
            <Input label="Degree" {...register(`education.${i}.degree`)} />
            <Input label="Field of study" {...register(`education.${i}.field_of_study`)} />
            <div className="grid grid-cols-2 gap-3">
              <Input label="Start" {...register(`education.${i}.start_date`)} error={errors.education?.[i]?.start_date?.message} />
              <Input label="End" {...register(`education.${i}.end_date`)} error={errors.education?.[i]?.end_date?.message} />
            </div>
            <Button variant="ghost" size="sm" className="w-fit" onClick={() => edu.remove(i)}><Trash2 className="h-4 w-4" aria-hidden /> Remove education {i + 1}</Button>
          </fieldset>
        ))}
      </Section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Certifications" addLabel="Add" onAdd={() => cert.append({ name: "", issuer: "", issue_date: "" })}>
          {cert.fields.length === 0 && <p className="text-sm text-slate-500">None added.</p>}
          {cert.fields.map((f, i) => (
            <div key={f.id} className="space-y-2 rounded-lg border border-slate-200 p-3">
              <Input label="Certification *" {...register(`certifications.${i}.name`)} error={errors.certifications?.[i]?.name?.message} />
              <div className="grid grid-cols-2 gap-2"><Input label="Issuer" {...register(`certifications.${i}.issuer`)} /><Input label="Date" {...register(`certifications.${i}.issue_date`)} error={errors.certifications?.[i]?.issue_date?.message} /></div>
              <Button variant="ghost" size="sm" onClick={() => cert.remove(i)}><Trash2 className="h-4 w-4" aria-hidden /> Remove certification {i + 1}</Button>
            </div>
          ))}
        </Section>
        <Section title="Languages" addLabel="Add" onAdd={() => lang.append({ language: "", proficiency: "" })}>
          {lang.fields.length === 0 && <p className="text-sm text-slate-500">None added.</p>}
          {lang.fields.map((f, i) => (
            <div key={f.id} className="grid grid-cols-[1fr_1fr_auto] items-end gap-2">
              <Input label="Language *" {...register(`languages.${i}.language`)} error={errors.languages?.[i]?.language?.message} />
              <Input label="Proficiency" {...register(`languages.${i}.proficiency`)} />
              <Button variant="ghost" size="sm" aria-label={`Remove language ${i + 1}`} onClick={() => lang.remove(i)}><Trash2 className="h-4 w-4" /></Button>
            </div>
          ))}
        </Section>
      </div>

      <Card>
        <CardHeader title="Job preferences" />
        <CardBody className="grid gap-4 sm:grid-cols-2">
          <Input label="Salary expectation (min)" inputMode="numeric" {...register("salary_min")} error={errors.salary_min?.message} />
          <Input label="Salary expectation (max)" inputMode="numeric" {...register("salary_max")} error={errors.salary_max?.message} />
          <Select label="Currency" {...register("salary_currency")}>{["USD", "EUR", "GBP", "KES"].map((c) => <option key={c}>{c}</option>)}</Select>
          <Input label="Preferred employment types" {...register("employment_types")} hint="e.g. full-time, contract" />
          <Input label="Preferred locations" {...register("preferred_locations")} hint="Comma-separated" />
          <Input label="Notice period" {...register("notice_period")} />
          <Input label="Available from" {...register("available_from")} hint="e.g. Immediately, 2026-12-01" />
          <fieldset className="flex flex-wrap items-center gap-4 text-sm"><legend className="mb-1 font-medium text-slate-700">Work mode</legend>
            <label className="flex items-center gap-2"><input type="checkbox" {...register("work_remote")} /> Remote</label>
            <label className="flex items-center gap-2"><input type="checkbox" {...register("work_hybrid")} /> Hybrid</label>
            <label className="flex items-center gap-2"><input type="checkbox" {...register("work_onsite")} /> On-site</label>
          </fieldset>
          <div className="sm:col-span-2"><Input label="Work authorization (optional, verified by you)" {...register("work_authorization")} hint="Only offered for your review on matching questions; it is never auto-filled." /></div>
        </CardBody>
      </Card>

      <div className="flex justify-between">
        <Button variant="danger" disabled={!profile} onClick={() => setConfirmDelete(true)}>Delete profile</Button>
        <Button type="submit" loading={save.isPending} disabled={!isDirty && !imported}>Save profile</Button>
      </div>
      <ConfirmDialog open={confirmDelete} danger title="Delete your profile?" confirmLabel="Delete profile" loading={remove.isPending}
        description="This permanently removes your profile (skills, experience, education) together with all generated CVs, cover letters, uploaded documents and job match scores. Your application tracker entries are kept." onConfirm={() => remove.mutate()} onCancel={() => setConfirmDelete(false)} />
    </form>
  );
}
