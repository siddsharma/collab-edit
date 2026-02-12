import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

console.log("Raw Firebase config:", firebaseConfig);
console.log("Firebase config being loaded:", {
  apiKey: firebaseConfig.apiKey ? "SET" : "MISSING",
  authDomain: firebaseConfig.authDomain ? "SET" : "MISSING",
  projectId: firebaseConfig.projectId ? "SET" : "MISSING",
  storageBucket: firebaseConfig.storageBucket ? "SET" : "MISSING",
  messagingSenderId: firebaseConfig.messagingSenderId ? "SET" : "MISSING",
  appId: firebaseConfig.appId ? "SET" : "MISSING",
});

// Check for missing required fields
const requiredFields = ['apiKey', 'authDomain', 'projectId'];
const missingFields = requiredFields.filter(field => !firebaseConfig[field]);

if (missingFields.length > 0) {
  console.warn("⚠️ Missing Firebase config fields:", missingFields);
}

let app;
let auth;

try {
  if (missingFields.length === 0) {
    app = initializeApp(firebaseConfig);
    auth = getAuth(app);
    console.log("✓ Firebase initialized successfully");
  } else {
    console.error("❌ Cannot initialize Firebase - missing required fields:", missingFields);
    throw new Error(`Missing Firebase config: ${missingFields.join(', ')}`);
  }
} catch (error) {
  console.error("❌ Failed to initialize Firebase:", error.message || error);
}

export { auth };
