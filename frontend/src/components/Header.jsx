import { signOut } from "firebase/auth";
import { auth } from "../firebaseConfig";
import { useNavigate } from "react-router-dom";
import "../styles/Header.css";

export function Header({ user, noteName, showBack = false, onBack = null }) {
  const navigate = useNavigate();

  const handleSignOut = async () => {
    try {
      await signOut(auth);
      navigate("/");
    } catch (error) {
      console.error("Sign out error:", error);
    }
  };

  const handleBack = () => {
    if (onBack) {
      onBack();
    } else {
      navigate("/notes");
    }
  };

  return (
    <header className="app-header">
      <div className="header-left">
        {showBack && (
          <button onClick={handleBack} className="back-btn">
            ← Back
          </button>
        )}
        <div className="header-title">
          {noteName ? (
            <>
              <span className="note-name">{noteName}</span>
            </>
          ) : (
            <span className="page-title">Notes</span>
          )}
        </div>
      </div>

      <div className="header-right">
        <div className="user-info">
          <span className="user-email">{user?.email || "User"}</span>
        </div>
        <button onClick={handleSignOut} className="signout-btn">
          Sign Out
        </button>
      </div>
    </header>
  );
}
