import { useEffect, useId, useRef, useState } from 'react';

type Item = { label: string; action: () => void; danger?: boolean };
export default function Menu({ label, text = '···', items, disabled = false, className = '' }: {
  label: string; text?: string; items: Item[]; disabled?: boolean; className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const popup = useRef<HTMLDivElement>(null);
  const id = useId();
  function close() { setOpen(false); trigger.current?.focus(); }
  useEffect(() => {
    if (!open) return;
    const rect = trigger.current?.getBoundingClientRect();
    if (rect) {
      const height = items.length * 42 + 16;
      setPosition({ top: rect.bottom + height + 8 < window.innerHeight ? rect.bottom + 6 : Math.max(8, rect.top - height - 6),
        left: Math.max(8, Math.min(rect.left, window.innerWidth - 252)) });
    }
    popup.current?.querySelector('button')?.focus();
    function outside(event: PointerEvent) {
      if (event.target instanceof Node && !root.current?.contains(event.target)) setOpen(false);
    }
    document.addEventListener('pointerdown', outside);
    return () => document.removeEventListener('pointerdown', outside);
  }, [open]);
  useEffect(() => { if (disabled) setOpen(false); }, [disabled]);
  return <div ref={root} className={`popup-anchor ${className}`} onKeyDown={(e) => {
    if (e.key === 'Escape') { e.stopPropagation(); close(); }
    if (open && ['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(e.key)) {
      e.preventDefault();
      const buttons = Array.from(popup.current?.querySelectorAll('button') ?? []);
      const current = buttons.findIndex((b) => b === document.activeElement);
      const index = e.key === 'Home' ? 0 : e.key === 'End' ? buttons.length - 1
        : (current + (e.key === 'ArrowDown' ? 1 : -1) + buttons.length) % buttons.length;
      buttons[index]?.focus();
    }
  }}>
    <button ref={trigger} type="button" className="quiet menu-trigger" aria-label={label}
      aria-haspopup="menu" aria-expanded={open} aria-controls={open ? id : undefined} disabled={disabled}
      onKeyDown={(e) => { if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); } }}
      onClick={() => setOpen(!open)}>{text}</button>
    {open && <div ref={popup} id={id} role="menu" aria-label={label} className="popup-menu" style={position}
      onBlur={(e) => { if (!root.current?.contains(e.relatedTarget)) setOpen(false); }}>
      {items.map((item) => <button key={item.label} type="button" role="menuitem"
        className={item.danger ? 'danger' : ''} onClick={() => { close(); item.action(); }}>{item.label}</button>)}
    </div>}
  </div>;
}
