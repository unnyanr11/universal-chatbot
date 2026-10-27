import {
  AssistantClient,
  type Citation,
  type ChatActionReference,
} from "../../../packages/js-sdk/index";
export type Project = {
  id: string;
  name: string;
  environment: string;
  role?: string;
  organization_id?: string;
};
export type Assistant = {
  id: string;
  name: string;
  welcome_message: string;
  status: string;
};
export type Document = {
  id: string;
  title: string;
  status: string;
  error: string;
};
export type Service = {
  id: string;
  name: string;
  timezone: string;
  duration_minutes: number;
  location: string;
};
export type Slot = {
  staff?: string | null;
  slot_id: string;
  service: string;
  start_at: string;
  end_at: string;
  timezone: string;
  location: string;
};
export type Booking = Slot & { id: string; status: string; version: number };
export type Operation = {
  id: string;
  kind: string;
  state: string;
  booking_id: string;
  expires_at: number;
  error: string;
  preview: Slot | null;
  policy: string;
  notification: string;
};
export type Tool = {
  name: string;
  kind: string;
  status: string;
  description?: string;
  input_schema?: Record<string, unknown>;
  output_schema?: Record<string, unknown>;
};
export type ChatMessage = {
  action?: ChatActionReference | null;
  provisional?: boolean;
  mode?: string;
  role: string;
  text: string;
  citations?: Citation[];
};
export const client = new AssistantClient();
export const widget = new URLSearchParams(location.search).has("widget");
export function localTime(slot: Slot) {
  return (
    new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: slot.timezone,
    }).format(new Date(slot.start_at)) +
    " · " +
    slot.timezone
  );
}
