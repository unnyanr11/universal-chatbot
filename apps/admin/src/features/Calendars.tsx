import { useEffect, useState } from "react";
import { client } from "../model";
import { ErrorNotice, useResource, useTask } from "./shared";
type Policy = {
  opening_hours: Record<string, [string, string][]>;
  holidays: string[];
  buffer_before_minutes: number;
  buffer_after_minutes: number;
  lead_time_minutes: number;
  cancellation_cutoff_minutes: number;
  booking_window_days: number;
};
const defaultPolicy: Policy = {
  opening_hours: {
    "0": [
      ["09:00", "12:00"],
      ["13:00", "17:00"],
    ],
    "1": [
      ["09:00", "12:00"],
      ["13:00", "17:00"],
    ],
    "2": [
      ["09:00", "12:00"],
      ["13:00", "17:00"],
    ],
    "3": [
      ["09:00", "12:00"],
      ["13:00", "17:00"],
    ],
    "4": [
      ["09:00", "12:00"],
      ["13:00", "17:00"],
    ],
  },
  holidays: [],
  buffer_before_minutes: 0,
  buffer_after_minutes: 0,
  lead_time_minutes: 60,
  cancellation_cutoff_minutes: 60,
  booking_window_days: 30,
};
export function Calendars({
  project,
  onChanged,
}: {
  project: string;
  onChanged: () => void;
}) {
  const root = `/v1/projects/${project}`;
  const [tick, setTick] = useState(0),
    [staffName, setStaffName] = useState(""),
    [staff, setStaff] = useState(""),
    [name, setName] = useState(""),
    [duration, setDuration] = useState(30),
    [zone, setZone] = useState("Asia/Kolkata"),
    [location, setLocation] = useState("Service desk"),
    [service, setService] = useState(""),
    [policyText, setPolicyText] = useState(
      JSON.stringify(defaultPolicy, null, 2),
    ),
    [day, setDay] = useState(
      new Date(Date.now() + 86400000).toISOString().slice(0, 10),
    ),
    [days, setDays] = useState(7),
    [notice, setNotice] = useState("");
  const job = useTask();
  const people = useResource<{ items: { id: string; name: string }[] }>(
      root + "/staff",
      tick,
    ),
    services = useResource<{
      items: { id: string; name: string; timezone: string }[];
    }>(root + "/services", tick),
    policy = useResource<{ revision: number; policy: Policy | null }>(
      service ? root + `/services/${service}/policy` : "",
      tick,
    );
  useEffect(() => {
    if (policy.data?.policy)
      setPolicyText(JSON.stringify(policy.data.policy, null, 2));
  }, [policy.data]);
  return (
    <>
      <ErrorNotice
        error={job.error || people.error || services.error || policy.error}
      />
      {notice && (
        <p role="status" className="notice">
          {notice}
        </p>
      )}
      <div className="booking-grid">
        <section className="panel">
          <h2>Staff and service setup</h2>
          <p className="muted">
            Managed services share staff capacity across calendars. The legacy
            seeded fixed-slot services remain available separately.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void job.task(async () => {
                await client.request(root + "/staff", {
                  method: "POST",
                  body: JSON.stringify({ name: staffName }),
                });
                setStaffName("");
                setTick((v) => v + 1);
              });
            }}
          >
            <label>
              Staff name
              <input
                value={staffName}
                onChange={(e) => setStaffName(e.target.value)}
                required
              />
            </label>
            <button disabled={job.busy}>Add staff member</button>
          </form>
          <hr />
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void job.task(async () => {
                const result = await client.request<{ id: string }>(
                  root + "/services",
                  {
                    method: "POST",
                    body: JSON.stringify({
                      name,
                      staff_id: staff,
                      duration_minutes: duration,
                      timezone: zone,
                      location,
                      policy: defaultPolicy,
                    }),
                  },
                );
                setService(result.id);
                setTick((v) => v + 1);
                onChanged();
                setNotice(
                  "Managed service created. Generate availability dates to make it bookable.",
                );
              });
            }}
          >
            <label>
              Service name
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </label>
            <label>
              Assigned staff
              <select
                aria-label="Assigned staff"
                value={staff}
                onChange={(e) => setStaff(e.target.value)}
                required
              >
                <option value="">Choose staff</option>
                {people.data?.items.map((p) => (
                  <option value={p.id} key={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Duration in minutes
              <input
                type="number"
                min={5}
                max={240}
                value={duration}
                onChange={(e) => setDuration(Number(e.target.value))}
              />
            </label>
            <label>
              Business timezone
              <input
                value={zone}
                onChange={(e) => setZone(e.target.value)}
                required
              />
            </label>
            <label>
              Location
              <input
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                required
              />
            </label>
            <button className="primary" disabled={job.busy}>
              Create managed service
            </button>
          </form>
        </section>
        <section className="panel">
          <h2>Calendar policy</h2>
          <label>
            Service calendar
            <select
              aria-label="Service calendar"
              value={service}
              onChange={(e) => {
                setService(e.target.value);
                setNotice("");
              }}
            >
              <option value="">Choose a service</option>
              {services.data?.items.map((s) => (
                <option value={s.id} key={s.id}>
                  {s.name} · {s.timezone}
                </option>
              ))}
            </select>
          </label>
          {service && policy.data?.policy === null ? (
            <p className="muted">
              This is a legacy fixed-slot service. Create a managed service to
              configure staff, buffers, opening hours and holidays.
            </p>
          ) : service && policy.data?.policy ? (
            <>
              <p className="muted">
                Opening-hour keys are 0 (Monday) through 6 (Sunday). Split
                periods define breaks. Ambiguous or missing DST periods are
                skipped. Capacity is one appointment per assigned staff member.
              </p>
              <label>
                Policy JSON
                <textarea
                  className="policy-editor"
                  value={policyText}
                  onChange={(e) => setPolicyText(e.target.value)}
                  rows={18}
                />
              </label>
              <button
                disabled={job.busy}
                onClick={() =>
                  job.task(async () => {
                    await client.request(root + `/services/${service}/policy`, {
                      method: "PUT",
                      body: JSON.stringify({
                        revision: policy.data!.revision,
                        policy: JSON.parse(policyText),
                      }),
                    });
                    setTick((v) => v + 1);
                    setNotice(
                      "Policy saved. Pending approvals under the old policy are invalid. Regenerate dates to publish new availability.",
                    );
                  })
                }
              >
                Save calendar policy
              </button>
              <h3>Generate available slots</h3>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void job.task(async () => {
                    const result = await client.request<{
                      created: number;
                      skipped_dst_periods: number;
                    }>(root + `/services/${service}/generate-slots`, {
                      method: "POST",
                      body: JSON.stringify({ start_date: day, days }),
                    });
                    setNotice(
                      `Generated ${result.created} slots; skipped ${result.skipped_dst_periods} ambiguous/missing DST periods.`,
                    );
                    onChanged();
                  });
                }}
              >
                <label>
                  Start date
                  <input
                    type="date"
                    value={day}
                    onChange={(e) => setDay(e.target.value)}
                    required
                  />
                </label>
                <label>
                  Days
                  <input
                    type="number"
                    min={1}
                    max={30}
                    value={days}
                    onChange={(e) => setDays(Number(e.target.value))}
                  />
                </label>
                <button className="primary" disabled={job.busy}>
                  Generate availability
                </button>
              </form>
            </>
          ) : (
            <p className="empty">
              Choose a managed service to edit its policy.
            </p>
          )}
        </section>
      </div>
    </>
  );
}
