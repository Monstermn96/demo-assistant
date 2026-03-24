import { useState, useEffect, useCallback } from 'react';
import { StickyNote, Plus, Search, Trash2, Save, ArrowLeft, Pencil } from 'lucide-react';
import { api } from '../services/api';
import { MobileHeader } from '../components/MobileHeader';

interface NoteItem {
  id: number;
  title: string;
  content: string;
  created_at: string;
  updated_at: string;
}

type View = 'list' | 'edit' | 'detail';

export function Notes() {
  const [notes, setNotes] = useState<NoteItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [view, setView] = useState<View>('list');
  const [editId, setEditId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editContent, setEditContent] = useState('');
  const [selectedNote, setSelectedNote] = useState<NoteItem | null>(null);

  const fetchNotes = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getNotes();
      setNotes(data);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchNotes(); }, [fetchNotes]);

  const handleSearch = useCallback(async (query: string) => {
    setSearchQuery(query);
    if (!query.trim()) {
      fetchNotes();
      return;
    }
    try {
      const data = await api.searchNotes(query);
      setNotes(data);
    } catch {
      /* ignore */
    }
  }, [fetchNotes]);

  const handleNew = () => {
    setEditId(null);
    setEditTitle('');
    setEditContent('');
    setView('edit');
  };

  const handleEdit = (note: NoteItem) => {
    setEditId(note.id);
    setEditTitle(note.title);
    setEditContent(note.content);
    setView('edit');
  };

  const handleSave = async () => {
    if (!editTitle.trim()) return;
    try {
      if (editId) {
        await api.updateNote(editId, { title: editTitle, content: editContent });
      } else {
        await api.createNote(editTitle, editContent);
      }
      setView('list');
      fetchNotes();
    } catch {
      /* ignore */
    }
  };

  const handleDelete = async (noteId: number, e?: React.MouseEvent) => {
    e?.stopPropagation();
    try {
      await api.deleteNote(noteId);
      if (selectedNote?.id === noteId) {
        setSelectedNote(null);
        setView('list');
      }
      fetchNotes();
    } catch {
      /* ignore */
    }
  };

  const handleSelectNote = (note: NoteItem) => {
    setSelectedNote(note);
    setView('detail');
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) +
      ' ' + d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
  };

  if (view === 'detail' && selectedNote) {
    return (
      <div className="flex flex-col flex-1 min-h-0">
        <MobileHeader
          title={selectedNote.title}
          rightAction={
            <div className="flex items-center gap-1">
              <button
                onClick={() => handleEdit(selectedNote)}
                className="p-2 rounded-lg hover:bg-[var(--color-surface-hover)] text-[var(--color-text)] transition-colors active:scale-[0.98]"
                aria-label="Edit"
              >
                <Pencil className="w-4 h-4" />
              </button>
              <button
                onClick={() => handleDelete(selectedNote.id)}
                className="p-2 rounded-lg hover:bg-red-500/10 text-red-500 transition-colors active:scale-[0.98]"
                aria-label="Delete"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          }
        />
        <div className="p-4 md:p-6 max-w-4xl mx-auto flex-1 w-full">
        <div className="flex items-center gap-3 mb-6">
          <button
            onClick={() => setView('list')}
            className="p-2 rounded-lg hover:bg-[var(--color-surface-hover)] transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="text-xl font-bold flex-1 truncate hidden md:block">{selectedNote.title}</h1>
        </div>
        <div className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-6">
          <p className="text-xs text-[var(--color-text-secondary)] mb-4">
            Updated {formatDate(selectedNote.updated_at)}
          </p>
          <div className="whitespace-pre-wrap text-sm leading-relaxed">{selectedNote.content}</div>
        </div>
        </div>
      </div>
    );
  }

  if (view === 'edit') {
    return (
      <div className="flex flex-col flex-1 min-h-0">
        <MobileHeader title={editId ? 'Edit Note' : 'New Note'} />
        <div className="p-4 md:p-6 max-w-4xl mx-auto flex-1 w-full">
        <div className="flex items-center gap-3 mb-6">
          <button
            onClick={() => setView('list')}
            className="p-2 rounded-lg hover:bg-[var(--color-surface-hover)] transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="text-xl font-bold hidden md:block">{editId ? 'Edit Note' : 'New Note'}</h1>
        </div>
        <div className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-6">
          <input
            type="text"
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            placeholder="Title"
            className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] mb-3 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50"
            autoFocus
          />
          <textarea
            value={editContent}
            onChange={(e) => setEditContent(e.target.value)}
            placeholder="Write your note..."
            rows={12}
            className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] mb-4 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50"
          />
          <button
            onClick={handleSave}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] text-white text-sm font-medium transition-colors"
          >
            <Save className="w-4 h-4" />
            {editId ? 'Update Note' : 'Save Note'}
          </button>
        </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <MobileHeader
        title="Notes"
        rightAction={
          <button
            onClick={handleNew}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] text-white text-sm font-medium transition-colors active:scale-[0.98]"
          >
            <Plus className="w-4 h-4" />
            New Note
          </button>
        }
      />
      <div className="p-4 md:p-6 max-w-4xl mx-auto flex-1 w-full">
      <div className="hidden md:flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <StickyNote className="w-6 h-6 text-[var(--color-primary)]" />
          <h1 className="text-xl font-bold">Notes</h1>
        </div>
        <button
          onClick={handleNew}
          className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] text-white text-sm font-medium transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Note
        </button>
      </div>

      <div className="relative mb-6">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-text-secondary)]" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => handleSearch(e.target.value)}
          placeholder="Search notes..."
          className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50"
        />
      </div>

      {loading ? (
        <div className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-8 text-center">
          <p className="text-[var(--color-text-secondary)]">Loading notes...</p>
        </div>
      ) : notes.length === 0 ? (
        <div className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-8 text-center">
          <StickyNote className="w-12 h-12 mx-auto mb-4 text-[var(--color-text-secondary)] opacity-30" />
          <p className="text-[var(--color-text-secondary)]">
            {searchQuery ? 'No notes match your search' : 'No notes yet'}
          </p>
          <p className="text-sm text-[var(--color-text-secondary)] mt-1 opacity-60">
            {searchQuery ? 'Try a different query.' : 'Create a note or ask ARIM to save one in chat.'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {notes.map((note) => (
            <div
              key={note.id}
              className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-4 hover:bg-[var(--color-surface-hover)] cursor-pointer transition-colors group active:scale-[0.99]"
              onClick={() => handleSelectNote(note)}
            >
              <div className="flex items-start justify-between mb-2">
                <h3 className="font-medium text-sm truncate">{note.title}</h3>
                <button
                  onClick={(e) => handleDelete(note.id, e)}
                  className="p-1 rounded opacity-60 md:opacity-0 md:group-hover:opacity-60 hover:!opacity-100 hover:bg-red-500/10 hover:text-red-500 transition-all"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
              <p className="text-xs text-[var(--color-text-secondary)] line-clamp-3 mb-2">{note.content}</p>
              <p className="text-xs text-[var(--color-text-secondary)] opacity-50">{formatDate(note.updated_at)}</p>
            </div>
          ))}
        </div>
      )}
      </div>
    </div>
  );
}
