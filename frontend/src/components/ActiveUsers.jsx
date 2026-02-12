import "../styles/ActiveUsers.css";

export function ActiveUsers({ users }) {
  return (
    <div className="active-users-container">
      <h3>Active Users ({users.length})</h3>
      <div className="active-users-list">
        {users.length === 0 ? (
          <p className="no-users">No other users editing</p>
        ) : (
          users.map((user) => (
            <div key={user.id} className="user-badge" title={user.name || user.id}>
              <span className="user-avatar">{user.name?.charAt(0) || "?"}</span>
              <span className="user-name">{user.name || "Anonymous"}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
