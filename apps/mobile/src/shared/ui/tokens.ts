export const color = {
  bgApp: "#f6f2ea",
  bgSurface: "#fffdf8",
  bgElevated: "#ffffff",
  bgMuted: "#f1ebdf",
  bgAccentSoft: "#ece6ff",
  bgBrandSoft: "#e3f1e8",
  bgInverse: "#2f211c",
  fgPrimary: "#2d211c",
  fgSecondary: "rgba(45, 33, 28, 0.72)",
  fgTertiary: "rgba(45, 33, 28, 0.48)",
  accentPrimary: "#3f8f63",
  accentContrast: "#ffffff",
  statusWarning: "#a06a22",
  statusError: "#b54738",
  statusSuccess: "#317e57",
  borderSubtle: "rgba(45, 33, 28, 0.08)",
  focusRing: "rgba(63, 143, 99, 0.18)",
} as const;

export const space = {
  s8: 8,
  s10: 10,
  s12: 12,
  s16: 16,
  s20: 20,
  s24: 24,
  s32: 32,
} as const;

export const radius = {
  card: 18,
  input: 18,
  panel: 28,
  pill: 999,
} as const;

export const tokens = {
  color,
  space,
  radius,
} as const;

