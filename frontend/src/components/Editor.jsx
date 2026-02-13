import { useState, useEffect, useRef, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { auth } from "../firebaseConfig";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Collaboration from "@tiptap/extension-collaboration";
import Underline from "@tiptap/extension-underline";
import TextAlign from "@tiptap/extension-text-align";
import Highlight from "@tiptap/extension-highlight";
import { io } from "socket.io-client";
import axios from "axios";
import * as Y from "yjs";
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

function parseMsEnv(value, fallback) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback;
  }
  return parsed;
}

const YJS_SEND_DEBOUNCE_MS = parseMsEnv(import.meta.env.VITE_YJS_SEND_DEBOUNCE_MS, 1000);
const YJS_SEND_MAX_INTERVAL_MS = Math.max(
  YJS_SEND_DEBOUNCE_MS,
  parseMsEnv(import.meta.env.VITE_YJS_SEND_MAX_INTERVAL_MS, 5000)
);

function uint8ToBase64(bytes) {
  let binary = "";
  const chunkSize = 0x8000;

  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
  }

  return btoa(binary);
}

function base64ToUint8(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function VersionPreview({ yjsUpdates, onContentReady }) {
  const snapshotDoc = useMemo(() => {
    const doc = new Y.Doc();
    if (Array.isArray(yjsUpdates)) {
      for (const encodedUpdate of yjsUpdates) {
        try {
          Y.applyUpdate(doc, base64ToUint8(encodedUpdate), "history");
        } catch (error) {
          console.error("Failed to apply history update:", error);
        }
      }
    }
    return doc;
  }, [yjsUpdates]);

  useEffect(() => {
    return () => {
      snapshotDoc.destroy();
    };
  }, [snapshotDoc]);

  const previewEditor = useEditor({
    editable: false,
    extensions: [
      StarterKit.configure({
        history: false,
      }),
      Collaboration.configure({
        document: snapshotDoc,
        field: "default",
      }),
      Underline,
      TextAlign.configure({
        types: ["heading", "paragraph"],
      }),
      Highlight.configure({
        multicolor: false,
      }),
    ],
    content: "<p></p>",
  });

  if (!previewEditor) {
    return <p>Loading version preview...</p>;
  }

  useEffect(() => {
    if (!previewEditor || !onContentReady) return;
    onContentReady(previewEditor.getJSON());
  }, [previewEditor, yjsUpdates, onContentReady]);

  return <EditorContent editor={previewEditor} className="editor version-preview-editor" />;
}

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
  const [historyOpen, setHistoryOpen] = useState(false);
  const [versions, setVersions] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const [selectedVersionId, setSelectedVersionId] = useState("");
  const [selectedVersionTimestamp, setSelectedVersionTimestamp] = useState("");
  const [selectedVersionUpdates, setSelectedVersionUpdates] = useState([]);
  const [selectedVersionContent, setSelectedVersionContent] = useState(null);
  const [selectedVersionLoading, setSelectedVersionLoading] = useState(false);
  const [restoreLoading, setRestoreLoading] = useState(false);
  const pendingLocalUpdatesRef = useRef([]);
  const flushTimerRef = useRef(null);
  const maxFlushTimerRef = useRef(null);
  const initializedFromSnapshotRef = useRef(false);
  const skipNextUpdateRef = useRef(false);
  const didBootstrapSyncRef = useRef(false);
  const ydoc = useMemo(() => new Y.Doc(), [noteId]);

  useEffect(() => {
    initializedFromSnapshotRef.current = false;
    didBootstrapSyncRef.current = false;
    setHistoryOpen(false);
    setVersions([]);
    setHistoryError("");
    setSelectedVersionId("");
    setSelectedVersionTimestamp("");
    setSelectedVersionUpdates([]);
    setSelectedVersionContent(null);
  }, [noteId]);

  useEffect(() => {
    return () => {
      ydoc.destroy();
    };
  }, [ydoc]);

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

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        history: false,
      }),
      Collaboration.configure({
        document: ydoc,
        field: "default",
      }),
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
    onUpdate: () => {
      if (skipNextUpdateRef.current) {
        skipNextUpdateRef.current = false;
        return;
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
          if (!initializedFromSnapshotRef.current) {
            const content = data.content || { type: "doc", content: [{ type: "paragraph" }] };
            skipNextUpdateRef.current = true;
            editor.commands.setContent(content);
            initializedFromSnapshotRef.current = true;
          }

          if (Array.isArray(data.yjs_updates) && data.yjs_updates.length > 0) {
            for (const encodedUpdate of data.yjs_updates) {
              try {
                const updateBytes = base64ToUint8(encodedUpdate);
                skipNextUpdateRef.current = true;
                Y.applyUpdate(ydoc, updateBytes, "remote");
              } catch (error) {
                console.error("Failed to apply replayed Yjs update:", error);
              }
            }
          }

          if (!didBootstrapSyncRef.current) {
            const fullStateUpdate = Y.encodeStateAsUpdate(ydoc);
            newSocket.emit("yjs_update", {
              note_id: noteId,
              update: uint8ToBase64(fullStateUpdate),
            });
            didBootstrapSyncRef.current = true;
          }

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

      newSocket.on("yjs_update", (data) => {
        if (!data?.update) return;

        try {
          const updateBytes = base64ToUint8(data.update);
          skipNextUpdateRef.current = true;
          Y.applyUpdate(ydoc, updateBytes, "remote");
        } catch (error) {
          console.error("Failed to apply Yjs update:", error);
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
  }, [noteId, editor, ydoc]); // Only reinitialize when note/editor changes

  useEffect(() => {
    if (!socket || !connected || !isReady) return;

    const clearFlushTimers = () => {
      if (flushTimerRef.current) {
        clearTimeout(flushTimerRef.current);
        flushTimerRef.current = null;
      }
      if (maxFlushTimerRef.current) {
        clearTimeout(maxFlushTimerRef.current);
        maxFlushTimerRef.current = null;
      }
    };

    const flushQueuedUpdates = () => {
      if (!pendingLocalUpdatesRef.current.length) return;
      if (!socket.connected) return;

      let merged;
      try {
        merged = Y.mergeUpdates(pendingLocalUpdatesRef.current);
      } catch (error) {
        console.error("Failed to merge Yjs updates:", error);
        pendingLocalUpdatesRef.current = [];
        clearFlushTimers();
        return;
      }

      pendingLocalUpdatesRef.current = [];
      clearFlushTimers();
      socket.emit("yjs_update", {
        note_id: noteId,
        update: uint8ToBase64(merged),
      });
    };

    const scheduleFlush = () => {
      if (flushTimerRef.current) {
        clearTimeout(flushTimerRef.current);
      }
      flushTimerRef.current = setTimeout(flushQueuedUpdates, YJS_SEND_DEBOUNCE_MS);

      if (!maxFlushTimerRef.current) {
        maxFlushTimerRef.current = setTimeout(flushQueuedUpdates, YJS_SEND_MAX_INTERVAL_MS);
      }
    };

    const onYjsUpdate = (update, origin) => {
      if (origin === "remote") return;
      pendingLocalUpdatesRef.current.push(update);
      scheduleFlush();
    };

    const onVisibilityChange = () => {
      if (document.visibilityState === "hidden") {
        flushQueuedUpdates();
      }
    };

    const onPageHide = () => {
      flushQueuedUpdates();
    };

    ydoc.on("update", onYjsUpdate);
    document.addEventListener("visibilitychange", onVisibilityChange);
    window.addEventListener("pagehide", onPageHide);
    if (pendingLocalUpdatesRef.current.length > 0) {
      scheduleFlush();
    }

    return () => {
      flushQueuedUpdates();
      clearFlushTimers();
      ydoc.off("update", onYjsUpdate);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      window.removeEventListener("pagehide", onPageHide);
    };
  }, [socket, connected, isReady, noteId, ydoc]);

  const openVersionHistory = async () => {
    try {
      setHistoryOpen(true);
      setHistoryLoading(true);
      setHistoryError("");

      const response = await axios.get(`${API_URL}/notes/${noteId}/versions`, {
        params: { limit: 200 },
      });
      const fetchedVersions = Array.isArray(response.data) ? response.data : [];
      setVersions(fetchedVersions);

      if (fetchedVersions.length > 0) {
        const firstVersionId = fetchedVersions[0].id;
        await loadVersionSnapshot(firstVersionId);
      } else {
        setSelectedVersionId("");
        setSelectedVersionTimestamp("");
        setSelectedVersionUpdates([]);
        setSelectedVersionContent(null);
      }
    } catch (error) {
      console.error("Failed to load version history:", error);
      setHistoryError("Failed to load version history.");
    } finally {
      setHistoryLoading(false);
    }
  };

  const loadVersionSnapshot = async (versionId) => {
    if (!versionId) return;
    try {
      setSelectedVersionLoading(true);
      setSelectedVersionId(versionId);

      const response = await axios.get(`${API_URL}/notes/${noteId}/versions/${versionId}`);
      setSelectedVersionUpdates(Array.isArray(response.data?.yjs_updates) ? response.data.yjs_updates : []);
      setSelectedVersionTimestamp(response.data?.version_timestamp || "");
    } catch (error) {
      console.error("Failed to load version snapshot:", error);
      setHistoryError("Failed to load selected version.");
    } finally {
      setSelectedVersionLoading(false);
    }
  };

  const restoreSelectedVersion = async () => {
    if (!selectedVersionId || !selectedVersionContent || !editor) return;
    try {
      setRestoreLoading(true);
      setHistoryError("");

      await axios.post(`${API_URL}/notes/${noteId}/versions/${selectedVersionId}/restore`, {
        user_id: user?.uid || null,
        user_name: user?.email || user?.displayName || user?.uid || null,
      });

      editor.commands.setContent(selectedVersionContent);
      setHistoryOpen(false);
    } catch (error) {
      console.error("Failed to restore version:", error);
      setHistoryError("Failed to restore selected version.");
    } finally {
      setRestoreLoading(false);
    }
  };

  if (!editor) {
    return <div className="editor-container"><p>Loading editor...</p></div>;
  }

  return (
    <div className="editor-page">
      <Header
        user={user}
        noteName={noteName}
        showBack={true}
        onBack={() => navigate("/notes")}
        onVersionHistory={openVersionHistory}
      />

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

      {historyOpen && (
        <div className="version-history-overlay">
          <div className="version-history-modal">
            <div className="version-history-header">
              <h3>Version History</h3>
              <div className="version-history-actions">
                <button
                  className="toolbar-button"
                  onClick={restoreSelectedVersion}
                  disabled={!selectedVersionId || !selectedVersionContent || selectedVersionLoading || restoreLoading}
                >
                  {restoreLoading ? "Restoring..." : "Restore this version"}
                </button>
                <button
                  className="toolbar-button"
                  onClick={() => setHistoryOpen(false)}
                >
                  Close
                </button>
              </div>
            </div>

            {historyError && <p className="version-history-error">{historyError}</p>}

            <div className="version-history-body">
              <div className="version-history-list">
                {historyLoading ? (
                  <p>Loading versions...</p>
                ) : (
                  versions.map((version) => (
                    <button
                      key={version.id}
                      className={`version-item ${selectedVersionId === version.id ? "active" : ""}`}
                      onClick={() => loadVersionSnapshot(version.id)}
                    >
                      <span>{new Date(version.timestamp).toLocaleString()}</span>
                      <span>{version.user_name || version.user_id}</span>
                    </button>
                  ))
                )}
                {!historyLoading && versions.length === 0 && (
                  <p>No versions found for this note.</p>
                )}
              </div>

              <div className="version-history-preview">
                {selectedVersionLoading ? (
                  <p>Loading snapshot...</p>
                ) : selectedVersionId ? (
                  <>
                    <p className="version-selected-time">
                      Snapshot: {selectedVersionTimestamp ? new Date(selectedVersionTimestamp).toLocaleString() : ""}
                    </p>
                    <VersionPreview
                      yjsUpdates={selectedVersionUpdates}
                      onContentReady={setSelectedVersionContent}
                    />
                  </>
                ) : (
                  <p>Select a version to preview.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
