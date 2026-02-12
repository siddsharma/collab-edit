import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { auth } from "./firebaseConfig";
import { Login } from "./components/Login";
import { NoteList } from "./components/NoteList";
import { Editor } from "./components/Editor";
import "./App.css";

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = auth.onAuthStateChanged((currentUser) => {
      setUser(currentUser);
      setLoading(false);
    });
    return () => unsubscribe();
  }, []);

  if (loading) {
    return <div className="app-loader">Loading...</div>;
  }

  return (
    <Router>
      <Routes>
        <Route path="/" element={user ? <Navigate to="/notes" /> : <Login />} />
        <Route path="/notes" element={user ? <NoteList user={user} /> : <Navigate to="/" />} />
        <Route path="/notes/:noteId" element={user ? <Editor user={user} /> : <Navigate to="/" />} />
      </Routes>
    </Router>
  );
}

export default App;
