export default function Loading() {
  return (
    <div className="page">
      <div className="hero animate-pulse">
        <div className="heroCard">
          <div className="skeleton-header" style={{ width: "80%", height: "48px" }}></div>
          <div className="skeleton-line" style={{ width: "40%", height: "24px", marginTop: "16px" }}></div>
        </div>
        <div className="adminCard">
          <div className="skeleton-header"></div>
          <div className="skeleton-line short"></div>
          <div className="skeleton-line short" style={{ width: "50%" }}></div>
        </div>
      </div>
      <div className="sectionHeader">
        <div className="skeleton-header animate-pulse" style={{ width: "200px" }}></div>
      </div>
      <div className="bookGrid">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bookCard animate-pulse">
            <div className="coverTone skeleton-card" style={{ border: "none", borderRadius: "0" }}></div>
            <div className="bookMeta">
              <div className="skeleton-header"></div>
              <div className="skeleton-line"></div>
            </div>
            <div className="badgeRow">
              <div className="skeleton-line short" style={{ width: "30%" }}></div>
              <div className="skeleton-line short" style={{ width: "30%" }}></div>
            </div>
            <div className="bookTimestamp">
              <div className="skeleton-line short" style={{ marginTop: "12px", width: "40%" }}></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
