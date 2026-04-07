export const color = {
  bgApp: "#f5f5f7",
  bgSurface: "#ffffff",
  bgElevated: "#ffffff",
  bgInverse: "#1d1d1f",
  fgPrimary: "#1d1d1f",
  fgSecondary: "rgba(29, 29, 31, 0.72)",
  fgTertiary: "rgba(29, 29, 31, 0.48)",
  accentPrimary: "#0071e3",
  statusWarning: "#b26b00",
  statusError: "#c62828",
  statusSuccess: "#1f8f4c",
  borderSubtle: "rgba(29, 29, 31, 0.08)",
  focusRing: "rgba(0, 113, 227, 0.22)",
} as const;

export const space = {
  s8: 8,
  s12: 12,
  s16: 16,
  s20: 20,
  s24: 24,
  s32: 32,
} as const;

export const radius = {
  card: 12,
  input: 12,
  panel: 18,
  pill: 999,
} as const;

export const tokens = {
  color,
  space,
  radius,
} as const;

