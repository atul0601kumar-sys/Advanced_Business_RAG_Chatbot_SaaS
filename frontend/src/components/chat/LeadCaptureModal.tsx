"use client";

import { useEffect, useState } from "react";

type LeadCaptureModalProps = {
  open: boolean;
  scheduleCallEnabled: boolean;
  defaultMessage: string;
  requiredFields?: string[];
  onClose: () => void;
  onSubmit: (payload: {
    name: string;
    email: string;
    phone: string;
    company: string;
    useCase: string;
    message: string;
    scheduleCallRequested: boolean;
  }) => Promise<void>;
};

export function LeadCaptureModal({
  open,
  scheduleCallEnabled,
  defaultMessage,
  requiredFields = ["name", "email"],
  onClose,
  onSubmit,
}: LeadCaptureModalProps) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [company, setCompany] = useState("");
  const [useCase, setUseCase] = useState("general");
  const [message, setMessage] = useState(defaultMessage);
  const [scheduleCallRequested, setScheduleCallRequested] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const requiresName = requiredFields.includes("name");
  const requiresEmail = requiredFields.includes("email");

  useEffect(() => {
    setMessage(defaultMessage);
    setScheduleCallRequested(scheduleCallEnabled);
  }, [defaultMessage, open]);

  if (!open) {
    return null;
  }

  async function handleSubmit() {
    if ((requiresName && !name.trim()) || (requiresEmail && !email.trim())) {
      setError("Please fill in the required contact fields.");
      return;
    }
    setError("");
    setIsSubmitting(true);
    try {
      await onSubmit({
        name: name.trim(),
        email: email.trim(),
        phone: phone.trim(),
        company: company.trim(),
        useCase: useCase.trim(),
        message: message.trim(),
        scheduleCallRequested,
      });
      setName("");
      setEmail("");
      setPhone("");
      setCompany("");
      setUseCase("general");
      setMessage(defaultMessage);
      setScheduleCallRequested(false);
      onClose();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Could not submit your details.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4">
      <div className="w-full max-w-2xl rounded-[2rem] border border-white/10 bg-slate-950 p-6 text-white shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.35em] text-cyan-200/70">Human handoff</p>
            <h2 className="mt-3 text-3xl font-semibold">Talk to a human expert</h2>
            <p className="mt-3 text-sm text-slate-300">
              Share your details and we will route this conversation to the right teammate.
            </p>
          </div>
          <button
            aria-label="Close lead form"
            className="rounded-full border border-white/10 px-3 py-2 text-sm text-slate-300"
            onClick={onClose}
            type="button"
          >
            Close
          </button>
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <input
            className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none"
            onChange={(event) => setName(event.target.value)}
            placeholder={requiresName ? "Name *" : "Name"}
            value={name}
          />
          <input
            className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none"
            onChange={(event) => setEmail(event.target.value)}
            placeholder={requiresEmail ? "Email *" : "Email"}
            value={email}
          />
          <input
            className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none"
            onChange={(event) => setPhone(event.target.value)}
            placeholder="Phone"
            value={phone}
          />
          <input
            className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none"
            onChange={(event) => setCompany(event.target.value)}
            placeholder="Company"
            value={company}
          />
          <select
            className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none md:col-span-2"
            onChange={(event) => setUseCase(event.target.value)}
            value={useCase}
          >
            <option value="general">General inquiry</option>
            <option value="sales">Sales / pricing</option>
            <option value="support">Support</option>
            <option value="demo">Demo request</option>
          </select>
          <textarea
            className="min-h-32 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none md:col-span-2"
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Tell us what you need"
            value={message}
          />
        </div>

        {scheduleCallEnabled ? (
          <label className="mt-4 flex items-center gap-3 text-sm text-slate-300">
            <input
              checked={scheduleCallRequested}
              onChange={(event) => setScheduleCallRequested(event.target.checked)}
              type="checkbox"
            />
            Schedule a call instead of email follow-up
          </label>
        ) : null}

        {error ? <p className="mt-4 text-sm text-rose-300">{error}</p> : null}

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            className="rounded-full bg-white px-5 py-3 text-sm font-semibold text-slate-950 disabled:opacity-50"
            disabled={isSubmitting}
            onClick={() => void handleSubmit()}
            type="button"
          >
            {isSubmitting ? "Submitting..." : "Submit details"}
          </button>
          <button
            className="rounded-full border border-white/10 px-5 py-3 text-sm text-slate-300"
            onClick={onClose}
            type="button"
          >
            Maybe later
          </button>
        </div>
      </div>
    </div>
  );
}
