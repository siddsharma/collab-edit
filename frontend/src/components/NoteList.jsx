import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { Header } from "./Header";
import "../styles/NoteList.css";

export function NoteList({ user }) {
  const [notes, setNotes] = useState([]);
  const [newTitle, setNewTitle] = useState("");
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

  useEffect(() => {
    fetchNotes();
  }, []);

  const fetchNotes = async () => {
    try {
      const response = await axios.get(`${API_URL}/notes`);
      setNotes(response.data);
      setLoading(false);
    } catch (error) {
      console.error("Error fetching notes:", error);
      setLoading(false);
    }
  };

  const handleCreateNote = async (e) => {
    e.preventDefault();
    if (!newTitle.trim()) return;

    try {
      const response = await axios.post(`${API_URL}/notes`, {
        title: newTitle.trim(),
      });
      setNewTitle("");
      setNotes([...notes, response.data]);
      navigate(`/notes/${response.data.id}`);
    } catch (error) {
      console.error("Error creating note:", error);
    }
  };

  const handleDeleteNote = async (e, noteId) => {
    e.stopPropagation();
    
    if (!window.confirm("Are you sure you want to delete this note?")) {
      return;
    }

    try {
      await axios.delete(`${API_URL}/notes/${noteId}`);
      setNotes(notes.filter((note) => note.id !== noteId));
    } catch (error) {
      console.error("Error deleting note:", error);
    }
  };

  if (loading) return <div className="notes-container"><p>Loading...</p></div>;

  return (
    <div className="notes-page">
      <Header user={user} />
      
      <div className="notes-container">
        <form onSubmit={handleCreateNote} className="create-note-form">
          <input
            type="text"
            placeholder="New note title..."
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            className="note-input"
          />
          <button type="submit" className="create-btn">
            Create Note
          </button>
        </form>

        <div className="notes-list">
          {notes.length === 0 ? (
            <p className="no-notes">No notes yet. Create one to get started!</p>
          ) : (
            notes.map((note) => (
              <div
                key={note.id}
                className="note-item"
                onClick={() => navigate(`/notes/${note.id}`)}
              >
                <div className="note-content">
                  <h3>{note.title}</h3>
                  <p className="note-date">
                    Updated: {new Date(note.updated_at).toLocaleDateString()}
                  </p>
                </div>
                <button
                  className="delete-btn"
                  onClick={(e) => handleDeleteNote(e, note.id)}
                  title="Delete note"
                >
                  ✕
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
