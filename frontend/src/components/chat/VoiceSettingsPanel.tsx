"use client";

import type { Dispatch, SetStateAction } from "react";

import type { ChatbotSettingsResponse } from "@/lib/settings";

type VoiceSettingsPanelProps = {
  draftSettings: ChatbotSettingsResponse;
  setDraftSettings: Dispatch<SetStateAction<ChatbotSettingsResponse | null>>;
};

export function VoiceSettingsPanel({
  draftSettings,
  setDraftSettings,
}: VoiceSettingsPanelProps) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="grid gap-3">
        <ToggleField
          label="Enable voice input"
          checked={draftSettings.voice.voice_input_enabled}
          onChange={(checked) =>
            updateDraft(setDraftSettings, (draft) => {
              draft.voice.voice_input_enabled = checked;
            })
          }
        />
        <ToggleField
          label="Enable voice output"
          checked={draftSettings.voice.voice_output_enabled}
          onChange={(checked) =>
            updateDraft(setDraftSettings, (draft) => {
              draft.voice.voice_output_enabled = checked;
            })
          }
        />
        <ToggleField
          label="Show transcript preview"
          checked={draftSettings.voice.transcript_preview_enabled}
          onChange={(checked) =>
            updateDraft(setDraftSettings, (draft) => {
              draft.voice.transcript_preview_enabled = checked;
            })
          }
        />
        <ToggleField
          label="Auto-read assistant responses"
          checked={draftSettings.voice.auto_read_assistant_responses}
          onChange={(checked) =>
            updateDraft(setDraftSettings, (draft) => {
              draft.voice.auto_read_assistant_responses = checked;
            })
          }
        />
      </div>
      <div className="grid gap-4">
        <TextField
          label="Voice style"
          value={draftSettings.voice.voice_style ?? ""}
          onChange={(value) =>
            updateDraft(setDraftSettings, (draft) => {
              draft.voice.voice_style = value || null;
            })
          }
        />
        <div className="rounded-3xl border border-cyan-400/20 bg-cyan-400/10 p-4 text-sm text-cyan-50">
          Browser speech is used first for low-latency demos. If browser support is missing, the app can fall back to the backend voice provider.
        </div>
      </div>
    </div>
  );
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="grid gap-2 text-sm text-slate-300">
      <span>{label}</span>
      <input className="rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 text-white outline-none" value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function ToggleField({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <label className="flex items-center gap-3 text-sm text-slate-300">
      <input checked={checked} onChange={(event) => onChange(event.target.checked)} type="checkbox" />
      <span>{label}</span>
    </label>
  );
}

function updateDraft(
  setDraft: Dispatch<SetStateAction<ChatbotSettingsResponse | null>>,
  mutator: (draft: ChatbotSettingsResponse) => void,
) {
  setDraft((current) => {
    if (!current) return current;
    const next = structuredClone(current);
    mutator(next);
    return next;
  });
}
