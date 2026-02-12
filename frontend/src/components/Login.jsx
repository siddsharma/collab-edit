import { signInWithPopup, GoogleAuthProvider, signOut } from "firebase/auth";
import { auth } from "../firebaseConfig";
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "../styles/Login.css";

export function Login() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [debugInfo, setDebugInfo] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const config = {
      projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
      authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
      apiKey: import.meta.env.VITE_FIREBASE_API_KEY ? "SET" : "MISSING",
    };
    setDebugInfo(config);
    console.log("Firebase config:", config);
    
    const unsubscribe = auth.onAuthStateChanged((currentUser) => {
      setUser(currentUser);
      setLoading(false);
      if (currentUser) {
        navigate("/notes");
      }
    });
    return () => unsubscribe();
  }, [navigate]);

  const handleGoogleSignIn = async () => {
    try {
      console.log("Starting Google sign in...");
      const provider = new GoogleAuthProvider();
      const result = await signInWithPopup(auth, provider);
      console.log("Sign in success:", result.user.email);
    } catch (error) {
      console.error("Sign in error:", error);
      setError(error.message || error.toString());
    }
  };

  if (loading) {
    return <div className="login-container"><p>Loading...</p></div>;
  }

  return (
    <div className="login-container">
      <div className="login-box">
        <h1>Collaborative Notes</h1>
        <p>Edit notes together in real-time</p>
        {error && <p style={{ color: "red", marginBottom: "20px", fontSize: "14px" }}>{error}</p>}
        {debugInfo && (
          <div style={{ 
            backgroundColor: "#f0f0f0", 
            padding: "10px", 
            borderRadius: "5px", 
            marginBottom: "20px",
            fontSize: "12px",
            color: "#333"
          }}>
            <strong>Debug Info:</strong>
            <div>projectId: {debugInfo.projectId}</div>
            <div>authDomain: {debugInfo.authDomain}</div>
            <div>apiKey: {debugInfo.apiKey}</div>
          </div>
        )}
        <button onClick={handleGoogleSignIn} className="google-signin-btn">
          Sign in with Google
        </button>
      </div>
    </div>
  );
}

