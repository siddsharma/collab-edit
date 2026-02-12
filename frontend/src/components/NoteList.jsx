import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { auth } from "../firebaseConfig";
import { signOut } from "firebase/auth";
import axios from "axios";
import "../styles/NoteList.css";

export function NoteList() {
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
      const response = await axios.post(
        `${API_URL}/notes?title=${encodeURIComponent(newTitle)}`
      );
      setNewTitle("");
      setNotes([...notes, response.data]);
      navigate(`/notes/${response.data.id}`);
    } catch (error) {
      console.error("Error creating note:", error);
    }
  };

  const handleSignOut = async () => {
    try {
      await signOut(auth);
      navigate("/");
    } catch (error) {
      console.error("Sign out error:", error);
    }
  };

  if (loading) return <div className="notes-container"><p>Loading...</p></div>;

  return (
    <div className="notes-container">
      <div className="header">
        <h1>My Notes</h1>
        <button onClick={handleSignOut} className="signout-btn">
          Sign Out
        </button>
      </div>

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
              <h3>{note.title}</h3>
              <p className="note-date">
                Updated: {new Date(note.updated_at).toLocaleDateString()}
              </p>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
