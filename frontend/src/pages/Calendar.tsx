import { useState, useEffect } from 'react';
import { CalendarDays, Plus, Clock, Trash2, Pencil, X, Loader2 } from 'lucide-react';
import { api, type CalendarEvent } from '../services/api';
import { MobileHeader } from '../components/MobileHeader';

export function Calendar() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editingEvent, setEditingEvent] = useState<CalendarEvent | null>(null);
  const [createSuccess, setCreateSuccess] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [allDay, setAllDay] = useState(false);

  const loadEvents = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await api.getCalendarEvents();
      setEvents(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load events');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEvents();
  }, []);

  const handleCreate = async () => {
    if (!title.trim() || !startTime) return;
    try {
      const payload = {
        title: title.trim(),
        ...(description.trim() ? { description: description.trim() } : {}),
        start_time: new Date(startTime).toISOString(),
        ...(endTime.trim() ? { end_time: new Date(endTime).toISOString() } : {}),
        all_day: false,
      };
      await api.createCalendarEvent(payload);
      await loadEvents();
      setShowForm(false);
      setTitle('');
      setDescription('');
      setStartTime('');
      setEndTime('');
      setCreateSuccess(true);
      setTimeout(() => setCreateSuccess(false), 3000);
    } catch {
      /* leave form open on error */
    }
  };

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  };

  const toDatetimeLocal = (iso: string) => {
    const d = new Date(iso);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };

  const handleDelete = async (event: CalendarEvent) => {
    const message = event.title.trim() ? `Delete "${event.title}"?` : 'Delete this event?';
    if (!window.confirm(message)) return;
    try {
      await api.deleteCalendarEvent(event.id);
      await loadEvents();
    } catch {
      /* ignore */
    }
  };

  const openEdit = (event: CalendarEvent) => {
    setEditingEvent(event);
    setTitle(event.title);
    setDescription(event.description ?? '');
    setStartTime(toDatetimeLocal(event.start_time));
    setEndTime(event.end_time ? toDatetimeLocal(event.end_time) : '');
    setAllDay(event.all_day);
  };

  const handleUpdate = async () => {
    if (!editingEvent || !title.trim() || !startTime) return;
    try {
      await api.updateCalendarEvent(editingEvent.id, {
        title: title.trim(),
        description: description.trim() || undefined,
        start_time: new Date(startTime).toISOString(),
        end_time: endTime.trim() ? new Date(endTime).toISOString() : undefined,
        all_day: allDay,
      });
      setEditingEvent(null);
      setTitle('');
      setDescription('');
      setStartTime('');
      setEndTime('');
      setAllDay(false);
      await loadEvents();
    } catch {
      /* leave modal open on error */
    }
  };

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <MobileHeader
        title="Calendar"
        rightAction={
          <button
            onClick={() => setShowForm(true)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] text-white text-sm font-medium transition-colors active:scale-[0.98]"
          >
            <Plus className="w-4 h-4" />
            New Event
          </button>
        }
      />
      <div className="p-4 md:p-6 max-w-4xl mx-auto flex-1 w-full">
      <div className="hidden md:flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <CalendarDays className="w-6 h-6 text-[var(--color-primary)]" />
          <h1 className="text-xl font-bold">Calendar</h1>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] text-white text-sm font-medium transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Event
        </button>
      </div>

      {createSuccess && (
        <p className="mb-4 text-sm text-[var(--color-primary)]" role="status">Event created.</p>
      )}

      {/* Create form */}
      {showForm && (
        <div className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold">New Event</h2>
            <button onClick={() => setShowForm(false)} className="p-1 rounded-lg hover:bg-[var(--color-surface-hover)]">
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="space-y-3">
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Event title"
              className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50"
              autoFocus
            />
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Description (optional)"
              className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50"
            />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-[var(--color-text-secondary)] mb-1">Start</label>
                <input
                  type="datetime-local"
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50"
                />
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-secondary)] mb-1">End</label>
                <input
                  type="datetime-local"
                  value={endTime}
                  onChange={(e) => setEndTime(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50"
                />
              </div>
            </div>
            <button
              onClick={handleCreate}
              className="px-4 py-2 rounded-lg bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] text-white text-sm font-medium"
            >
              Create Event
            </button>
          </div>
        </div>
      )}

      {/* Edit form */}
      {editingEvent && (
        <div className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold">Edit Event</h2>
            <button
              onClick={() => {
                setEditingEvent(null);
                setTitle('');
                setDescription('');
                setStartTime('');
                setEndTime('');
                setAllDay(false);
              }}
              className="p-1 rounded-lg hover:bg-[var(--color-surface-hover)]"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="space-y-3">
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Event title"
              className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50"
            />
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Description (optional)"
              className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50"
            />
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={allDay}
                onChange={(e) => setAllDay(e.target.checked)}
                className="rounded border-[var(--color-border)]"
              />
              All day
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-[var(--color-text-secondary)] mb-1">Start</label>
                <input
                  type="datetime-local"
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50"
                />
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-secondary)] mb-1">End</label>
                <input
                  type="datetime-local"
                  value={endTime}
                  onChange={(e) => setEndTime(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50"
                />
              </div>
            </div>
            <button
              onClick={handleUpdate}
              className="px-4 py-2 rounded-lg bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] text-white text-sm font-medium"
            >
              Save changes
            </button>
          </div>
        </div>
      )}

      {/* Events list */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-[var(--color-primary)]" />
        </div>
      ) : error ? (
        <div className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-8 text-center">
          <CalendarDays className="w-12 h-12 mx-auto mb-4 text-[var(--color-text-secondary)] opacity-30" />
          <p className="text-[var(--color-text-secondary)]">{error}</p>
          <p className="text-sm text-[var(--color-text-secondary)] mt-2 opacity-60">
            Try again later or create an event manually.
          </p>
          <button
            onClick={() => {
              setError('');
              setLoading(true);
              api.getCalendarEvents()
                .then((data) => setEvents(data))
                .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load events'))
                .finally(() => setLoading(false));
            }}
            className="mt-4 px-4 py-2 rounded-lg bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] text-white text-sm font-medium"
          >
            Retry
          </button>
        </div>
      ) : events.length === 0 ? (
        <div className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-8 text-center">
          <CalendarDays className="w-12 h-12 mx-auto mb-4 text-[var(--color-text-secondary)] opacity-30" />
          <p className="text-[var(--color-text-secondary)]">No upcoming events</p>
          <p className="text-sm text-[var(--color-text-secondary)] mt-1 opacity-60">
            Create an event or ask ARIM to schedule one in chat.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {events.map((event) => (
            <div
              key={event.id}
              className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-4 flex items-start gap-4 group hover:bg-[var(--color-surface-hover)] transition-colors active:scale-[0.99]"
            >
              <div className="w-12 h-12 rounded-xl bg-[var(--color-primary)]/10 flex flex-col items-center justify-center shrink-0">
                <span className="text-xs text-[var(--color-primary)] font-medium">
                  {new Date(event.start_time).toLocaleDateString('en-US', { month: 'short' })}
                </span>
                <span className="text-lg font-bold text-[var(--color-primary)] leading-none">
                  {new Date(event.start_time).getDate()}
                </span>
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="font-medium text-sm">{event.title}</h3>
                {event.description && (
                  <p className="text-xs text-[var(--color-text-secondary)] mt-0.5">{event.description}</p>
                )}
                <div className="flex items-center gap-1 mt-1.5 text-xs text-[var(--color-text-secondary)]">
                  <Clock className="w-3 h-3" />
                  {event.all_day ? 'All day' : `${formatTime(event.start_time)}${event.end_time ? ` - ${formatTime(event.end_time)}` : ''}`}
                </div>
              </div>
              <div className="flex items-center gap-1 shrink-0 mt-1 opacity-60 md:opacity-0 md:group-hover:opacity-100 transition-opacity">
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); openEdit(event); }}
                  className="p-1.5 rounded-lg hover:bg-[var(--color-surface-hover)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
                  aria-label={`Edit ${event.title}`}
                >
                  <Pencil className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); handleDelete(event); }}
                  className="p-1.5 rounded-lg hover:bg-[var(--color-surface-hover)] text-[var(--color-text-secondary)] hover:text-red-500"
                  aria-label={`Delete ${event.title}`}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
      </div>
    </div>
  );
}
