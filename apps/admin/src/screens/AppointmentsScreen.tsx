import { type StudioState } from "../useStudio";
import { client, localTime, widget, type Assistant } from "../model";
import { type Citation } from "../../../../packages/js-sdk/index";
export function AppointmentsScreen({ studio }: { studio: StudioState }) {
  const {
    error,
    setNotice,
    busy,
    services,
    bookings,
    slots,
    service,
    operation,
    setOperation,
    reschedule,
    setReschedule,
    chooseService,
    propose,
    confirmBooking,
  } = studio;
  return (
    <>
      <div className="section-heading">
        <div>
          <h2>Book with confidence.</h2>
          <p className="muted">
            Real local bookings · Capacity is checked again when you confirm.
          </p>
        </div>
        <span className="badge">In-app reminders only</span>
      </div>
      <div className="booking-grid">
        <section className="panel">
          <h3>
            {reschedule ? "Choose a replacement slot" : "Find an appointment"}
          </h3>
          {services.length === 0 && (
            <p className="muted">
              A workspace owner can add services, staff and availability in
              Calendars.
            </p>
          )}
          <label>
            Service
            <select
              aria-label="Service"
              value={service}
              onChange={(e) => chooseService(e.target.value)}
            >
              <option value="">Choose a service</option>
              {services.map((s) => (
                <option value={s.id} key={s.id}>
                  {s.name} · {s.duration_minutes} min
                </option>
              ))}
            </select>
          </label>
          <div className="slots">
            {slots.map((s) => (
              <button
                disabled={busy}
                key={s.slot_id}
                onClick={() =>
                  propose(
                    reschedule ? "reschedule" : "book",
                    s.slot_id,
                    reschedule,
                  )
                }
              >
                <strong>{localTime(s)}</strong>
                <small>{s.location}</small>
              </button>
            ))}
          </div>
          {service && slots.length === 0 && (
            <p className="muted">
              No available slots. Choose another service or ask a workspace
              owner to generate availability in Calendars.
            </p>
          )}
        </section>
        <section className="panel">
          <h3>Review and confirm</h3>
          {!operation ? (
            <div className="empty">
              <span>▦</span>
              <p>
                Choose a slot or manage an existing appointment.
                <br />A preview does not reserve capacity.
              </p>
            </div>
          ) : (
            <div className="receipt">
              <span className={"badge " + operation.state}>
                {operation.state.replaceAll("_", " ")}
              </span>
              <h2>
                {operation.kind === "cancel"
                  ? "Cancel appointment"
                  : operation.kind === "reschedule"
                    ? "Reschedule appointment"
                    : "Confirm appointment"}
              </h2>
              {operation.preview && (
                <>
                  <strong>{operation.preview.service}</strong>
                  <p>{localTime(operation.preview)}</p>
                  <p>{operation.preview.location}</p>
                  {operation.preview.staff && (
                    <p>Staff: {operation.preview.staff}</p>
                  )}
                </>
              )}
              <p className="fine">{operation.policy}</p>
              <p className="fine">{operation.notification}</p>
              {operation.error && <p className="error">{operation.error}</p>}
              {operation.state === "awaiting_confirmation" ? (
                <>
                  <p className="fine">
                    Approval expires{" "}
                    {new Date(operation.expires_at * 1000).toLocaleTimeString()}
                    .
                  </p>
                  <button
                    className="primary"
                    disabled={busy}
                    onClick={confirmBooking}
                  >
                    Confirm{" "}
                    {operation.kind === "cancel"
                      ? "cancellation"
                      : "appointment"}
                  </button>
                  <button onClick={() => setOperation(null)}>
                    Dismiss preview
                  </button>
                </>
              ) : (
                <p>Reference: {operation.booking_id || operation.id}</p>
              )}
            </div>
          )}
        </section>
      </div>
      <section className="panel">
        <h2>Your appointments</h2>
        {bookings.length === 0 && <p className="muted">No appointments yet.</p>}
        {bookings.map((b) => (
          <article className="booking-row" key={b.id}>
            <div className="grow">
              <strong>{b.service}</strong>
              <p>{localTime(b)}</p>
              <small>
                {b.location} · Reference {b.id.slice(0, 8)}
              </small>
            </div>
            <span className="badge">{b.status}</span>
            {b.status === "confirmed" && (
              <>
                <button
                  disabled={busy}
                  onClick={() => {
                    setReschedule(b.id);
                    setOperation(null);
                    setNotice(
                      "Choose a service and replacement slot. Your original remains booked until the replacement succeeds.",
                    );
                  }}
                >
                  Reschedule
                </button>
                <button
                  disabled={busy}
                  onClick={() => propose("cancel", "", b.id)}
                >
                  Cancel
                </button>
              </>
            )}
          </article>
        ))}
      </section>
    </>
  );
}
