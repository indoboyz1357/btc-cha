"use client";

interface ToggleProps {
  checked: boolean;
  onChange: (v: boolean) => void;
  id?: string;
}

export default function Toggle({ checked, onChange, id }: ToggleProps) {
  return (
    <div
      id={id}
      className={`toggle-track ${checked ? "on" : ""}`}
      onClick={() => onChange(!checked)}
      role="switch"
      aria-checked={checked}
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && onChange(!checked)}
    >
      <div className="toggle-thumb" />
    </div>
  );
}
