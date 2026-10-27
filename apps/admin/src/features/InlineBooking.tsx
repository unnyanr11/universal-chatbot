import { useState } from "react";
import { client, localTime, type Slot, type Operation } from "../model";
import { ErrorNotice, useResource, useTask } from "./shared";
import { type ChatActionReference } from "../../../../packages/js-sdk";
type Data = {
  services: { id: string; name: string }[];
  bookings: (Slot & { id: string; status: string })[];
  operation: Operation | null;
};
export function InlineBooking({ action }: { action: ChatActionReference }) {
  const root = `/v1/projects/${action.project_id}`;
  const [tick, setTick] = useState(0),
    [service, setService] = useState(""),
    [booking, setBooking] = useState("");
  const resource = useResource<Data>(root + "/chat-actions/" + action.id, tick);
  const slots = useResource<{ items: Slot[] }>(
    service ? root + `/services/${service}/slots` : "",
    tick,
  );
  const [receipt, setReceipt] = useState<Operation>();
  const job = useTask();
  const op = receipt ?? resource.data?.operation;
  return (
    <section className="inline-booking" aria-label="Appointment action">
      <h3>
        {action.kind === "book"
          ? "Choose your appointment"
          : action.kind === "reschedule"
            ? "Reschedule your appointment"
            : "Cancel your appointment"}
      </h3>
      <ErrorNotice error={job.error || resource.error || slots.error} />
      {op ? (
        <>
          <span className="badge">{op.state.replaceAll("_", " ")}</span>
          {op.preview && (
            <>
              <strong>{op.preview.service}</strong>
              <p>{localTime(op.preview)}</p>
              <p>
                {op.preview.location}
                {op.preview.staff ? " · " + op.preview.staff : ""}
              </p>
            </>
          )}
          <p className="fine">{op.policy}</p>
          <p className="fine">{op.notification}</p>
          {op.error && <p className="error">{op.error}</p>}
          {op.state === "awaiting_confirmation" && (
            <button
              className="primary"
              disabled={job.busy}
              onClick={() =>
                job.task(async () => {
                  setReceipt(
                    await client.request<Operation>(
                      root + `/operations/${op.id}/confirm`,
                      { method: "POST" },
                    ),
                  );
                  setTick((v) => v + 1);
                })
              }
            >
              Confirm{" "}
              {action.kind === "cancel" ? "cancellation" : "appointment"}
            </button>
          )}
          <button
            disabled={job.busy}
            onClick={() =>
              job.task(async () => {
                setReceipt(
                  await client.request<Operation>(
                    root + `/operations/${op.id}`,
                  ),
                );
              })
            }
          >
            Refresh receipt
          </button>
          {op.booking_id && <p className="fine">Reference: {op.booking_id}</p>}
          <p className="fine">
            To change the selected details, ask for a new action. Replaying this
            card cannot execute another booking.
          </p>
        </>
      ) : (
        <>
          {action.kind !== "book" && (
            <label>
              Your appointment
              <select
                aria-label="Chat appointment to change"
                value={booking}
                required
                onChange={(e) => setBooking(e.target.value)}
              >
                <option value="">Choose an appointment</option>
                {resource.data?.bookings
                  .filter((b) => b.status === "confirmed")
                  .map((b) => (
                    <option value={b.id} key={b.id}>
                      {b.service} · {localTime(b)}
                    </option>
                  ))}
              </select>
            </label>
          )}
          {action.kind !== "cancel" && (
            <>
              <label>
                Service
                <select
                  aria-label="Chat booking service"
                  value={service}
                  onChange={(e) => setService(e.target.value)}
                >
                  <option value="">Choose a service</option>
                  {resource.data?.services.map((s) => (
                    <option value={s.id} key={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </label>
              <p className="fine">
                Times are in the business timezone shown. Pick an exact
                date/time; relative or ambiguous dates are not guessed.
              </p>
              {slots.data?.items.slice(0, 20).map((slot) => (
                <button
                  className="slot-choice"
                  key={slot.slot_id}
                  disabled={
                    job.busy || (action.kind === "reschedule" && !booking)
                  }
                  onClick={() =>
                    job.task(async () => {
                      setReceipt(
                        await client.request<Operation>(
                          root + `/chat-actions/${action.id}/propose`,
                          {
                            method: "POST",
                            body: JSON.stringify({
                              slot_id: slot.slot_id,
                              booking_id: booking,
                            }),
                          },
                        ),
                      );
                    })
                  }
                >
                  {localTime(slot)}
                </button>
              ))}
            </>
          )}
          {action.kind === "cancel" && (
            <button
              disabled={!booking || job.busy}
              onClick={() =>
                job.task(async () => {
                  setReceipt(
                    await client.request<Operation>(
                      root + `/chat-actions/${action.id}/propose`,
                      {
                        method: "POST",
                        body: JSON.stringify({ booking_id: booking }),
                      },
                    ),
                  );
                })
              }
            >
              Preview cancellation
            </button>
          )}
        </>
      )}
    </section>
  );
}
