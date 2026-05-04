export function getActiveSession(utcHour: number): string {
  if (utcHour >= 7 && utcHour < 16) return "London";
  if (utcHour >= 12 && utcHour < 21) return "New York";
  if (utcHour >= 0 && utcHour < 9)   return "Tokyo";
  return "Sydney";
}
