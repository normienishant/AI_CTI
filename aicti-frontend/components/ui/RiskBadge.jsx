'use client';

const RISK_COLORS = {
  Critical: '#dc2626',
  High: '#f97316',
  Medium: '#facc15',
  Low: '#16a34a',
};

export default function RiskBadge({ risk, style = {} }) {
  if (!risk || !risk.level) return null;
  const color = RISK_COLORS[risk.level] || '#2563eb';
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        background: 'rgba(15, 23, 42, 0.05)',
        color,
        padding: '4px 10px',
        borderRadius: 999,
        fontSize: '0.72rem',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '0.08em',
        ...style,
      }}
    >
      {risk.level}
    </span>
  );
}
