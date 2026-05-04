export function getActiveSession(utcHour: number): string {
  if (utcHour >= 7 && utcHour < 16) return "London";
  if (utcHour >= 12 && utcHour < 21) return "New York";
  if (utcHour >= 0 && utcHour < 9)   return "Tokyo";
  return "Sydney";
}

export function formatPrice(price: number, decimals = 2): string {
  return price.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function formatChange(change: number, pct: number): string {
  const sign = change >= 0 ? "+" : "";
  return `${sign}${formatPrice(change)} (${sign}${pct.toFixed(2)}%)`;
}

export function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return iso;
  }
}

export function formatDateTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("id-ID", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
