import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { auth } from "../firebaseConfig";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { io } from "socket.io-client";
import { ActiveUsers } from "./ActiveUsers";
import "../styles/Editor.css";

const SOCKET_URL = import.meta.env.VITE_SOCKET_URL || "http://localhost:8000";

export function Editor() {
  const { noteId } = useParams();
  const navigate = useNavigate();
  const [activeUsers, setActiveUsers] = useState([]);
  const [socket, setSocket] = useState(null);
  const socketRef = useRef(null);
  const [connected, setConnected] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const initializingRef = useRef(false);

  const editor = useEditor({
    extensions: [StarterKit],
    content: "<p></p>",
    editable: true,
    onCreate: ({ editor }) => {
      console.log("Editor created, editable:", editor.isEditable);
    },
    onUpdate: ({ editor }) => {
      console.log("Editor updated, socket:", !!socket, "connected:", connected, "isReady:", isReady);
      if (socket && connected && isReady) {
        console.log("Sending update to backend");
        socket.emit("update_note", {
          delta: editor.getJSON(),
        });
      }
    },
  });

  // Initialize socket connection
  useEffect(() => {
    if (!editor) return;
    if (initializingRef.current) return; // Prevent duplicate connections

    initializingRef.current = true;

    const initSocket = async () => {
      const token = await auth.currentUser?.getIdToken();
      const newSocket = io(SOCKET_URL, {
        auth: { token },
      });

      newSocket.on("connect", () => {
        console.log("Connected to server");
        setConnected(true);
        newSocket.emit("join_note", {
          token,
          note_id: noteId,
        });
      });

      newSocket.on("load_note", (data) => {
        console.log("Loading note:", data);
        console.log("Raw active_users:", data.active_users);
        console.log("User names mapping:", data.user_names);
        if (editor) {
          // Set content or default to empty if not provided
          const content = data.content || { type: "doc", content: [{ type: "paragraph" }] };
          editor.commands.setContent(content);

          // Set active users if provided (deduplicate by user ID)
          if (data.active_users) {
            const uniqueUsers = [...new Set(data.active_users)];
            console.log("After deduplication:", uniqueUsers);
            const user_names = data.user_names || {};
            setActiveUsers(
              uniqueUsers.map((userId) => ({
                id: userId,
                name: user_names[userId] || userId,
              }))
            );
          }

          setIsReady(true);
          console.log("Editor is ready");
        }
      });

      newSocket.on("user_joined", (data) => {
        console.log("User joined event:", data);
        console.log("Raw active_users:", data.active_users);
        console.log("User names mapping:", data.user_names);
        // Deduplicate users by user ID
        const uniqueUsers = [...new Set(data.active_users)];
        console.log("After deduplication:", uniqueUsers);

        // Update all active users with the new list using user_names mapping
        const user_names = data.user_names || {};
        setActiveUsers(
          uniqueUsers.map((userId) => ({
            id: userId,
            name: user_names[userId] || userId,
          }))
        );
      });

      newSocket.on("user_left", (data) => {
        console.log("User left event:", data);
        console.log("User names mapping:", data.user_names);
        // Deduplicate users by user ID
        const uniqueUsers = [...new Set(data.active_users)];
        const user_names = data.user_names || {};
        setActiveUsers(
          uniqueUsers.map((userId) => ({
            id: userId,
            name: user_names[userId] || userId,
          }))
        );
      });

      newSocket.on("note_updated", (data) => {
        console.log("Received remote update:", data);
        if (data.content && editor) {
          const currentJSON = JSON.stringify(editor.getJSON());
          const newJSON = JSON.stringify(data.content);

          if (currentJSON !== newJSON) {
            editor.commands.setContent(data.content);
          }
        }
      });

      newSocket.on("disconnect", () => {
        console.log("Disconnected from server");
        setConnected(false);
      });

      // keep a ref to the socket so cleanup can access the latest instance
      socketRef.current = newSocket;
      setSocket(newSocket);
    };

    initSocket();

    return () => {
      const s = socketRef.current;
      if (s) {
        console.log("Cleaning up socket connection");
        try {
          s.disconnect();
        } catch (e) {
          console.warn("Error disconnecting socket:", e);
        }
        socketRef.current = null;
        setSocket(null);
      }
      initializingRef.current = false;
    };
  }, [noteId]); // Only reinitialize when noteId changes

  if (!editor) {
    return <div className="editor-container"><p>Loading editor...</p></div>;
  }

  return (
    <div className="editor-container">
      <div className="editor-header">
        <button onClick={() => navigate("/notes")} className="back-btn">
          ← Back
        </button>
        <div className="status">
          <span className={`status-indicator ${connected ? "connected" : "disconnected"}`}>
            {connected ? "Connected" : "Disconnected"}
          </span>
        </div>
      </div>

      <ActiveUsers users={activeUsers} />

      <div className="editor-wrapper">
        <EditorContent editor={editor} className="editor" />
      </div>
    </div>
  );
}
