export default function MetricCard({title, value, color}) {
  return (
    <div className="card w-full">
      <div className="kicker">{title}</div>
      <div className="mt-3" style={{fontSize: '2rem', fontWeight:700, color: color || '#5ce1ff'}}>{value}</div>
    </div>
  );
}
