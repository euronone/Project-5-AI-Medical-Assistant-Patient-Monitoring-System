"use client";

import { useCallback, useEffect, useState } from "react";
import apiClient from "@/lib/api-client";
import type { User } from "@/types/auth";

interface Appointment {
  id: string;
  patient_id: string;
  doctor_id: string;
  doctor_name?: string;
  doctor?: {
    first_name?: string;
    last_name?: string;
    name?: string;
    specialization?: string;
  };
  appointment_type: string;
  status: string;
  scheduled_at: string;
  duration_minutes: number;
  reason: string | null;
  notes: string | null;
  created_at: string;
}

interface DoctorOption {
  user_id: string;
  first_name: string | null;
  last_name: string | null;
  specialization: string;
  department: string | null;
}

interface AvailabilitySlot {
  start: string;
  end: string;
}

const typeBadge: Record<string, string> = {
  in_person: "bg-blue-100 text-blue-700",
  telemedicine: "bg-purple-100 text-purple-700",
  follow_up: "bg-teal-100 text-teal-700",
  emergency: "bg-red-100 text-red-700",
};

const statusBadge: Record<string, string> = {
  scheduled: "bg-blue-100 text-blue-700",
  confirmed: "bg-green-100 text-green-700",
  in_progress: "bg-amber-100 text-amber-700",
  completed: "bg-gray-100 text-gray-700",
  cancelled: "bg-red-100 text-red-700",
  no_show: "bg-red-100 text-red-700",
};

function getStoredUser(): User | null {
  const raw = localStorage.getItem("user");
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

function doctorLabel(d: DoctorOption): string {
  const fn = d.first_name?.trim() || "";
  const ln = d.last_name?.trim() || "";
  const name = [fn, ln].filter(Boolean).join(" ");
  return name ? `Dr. ${name}` : `Provider (${d.specialization})`;
}

function parseApiError(data: unknown): string | null {
  if (!data || typeof data !== "object" || !("error" in data)) return null;
  const err = (data as { error: Record<string, unknown> }).error;
  if (typeof err.message === "string") return err.message;
  if (Array.isArray(err.details)) {
    return (err.details as { msg?: string }[])
      .map((x) => x.msg)
      .filter(Boolean)
      .join(" ");
  }
  return null;
}

export default function AppointmentsPage() {
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [doctors, setDoctors] = useState<DoctorOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [doctorsLoading, setDoctorsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [bookDoctorId, setBookDoctorId] = useState("");
  const [bookDate, setBookDate] = useState("");
  const [slots, setSlots] = useState<AvailabilitySlot[]>([]);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [selectedSlotStart, setSelectedSlotStart] = useState<string | null>(null);
  const [bookManualTime, setBookManualTime] = useState("");
  const [bookType, setBookType] = useState("in_person");
  const [bookReason, setBookReason] = useState("");
  const [bookNotes, setBookNotes] = useState("");
  const [booking, setBooking] = useState(false);
  const [bookMessage, setBookMessage] = useState<string | null>(null);
  const [bookError, setBookError] = useState<string | null>(null);

  const fetchAppointments = useCallback(async () => {
    try {
      const res = await apiClient.get("/appointments");
      setError(null);
      const data = res.data?.appointments ?? res.data;
      setAppointments(Array.isArray(data) ? data : []);
    } catch (err: unknown) {
      const status =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { status?: number } }).response?.status
          : undefined;
      if (status === 404) {
        setAppointments([]);
      } else {
        setError("Failed to load appointments.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchDoctors = useCallback(async () => {
    try {
      const res = await apiClient.get<DoctorOption[]>("/doctors");
      const list = Array.isArray(res.data) ? res.data : [];
      setDoctors(
        list.map((d) => ({
          user_id: d.user_id,
          first_name: d.first_name ?? null,
          last_name: d.last_name ?? null,
          specialization: d.specialization,
          department: d.department ?? null,
        }))
      );
    } catch {
      setDoctors([]);
    } finally {
      setDoctorsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAppointments();
    fetchDoctors();
  }, [fetchAppointments, fetchDoctors]);

  useEffect(() => {
    if (!bookDoctorId || !bookDate) {
      setSlots([]);
      setSelectedSlotStart(null);
      return;
    }

    const load = async () => {
      setSlotsLoading(true);
      setSelectedSlotStart(null);
      setBookManualTime("");
      setBookError(null);
      try {
        const dayIso = new Date(`${bookDate}T12:00:00.000Z`).toISOString();
        const res = await apiClient.get<{
          available_slots: AvailabilitySlot[];
        }>(`/appointments/availability/${bookDoctorId}`, { params: { date: dayIso } });
        setSlots(res.data?.available_slots ?? []);
      } catch {
        setSlots([]);
        setBookError("Could not load available times for that day.");
      } finally {
        setSlotsLoading(false);
      }
    };

    void load();
  }, [bookDoctorId, bookDate]);

  const handleBook = async (e: React.FormEvent) => {
    e.preventDefault();
    setBookError(null);
    setBookMessage(null);

    const user = getStoredUser();
    if (!user?.id) {
      setBookError("Please sign in again.");
      return;
    }
    let scheduledAt: string;
    if (selectedSlotStart) {
      scheduledAt = selectedSlotStart;
    } else if (bookDate && bookManualTime) {
      const local = new Date(`${bookDate}T${bookManualTime}:00`);
      if (Number.isNaN(local.getTime())) {
        setBookError("Invalid date or time.");
        return;
      }
      if (local.getTime() < Date.now()) {
        setBookError("Choose a date and time in the future.");
        return;
      }
      scheduledAt = local.toISOString();
    } else {
      setBookError("Select a suggested time, or set both date and time below.");
      return;
    }

    setBooking(true);
    try {
      const res = await apiClient.post<
        Appointment & {
          confirmation_email_sent?: boolean;
          confirmation_emails?: { patient?: boolean; doctor?: boolean };
          email_provider?: { configured?: boolean; primary?: string };
        }
      >("/appointments", {
        patient_id: user.id,
        doctor_id: bookDoctorId,
        appointment_type: bookType,
        scheduled_at: scheduledAt,
        duration_minutes: 30,
        reason: bookReason.trim() || undefined,
        notes: bookNotes.trim() || undefined,
      });
      const ce = res.data?.confirmation_emails;
      const p = Boolean(ce?.patient ?? res.data?.confirmation_email_sent);
      const d = Boolean(ce?.doctor);
      const provider = res.data?.email_provider;
      const providerName =
        provider?.primary && provider.primary !== "none"
          ? String(provider.primary).toUpperCase()
          : "email provider";
      if (p && d) {
        setBookMessage("Appointment booked. Confirmation emails were sent to you and your provider.");
      } else if (p) {
        setBookMessage(
          "Appointment booked. Confirmation was sent to your email. The provider email could not be sent (check their account or mail configuration)."
        );
      } else if (d) {
        setBookMessage(
          "Appointment booked. Provider was notified by email; your confirmation could not be sent. Check mail settings."
        );
      } else {
        if (provider?.configured) {
          setBookMessage(
            `Appointment booked. Email delivery failed via ${providerName}. Check provider/API/domain verification and backend logs.`
          );
        } else {
          setBookMessage(
            "Appointment booked. Confirmation emails were not sent (configure Resend, SendGrid, or SMTP on the server)."
          );
        }
      }
      setBookReason("");
      setBookNotes("");
      setSelectedSlotStart(null);
      setBookManualTime("");
      await fetchAppointments();
    } catch (err: unknown) {
      let msg = "Booking failed.";
      if (
        err &&
        typeof err === "object" &&
        "response" in err &&
        (err as { response?: { data?: unknown } }).response?.data
      ) {
        const parsed = parseApiError((err as { response: { data: unknown } }).response.data);
        if (parsed) msg = parsed;
      }
      setBookError(msg);
    } finally {
      setBooking(false);
    }
  };

  const now = new Date();
  const upcoming = appointments.filter(
    (a) =>
      new Date(a.scheduled_at) >= now &&
      !["completed", "cancelled", "no_show"].includes(a.status)
  );
  const past = appointments.filter(
    (a) =>
      new Date(a.scheduled_at) < now ||
      ["completed", "cancelled", "no_show"].includes(a.status)
  );

  const getDoctorName = (a: Appointment): string => {
    if (a.doctor_name) return a.doctor_name;
    if (a.doctor) {
      if (a.doctor.name) return a.doctor.name;
      if (a.doctor.first_name)
        return `Dr. ${a.doctor.first_name} ${a.doctor.last_name ?? ""}`.trim();
    }
    return "Provider";
  };

  const formatDateTime = (dt: string): string => {
    const d = new Date(dt);
    return d.toLocaleDateString("en-US", {
      weekday: "short",
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  };

  const formatSlotLabel = (iso: string): string => {
    const d = new Date(iso);
    return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  };

  const minBookDate = new Date().toISOString().slice(0, 10);

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Appointments</h1>
          <p className="mt-1 text-muted-foreground">Book visits and view your schedule.</p>
        </div>
        <div className="text-sm text-muted-foreground">
          {upcoming.length} upcoming
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
        <form onSubmit={(e) => void handleBook(e)} className="space-y-4">
          {bookMessage && (
            <p className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-800 dark:bg-green-950/40 dark:text-green-200">
              {bookMessage}
            </p>
          )}
          {bookError && (
            <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{bookError}</p>
          )}

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <label htmlFor="provider" className="text-sm font-medium text-foreground">
                Provider
              </label>
              <select
                id="provider"
                value={bookDoctorId}
                onChange={(e) => setBookDoctorId(e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                disabled={doctorsLoading}
              >
                <option value="">
                  {doctorsLoading ? "Loading providers…" : "Select a doctor"}
                </option>
                {doctors.map((d) => (
                  <option key={d.user_id} value={d.user_id}>
                    {doctorLabel(d)} — {d.specialization}
                    {d.department ? ` (${d.department})` : ""}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <label htmlFor="appt-date" className="text-sm font-medium text-foreground">
                Date
              </label>
              <input
                id="appt-date"
                type="date"
                min={minBookDate}
                value={bookDate}
                onChange={(e) => {
                  setBookDate(e.target.value);
                  setSelectedSlotStart(null);
                }}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label htmlFor="appt-time" className="text-sm font-medium text-foreground">
              Time
            </label>
            <input
              id="appt-time"
              type="time"
              step={1800}
              value={bookManualTime}
              onChange={(e) => {
                setBookManualTime(e.target.value);
                setSelectedSlotStart(null);
              }}
              disabled={!bookDate}
              className="w-full max-w-xs rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
            />
            <p className="text-xs text-muted-foreground">
              Used when you do not pick a suggested slot. Must be on the selected date and in the future.
            </p>
          </div>

          <div className="space-y-2">
            <span className="text-sm font-medium text-foreground">Suggested times</span>
            {!bookDoctorId || !bookDate ? (
              <p className="text-sm text-muted-foreground">Choose a provider and date to see slots.</p>
            ) : slotsLoading ? (
              <p className="text-sm text-muted-foreground">Loading slots…</p>
            ) : slots.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No open slots that day. Try another date.
              </p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {slots.map((s) => {
                  const active = selectedSlotStart === s.start;
                  return (
                    <button
                      key={s.start}
                      type="button"
                      onClick={() => {
                        setSelectedSlotStart(s.start);
                        const d = new Date(s.start);
                        const hh = String(d.getHours()).padStart(2, "0");
                        const mm = String(d.getMinutes()).padStart(2, "0");
                        setBookManualTime(`${hh}:${mm}`);
                      }}
                      className={`rounded-md border px-3 py-1.5 text-sm transition-colors ${
                        active
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-border bg-background hover:bg-muted/50"
                      }`}
                    >
                      {formatSlotLabel(s.start)}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <label htmlFor="appt-type" className="text-sm font-medium text-foreground">
                Visit type
              </label>
              <select
                id="appt-type"
                value={bookType}
                onChange={(e) => setBookType(e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="in_person">In person</option>
                <option value="telemedicine">Telemedicine</option>
                <option value="follow_up">Follow-up</option>
                <option value="emergency">Urgent / same-day</option>
              </select>
            </div>
            <div className="space-y-2">
              <label htmlFor="appt-reason" className="text-sm font-medium text-foreground">
                Reason <span className="font-normal text-muted-foreground">(optional)</span>
              </label>
              <input
                id="appt-reason"
                type="text"
                value={bookReason}
                onChange={(e) => setBookReason(e.target.value)}
                placeholder="e.g. Annual checkup"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label htmlFor="appt-notes" className="text-sm font-medium text-foreground">
              Notes for provider <span className="font-normal text-muted-foreground">(optional)</span>
            </label>
            <textarea
              id="appt-notes"
              value={bookNotes}
              onChange={(e) => setBookNotes(e.target.value)}
              rows={2}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          <button
            type="submit"
            disabled={
              booking ||
              !bookDoctorId ||
              !bookDate ||
              (!selectedSlotStart && !bookManualTime)
            }
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {booking ? "Booking…" : "Confirm booking"}
          </button>
        </form>
      </div>

      {loading ? (
        <div className="rounded-lg border border-border bg-card p-12 text-center">
          <p className="text-sm text-muted-foreground">Loading appointments...</p>
        </div>
      ) : error ? (
        <div className="rounded-lg border border-border bg-card p-12 text-center">
          <p className="text-sm text-destructive">{error}</p>
        </div>
      ) : appointments.length === 0 ? (
        <div className="grid gap-6 md:grid-cols-2">
          <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-foreground">Upcoming</h2>
            <p className="mt-4 text-sm text-muted-foreground">
              No upcoming appointments yet. Use the form above to book with a listed provider.
            </p>
          </div>
          <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-foreground">Past Appointments</h2>
            <p className="mt-4 text-sm text-muted-foreground">
              Your appointment history will appear here.
            </p>
          </div>
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <div>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              Upcoming ({upcoming.length})
            </h2>
            {upcoming.length === 0 ? (
              <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
                <p className="text-sm text-muted-foreground">No upcoming appointments scheduled.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {upcoming.map((appt) => (
                  <AppointmentCard
                    key={appt.id}
                    appt={appt}
                    doctorName={getDoctorName(appt)}
                    formatDateTime={formatDateTime}
                  />
                ))}
              </div>
            )}
          </div>

          <div>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              Past ({past.length})
            </h2>
            {past.length === 0 ? (
              <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
                <p className="text-sm text-muted-foreground">No past appointments found.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {past.map((appt) => (
                  <AppointmentCard
                    key={appt.id}
                    appt={appt}
                    doctorName={getDoctorName(appt)}
                    formatDateTime={formatDateTime}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function AppointmentCard({
  appt,
  doctorName,
  formatDateTime,
}: {
  appt: Appointment;
  doctorName: string;
  formatDateTime: (dt: string) => string;
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-sm font-semibold text-foreground">{doctorName}</h3>
          {appt.doctor?.specialization && (
            <p className="text-xs text-muted-foreground">{appt.doctor.specialization}</p>
          )}
        </div>
        <div className="flex gap-2">
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
              typeBadge[appt.appointment_type] ?? "bg-gray-100 text-gray-700"
            }`}
          >
            {appt.appointment_type.replace("_", " ")}
          </span>
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
              statusBadge[appt.status] ?? "bg-gray-100 text-gray-700"
            }`}
          >
            {appt.status.replace("_", " ")}
          </span>
        </div>
      </div>

      <div className="mt-3 space-y-1 text-sm">
        <div className="flex items-center gap-2 text-muted-foreground">
          <span className="font-medium text-foreground">
            {formatDateTime(appt.scheduled_at)}
          </span>
        </div>
        <p className="text-muted-foreground">
          Duration: {appt.duration_minutes} minutes
        </p>
        {appt.reason && (
          <p className="text-muted-foreground">
            <span className="font-medium text-foreground">Reason:</span> {appt.reason}
          </p>
        )}
        {appt.notes && (
          <p className="text-xs text-muted-foreground mt-2 italic">{appt.notes}</p>
        )}
      </div>

      {appt.appointment_type === "telemedicine" &&
        ["scheduled", "confirmed"].includes(appt.status) && (
          <div className="mt-3">
            <span className="inline-flex items-center rounded-md bg-purple-50 px-3 py-1 text-xs font-medium text-purple-700 border border-purple-200">
              Video call link will be available when the session starts
            </span>
          </div>
        )}
    </div>
  );
}
