import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { auth } from "../firebaseConfig";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import TextAlign from "@tiptap/extension-text-align";
import Highlight from "@tiptap/extension-highlight";
import { io } from "socket.io-client";
import axios from "axios";
import { Header } from "./Header";
import { ActiveUsers } from "./ActiveUsers";
import "../styles/Editor.css";

// Toolbar component
function Toolbar({ editor }) {
  if (!editor) return null;

  const buttonClass = (isActive) =>
    `toolbar-button ${isActive ? "active" : ""}`;

  return (
    <div className="editor-toolbar">
      <div className="toolbar-group">
        <button
          className={buttonClass(editor.isActive("bold"))}
          onClick={() => editor.chain().focus().toggleBold().run()}
          title="Bold (Cmd+B)"
        >
          <strong>B</strong>
        </button>
        <button
          className={buttonClass(editor.isActive("italic"))}
          onClick={() => editor.chain().focus().toggleItalic().run()}
          title="Italic (Cmd+I)"
        >
          <em>I</em>
        </button>
        <button
          className={buttonClass(editor.isActive("underline"))}
          onClick={() => editor.chain().focus().toggleUnderline().run()}
          title="Underline (Cmd+U)"
        >
          <u>U</u>
        </button>
        <button
          className={buttonClass(editor.isActive("strike"))}
          onClick={() => editor.chain().focus().toggleStrike().run()}
          title="Strikethrough"
        >
          <s>S</s>
        </button>
      </div>

      <div className="toolbar-divider"></div>

      <div className="toolbar-group">
        <button
          className={buttonClass(editor.isActive("heading", { level: 1 }))}
          onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
          title="Heading 1"
        >
          H1
        </button>
        <button
          className={buttonClass(editor.isActive("heading", { level: 2 }))}
          onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
          title="Heading 2"
        >
          H2
        </button>
        <button
          className={buttonClass(editor.isActive("heading", { level: 3 }))}
          onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
          title="Heading 3"
        >
          H3
        </button>
      </div>

      <div className="toolbar-divider"></div>

      <div className="toolbar-group">
        <button
          className={buttonClass(editor.isActive("bulletList"))}
          onClick={() => editor.chain().focus().toggleBulletList().run()}
          title="Bullet List"
        >
          • List
        </button>
        <button
          className={buttonClass(editor.isActive("orderedList"))}
          onClick={() => editor.chain().focus().toggleOrderedList().run()}
          title="Ordered List"
        >
          1. List
        </button>
        <button
          className={buttonClass(editor.isActive("blockquote"))}
          onClick={() => editor.chain().focus().toggleBlockquote().run()}
          title="Quote"
        >
          « "
        </button>
      </div>

      <div className="toolbar-divider"></div>

      <div className="toolbar-group">
        <button
          className={buttonClass(editor.isActive("codeBlock"))}
          onClick={() => editor.chain().focus().toggleCodeBlock().run()}
          title="Code Block"
        >
          {`</>`}
        </button>
        <button
          className={buttonClass(editor.isActive("highlight"))}
          onClick={() => editor.chain().focus().toggleHighlight().run()}
          title="Highlight"
        >
          🖍️
        </button>
      </div>

      <div className="toolbar-divider"></div>

      <div className="toolbar-group">
        <button
          onClick={() => editor.chain().focus().setTextAlign("left").run()}
          className={buttonClass(editor.isActive({ textAlign: "left" }))}
          title="Align Left"
        >
          ◀
        </button>
        <button
          onClick={() => editor.chain().focus().setTextAlign("center").run()}
          className={buttonClass(editor.isActive({ textAlign: "center" }))}
          title="Align Center"
        >
          ▮▮
        </button>
        <button
          onClick={() => editor.chain().focus().setTextAlign("right").run()}
          className={buttonClass(editor.isActive({ textAlign: "right" }))}
          title="Align Right"
        >
          ▶
        </button>
      </div>

      <div className="toolbar-divider"></div>

      <div className="toolbar-group">
        <button
          onClick={() => editor.chain().focus().undo().run()}
          disabled={!editor.can().undo()}
          title="Undo"
        >
          ↶ Undo
        </button>
        <button
          onClick={() => editor.chain().focus().redo().run()}
          disabled={!editor.can().redo()}
          title="Redo"
        >
          ↷ Redo
        </button>
      </div>
      <div className="toolbar-divider"></div>
      <button
        onClick={() => editor.chain().focus().clearNodes().run()}
        title="Clear formatting"
        className="toolbar-button"
      >
        ✕ Clear
      </button>
    </div>
  );
}

const SOCKET_URL = import.meta.env.VITE_SOCKET_URL || "http://localhost:8000";
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const SAVE_DEBOUNCE_MS = 1500;
const SAVE_MAX_INTERVAL_MS = 10000;

export function Editor({ user }) {
  const { noteId } = useParams();
  const navigate = useNavigate();
  const [activeUsers, setActiveUsers] = useState([]);
  const [socket, setSocket] = useState(null);
  const socketRef = useRef(null);
  const [connected, setConnected] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const initializingRef = useRef(false);
  const [noteName, setNoteName] = useState("");
  const [noteLoading, setNoteLoading] = useState(true);
  const saveTimerRef = useRef(null);
  const latestContentRef = useRef(null);
  const lastSavedContentRef = useRef("");
  const lastSaveAtRef = useRef(Date.now());

  // Fetch note details to get the title
  useEffect(() => {
    const fetchNoteDetails = async () => {
      try {
        const response = await axios.get(`${API_URL}/notes/${noteId}`);
        setNoteName(response.data.title);
        setNoteLoading(false);
      } catch (error) {
        console.error("Error fetching note details:", error);
        setNoteLoading(false);
      }
    };

    fetchNoteDetails();
  }, [noteId]);

  const saveNote = useCallback(
    async ({ keepalive = false, reason = "autosave" } = {}) => {
      if (!noteId || !latestContentRef.current) return;

      const nextSerialized = JSON.stringify(latestContentRef.current);
      if (nextSerialized === lastSavedContentRef.current) return;

      const payload = JSON.stringify({ content: latestContentRef.current });
      const url = `${API_URL}/notes/${noteId}`;

      try {
        if (keepalive) {
          fetch(url, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: payload,
            keepalive: true,
          });
          return;
        }

        await axios.put(url, { content: latestContentRef.current });
        lastSavedContentRef.current = nextSerialized;
        lastSaveAtRef.current = Date.now();
      } catch (error) {
        console.error(`Error saving note (${reason}):`, error);
      }
    },
    [noteId]
  );

  const scheduleAutosave = useCallback(() => {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
    }
    saveTimerRef.current = setTimeout(() => {
      void saveNote({ reason: "debounce" });
    }, SAVE_DEBOUNCE_MS);
  }, [saveNote]);

  const editor = useEditor({
    extensions: [
      StarterKit,
      Underline,
      TextAlign.configure({
        types: ["heading", "paragraph"],
      }),
      Highlight.configure({
        multicolor: false,
      }),
    ],
    content: "<p></p>",
    editable: true,
    onCreate: ({ editor }) => {
      console.log("Editor created, editable:", editor.isEditable);
    },
    onUpdate: ({ editor }) => {
      const content = editor.getJSON();
      latestContentRef.current = content;
      console.log("Editor updated, socket:", !!socket, "connected:", connected, "isReady:", isReady);
      if (socket && connected && isReady) {
        console.log("Sending update to backend");
        socket.emit("update_note", {
          note_id: noteId,
          delta: content,
        });
      }
      scheduleAutosave();
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
          latestContentRef.current = content;
          lastSavedContentRef.current = JSON.stringify(content);
          lastSaveAtRef.current = Date.now();

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
            latestContentRef.current = data.content;
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

  useEffect(() => {
    if (!editor || !isReady) return;

    const interval = setInterval(() => {
      const hasUnsaved =
        latestContentRef.current &&
        JSON.stringify(latestContentRef.current) !== lastSavedContentRef.current;
      const staleSave = Date.now() - lastSaveAtRef.current >= SAVE_MAX_INTERVAL_MS;

      if (hasUnsaved && staleSave) {
        void saveNote({ reason: "checkpoint" });
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [editor, isReady, saveNote]);

  useEffect(() => {
    const flush = () => {
      void saveNote({ keepalive: true, reason: "lifecycle" });
    };

    const onVisibilityChange = () => {
      if (document.visibilityState === "hidden") {
        flush();
      }
    };

    window.addEventListener("pagehide", flush);
    window.addEventListener("beforeunload", flush);
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      window.removeEventListener("pagehide", flush);
      window.removeEventListener("beforeunload", flush);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }
    };
  }, [saveNote]);

  if (!editor) {
    return <div className="editor-container"><p>Loading editor...</p></div>;
  }

  return (
    <div className="editor-page">
      <Header user={user} noteName={noteName} showBack={true} onBack={() => navigate("/notes")} />

      <div className="editor-container">
        <div className="editor-status">
          <span className={`status-indicator ${connected ? "connected" : "disconnected"}`}>
            {connected ? "Connected" : "Disconnected"}
          </span>
        </div>

        <Toolbar editor={editor} />

        <ActiveUsers users={activeUsers} />

        <div className="editor-wrapper">
          <EditorContent editor={editor} className="editor" />
        </div>
      </div>
    </div>
  );
}
