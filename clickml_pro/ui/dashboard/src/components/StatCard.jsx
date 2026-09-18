export default function StatCard({ label, value, sub, color = '', icon: Icon }) {
  return (
    <div className={`stat-card ${color}`}>
      <div className="stat-header">
        <div className="stat-label">{label}</div>
        {Icon && (
          <div className="stat-icon">
            <Icon size={16} />
          </div>
        )}
      </div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}
