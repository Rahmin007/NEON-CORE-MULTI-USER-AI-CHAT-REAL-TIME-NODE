export default function Brand({ compact = false }) {
  return (
    <div className="select-none">
      <p className={`font-display font-extrabold tracking-[0.12em] text-cyan ${compact ? 'text-lg' : 'text-2xl'}`}>
        NEON<span className="text-pink">{'//'}</span>CORE
      </p>
      {!compact && <p className="font-display text-[9px] tracking-[0.3em] text-muted">MULTI-USER AI CHAT · REAL-TIME NODE</p>}
    </div>
  );
}
